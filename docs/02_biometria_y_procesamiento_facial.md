# Biometria y Procesamiento Facial

Este documento detalla el funcionamiento del subsistema biometrico facial implementado en el archivo `face_service.py`, sus modelos de red neuronal y los criterios de decision para el reconocimiento de asistentes.

---

## 1. Arquitectura de Redes Neuronales (OpenCV DNN)

El sistema utiliza dos modelos complementarios en formato abierto ONNX:

### 1.1 Detector Facial: YuNet
- **Archivo**: `models/face_detection_yunet.onnx`
- **Tamano de entrada estandar**: 320 x 320 pixeles.
- **Salida**: Bounding box del rostro, puntaje de confianza y ubicacion de 5 puntos de referencia (landmarks: ojo derecho, ojo izquierdo, punta de la nariz, comisura derecha de la boca, comisura izquierda de la boca).
- **Rendimiento**: Menos de 15 ms por fotograma en procesadores x86_64 multinucleo convencionales.

### 1.2 Extractor de Caracteristicas: SFace
- **Archivo**: `models/face_recognition_sface.onnx`
- **Operacion**: Toma el recorte facial alineado generado por YuNet y extrae un vector denso de 128 numeros en punto flotante (embedding).
- **Normalizacion**: Cada vector se normaliza segun su norma euclidiana L2:
  ```
  v_norm = v / ||v||_2
  ```

---

## 2. Metrica de Comparacion y Criterios de Decision

Dado que los embeddings estan normalizados unitariamente, la distancia angular y la similitud coseno se calculan mediante el producto escalar simple:

```
Similitud(A, B) = A . B
```

El valor resultante oscila en el intervalo `[-1.0, 1.0]`, donde 1.0 representa coincidencia biometrica identica.

### 2.1 Umbral de Decision
- **Umbral por Defecto (`DEFAULT_COSINE_THRESHOLD`)**: `0.55` (en rama main) o configurable hasta `0.70` para entornos con tolerancia cero a falsos positivos.
- **Margen de Ambiguedad (`MIN_AMBIGUITY_MARGIN`)**: `0.040`. Para que una identificacion sea aceptada, el mejor candidato (Top-1) debe superar al segundo mejor candidato (Top-2) por al menos este margen, evitando coincidencias ambiguas entre personas de fisonomia parecida.

---

## 3. Enrolamiento Multi-Foto

Para maximizar la tasa de acierto del reconocimiento frente al totem sin exigir una pose rigida al usuario:
1. El sistema permite registrar de **1 a 4 fotos por asistente**.
2. Cada imagen puede capturar al usuario con diferentes expresiones (serio, sonriente) o ligeras variaciones de angulo (+/- 15 grados).
3. Los vectores se indexan en memoria en el diccionario `_embeddings_cache` y se persisten en `face_data/embeddings.json`.
4. Al evaluar una cara en el kiosko, la similitud del asistente corresponde al valor maximo obtenido entre cualquiera de sus fotos enroladas.

---

## 4. Almacenamiento y Privacidad

- Los recortes faciales miniatura de referencia se guardan en la carpeta `face_data/images/`.
- El archivo `face_data/embeddings.json` almacena exclusivamente los vectores numericos anonimizados vinculados al identificador del invitado.
- Si se requiere purgar la informacion biometrica de un evento, el panel administrativo ofrece la opcion de eliminacion individual o reseteo completo de la galeria mediante `/api/faces/delete-all`.
