import json
from datetime import datetime
from app.extensions import db


class FaceProfile(db.Model):
    __tablename__ = "face_profiles"

    id = db.Column(db.Integer, primary_key=True)
    guest_id = db.Column(db.Integer, db.ForeignKey("guests.id", ondelete="CASCADE"), nullable=False, index=True)
    image_id = db.Column(db.String(64), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    thumb_filename = db.Column(db.String(255), nullable=False)
    embedding_json = db.Column(db.Text, nullable=False)
    quality_score = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def get_embedding(self) -> list[float]:
        try:
            return json.loads(self.embedding_json)
        except Exception:
            return []

    def set_embedding(self, embedding_list: list[float]):
        self.embedding_json = json.dumps(embedding_list)

    def to_dict(self) -> dict:
        return {
            "image_id": self.image_id,
            "filename": self.filename,
            "thumb_filename": self.thumb_filename,
            "quality_score": self.quality_score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
