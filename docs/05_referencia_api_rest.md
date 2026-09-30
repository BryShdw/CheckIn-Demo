# Referencia de API REST

Este documento contiene la especificacion completa de las rutas y servicios web expuestos por el sistema CheckIn, categorizados por blueprint funcional.

---

## 1. Convenciones Generales

- **Formato de Intercambio**: Peticiones y respuestas en `application/json` (salvo rutas especificas de carga de archivos multipart o descarga de binarios/imagenes).
- **Codificacion**: UTF-8.
- **Autenticacion**:
  - Rutas bajo `/admin/api/*` requieren sesion activa autenticada mediante cookie segura (`Flask-Login`).
  - Rutas bajo `/api/*` estan disenadas para consumo de terminales de autoservicio y totems (exentas de CSRF para permitir consumo interactivo continuo mediante `fetch`).

---

## 2. Blueprint de API Publica y Kiosko (`/api`)

### 2.1 Estado del Sistema y Configuracion del Kiosko

#### `GET /api/status`
Retorna el estado general del evento activo, la impresora Brother y las metricas globales.

- **Respuesta (200 OK)**:
```json
{
  "status": "ok",
  "event_id": 1,
  "event_name": "Congreso de Tecnologia 2026",
  "guest_count": 250,
  "data_source": "mysql",
  "printer": {
    "enabled": true,
    "installed": true,
    "online": true,
    "is_ready": true,
    "name": "Brother QL-800",
    "status_text": "Lista y en linea",
    "details": "Puerto: USB001. Trabajos en cola: 0.",
    "jobs_in_queue": 0
  },
  "kiosk_settings": {
    "method": "both",
    "mode": "auto",
    "face_threshold": 0.70
  },
  "stats": {
    "total": 250,
    "checked_in": 115,
    "pending": 135,
    "percentage": 46.0
  }
}
```

#### `GET /api/kiosk-settings`
Consulta los parametros del Kiosko asociados al evento activo.

#### `POST /api/kiosk-settings`
Actualiza parametros en tiempo de ejecucion.
- **Cuerpo (JSON)**:
```json
{
  "method": "facial",
  "mode": "auto",
  "face_threshold": 0.72
}
```
- **Valores validos**:
  - `method`: `"facial"`, `"qr"`, `"both"`.
  - `mode`: `"auto"` (imprime de inmediato al detectar), `"manual"` (requiere confirmacion en pantalla).
  - `face_threshold`: Flotante entre `0.50` y `0.95`.

---

### 2.2 Gestion y Consulta de Invitados

#### `GET /api/guests`
Retorna el listado completo de asistentes del evento activo.

#### `GET /api/guest/<guest_id>`
Busca un invitado por DNI, codigo o ID numerico.

#### `POST /api/guest/<guest_id>/status`
Alterna manualmente la condicion de un invitado (Registrado <-> Pendiente) desde la interfaz.
- **Respuesta (200 OK)**:
```json
{
  "status": "ok",
  "message": "Estado de CARLOS PEREZ actualizado a Registrado.",
  "checked_in": true,
  "guest": { ... }
}
```

#### `DELETE /api/guest/<guest_id>`
Desactiva logicamente al invitado de la base de datos (`is_active = False`).

---

### 2.3 Procesamiento de Acreditacion y Check-In

#### `POST /api/checkin`
Procesa la acreditacion manual o mediante lectura de codigo QR.
- **Cuerpo (JSON)**:
```json
{
  "guest_id": "ASIS-1002",
  "method": "QR",
  "force_reprint": false
}
```
- **Respuestas**:
  - `200 OK`: Acreditacion exitosa y credencial emitida.
  - `409 Conflict`: El asistente ya cuenta con acreditacion previa registrada.
  - `400 Bad Request`: Identificador inexistente o solicitud malformada.
  - `500 Internal Server Error`: Fallo de hardware de impresion (imposibilidad de acreditar).

#### `POST /api/print/<guest_id>`
Ruta directa de impresion y confirmacion desde el terminal de autoservicio.
- **Parametros Query / Body**:
  - `force=true`: Permite reimpresion forzada si ya contaba con check-in.
  - `method`: `"KIOSK"`, `"FACIAL"`, `"QR"`, `"MANUAL"`.

---

### 2.4 Biometria y Reconocimiento Facial

