# Subsistema de Impresion Termica y Hardware Brother QL-800

Este documento detalla las especificaciones tecnicas, protocolos de comunicacion, gestion de colas y reglas criticas de negocio asociadas al hardware de impresion termica de credenciales.

---

## 1. Especificaciones de Hardware

El sistema esta calibrado y optimizado de forma nativa para la impresora termica de etiquetas de alta velocidad **Brother QL-800** (compatible tambien con QL-810W y QL-820NWB mediante conexion USB local).

- **Fabricante**: Brother Industries, Ltd.
- **Modelo Oficial**: Brother QL-800
- **Tecnologia**: Termica directa (sin tinta ni cinta toner).
- **Resolucion de Cabezal**: 300 x 300 DPI (hasta 300 x 600 DPI en modo de alta resolucion).
- **Consumible Estandar**: Rollo de etiquetas troqueladas precortadas **DK-1208** (Papel blanco termico de alta blancura con adhesivo o soporte de solapero).
- **Dimensiones Fisicas de Etiqueta**: 38 mm (alto) x 90.3 mm (ancho).
- **Dimensiones en Pixeles (300 DPI)**: 413 px (alto) x 991 px (ancho).
- **Interfaz de Comunicacion**: USB 2.0 Full Speed (Conector Tipo B hembra en impresora hacia Tipo A/C en el computador anfitrion).

---

## 2. Subsistema de Software y Renderizado de Etiquetas

El renderizado y spooling se gestionan a traves de `app/services/printer_service.py` utilizando dos capas fundamentales:

### 2.1 Generacion Matricial de la Imagen (Pillow / PIL)

Cada etiqueta se construye dinamicamente en memoria RAM en escala de grises de 8 bits (`L`) con fondo blanco (`255`) y trazos en negro puro (`0`):
1. **Lienzo**: Canvas exacto de 991 x 413 pixeles.
2. **Fuentes Tipograficas**: Familia tipografica del sistema Windows (`Segoe UI Bold / Regular`, con fallbacks a `Arial`, `Calibri` o `Tahoma`).
3. **Ajuste Dinamico de Tamano (`fit_font`)**: Si el texto de la persona, empresa o cargo supera el ancho util horizontal, la funcion reduce progresivamente el tamano de punto de 2 en 2 pixeles hasta encajar dentro de los margenes sin truncar el nombre.
4. **Division Balanceada de Nombres (`split_name_balanced`)**: Para nombres largos que superan el ancho maximo permitido, el algoritmo divide el texto en dos lineas manteniendo el equilibrio sintactico entre palabras.
5. **Generacion de Codigo QR Integrado**: Mediante la libreria `qrcode`, se genera una matriz QR Version 1 (Nivel de correccion de errores M) que se escala e inserta en el margen derecho o izquierdo segun la plantilla.

### 2.2 Subsistema GDI de Windows (`win32print` y `win32ui`)

Para garantizar la maxima nitidez y evitar dialogos emergentes del navegador:
1. Se abre el canal de impresion directo mediante `win32print.OpenPrinter()`.
2. Se instancia un Contexto de Dispositivo (`win32ui.CreateDC()`) asociado al controlador oficial de Windows.
3. Se invoca `StartDoc()` y `StartPage()`.
4. La imagen rasterizada se transfiere como bitmap independiente del dispositivo (`ImageWin.Dib`) al contexto GDI del cabezal termico.
5. Se llama `EndPage()`, `EndDoc()` y `DeleteDC()`. El corte automatico de la cuchilla de la Brother QL-800 se ejecuta al finalizar la pagina.

---

## 3. Regla Critica de Negocio: Validacion Estricta de Impresion

A diferencia de sistemas web tradicionales que confirman la asistencia antes de saber si la impresora respondio, este sistema implementa una **politica transaccional estricta de hardware**:

> [REGLA OBLIGATORIA]: Un asistente NO es registrado en la base de datos MySQL como "Presente" ni se genera registro en la tabla `checkins` si la emision fisica de la credencial falla.

### Flujo de Ejecucion Transaccional

```
[Captura / DNI / QR / Facial]
              |
              v
[Validacion de existencia en evento activo]
              |
              v
[Comprobacion de Hardware Brother QL-800]
     |-- Si no esta conectada / sin papel / offline
     |   --> Retorna ERROR 500 / 400
     |   --> Transaccion BD abortada (Cero registros fantasma)
     |
     v
[Spooling Fisico al Cabezal Termico GDI]
     |-- Si spooling falla (excepcion Win32)
     |   --> Retorna ERROR
     |   --> Rollback en MySQL
     |
     v
[Emision Exitosa de Etiqueta]
     |
     v
[Commit en MySQL: checkins y audit_logs]
```

