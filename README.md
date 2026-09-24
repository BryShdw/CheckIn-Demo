# 🎟️ Guest Check-in & Brother Label Printing System (QR + Facial)

Sistema integral de acreditación y control de acceso para eventos con **escaneo dual de código QR y reconocimiento facial en pantalla de autoservicio (kiosko)**, e impresión directa de etiquetas en la impresora **Brother QL-800** con rollo **DK-1208 (38 mm × 90.3 mm)**.

Diseñado para ejecutarse en una **Intel NUC con Windows 10 / 11** conectada a la impresora Brother oficial por puerto USB.

---

## 🚀 Características Principales

1. **Acreditación Dual (Facial y QR)**:
   - **Reconocimiento Facial en CPU**: Utiliza modelos optimizados de OpenCV DNN (**YuNet** para detección + **SFace** para embeddings de 128 dimensiones). No requiere GPU ni herramientas pesadas de C++.
   - **Enrolamiento Multi-Foto (1 a 4 fotos por invitado)**: Desde el panel de administración se pueden tomar fotos directamente con la cámara web o subir archivos de imagen (ej. frontal, sonrisa, leves giros) para lograr una identificación facial de alta precisión.
   - **Modo Dual o Conmutable**: El kiosko permite acreditación combinada (QR + Facial simultáneos), o aislar solo Facial o solo QR.

2. **Gestión Exclusiva desde OneDrive / SharePoint**:
   - Los datos de los invitados provienen directamente de archivos CSV alojados en la nube (Microsoft OneDrive / SharePoint).
   - **Multi-documento y Caché Local**: Puedes agregar múltiples enlaces de OneDrive desde el panel de administración. Cada enlace se descarga, valida y almacena en caché en la carpeta `onedrive_caches/`, permitiendo que el sistema funcione fluidamente incluso si se interrumpe la conexión a internet.
   - **Selector de Documentos**: Cambia entre distintas listas o eventos desde un desplegable en el panel de administración con un solo clic.

3. **Flujo de Check-in Vinculado a la Impresión**:
   - Cuando el invitado es reconocido por rostro o escanea su QR en el kiosko (o se ingresa su ID manualmente), el sistema envía la orden a la impresora Brother QL-800.
   - **El estado cambia a "Registrado" únicamente cuando la etiqueta se imprime exitosamente**. Si ocurre un atasco o corte de hardware, el check-in se mantiene pendiente y el sistema avisa del error.

4. **Diseño de Etiqueta Optimizado para DK-1208 (38mm × 90.3mm)**:
   - **Exclusivo para Emblemas Pre-impresos**: Dado que el sticker se adhiere sobre un emblema que ya posee el logotipo e identidad gráfica del evento, **los únicos elementos impresos son Nombre y apellidos, Empresa y Puesto**.
   - **Máxima Claridad y Legibilidad Tipográfica**:
     - Nombre completo centrado en tipografía grande y negrita de alto impacto (con división equilibrada inteligente en 2 líneas si es extenso).
     - Empresa en tamaño destacado.
     - Puesto / Cargo en tamaño proporcional y legible.
     - Auto-escalado de fuente dinámico (`fit_font`) para evitar truncamientos en textos largos.
     - Sin elementos distractores: sin QR, sin franja superior, sin pie de página, sin ID y sin líneas.
   - **Renderizado nativo a 300 DPI (991 × 413 px en horizontal)** mediante el spooler de impresión GDI de Windows (`win32print`).

5. **Kiosko de Autoservicio (`/`)**:
   - Escaneo dual por cámara web en tiempo real con detección rápida vía `jsQR` e inferencia facial no bloqueante.
   - Soporte para escáneres de pistola de código de barras USB (ingreso de texto en campo rápido).
   - Carga manual de imágenes con código QR.
   - Modos **Automático** (reconocimiento e impresión inmediata) y **Manual** (requiere pulsar "Imprimir Ficha").
   - Protección contra escaneo duplicado y cooldown de 4 segundos tras reconocimiento exitoso.

6. **Panel de Administración (`/admin`)**:
   - Indicador en vivo de estado de la impresora Brother QL-800.
   - Gestor interactivo de documentos OneDrive (Agregar nuevo enlace, seleccionar activo, sincronizar y eliminar de caché).
   - **Gestor de Enrolamiento Facial**: Modal para capturar fotos con webcam o subir imágenes por invitado (hasta 4 fotos por persona con visualización de recortes alineados y eliminación selectiva).
   - Estadísticas de asistencia en tiempo real (Total, Registrados, Pendientes).
   - Búsqueda y filtrado instantáneo por nombre, ID, empresa o cargo.
   - Acciones por invitado: Reimpresión forzada, alternar estado manual (Registrado/Pendiente) y eliminación.
   - Reseteo general de check-ins para pruebas o inicio de jornada.

---

## 🏗️ Arquitectura del Sistema

