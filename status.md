# Estatus del Proyecto: Sistema CheckIn (Rama Main)

Fecha de Ultima Actualizacion: Septiembre 2026
Version del Sistema: 1.5.0-offline
Rama: main

---

## 1. Resumen Ejecutivo del Estado del Sistema

El sistema en la rama `main` se encuentra **completamente operativo y optimizado** para implementaciones locales y autonomas. Ofrece acreditacion mediante lectura de codigos QR y reconocimiento facial por vision artificial en CPU (YuNet + SFace), integracion de hardware nativa para la impresora termica **Brother QL-800** con rollo **DK-1208** (38mm x 90.3mm), e importacion flexible de datos desde hojas CSV locales y enlaces compartidos de **Microsoft OneDrive / SharePoint**.

---

## 2. Matriz de Componentes y Estado de Implementacion

| Modulo / Caracteristica | Estado | Descripcion |
| :--- | :--- | :--- |
| **Servidor y API Flask** | [COMPLETADO] | Servidor ligero en `app.py` con concurrencia controlada por cerrojos y almacenamiento local. |
| **Biometria Facial (YuNet + SFace)** | [COMPLETADO] | Pipeline de vision en CPU sin dependencias pesadas, extraccion de vectores 128D y enrolamiento de 1 a 4 fotos por persona. |
| **Impresion Termica Brother QL-800** | [COMPLETADO] | Renderizado GDI nativo de Windows a 300 DPI con rollo DK-1208. Validacion estricta: solo se confirma el check-in si la credencial fue emitida. |
| **Sincronizacion OneDrive / SharePoint** | [COMPLETADO] | Descarga directa y almacenamiento en cache en `onedrive_caches/`, permitiendo funcionamiento continuo sin internet. |
| **Kiosko de Autoservicio** | [COMPLETADO] | Pantalla completa interactiva (`/`), escaneo QR en vivo y deteccion facial automatica o manual. |
| **Panel de Administracion** | [COMPLETADO] | Interfaz web (`/admin`) con monitoreo de impresora, metricas en tiempo real, gestion de asistentes y reimpresiones. |
| **Documentacion Tecnica Integral** | [COMPLETADO] | Manuales organizados en `docs/` y guias de despliegue sin caracteres decorativos ni emojis. |

---

## 3. Requerimientos de Hardware y Software

- **Sistema Operativo**: Windows 10 o Windows 11 de 64 bits.
- **Python**: 3.10 o 3.11.
- **Impresora**: Brother QL-800 conectada por USB con rollo DK-1208.
- **Camara Web**: Camara USB o integrada HD 720p/1080p.

---

## 4. Indice de Documentacion Tecnica (`docs/`)

1. `docs/01_arquitectura_del_sistema.md`: Diseno general, flujo de datos, persistencia en archivos y proteccion de concurrencia.
2. `docs/02_biometria_y_procesamiento_facial.md`: Algoritmos YuNet y SFace, embeddings de 128 dimensiones y enrolamiento multi-foto.
3. `docs/03_impresion_y_hardware_brother.md`: Especificaciones del hardware Brother QL-800, renderizado GDI y regla transaccional de emision obligatoria.
4. `docs/04_guia_despliegue_y_replicacion.md`: Guia paso a paso para instalar y ejecutar el sistema en nuevas computadoras.
5. `docs/05_referencia_api_rest.md`: Catalogo de rutas HTTP de `app.py`.
6. `docs/06_manual_de_usuario_y_operaciones.md`: Manual operativo para el personal de recepcion y administradores del evento.
