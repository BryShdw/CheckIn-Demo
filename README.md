# 🎟️ Sistema de Acreditación Inteligente CheckIn-DACER (MySQL + Facial + QR + Impresión Brother)

Plataforma empresarial de acreditación y control de acceso para eventos corporativos y masivos. Cuenta con **reconocimiento facial por visión artificial en CPU**, **escaneo de credenciales QR**, persistencia transaccional en **MySQL**, **gestión multi-evento**, **cuatro métodos de carga de asistentes** (incluyendo integración directa con **OneDrive / SharePoint**) e **impresión térmica de credenciales en Brother QL-800** con rollo DK-1208 (38 mm × 90.3 mm).

Diseñado para ejecutarse en una **Intel NUC con Windows 10 / 11** conectada a la impresora Brother oficial por puerto USB.

---

## 🚀 Novedades de la Rama `feature/mysql-security-architecture`

1. **Migración a Base de Datos Relacional MySQL**:
   - Transiciones desde archivos planos hacia una base de datos relacional MySQL (`checkin_dacer_db`) con transacciones ACID, índices optimizados y soporte completo UTF-8 (`utf8mb4`).
2. **Autenticación y Seguridad Empresarial**:
   - Control de acceso basado en roles (**SUPERADMIN**, **ADMIN**, **OPERATOR**).
   - Hashing criptográfico de contraseñas con **PBKDF2/SHA256**.
   - Credenciales iniciales por defecto (`Admin` / `000000`) con **cambio forzado obligatorio** en el primer inicio de sesión.
   - Protección contra falsificación de peticiones (**Flask-WTF CSRF**) y limitador de tasa (**Flask-Limiter**).
   - Registro forense inmutable de acciones en tabla de auditoría (`audit_logs`).
3. **Gestión Multi-Evento**:
   - Cada asistente, asistencia y configuración pertenece explícitamente a un evento.
   - Selector y creador de eventos integrado en el panel con estadísticas en tiempo real (% asistencia, totales y acreditados).
   - Conmutación en caliente del evento activo, recargando automáticamente la memoria del modelo biométrico.
4. **Múltiples Métodos de Carga de Asistentes**:
   - **📁 Archivo Excel (.xlsx) / CSV (.csv)**: Mapeo inteligente de encabezados (ID, Nombre, Empresa, Cargo, Correo, Teléfono).
   - **☁️ Enlace OneDrive / SharePoint**: Resolvedor inteligente que transforma enlaces compartidos corporativos a descarga directa (`?download=1`), evitando errores de migración o bloqueos (solución a error HTTP 308).
   - **👤 Registro Individual**: Formulario rápido para acreditar o agregar asistentes de último minuto en sala.
5. **Reconocimiento Facial de Alta Precisión (Umbral 0.70)**:
   - OpenCV DNN con redes neuronales **YuNet** (detección de rostro y landmarks) y **SFace** (vector de características de 128 dimensiones).
   - Umbral biométrico calibrado por defecto en **0.70** para garantizar máxima especificidad y eliminar falsos positivos.
   - Enrolamiento de 1 a 4 fotos por persona desde cámara web o subida de imágenes.
6. **Flujo de Check-in Vinculado a la Impresión Térmica**:
   - Renderizado nativo a 300 DPI mediante el spooler de Windows GDI (`win32print`), adaptado exclusivamente para etiquetas pre-impresas en rollo **DK-1208** (Nombre completo destacado, Empresa y Cargo, sin elementos distractores).
   - La asistencia se confirma únicamente tras la emisión exitosa del ticket.

---

## 🏛️ Arquitectura del Sistema

```
                   [ Microsoft OneDrive / SharePoint ]
                   (Enlaces compartidos o archivos .xlsx / .csv)
                                     │
                                     ▼ (Sincronización directa ?download=1)
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             NUC (Windows 10 / 11)                                │
│                                                                                  │
│   MySQL 8.0+ (checkin_dacer_db)                                                  │
│   ├── users             (Roles, hashes PBKDF2, must_change_password)             │
│   ├── events            (Eventos activos, metadatos, caché)                      │
│   ├── guests            (Asistentes vinculados a event_id)                       │
│   ├── checkins          (Asistencias, método QR/Facial, timestamp)               │
│   ├── face_profiles     (Embeddings 128D vinculados a invitados)                 │
│   ├── kiosk_settings    (Modo, método de escaneo, umbral 0.70)                   │
│   └── audit_logs        (Auditoría forense inmutable)                            │
│                                                                                  │
│   Backend Modular Flask (Application Factory)                                    │
│   ├── blueprints/ (kiosk, admin, auth, api)                                      │
│   └── services/   (face_service, import_service, printer_service, guest_service) │
│                                                                                  │
│                    ┌──────────────────┴──────────────────┐                       │
│                    ▼                                     ▼                       │
│          Kiosko Autoservicio                     Panel de Control                │
│             (index.html)                           (admin.html)                  │
└────────────────────┬─────────────────────────────────────┬───────────────────────┘
                     │                                     │
                     └──────────────────┬──────────────────┘
                                        ▼
                           Windows GDI Print Spooler
                               (win32print)
                                        │
                                        ▼
                         Impresora Brother QL-800
                       Rollo DK-1208 (38mm × 90.3mm)
```

---

## 💻 Puesta en Marcha Rápida en la NUC

### 1. Requisitos
- **Windows 10 / 11** (64 bits).
- **Python 3.10+**.
- **MySQL Server 8.0+** corriendo en el puerto 3306 (`root` / `root`).
- Impresora **Brother QL-800** con rollo DK-1208 instalada en Windows.

### 2. Base de Datos en MySQL
Crea la base de datos si no existe:
```sql
CREATE DATABASE IF NOT EXISTS checkin_dacer_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 3. Configurar Entorno e Instalar Dependencias
```powershell
# 1. Situarse en la rama
git checkout feature/mysql-security-architecture

# 2. Crear y activar entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# 3. Instalar librerías
pip install -r requirements.txt
```

### 4. Ejecutar la Suite de Verificación Integral
```powershell
python test_full_system.py
```
*Debe reportar: `¡TODAS LAS PRUEBAS DE INTEGRACIÓN Y SEGURIDAD PASARON (10/10)!`*.

### 5. Iniciar la Aplicación
```powershell
python run.py
```

- **Kiosko de Autoservicio**: [http://localhost:5000/](http://localhost:5000/)
- **Panel Administrativo**: [http://localhost:5000/admin/](http://localhost:5000/admin/)

---

## 🔑 Credenciales Iniciales de Administrador

- **Usuario**: `Admin`
- **Contraseña Inicial**: `000000`
- **Nota de Seguridad**: Al iniciar sesión por primera vez, el sistema redirige de forma obligatoria a la pantalla de cambio de clave (`/auth/change-password`). No se permite el acceso al panel hasta registrar una contraseña segura.

---

## 📖 Documentación Detallada

Para una explicación exhaustiva de cada módulo, diagramas de secuencia detallados, esquemas de base de datos y flujos de datos paso a paso, consulta el documento:
👉 **[ARQUITECTURA_Y_FUNCIONAMIENTO.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/ARQUITECTURA_Y_FUNCIONAMIENTO.md)**
