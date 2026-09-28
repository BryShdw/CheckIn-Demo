# Especificación Funcional y de Interfaz: Panel de Administración CheckIn DACER

> **Documento de Diseño UI/UX y Arquitectura Frontend**  
> **Versión:** 2.0 (Arquitectura Segura MySQL + Enrolamiento Facial en Memoria)  
> **Objetivo:** Servir como guía integral, detallada y estructurada para diseñadores y herramientas de generación de interfaces (Figma, v0, Lovable, Tailwind UI, etc.).

---

## 1. Identidad Visual, Estilo y Tema

### 1.1 Filosofía de Diseño
El panel de administración está concebido con un estilo **Dark Theme Enterprise Moderno** (Inspirado en Dashboards SaaS de alto rendimiento como Vercel, Supabase o Stripe), optimizado para control de eventos masivos en tiempo real con alta legibilidad, respuesta táctil y feedback visual inmediato.

* **Tema Base:** Oscuro profundo (`#0d1117`, `#161b22`, `#1f2937`).
* **Acentos:**
  * **Primario (Acción / Marca):** Azul Eléctrico / Índigo (`#3b82f6` - `#6366f1`).
  * **Éxito (Asistencia / Verificado):** Verde Esmeralda (`#10b981`).
  * **Advertencia (Pendiente / Alerta):** Ámbar / Naranja (`#f59e0b`).
  * **Peligro (Error / Eliminación):** Rojo Coral (`#ef4444`).
* **Tipografía:** Sans-Serif moderna y legible (`Inter`, `system-ui`, `-apple-system`).
* **Bordes y Superficies:** Tarjetas elevadas con bordes sutiles (`border border-slate-700/60`), esquinas redondeadas (`rounded-xl` / 12px), sombras suaves y efecto vidrio (*glassmorphism* / `backdrop-blur-md`) en encabezados y modales.

---

## 2. Estructura General y Layout del Panel

El panel se compone de:
1. **Encabezado Superior Fijo (Top Navbar)**.
2. **Barra de Navegación por Pestañas (Tabs Navigation)**.
3. **Área de Contenido Principal (Vistas Dinámicas)**.
4. **Sistema Global de Notificaciones (Floating Toasts)**.

```
+---------------------------------------------------------------------------------------+
|  [Logo DACER]  [Badge En Línea]   [Selector Evento Activo v]   [Usuario: Admin] [Salir]  |
+---------------------------------------------------------------------------------------+
|  [Tab 1: Acreditación]  [Tab 2: Eventos]  [Tab 3: Métricas]  [Tab 4: Usuarios] [Tab 5: Logs] |
+---------------------------------------------------------------------------------------+
|                                                                                       |
|  [KPIs: Total | Registrados | Pendientes | % Asistencia]                              |
|                                                                                       |
|  [Configuraciones de Kiosko: Método de Entrada | Impresión de Gafetes]                |
|                                                                                       |
|  [Buscador rápido] [Filtro Estado] [Btn Subir Datos] [Btn +Nuevo] [Exportar] [Limpiar] |
|                                                                                       |
|  +---------------------------------------------------------------------------------+  |
|  | Tabla de Invitados (Avatar/Rostro, ID, Nombre, Empresa, Estado, Hora, Acciones) |  |
|  +---------------------------------------------------------------------------------+  |
+---------------------------------------------------------------------------------------+
```

---

## 3. Vistas y Módulos Detallados

### 3.1 Encabezado Superior (Header)
* **Logotipo y Marca:** Isotipo de DACER acompañado del texto "CheckIn DACER - Panel de Administración".
* **Badge de Estado del Sistema:** Pastilla redondeada en verde pulsante indicando `"Servidor Activo (MySQL Conectado)"`.
* **Selector Rápido de Evento Activo:** Menú desplegable (*select dropdown*) que lista los eventos disponibles y marca con un punto verde el evento actualmente en curso en los kioskos.
* **Perfil de Usuario:**
  * Nombre del usuario autenticado (ej. `Admin`).
  * Rol actual con badge (`SUPERADMIN`, `ADMIN` u `OPERATOR`).
  * Botón `"Cerrar Sesión"` (icono de salida, redirige a `/auth/logout`).

---

### 3.2 Pestaña 1: Acreditación e Invitados (Vista Principal)

