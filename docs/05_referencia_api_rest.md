# Referencia de API REST (Rama Main)

Este documento especifica los endpoints HTTP proporcionados por el servidor `app.py`.

---

## 1. Endpoints de Consulta y Gestion de Invitados

### `GET /api/guests`
Retorna el listado completo de invitados cargados en memoria con su estado de acreditacion.

- **Respuesta (200 OK)**:
```json
[
  {
    "id": "INV-001",
    "name": "CARLOS PEREZ GOMEZ",
    "company": "CORPORACION TECNOLOGICA",
    "position": "GERENTE DE OPERACIONES",
    "checked_in": true,
    "checked_in_at": "30/09/2026 14:15:00",
    "method": "FACIAL",
    "faces_count": 2
  }
]
```

### `GET /api/guest/<id>`
Obtiene los datos detallados de un invitado por su identificador unico.

### `POST /api/guest`
Agrega un nuevo participante individual a la lista en memoria y al archivo CSV.
- **Cuerpo (JSON)**:
```json
{
  "id": "INV-100",
  "name": "MARIA ELENA SOTO",
  "company": "BANCO REGIONAL",
  "position": "ESPECIALISTA EN CIBERSEGURIDAD"
}
```

### `DELETE /api/guest/<id>`
Elimina al invitado de la coleccion activa y remueve su registro de asistencia en `checkins.json`.

---

## 2. Endpoints de Acreditacion e Impresion

### `POST /api/checkin/<id>`
Registra manualmente la asistencia de un participante sin emitir impresion fisica.

### `POST /api/guest/<id>/status`
Alterna el estado del asistente entre `Registrado` y `Pendiente`.

### `POST /api/print/<id>`
Envia la credencial del participante al spooler de la impresora Brother QL-800 y valida la asistencia.
- **Parametros Query**: `force=true` (Permite reimpresion forzada si ya contaba con registro previo).

### `POST /api/reset`
Restablece todos los check-ins locales vaciando el archivo `checkins.json`.

---

## 3. Endpoints Biometricos y Reconocimiento Facial

### `POST /api/facial-match`
Recibe un fotograma en base64 de la camara web y realiza el cotejo biometrico.
- **Cuerpo (JSON)**:
```json
{
  "image_base64": "data:image/jpeg;base64,...",
  "auto_checkin": true,
  "threshold": 0.55
}
```
- **Estados de Respuesta**:
  - `status: "ok"`: Asistente reconocido y etiqueta emitida en la Brother QL-800.
  - `status: "already_registered"`: Reconocido, pero ya cuenta con asistencia previa.
  - `status: "no_match"`: Rostro detectado pero no coincide con ningun perfil registrado.
  - `status: "no_face"`: No se detecta ningun rostro en el fotograma.

### `POST /api/guest/<id>/face`
Enrola una nueva fotografia para el invitado.
- **Entrada**: Archivo multipart con clave `image` o cuerpo JSON con `image_base64`.

### `GET /api/guest/<id>/faces`
Devuelve el listado de recortes y metadatos de las fotos enroladas para el invitado.

### `DELETE /api/guest/<id>/face`
Elimina los datos faciales asociados al invitado.

### `POST /api/faces/delete-all`
Purga la totalidad de fotos y embeddings del sistema.

---

## 4. Endpoints de Hardware y Diagnostico

### `GET /api/status`
Retorna el estado global del sistema, fuente de datos activa y estadisticas de asistencia.

### `GET /api/printer/status`
Consulta el estado de conexion fisica (WMI USB) y la cola de impresion de la Brother QL-800.

### `POST /api/printer/purge-jobs`
Limpia y purga de forma forzada la cola de trabajos atascados en el spooler de Windows.

### `POST /api/printer/test`
Envia una etiqueta de prueba a la impresora Brother.

---

## 5. Endpoints de Gestion de Documentos OneDrive

### `POST /api/documents/add`
Agrega un nuevo enlace de OneDrive o SharePoint, descarga su contenido y lo establece como activo.

### `POST /api/documents/sync`
Fuerza la descarga y actualizacion del documento activo de OneDrive.

### `POST /api/documents/select`
Conmuta la lista activa hacia otro documento previamente descargado en `onedrive_caches/`.
