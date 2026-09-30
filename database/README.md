# Base de Datos MySQL - Sistema de Acreditacion y Check-In DACER

Este directorio contiene los scripts y definiciones de estructura relacional para MySQL 8.0+ del sistema de acreditacion.

---

## Archivos

- `schema.sql`: Script DDL completo con la creacion de la base de datos `checkin_dacer_db`, tablas con claves foraneas en cascada (`ON DELETE CASCADE`), indices optimizados para busqueda en vivo y datos semilla iniciales (usuario `Admin` por defecto, Evento Demo y configuracion del Kiosko).

---

## Instrucciones de Despliegue / Restauracion

### Opcion 1: Desde la consola de comandos de Windows (PowerShell / CMD)
```powershell
mysql -u root -p < database/schema.sql
```

### Opcion 2: Desde MySQL Workbench o DBeaver
1. Abrir una conexion a su servidor MySQL (puerto 3306).
2. Abrir el archivo `database/schema.sql`.
3. Ejecutar el script completo (`Ctrl + Shift + Enter`).

---

## Modelo de Datos y Tablas

| Tabla | Proposito | Regla de Integridad |
|---|---|---|
| `events` | Eventos activos y archivados. | Slug unico, control de evento activo. |
| `users` | Administradores, supervisores y operadores. | Credencial inicial `Admin / 000000`, flag forzoso `must_change_password`. |
| `guests` | Asistentes e invitados importados por evento. | Clave foranea `event_id` con eliminacion en cascada. Codigo unico por evento. |
| `face_profiles` | Embeddings normalizados SFace (128D) y miniaturas base64. | Cero archivos en disco (100% en MySQL y cache en memoria RAM). Eliminacion en cascada. |
| `checkins` | Asistencias registradas fisicamente. | Integridad estricta: solo se registra si la impresora emite el ticket fisico. |
| `audit_logs` | Trazabilidad y auditoria de seguridad. | Registro inmutable de acciones, usuario, IP y fecha. |
| `kiosk_settings` | Configuracion operativa del kiosko por evento. | Metodo de escaneo (`both`, `facial`, `qr`), modo (`auto`, `manual`) y umbral. |

---

## Credenciales Iniciales de Administrador

- Usuario: `Admin`
- Contrasena temporal: `000000`
- Comportamiento: Al iniciar sesion por primera vez, el sistema obliga al cambio inmediato de contrasena antes de habilitar el acceso al panel `/admin/`.