#### A. Tarjetas de Métricas Rápidas (KPI Cards)
Cuatro tarjetas en rejilla responsiva (4 columnas en desktop, 2 en tablet, 1 en móvil):
1. **Total de Invitados:** Número total en base de datos para el evento activo (icono de lista/usuarios).
2. **Acreditados / Presentes:** Contador en verde esmeralda con número de check-ins confirmados.
3. **Pendientes de Ingreso:** Contador en ámbar con invitados faltantes.
4. **Porcentaje de Avance:** Barra de progreso interactiva (0% a 100%) con porcentaje en grande.

#### B. Tarjetas de Configuración del Kiosko
Dos paneles de control en tiempo real:
* **Tarjeta 1: Método de Acreditación en Kiosko:**
  * Selector desplegable:
    * `QR Only`: Kiosko solo solicita escanear código QR.
    * `Facial Only`: Kiosko activa inmediatamente reconocimiento biométrico.
    * `Híbrido (QR + Facial)`: Pantalla con ambos métodos habilitados simultáneamente.
  * *Nota de Diseño:* El umbral facial biométrico está predeterminado en `0.70` en el backend y no se expone al usuario para evitar descalibraciones accidentales.
* **Tarjeta 2: Modo de Impresión de Gafetes:**
  * Selector:
    * `Automático`: Imprime credencial en la impresora térmica Brother QL-800 al instante de validar.
    * `Confirmación`: Muestra botón en pantalla antes de enviar a impresión.
    * `Desactivado`: Acredita al invitado sin emitir gafete físico.
  * Selector de dispositivo de impresión detectado (ej. `Brother QL-800`).

#### C. Barra de Herramientas y Acciones (Action Toolbar)
* **Barra de Búsqueda Reactiva:** Campo de texto con icono de lupa que filtra en vivo por Nombre, Documento/ID, Empresa o Email.
* **Filtro de Estado:** Botones de alternancia o dropdown:
  * `Todos`
  * `Registrados` (Checked-in)
  * `Pendientes`
* **Botones Principales de Acción:**
  1. **"Cargar / Obtener Datos" (Botón Primario Destacado):** Abre el modal multi-origen (Excel, CSV, OneDrive/SharePoint).
  2. **"+ Nuevo Invitado":** Abre modal de registro manual individual.
  3. **"Exportar Excel (.xlsx)":** Descarga directa de la lista con estados y horas de ingreso.
  4. **"Reiniciar Asistencias":** Pone todos los check-ins en falso para iniciar una nueva jornada.
  5. **"Limpiar Invitados":** Botón de peligro que vacía la lista del evento tras confirmar contraseña o advertencia.

#### D. Tabla de Invitados (Data Table)
Estructura de columnas:
1. **Biometría / Avatar:**
   * Miniatura circular de la foto enrolada del invitado (si existe).
   * Si no tiene rostro registrado: Icono de silueta neutral con indicador ámbar `Sin Rostro`.
   * Si tiene rostro registrado: Miniatura con borde verde e indicador `Enrolado`.
2. **Código / ID:** Código único de invitación (ej. `INV-001`, `DNI`, etc.).
3. **Nombre y Apellidos:** Texto principal en negrita con tipografía clara.
4. **Empresa / Cargo:** Nombre de la organización y cargo debajo en texto secundario atenuado.
5. **Email / Contacto:** Correo electrónico del invitado.
6. **Estado de Asistencia:**
   * Badge interactivo o Switch:
     * Verde: `"Acreditado"` con marca de tiempo (ej. `10:42 AM`).
     * Gris/Ámbar: `"Pendiente"`.
   * *Acción rápida:* Al hacer clic en el switch/badge se alterna el estado de asistencia de inmediato sin recargar la página.
7. **Acciones por Fila:**
   * **Botón Cámara / Enrolar Rostro (Icono):** Abre el modal biométrico para tomar foto con webcam o subir imagen.
   * **Botón Imprimir (Icono Impresora):** Dispara la reimpresión manual de gafete individual.
   * **Botón Editar (Icono Lápiz):** Abre formulario con datos del invitado.
   * **Botón Eliminar (Icono Basura):** Elimina al invitado de MySQL previa confirmación.

* **Estados de la Tabla:**
  * **Cargando:** Filas simuladas (*skeleton loaders*) con animación de pulso.
  * **Sin Resultados de Búsqueda:** Mensaje `"No se encontraron invitados que coincidan con la búsqueda"`.
  * **Estado Vacío (Empty State):** Ilustración de lista vacía con texto `"No hay invitados registrados en este evento"` y botón directo `"Cargar Datos Ahora"`.

---

