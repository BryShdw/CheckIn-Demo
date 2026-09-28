import logging
from app.extensions import db
from app.models.user import User

log = logging.getLogger(__name__)


def ensure_default_admin():
    """
    Crea el usuario administrador por defecto si la base de datos está vacía.
    Usuario: Admin
    Contraseña inicial: 000000
    must_change_password: True (obliga al usuario a cambiarla tras el primer inicio de sesión).
    """
    admin = User.query.filter_by(username="Admin").first()
    if not admin:
        admin_lower = User.query.filter_by(username="admin").first()
        if admin_lower:
            return admin_lower

        log.info("Creando usuario administrador por defecto (Admin)...")
        admin = User(
            username="Admin",
            email="admin@dacer.com.pe",
            role="SUPERADMIN",
            is_active=True,
            must_change_password=True,
        )
        admin.set_password("000000")
        db.session.add(admin)
        db.session.commit()
        log.info("Usuario 'Admin' creado con contraseña base '000000' (cambio obligatorio en primer login).")
    return admin


def authenticate_user(username: str, password: str) -> tuple[User | None, str | None]:
    """Valida credenciales de usuario."""
    user = User.query.filter(
        db.or_(User.username == username, User.email == username)
    ).first()

    if not user:
        return None, "Usuario o contraseña incorrectos."

    if not user.is_active:
        return None, "Este usuario se encuentra desactivado. Contacte al administrador."

    if not user.check_password(password):
        return None, "Usuario o contraseña incorrectos."

    return user, None


def change_password(user: User, new_password: str) -> tuple[bool, str]:
    """Actualiza la contraseña del usuario y desactiva el flag must_change_password."""
    if len(new_password) < 6:
        return False, "La nueva contraseña debe tener al menos 6 caracteres."

    if new_password == "000000":
        return False, "No puedes usar la contraseña por defecto. Elige una más segura."

    user.set_password(new_password)
    user.must_change_password = False
    db.session.commit()
    return True, "Contraseña actualizada exitosamente."
