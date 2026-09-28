from datetime import datetime
from app.extensions import db


class Guest(db.Model):
    __tablename__ = "guests"
    __table_args__ = (
        db.UniqueConstraint("event_id", "guest_code", name="uq_event_guest_code"),
    )

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    guest_code = db.Column(db.String(64), nullable=False, index=True)
    full_name = db.Column(db.String(150), nullable=False, index=True)
    company = db.Column(db.String(150), nullable=True)
    position = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    category = db.Column(db.String(50), default="GENERAL", nullable=False)
    qr_hash = db.Column(db.String(255), nullable=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    checkins = db.relationship("Checkin", backref="guest", cascade="all, delete-orphan", lazy="dynamic")
    face_profiles = db.relationship("FaceProfile", backref="guest", cascade="all, delete-orphan", lazy="dynamic")

    @property
    def latest_checkin(self):
        return self.checkins.order_by(db.desc("checked_in_at")).first()

    @property
    def is_checked_in(self) -> bool:
        c = self.latest_checkin
        return c is not None

    def to_dict(self) -> dict:
        latest = self.latest_checkin
        faces = self.face_profiles.all()
        return {
            "id": self.guest_code,
            "db_id": self.id,
            "event_id": self.event_id,
            "name": self.full_name,
            "company": self.company or "",
            "position": self.position or "",
            "email": self.email or "",
            "phone": self.phone or "",
            "category": self.category,
            "checked_in": latest is not None,
            "checked_in_at": latest.checked_in_at.isoformat() if latest else None,
            "checkin_method": latest.method if latest else None,
            "face_count": len(faces),
            "face_enrolled": len(faces) > 0,
            "faces": [f.to_dict() for f in faces],
        }
