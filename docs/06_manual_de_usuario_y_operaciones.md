# Manual de Usuario y Operaciones del Sistema

Este manual proporciona instrucciones operativas detalladas para coordinadores de eventos, recepcionistas, operadores de totem y administradores del sistema.

---

## 1. Perfiles de Usuario y Niveles de Acceso (RBAC)

El sistema opera bajo un modelo de control de acceso basado en roles:

1. **SuperAdministrador (SUPERADMIN)**:
   - Control total de la plataforma.
   - Creacion, edicion y eliminacion de usuarios del sistema.
   - Eliminacion de eventos y purga general de registros.
   - Acceso al registro inmutable de auditoria.

2. **Administrador (ADMIN)**:
   - Creacion y configuracion de eventos.
   - Importacion de listas de asistentes (Excel y OneDrive).
   - Configuracion y calibracion del disenador de credenciales.
   - Exportacion de reportes consolidados en Excel.
   - Gestion de parametros de kiosko y umbral facial.

3. **Operador (OPERATOR)**:
   - Consulta de asistentes y busqueda rapida en recepcion.
   - Acreditacion manual y confirmacion de ingresos.
   - Emision y reimpresion de credenciales por extravio.
   - Enrolamiento de fotografias de asistentes.

---

## 2. Preparacion y Configuracion Previa al Evento

### 2.1 Creacion y Activacion del Evento
1. Inicie sesion en el panel administrativo (`http://localhost:5000/admin`).
2. En la seccion **Eventos**, presione el boton **Nuevo Evento**.
3. Complete el nombre (ejemplo: *Congreso Nacional de Mineria 2026*), la sede y una descripcion opcional.
4. Si dispone de una hoja compartida de Excel en linea, ingrese el enlace en **Enlace de OneDrive / SharePoint**.
5. Marque la casilla **Establecer como evento activo** y presione **Guardar Evento**.
6. Todas las terminales de kiosko y puntos de impresion quedaran sincronizados inmediatamente con este evento.

### 2.2 Carga de la Lista de Asistentes

#### Opcion A: Carga mediante Archivo Excel (.xlsx / .csv)
1. Prepare un archivo Excel con las siguientes columnas recomendadas en la primera fila:
   - `codigo` o `dni`: Identificador unico del participante.
   - `nombre` o `nombres_apellidos`: Nombre completo.
   - `empresa` o `institucion`: Organizacion de procedencia.
   - `cargo`: Puesto de trabajo.
   - `categoria`: Tipo de acceso (ejemplo: General, VIP, Expositor, Prensa).
2. En la pestana **Asistentes**, presione **Cargar Archivo**.
3. Seleccione el documento de su computadora. El sistema analizara los datos, insertara nuevos registros y actualizara los existentes sin generar duplicados.

#### Opcion B: Sincronizacion Continua con OneDrive / SharePoint
1. Si configuro el enlace en el evento, presione el boton **Sincronizar OneDrive**.
2. El sistema descargara el libro en memoria RAM, cotejara los cambios y actualizara el listado en cuestion de segundos.

### 2.3 Personalizacion de la Credencial (Disenador de Etiquetas)
1. Ingrese a la seccion **Disenador de Credencial** en el panel.
2. Active o desactive los campos segun las necesidades del evento:
   - **Nombre Completo**: Ajuste el tamano maximo de fuente (por defecto 54 pt). Si el nombre es extenso, la opcion *Multilinea Automatica* lo dividira en dos renglones balanceados.
   - **Empresa / Organizacion**: Tamano recomendado 30-34 pt en negrita.
   - **Cargo**: Tamano recomendado 24-28 pt regular.
   - **Codigo QR**: Permite habilitar o deshabilitar un codigo QR impreso en el costado derecho o izquierdo de la credencial.
   - **Espaciado y Alineacion**: Permite centrado o alineacion izquierda, asi como calibrar el espaciado vertical entre lineas.
3. Observe la **Vista Previa en Vivo**.
4. Presione **Imprimir Prueba** para verificar la alineacion y calidad fisica en la impresora Brother QL-800.
5. Presione **Guardar Plantilla**.

---

## 3. Operacion de Acreditacion en la Recepcion

### 3.1 Flujo de Atencion en Mostrador (Mesa de Registro Manual)
1. El asistente se aproxima al mostrador e indica su DNI, codigo o nombre.
2. El operador escribe el dato en la barra de busqueda del panel administrativo.
3. El resultado aparece en pantalla con su estado actual (Pendiente o Registrado).
4. El operador presiona el boton **Imprimir Credencial**:
   - El sistema envia la orden a la impresora Brother QL-800.
   - Al confirmarse la impresion, el asistente queda marcado automaticamente como **Registrado**.
   - El operador entrega la credencial fisica al asistente.

