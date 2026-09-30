# Guia de Despliegue y Replicacion en Nuevas Computadoras

Esta guia paso a paso detalla el procedimiento para replicar e instalar el sistema CheckIn en cualquier computadora o terminal con Windows 10 u 11 (Laptop, Mini PC, Intel NUC o Totem).

---

## 1. Requisitos Previos

- **Sistema Operativo**: Windows 10 o Windows 11 de 64 bits.
- **Python**: Version 3.10 o 3.11 de 64 bits (Descargar desde python.org; **marcar obligatoriamente la casilla "Add python.exe to PATH"** durante el asistente de instalacion).
- **Controlador de Impresora**: Paquete oficial de controladores de la impresora Brother QL-800 para Windows.
- **Hardware de Impresion**: Impresora termica Brother QL-800 conectada por cable USB con rollo DK-1208 (38mm x 90mm).
- **Camara Web**: Camara USB o integrada HD (720p o 1080p).

---

## 2. Instalacion del Controlador de la Impresora

1. Conecte el cable de alimentacion y el cable USB de la impresora Brother al computador. Encienda la unidad.
2. Ejecute el instalador oficial de controladores de Brother para Windows.
3. Al finalizar, abra el menu de configuracion de Windows en `Dispositivos e impresoras`.
4. Haga clic derecho en **Brother QL-800** y seleccione **Propiedades de la impresora**.
5. En la pestana **Opciones avanzadas -> Valores predeterminados de impresion**:
   - Establezca el tamano de papel en `38mm x 90mm` o `DK-1208`.
   - Active la opcion `Corte automatico al finalizar cada etiqueta`.
   - Guarde los cambios.

---

## 3. Instalacion del Software CheckIn

### 3.1 Copiar o Descargar el Proyecto
Copie los archivos del sistema a una carpeta de facil acceso (por ejemplo: `C:\Checkin-Demo`).

### 3.2 Crear y Activar el Entorno Virtual
Abra una ventana de PowerShell en la carpeta del proyecto:
```powershell
# Crear entorno virtual aislado
python -m venv venv

# Activar entorno virtual
.\venv\Scripts\Activate.ps1
```
*(Si PowerShell muestra una advertencia sobre politicas de ejecucion, ejecute previamente: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`)*.

### 3.3 Instalar Dependencias de Python
Con el entorno virtual activado:
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

### 3.4 Verificar Archivos de Modelos Faciales
Compruebe que la carpeta `models/` contenga los dos archivos de red neuronal requeridos:
- `models/face_detection_yunet.onnx`
- `models/face_recognition_sface.onnx`

Si no se encuentran presentes, el sistema intentara descargarlos automaticamente en el primer inicio si cuenta con conexion a internet.

---

## 4. Ejecucion y Puesta en Marcha

### 4.1 Inicio Rapido mediante Archivo por Lotes
Haga doble clic en el archivo:
```cmd
iniciar_sistema.bat
```
El script activara el entorno virtual de forma automatica y levantara el servidor web en el puerto `5000`.

### 4.2 Inicio Manual desde Consola
```powershell
python app.py
```

---

## 5. Acceso a las Interfaces y Despliegue en Modo Kiosko

### 5.1 Enlaces Locales
- **Panel Administrativo**: `http://localhost:5000/admin`
- **Pantalla de Kiosko / Autoservicio**: `http://localhost:5000/` o `http://localhost:5000/kiosk`

### 5.2 Despliegue en Modo Kiosko a Pantalla Completa (Totem)
Para bloquear la interfaz del navegador y ofrecer una experiencia interactiva sin distracciones:

Cree un acceso directo en el escritorio de Windows con el siguiente comando:
```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" --kiosk --kiosk-printing --disable-pinch --overscroll-history-navigation=0 "http://localhost:5000/"
```
*(O con Microsoft Edge)*:
```cmd
"msedge.exe" --kiosk --kiosk-printing --edge-kiosk-type=fullscreen "http://localhost:5000/"
```

---

## 6. Lista de Verificacion Final

- [ ] La impresora Brother muestra luz verde fija y esta conectada por cable USB.
- [ ] Al ingresar a `http://localhost:5000/admin`, el indicador muestra "Brother QL-800: En linea y lista".
- [ ] En la seccion de administracion de OneDrive, cargue un enlace compartido o verifique que exista un archivo de datos local.
- [ ] Al abrir la interfaz del kiosko, la camara web se activa y el circulo de deteccion responde al rostro del asistente.
