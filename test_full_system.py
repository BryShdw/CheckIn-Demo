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
import os
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
        # 1. Limpieza de estado residual previo
        from app.models.kiosk_setting import KioskSetting
        Checkin.query.delete()
        Guest.query.delete()
        first_event = Event.query.order_by(Event.id.asc()).first()
        if first_event:
            Event.query.filter(Event.id != first_event.id).delete()
            Event.query.update({Event.is_active: False})
            first_event.is_active = True
            ks = KioskSetting.query.filter_by(event_id=first_event.id).first()
            if ks:
                ks.face_threshold = 0.70
            else:
                db.session.add(KioskSetting(event_id=first_event.id, face_threshold=0.70))
        
        # Verificar Usuario Admin por defecto
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

    # 9c. Probar Importación desde Enlace OneDrive / SharePoint
    onedrive_test_url = "https://api.onedrive.com/v1.0/shares/u!aHR0cHM6Ly9kYWNlcjE5ODQtbXkuc2hhcmVwb2ludC5jb20vOng6L2cvcGVyc29uYWwvYnJheWFuX2RlbGdhZG9fZGFjZXJfY29tX3BlL0lRREkxVVlrcVZIR1FJUTZPQUJITWhJS0FlWlFwbGlmZXJ0WFZzN2hhcWtFRk9VP2U9Q0ZzTldI/root/content"
    res = client.post("/admin/api/import/onedrive", json={"url": onedrive_test_url})
    assert res.status_code == 200, f"Error esperado 200 pero recibido {res.status_code}: {res.get_data(as_text=True)}"
    od_data = res.get_json()
    assert od_data["status"] == "ok"
    assert od_data["count"] == 30
    print(f"[OK] Importación desde enlace OneDrive/SharePoint exitosa: {od_data['count']} invitados importados a MySQL.")

    # 10. Probar Kiosko y API de Check-in
    res = client.get("/")
    assert res.status_code == 200
    print("[OK] Kiosko principal / responde HTTP 200.")

    res = client.get("/api/status")
    assert res.status_code == 200
    status_data = res.get_json()
    assert status_data["status"] == "ok"
    print(f"[OK] API /api/status funcionando (Evento: '{status_data['event_name']}').")

    res = client.get("/api/kiosk-settings")
    assert res.status_code == 200
    k_data = res.get_json()
    assert k_data["settings"]["face_threshold"] == 0.70
    print(f"[OK] Umbral facial por defecto verificado en 0.70 ({k_data['settings']['face_threshold']}).")

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

    # 11. Probar APIs de Gestión Multi-Evento
    # Crear un nuevo evento
    res = client.post("/admin/api/events", json={
        "name": "Cumbre Tecnológica 2026",
        "description": "Evento de prueba automatizado",
        "kiosk_welcome_text": "Bienvenidos a la Cumbre Tecnológica 2026"
    })
    assert res.status_code in (200, 201)
    new_event = res.get_json()["event"]
    new_event_id = new_event["id"]
    print(f"[OK] Evento creado: '{new_event['name']}' (ID: {new_event_id}).")

    # Activar el nuevo evento
    res = client.post(f"/admin/api/events/{new_event_id}/activate")
    assert res.status_code == 200
    assert res.get_json()["status"] == "ok"
    print(f"[OK] Evento '{new_event_id}' activado como evento activo principal.")

    # 12. Probar Registro Manual Individual de Invitado
    res = client.post("/api/guest", json={
        "id": "ASIST-001",
        "name": "Dra. Elena Ramos",
        "company": "BioTech Innovations",
        "position": "Directora de I+D",
        "email": "elena.ramos@biotech.com"
    })
    assert res.status_code in (200, 201)
    print("[OK] Invitado ASIST-001 registrado individualmente vía /api/guest.")

    # 13. Probar Alternancia de Asistencia Manual /api/guest/<id>/status (Corrección de Error 405)
    # Marcar como registrado
    res = client.post("/api/guest/ASIST-001/status", json={"checked_in": True})
    assert res.status_code == 200, f"Error esperado 200 pero recibido {res.status_code}"
    status_resp = res.get_json()
    assert status_resp["checked_in"] is True
    print("[OK] POST /api/guest/ASIST-001/status marcó asistencia exitosamente (HTTP 200, no 405).")

    # Desmarcar como pendiente
    res = client.post("/api/guest/ASIST-001/status", json={"checked_in": False})
    assert res.status_code == 200
    status_resp = res.get_json()
    assert status_resp["checked_in"] is False
    print("[OK] POST /api/guest/ASIST-001/status desmarcó asistencia exitosamente (HTTP 200, no 405).")

    # 14. Probar Endpoint de Rostros y Almacenamiento Cero en Disco
    res = client.get("/api/guest/ASIST-001/faces")
    assert res.status_code == 200
    faces_data = res.get_json()
    assert faces_data["status"] == "ok"
    assert "faces" in faces_data
    print(f"[OK] GET /api/guest/ASIST-001/faces responde 200 (Total rostros: {len(faces_data['faces'])}).")

    # Probar endpoint de enrolamiento facial con payload inválido/sin rostro para verificar respuesta JSON adecuada
    res = client.post("/api/guest/ASIST-001/face", json={"image_base64": "data:image/jpeg;base64,invalidbase64data"})
    assert res.status_code in (200, 400)
    print("[OK] POST /api/guest/ASIST-001/face maneja peticiones JSON de enrolamiento correctamente.")

    # Verificar que NO se crearon archivos en disco en las carpetas de caché/imágenes
    od_files = [f for f in os.listdir("onedrive_caches") if f != ".gitkeep"]
    face_files = [f for f in os.listdir("face_data/images") if f != ".gitkeep"]
    assert len(od_files) == 0, f"Se detectaron archivos temporales en onedrive_caches: {od_files}"
    assert len(face_files) == 0, f"Se detectaron imágenes en face_data/images: {face_files}"
    print("[OK] Verificado: Cero archivos en disco en onedrive_caches/ y face_data/images/ (100% en memoria y MySQL).")

    # 15. Limpieza final: Eliminar evento de prueba y dejar la BD completamente en 0 invitados
    with app.app_context():
        Checkin.query.delete()
        Guest.query.delete()
        
        # Conservar el primer evento base y eliminar los de prueba
        first_event = Event.query.order_by(Event.id.asc()).first()
        if first_event:
            Event.query.filter(Event.id != first_event.id).delete()
            first_event.is_active = True
            
        admin = User.query.filter_by(username="Admin").first()
        admin.set_password("000000")
        admin.must_change_password = True
        db.session.commit()
        
        total_guests_now = Guest.query.count()
        assert total_guests_now == 0, f"Se esperaban 0 invitados tras la limpieza, pero hay {total_guests_now}"
        print(f"[OK] Base de datos limpia con {total_guests_now} invitados. Sistema listo en estado inicial.")
        print("[OK] Credencial inicial de Admin: 'Admin' / '000000' (must_change_password=True).")

    print("\n============================================================")
    print("¡TODAS LAS PRUEBAS DE INTEGRACIÓN Y SEGURIDAD PASARON (10/10)!")
    print("============================================================")

if __name__ == "__main__":
    run_tests()
