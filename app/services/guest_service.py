import logging
from urllib.parse import urlparse, parse_qs, unquote
from app.config import Config
from app.extensions import db
from app.models.event import Event
from app.models.guest import Guest
from app.models.kiosk_setting import KioskSetting
from app.models.checkin import Checkin

log = logging.getLogger(__name__)


def get_or_create_active_event() -> Event:
    """Retorna el evento actualmente activo o crea el evento por defecto en MySQL."""
    event = Event.query.filter_by(is_active=True).first()
    if not event:
        event = Event(
            slug="evento-demo-2026",
            name=Config.DEFAULT_EVENT_NAME,
            description="Evento principal de demostración y acreditación",
            is_active=True,
        )
        db.session.add(event)
        db.session.commit()
        log.info(f"Evento activo por defecto creado en MySQL: {event.name}")
    return event


def get_kiosk_settings(event_id: int | None = None) -> KioskSetting:
    """Retorna o crea la configuración operativa del kiosko en MySQL."""
    if event_id is None:
        event = get_or_create_active_event()
        event_id = event.id

    setting = KioskSetting.query.filter_by(event_id=event_id).first()
    if not setting:
        setting = KioskSetting(
            event_id=event_id,
            scan_method="both",
            operation_mode="manual",
            face_threshold=Config.DEFAULT_FACE_THRESHOLD,
        )
        db.session.add(setting)
        db.session.commit()
    return setting


def update_kiosk_settings(key: str, value, event_id: int | None = None) -> KioskSetting:
    """Actualiza un parámetro del kiosko en MySQL."""
    setting = get_kiosk_settings(event_id)
    if key == "method" and str(value).lower() in ("both", "facial", "qr"):
        setting.scan_method = str(value).lower()
    elif key == "mode" and str(value).lower() in ("manual", "auto"):
        setting.operation_mode = str(value).lower()
    elif key == "face_threshold":
        setting.face_threshold = max(0.40, min(0.90, float(value)))
    db.session.commit()
    return setting


def extract_candidate_ids(raw_id: str) -> list[str]:
    """Extrae posibles identificadores de un texto crudo o URL de código QR."""
    candidates = []
    cleaned = (raw_id or "").strip()
    if not cleaned:
        return candidates

    candidates.append(cleaned)
    candidates.append(cleaned.upper())

    if "?" in cleaned or "=" in cleaned or "/" in cleaned:
        try:
            unquoted = unquote(cleaned)
            if unquoted not in candidates:
                candidates.append(unquoted)
                candidates.append(unquoted.upper())
            parsed = urlparse(unquoted)
            qs = parse_qs(parsed.query)
            for k in ["id", "code", "codigo", "invitado", "guest", "uid", "q"]:
                if k in qs and qs[k]:
                    for val in qs[k]:
                        v = val.strip()
                        if v and v not in candidates:
                            candidates.append(v)
                            candidates.append(v.upper())
            parts = [p.strip() for p in parsed.path.split("/") if p.strip()]
            if parts:
                last_p = parts[-1]
                if last_p and last_p not in candidates:
                    candidates.append(last_p)
                    candidates.append(last_p.upper())
        except Exception:
            pass

    seen = set()
    result = []
    for c in candidates:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return result


def find_guest(guest_code_or_url: str, event_id: int | None = None) -> Guest | None:
    """Busca un invitado en MySQL por código, QR o candidatos extraídos."""
    if not guest_code_or_url:
        return None

    if event_id is None:
        event = get_or_create_active_event()
        event_id = event.id

    candidates = extract_candidate_ids(guest_code_or_url)
    for cand in candidates:
        guest = Guest.query.filter(
            Guest.event_id == event_id,
            db.or_(
                Guest.guest_code == cand,
                Guest.guest_code == cand.upper(),
                Guest.qr_hash == cand,
            )
        ).first()
        if guest:
            return guest
    return None


def list_guests(event_id: int | None = None) -> list[dict]:
    """Lista todos los invitados del evento activo en formato dict."""
    if event_id is None:
        event = get_or_create_active_event()
        event_id = event.id

    guests = Guest.query.filter_by(event_id=event_id, is_active=True).order_by(Guest.id.asc()).all()
    return [g.to_dict() for g in guests]


def create_guest(full_name: str, company: str = "", position: str = "",
                 guest_code: str | None = None, email: str = "", phone: str = "",
                 category: str = "GENERAL", event_id: int | None = None) -> Guest:
    """Crea un nuevo invitado en MySQL."""
    if event_id is None:
        event = get_or_create_active_event()
        event_id = event.id

    if not guest_code:
        # Generar código correlativo tipo INV-001
        count = Guest.query.filter_by(event_id=event_id).count() + 1
        guest_code = f"INV-{count:03d}"
        while Guest.query.filter_by(event_id=event_id, guest_code=guest_code).first():
            count += 1
            guest_code = f"INV-{count:03d}"

    guest = Guest(
        event_id=event_id,
        guest_code=guest_code.strip().upper(),
        full_name=full_name.strip(),
        company=company.strip() if company else "",
        position=position.strip() if position else "",
        email=email.strip() if email else "",
        phone=phone.strip() if phone else "",
        category=category.strip() if category else "GENERAL",
        is_active=True,
    )
    db.session.add(guest)
    db.session.commit()
    return guest


def delete_guest(guest_code: str, event_id: int | None = None) -> bool:
    """Elimina un invitado y sus asistencias en cascada en MySQL."""
    guest = find_guest(guest_code, event_id)
    if not guest:
        return False
    db.session.delete(guest)
    db.session.commit()
    return True


def reset_all_checkins(event_id: int | None = None) -> int:
    """Elimina todas las asistencias del evento activo en MySQL."""
    if event_id is None:
        event = get_or_create_active_event()
        event_id = event.id

    count = Checkin.query.filter_by(event_id=event_id).count()
    Checkin.query.filter_by(event_id=event_id).delete()
    db.session.commit()
    return count


def get_event_stats(event_id: int | None = None) -> dict:
    """Calcula métricas y estadísticas de asistencia en tiempo real desde MySQL."""
    if event_id is None:
        event = get_or_create_active_event()
        event_id = event.id

    total = Guest.query.filter_by(event_id=event_id, is_active=True).count()

    # Contar invitados únicos que tienen al menos un checkin
    checked_in = db.session.query(db.func.count(db.func.distinct(Checkin.guest_id)))\
        .filter(Checkin.event_id == event_id).scalar() or 0

    pending = max(0, total - checked_in)
    pct = round((checked_in / total * 100), 1) if total > 0 else 0.0

    # Desglose por método
    facial_count = Checkin.query.filter_by(event_id=event_id, method="FACIAL").count()
    qr_count = Checkin.query.filter_by(event_id=event_id, method="QR").count()
    manual_count = Checkin.query.filter_by(event_id=event_id, method="MANUAL").count()

    return {
        "total": total,
        "total_guests": total,
        "checked_in": checked_in,
        "pending": pending,
        "percentage": pct,
        "attendance_percentage": pct,
        "methods": {
            "facial": facial_count,
            "qr": qr_count,
            "manual": manual_count,
        },
        "method_facial": facial_count,
        "method_qr": qr_count,
        "method_manual": manual_count,
    }
