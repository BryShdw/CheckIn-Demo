# Impresion Termica y Hardware Brother QL-800

Este documento contiene las especificaciones de integracion del hardware de impresion termica Brother QL-800 con el sistema CheckIn.

---

## 1. Caracteristicas del Hardware

- **Dispositivo Soportado**: Brother QL-800 (y modelos compatibles de la serie QL: QL-810W, QL-820NWB conectados por USB).
- **Consumible Oficial**: Rollo troquelado precortado **Brother DK-1208** (38 mm de alto x 90.3 mm de ancho).
- **Resolucion**: 300 x 300 DPI.
- **Dimensiones del Canvas de Impresion**: 991 pixeles de ancho x 413 pixeles de alto (orientacion apaisada / landscape).
- **Mecanismo de Corte**: Cuchilla automatica integrada al finalizar cada etiqueta.

---

## 2. Renderizado GDI y Spooler de Windows

El sistema no utiliza el dialogo de impresion de HTML ni ventanas emergentes del navegador. En su lugar, utiliza el subsistema de interfaz grafica de dispositivos (GDI) de Windows:

1. Se genera la etiqueta en memoria RAM utilizando la libreria `Pillow (PIL)`.
2. Se utiliza la familia de fuentes tipograficas del sistema operativo (`Arial`, `Segoe UI`).
3. El tamano de fuente del nombre se escala dinamicamente mediante la funcion `fit_font` para evitar desbordes.
4. Para nombres largos de tres o mas palabras, la funcion `split_name_balanced` divide el texto en dos lineas manteniendo el equilibrio visual.
5. El bitmap resultante se envia directamente al controlador de Windows mediante `win32print.OpenPrinter()` y `win32ui.CreateDC()`.

---

## 3. Diseno de Etiqueta DK-1208

Dado que las credenciales físicas frecuentemente cuentan con un emblema pre-impreso con la marca y grafica del evento:
- **Nombre Completo**: Ocupa el centro superior en tipografia grande y negrita.
- **Empresa / Institucion**: Se ubica en la parte intermedia en tamano destacado.
- **Cargo / Posicion**: Se posiciona en la parte inferior en estilo regular.
- **Elementos suprimidos**: Se omiten codigos de barras, bordes y encabezados innecesarios para garantizar la maxima legibilidad a distancia.

---

## 4. Regla Transaccional de Impresion

> [REGLA OBLIGATORIA]: La asistencia de un participante en `checkins.json` se valida UNICAMENTE cuando el trabajo de impresion fue recibido y aceptado exitosamente por el spooler de la impresora Brother.

Si el cable USB se encuentra desconectado, la impresora esta apagada, o la cola se encuentra pausada o con error de papel:
1. El sistema aborta la transaccion.
2. La asistencia del invitado se mantiene como **Pendiente**.
3. Se muestra una notificacion clara en pantalla indicando el problema de hardware para su pronta resolucion.

---

## 5. Deteccion de Estado y Purga de Cola

### 5.1 Verificacion WMI PnP
Mediante consultas WMI (`Win32_PnPEntity`), el sistema verifica si la impresora Brother (`VID_04F9`) esta conectada fisicamente al bus USB. Si el dispositivo no responde o esta apagado, el estado se marca de inmediato como "Desconectada o Apagada".

### 5.2 Purga de Trabajos Atascados
A traves del endpoint `POST /api/printer/purge-jobs` o desde el boton en el panel administrativo, el sistema ejecuta la orden de purga de Windows GDI (`PRINTER_CONTROL_PURGE`), cancelando trabajos pendientes que puedan tener el puerto bloqueado.
