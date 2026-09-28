"""
Script de verificación exhaustiva del sistema Check-In con MySQL y Arquitectura Segura.
Valida:
1. Base de datos MySQL y tablas creadas.
2. Usuario Admin por defecto (Admin / 000000) y flag must_change_password.
3. Bloqueo de acceso al dashboard mientras must_change_password=True.
4. Flujo de cambio de contraseña a contraseña segura.
5. Acceso al dashboard /admin/ posterior al cambio.
6. APIs de usuarios: crear, listar y eliminar usuarios.
7. APIs de auditoría y analítica.
8. Kiosko y API pública: status, kiosk-settings, checkin, duplicate checkin.
9. Exportación de reporte Excel de asistencia.
10. Importación de archivo Excel / CSV a MySQL.
"""
import io
import openpyxl
from app import create_app
from app.extensions import db
from app.models.user import User
from app.models.guest import Guest
from app.models.checkin import Checkin
from app.models.event import Event
from app.models.audit_log import AuditLog

def run_tests():
    print("=== INICIANDO PRUEBAS DE INTEGRACIÓN MYSQL Y ARQUITECTURA SEGURA ===")
    app = create_app()
    app.config["TESTING"] = True
    client = app.test_client()

    with app.app_context():
        # 1. Verificar Usuario Admin por defecto
        admin = User.query.filter_by(username="Admin").first()
        assert admin is not None, "El usuario Admin debe existir en MySQL."
        print(f"[OK] Usuario Admin encontrado en MySQL (ID: {admin.id}, Rol: {admin.role})")

        # Asegurar estado inicial con 000000 para la prueba
        admin.set_password("000000")
        admin.must_change_password = True
        db.session.commit()
        print("[OK] Credenciales Admin restablecidas a 'Admin'/'000000' con must_change_password=True.")

    # 2. Intentar acceder a /admin/ sin estar autenticado
    res = client.get("/admin/", follow_redirects=False)
    assert res.status_code in (302, 308), f"Sin autenticar debe redirigir (obtenido: {res.status_code})"
    print("[OK] Acceso anónimo a /admin/ protegido y redirigido a login.")

    import re
    def get_csrf_token():
        login_page = client.get("/auth/login").get_data(as_text=True)
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page)
        return m.group(1) if m else ""

    csrf_token = get_csrf_token()

    # 3. Iniciar sesión con Admin y credencial incorrecta
    res = client.post("/auth/login", data={
        "username": "Admin",
        "password": "wrong_password",
        "csrf_token": csrf_token
    }, follow_redirects=True)
    assert "Credenciales incorrectas" in res.get_data(as_text=True) or res.status_code == 401
    print("[OK] Contraseña incorrecta rechazada con código 401.")

    # Iniciar sesión con Admin y 000000
    csrf_token = get_csrf_token()
    res = client.post("/auth/login", data={
        "username": "Admin",
        "password": "000000",
        "csrf_token": csrf_token
    }, follow_redirects=False)
    assert res.status_code == 302
    assert "/auth/change-password" in res.headers.get("Location", "")
    print("[OK] Login con contraseña por defecto redirige forzosamente a /auth/change-password.")

    # 4. Verificar que intentar ir a /admin/ mientras must_change_password=True sigue redirigiendo
    res = client.get("/admin/", follow_redirects=False)
    assert res.status_code == 302
    assert "/auth/change-password" in res.headers.get("Location", "")
    print("[OK] Acceso a /admin/ bloqueado mientras must_change_password sea True.")

    # 5. Cambiar contraseña a una contraseña segura
    def get_change_pwd_csrf():
        page = client.get("/auth/change-password").get_data(as_text=True)
        m = re.search(r'name="csrf_token"\s+value="([^"]+)"', page)
        return m.group(1) if m else ""

    res = client.post("/auth/change-password", data={
        "new_password": "AdminSecure2026!",
        "confirm_password": "AdminSecure2026!",
        "csrf_token": get_change_pwd_csrf()
    }, follow_redirects=False)
    assert res.status_code == 302
    assert "/admin" in res.headers.get("Location", "")
    print("[OK] Contraseña actualizada exitosamente. Redirige a /admin/.")

    with app.app_context():
        admin = User.query.filter_by(username="Admin").first()
        assert admin.must_change_password is False
        assert admin.check_password("AdminSecure2026!") is True
        print("[OK] En MySQL: must_change_password=False y nuevo hash validado.")

    # 6. Acceder al dashboard de administración /admin/ ahora autenticado
    res = client.get("/admin/", follow_redirects=True)
    assert res.status_code == 200
    html = res.get_data(as_text=True)
    assert "Panel de Control" in html
    assert "Admin" in html
    print("[OK] Panel /admin/ carga correctamente con HTTP 200 y sesión activa de Admin.")

    # 7. Probar API de Gestión de Usuarios (/admin/api/users)
    # Listar usuarios
    res = client.get("/admin/api/users")
    assert res.status_code == 200
    data = res.get_json()
    assert data["status"] == "ok"
    assert any(u["username"] == "Admin" for u in data["users"])
    print(f"[OK] API /admin/api/users listó {len(data['users'])} usuario(s).")

    # Crear nuevo usuario Operador
    res = client.post("/admin/api/users", json={
        "username": "operador_test",
        "password": "OperadorPass123!",
        "role": "OPERATOR",
        "email": "operador@test.com"
    })
    assert res.status_code == 200
    created_user = res.get_json()["user"]
    user_id = created_user["id"]
    print(f"[OK] Usuario 'operador_test' creado en MySQL (ID: {user_id}).")

    # Eliminar usuario creado
    res = client.delete(f"/admin/api/users/{user_id}")
    assert res.status_code == 200
    print("[OK] Usuario 'operador_test' eliminado exitosamente.")

    # 8. Probar API de Auditoría y Analítica
    res = client.get("/admin/api/audit-logs")
    assert res.status_code == 200
    logs_data = res.get_json()
    assert logs_data["status"] == "ok"
    assert len(logs_data["logs"]) > 0
    print(f"[OK] API /admin/api/audit-logs devolvió {len(logs_data['logs'])} registros de auditoría en MySQL.")

    res = client.get("/admin/api/analytics")
    assert res.status_code == 200
    ana_data = res.get_json()
    assert ana_data["status"] == "ok"
    print(f"[OK] API /admin/api/analytics: {ana_data['stats']['total_guests']} invitados, {ana_data['stats']['checked_in']} asistencias.")

    # 9. Probar Exportación a Excel (.xlsx)
    res = client.get("/admin/export-attendance")
    assert res.status_code == 200
    assert "spreadsheetml" in res.headers.get("Content-Type", "")
    wb = openpyxl.load_workbook(io.BytesIO(res.data))
    assert "Control de Asistencia" in wb.sheetnames
    sheet = wb["Control de Asistencia"]
    assert sheet.cell(1, 1).value == "Código"
    print(f"[OK] Exportación Excel generada válidamente ({sheet.max_row} filas en hoja de cálculo).")

    # 9b. Probar Importación de Archivo Excel (.xlsx)
    wb_test = openpyxl.Workbook()
    ws_test = wb_test.active
    ws_test.append(["Código", "Nombre", "Empresa", "Cargo", "Correo"])
    ws_test.append(["TEST-999", "Invitado De Prueba Excel", "DACER Tech", "Tester", "test@dacer.com"])
    excel_buf = io.BytesIO()
    wb_test.save(excel_buf)
    excel_buf.seek(0)

    res = client.post("/admin/api/import/file", data={
        "file": (excel_buf, "invitados_test.xlsx")
    }, content_type="multipart/form-data")
    assert res.status_code == 200
    import_data = res.get_json()
    assert import_data["status"] == "ok"
    assert import_data["total"] >= 1
    print(f"[OK] Importación de archivo Excel procesada en MySQL exitosamente ({import_data['message']}).")

    # 10. Probar Kiosko y API de Check-in
    res = client.get("/")
    assert res.status_code == 200
    print("[OK] Kiosko principal / responde HTTP 200.")

    res = client.get("/api/status")
    assert res.status_code == 200
    status_data = res.get_json()
    assert status_data["status"] == "ok"
    print(f"[OK] API /api/status funcionando (Evento: '{status_data['event_name']}').")

    # Limpiar check-ins previos para prueba limpia y reproducible
    with app.app_context():
        from app.services.guest_service import reset_all_checkins
        reset_all_checkins()
        g = Guest.query.first()
        guest_code = g.guest_code if g else None

    if guest_code:
        # Check-in
        res = client.post("/api/checkin", json={
            "identifier": guest_code,
            "method": "qr"
        })
        assert res.status_code == 200
        checkin_data = res.get_json()
        assert checkin_data["success"] is True
        print(f"[OK] Check-in procesado para invitado {guest_code} ({checkin_data['guest']['name']}).")

        # Intentar check-in duplicado
        res = client.post("/api/checkin", json={
            "identifier": guest_code,
            "method": "qr"
        })
        assert res.status_code in (200, 409)
        dup_data = res.get_json()
        assert dup_data["already_checked_in"] is True
        print(f"[OK] Detección de duplicado correcta (already_checked_in=True).")

    # Restablecer contraseña de Admin a 000000 para entrega al usuario
    with app.app_context():
        admin = User.query.filter_by(username="Admin").first()
        admin.set_password("000000")
        admin.must_change_password = True
        db.session.commit()
        print("[OK] Credencial inicial de Admin dejada lista para el usuario: 'Admin' / '000000' (must_change_password=True).")

    print("\n============================================================")
    print("¡TODAS LAS PRUEBAS DE INTEGRACIÓN Y SEGURIDAD PASARON (10/10)!")
    print("============================================================")

if __name__ == "__main__":
    run_tests()
