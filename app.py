"""
app.py
──────
Backend Flask para el sistema de registro de invitados con QR.
Impresión directa en Brother QL-800 con rollo DK-1208 (38mm × 90.3mm).

Fuente de datos:
  1. Enlace compartido de OneDrive (si está configurado)
  2. guests_cache.csv (último CSV descargado)
  3. guests.csv (archivo local de respaldo)

Estado de check-in:
  Se guarda en checkins.json (local en el NUC), persistido independientemente.

Rutas:
  GET    /                       → interfaz kiosko (cámara + carga de QR + lector)
  GET    /admin                  → panel de administración avanzado
  GET    /api/guests             → lista todos los invitados con estado
  GET    /api/guest/<id>         → datos de un invitado por ID
  POST   /api/guest              → crea un nuevo invitado en guests.csv
  POST   /api/checkin/<id>       → marca el check-in de un invitado
  POST   /api/guest/<id>/status  → modifica el estado (registrado / pendiente)
  DELETE /api/guest/<id>         → elimina un invitado de guests.csv y checkins
  POST   /api/print/<id>         → imprime etiqueta (soporta force=true)
  POST   /api/reload-guests      → recarga el CSV desde guests.csv o OneDrive
  POST   /api/reset              → resetea los check-ins locales
  GET    /api/status             → estado general del sistema
  GET    /api/printer/status     → estado en vivo de la impresora Brother
  GET    /api/qr-samples         → lista de archivos QR disponibles en qr_output
"""

import base64
import csv
import io
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

import requests
from flask import Flask, jsonify, render_template, request, send_from_directory
from PIL import Image, ImageDraw, ImageFont, ImageWin
import qrcode
import face_service

# Importar win32print para impresión directa en Windows
try:
    import win32ui
    import win32con
    import win32print
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

# ─── CONFIGURACIÓN ────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent

# Impresora Brother QL-800 en Windows
PRINTER_NAME       = "Brother QL-800"
PRINTER_MODEL      = "QL-800"
LABEL_TYPE         = "38x90"          # DK-1208 → 38mm × 90.3mm
PRINTER_ENABLED    = True             # Activa para imprimir en la QL-800 física

# Dimensiones de la etiqueta a 300 DPI (Landscape para DK-1208)
# Ancho imprimible ~991 px, Alto imprimible ~413 px
LABEL_WIDTH_PX     = 991
LABEL_HEIGHT_PX    = 413

# Archivos locales
CHECKINS_FILE       = BASE_DIR / "checkins.json"
LOCAL_CACHE_CSV     = BASE_DIR / "guests_cache.csv"
LOCAL_FALLBACK_CSV  = BASE_DIR / "guests.csv"
QR_OUTPUT_DIR       = BASE_DIR / "qr_output"

# ─── APP ──────────────────────────────────────────────────────────────────────

app = Flask(__name__)
app.config["JSON_ENSURE_ASCII"] = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─── Estado en memoria ────────────────────────────────────────────────────────

GUESTS: list[dict] = []      # [{id, name, company, position}, ...]
data_lock = Lock()
DATA_SOURCE = "none"         # "onedrive" | "cache" | "local" | "none"


# ─────────────────────────────────────────────────────────────────────────────
# Tipografías auxiliares
# ─────────────────────────────────────────────────────────────────────────────

def get_font(size: int, bold: bool = True):
    candidates = [
        ("C:/Windows/Fonts/arialbd.ttf", True),
        ("C:/Windows/Fonts/arial.ttf", False),
        ("C:/Windows/Fonts/segoeuib.ttf", True),
        ("C:/Windows/Fonts/segoeui.ttf", False),
    ]
    for path, is_bold in candidates:
        if bold and not is_bold:
            continue
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default()


# ─────────────────────────────────────────────────────────────────────────────
# Lectura y Escritura de CSV de Invitados
# ─────────────────────────────────────────────────────────────────────────────

def parse_csv_content(content: str) -> list[dict]:
    """
    Parsea el contenido de un CSV con columnas:
    ID, Nombres y Apellidos, Empresa, Cargo
    """
    reader = csv.DictReader(io.StringIO(content))
    guests = []
    for row in reader:
        guest_id = (
            row.get("ID") or row.get("id") or row.get("CODIGO") or row.get("Codigo") or ""
        ).strip()
        if not guest_id:
            continue

        name = (
            row.get("Nombres y Apellidos") or row.get("Nombre") or row.get("full_name") or ""
        ).strip()
        company = (
            row.get("Empresa") or row.get("empresa") or row.get("Company") or ""
        ).strip()
        position = (
            row.get("Cargo") or row.get("cargo") or row.get("Position") or row.get("Puesto") or ""
        ).strip()

        guests.append({
            "id":       guest_id,
            "name":     name,
            "company":  company,
            "position": position,
        })
    return guests


DOCS_CACHE_DIR      = BASE_DIR / "onedrive_caches"
DOCS_CACHE_DIR.mkdir(exist_ok=True)
SETTINGS_FILE       = BASE_DIR / "settings.json"


def load_settings() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "active_doc_id": "",
        "documents": []
    }


