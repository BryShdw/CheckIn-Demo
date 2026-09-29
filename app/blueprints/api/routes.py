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
from app.models.checkin import Checkin
from app.models.face_profile import FaceProfile
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


@api_bp.route("/guest/<path:guest_id>/status", methods=["POST"])
def api_toggle_guest_status(guest_id):
    """
    Alterna el estado de asistencia de un invitado (Registrado <-> Pendiente)
    manualmente desde el panel de administración.
    """
    event = get_or_create_active_event()
    guest = find_guest(guest_id, event.id)
    if not guest:
        return jsonify({"error": f"Invitado con ID '{guest_id}' no encontrado."}), 404

    user_id = current_user.id if current_user.is_authenticated else None

    if guest.is_checked_in:
        Checkin.query.filter_by(guest_id=guest.id, event_id=event.id).delete()
        db.session.commit()
        log_audit(
            "CHECKIN_CANCEL",
            user_id=user_id,
            target_type="GUEST",
            target_id=guest.guest_code,
            details=f"Asistencia revertida a pendiente para: {guest.full_name}",
            ip_address=request.remote_addr,
        )
    else:
        checkin = Checkin(
            event_id=event.id,
            guest_id=guest.id,
            method="MANUAL",
            verified_by_user_id=user_id,
            ip_address=request.remote_addr,
            printed_success=False,
        )
        db.session.add(checkin)
        db.session.commit()
        log_audit(
            "CHECKIN_MANUAL",
            user_id=user_id,
            target_type="GUEST",
            target_id=guest.guest_code,
            details=f"Asistencia confirmada manualmente para: {guest.full_name}",
            ip_address=request.remote_addr,
        )

    return jsonify({
        "status": "ok",
        "message": f"Estado de {guest.full_name} actualizado a {'Registrado' if guest.is_checked_in else 'Pendiente'}.",
        "checked_in": guest.is_checked_in,
        "guest": guest.to_dict(),
    })


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
    """
    Recibe fotograma de la cámara del Kiosko en base64 o archivo multipart.
    Identifica al usuario por biometría facial YuNet + SFace.
    - Modo automático: ejecuta check-in e imprime credencial física en Brother QL-800.
    - Modo manual: retorna datos del participante para confirmación en pantalla.
    - Respuestas estructuradas compatibles con index.html:
      * 'ok': Acreditado y etiqueta impresa.
      * 'already_registered': Ya cuenta con check-in previo.
      * 'identified': Modo manual, esperando confirmación del usuario.
      * 'not_registered': ID no encontrado en la lista activa.
      * 'print_failed': Error de hardware de impresión.
      * 'no_match': Rostro detectado pero no coincide con la base.
      * 'no_face': Ningún rostro detectado en el fotograma.
    """
    data = request.get_json(silent=True) or {}
    image_b64 = data.get("image_base64") or data.get("image") or data.get("image_data")

    img_bgr = None
    if not image_b64 and "file" in request.files:
        try:
            file_bytes = request.files["file"].read()
            np_arr = np.frombuffer(file_bytes, np.uint8)
            img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error leyendo archivo de imagen: {e}"}), 400
    elif image_b64:
        try:
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            img_bytes = base64.b64decode(image_b64)
            np_arr = np.frombuffer(img_bytes, np.uint8)
            img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error decodificando imagen base64: {e}"}), 400

    if img_bgr is None or img_bgr.size == 0:
        return jsonify({"status": "error", "message": "No se recibió una imagen válida"}), 400

    event = get_or_create_active_event()
    k_settings = get_kiosk_settings(event.id)
    threshold = float(data.get("threshold") or k_settings.face_threshold or Config.DEFAULT_FACE_THRESHOLD)

    if "auto_checkin" in data:
        auto_checkin = data.get("auto_checkin")
        if isinstance(auto_checkin, str):
            auto_checkin = auto_checkin.lower() in ("true", "1", "yes")
        else:
            auto_checkin = bool(auto_checkin)
    else:
        auto_checkin = (k_settings.mode == "auto")

    matched_code, similarity, bbox, top2_sim = match_face(img_bgr, threshold=threshold)

    # 1. Sin rostro detectado en fotograma
    if bbox is None:
        return jsonify({
            "status": "no_face",
            "similarity": 0.0,
            "bbox": None,
            "message": "No se detectó ningún rostro en la cámara",
        })

    # 2. Rostro detectado pero no coincide con ningún participante autorizado
    if not matched_code:
        return jsonify({
            "status": "no_match",
            "similarity": similarity,
            "bbox": bbox,
            "message": "Rostro detectado pero no coincide con ningún participante registrado",
        })

    # 3. Candidato identificado: buscar en MySQL
    guest = find_guest(matched_code, event.id)
    if not guest:
        return jsonify({
            "status": "not_registered",
            "guest_id": matched_code,
            "similarity": similarity,
            "bbox": bbox,
            "message": f"Usuario no registrado en la lista activa ({matched_code})",
        })

    # 4. Modo Automático: procesar check-in e imprimir credencial
    if auto_checkin:
        if guest.is_checked_in:
            return jsonify({
                "status": "already_registered",
                "already_checked_in": True,
                "guest": guest.to_dict(),
                "similarity": similarity,
                "bbox": bbox,
                "message": f"El invitado {guest.full_name} ya cuenta con asistencia previa.",
            })

        user_id = current_user.id if current_user.is_authenticated else None
        result, status_code = process_checkin(
            guest_code_or_url=guest.guest_code,
            method="FACIAL",
            confidence_score=similarity,
            verified_by_user_id=user_id,
            ip_address=request.remote_addr,
            force_reprint=False,
        )

        if status_code == 200:
            return jsonify({
                "status": "ok",
                "success": True,
                "guest": result.get("guest") or guest.to_dict(),
                "print": {"status": "ok", "message": result.get("message")},
                "similarity": similarity,
                "bbox": bbox,
                "message": f"¡Bienvenido(a) {guest.full_name}! Credencial emitida.",
            }), 200
        elif status_code == 409:
            return jsonify({
                "status": "already_registered",
                "already_checked_in": True,
                "guest": result.get("guest") or guest.to_dict(),
                "similarity": similarity,
                "bbox": bbox,
                "message": result.get("message"),
            }), 200
        else:
            return jsonify({
                "status": "print_failed",
                "guest": guest.to_dict(),
                "similarity": similarity,
                "bbox": bbox,
                "error": result.get("error", "Error procesando impresión/checkin"),
                "message": result.get("error", "Error procesando impresión/checkin"),
            }), 500

    # 5. Modo Manual: identificación para confirmación visual
    if guest.is_checked_in:
        return jsonify({
            "status": "already_registered",
            "already_checked_in": True,
            "guest": guest.to_dict(),
            "similarity": similarity,
            "bbox": bbox,
            "message": f"El invitado {guest.full_name} ya cuenta con asistencia previa.",
        })

    return jsonify({
        "status": "identified",
        "guest": guest.to_dict(),
        "similarity": similarity,
        "bbox": bbox,
        "message": f"Rostro identificado: {guest.full_name}",
    })


