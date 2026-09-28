import logging
from app.extensions import db
from app.models.audit_log import AuditLog

log = logging.getLogger(__name__)


def log_audit(action: str, user_id: int | None = None, target_type: str | None = None,
              target_id: str | None = None, details: str | None = None,
              ip_address: str | None = None):
    """Registra una acción en la tabla audit_logs de MySQL."""
    try:
        entry = AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
            ip_address=ip_address,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        log.error(f"Error registrando auditoría: {e}")
        db.session.rollback()
