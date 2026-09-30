# Sistema de Acreditacion Inteligente CheckIn (Rama Main)

Sistema integral de acreditacion y control de acceso para eventos corporativos y masivos con escaneo dual de codigo QR y reconocimiento facial en pantalla de autoservicio (kiosko), e impresion directa de etiquetas en la impresora termica Brother QL-800 con rollo DK-1208 (38 mm x 90.3 mm).

El sistema esta disenado para ejecutarse en computadoras con Windows 10 u 11 (Laptop, Mini PC, Intel NUC o Totem) conectadas a la impresora Brother oficial por puerto USB.

---

## 1. Caracteristicas Principales

1. **Acreditacion Dual (Facial y QR)**:
   - **Reconocimiento Facial en CPU**: Utiliza modelos optimizados de OpenCV DNN (YuNet para deteccion y SFace para extraccion de embeddings de 128 dimensiones). No requiere GPU ni herramientas pesadas de compilacion C++.
   - **Enrolamiento Multi-Foto (1 a 4 fotos por invitado)**: Desde el panel de administracion se pueden capturar fotos directamente con la camara web o subir archivos de imagen para lograr una identificacion facial de alta precision bajo diversos angulos.
   - **Modo Dual o Conmutable**: El kiosko permite acreditacion combinada (QR y facial simultaneos), o aislar solo Facial o solo QR.

2. **Gestion Exclusiva desde OneDrive / SharePoint**:
   - Los datos de los invitados pueden importarse directamente desde archivos CSV compartidos en la nube (Microsoft OneDrive o SharePoint).
   - **Multi-documento y Cache Local**: Se pueden registrar multiples enlaces de OneDrive desde el panel de administracion. Cada enlace se descarga, valida y almacena en cache en la carpeta `onedrive_caches/`, permitiendo que el sistema funcione fluidamente incluso si se interrumpe la conexion a internet.
   - **Selector de Documentos**: Conmutacion instantanea entre distintas listas o eventos desde un desplegable en el panel de administracion.

3. **Flujo de Check-in Vinculado a la Impresion**:
   - Cuando el invitado es reconocido por rostro o escanea su QR en el kiosko (o se ingresa su identificador manualmente), el sistema envia la orden a la impresora Brother QL-800.
   - **El estado cambia a "Registrado" unicamente cuando la etiqueta se imprime exitosamente**. Si ocurre un atasco o desconexion de hardware, el check-in se mantiene pendiente y el sistema alerta del problema.

4. **Diseno de Etiqueta Optimizado para DK-1208 (38mm x 90.3mm)**:
   - Los unicos elementos impresos son Nombre y Apellidos, Empresa y Puesto, disenados para adherirse sobre solaperos o emblemas pre-impresos.
   - Nombre completo centrado en tipografia grande y negrita de alto impacto (con division equilibrada inteligente en dos lineas si es extenso).
   - Auto-escalado de fuente dinamico (`fit_font`) para evitar truncamientos en textos largos.
   - Renderizado nativo a 300 DPI mediante el spooler de impresion GDI de Windows (`win32print`).

5. **Kiosko de Autoservicio (`/` o `/kiosk`)**:
   - Escaneo dual por camara web en tiempo real con deteccion rapida via `jsQR` e inferencia facial no bloqueante.
   - Soporte para lectores de pistola USB de codigo de barras.
   - Modos Automatico (reconocimiento e impresion inmediata) y Manual (requiere confirmacion en pantalla).
   - Proteccion contra escaneo duplicado con advertencia visual de registro previo.

6. **Panel de Administracion (`/admin`)**:
   - Indicador en vivo de estado de la impresora Brother QL-800.
   - Gestor interactivo de documentos OneDrive y cache local.
   - Gestor de enrolamiento facial con camara web.
   - Estadisticas de asistencia en tiempo real (Total, Registrados, Pendientes).
   - Busqueda y filtrado instantaneo por nombre, ID, empresa o cargo.
   - Reimpresion forzada y alternancia de estado manual.

---

## 2. Arquitectura del Sistema