#### `POST /api/facial-match`
Endpoint principal de cotejo biometrico en tiempo real.
- **Cuerpo (JSON o Multipart)**:
  - `image_base64`: Fotograma capturado en formato Data URI base64 (`data:image/jpeg;base64,...`).
  - `auto_checkin`: Booleano (opcional; si se omite, toma la configuracion del evento).
  - `threshold`: Umbral de similitud coseno (opcional; por defecto `0.70`).
- **Estados de Respuesta**:
  - `status: "ok"`: Rostro reconocido y credencial emitida exitosamente.
  - `status: "identified"`: Rostro identificado en modo manual (esperando confirmacion del operador).
  - `status: "already_registered"`: Rostro reconocido pero ya tiene ingreso validado.
  - `status: "no_match"`: Rostro detectado con nitidez pero no coincide con la base de datos.
  - `status: "no_face"`: No se detecto ninguna estructura facial en el fotograma.
  - `status: "print_failed"`: Identificado correctamente pero la impresora Brother fallo.

#### `POST /api/guest/<guest_id>/face`
Enrola una nueva imagen facial para un asistente.
- **Entrada**: Multipart con campo `image` o JSON con `image_base64`.
- **Proceso**: Detecta rostro con YuNet, extrae vector SFace de 128 flotantes y persiste el perfil en `face_profiles`.

#### `GET /api/guest/<guest_id>/faces`
Obtiene las miniaturas y metadatos de las fotos enroladas para el asistente.

#### `DELETE /api/guest/<guest_id>/face`
Elimina las fotos enroladas del asistente.

#### `POST /api/faces/delete-all`
Purga la totalidad de vectores faciales de todos los participantes.

---

### 2.5 Hardware y Diagnostico de Impresion

#### `GET /api/printer/status`
Consulta en tiempo real el estado USB (WMI PnP) y el spooler de la impresora Brother QL-800.

#### `POST /api/printer/purge-jobs`
Elimina inmediatamente todos los trabajos atascados en la cola de impresion de Windows.

#### `POST /api/printer/test`
Envia una etiqueta de prueba estandar al cabezal termico.

#### `GET /api/label-preview/<guest_id>`
Genera y retorna un stream binario en formato PNG con la apariencia visual exacta de la etiqueta que se emitiria para dicho invitado.

---

## 3. Blueprint de Administracion (`/admin/api`)

Todas estas rutas requieren sesion de usuario autenticado con permisos `ADMIN` o `SUPERADMIN`.

### 3.1 Eventos

- `GET /admin/api/events`: Retorna la lista de eventos creados.
- `POST /admin/api/events`: Crea un nuevo evento en el sistema.
- `POST /admin/api/events/<id>/activate`: Establece el evento indicado como el evento activo para acreditacion.
- `DELETE /admin/api/events/<id>`: Elimina un evento y sus registros asociados (solo SuperAdmin).

### 3.2 Usuarios y Seguridad RBAC

- `GET /admin/api/users`: Lista de operadores y administradores.
- `POST /admin/api/users`: Registra un nuevo usuario (`SUPERADMIN`, `ADMIN`, `OPERATOR`).
- `DELETE /admin/api/users/<id>`: Elimina una cuenta de usuario.

### 3.3 Auditoria y Analitica

- `GET /admin/api/audit-logs`: Obtiene los ultimos 150 registros inmutables de auditoria con usuario, IP, accion y fecha.
- `GET /admin/api/analytics`: Resumen estadistico y distribucion horaria de ingresos en intervalos de una hora para graficos interactivos.

### 3.4 Importacion y Exportacion

- `POST /admin/api/import/file`: Carga un archivo Excel (`.xlsx`) o delimitado (`.csv`) para insercion y actualizacion automatica de asistentes.
- `POST /admin/api/import/onedrive`: Sincroniza la lista de asistentes directamente desde una hoja compartida de Microsoft OneDrive / SharePoint.
- `GET /admin/export-attendance`: Descarga dinamica de un archivo `.xlsx` con el reporte consolidado de asistencia, marcas de tiempo y metodo de registro.

### 3.5 Disenador de Plantillas de Credencial

- `GET /admin/api/label-template`: Obtiene el esquema JSON de distribucion de campos del evento activo.
- `POST /admin/api/label-template`: Guarda modificaciones en los campos (tamanos de fuente, negrita, visibilidad, posicion de QR).
- `POST /admin/api/label-preview`: Renderiza en tiempo real el PNG resultante de la configuracion enviada en el cuerpo de la peticion.
- `POST /admin/api/label-template/test-print`: Emite una impresion fisica en la Brother QL-800 con la configuracion de prueba.