@api_bp.route("/guest/<path:guest_id>/faces", methods=["GET"])
def api_get_guest_faces(guest_id):
    """Devuelve la galería de fotos enroladas para un invitado desde MySQL."""
    event = get_or_create_active_event()
    guest = find_guest(guest_id, event.id)
    if not guest:
        return jsonify({"error": f"Invitado con ID '{guest_id}' no encontrado", "faces": []}), 404

    profiles = FaceProfile.query.filter_by(guest_id=guest.id).order_by(FaceProfile.id.asc()).all()
    return jsonify({
        "status": "ok",
        "success": True,
        "faces": [p.to_dict() for p in profiles],
        "count": len(profiles),
    })


@api_bp.route("/guest/<path:guest_id>/face", methods=["POST"])
def api_enroll_guest_face(guest_id):
    event = get_or_create_active_event()
    guest = find_guest(guest_id, event.id)
    if not guest:
        return jsonify({"error": f"Invitado con ID '{guest_id}' no encontrado"}), 404

    img_bgr = None
    file = request.files.get("image") or request.files.get("file")
    if file:
        img_bytes = file.read()
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    else:
        data = request.get_json() or {}
        image_b64 = data.get("image") or data.get("image_base64") or data.get("image_data")
        if image_b64:
            if "," in image_b64:
                image_b64 = image_b64.split(",", 1)[1]
            try:
                img_bytes = base64.b64decode(image_b64)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                img_bgr = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            except Exception as e:
                return jsonify({"error": f"Error decodificando imagen base64: {e}"}), 400

    if img_bgr is None or img_bgr.size == 0:
        return jsonify({"error": "No se recibió una imagen válida"}), 400

    ok, msg, profile_dict = enroll_guest_face(guest, img_bgr)
    if not ok:
        return jsonify({"error": msg, "success": False}), 400

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("FACE_ENROLL", user_id=user_id, target_type="GUEST", target_id=guest.guest_code,
              details=f"Foto facial enrolada para {guest.full_name}", ip_address=request.remote_addr)

    return jsonify({
        "status": "ok",
        "success": True,
        "message": msg,
        "face": profile_dict,
        "guest": guest.to_dict(),
    })