### 3.3 Pestaña 2: Gestión Multi-Evento
Permite administrar múltiples cumbres, conferencias o ferias de manera independiente.
* **Tarjeta de Creación de Evento:**
  * Formulario con:
    * Nombre del Evento (requerido).
    * Fecha y Hora de Inicio / Fin.
    * Mensaje de Bienvenida para el Kiosko de entrada (ej. *"Bienvenidos al Congreso Anual 2026"*).
    * Botón `"Crear Evento"`.
* **Grilla / Lista de Eventos Creados:**
  * Tarjetas individuales de evento mostrando:
    * Nombre y Slug.
    * Estado: Badge `"ACTIVO"` (borde verde) o `"INACTIVO"`.
    * Total de invitados registrados y asistentes en ese evento.
    * Botón `"Activar para Kiosko"` (cambia el evento activo en tiempo real).
    * Botón `"Editar Datos"`.
    * Botón `"Archivar / Eliminar"`.

---

### 3.4 Pestaña 3: Métricas y Analítica en Vivo
Monitoreo visual del flujo de asistentes durante el evento:
* **Gráfico 1: Curva de Afluencia Temporal (Timeline):** Gráfico de líneas o áreas mostrando picos de acreditaciones por cada intervalo de 15/30 minutos.
* **Gráfico 2: Desglose por Método de Ingreso:** Gráfico tipo dona (*doughnut chart*) comparando ingresos vía:
  * Código QR
  * Reconocimiento Facial Biométrico
  * Check-in Manual desde Panel
* **Gráfico 3: Ranking de Asistencia por Empresa:** Gráfico de barras horizontales con las empresas con mayor porcentaje de asistencia.
* **Botón de Actualización:** Refresco automático cada 10 segundos con switch para pausar.

---

### 3.5 Pestaña 4: Control de Usuarios y Seguridad (RBAC)
Módulo visible para usuarios con rol `SUPERADMIN`:
* **Tabla de Operadores y Administradores:**
  * Columnas: Usuario, Rol (`SUPERADMIN`, `ADMIN`, `OPERATOR`), Estado (Activo/Inactivo), Debe Cambiar Contraseña (`Sí` / `No`), Última Conexión, Acciones.
* **Acciones por Usuario:**
  * `"Restablecer Contraseña"` (asigna contraseña temporal y fuerza cambio al login).
  * `"Cambiar Rol"`.
  * `"Eliminar Acceso"`.
* **Botón "+ Crear Nuevo Usuario":** Abre modal para dar de alta nuevo operador de acreditación.

---

### 3.6 Pestaña 5: Registro de Auditoría (Audit Trail)
Registro forense e inmutable de todas las operaciones realizadas en el sistema para cumplimiento y seguridad:
* **Tabla de Logs de Auditoría:**
  * Columnas: Fecha/Hora exacta, Usuario responsable, Tipo de Acción (`CHECKIN_QR`, `CHECKIN_FACE`, `IMPORT_EXCEL`, `IMPORT_ONEDRIVE`, `MANUAL_CHECKIN`, `DELETE_GUEST`, `SYSTEM_RESET`), Dirección IP, Parámetros/Detalles del evento.
* **Filtros:** Por rango de fechas, por usuario o por tipo de acción.

---

## 4. Modales y Ventanas Flotantes (Dialogs / Overlays)

### 4.1 Modal A: "Cargar / Obtener Datos de Invitados"
Ventana modal centrada con pestañas internas para 3 métodos de carga (todos procesados 100% en memoria hacia MySQL sin archivos temporales en disco):

```
+-------------------------------------------------------------------------+
|  Cargar Datos de Invitados                                          [X] |
+-------------------------------------------------------------------------+
|  [Tab: Archivo Local (Excel/CSV)]  [Tab: OneDrive/SharePoint]  [Tab: Texto] |
+-------------------------------------------------------------------------+
|                                                                         |
|   (Contenido dinámico según pestaña seleccionada)                       |
|                                                                         |
+-------------------------------------------------------------------------+
|                                                   [Cancelar] [Procesar] |
+-------------------------------------------------------------------------+
```

* **Pestaña 1: Archivo Local (Excel / CSV):**
  * Zona Drag & Drop con borde discontinuo para arrastrar archivos `.xlsx`, `.xls` o `.csv`.
  * Botón `"Seleccionar archivo del equipo"`.
  * Reconocimiento automático de columnas (`Nombre`, `DNI/Código`, `Empresa`, `Email`, `Cargo`).
