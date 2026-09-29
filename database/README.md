# Base de Datos MySQL — Sistema de Acreditación y Check-In DACER

Este directorio contiene los scripts y definiciones de estructura relacional para **MySQL 8.0+** del sistema de acreditación.

---

## 📁 Archivos

- **`schema.sql`**: Script DDL completo con la creación de la base de datos `checkin_dacer_db`, tablas con claves foráneas en cascada (`ON DELETE CASCADE`), índices optimizados para búsqueda en vivo y datos semilla iniciales (usuario `Admin` por defecto, Evento Demo y configuración del Kiosko).

---

## 🚀 Instrucciones de Despliegue / Restauración

### Opción 1: Desde la consola de comandos de Windows (PowerShell / CMD)
```powershell
mysql -u root -p < database/schema.sql
```

### Opción 2: Desde MySQL Workbench o DBeaver
1. Abrir una conexión a su servidor MySQL (puerto 3306).
2. Abrir el archivo `database/schema.sql`.
3. Ejecutar el script completo (`Ctrl + Shift + Enter`).

---

## 🗄️ Modelo de Datos y Tablas

| Tabla | Propósito | Regla de Integridad |
|---|---|---|
| **`events`** | Eventos activos y archivados. | Slug único, control de evento activo. |
| **`users`** | Administradores, supervisores y operadores. | Credencial inicial `Admin / 000000`, flag forzoso `must_change_password`. |
| **`guests`** | Asistentes e invitados importados por evento. | Clave foránea `event_id` con eliminación en cascada. Código único por evento. |
| **`face_profiles`** | Embeddings normalizados SFace (128D) y miniaturas base64. | Cero archivos en disco (100% en MySQL y caché en memoria RAM). Eliminación en cascada. |
| **`checkins`** | Asistencias registradas físicamente. | **Integridad estricta**: solo se registra si la impresora emite el ticket físico. |
| **`audit_logs`** | Trazabilidad y auditoría de seguridad. | Registro inmutable de acciones, usuario, IP y fecha. |
| **`kiosk_settings`** | Configuración operativa del kiosko por evento. | Método de escaneo (`both`, `facial`, `qr`), modo (`auto`, `manual`) y umbral. |

---

## 👤 Credenciales Iniciales de Administrador

- **Usuario**: `Admin`
- **Contraseña temporal**: `000000`
- **Comportamiento**: Al iniciar sesión por primera vez, el sistema obliga al cambio inmediato de contraseña antes de habilitar el acceso al panel `/admin/`.
