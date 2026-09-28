import logging
from flask import Flask
from app.config import Config
from app.extensions import db, login_manager, csrf, limiter
from app.blueprints import auth_bp, kiosk_bp, admin_bp, api_bp
from app.services.auth_service import ensure_default_admin
from app.services.guest_service import get_or_create_active_event
from app.services.face_service import init_face_service

# Configuración de logging corporativo
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


def create_app(config_class=Config) -> Flask:
    """Application Factory Pattern: crea y configura la instancia de Flask."""
    app = Flask(
        __name__,
        static_folder=str(config_class.BASE_DIR / "static"),
        template_folder=str(config_class.BASE_DIR / "templates"),
    )
    app.config.from_object(config_class)

    # Inicializar extensiones
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Registrar Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(kiosk_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)

    # Inicialización de Base de Datos y Servicios en el contexto de la aplicación
    with app.app_context():
        try:
            # 1. Crear tablas en MySQL si no existen
            db.create_all()
            log.info("Tablas de MySQL verificadas / creadas exitosamente.")

            # 2. Inicializar usuario Administrador por defecto (Admin / 000000)
            ensure_default_admin()

            # 3. Asegurar Evento Activo por defecto
            get_or_create_active_event()

            # 4. Inicializar modelos de Visión por Computadora y precargar embeddings
            init_face_service()

        except Exception as e:
            log.error(f"Error durante el arranque de base de datos/servicios: {e}")

    return app
