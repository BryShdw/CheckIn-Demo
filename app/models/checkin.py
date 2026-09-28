from datetime import datetime
from app.extensions import db


class Checkin(db.Model):
    __tablename__ = "checkins"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    guest_id = db.Column(db.Integer, db.ForeignKey("guests.id", ondelete="CASCADE"), nullable=False, index=True)
    verified_by_user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    method = db.Column(db.String(20), nullable=False)  # FACIAL, QR, MANUAL
    confidence_score = db.Column(db.Float, nullable=True)
    kiosk_identifier = db.Column(db.String(64), default="KIOSK-MAIN", nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    printed_success = db.Column(db.Boolean, default=True, nullable=False)
    checked_in_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "guest_id": self.guest_id,
            "guest_code": self.guest.guest_code if self.guest else None,
            "guest_name": self.guest.full_name if self.guest else None,
            "method": self.method,
            "confidence_score": self.confidence_score,
            "kiosk_identifier": self.kiosk_identifier,
            "ip_address": self.ip_address,
            "printed_success": self.printed_success,
            "checked_in_at": self.checked_in_at.isoformat() if self.checked_in_at else None,
            "verified_by": self.verifier.username if self.verifier else "Autoservicio",
        }
