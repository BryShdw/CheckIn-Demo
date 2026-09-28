import base64
import io
import logging
import cv2
import numpy as np
from flask import Blueprint, request, jsonify, send_file, send_from_directory
from flask_login import current_user

from app.config import Config
from app.extensions import db, csrf
from app.models.guest import Guest
from app.services.guest_service import (
    get_or_create_active_event,
    get_kiosk_settings,
    update_kiosk_settings,
    find_guest,
    list_guests,
    create_guest,
    delete_guest,
    reset_all_checkins,
    get_event_stats,
)
from app.services.checkin_service import process_checkin
from app.services.printer_service import (
    get_printer_connection_status,
    purge_printer_queue,
    build_label_image,
    print_guest_ticket,
)
from app.services.face_service import (
    match_face,
    enroll_guest_face,
    delete_guest_face,
    delete_all_enrolled_faces,
    get_enrolled_counts,
)
from app.services.import_service import sync_onedrive_link
from app.services.audit_service import log_audit

log = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

# Eximir endpoints de cámara / kiosko del token CSRF (ya que envían peticiones fetch/AJAX desde el tótem en pantalla completa)
csrf.exempt(api_bp)


# ── Estado del Sistema ───────────────────────────────────────────────────────

@api_bp.route("/status")
def api_status():
    event = get_or_create_active_event()
    k_settings = get_kiosk_settings(event.id)
    stats = get_event_stats(event.id)
    printer = get_printer_connection_status()

    return jsonify({
        "status": "ok",
        "event_id": event.id,
        "event_name": event.name,
        "guest_count": stats["total"],
        "data_source": "mysql",
        "printer": printer,
        "kiosk_settings": k_settings.to_dict(),
        "stats": stats,
    })


@api_bp.route("/kiosk-settings", methods=["GET", "POST"])
def api_kiosk_settings():
    event = get_or_create_active_event()
    if request.method == "POST":
        data = request.get_json() or {}
        for key in ["method", "mode", "face_threshold"]:
            if key in data:
                update_kiosk_settings(key, data[key], event.id)

    setting = get_kiosk_settings(event.id)
    return jsonify({
        "status": "ok",
        "settings": setting.to_dict(),
    })


# ── Consultas y CRUD de Invitados ───────────────────────────────────────────

@api_bp.route("/guests")
def api_get_guests():
    event = get_or_create_active_event()
    guests = list_guests(event.id)
    return jsonify(guests)


