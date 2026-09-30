# Guia de Despliegue y Replicacion en Nuevas Computadoras

Esta guia paso a paso esta disenada para permitir a cualquier tecnico, desarrollador o personal operativo instalar, configurar y poner en marcha el sistema CheckIn en cualquier computadora con sistema operativo Windows (Laptop, Mini PC, NUC o Totem) desde cero.

---

## 1. Requisitos Previos del Sistema

### 1.1 Hardware Recomendado
- **Procesador**: Intel Core i3 / AMD Ryzen 3 de 8va generacion o superior (recomendado i5 para procesamiento facial fluido a 30 FPS).
- **Memoria RAM**: Minimo 8 GB (Recomendado 16 GB).
- **Almacenamiento**: Minimo 5 GB de espacio libre en disco SSD.
- **Camara Web**: Camara USB 1080p o integrada de calidad minima HD 720p.
- **Impresora**: Brother QL-800 (o compatible de la serie QL) conectada por cable USB.
- **Consumible**: Rollo Brother DK-1208 (38mm x 90mm).

### 1.2 Software Base Necesario
1. **Sistema Operativo**: Windows 10 (64 bits) o Windows 11 (64 bits).
2. **Python**: Version 3.10.x o 3.11.x (Descargar desde python.org; **marcar obligatoriamente la casilla "Add python.exe to PATH"** durante la instalacion).
3. **Servidor de Base de Datos**: MySQL Server 8.0+ (MySQL Installer) o MariaDB 10.5+ / XAMPP.
4. **Navegador Web**: Google Chrome o Microsoft Edge actualizado.
5. **Controlador Brother QL-800**: Controlador oficial de Brother para Windows.

---

## 2. Instalacion del Controlador de la Impresora Brother

1. Conecte el cable de alimentacion y el cable USB de la impresora Brother QL-800 a la computadora. Encienda la impresora (el boton de encendido debe quedar en color verde fijo).
2. Descargue el instalador del controlador oficial desde el centro de descargas de Brother:
   - Nombre del paquete: *Instalador completo de controladores y software para QL-800*.
3. Ejecute el instalador siguiendo los pasos en pantalla seleccionando conexion USB.
4. Una vez instalada, abra `Panel de control -> Dispositivos e impresoras`.
5. Localice **Brother QL-800**, haga clic derecho y seleccione **Propiedades de la impresora**.
6. En la pestana **Opciones avanzadas -> Valores predeterminados de impresion**:
   - **Tamano de papel**: Seleccione `38mm x 90mm` o `DK-1208`.
   - **Opciones de corte**: Seleccione `Corte automatico al finalizar cada etiqueta`.
   - Haga clic en **Aplicar** y **Aceptar**.

---

## 3. Preparacion de la Base de Datos MySQL

1. Inicie sesion en su gestor de MySQL (MySQL Workbench, HeidiSQL, DBeaver o linea de comandos):
   ```sql
   CREATE DATABASE checkin_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
2. Ejecute el script de estructura inicial ubicado en la carpeta `database/schema.sql` del proyecto:
   ```bash
   mysql -u root -p checkin_db < database/schema.sql
   ```
3. El script creara las tablas fundamentales:
   - `events`: Informacion del evento y plantilla JSON de credenciales.
   - `guests`: Registro de invitados y asistentes.
   - `face_profiles`: Embeddings biometricos de 128 dimensiones.
   - `checkins`: Historial transaccional de ingresos validados.
   - `users`: Usuarios administrativos con contraseñas cifradas en Argon2id.
   - `audit_logs`: Trazabilidad inmutable de operaciones.
   - `kiosk_settings`: Parametros operativos de la pantalla de bienvenida.
4. Se generara el usuario inicial por defecto:
   - **Usuario**: `admin`
   - **Contrasena temporal**: `Admin2026!` (El sistema solicitara cambiarla en el primer inicio de sesion).

---

## 4. Instalacion y Configuracion del Proyecto

### 4.1 Clonar o Copiar el Directorio del Proyecto
Copie la carpeta del proyecto a una ruta estable (por ejemplo: `C:\Checkin-Demo`).

### 4.2 Crear el Entorno Virtual de Python
Abra una consola de PowerShell en la carpeta del proyecto:
```powershell
# Verificar version de Python
python --version

# Crear entorno virtual aislado
python -m venv venv

# Activar entorno virtual
.\venv\Scripts\Activate.ps1
```
*(Nota: Si PowerShell restringe la ejecucion de scripts, ejecute previamente: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*.

### 4.3 Instalar Dependencias
Con el entorno virtual activado (`(venv)` en el indicador de la consola):
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.4 Configurar Variables de Entorno (`.env`)
Copie el archivo de ejemplo o cree un archivo `.env` en la raiz del proyecto:
```ini
# Configuracion de Entorno
FLASK_ENV=production
FLASK_DEBUG=0
SECRET_KEY=clave_secreta_segura_debe_tener_minimo_32_caracteres_aleatorios

