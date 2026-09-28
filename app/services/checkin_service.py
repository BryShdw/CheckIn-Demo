import logging
from app.extensions import db
from app.models.checkin import Checkin
from app.models.guest import Guest
from app.services.guest_service import find_guest
from app.services.printer_service import print_guest_ticket
from app.services.audit_service import log_audit

log = logging.getLogger(__name__)


def process_checkin(guest_code_or_url: str, method: str = "QR",
                    verified_by_user_id: int | None = None,
                    confidence_score: float | None = None,
                    kiosk_id: str = "KIOSK-MAIN",
                    ip_address: str | None = None,
                    force_reprint: bool = False) -> tuple[dict, int]:
    """
    Procesa la validación, impresión de ticket y registro de asistencia en MySQL.
    Garantía de integridad: Solo se registra la asistencia si la etiqueta se imprime correctamente.
    """
    guest = find_guest(guest_code_or_url)
    if not guest:
        return {
            "status": "not_found",
            "error": "Invitado no encontrado en la lista del evento.",
            "id": guest_code_or_url,
        }, 404

    # 1. Comprobación de asistencia previa
    if guest.is_checked_in and not force_reprint:
        latest = guest.latest_checkin
        return {
            "status": "duplicate",
            "success": False,
            "already_checked_in": True,
            "message": f"El invitado '{guest.full_name}' ya fue acreditado previamente.",
            "checked_in_at": latest.checked_in_at.isoformat() if latest else None,
            "guest": guest.to_dict(),
        }, 409

    # 2. Impresión física en Brother QL-800
    guest_dict = guest.to_dict()
    print_ok, print_msg = print_guest_ticket(guest_dict)
    if not print_ok:
        log.error(f"Fallo de impresión para {guest.guest_code}: {print_msg}")
        return {
            "status": "print_error",
            "error": f"Fallo al imprimir credencial: {print_msg}",
            "guest": guest_dict,
        }, 500

    # 3. Registrar asistencia en MySQL únicamente tras confirmación de impresión
    checkin = Checkin(
        event_id=guest.event_id,
        guest_id=guest.id,
        verified_by_user_id=verified_by_user_id,
        method=method.upper(),
        confidence_score=confidence_score,
        kiosk_identifier=kiosk_id,
        ip_address=ip_address,
        printed_success=True,
    )
    db.session.add(checkin)
    db.session.commit()

    # 4. Auditoría
    log_audit(
        action=f"CHECKIN_{method.upper()}" + ("_REPRINT" if force_reprint else ""),
        user_id=verified_by_user_id,
        target_type="GUEST",
        target_id=guest.guest_code,
        details=f"Acreditado: {guest.full_name} ({guest.company}). Impresión: OK.",
        ip_address=ip_address,
    )

    log.info(f"Check-in exitoso: {guest.guest_code} - {guest.full_name} ({method})")
    return {
        "status": "ok",
        "success": True,
        "message": f"Check-in exitoso para {guest.full_name}",
        "checkin_id": checkin.id,
        "checked_in_at": checkin.checked_in_at.isoformat(),
        "guest": guest.to_dict(),
    }, 200
