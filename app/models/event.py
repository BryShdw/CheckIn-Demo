import json
from datetime import datetime
from app.extensions import db


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    location = db.Column(db.String(150), nullable=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    onedrive_url = db.Column(db.Text, nullable=True)
    label_template = db.Column(db.Text, nullable=True)
    cache_filename = db.Column(db.String(255), nullable=True)
    last_sync = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    guests = db.relationship("Guest", backref="event", cascade="all, delete-orphan", lazy="dynamic")
    checkins = db.relationship("Checkin", backref="event", cascade="all, delete-orphan", lazy="dynamic")

    def get_label_template(self) -> dict | None:
        if not self.label_template:
            return None
        try:
            return json.loads(self.label_template)
        except Exception:
            return None

    def set_label_template(self, template_dict: dict | None):
        if template_dict is None:
            self.label_template = None
        else:
            self.label_template = json.dumps(template_dict, ensure_ascii=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "slug": self.slug,
            "name": self.name,
            "description": self.description,
            "location": self.location,
            "is_active": self.is_active,
            "onedrive_url": self.onedrive_url,
            "label_template": self.get_label_template(),
            "cache_filename": self.cache_filename,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "guest_count": self.guests.count(),
        }
