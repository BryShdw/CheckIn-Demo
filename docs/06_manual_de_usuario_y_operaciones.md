# Manual de Usuario y Operaciones (Rama Main)

Este manual describe el modo de uso del sistema CheckIn en recepcion, mesas de atencion y terminales de autoservicio.

---

## 1. Operacion en la Mesa de Recepcion

### 1.1 Busqueda Manual y Acreditacion
1. Abra el panel administrativo en el navegador: `http://localhost:5000/admin`.
2. Escriba el nombre, documento de identidad o empresa del asistente en el buscador superior.
3. Al localizar al participante en la tabla:
   - Presione el boton **Imprimir** para enviar la credencial a la Brother QL-800.
   - El estado cambiara automaticamente a **Registrado** con la marca de tiempo de ingreso.

### 1.2 Registro de Asistentes Imprevistos
1. En la parte superior de la tabla, presione **Nuevo Invitado**.
2. Complete los campos requeridos: ID/DNI, Nombres y Apellidos, Empresa y Cargo.
3. Presione **Guardar e Imprimir** para emitir su credencial al instante.

### 1.3 Reimpresion por Perdida de Credencial
1. Localice al asistente en el panel de administracion.
2. Haga clic en el boton **Reimprimir**.
3. El sistema emitira una nueva etiqueta sin alterar la hora del primer ingreso.

---

## 2. Operacion en el Kiosko de Autoservicio

1. Inicie el navegador en el computador del totem en la URL `http://localhost:5000/`.
2. El asistente puede acreditarse mediante dos modalidades:
   - **Reconocimiento Facial**: Mirar directamente hacia la camara web a una distancia de 60 a 80 cm. Al confirmar la coincidencia, el sistema mostrara un mensaje de bienvenida y emitira la credencial termica de forma inmediata.
   - **Codigo QR**: Presentar el codigo QR frente a la camara web o utilizar un lector de pistola USB conectado.
3. **Control de Duplicidad**: Si el asistente ya registro su asistencia previamente, el sistema mostrara una alerta en color amarillo y no emitira etiquetas duplicadas.

---

## 3. Gestion de Listas desde OneDrive / SharePoint

1. En OneDrive o SharePoint, obtenga el enlace compartido de su archivo CSV con permisos de lectura.
2. En el panel administrativo (`/admin`), haga clic en **Agregar Enlace OneDrive**.
3. Ingrese una etiqueta descriptiva y pegue la URL.
4. Presione **Descargar y Activar**.
5. Los asistentes estaran disponibles de inmediato para el proceso de acreditacion.

---

## 4. Solucion de Problemas Operativos

### 4.1 La impresora Brother no responde
- Compruebe que la luz de encendido este en verde fijo.
- Verifique que la cubierta este bien cerrada y el rollo DK-1208 tenga papel suficiente.
- En el panel administrativo, presione **Purgar Cola** para eliminar trabajos de impresion bloqueados.

### 4.2 La camara no detecta a los asistentes
- Asegurese de que la persona se encuentre dentro del cuadro visual de la camara.
- Evite ubicar el totem frente a fuentes de luz muy intensas que provoquen sombras pronunciadas en el rostro.
