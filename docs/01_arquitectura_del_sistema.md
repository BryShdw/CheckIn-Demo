# Arquitectura del Sistema CheckIn (Rama Main)

Este documento describe la arquitectura de software, el flujo de datos, los componentes de procesamiento y las politicas de ejecucion correspondientes a la rama principal (`main`).

---

## 1. Vision General de la Arquitectura

La rama `main` esta concebida como un sistema independiente, autonomo y de alta resiliencia para el control de acceso y acreditacion en eventos corporativos y masivos. Su diseno prioriza la operacion sin dependencias externas complejas, permitiendo ejecucion completamente fuera de linea (offline) mediante almacenamiento local en archivos JSON y soporte de sincronizacion en caliente con Microsoft OneDrive / SharePoint.

```
                    [ Microsoft OneDrive / SharePoint ]
                    CSV con estructura: ID, Nombres, Empresa, Cargo
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
|   +-- images/         (Miniaturas recortes faciales)                          |
|                                                                               |
|   Backend Flask Monolitico (app.py)                                           |
|   +-- face_service.py (Vision artificial YuNet + SFace en CPU)                |
|   +-- config.py       (Parametros de entorno, tamano de rollo, eventos)       |
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

## 2. Modulos Principales

### 2.1 Servidor de Aplicacion (`app.py`)
- Desarrollado sobre Flask, gestiona el enrutamiento HTTP, la concurrencia mediante cerrojos de subprocesos (`threading.Lock`) y el ciclo de vida de los datos en memoria.
- Mantiene la coleccion de invitados en una lista en memoria RAM (`GUESTS`), lo que permite busquedas instantaneas en tiempo constante o lineal sin accesos a disco por cada peticion.

### 2.2 Motor Biometrico Facial (`face_service.py`)
- Implementa deteccion facial con la red neuronal convolucional profunda YuNet y extraccion de vectores de 128 dimensiones con la red SFace.
- Ambos modelos se ejecutan en formato ONNX nativo de OpenCV DNN utilizando exclusivamente la CPU.
- Permite almacenar de 1 a 4 fotografias por asistente en `face_data/embeddings.json` para garantizar reconocimiento bajo diferentes angulos o condiciones de iluminacion.

### 2.3 Subsistema de Impresion GDI Directa
- Integrado mediante la libreria `pywin32` (`win32print`, `win32ui`).
- Construye las etiquetas en memoria como mapas de bits independientes del dispositivo (DIB) a 300 DPI y las transmite directamente al spooler del controlador de Windows sin abrir dialogos interactivos de impresion.

### 2.4 Persistencia y Resiliencia Local
- **`checkins.json`**: Registro transaccional de asistencias confirmadas. Si se actualiza o recarga la lista de invitados desde OneDrive, los registros de asistencia ya realizados se conservan intactos.
- **`settings.json`**: Almacena las URLs de documentos de OneDrive configurados y cual de ellos es el documento activo.
- **`onedrive_caches/`**: Directorio donde se guardan copias locales de los archivos CSV descargados desde OneDrive, garantizando que el sistema continue operando si la conexion a internet se interrumpe durante el evento.

---

## 3. Interfaces de Usuario

### 3.1 Kiosko de Autoservicio (`/` o `/kiosk`)
- Disenado para pantallas tactiles de totems y terminales de atencion directa.
- Deteccion continua de codigos QR mediante la libreria JavaScript `jsQR`.
- Inferencia facial en tiempo real enviando fotogramas periodicos hacia `/api/facial-match`.
- Proteccion integrada contra duplicados: si una persona acreditada vuelve a escanearse, el sistema emite una notificacion de asistencia previa y no vuelve a imprimir la credencial.

### 3.2 Panel de Administracion (`/admin`)
- Indicador en vivo del estado de conectividad y cola de impresion de la Brother QL-800.
- Gestion dinamica de listas de asistentes: agregar enlaces de OneDrive, conmutar lista activa y sincronizacion forzada.
- Busqueda y filtrado instantaneo por nombre, documento, empresa o cargo.
- Gestion de enrolamiento biometrico: captura directa de fotos con la camara web y carga manual de fotografias.
- Reimpresion de credenciales y reinicio general de asistencias para pruebas.
