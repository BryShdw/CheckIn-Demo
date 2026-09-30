# Arquitectura del Sistema CheckIn-DACER

## 1. Resumen de la Arquitectura

El sistema CheckIn-DACER es una solucion empresarial de control de acceso, acreditacion biometrica e impresion termica de credenciales. La aplicacion esta disenada bajo el patron Application Factory de Flask y una arquitectura multicapa desacoplada (Model-Service-Controller) que garantiza alta cohesión, bajo acoplamiento y facilidad de mantenimiento.

Toda la persistencia transaccional y biometrica reside en una base de datos relacional MySQL 8.0+, eliminando dependencias de archivos locales en disco para datos criticos.

---

## 2. Diagrama Estructural de Capas

```
+-------------------------------------------------------------------------------+
|                             Capa de Presentacion                              |
|   - Kiosko Autoservicio (HTML5 / CSS3 Vanilla / JS ES6+ / jsQR / Camara Web)  |
|   - Panel de Administracion (Bootstrap / Tailwind / Modales Reactivos / Fetch)|
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                       Capa de Ruteo y Control (Blueprints)                     |
|   - app.blueprints.kiosk : Ruteo del portal publico del totem autoservicio    |
|   - app.blueprints.admin : Gestion de eventos, usuarios, invitados y diseno   |
|   - app.blueprints.auth  : Autenticacion, sesiones y cambio forzado de clave  |
|   - app.blueprints.api   : Endpoints JSON de check-in, biometria y hardware   |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                         Capa de Servicios de Negocio                          |
|   - guest_service   : Logica de asistentes, eventos y configuraciones         |
|   - checkin_service : Validacion de asistencia y regla estricta de impresion  |
|   - face_service    : Redes neuronales YuNet y SFace (OpenCV DNN)             |
|   - import_service  : Procesamiento Excel/CSV y resolutor de OneDrive        |
|   - printer_service : Motor GDI de impresion nativa Brother QL-800            |
|   - audit_service   : Registro inmutable de eventos de seguridad              |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                     Capa de Persistencia (ORM SQLAlchemy)                     |
|   - User, Event, Guest, Checkin, FaceProfile, KioskSetting, AuditLog          |
+-------------------------------------------------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                         Motor de Base de Datos MySQL                          |
|   - MySQL Server 8.0+ (InnoDB, transacciones ACID, UTF-8 utf8mb4)             |
+-------------------------------------------------------------------------------+
```

---

## 3. Componentes Principales

### 3.1. Fabrica de Aplicaciones (Application Factory)
Ubicada en `app/__init__.py`. Centraliza la instanciacion de Flask, el registro de extensiones y la inicializacion controlada de componentes en el siguiente orden:
1. Carga de configuracion desde `app.config.Config`.
2. Inicializacion de extensiones: SQLAlchemy (`db`), Flask-Login (`login_manager`), CSRFProtect (`csrf`) y Limiter (`limiter`).
3. Registro de Blueprints con sus respectivos prefijos de URL.
4. Verificacion y creacion automatica de tablas en MySQL (`db.create_all()`).
5. Precarga en memoria del modelo biometrico y los perfiles faciales del evento activo.

### 3.2. Modelo de Control de Acceso Basado en Roles (RBAC)
Implementado mediante `Flask-Login` y el modelo `User`:
- **SUPERADMIN**: Control total del sistema, gestion de otros administradores, configuracion global y depuracion.
- **ADMIN**: Gestion de eventos, carga y edicion de asistentes, diseno de etiquetas, control de asistencias y metricas.
- **OPERATOR**: Acceso operativo para acreditacion manual, busqueda rapida y atencion de incidencias en sala.

### 3.3. Politica de Cambio Forzado de Contrasena
El modelo `User` incluye el campo booleano `must_change_password`. La credencial inicial de fabrica (`Admin` / `000000`) cuenta con este indicador activo. Un middleware en `app.blueprints.admin` intercepta cualquier intento de navegacion de usuarios con `must_change_password=True` y redirige forzosamente hacia `/auth/change-password`, bloqueando el acceso al panel hasta que se registre una clave con complejidad adecuada.

### 3.4. Auditoria Forense Inmutable
Cada operacion sensible (login, importacion, check-in, reimpresion, modificacion de parametros, borrado de datos) emite un registro a traves de `log_audit()` en la tabla `audit_logs`. Cada fila almacena:
- `user_id`: Identificador del usuario autenticado (o nulo para operaciones de kiosko publico).
- `action`: Verbo de accion estandarizado (ej. `CHECKIN_QR`, `CHECKIN_FACIAL`, `IMPORT_ONEDRIVE`, `PRINTER_TEST`).
- `target_type` y `target_id`: Entidad afectada y su identificador.
- `details`: Descripcion textual contextualizada de la accion.
- `ip_address`: Direccion IP del cliente que origino la peticion.
- `created_at`: Marca temporal ISO 8601 del servidor.

---

## 4. Estructura de Directorios

```
Checkin-Demo/
|-- app/
|   |-- __init__.py                 # Application factory
|   |-- config.py                   # Configuracion centralizada y variables de entorno
|   |-- extensions.py               # Instancias singleton de extensiones Flask
|   |-- blueprints/
|   |   |-- admin/                  # Rutas del panel administrativo
|   |   |-- api/                    # Endpoints RESTful para kiosko y clientes
|   |   |-- auth/                   # Autenticacion y cambio de contrasena
|   |   `-- kiosk/                  # Portal del kiosko autoservicio
|   |-- models/                     # Modelos de base de datos SQLAlchemy
|   |   |-- audit_log.py
|   |   |-- checkin.py
|   |   |-- event.py
|   |   |-- face_profile.py
|   |   |-- guest.py
|   |   |-- kiosk_setting.py
|   |   `-- user.py
|   `-- services/                   # Logica de negocio especializada
|       |-- audit_service.py
|       |-- checkin_service.py
|       |-- face_service.py
|       |-- guest_service.py
|       |-- import_service.py
|       `-- printer_service.py
|-- database/
|   |-- README.md                   # Documentacion del esquema MySQL
|   `-- schema.sql                  # Script DDL completo de creacion e inicializacion
|-- docs/                           # Documentacion tecnica detallada
|-- models/                         # Modelos ONNX de vision artificial (YuNet, SFace)
|-- static/                         # Recursos estaticos (CSS, logotipos PNG)
|-- templates/
|   |-- admin/admin.html            # Plantilla del panel administrativo
|   |-- auth/login.html             # Pantalla de inicio de sesion
|   |-- auth/change_password.html   # Pantalla de cambio obligatorio de clave
|   `-- kiosk/index.html            # Pantalla completa del kiosko autoservicio
|-- .env.example                    # Plantilla de variables de entorno
|-- app.py                          # Punto de entrada de la aplicacion
|-- iniciar_sistema.bat             # Script de lanzamiento para Windows
|-- requirements.txt                # Dependencias Python
|-- run.py                          # Punto de entrada estandar
|-- status.md                       # Estado de modulos y pruebas del sistema
`-- test_full_system.py             # Suite automatizada de pruebas integrales
```
