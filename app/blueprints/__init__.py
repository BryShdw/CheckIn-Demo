from app.blueprints.auth import auth_bp
from app.blueprints.kiosk import kiosk_bp
from app.blueprints.admin import admin_bp
from app.blueprints.api import api_bp

__all__ = ["auth_bp", "kiosk_bp", "admin_bp", "api_bp"]
