import base64
import csv
import io
import json
import logging
from datetime import datetime
import openpyxl
import requests

from app.config import Config
from app.extensions import db
from app.models.guest import Guest
from app.models.event import Event
from app.models.face_profile import FaceProfile
from app.services.guest_service import get_or_create_active_event

log = logging.getLogger(__name__)


def transform_onedrive_url(raw_url: str) -> str:
    """Convierte un enlace compartido de OneDrive / SharePoint al endpoint de descarga directa."""
    raw_url = raw_url.strip()
    if not raw_url:
        return ""

    if "api.onedrive.com" in raw_url:
        return raw_url

    if "1drv.ms" in raw_url or "sharepoint.com" in raw_url or "onedrive.live.com" in raw_url:
        encoded = base64.b64encode(raw_url.encode("utf-8")).decode("utf-8")
        clean_encoded = encoded.rstrip("=").replace("/", "_").replace("+", "-")
        return f"https://api.onedrive.com/v1.0/shares/u!{clean_encoded}/root/content"

    return raw_url


def parse_csv_stream(content: str) -> list[dict]:
    """Parsea un contenido de texto CSV identificando delimitador y columnas."""
    lines = [line for line in content.splitlines() if line.strip()]
    if not lines:
        return []

    sample = "\n".join(lines[:10])
    delimiter = ","
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=";,|\t,")
        delimiter = dialect.delimiter
    except Exception:
        first_line = lines[0]
        if ";" in first_line:
            delimiter = ";"
        elif "\t" in first_line:
            delimiter = "\t"

    reader = csv.reader(lines, delimiter=delimiter)
    try:
        raw_header = next(reader)
    except StopIteration:
        return []

    def clean_col(s: str) -> str:
        s = s.strip().lower().replace("\ufeff", "").replace(" ", "_")
        accents = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
        for k, v in accents.items():
            s = s.replace(k, v)
        return s

    header = [clean_col(h) for h in raw_header]

    def find_idx(*keywords):
        for kw in keywords:
            for i, h in enumerate(header):
                if kw in h:
                    return i
        return None

    id_idx = find_idx("id", "codigo", "code", "identificacion", "dni")
    name_idx = find_idx("nombre", "nombres", "name", "asistente", "invitado")
    company_idx = find_idx("empresa", "company", "organizacion", "institucion")
    pos_idx = find_idx("cargo", "puesto", "position", "rol")
    email_idx = find_idx("correo", "email", "mail")
    phone_idx = find_idx("telefono", "celular", "phone")

    guests = []
    auto_id = 1
    for row in reader:
        if not row or not any(cell.strip() for cell in row):
            continue

        def get_val(idx):
            return row[idx].strip() if idx is not None and idx < len(row) else ""

        gid = get_val(id_idx) or f"INV-{auto_id:03d}"
        name = get_val(name_idx)
        if not name:
            continue

        company = get_val(company_idx)
        pos = get_val(pos_idx)
        email = get_val(email_idx)
        phone = get_val(phone_idx)

        guests.append({
            "guest_code": gid.upper(),
            "full_name": name,
            "company": company,
            "position": pos,
            "email": email,
            "phone": phone,
        })
        auto_id += 1

    return guests


def parse_excel_file(file_bytes: bytes) -> list[dict]:
    """Parsea un archivo Excel (.xlsx) y extrae las filas de invitados."""
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sheet = wb.active

    rows = list(sheet.iter_rows(values_only=True))
    if not rows:
        return []

    # Extraer encabezado
    raw_header = [str(cell) if cell is not None else "" for cell in rows[0]]

    def clean_col(s: str) -> str:
        s = s.strip().lower().replace(" ", "_")
        accents = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n"}
        for k, v in accents.items():
            s = s.replace(k, v)
        return s

    header = [clean_col(h) for h in raw_header]

    def find_idx(*keywords):
        for kw in keywords:
            for i, h in enumerate(header):
                if kw in h:
                    return i
        return None

    id_idx = find_idx("id", "codigo", "code", "dni")
    name_idx = find_idx("nombre", "nombres", "name", "asistente", "invitado")
    company_idx = find_idx("empresa", "company", "organizacion", "institucion")
    pos_idx = find_idx("cargo", "puesto", "position", "rol")
    email_idx = find_idx("correo", "email", "mail")
    phone_idx = find_idx("telefono", "celular", "phone")

    guests = []
    auto_id = 1
    for row in rows[1:]:
        if not row or not any(str(c).strip() for c in row if c is not None):
            continue

        def get_val(idx):
            if idx is not None and idx < len(row) and row[idx] is not None:
                return str(row[idx]).strip()
            return ""

        gid = get_val(id_idx) or f"INV-{auto_id:03d}"
        name = get_val(name_idx)
        if not name:
            continue

        guests.append({
            "guest_code": gid.upper(),
            "full_name": name,
            "company": get_val(company_idx),
            "position": get_val(pos_idx),
            "email": get_val(email_idx),
            "phone": get_val(phone_idx),
        })
        auto_id += 1

    return guests


