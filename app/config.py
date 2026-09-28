import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dacer-checkin-secret-key-2026-secure-token")

    # MySQL Database Configuration
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = os.getenv("DB_PORT", "3306")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "root")
    DB_NAME = os.getenv("DB_NAME", "checkin_dacer_db")

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_recycle": 280,
        "pool_pre_ping": True,
        "pool_size": 10,
        "max_overflow": 20,
    }

    # Session & Security
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 horas

    # Directories
    BASE_DIR = BASE_DIR
    MODELS_DIR = BASE_DIR / "models"
    FACE_DATA_DIR = BASE_DIR / "face_data"
    FACE_IMAGES_DIR = FACE_DATA_DIR / "images"
    ONEDRIVE_CACHES_DIR = BASE_DIR / "onedrive_caches"
    QR_OUTPUT_DIR = BASE_DIR / "qr_output"

    # Hardware & Printing
    PRINTER_NAME = os.getenv("PRINTER_NAME", "Brother QL-800")
    PRINTER_MODEL = os.getenv("PRINTER_MODEL", "QL-800")
    LABEL_TYPE = os.getenv("LABEL_TYPE", "38x90")
    PRINTER_ENABLED = True

    # Kiosk Defaults
    DEFAULT_EVENT_NAME = os.getenv("DEFAULT_EVENT_NAME", "EVENTO DEMO 2026")
    DEFAULT_FACE_THRESHOLD = float(os.getenv("FACE_THRESHOLD", "0.55"))