Esta politica garantiza que ningun asistente quede marcado como registrado si no tiene fisicamente su credencial en la mano.

---

## 4. Deteccion de Estado y Diagnostico de Hardware

El servicio expone la funcion `get_printer_connection_status()` y el endpoint `GET /api/printer/status`, ejecutando una verificacion en dos etapas:

### 4.1 Comprobacion en el Bus USB via WMI PnP
Consulta el subsistema WMI (`Win32_PnPEntity`) buscando dispositivos cuyo Vendor ID corresponda a Brother (`VID_04F9`). Si el dispositivo no aparece en la enumeracion PnP, el sistema reporta de inmediato:
- **Estado**: Desconectada o Apagada.
- **Detalle**: Cable USB no detectado o interruptor apagado.

### 4.2 Comprobacion del Spooler de Windows
Si el dispositivo USB esta conectado, se interroga a la API de Windows (`GetPrinter` Nivel 2) para evaluar las banderas de estado:
- `PRINTER_STATUS_OFFLINE (0x00000080)`: Fuera de linea.
- `PRINTER_STATUS_PAUSED (0x00000001)`: Cola pausada.
- `PRINTER_STATUS_ERROR (0x00000002)`: Error de hardware.
- `PRINTER_STATUS_PAPER_JAM (0x00000008)`: Atasco de papel en rodillo.
- `PRINTER_STATUS_PAPER_OUT (0x00000010)`: Carrete de etiquetas agotado.

---

## 5. Disenador Dinamico de Etiquetas

La disposicion visual de la credencial se almacena en formato JSON dentro de la columna `label_template` de la tabla `events`:

```json
{
  "header_text": {
    "enabled": false,
    "text": "CONGRESO INTERNACIONAL 2026",
    "font_size": 22,
    "bold": true
  },
  "full_name": {
    "enabled": true,
    "font_size": 54,
    "bold": true,
    "auto_multiline": true
  },
  "company": {
    "enabled": true,
    "font_size": 32,
    "bold": true
  },
  "position": {
    "enabled": true,
    "font_size": 26,
    "bold": false
  },
  "category": {
    "enabled": false,
    "font_size": 22,
    "bold": true
  },
  "guest_code": {
    "enabled": false,
    "font_size": 20,
    "bold": false
  },
  "qr_code": {
    "enabled": false,
    "position": "right",
    "size": 130
  },
  "align": "center",
  "line_spacing": 14,
  "vertical_offset": 0
}
```

Desde el panel de administracion (`/admin`), el operador puede previsualizar en tiempo real el renderizado exacto en PNG (`POST /admin/api/label-preview`) y emitir una prueba fisica al presionar "Imprimir Prueba" (`POST /admin/api/label-template/test-print`).

---

## 6. Resolucion de Problemas Frecuentes de Hardware

### 6.1 LED de Estado en Brother QL-800
- **Verde fijo**: Impresora encendida, en linea y lista.
- **Naranja / Verde parpadeante**: Recibiendo datos de impresion.
- **Rojo parpadeante**:
  - Tapa superior abierta.
  - Rollo agotado o mal colocado.
  - Carrete de tamano no coincidente con la configuracion del controlador.
- **Rojo fijo**: Error critico del cabezal o fallo de alimentacion.

### 6.2 Trabajos Atascados en Cola de Windows
Si un trabajo queda en estado "Error - Imprimiendo" en la cola del sistema operativo, ningun trabajo posterior podra procesarse.
- **Solucion desde el Sistema**: En el panel de control o mediante peticion POST a `/api/printer/purge-jobs`, el sistema ejecuta `win32print.SetPrinter(..., PRINTER_CONTROL_PURGE)`, eliminando todos los trabajos pendientes y liberando el puerto.
- **Solucion Manual en Windows**: Abrir PowerShell como Administrador y reiniciar el spooler:
  ```powershell
  Stop-Service Spooler
  Remove-Item -Path "C:\Windows\System32\spool\PRINTERS\*" -Force
  Start-Service Spooler
  ```

### 6.3 Configuracion Recomendada en el Controlador de Windows
Para evitar desfases en el corte o margenes desalineados:
1. Abrir `Configuracion de Windows -> Dispositivos -> Impresoras y escaneres`.
2. Seleccionar `Brother QL-800 -> Propiedades de la impresora -> Preferencias de impresion`.
3. Establecer **Tamano del papel**: `DK-1208 (38mm x 90.3mm)` o `38mm x 90mm`.
4. Establecer **Corte**: `Corte automatico al final de cada etiqueta`.
5. Calidad de impresion: `Prioridad a la resolucion (300 dpi)`.