def save_parsed_guests_to_event(guests_data: list[dict], event: Event) -> tuple[int, int]:
    """Guarda o actualiza (Upsert) los invitados dentro del evento especificado en MySQL."""
    inserted = 0
    updated = 0

    for item in guests_data:
        code = item["guest_code"].strip().upper()
        existing = Guest.query.filter_by(event_id=event.id, guest_code=code).first()

        if existing:
            existing.full_name = item["full_name"]
            existing.company = item.get("company", "")
            existing.position = item.get("position", "")
            existing.email = item.get("email", "")
            existing.phone = item.get("phone", "")
            existing.is_active = True
            updated += 1
        else:
            new_g = Guest(
                event_id=event.id,
                guest_code=code,
                full_name=item["full_name"],
                company=item.get("company", ""),
                position=item.get("position", ""),
                email=item.get("email", ""),
                phone=item.get("phone", ""),
                is_active=True,
            )
            db.session.add(new_g)
            inserted += 1

    db.session.commit()
    log.info(f"Guardados {inserted} nuevos y {updated} actualizados en evento '{event.name}'.")
    return inserted, updated


def sync_onedrive_link(raw_url: str, event_id: int | None = None) -> tuple[bool, str, int]:
    """Descarga el enlace de OneDrive/SharePoint y sincroniza los invitados en MySQL."""
    if event_id is None:
        event = get_or_create_active_event()
    else:
        event = Event.query.get(event_id)
        if not event:
            return False, "Evento no encontrado", 0

    direct_url = transform_onedrive_url(raw_url)
    log.info(f"Sincronizando enlace OneDrive para evento '{event.name}': {direct_url}")

    try:
        resp = requests.get(direct_url, timeout=18, allow_redirects=True)
        if resp.status_code != 200:
            return False, f"El servidor de OneDrive respondió con error HTTP {resp.status_code}.", 0

        raw_bytes = resp.content
        parsed = []

        # Determinar si es Excel o CSV
        if raw_bytes.startswith(b"PK\x03\x04") or "spreadsheet" in resp.headers.get("Content-Type", ""):
            parsed = parse_excel_file(raw_bytes)
        else:
            text = ""
            for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                try:
                    text = raw_bytes.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            parsed = parse_csv_stream(text)

        if not parsed:
            return False, "El archivo descargado de OneDrive está vacío o no tiene columnas reconocibles.", 0

        # Guardar en caché local de respaldo
        Config.ONEDRIVE_CACHES_DIR.mkdir(parents=True, exist_ok=True)
        cache_name = f"doc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        cache_path = Config.ONEDRIVE_CACHES_DIR / cache_name
        cache_path.write_bytes(raw_bytes)

        # Actualizar evento
        event.onedrive_url = raw_url
        event.cache_filename = cache_name
        event.last_sync = datetime.utcnow()

        ins, upd = save_parsed_guests_to_event(parsed, event)
        return True, f"Sincronización exitosa: {len(parsed)} invitados procesados ({ins} nuevos, {upd} actualizados).", len(parsed)

    except Exception as e:
        log.error(f"Error sincronizando OneDrive: {e}")
        return False, f"Error al conectar con OneDrive: {e}", 0


def migrate_legacy_data():
    """Migra datos existentes desde settings.json, cache de OneDrive y embeddings.json hacia MySQL."""
    event = get_or_create_active_event()

    # 1. Si no hay invitados en MySQL, intentar cargar la última caché disponible
    if Guest.query.filter_by(event_id=event.id).count() == 0:
        log.info("Base de datos MySQL sin invitados. Verificando cachés previas...")
        settings_path = Config.BASE_DIR / "settings.json"
        if settings_path.exists():
            try:
                st = json.loads(settings_path.read_text(encoding="utf-8"))
                docs = st.get("documents", [])
                if docs:
                    latest_doc = docs[0]
                    cache_file = latest_doc.get("cache_file")
                    if cache_file:
                        cache_path = Config.ONEDRIVE_CACHES_DIR / cache_file
                        if cache_path.exists():
                            raw = cache_path.read_bytes()
                            content = ""
                            for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
                                try:
                                    content = raw.decode(enc)
                                    break
                                except UnicodeDecodeError:
                                    continue
                            guests_data = parse_csv_stream(content)
                            if guests_data:
                                save_parsed_guests_to_event(guests_data, event)
                                log.info(f"Migrados {len(guests_data)} invitados desde {cache_file} a MySQL.")
            except Exception as e:
                log.warning(f"Error migrando datos legacy de settings: {e}")

    # 2. Migrar perfiles faciales desde embeddings.json si existen
    if FaceProfile.query.count() == 0:
        emb_path = Config.FACE_DATA_DIR / "embeddings.json"
        if emb_path.exists():
            try:
                emb_data = json.loads(emb_path.read_text(encoding="utf-8"))
                for guest_code, face_list in emb_data.items():
                    guest = Guest.query.filter_by(event_id=event.id, guest_code=guest_code).first()
                    if not guest:
                        continue
                    for f in face_list:
                        fp = FaceProfile(
                            guest_id=guest.id,
                            image_id=f.get("image_id", "img_legacy"),
                            filename=f.get("filename", ""),
                            thumb_filename=f.get("thumb_filename", ""),
                            embedding_json=json.dumps(f.get("embedding", [])),
                            quality_score=f.get("score", 1.0),
                        )
                        db.session.add(fp)
                db.session.commit()
                log.info("Migrados perfiles faciales legacy a MySQL.")
            except Exception as e:
                log.warning(f"Error migrando embeddings legacy: {e}")