# Cadena de Conexion a Base de Datos MySQL
# Formato: mysql+pymysql://<usuario>:<password>@<host>:<puerto>/<nombre_bd>
DATABASE_URL=mysql+pymysql://root:password123@localhost:3306/checkin_db

# Configuracion de Hardware de Impresion
PRINTER_ENABLED=true
PRINTER_NAME=Brother QL-800

# Parametros Biometricos y Algoritmos Faciales
DEFAULT_FACE_THRESHOLD=0.70
FACE_TOP2_MARGIN=0.08
FACE_MAX_PROFILES_PER_GUEST=5

# Rutas de Modelos de Vision por Computador
YUNET_MODEL_PATH=models/face_detection_yunet.onnx
SFACE_MODEL_PATH=models/face_recognition_sface.onnx
```

### 4.5 Verificar Presencia de Modelos ONNX
Asegurese de que los dos archivos de red neuronal esten presentes en la carpeta `models/`:
- `models/face_detection_yunet.onnx` (Detector de rostros YuNet)
- `models/face_recognition_sface.onnx` (Extractor de embeddings SFace)

---

## 5. Puesta en Marcha del Sistema

### 5.1 Modo de Inicio Rapido
Puede iniciar el sistema ejecutando el script proporcionado:
```powershell
.\iniciar_sistema.bat
```
O directamente desde la consola activada:
```powershell
python app.py
```
El servidor quedara escuchando en el puerto `5000` accesible localmente en `http://127.0.0.1:5000` y a traves de la red local en `http://<IP_LOCAL>:5000`.

### 5.2 Despliegue en Modo Kiosko / Totem (Pantalla Completa)
Para configurar la pantalla del totem de recepcion sin barras del navegador ni opciones de salida accesibles al asistente:

1. Cree un acceso directo en el escritorio de Windows con el siguiente destino:
   ```cmd
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk --kiosk-printing --disable-pinch --overscroll-history-navigation=0 "http://localhost:5000/kiosk"
   ```
   *(O utilizando Microsoft Edge)*:
   ```cmd
   "msedge.exe" --kiosk --kiosk-printing --edge-kiosk-type=fullscreen "http://localhost:5000/kiosk"
   ```
2. Al ejecutar este acceso directo, el sistema abrira la interfaz tactil en pantalla completa con reconocimiento facial continuo y camara activa.

---

## 6. Configuracion en Red Local (Totems Distribuidos)

Si se utiliza una arquitectura donde un computador principal (Servidor/Laptop) aloja la base de datos MySQL y la aplicacion, mientras que terminales adicionales (NUC o Totems) operan como clientes:

1. **Apertura de Puerto en Firewall de Windows (En el Servidor Principal)**:
   Abra PowerShell como Administrador en la laptop servidora y ejecute:
   ```powershell
   New-NetFirewallRule -DisplayName "CheckIn Server Port 5000" -Direction Inbound -LocalPort 5000 -Protocol TCP -Action Allow
   ```
2. **Acceso desde las NUC / Totems Clientes**:
   Abra el navegador en la NUC cliente apuntando a la IP de la laptop principal:
   `http://192.168.112.36:5000/kiosk`
3. **Impresion en Esquema Distribuido**:
   - Cada estacion que deba imprimir credenciales fisicas requiere tener conectada localmente su propia impresora Brother QL-800 por cable USB.
   - Si una estacion opera exclusivamente como kiosko de lectura, el procesamiento y la emision se gestionan de forma centralizada o local segun el punto de entrega seleccionado.

---

## 7. Lista de Comprobacion y Pruebas Iniciales (Checklist)

Una vez completada la instalacion, valide los siguientes puntos para certificar la operacion:

- [ ] **Acceso Web Administrativo**: Ingrese a `http://localhost:5000/admin`. Verifique el formulario de autenticacion.
- [ ] **Cambio de Contrasena Inicial**: Inicie con `admin` / `Admin2026!` y complete la actualizacion de la clave.
- [ ] **Diagnostico de Impresora**: En el panel administrativo, observe el indicador "Estado de Impresora". Debe indicar "En linea y lista" (Verde).
- [ ] **Prueba de Impresion**: Dirijase a la pestana "Disenador de Credenciales" y presione "Imprimir Prueba". La Brother QL-800 debe imprimir y cortar la etiqueta de muestra inmediatamente.
- [ ] **Carga de Lista de Invitados**: Cargue una lista de prueba mediante archivo Excel (.xlsx) o enlace de OneDrive. Verifique que los nombres se listen en el tablero.
- [ ] **Prueba de Camara en Kiosko**: Abra la ruta `/kiosk`. La camara web debe inicializarse y el circulo de deteccion facial debe responder a los rostros presentes.