def save_settings(s: dict):
    try:
        SETTINGS_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.error(f"Error guardando settings.json: {e}")


def get_active_doc_info() -> dict | None:
    st = load_settings()
    active_id = st.get("active_doc_id")
    docs = st.get("documents", [])
    for d in docs:
        if d.get("id") == active_id:
            return d
    if docs:
        return docs[0]
    return None


def transform_onedrive_url(shared_url: str) -> list[str]:
    """Genera candidatos de URLs de descarga directa para un enlace de OneDrive o SharePoint."""
    url = shared_url.strip()
    candidates = []

    # 1. SharePoint for Business o 1drv.ms con parámetro directo &download=1
    if "?" in url:
        candidates.append(url + "&download=1")
    else:
        candidates.append(url + "?download=1")

    # 2. API oficial para links públicos de OneDrive (u!base64)
    try:
        encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8")
        clean_encoded = encoded.rstrip("=").replace("/", "_").replace("+", "-")
        api_share_url = f"https://api.onedrive.com/v1.0/shares/u!{clean_encoded}/root/content"
        candidates.append(api_share_url)
    except Exception:
        pass

    # 3. Query string modificada con download=1
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    qs["download"] = ["1"]
    new_query = urlencode(qs, doseq=True)
    download_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
    candidates.append(download_url)

    if "onedrive.live.com" in url:
        candidates.append(url.replace("redir?", "download?").replace("view.aspx?", "download?"))

    candidates.append(url)

    seen = set()
    unique_candidates = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            unique_candidates.append(c)
    return unique_candidates


def download_onedrive_csv(url: str) -> tuple[list[dict], bytes] | tuple[None, None]:
    """Descarga y parsea un CSV desde OneDrive/SharePoint con tolerancia a múltiples encodings."""
    candidates = transform_onedrive_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }

    for download_url in candidates:
        try:
            resp = requests.get(download_url, headers=headers, timeout=12, allow_redirects=True)
            if resp.status_code == 200 and resp.content:
                raw_head = resp.content[:250].lower()
                if b"<html" in raw_head or b"<!doctype" in raw_head:
                    continue

                content = ""
                for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                    try:
                        content = resp.content.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue

                if content:
                    parsed = parse_csv_content(content)
                    if parsed:
                        return parsed, resp.content
        except Exception as e:
            log.debug(f"Intento fallido con URL {download_url}: {e}")

    return None, None


def load_guests() -> tuple[list[dict], str]:
    """Carga invitados exclusivamente desde el documento activo de OneDrive (o su caché local)."""
    doc = get_active_doc_info()
    if not doc:
        if LOCAL_FALLBACK_CSV.exists():
            try:
                raw = LOCAL_FALLBACK_CSV.read_bytes()
                content = ""
                for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                    try:
                        content = raw.decode(enc)
                        break
                    except UnicodeDecodeError:
                        continue
                guests = parse_csv_content(content)
                if guests:
                    log.info(f"Cargados {len(guests)} invitados desde archivo local de respaldo '{LOCAL_FALLBACK_CSV.name}'.")
                    return guests, "local"
            except Exception as e:
                log.warning(f"Error leyendo fallback {LOCAL_FALLBACK_CSV}: {e}")
        return [], "none"

    cache_file = doc.get("cache_file") or f"{doc['id']}.csv"
    cache_path = DOCS_CACHE_DIR / cache_file

    # 1. Intentar cargar desde el archivo de caché local del documento
    if cache_path.exists():
        try:
            raw = cache_path.read_bytes()
            content = ""
            for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                try:
                    content = raw.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            guests = parse_csv_content(content)
            if guests:
                log.info(f"Cargados {len(guests)} invitados desde caché de '{doc.get('name')}'.")
                return guests, "onedrive_cache"
        except Exception as e:
            log.warning(f"Error leyendo caché {cache_path}: {e}")

    # 2. Si no hay caché o está vacío, intentar descarga directa de la URL
    url = doc.get("url", "").strip()
    if url:
        guests, raw_bytes = download_onedrive_csv(url)
        if guests:
            cache_path.write_bytes(raw_bytes)
            st = load_settings()
            for d in st.get("documents", []):
                if d.get("id") == doc["id"]:
                    d["guest_count"] = len(guests)
                    d["last_sync"] = datetime.now().isoformat()
            save_settings(st)
            log.info(f"Descargados y cacheados {len(guests)} invitados de '{doc.get('name')}'.")
            return guests, "onedrive"

    return [], "none"


