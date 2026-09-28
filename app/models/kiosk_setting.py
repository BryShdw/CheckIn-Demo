from datetime import datetime
from app.extensions import db


class KioskSetting(db.Model):
    __tablename__ = "kiosk_settings"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=True, unique=True)
    scan_method = db.Column(db.String(20), default="both", nullable=False)  # both, facial, qr
    operation_mode = db.Column(db.String(20), default="manual", nullable=False)  # manual, auto
    face_threshold = db.Column(db.Float, default=0.55, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "method": self.scan_method,
            "mode": self.operation_mode,
            "face_threshold": self.face_threshold,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