```
                    [ Microsoft OneDrive / SharePoint ]
                    CSV con estructura: ID, Nombres y Apellidos, Empresa, Cargo
                                      │
                                      ▼ (Descarga / Sincronización)
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             NUC (Windows 10 / 11)                                │
│                                                                                  │
│   onedrive_caches/                     settings.json         checkins.json       │
│   ├── doc_1.csv   (Lista activa)    (Metadatos de enlaces) (Estado asistencia)   │
│   └── doc_2.csv   (Otras listas)                                                 │
│                                                                                  │
│                                 Backend Flask                                    │
│                                   (app.py)                                       │
│                                       │                                          │
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

## 📋 Estructura Requerida del CSV de OneDrive

Todo archivo CSV compartido desde OneDrive o SharePoint debe contener los siguientes encabezados en su primera fila:

```csv
ID,Nombres y Apellidos,Empresa,Cargo
INV-001,María González Pérez,Grupo Innovación S.A.,Directora de Proyectos
INV-002,Carlos Ramírez López,Tecnologías del Norte,Gerente Comercial
INV-003,Ana Sofía Herrera Vega,Consultora AHV,CEO
INV-004,Roberto Mendoza Castro,Industrias Mendoza,Director de Operaciones
```

> **Compatibilidad**: El sistema soporta codificaciones `UTF-8 con BOM`, `UTF-8 estándar`, `Windows CP-1252` y `ISO-8859-1 (Latin-1)`, garantizando que tildes, letras ñ y caracteres especiales se muestren e impriman correctamente.

---

## ☁️ Cómo Obtener y Usar Enlaces de OneDrive / SharePoint

1. En OneDrive o SharePoint (Office 365), ubica tu archivo CSV.
2. Haz clic derecho y selecciona **Compartir** (*Share*).
3. Asegúrate de que el enlace tenga permisos de visualización pública o para cualquier miembro de la organización con el vínculo:
   - *"Cualquier persona que tenga el vínculo puede ver"* (o vínculo directo de lectura).
4. Copia el enlace generado. Ejemplo:
   ```
   https://tuempresa-my.sharepoint.com/:x:/g/personal/.../tu_enlace_compartido?e=xyz123
   ```
5. En el Panel de Administración (`/admin`), haz clic en **➕ Agregar Enlace OneDrive**.
6. Escribe un nombre descriptivo (ej. *Invitados Gala Noche*) y pega la URL.
7. Haz clic en **Descargar y Activar**. El sistema descargará el archivo, validará las 4 columnas requeridas, creará una copia en `onedrive_caches/` y lo establecerá como la lista activa para el kiosko.

---

## 🖨️ Configuración de la Impresora Brother QL-800

1. **Instalación del Controlador**:
   - Asegúrate de tener instalado el controlador oficial de la impresora Brother QL-800 en Windows.
   - En *Configuración de Windows > Dispositivos > Impresoras y escáneres*, la impresora debe aparecer con el nombre `Brother QL-800` (o similar).
2. **Rollo de Etiquetas**:
   - Coloca el rollo pre-cortado **DK-1208** (38 mm × 90.3 mm / 400 etiquetas por rollo).
3. **Impresión Directa**:
   - El sistema utiliza `pywin32` (`win32print`, `win32ui`) para dibujar directamente en el contexto del dispositivo de la impresora, respetando la orientación horizontal de la cinta sin requerir cuadros de diálogo del navegador.

---

## 💻 Inicio y Ejecución en la NUC

### Opción A: Acceso Directo por Lote (Recomendado)
Haz doble clic sobre el archivo:
```bat
iniciar_sistema.bat
```
Este script activa automáticamente el entorno virtual (`venv`) e inicia el servidor Flask en `http://0.0.0.0:5000`.

### Opción B: Desde PowerShell / Terminal
```powershell
# 1. Navegar al directorio
cd C:\Users\Administrator\Desktop\guest-checkin

# 2. Activar entorno virtual
.\venv\Scripts\activate

# 3. Iniciar aplicación
python app.py
```

### URLs de Acceso:
- **Pantalla Kiosko**: [http://localhost:5000](http://localhost:5000)
- **Panel de Administración**: [http://localhost:5000/admin](http://localhost:5000/admin)

---

## 📂 Estructura del Proyecto

```
guest-checkin/
├── app.py                  # Backend Flask, rutas API, gestor de documentos y renderizado GDI
├── config.py               # Configuración base (Nombre de evento, rollo, etc.)
├── settings.json           # Registro persistente de documentos OneDrive y documento activo
├── checkins.json           # Registro local persistente de asistencia por invitado
├── iniciar_sistema.bat     # Lanzador de un clic para Windows
├── requirements.txt        # Dependencias de Python (Flask, Pillow, pywin32, requests, etc.)
├── onedrive_caches/        # Almacenamiento local en caché de los CSVs de OneDrive
│   └── doc_1.csv           # Copia local del documento activo
├── templates/
│   ├── index.html          # Interfaz de autoservicio (kiosko, cámara, escaneo QR)
│   └── admin.html          # Panel de administración (documentos OneDrive, impresiones, lista)
└── static/                 # Estilos, scripts y assets estáticos
```

---

## 🔒 Restricciones y Notas Técnicas

- **Persistencia de Asistencia**: Los check-ins (`checkins.json`) son independientes de las descargas de OneDrive. Si se sincroniza un CSV actualizado, los invitados que ya hayan ingresado conservan su marca de asistencia y hora de ingreso.
- **Sin impresiones de prueba accidentales**: Las pruebas de conexión de la impresora se realizan verificando el estado del spooler de Windows sin disparar trabajos de impresión en blanco ni consumir etiquetas físicas.