* **Pestaña 2: Sincronización OneDrive / SharePoint:**
  * Campo de texto para pegar el enlace compartido (`https://1drv.ms/...` o enlace corporativo de SharePoint).
  * Texto de ayuda indicando que el archivo debe contener una tabla con columnas de invitados.
  * Botón `"Sincronizar e Importar a MySQL"`.
  * Barra de progreso con estados: *"Conectando con Microsoft..."* -> *"Descargando en memoria..."* -> *"Guardando en base de datos MySQL..."*.
* **Pestaña 3: Pegado Rápido de Texto:**
  * Área de texto (*textarea*) para copiar y pegar directamente filas de Excel o texto delimitado por comas/tabulaciones.

---

### 4.2 Modal B: "Enrolamiento Biométrico Facial"
Ventana modal diseñada para asociar la biometría facial a un invitado específico:

```
+-------------------------------------------------------------------------+
|  Enrolamiento Facial: Dra. Elena Ramos (INV-001)                    [X] |
+-------------------------------------------------------------------------+
|  +------------------------------------+  +----------------------------+ |
|  | [ Stream de Cámara Web en Vivo ]   |  | Rostros Registrados (1/3)  | |
|  |                                    |  |                            | |
|  |        [ Guía Oval Facial ]        |  |  [Miniatura 1] [Eliminar]  | |
|  |                                    |  |                            | |
|  +------------------------------------+  +----------------------------+ |
|  [ Capturar Foto ] [ Subir Imagen ]       [ Estado: Enrolado en MySQL]  |
+-------------------------------------------------------------------------+
|                                                               [Cerrar]  |
+-------------------------------------------------------------------------+
```

* **Encabezado:** Nombre del invitado y código de identificación.
* **Zona de Captura por Cámara:**
  * Visor de video HTML5 en tiempo real.
  * Recuadro / óvalo guía translúcido superpuesto que indica al operador dónde posicionar el rostro.
  * Selector de cámara (si hay múltiples webcams conectadas).
  * Botón de acción destacado `"Capturar Foto"`: congela el fotograma, extrae el embedding biométrico (vector de 128 float) con el motor OpenCV SFace, genera la miniatura optimizada en base64 y la guarda directamente en la tabla `face_profiles` de MySQL.
* **Zona de Carga Alternativa:**
  * Botón `"Subir Foto desde Archivo"` para cargar fotos previas (.jpg/.png) tomadas con cámara réflex o celular.
* **Galería de Rostros Enrolados:**
  * Cuadrícula con las miniaturas de los rostros enrolados para ese invitado (permite hasta 3 ángulos por persona).
  * Cada miniatura incluye botón de papelera para eliminar ese perfil biométrico si fue tomado con baja iluminación o ángulo incorrecto.

---

### 4.3 Modal C: "Nuevo / Editar Invitado Manual"
Formulario flotante para altas individuales o corrección de datos:
* **Campos:**
  * `Código de Invitación / DNI`: Campo de texto con botón `"Auto-generar"`.
  * `Nombre y Apellidos`: Campo requerido.
  * `Empresa / Organización`: Campo de texto.
  * `Cargo / Puesto`: Campo de texto.
  * `Correo Electrónico`: Validación de formato email.
  * `Teléfono / Móvil`: Opcional.
* **Botones:** `"Guardar Invitado"` y `"Cancelar"`.

---

### 4.4 Modal D: "Cambio Obligatorio de Contraseña (First Login)"
Overlay modal de seguridad no cerrable que aparece automáticamente si un usuario tiene la marca `must_change_password=True`:
* **Mensaje Informativo:** *"Por motivos de seguridad y buenas prácticas, debe actualizar la contraseña temporal por defecto antes de continuar al panel."*
* **Campos:**
  * Contraseña actual.
  * Nueva contraseña segura.
  * Confirmación de contraseña.
  * Indicador de robustez de contraseña (mínimo 6-8 caracteres).
* **Botón:** `"Guardar y Acceder al Sistema"`.

---

### 4.5 Modal E: "Confirmación de Acciones Sensibles"
Diálogo modal de confirmación rápida antes de acciones irreversibles:
* **Casos:**
  * "Reiniciar todas las asistencias"
  * "Vaciar todos los invitados del evento"
  * "Eliminar usuario operador"
* **Componentes:** Icono de advertencia en rojo/naranja, descripción clara del impacto y dos botones: `"Cancelar"` y `"Confirmar y Proceder"`.

---

## 5. Sistema de Alertas y Notificaciones (Toasts)

El panel cuenta con un contenedor flotante en la esquina superior o inferior derecha (`z-index: 9999`) para feedback visual en tiempo real:

