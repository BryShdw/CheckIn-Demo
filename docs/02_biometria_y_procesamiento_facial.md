# Biometria y Procesamiento Facial en CheckIn-DACER

## 1. Descripcion General

El modulo biometrico de CheckIn-DACER proporciona identificacion facial en tiempo real ejecutada completamente en CPU (sin requerir tarjetas graficas dedicadas GPU). Utiliza el modulo DNN (Deep Neural Networks) de OpenCV junto con arquitecturas neuronales optimizadas para inferencia ligera y de baja latencia.

---

## 2. Modelos Neuronales Utilizados

| Componente | Red Neuronal | Archivo de Modelo | Entrada | Salida |
|---|---|---|---|---|
| **Detector Facial** | **YuNet** | `models/face_detection_yunet.onnx` | Imagen BGR 320x320 o dinamica | Bounding Box, landmarks (ojos, nariz, comisuras) y confianza |
| **Extractor de Caracteristicas** | **SFace** | `models/face_recognition_sface.onnx` | Region facial alineada 112x112 | Vector de caracteristicas (Embedding) de 128 dimensiones |

Los pesos neuronales provienen de los repositorios oficiales de OpenCV Model Zoo y operan en precision FP32/quantized para asegurar consistencia determinista entre plataformas.

---

## 3. Flujo de Procesamiento en Tiempo Real

```
[ Camara Web / Video Stream ]
            |
            v  Frame capturado (Base64 JPEG o Canvas)
[ Decodificacion OpenCV (cv2.imdecode) ]
            |
            v
[ Detector YuNet ] ---> ¿Rostro detectado con confianza >= 0.75?
            |           No  --> Retornar { status: "no_face" }
            v Si
[ Alineacion Facial mediante Landmarks ]
            |
            v
[ Extractor SFace ] ---> Generacion de Vector de 128 Dimensiones (Embedding)
            |
            v
[ Busqueda en Memoria RAM (Vectorial Cosine Similarity) ]
            |
            v
   ¿Maxima similitud >= Umbral (0.70)?
    |                       |
    | Si                    | No
    v                       v
[ Match Exitoso ]      [ Rostro No Reconocido ]
(Asociado a Guest ID)  (Incrementar contador de frames no coincidentes)
```

---

## 4. Algoritmo de Coincidencia (Cosine Similarity)

Dado un embedding de consulta `E_q` extraido del frame de camara y un embedding almacenado `E_db` perteneciente a un participante enrolado:

$$\text{Similitud Cosine} = \frac{E_q \cdot E_{db}}{\|E_q\|_2 \times \|E_{db}\|_2}$$

Dado que SFace produce vectores normalizados L2 ($\|E\|_2 = 1$), el calculo se simplifica al producto escalar directo:

$$\text{Similitud} = E_q \cdot E_{db} = \sum_{i=1}^{128} E_q[i] \times E_{db}[i]$$

### Calibracion del Umbral de Coincidencia (Threshold = 0.70)
- **0.50 - 0.60 (Baja especificidad)**: Propenso a falsos positivos en entornos con iluminacion no controlada o participantes con rasgos similares.
- **0.70 (Punto de operacion calibrado)**: Garantiza cero falsos positivos en entornos corporativos masivos, permitiendo una identificacion inmediata y certera.
- **0.80+ (Alta rigidez)**: Recomendado unicamente cuando se dispone de iluminacion de estudio profesional y enrolamiento multi-angulo.

---

## 5. Persistencia y Almacenamiento Cero-Disco

Para garantizar privacidad, portabilidad y limpieza del entorno:
1. **Los embeddings faciales se almacenan en MySQL**: La tabla `face_profiles` almacena el vector de 128 floats codificado en formato JSON o binario estructurado, junto con la miniatura base64 del rostro.
2. **Cero archivos residuales en disco**: Las imagenes enviadas no se guardan como archivos temporales en el sistema de archivos del servidor.
3. **Cache de memoria en caliente**: Al inicializar la aplicacion o al cambiar de evento activo, `FaceRecognitionService` carga todos los embeddings del evento en estructuras `numpy.ndarray` en memoria RAM. Esto permite comparar un rostro contra cientos o miles de asistentes en menos de 5 milisegundos.

---

## 6. Proceso de Enrolamiento de Asistentes

El enrolamiento puede realizarse por dos vias:
1. **Enrolamiento individual en el Panel de Administracion**:
   - Captura directa desde la camara web del operador.
   - Subida de fotografia (JPG/PNG).
   - Se admite registrar de 1 a 4 perfiles faciales por participante (vista frontal, leve inclinacion izquierda, leve inclinacion derecha) para mejorar el reconocimiento en angulos variables.
2. **Eliminacion y depuracion**:
   - Se pueden eliminar perfiles faciales individuales (`DELETE /api/guest/<id>/face/<face_id>`).
   - Se pueden purgar todos los perfiles de un evento desde el panel con un solo clic.