### 3.2 Protocolo de Reimpresion por Extravio o Deterioro
Si un participante acreditado extravia su credencial durante el transcurso del evento:
1. Busque al participante en la lista.
2. Verifique su identidad con un documento oficial.
3. Presione el boton **Reimprimir**.
4. El sistema solicitara confirmacion. Al aceptar, se generara una nueva etiqueta fisica y quedara registrado en el log de auditoria la fecha, hora y usuario que autorizo la reimpresion.

---

## 4. Operacion del Kiosko de Autoservicio / Totem

### 4.1 Puesta en Modo Kiosko
1. En la computadora conectada al totem, inicie la aplicacion y abra el navegador en modo quiosco:
   `http://localhost:5000/kiosk`
2. El sistema mostrara la pantalla de bienvenida institucional con la camara web activa.

### 4.2 Experiencia del Asistente

#### Modo Biometrico Facial Continuo (Auto-CheckIn)
1. El asistente se ubica frente a la pantalla a una distancia de entre 50 cm y 1 metro.
2. El sistema detecta el rostro y muestra un circulo verde de confirmacion.
3. Si el asistente fue pre-enrolado en la base de datos:
   - El sistema emite un sonido agradable de confirmacion.
   - En pantalla aparece el mensaje: *"Bienvenido(a) [Nombre del Asistente]"*.
   - La impresora Brother QL-800 expulsa y corta la credencial inmediatamente (tiempo promedio: 1.5 segundos).
   - El asistente toma su credencial y avanza hacia la sala.

#### Modo Codigo QR
1. El asistente aproxima el codigo QR recibido en su correo electronico frente a la camara web.
2. El sistema decodifica el valor, localiza el registro en la base de datos y procede a la emision automatica de la credencial.

#### Proteccion contra Duplicidad
Si una persona que ya retiro su credencial intenta registrarse nuevamente frente al totem:
- La pantalla muestra una alerta amarilla: *"El asistente ya cuenta con acreditacion previa registrada a las [Hora]"*.
- La impresora **NO emite duplicados**, evitando desperdicio de insumos y fraudes de acceso.
- Se le indica al asistente consultar en la mesa de atencion al cliente.

---

## 5. Cierre del Evento y Reportes

1. Ingrese a la pestana **Analitica** para revisar el tablero de metricas:
   - Total de invitados registrados vs pendientes.
   - Curva de afluencia horaria (horas pico de ingreso).
   - Porcentaje de participacion efectiva.
2. Presione el boton **Exportar Asistencia a Excel**.
3. El sistema descargara un archivo `.xlsx` estructurado con la relacion nominal, empresa, cargo, estado, fecha/hora exacta de ingreso y metodo utilizado (Facial, QR, Manual).

---

## 6. Resolucion de Incidentes Operativos en Vivo

### 6.1 La impresora no imprime y el sistema muestra "Impresora no lista"
- **Paso 1**: Verifique que la impresora este encendida (LED verde fijo). Si esta apagada, presione el boton de encendido.
- **Paso 2**: Revise que el cable USB este firmemente conectado al computador.
- **Paso 3**: Si el LED parpadea en color rojo, abra la cubierta superior y compruebe que el rollo DK-1208 este instalado correctamente y no se haya terminado.
- **Paso 4**: En el panel administrativo, presione el boton **Purgar Cola** para liberar trabajos en cola que puedan estar bloqueando el spooler de Windows.

### 6.2 El reconocimiento facial no detecta a la persona
- **Paso 1**: Verifique que la persona no tenga lentes oscuros o accesorios que oculten completamente los rasgos faciales.
- **Paso 2**: Asegurese de que la iluminacion del recinto no genere contraluz severo (ventanas o focos intensos directamente detras de la persona).
- **Paso 3**: Si la persona no esta enrolada previamente en la base biometrica, utilice la busqueda manual en recepcion por DNI para acreditarlo y, si se requiere, enrolar su rostro en ese instante.

### 6.3 Desconexion de Red o Caida de Internet
- El sistema opera de manera **completamente local y autonoma**.
- La base de datos MySQL, el motor biometrico YuNet/SFace y el controlador de la impresora se ejecutan en la computadora anfitriona sin requerir conexion a internet para la acreditacion continua.