1. **Toast de Éxito (Verde):**
   * Mensaje: *"30 invitados sincronizados correctamente desde OneDrive"*.
   * Mensaje: *"Rostro enrolado con éxito para Dra. Elena Ramos"*.
   * Mensaje: *"Asistencia registrada manualmente"*.
2. **Toast de Advertencia (Ámbar):**
   * Mensaje: *"No se detectó ningún rostro claro en la imagen capturada. Intente de nuevo"*.
   * Mensaje: *"El invitado ya se encontraba acreditado"*.
3. **Toast de Error (Rojo):**
   * Mensaje: *"Error al conectar con la base de datos MySQL"*.
   * Mensaje: *"Enlace de OneDrive no válido o sin permisos públicos de lectura"*.
4. **Toast Informativo (Azul):**
   * Mensaje: *"Impresión de gafete enviada a Brother QL-800"*.

---

## 6. Especificación Técnica de Endpoints REST del Panel

Para integrar este diseño con el backend Flask existente, las vistas y modales interactúan con las siguientes rutas de API:

| Módulo / Función | Método HTTP | Ruta Endpoint | Formato de Carga / Respuesta |
| :--- | :--- | :--- | :--- |
| **Listar Invitados** | `GET` | `/api/guests` | Retorna lista de invitados con flag `enrolled` y `checked_in`. |
| **Alternar Asistencia** | `POST` | `/api/guest/<id>/status` | JSON: `{"checked_in": true/false}`. |
| **Crear Invitado Manual** | `POST` | `/api/guest` | JSON: `{"id", "name", "company", "position", "email"}`. |
| **Actualizar Invitado** | `PUT` | `/api/guest/<id>` | JSON: Datos actualizados del invitado. |
| **Eliminar Invitado** | `DELETE` | `/api/guest/<id>` | Elimina de MySQL e invalida perfiles biométricos. |
| **Subir Archivo Local** | `POST` | `/api/guests/upload` | `multipart/form-data` con archivo Excel o CSV (leído en memoria). |
| **Sincronizar OneDrive** | `POST` | `/admin/api/import/onedrive` | JSON: `{"url": "https://1drv.ms/..."}` (descarga en RAM hacia MySQL). |
| **Listar Rostros de Invitado**| `GET` | `/api/guest/<id>/faces` | Retorna perfiles biométricos y miniaturas asociadas. |
| **Enrolar Rostro (Foto/Webcam)**| `POST` | `/api/guest/<id>/face` | JSON con `{"image_base64": "data:image/jpeg;base64,..."}` o multipart. |
| **Eliminar Rostro Enrolado** | `DELETE` | `/api/guest/<id>/face/<face_id>`| Elimina el embedding y la miniatura de MySQL. |
| **Ajustes de Kiosko** | `GET` / `POST`| `/api/kiosk-settings` | Configura método de acreditación e impresión de gafete. |
| **Métricas en Vivo** | `GET` | `/admin/api/analytics` | Retorna totales, porcentajes, desglose por método y empresa. |
| **Listar Eventos** | `GET` | `/admin/api/events` | Retorna eventos creados y estado activo. |
| **Activar Evento** | `POST` | `/admin/api/events/<id>/activate` | Establece el evento como principal para kioskos. |
| **Exportar a Excel** | `GET` | `/admin/api/export/excel` | Descarga archivo binario `.xlsx` generado en memoria. |
| **Gestión de Usuarios** | `GET` / `POST`| `/admin/api/users` | Listado y alta de usuarios operadores/admins. |
| **Auditoría Forense** | `GET` | `/admin/api/audit-logs` | Logs del sistema con paginación e IP. |

---

## 7. Requerimientos Clave para Herramientas de Prototipado y Rediseño

Si este documento se suministra a herramientas de diseño asistido por IA (como v0.dev, Cursor Composer, Lovable o diseñadores en Figma):
1. **Conservar siempre los IDs de campos y llamadas API** para permitir el reemplazo directo de plantillas HTML/JS.
2. **Priorizar la visualización de la webcam y el feedback biométrico:** El modal de enrolamiento debe verse limpio, con recuadro centrado para el rostro del participante.
3. **Cero persistencia en disco:** No diseñar interfaces para explorar carpetas locales o "ver archivos guardados en el servidor"; toda la información reside en base de datos.
4. **Diseño Mobile-Friendly / Tablet-Friendly:** El personal en recepción del evento frecuentemente opera el panel desde iPads o tablets táctiles; asegurar botones de al menos 44x44px y paddings generosos.