```
                    [ Microsoft OneDrive / SharePoint ]
                    CSV con estructura: ID, Nombres y Apellidos, Empresa, Cargo
                                       |
                                       v (Descarga / Sincronizacion)
+-------------------------------------------------------------------------------+
|                       COMPUTADOR ANFITRION (WINDOWS 10 / 11)                   |
|                                                                               |
|   onedrive_caches/                     settings.json         checkins.json    |
|   +-- doc_1.csv   (Lista activa)    (Metadatos enlaces)   (Estado asistencia) |
|   +-- doc_2.csv   (Otras listas)                                              |
|                                                                               |
|   face_data/                                                                  |
|   +-- embeddings.json (Vectores 128D)                                         |
|   +-- images/         (Miniaturas faciales)                                   |
|                                                                               |
|   Backend Flask Monolitico (app.py)                                           |
|   +-- face_service.py (Vision artificial YuNet + SFace en CPU)                |
|   +-- config.py       (Configuracion de hardware y eventos)                   |
|                                                                               |
|        +--------------------------------+-------------------------------+     |
|        |                                                                |     |
|        v                                                                v     |
|  Kiosko de Autoservicio / Totem                          Panel Administrativo |
|  (index.html - Pantalla completa)                        (admin.html)         |
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

## 3. Modo de Uso y Replicacion en Otras Computadoras

Para configurar el sistema en una computadora nueva:

### Paso 1: Requisitos de Software y Hardware
- Computadora con Windows 10 u 11 de 64 bits.
- Python 3.10 o 3.11 instalado con la opcion **"Add python.exe to PATH" activada**.
- Impresora Brother QL-800 instalada con su controlador oficial y rollo DK-1208 configurado como predeterminado (38mm x 90mm).
- Camara web funcional conectada al equipo.

### Paso 2: Preparar el Entorno
Abra una consola de PowerShell en la carpeta del proyecto:
```powershell
# 1. Crear entorno virtual
python -m venv venv

# 2. Activar entorno virtual
.\venv\Scripts\Activate.ps1

# 3. Instalar dependencias
pip install --upgrade pip
pip install -r requirements.txt
```

### Paso 3: Iniciar el Sistema
Puede iniciarlo con el archivo por lotes:
```cmd
.\iniciar_sistema.bat
```
O directamente desde la consola:
```powershell
python app.py
```

### Paso 4: Despliegue en Modo Kiosko / Totem
Para ejecutar la interfaz a pantalla completa sin elementos del navegador:
```cmd
chrome.exe --kiosk --kiosk-printing "http://localhost:5000/"
```

### Enlaces de Acceso Local:
- **Pantalla de Kiosko**: `http://localhost:5000/`
- **Panel Administrativo**: `http://localhost:5000/admin`

---

## 4. Estructura Requerida del Archivo CSV

Los archivos de lista de asistentes (locales o en OneDrive/SharePoint) deben tener los siguientes encabezados en la primera fila:

```csv
ID,Nombres y Apellidos,Empresa,Cargo
INV-001,Maria Gonzalez Perez,Grupo Innovacion S.A.,Directora de Proyectos
INV-002,Carlos Ramirez Lopez,Tecnologias del Norte,Gerente Comercial
INV-003,Ana Sofia Herrera Vega,Consultora AHV,CEO
INV-004,Roberto Mendoza Castro,Industrias Mendoza,Director de Operaciones
```

---

## 5. Indice de Documentacion Tecnica (`docs/`)

Para consultar documentacion a detalle, revise la carpeta `docs/`:

- [docs/01_arquitectura_del_sistema.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/01_arquitectura_del_sistema.md): Arquitectura de software, concurrencia y persistencia.
- [docs/02_biometria_y_procesamiento_facial.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/02_biometria_y_procesamiento_facial.md): Modelos YuNet y SFace, embeddings y similitud coseno.
- [docs/03_impresion_y_hardware_brother.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/03_impresion_y_hardware_brother.md): Hardware Brother QL-800, GDI a 300 DPI y regla de impresion obligatoria.
- [docs/04_guia_despliegue_y_replicacion.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/04_guia_despliegue_y_replicacion.md): Guia de instalacion y puesta en marcha en computadoras nuevas.
- [docs/05_referencia_api_rest.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/05_referencia_api_rest.md): Referencia completa de rutas y metodos HTTP.
- [docs/06_manual_de_usuario_y_operaciones.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/docs/06_manual_de_usuario_y_operaciones.md): Manual de usuario para recepcionistas y operadores.
- [status.md](file:///c:/Users/braya/PROYECTS/Checkin-Demo/status.md): Estado actual del proyecto y checklist de caracteristicas.
