from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import login_manager, limiter, db
from app.models.user import User
from app.services.auth_service import authenticate_user, change_password
from app.services.audit_service import log_audit

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        if current_user.must_change_password:
            return redirect(url_for("auth.change_password_view"))
        return redirect(url_for("admin.admin_dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user, err = authenticate_user(username, password)
        if err:
            flash(err, "danger")
            log_audit("LOGIN_FAILED", details=f"Intento fallido para usuario: {username}", ip_address=request.remote_addr)
            return render_template("auth/login.html", username=username), 401

        login_user(user, remember=True)
        user.last_login = datetime.utcnow()
        db.session.commit()

        log_audit("LOGIN_SUCCESS", user_id=user.id, details=f"Inicio de sesión exitoso ({user.role})", ip_address=request.remote_addr)

        if user.must_change_password:
            flash("Bienvenido. Por seguridad, debes actualizar tu contraseña por defecto antes de continuar.", "warn")
            return redirect(url_for("auth.change_password_view"))

        next_url = request.args.get("next")
        return redirect(next_url or url_for("admin.admin_dashboard"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    log_audit("LOGOUT", user_id=current_user.id, ip_address=request.remote_addr)
    logout_user()
    flash("Has cerrado sesión correctamente.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password_view():
    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if new_password != confirm_password:
            flash("Las contraseñas no coinciden. Inténtalo de nuevo.", "danger")
            return render_template("auth/change_password.html")

        ok, msg = change_password(current_user, new_password)
        if not ok:
            flash(msg, "danger")
            return render_template("auth/change_password.html")

        log_audit("PASSWORD_CHANGE", user_id=current_user.id, details="Contraseña actualizada exitosamente", ip_address=request.remote_addr)
        flash("Contraseña actualizada con éxito. Ya puedes administrar el sistema.", "success")
        return redirect(url_for("admin.admin_dashboard"))

    return render_template("auth/change_password.html")
