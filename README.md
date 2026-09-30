# Sistema de Acreditacion Inteligente CheckIn

Plataforma empresarial de acreditacion y control de acceso para eventos corporativos y masivos. El sistema integra reconocimiento facial mediante vision por computador en CPU (YuNet + SFace), lectura optica de credenciales QR, persistencia transaccional en MySQL 8, gestion multi-evento, sincronizacion con Microsoft OneDrive / SharePoint e impresion termica de alta velocidad en hardware Brother QL-800 con rollo DK-1208 (38 mm x 90.3 mm).

---

## 1. Caracteristicas Principales

1. **Persistencia Relacional en MySQL 8**:
   - Transacciones ACID seguras con soporte integral de caracteres UTF-8 (`utf8mb4`).
   - Esquema modular compuesto por tablas de eventos, asistentes, perfiles biometricos, asistencias validadas, usuarios y registros inmutables de auditoria.

2. **Seguridad y Control de Acceso por Roles (RBAC)**:
   - Tres niveles jerarquicos: SUPERADMIN, ADMIN y OPERATOR.
   - Hashing criptografico seguro de credenciales con Argon2id.
   - Forzado de actualizacion de contrasena en el primer inicio de sesion.
   - Proteccion CSRF en formularios web y control estricto de sesiones HTTP.

3. **Biometria Facial en Tiempo Real (CPU)**:
   - Pipeline de vision artificial basado en OpenCV DNN con modelos ONNX oficiales: YuNet (deteccion de rostro) y SFace (extraccion de vectores de 128 dimensiones).
   - Umbral de similitud coseno calibrado en 0.70 para eliminar falsos positivos.
   - Cache de embeddings en memoria RAM para cotejos inmediatos sin latencia de disco.

4. **Impresion Termica Directa (Brother QL-800)**:
   - Integracion nativa con el subsistema GDI de Windows (`win32print`) a 300 DPI.
   - Disenador de credenciales visual y personalizable por evento con ajuste automatico de fuentes (`fit_font`) y particion de nombres extensos.
   - Regla estricta de negocio: la asistencia solo se valida en la base de datos si la impresion fisica de la credencial concluye satisfactoriamente.

5. **Importacion y Sincronizacion Flexible**:
   - Carga de archivos locales en formatos Excel (.xlsx) y CSV con autodeteccion inteligente de columnas.
   - Sincronizacion directa con hojas de calculo compartidas en Microsoft OneDrive / SharePoint sin requerir descargas manuales intermedias.

---

## 2. Arquitectura General del Sistema

```
                    [ Microsoft OneDrive / SharePoint ]
                    (Enlaces compartidos .xlsx / .csv)
                                     |
                                     v (Sincronizacion directa)
+-------------------------------------------------------------------------------+
|                       COMPUTADOR ANFITRION (WINDOWS 10 / 11)                   |
|                                                                               |
|  MySQL 8.0+ (checkin_db)                                                      |
|  +-- users (Roles RBAC, contraseñas Argon2id, banderas de seguridad)          |
|  +-- events (Eventos activos, metadatos, plantillas JSON de credenciales)     |
|  +-- guests (Lista de asistentes vinculados al evento)                        |
|  +-- checkins (Transacciones de ingreso, metodo, timestamp, IP)               |
|  +-- face_profiles (Embeddings biometricos de 128D)                           |
|  +-- kiosk_settings (Modo operativo, umbrales y metodos)                      |
|  +-- audit_logs (Trazabilidad inmutable de operaciones del sistema)           |
|                                                                               |
|  Backend Flask Modular (Application Factory)                                  |
|  +-- Blueprints: Kiosk, Admin, Auth, API                                      |
|  +-- Servicios: face_service, printer_service, guest_service, import_service  |
|                                                                               |
|        +--------------------------------+-------------------------------+     |
|        |                                                                |     |
|        v                                                                v     |
|  Kiosko de Autoservicio / Totem                          Panel Administrativo |
|  (/kiosk - Pantalla completa)                            (/admin - Gestion)   |
+-------------------------------------------------------------------------------+
                                 |
                                 v
                     Subsistema Spooler Windows GDI
                              (win32print)
                                 |
                                 v
                      Impresora Brother QL-800
                    Rollo DK-1208 (38mm x 90.3mm)
```

---

## 3. Guia de Replicacion y Puesta en Marcha en Nuevas Computadoras