@api_bp.route("/guest/<path:guest_id>/face", methods=["DELETE"])
@api_bp.route("/guest/<path:guest_id>/face/<path:image_id>", methods=["DELETE"])
def api_delete_guest_face_route(guest_id, image_id=None):
    event = get_or_create_active_event()
    guest = find_guest(guest_id, event.id)
    if not guest:
        return jsonify({"error": f"Invitado con ID '{guest_id}' no encontrado"}), 404

    target_image_id = image_id or request.args.get("image_id")
    delete_guest_face(guest, target_image_id)

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("FACE_DELETE", user_id=user_id, target_type="GUEST", target_id=guest.guest_code,
              details=f"Foto facial eliminada para {guest.full_name}", ip_address=request.remote_addr)

    return jsonify({
        "status": "ok",
        "success": True,
        "message": "Fotos faciales eliminadas.",
        "guest": guest.to_dict(),
    })


@api_bp.route("/faces/delete-all", methods=["POST", "DELETE"])
@api_bp.route("/guest/faces/all", methods=["POST", "DELETE"])
@api_bp.route("/faces/all", methods=["POST", "DELETE"])
def api_delete_all_faces():
    res = delete_all_enrolled_faces()
    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("FACE_PURGE_ALL", user_id=user_id, details=f"Eliminadas todas las fotos faciales ({res['deleted_count']} perfiles)", ip_address=request.remote_addr)
    return jsonify({
        "status": "ok",
        "success": True,
        "message": f"Se han eliminado todas las fotos de enrolamiento ({res.get('deleted_count', 0)} perfiles reseteados).",
        "deleted_count": res.get("deleted_count", 0),
    })


@api_bp.route("/face-image/<path:guest_id>/<filename>")
def api_serve_face_image(guest_id, filename):
    image_id = filename.replace(".jpg", "").replace("_aligned", "")
    profile = FaceProfile.query.filter((FaceProfile.filename == filename) | (FaceProfile.thumb_filename == filename) | (FaceProfile.image_id == image_id)).first()
    if profile and profile.thumb_data and "base64," in profile.thumb_data:
        try:
            raw_b64 = profile.thumb_data.split("base64,")[1]
            img_bytes = base64.b64decode(raw_b64)
            return send_file(io.BytesIO(img_bytes), mimetype="image/jpeg")
        except Exception:
            pass
    return jsonify({"error": "Imagen no disponible"}), 404


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


@api_bp.route("/reset-all", methods=["POST"])
@api_bp.route("/reset-checkins", methods=["POST"])
@api_bp.route("/checkins/reset", methods=["POST"])
def api_reset_checkins():
    event = get_or_create_active_event()
    count = reset_all_checkins(event.id)

    user_id = current_user.id if current_user.is_authenticated else None
    log_audit("CHECKINS_RESET", user_id=user_id, target_type="EVENT", target_id=str(event.id),
              details=f"Reiniciadas {count} asistencias.", ip_address=request.remote_addr)

    return jsonify({
        "status": "ok",
        "success": True,
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