def save_guests_to_csv(guests_list: list[dict]):
    """Persiste cambios en el archivo de caché del documento OneDrive activo."""
    doc = get_active_doc_info()
    if not doc:
        return

    cache_file = doc.get("cache_file") or f"{doc['id']}.csv"
    cache_path = DOCS_CACHE_DIR / cache_file
    fieldnames = ["ID", "Nombres y Apellidos", "Empresa", "Cargo"]
    try:
        with open(cache_path, mode="w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for g in guests_list:
                writer.writerow({
                    "ID": g.get("id", "").strip(),
                    "Nombres y Apellidos": g.get("name", "").strip(),
                    "Empresa": g.get("company", "").strip(),
                    "Cargo": g.get("position", "").strip(),
                })
        st = load_settings()
        for d in st.get("documents", []):
            if d.get("id") == doc["id"]:
                d["guest_count"] = len(guests_list)
        save_settings(st)
        log.info(f"Guardados {len(guests_list)} invitados en caché de '{doc.get('name')}'.")
    except Exception as e:
        log.error(f"Error guardando caché {cache_path}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Registro y Estado de Check-ins (local)
# ─────────────────────────────────────────────────────────────────────────────

def load_checkins() -> dict:
    if CHECKINS_FILE.exists():
        try:
            return json.loads(CHECKINS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_checkins(checkins: dict):
    CHECKINS_FILE.write_text(
        json.dumps(checkins, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def merge_guest_with_checkin(guest: dict, checkins: dict) -> dict:
    ci = checkins.get(guest["id"].strip().upper(), {})
    return {
        **guest,
        "checked_in":    ci.get("checked_in", False),
        "checked_in_at": ci.get("checked_in_at"),
    }


def find_guest(guest_id: str) -> dict | None:
    guest_id = guest_id.strip().upper()
    checkins = load_checkins()
    for g in GUESTS:
        if g["id"].strip().upper() == guest_id:
            return merge_guest_with_checkin(g, checkins)
    return None


def do_checkin(guest_id: str) -> dict | None:
    guest_id = guest_id.strip().upper()
    guest_base = next((g for g in GUESTS if g["id"].strip().upper() == guest_id), None)
    if not guest_base:
        return None

    with data_lock:
        checkins = load_checkins()
        checkins[guest_id] = {
            "checked_in":    True,
            "checked_in_at": datetime.now().isoformat(),
        }
        save_checkins(checkins)

    return merge_guest_with_checkin(guest_base, checkins)


def set_guest_status(guest_id: str, is_checked_in: bool) -> dict | None:
    guest_id = guest_id.strip().upper()
    guest_base = next((g for g in GUESTS if g["id"].strip().upper() == guest_id), None)
    if not guest_base:
        return None

    with data_lock:
        checkins = load_checkins()
        if is_checked_in:
            checkins[guest_id] = {
                "checked_in":    True,
                "checked_in_at": datetime.now().isoformat(),
            }
        else:
            checkins[guest_id] = {
                "checked_in":    False,
                "checked_in_at": None,
            }
        save_checkins(checkins)

    return merge_guest_with_checkin(guest_base, checkins)


def delete_guest(guest_id: str) -> bool:
    global GUESTS
    guest_id = guest_id.strip().upper()
    with data_lock:
        prev_len = len(GUESTS)
        GUESTS = [g for g in GUESTS if g["id"].strip().upper() != guest_id]
        if len(GUESTS) == prev_len:
            return False

        # Guardar en CSV
        save_guests_to_csv(GUESTS)

        # Limpiar de checkins
        checkins = load_checkins()
        if guest_id in checkins:
            del checkins[guest_id]
            save_checkins(checkins)

    return True


def add_or_update_guest(guest_data: dict) -> dict:
    global GUESTS
    gid = guest_data.get("id", "").strip().upper()
    if not gid:
        raise ValueError("El ID es obligatorio")

    name = guest_data.get("name", "").strip()
    company = guest_data.get("company", "").strip()
    position = guest_data.get("position", "").strip()

    new_guest = {
        "id": gid,
        "name": name,
        "company": company,
        "position": position,
    }

    with data_lock:
        idx = next((i for i, g in enumerate(GUESTS) if g["id"].strip().upper() == gid), -1)
        if idx >= 0:
            GUESTS[idx] = new_guest
        else:
            GUESTS.append(new_guest)

        save_guests_to_csv(GUESTS)

    checkins = load_checkins()
    return merge_guest_with_checkin(new_guest, checkins)


# ─────────────────────────────────────────────────────────────────────────────
# Generador de Etiqueta — Brother QL-800 con rollo DK-1208 (38mm × 90.3mm)
# Formato Grande sin QR: enfocado en Nombres, Empresa y Cargo a máxima legibilidad
# Dimensiones en horizontal: 991 px de ancho × 413 px de alto a 300 DPI
# ─────────────────────────────────────────────────────────────────────────────

def build_label_image(guest: dict) -> Image.Image:
    try:
        from config import EVENT_NAME
    except ImportError:
        EVENT_NAME = "EVENTO DEMO 2026"

    W, H = LABEL_WIDTH_PX, LABEL_HEIGHT_PX
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    # 1. Encabezado del evento (Franja azul superior)
    draw.rectangle([25, 14, 966, 68], fill=(20, 60, 140))
    draw.text((W // 2, 41), EVENT_NAME, font=get_font(24, bold=True), fill="white", anchor="mm")

    # 2. Nombre del Invitado (Tipografía grande, destacada y centrada)
    name = (guest.get("name") or guest.get("full_name") or guest.get("id") or "").strip()
    words = name.split()

    if len(name) > 22 and len(words) > 1:
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
        font_name = get_font(42, bold=True)
        draw.text((W // 2, 110), lines[0], font=font_name, fill=(15, 20, 30), anchor="mm")
        draw.text((W // 2, 156), lines[1], font=font_name, fill=(15, 20, 30), anchor="mm")
        y_sep = 196
    else:
        font_name = get_font(52, bold=True)
        draw.text((W // 2, 130), name, font=font_name, fill=(15, 20, 30), anchor="mm")
        y_sep = 175

    # 3. Línea divisoria elegante
    draw.line([(70, y_sep), (921, y_sep)], fill=(210, 215, 225), width=2)

    # 4. Empresa y Cargo (Centrados y con jerarquía visual)
    company = guest.get("company", "").strip()
    position = guest.get("position", "").strip()

    if company and position:
        comp_display = company if len(company) <= 38 else company[:36] + "…"
        draw.text((W // 2, y_sep + 40), comp_display, font=get_font(34, bold=True), fill=(20, 60, 140), anchor="mm")
        pos_display = position if len(position) <= 42 else position[:40] + "…"
        draw.text((W // 2, y_sep + 88), pos_display, font=get_font(28, bold=False), fill=(60, 65, 75), anchor="mm")
    elif company:
        comp_display = company if len(company) <= 38 else company[:36] + "…"
        draw.text((W // 2, y_sep + 65), comp_display, font=get_font(36, bold=True), fill=(20, 60, 140), anchor="mm")
    elif position:
        pos_display = position if len(position) <= 42 else position[:40] + "…"
        draw.text((W // 2, y_sep + 65), pos_display, font=get_font(32, bold=True), fill=(60, 65, 75), anchor="mm")

    # 5. Pie de etiqueta inferior
    draw.line([(40, 360), (951, 360)], fill=(225, 230, 238), width=1)
    gid = guest.get("id", "")
    draw.text((60, 385), f"ID: {gid}", font=get_font(18, bold=True), fill=(120, 125, 135), anchor="lm")
    draw.text((W - 60, 385), "ACCESO OFICIAL", font=get_font(18, bold=True), fill=(22, 163, 74), anchor="rm")

    return img


# ─────────────────────────────────────────────────────────────────────────────
# Impresión Directa en Windows (GDI / Brother QL-800 Spooler)
# ─────────────────────────────────────────────────────────────────────────────

def print_label(guest: dict, printer_name: str = PRINTER_NAME) -> dict:
    """
    Imprime la etiqueta del invitado en la impresora Brother QL-800 usando el spooler GDI nativo de Windows.
    """
    if not PRINTER_ENABLED:
        log.info(f"[SIMULADO] Impresión de prueba para: {guest['id']} — {guest.get('name')}")
        return {"status": "simulated", "message": "Impresión simulada (impresora deshabilitada en config)"}

    if not WIN32_AVAILABLE:
        return {"status": "error", "message": "El módulo pywin32 no está disponible en este entorno."}

    # Verificar si la impresora existe en Windows
    installed_printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
    target_printer = None
    for p in installed_printers:
        if printer_name.lower() in p.lower():
            target_printer = p
            break

    if not target_printer:
        log.error(f"No se encontró la impresora '{printer_name}'. Impresoras disponibles: {installed_printers}")
        return {
            "status": "error",
            "message": f"Impresora '{printer_name}' no encontrada. Conéctala o revisa su nombre en Windows."
        }

    try:
        label_img = build_label_image(guest)

        hDC = win32ui.CreateDC()
        hDC.CreatePrinterDC(target_printer)

        # Obtener dimensiones del área imprimible del dispositivo
        pw = hDC.GetDeviceCaps(win32con.HORZRES)
        ph = hDC.GetDeviceCaps(win32con.VERTRES)

        # Iniciar documento de impresión en el spooler
        doc_title = f"Ficha {guest['id']} - {guest.get('name', '')}"
        hDC.StartDoc(doc_title)
        hDC.StartPage()

        # Dibujar imagen en el contexto del dispositivo
        dib = ImageWin.Dib(label_img)
        dib.draw(hDC.GetHandleOutput(), (0, 0, pw, ph))

        hDC.EndPage()
        hDC.EndDoc()
        del hDC

        log.info(f"Impresión enviada exitosamente para {guest['id']} a '{target_printer}' ({pw}x{ph} px).")
        return {
            "status": "ok",
            "message": f"Etiqueta impresa correctamente en {target_printer}"
        }

    except Exception as e:
        log.exception(f"Error imprimiendo ficha de {guest['id']}: {e}")
        return {"status": "error", "message": f"Fallo al imprimir: {str(e)}"}


# ─────────────────────────────────────────────────────────────────────────────
# Rutas API
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/guests")
def api_guests():
    checkins = load_checkins()
    face_counts = face_service.get_enrolled_counts()
    result = []
    for g in GUESTS:
        merged = merge_guest_with_checkin(g, checkins)
        fc = face_counts.get(g["id"].strip().upper(), 0)
        merged["face_count"] = fc
        merged["face_enrolled"] = fc > 0
        result.append(merged)
    return jsonify(result)


@app.route("/api/guest/<guest_id>")
def api_guest(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404
    faces = face_service.get_guest_faces(guest_id)
    guest["faces"] = faces
    guest["face_count"] = len(faces)
    guest["face_enrolled"] = len(faces) > 0
    return jsonify(guest)


@app.route("/api/guest", methods=["POST"])
def api_create_guest():
    data = request.get_json(silent=True) or request.form.to_dict()
    if not data or not data.get("id"):
        return jsonify({"error": "Se requiere ID de invitado"}), 400

    try:
        guest = add_or_update_guest(data)
        return jsonify({"status": "ok", "guest": guest, "message": "Invitado guardado exitosamente"})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/guest/<guest_id>", methods=["DELETE"])
def api_delete_guest(guest_id):
    success = delete_guest(guest_id)
    if not success:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404
    return jsonify({"status": "ok", "message": f"Invitado {guest_id} eliminado correctamente"})


@app.route("/api/guest/<guest_id>/status", methods=["POST"])
def api_toggle_guest_status(guest_id):
    data = request.get_json(silent=True) or {}
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404

    # Si se pasa explícitamente checked_in se usa, si no, se alterna (toggle)
    if "checked_in" in data:
        new_state = bool(data["checked_in"])
    else:
        new_state = not guest.get("checked_in", False)

    updated = set_guest_status(guest_id, new_state)
    return jsonify({
        "status": "ok",
        "guest": updated,
        "message": f"Estado actualizado a {'Registrado' if new_state else 'Pendiente'}"
    })


@app.route("/api/checkin/<guest_id>", methods=["POST"])
def api_checkin(guest_id):
    guest = do_checkin(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404
    return jsonify({"status": "ok", "guest": guest})


@app.route("/api/print/<guest_id>", methods=["POST"])
def api_print(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404

    # Revisar si se solicita forzar reimpresión
    force = request.args.get("force", "").lower() in ("true", "1", "yes")
    req_json = request.get_json(silent=True) or {}
    if req_json.get("force"):
        force = True

    # Si no es forzada y ya estaba registrado previamente, avisar sin reimprimir
    if not force and guest.get("checked_in"):
        return jsonify({
            "guest": guest,
            "print": {
                "status": "already_registered",
                "message": "El invitado ya cuenta con check-in y ticket impreso anteriormente.",
            },
            "status": "already_registered",
        })

    # Imprimir la etiqueta en la Brother QL-800
    result = print_label(guest)

    # REQUERIMIENTO CLAVE: Cuando el individuo imprima su ticket, recién cambiará el estado a check-in
    if result.get("status") in ("ok", "simulated"):
        updated_guest = do_checkin(guest_id)
        log.info(f"Check-in confirmado para {guest_id} tras impresión exitosa.")
        return jsonify({
            "status": "ok",
            "guest": updated_guest,
            "print": result,
            "message": "Ticket impreso y check-in registrado con éxito"
        })
    else:
        log.error(f"Fallo en la impresión para {guest_id}. El check-in NO fue registrado.")
        return jsonify({
            "status": "print_failed",
            "guest": guest,
            "print": result,
            "message": f"No se pudo imprimir el ticket: {result.get('message', 'Error de hardware')}. Check-in pendiente."
        }), 500


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints de Reconocimiento y Enrolamiento Facial
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/guest/<guest_id>/faces", methods=["GET"])
def api_get_guest_faces(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404
    faces = face_service.get_guest_faces(guest_id)
    return jsonify({
        "status": "ok",
        "guest_id": guest_id,
        "count": len(faces),
        "faces": faces,
    })


@app.route("/api/guest/<guest_id>/face", methods=["POST"])
def api_enroll_guest_face(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404

    # 1. Puede ser archivo subido multipart (file)
    if "file" in request.files:
        file = request.files["file"]
        if not file.filename:
            return jsonify({"error": "Archivo no seleccionado"}), 400
        img_bytes = file.read()
        res = face_service.enroll_guest_image(guest_id, img_bytes)
        if not res.get("success"):
            return jsonify(res), 400
        return jsonify(res)

    # 2. O JSON con image_base64 (captura de webcam)
    data = request.get_json(silent=True) or {}
    img_b64 = data.get("image_base64") or data.get("image")
    if not img_b64:
        return jsonify({"error": "Debe enviar un archivo o una imagen en formato base64"}), 400

    res = face_service.enroll_guest_image(guest_id, img_b64)
    if not res.get("success"):
        return jsonify(res), 400
    return jsonify(res)


@app.route("/api/guest/<guest_id>/face-image/<image_id>", methods=["GET"])
def api_get_guest_face_image(guest_id, image_id):
    guest_dir = face_service.FACE_IMAGES_DIR / guest_id.strip().upper()
    is_thumb = request.args.get("thumb", "").lower() in ("1", "true", "yes")

    filename = f"{image_id}_aligned.jpg" if is_thumb else f"{image_id}.jpg"
    target_path = guest_dir / filename

    if not target_path.exists():
        # Fallback al original si el aligned no existe
        target_path = guest_dir / f"{image_id}.jpg"

    if not target_path.exists():
        return jsonify({"error": "Imagen no encontrada"}), 404

    return send_from_directory(str(guest_dir), target_path.name)


@app.route("/api/guest/<guest_id>/face", methods=["DELETE"])
def api_delete_guest_face(guest_id):
    guest = find_guest(guest_id)
    if not guest:
        return jsonify({"error": "Invitado no encontrado", "id": guest_id}), 404

    image_id = request.args.get("image_id") or (request.get_json(silent=True) or {}).get("image_id")
    success = face_service.delete_guest_face(guest_id, image_id)
    if not success:
        return jsonify({"error": "No se encontraron fotos para eliminar"}), 404

    faces = face_service.get_guest_faces(guest_id)
    return jsonify({
        "status": "ok",
        "message": "Foto(s) eliminada(s) correctamente",
        "remaining_count": len(faces),
    })


@app.route("/api/facial-match", methods=["POST"])
def api_facial_match():
    """
    Recibe un fotograma de la cámara web, detecta si hay un rostro coincidente
    y opcionalmente ejecuta el check-in e impresión de etiqueta.
    """
    # 1. Obtener imagen base64
    data = request.get_json(silent=True) or {}
    img_b64 = data.get("image_base64") or data.get("image")

    if not img_b64 and "file" in request.files:
        img_b64 = request.files["file"].read()

    if not img_b64:
        return jsonify({"error": "Se requiere imagen para el reconocimiento"}), 400

    threshold = float(data.get("threshold") or face_service.DEFAULT_COSINE_THRESHOLD)
    auto_checkin = data.get("auto_checkin", True)
    if isinstance(auto_checkin, str):
        auto_checkin = auto_checkin.lower() in ("true", "1", "yes")

    # 2. Inferencia con OpenCV SFace + YuNet
    match_result = face_service.match_face(img_b64, threshold=threshold)

    if not match_result.get("matched"):
        return jsonify({
            "status": "no_match",
            "reason": match_result.get("reason"),
            "similarity": match_result.get("similarity"),
            "candidate_id": match_result.get("candidate_id"),
            "bbox": match_result.get("bbox"),
            "message": match_result.get("message"),
        })

    matched_id = match_result["guest_id"]
    guest = find_guest(matched_id)
    if not guest:
        return jsonify({
            "status": "no_match",
            "reason": "guest_not_found_in_list",
            "message": f"Rostro coincide con {matched_id} pero no figura en la lista activa",
        })

    # Si se pide auto_checkin (modo normal del Kiosko):
    if auto_checkin:
        # Verificar si ya estaba registrado
        if guest.get("checked_in"):
            return jsonify({
                "status": "already_registered",
                "guest": guest,
                "similarity": match_result["similarity"],
                "bbox": match_result.get("bbox"),
                "message": f"El invitado {guest.get('name')} ya cuenta con check-in previo.",
            })

        # Imprimir en Brother QL-800
        print_res = print_label(guest)

        # REGLA DE NEGOCIO: El check-in se confirma solo si la impresión tuvo éxito
        if print_res.get("status") in ("ok", "simulated"):
            updated_guest = do_checkin(matched_id)
            log.info(f"Check-in facial confirmado para {matched_id} ({guest.get('name')}) tras impresión exitosa.")
            return jsonify({
                "status": "ok",
                "guest": updated_guest,
                "print": print_res,
                "similarity": match_result["similarity"],
                "bbox": match_result.get("bbox"),
                "message": f"¡Bienvenido(a) {guest.get('name')}! Etiqueta impresa y check-in confirmado.",
            })
        else:
            log.error(f"Fallo en la impresión de etiqueta para {matched_id}. Check-in facial pendiente.")
            return jsonify({
                "status": "print_failed",
                "guest": guest,
                "print": print_res,
                "similarity": match_result["similarity"],
                "bbox": match_result.get("bbox"),
                "message": f"No se pudo imprimir la etiqueta: {print_res.get('message', 'Error de hardware')}. Check-in pendiente.",
            }), 500

    # Modo manual o solo identificación
    return jsonify({
        "status": "identified",
        "guest": guest,
        "similarity": match_result["similarity"],
        "bbox": match_result.get("bbox"),
        "message": f"Rostro identificado: {guest.get('name')}",
    })




# ─────────────────────────────────────────────────────────────────────────────
# Endpoints de Gestión de Documentos OneDrive (Multi-documentos & Caché)
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/api/documents", methods=["GET"])
def api_get_documents():
    st = load_settings()
    active_doc = get_active_doc_info()
    return jsonify({
        "status": "ok",
        "active_doc_id": st.get("active_doc_id"),
        "active_document": active_doc,
        "documents": st.get("documents", []),
        "guest_count": len(GUESTS),
        "data_source": DATA_SOURCE,
    })


@app.route("/api/documents", methods=["POST"])
def api_add_document():
    global GUESTS, DATA_SOURCE
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    url = (data.get("url") or "").strip()
    name = (data.get("name") or "").strip()

    if not url:
        return jsonify({"error": "Debe proporcionar una URL de OneDrive o SharePoint válida."}), 400

    if not name:
        name = f"Documento OneDrive ({datetime.now().strftime('%d/%m/%Y %H:%M')})"

    log.info(f"Validando y descargando nuevo documento OneDrive: {url}")
    parsed_guests, raw_bytes = download_onedrive_csv(url)

    if not parsed_guests or not raw_bytes:
        return jsonify({
            "error": "No se pudo descargar o procesar el archivo CSV desde el enlace proporcionado. Asegúrese de que el enlace sea accesible y corresponda a un CSV válido con las columnas 'ID', 'Nombres y Apellidos', 'Empresa', 'Cargo'."
        }), 400

    doc_id = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    cache_filename = f"{doc_id}.csv"
    cache_path = DOCS_CACHE_DIR / cache_filename

    try:
        cache_path.write_bytes(raw_bytes)
    except Exception as e:
        log.error(f"Error guardando caché {cache_path}: {e}")
        return jsonify({"error": f"Error al guardar archivo en caché: {str(e)}"}), 500

    new_doc = {
        "id": doc_id,
        "name": name,
        "url": url,
        "cache_file": cache_filename,
        "last_sync": datetime.now().isoformat(),
        "guest_count": len(parsed_guests),
    }

    st = load_settings()
    docs = st.get("documents", [])
    docs.append(new_doc)
    st["documents"] = docs
    st["active_doc_id"] = doc_id
    save_settings(st)

    with data_lock:
        GUESTS = parsed_guests
        DATA_SOURCE = "onedrive"

    log.info(f"Nuevo documento registrado y activado: {name} ({len(GUESTS)} invitados).")
    return jsonify({
        "status": "ok",
        "message": f"Documento '{name}' agregado y activado con {len(GUESTS)} invitados.",
        "document": new_doc,
        "active_doc_id": doc_id,
        "guest_count": len(GUESTS),
        "data_source": DATA_SOURCE,
    })


@app.route("/api/documents/select", methods=["POST"])
def api_select_document():
    global GUESTS, DATA_SOURCE
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    target_id = (data.get("id") or "").strip()

    st = load_settings()
    docs = st.get("documents", [])
    target_doc = next((d for d in docs if d.get("id") == target_id), None)

    if not target_doc:
        return jsonify({"error": f"No se encontró el documento con ID '{target_id}' en caché."}), 404

    st["active_doc_id"] = target_id
    save_settings(st)

    with data_lock:
        guests, source = load_guests()
        GUESTS = guests
        DATA_SOURCE = source

    log.info(f"Documento activo cambiado a: {target_doc.get('name')} ({len(GUESTS)} invitados, fuente: {DATA_SOURCE}).")
    return jsonify({
        "status": "ok",
        "message": f"Fuente cambiada a '{target_doc.get('name')}' ({len(GUESTS)} invitados).",
        "active_doc_id": target_id,
        "active_document": target_doc,
        "guest_count": len(GUESTS),
        "data_source": DATA_SOURCE,
    })


@app.route("/api/documents/<doc_id>/sync", methods=["POST"])
def api_sync_document(doc_id):
    global GUESTS, DATA_SOURCE
    st = load_settings()
    docs = st.get("documents", [])
    target_doc = next((d for d in docs if d.get("id") == doc_id), None)

    if not target_doc:
        return jsonify({"error": f"Documento '{doc_id}' no encontrado."}), 404

    url = target_doc.get("url", "").strip()
    if not url:
        return jsonify({"error": "El documento no tiene una URL de OneDrive asociada."}), 400

    parsed_guests, raw_bytes = download_onedrive_csv(url)
    if parsed_guests and raw_bytes:
        cache_filename = target_doc.get("cache_file") or f"{doc_id}.csv"
        cache_path = DOCS_CACHE_DIR / cache_filename
        try:
            cache_path.write_bytes(raw_bytes)
        except Exception as e:
            log.warning(f"Error actualizando caché {cache_path}: {e}")

        target_doc["last_sync"] = datetime.now().isoformat()
        target_doc["guest_count"] = len(parsed_guests)
        save_settings(st)

        if st.get("active_doc_id") == doc_id:
            with data_lock:
                GUESTS = parsed_guests
                DATA_SOURCE = "onedrive"

        return jsonify({
            "status": "ok",
            "message": f"Documento '{target_doc.get('name')}' sincronizado con éxito ({len(parsed_guests)} invitados actualizados).",
            "guest_count": len(parsed_guests),
            "last_sync": target_doc["last_sync"],
        })
    else:
        return jsonify({
            "status": "warning",
            "message": "No se pudo descargar la última versión de OneDrive. Se mantiene la versión en caché local.",
        }), 502


@app.route("/api/documents/<doc_id>", methods=["DELETE"])
def api_delete_document(doc_id):
    global GUESTS, DATA_SOURCE
    st = load_settings()
    docs = st.get("documents", [])
    target_doc = next((d for d in docs if d.get("id") == doc_id), None)

    if not target_doc:
        return jsonify({"error": f"Documento '{doc_id}' no encontrado."}), 404

    if len(docs) <= 1:
        return jsonify({"error": "No se puede eliminar el único documento configurado. Agregue otro antes de eliminar este."}), 400

    # Eliminar archivo de caché si existe
    cache_filename = target_doc.get("cache_file") or f"{doc_id}.csv"
    cache_path = DOCS_CACHE_DIR / cache_filename
    if cache_path.exists():
        try:
            cache_path.unlink()
        except Exception as e:
            log.warning(f"No se pudo eliminar archivo físico {cache_path}: {e}")

    # Remover de la lista
    docs = [d for d in docs if d.get("id") != doc_id]
    st["documents"] = docs

    # Si era el documento activo, activar el primero de los restantes
    active_switched = False
    if st.get("active_doc_id") == doc_id:
        st["active_doc_id"] = docs[0]["id"]
        active_switched = True

    save_settings(st)

    if active_switched:
        with data_lock:
            guests, source = load_guests()
            GUESTS = guests
            DATA_SOURCE = source

    return jsonify({
        "status": "ok",
        "message": f"Documento '{target_doc.get('name')}' eliminado del sistema.",
        "active_doc_id": st.get("active_doc_id"),
        "guest_count": len(GUESTS),
    })


@app.route("/api/reload-guests", methods=["POST"])
def api_reload_guests():
    global GUESTS, DATA_SOURCE
    with data_lock:
        guests, source = load_guests()
        GUESTS      = guests
        DATA_SOURCE = source

    return jsonify({
        "status":  "ok",
        "source":  DATA_SOURCE,
        "count":   len(GUESTS),
        "message": f"{len(GUESTS)} invitados cargados desde '{DATA_SOURCE}'.",
    })


@app.route("/api/reset", methods=["POST"])
def api_reset():
    with data_lock:
        save_checkins({})
    log.info("Check-ins reseteados.")
    return jsonify({"status": "ok", "message": "Todos los check-ins han sido reseteados."})


@app.route("/api/status")
def api_status():
    st = load_settings()
    active_doc = get_active_doc_info()

    return jsonify({
        "active_doc_id":   st.get("active_doc_id"),
        "active_document": active_doc,
        "data_source":     DATA_SOURCE,
        "guest_count":     len(GUESTS),
        "printer": {
            "enabled": PRINTER_ENABLED,
            "name":    PRINTER_NAME,
            "model":   PRINTER_MODEL,
            "label":   LABEL_TYPE,
        },
    })


@app.route("/api/printer/status")
def api_printer_status():
    installed = False
    status_text = "Desconectada"
    if WIN32_AVAILABLE:
        try:
            printers = [p[2] for p in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)]
            for p in printers:
                if PRINTER_NAME.lower() in p.lower():
                    installed = True
                    status_text = f"Conectada en Windows ({p})"
                    break
        except Exception as e:
            status_text = str(e)

    return jsonify({
        "enabled":     PRINTER_ENABLED,
        "name":        PRINTER_NAME,
        "model":       PRINTER_MODEL,
        "label":       LABEL_TYPE,
        "installed":   installed,
        "status_text": status_text,
    })


@app.route("/api/qr-samples")
def api_qr_samples():
    """Retorna lista de QRs disponibles en la carpeta qr_output para pruebas rápidas."""
    samples = []
    if QR_OUTPUT_DIR.exists():
        for file in sorted(QR_OUTPUT_DIR.glob("*_qr.png")):
            gid = file.stem.replace("_qr", "")
            samples.append({
                "id": gid,
                "filename": file.name,
                "url": f"/qr-file/{file.name}",
            })
    return jsonify(samples)


@app.route("/qr-file/<filename>")
def serve_qr_file(filename):
    from flask import send_from_directory
    return send_from_directory(QR_OUTPUT_DIR, filename)


# ─────────────────────────────────────────────────────────────────────────────
# Rutas de vistas
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin")
def admin():
    return render_template("admin.html")


# ─────────────────────────────────────────────────────────────────────────────
# Inicio
# ─────────────────────────────────────────────────────────────────────────────

def startup():
    global GUESTS, DATA_SOURCE
    log.info("Cargando lista de invitados...")
    guests, source = load_guests()
    GUESTS      = guests
    DATA_SOURCE = source

    source_label = {
        "onedrive": "Enlace OneDrive (en línea)",
        "cache":    "Cache local (offline)",
        "local":    "CSV local de respaldo",
        "none":     "SIN DATOS",
    }.get(source, source)

    log.info(f"Fuente de datos activa: {source_label}")
    log.info(f"Invitados cargados: {len(GUESTS)}")
    log.info(f"Impresora: {PRINTER_NAME} (Rollo {LABEL_TYPE} - 38x90mm)")
    log.info(f"Estado de impresión: {'HABILITADA' if PRINTER_ENABLED else 'SIMULADA'}")

    try:
        face_service.init_face_service()
    except Exception as e:
        log.error(f"Error inicializando servicio facial: {e}")


if __name__ == "__main__":
    startup()
    app.run(host="0.0.0.0", port=5000, debug=True)