Para instalar y ejecutar el sistema en una nueva computadora (Laptop, Mini PC, Intel NUC o Totem):

### Paso 1: Requisitos de Software
- Windows 10 o Windows 11 de 64 bits.
- Python 3.10 o superior (marcar la opcion "Add python.exe to PATH" durante la instalacion).
- MySQL Server 8.0 o superior (puerto predeterminado 3306).
- Controlador oficial de la impresora Brother QL-800 instalado en Windows.

### Paso 2: Clonar el Repositorio y Configurar Entorno
Abra PowerShell en la carpeta donde instalara el proyecto:
```powershell
# Crear y activar el entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# Actualizar pip e instalar dependencias requeridas
pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 3: Inicializar la Base de Datos MySQL
En su cliente de MySQL, ejecute el script de definicion de datos:
```sql
CREATE DATABASE checkin_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```
Importe el esquema inicial ejecutando desde la raiz del proyecto:
```bash
mysql -u root -p checkin_db < database/schema.sql
```

### Paso 4: Configurar Variables de Entorno (`.env`)
Cree o modifique el archivo `.env` en la raiz del proyecto:
```ini
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=clave_secreta_de_al_menos_32_caracteres_aleatorios_y_seguros

# Cadena de conexion a MySQL
DATABASE_URL=mysql+pymysql://root:password123@localhost:3306/checkin_db

# Configuracion de Impresora
PRINTER_ENABLED=true
PRINTER_NAME=Brother QL-800

# Parametros Biometricos
DEFAULT_FACE_THRESHOLD=0.70
FACE_TOP2_MARGIN=0.08
YUNET_MODEL_PATH=models/face_detection_yunet.onnx
SFACE_MODEL_PATH=models/face_recognition_sface.onnx
```

### Paso 5: Validar la Instalacion con la Suite de Pruebas
Ejecute las 10 pruebas integrales automatizadas:
```powershell
python test_full_system.py
```
Verifique que el resultado sea: `10 passed`.

### Paso 6: Iniciar el Sistema
Para arrancar el servidor en modo produccion/desarrollo local:
```powershell
python app.py
```
O ejecutando el archivo por lotes:
```powershell
.\iniciar_sistema.bat
```

### Paso 7: Acceso a las Interfaces
- **Panel Administrativo**: `http://localhost:5000/admin`
  - Usuario por defecto: `admin`
  - Contrasena temporal: `Admin2026!` (Se solicitara cambio inmediato al primer ingreso).
- **Kiosko de Autoservicio / Totem**: `http://localhost:5000/kiosk`
  - Para desplegarlo en modo kiosko pantalla completa en Chrome:
    ```cmd
    chrome.exe --kiosk --kiosk-printing "http://localhost:5000/kiosk"
    ```

---

## 4. Estructura de Documentacion Detallada (`docs/`)

Para profundizar en la arquitectura y detalles tecnicos especificos, consulte los manuales ubicados en el directorio `docs/`:

- [docs/01_arquitectura_del_sistema.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/01_arquitectura_del_sistema.md): Diseno de software, Application Factory, modelos relacionales y politicas de seguridad.
- [docs/02_biometria_y_procesamiento_facial.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/02_biometria_y_procesamiento_facial.md): Modelos YuNet y SFace, extraccion de caracteristicas y calibracion de umbrales.
- [docs/03_impresion_y_hardware_brother.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/03_impresion_y_hardware_brother.md): Hardware Brother QL-800, spooler GDI, diseno de credenciales y resolucion de fallos.
- [docs/04_guia_despliegue_y_replicacion.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/04_guia_despliegue_y_replicacion.md): Manual paso a paso para desplegar en computadoras nuevas desde cero.
- [docs/05_referencia_api_rest.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/05_referencia_api_rest.md): Catalogo completo de endpoints HTTP, parametros JSON y codigos de estado.
- [docs/06_manual_de_usuario_y_operaciones.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/06_manual_de_usuario_y_operaciones.md): Guia de usuario para operadores, coordinadores y personal de recepcion.
- [status.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/status.md): Estado actual del proyecto, checklist de modulos y certificacion de pruebas.

---

## 5. Limpieza y Mantenimiento

Para mantener el entorno limpio, el proyecto no almacena copias redundantes ni archivos temporales en los directorios de control de versiones. Todas las descargas de sincronizacion y transformaciones graficas se realizan en memoria dinamica (RAM).