@api_bp.route("/guest/<path:guest_id>", methods=["GET"])
def api_get_guest(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404
    return jsonify(guest.to_dict())


@api_bp.route("/guest", methods=["POST"])
def api_create_guest():
    data = request.get_json() or {}
    name = (data.get("name") or data.get("full_name") or "").strip()
    if not name:
        return jsonify({"error": "El nombre completo es obligatorio."}), 400

    event = get_or_create_active_event()
    guest = create_guest(
        full_name=name,
        company=data.get("company", ""),
        position=data.get("position", ""),
        guest_code=data.get("id"),
        email=data.get("email", ""),
        phone=data.get("phone", ""),
        category=data.get("category", "GENERAL"),
        event_id=event.id,
    )

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("GUEST_CREATE", user_id=user_id, target_type="GUEST", target_id=guest.guest_code,
              details=f"Invitado creado: {name}", ip_address=request.remote_addr)

    return jsonify({"status": "ok", "guest": guest.to_dict()}), 201


@api_bp.route("/guest/<guest_id>", methods=["DELETE"])
def api_delete_guest(guest_id):
    event = get_or_create_active_event()
    guest = find_guest(guest_id, event.id)
    if not guest:
        return jsonify({"error": f"Invitado con ID '{guest_id}' no encontrado."}), 404

    name = guest.full_name
    delete_guest_face(guest)
    delete_guest(guest_id, event.id)

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("GUEST_DELETE", user_id=user_id, target_type="GUEST", target_id=guest_id,
              details=f"Invitado eliminado: {name}", ip_address=request.remote_addr)

    return jsonify({"status": "ok", "message": f"Invitado '{name}' eliminado de la base de datos."})


# ── Check-In y Acreditación ─────────────────────────────────────────────────

@api_bp.route("/checkin", methods=["POST"])
def api_checkin():
    data = request.get_json() or {}
    guest_id = data.get("guest_id") or data.get("id") or data.get("code") or data.get("identifier")
    if not guest_id:
        return jsonify({"error": "Identificador de invitado no proporcionado."}), 400

    method = data.get("method", "QR").upper()
    force_reprint = bool(data.get("force_reprint", False))
    user_id = current_user.id if current_user.is_authenticated else None

    result, status_code = process_checkin(
        guest_code_or_url=guest_id,
        method=method,
        verified_by_user_id=user_id,
        ip_address=request.remote_addr,
        force_reprint=force_reprint,
    )
    return jsonify(result), status_code


@api_bp.route("/print/<path:guest_id>", methods=["POST"])
def api_print_ticket(guest_id):
    """
    Ruta de impresión directa del Kiosko:
    Imprime la etiqueta física y confirma el check-in en MySQL.
    """
    force = request.args.get("force", "").lower() in ("true", "1", "yes")
    req_json = request.get_json(silent=True) or {}
    if req_json.get("force"):
        force = True

    method = req_json.get("method", "KIOSK").upper()
    user_id = current_user.id if current_user.is_authenticated else None

    result, status_code = process_checkin(
        guest_code_or_url=guest_id,
        method=method,
        verified_by_user_id=user_id,
        ip_address=request.remote_addr,
        force_reprint=force,
    )

    if status_code == 200:
        return jsonify({
            "status": "ok",
            "success": True,
            "guest": result.get("guest"),
            "print": {"status": "ok", "message": result.get("message")},
            "message": result.get("message"),
        }), 200
    elif status_code == 409:
        return jsonify({
            "status": "already_registered",
            "already_checked_in": True,
            "guest": result.get("guest"),
            "print": {
                "status": "already_registered",
                "message": result.get("message"),
            },
            "message": result.get("message"),
        }), 200
    else:
        return jsonify({
            "status": "print_failed",
            "error": result.get("error", "Error procesando impresión/checkin"),
            "message": result.get("error", "Error procesando impresión/checkin"),
            "guest": result.get("guest"),
            "print": {"status": "error", "message": result.get("error")},
        }), status_code


# ── Reconocimiento y Enrolamiento Facial ─────────────────────────────────────

@api_bp.route("/facial-match", methods=["POST"])
def api_facial_match():
    data = request.get_json() or {}
    image_b64 = data.get("image")
    if not image_b64:
        return jsonify({"status": "error", "message": "No se recibió imagen"}), 400

    try:
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        img_bytes = base64.b64decode(image_b64)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img_bgr is None:
            return jsonify({"status": "error", "message": "Imagen no decodificable"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error decodificando imagen: {e}"}), 400

    event = get_or_create_active_event()
    k_settings = get_kiosk_settings(event.id)
    threshold = k_settings.face_threshold

    matched_code, similarity, bbox, top2_sim = match_face(img_bgr, threshold=threshold)

    if not matched_code:
        return jsonify({
            "status": "unmatched",
            "similarity": similarity,
            "bbox": bbox,
        })

    guest = find_guest(matched_code, event.id)
    if not guest:
        return jsonify({"status": "unmatched", "similarity": similarity, "bbox": bbox})

    return jsonify({
        "status": "matched",
        "guest": guest.to_dict(),
        "similarity": similarity,
        "bbox": bbox,
    })


@api_bp.route("/guest/<guest_id>/face", methods=["POST"])
def api_enroll_guest_face(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": f"Invitado con ID '{guest_id}' no encontrado"}), 404

    img_bgr = None
    if "image" in request.files:
        file = request.files["image"]
        img_bytes = file.read()
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    else:
        data = request.get_json() or {}
        image_b64 = data.get("image")
        if image_b64:
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(image_b64)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if img_bgr is None or img_bgr.size == 0:
        return jsonify({"error": "No se recibió una imagen válida"}), 400

    ok, msg, profile_dict = enroll_guest_face(guest, img_bgr)
    if not ok:
        return jsonify({"error": msg}), 400

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("FACE_ENROLL", user_id=user_id, target_type="GUEST", target_id=guest.guest_code,
              details=f"Foto facial enrolada para {guest.full_name}", ip_address=request.remote_addr)

    return jsonify({
        "status": "ok",
        "message": msg,
        "face": profile_dict,
        "guest": guest.to_dict(),
    })


@api_bp.route("/guest/<guest_id>/face", methods=["DELETE"])
def api_delete_guest_face_route(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": f"Invitado con ID '{guest_id}' no encontrado"}), 404

    image_id = request.args.get("image_id")
    delete_guest_face(guest, image_id)

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("FACE_DELETE", user_id=user_id, target_type="GUEST", target_id=guest.guest_code,
              details=f"Foto facial eliminada para {guest.full_name}", ip_address=request.remote_addr)

    return jsonify({
        "status": "ok",
        "message": "Fotos faciales eliminadas.",
        "guest": guest.to_dict(),
    })


@api_bp.route("/faces/delete-all", methods=["POST"])
def api_delete_all_faces():
    res = delete_all_enrolled_faces()
    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("FACE_PURGE_ALL", user_id=user_id, details=f"Eliminadas todas las fotos faciales ({res['deleted_count']} perfiles)", ip_address=request.remote_addr)
    return jsonify({
        "status": "ok",
        "message": f"Se han eliminado todas las fotos de enrolamiento ({res.get('deleted_count', 0)} perfiles reseteados).",
        "deleted_count": res.get("deleted_count", 0),
    })


@api_bp.route("/face-image/<guest_id>/<filename>")
def api_serve_face_image(guest_id, filename):
    guest_dir = Config.FACE_IMAGES_DIR / guest_id
    return send_from_directory(guest_dir, filename)


# ── Hardware e Impresión ────────────────────────────────────────────────────

@api_bp.route("/printer/status")
def api_printer_status():
    return jsonify(get_printer_connection_status())


@api_bp.route("/printer/purge-jobs", methods=["POST"])
def api_printer_purge():
    ok, msg = purge_printer_queue()
    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("PRINTER_PURGE", user_id=user_id, details=msg, ip_address=request.remote_addr)
    return jsonify({"status": "ok" if ok else "error", "message": msg}), 200 if ok else 400


@api_bp.route("/printer/test", methods=["POST"])
def api_printer_test():
    sample_guest = {
        "guest_code": "TEST-001",
        "full_name": "CARLOS ALBERTO MENDOZA SOTO",
        "company": "CORPORACIÓN ANDINA DE FOMENTO",
        "position": "DIRECTOR DE INNOVACIÓN Y TECNOLOGÍA",
    }
    ok, msg = print_guest_ticket(sample_guest)
    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("PRINTER_TEST", user_id=user_id, details=f"Prueba de impresión: {msg}", ip_address=request.remote_addr)
    return jsonify({"status": "ok" if ok else "error", "message": msg}), 200 if ok else 500


@api_bp.route("/label-preview/<path:guest_id>")
def api_label_preview(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404
    label_img = build_label_image(guest.to_dict())
    buf = io.BytesIO()
    label_img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


# ── Sincronización OneDrive y Reinicio de Asistencias ────────────────────────

@api_bp.route("/documents/add", methods=["POST"])
def api_add_onedrive_doc():
    data = request.get_json() or {}
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "URL de OneDrive requerida."}), 400

    event = get_or_create_active_event()
    ok, msg, count = sync_onedrive_link(url, event.id)
    if not ok:
        return jsonify({"error": msg}), 400

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("ONEDRIVE_SYNC", user_id=user_id, target_type="EVENT", target_id=str(event.id),
              details=f"Sincronizado OneDrive: {count} invitados", ip_address=request.remote_addr)

    return jsonify({"status": "ok", "message": msg, "guest_count": count})


@api_bp.route("/documents/sync", methods=["POST"])
def api_resync_onedrive():
    event = get_or_create_active_event()
    if not event.onedrive_url:
        return jsonify({"error": "No hay enlace de OneDrive configurado para este evento."}), 400

    ok, msg, count = sync_onedrive_link(event.onedrive_url, event.id)
    if not ok:
        return jsonify({"error": msg}), 400

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("ONEDRIVE_RESYNC", user_id=user_id, target_type="EVENT", target_id=str(event.id),
              details=f"Re-sincronizado OneDrive: {count} invitados", ip_address=request.remote_addr)

    return jsonify({"status": "ok", "message": msg, "guest_count": count})


@api_bp.route("/reset-checkins", methods=["POST"])
def api_reset_checkins():
    event = get_or_create_active_event()
    count = reset_all_checkins(event.id)

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("CHECKINS_RESET", user_id=user_id, target_type="EVENT", target_id=str(event.id),
              details=f"Reiniciadas {count} asistencias.", ip_address=request.remote_addr)

    return jsonify({
        "status": "ok",
        "message": f"Se han reiniciado {count} registros de asistencia.",
        "reset_count": count,
    })


@api_bp.route("/qr-samples")
def api_qr_samples():
    if not Config.QR_OUTPUT_DIR.exists():
        return jsonify([])
    samples = []
    for f in Config.QR_OUTPUT_DIR.glob("*.png"):
        samples.append({
            "filename": f.name,
            "guest_id": f.stem.replace("qr_", ""),
            "url": f"/qr-file/{f.name}"
        })
    return jsonify(samples)


@api_bp.route("/qr-file/<filename>")
def serve_qr_file(filename):
    return send_from_directory(Config.QR_OUTPUT_DIR, filename)
