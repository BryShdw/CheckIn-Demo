"""
face_service.py
───────────────
Módulo de reconocimiento y gestión facial usando OpenCV DNN con YuNet (detección)
y SFace (extracción de embeddings/características a 128 dimensiones).

Optimizado para ejecutarse en CPU x86_64 sin dependencias pesadas ni compiladores C++.
Soporta enrolamiento de 1 a 4 imágenes por invitado para aumentar la robustez de coincidencia.
"""

import base64
import io
import json
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from threading import Lock

import cv2
import numpy as np

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(exist_ok=True)

FACE_DATA_DIR = BASE_DIR / "face_data"
FACE_DATA_DIR.mkdir(exist_ok=True)
FACE_IMAGES_DIR = FACE_DATA_DIR / "images"
FACE_IMAGES_DIR.mkdir(exist_ok=True)

EMBEDDINGS_FILE = FACE_DATA_DIR / "embeddings.json"

YUNET_MODEL_PATH = MODELS_DIR / "face_detection_yunet.onnx"
SFACE_MODEL_PATH = MODELS_DIR / "face_recognition_sface.onnx"

# Umbral de similitud coseno por defecto (producto punto de vectores normalizados)
# Rango típico: 0.60 a 0.75 para alta certeza.
DEFAULT_COSINE_THRESHOLD = 0.62

_face_lock = Lock()
_detector_instance = None
_recognizer_instance = None
_embeddings_cache: dict[str, list[dict]] = {}


def check_and_download_models():
    """Descarga los modelos ONNX oficiales si no existen."""
    import requests

    urls = {
        YUNET_MODEL_PATH: "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        SFACE_MODEL_PATH: "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
    }
    for path, url in urls.items():
        if not path.exists() or path.stat().st_size < 1000:
            log.info(f"Descargando modelo facial {path.name}...")
            r = requests.get(url, allow_redirects=True, timeout=30)
            if r.status_code == 200:
                path.write_bytes(r.content)
                log.info(f"Modelo {path.name} guardado ({len(r.content)} bytes).")
            else:
                raise RuntimeError(f"Error descargando {path.name}: HTTP {r.status_code}")


def init_face_service():
    """Inicializa los detectores y carga los embeddings en memoria."""
    global _detector_instance, _recognizer_instance
    check_and_download_models()

    log.info("Inicializando OpenCV YuNet y SFace...")
    _detector_instance = cv2.FaceDetectorYN.create(
        str(YUNET_MODEL_PATH),
        "",
        (320, 320),
        score_threshold=0.55,
        nms_threshold=0.3,
        top_k=5,
    )
    _recognizer_instance = cv2.FaceRecognizerSF.create(str(SFACE_MODEL_PATH), "")
    load_embeddings_from_disk()
    log.info(f"Servicio facial listo. Invitados con rostros enrolados: {len(_embeddings_cache)}")


def load_embeddings_from_disk():
    global _embeddings_cache
    with _face_lock:
        if EMBEDDINGS_FILE.exists():
            try:
                _embeddings_cache = json.loads(EMBEDDINGS_FILE.read_text(encoding="utf-8"))
            except Exception as e:
                log.error(f"Error cargando {EMBEDDINGS_FILE}: {e}")
                _embeddings_cache = {}
        else:
            _embeddings_cache = {}


def save_embeddings_to_disk():
    with _face_lock:
        try:
            EMBEDDINGS_FILE.write_text(
                json.dumps(_embeddings_cache, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.error(f"Error guardando {EMBEDDINGS_FILE}: {e}")


def decode_image_input(img_input) -> np.ndarray | None:
    """
    Convierte imagen en bytes, string Base64 o array NumPy en formato BGR de OpenCV.
    """
    if isinstance(img_input, np.ndarray):
        return img_input

    if isinstance(img_input, str):
        # Manejar data URL: "data:image/jpeg;base64,..."
        if "base64," in img_input:
            img_input = img_input.split("base64,")[1]
        try:
            raw_bytes = base64.b64decode(img_input)
            nparr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            log.error(f"Error decodificando imagen base64: {e}")
            return None

    if isinstance(img_input, (bytes, bytearray)):
        try:
            nparr = np.frombuffer(img_input, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            log.error(f"Error decodificando imagen desde bytes: {e}")
            return None

    return None


def extract_face_feature(img_bgr: np.ndarray):
    """
    Detecta el rostro principal y extrae el embedding normalizado de 128 dimensiones.
    Retorna: (feature_normalized, aligned_face, bbox, score) o None si no se detecta rostro.
    """
    if img_bgr is None or img_bgr.size == 0:
        return None

    h, w = img_bgr.shape[:2]

    # Re-escalar si es excesivamente grande para velocidad
    max_dim = 960
    scale = 1.0
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        new_w, new_h = int(w * scale), int(h * scale)
        proc_img = cv2.resize(img_bgr, (new_w, new_h))
    else:
        proc_img = img_bgr

    ph, pw = proc_img.shape[:2]

    with _face_lock:
        _detector_instance.setInputSize((pw, ph))
        retval, faces = _detector_instance.detect(proc_img)

    if faces is None or len(faces) == 0:
        return None

    # Seleccionar la cara con mayor área o score (rostro principal)
    best_face = None
    best_score = -1.0
    for face in faces:
        score = face[14]
        # Área del bounding box (ancho * alto)
        area = face[2] * face[3]
        if area > 1200 and score > best_score:
            best_score = score
            best_face = face

    if best_face is None:
        best_face = faces[0]

    # Reajustar coordenadas si se escaló la imagen
    if scale != 1.0:
        actual_face = best_face.copy()
        actual_face[:14] = actual_face[:14] / scale
    else:
        actual_face = best_face

    # Alinear y recortar rostro (SFace espera dimensiones estándar alineadas por landmarks)
    aligned_face = _recognizer_instance.alignCrop(img_bgr, actual_face)

    # Extraer feature embedding
    feature = _recognizer_instance.feature(aligned_face)

    # Normalizar a vector unitario L2
    norm = np.linalg.norm(feature)
    if norm > 0:
        norm_feature = feature / norm
    else:
        norm_feature = feature

    bbox = [int(actual_face[0]), int(actual_face[1]), int(actual_face[2]), int(actual_face[3])]
    score = float(actual_face[14])

    return norm_feature.flatten().tolist(), aligned_face, bbox, score


def enroll_guest_image(guest_id: str, img_input, max_images: int = 4) -> dict:
    """
    Registra una imagen para el invitado. Permite hasta max_images (por defecto 4).
    """
    guest_id = guest_id.strip().upper()
    img_bgr = decode_image_input(img_input)
    if img_bgr is None:
        return {"success": False, "error": "Formato de imagen inválido o no legible."}

    extracted = extract_face_feature(img_bgr)
    if not extracted:
        return {
            "success": False,
            "error": "No se detectó ningún rostro nítido. Asegúrate de tener buena luz y mirar hacia la cámara.",
        }

    feature_vec, aligned_face, bbox, score = extracted

    guest_dir = FACE_IMAGES_DIR / guest_id
    guest_dir.mkdir(exist_ok=True)

    guest_faces = _embeddings_cache.get(guest_id, [])

    if len(guest_faces) >= max_images:
        return {
            "success": False,
            "error": f"Límite alcanzado: el invitado ya tiene {max_images} fotos registradas. Elimina alguna para agregar una nueva.",
            "face_count": len(guest_faces),
        }

    image_id = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:19]}"
    img_filename = f"{image_id}.jpg"
    thumb_filename = f"{image_id}_aligned.jpg"

    cv2.imwrite(str(guest_dir / img_filename), img_bgr)
    cv2.imwrite(str(guest_dir / thumb_filename), aligned_face)

    new_record = {
        "image_id": image_id,
        "filename": img_filename,
        "thumb_filename": thumb_filename,
        "created_at": datetime.now().isoformat(),
        "score": score,
        "embedding": feature_vec,
    }

    guest_faces.append(new_record)
    _embeddings_cache[guest_id] = guest_faces
    save_embeddings_to_disk()

    log.info(f"Rostro enrolado para {guest_id} (Total fotos: {len(guest_faces)}).")
    return {
        "success": True,
        "guest_id": guest_id,
        "image_id": image_id,
        "face_count": len(guest_faces),
        "score": round(score, 3),
        "message": f"Foto registrada con éxito (Total: {len(guest_faces)}/{max_images}).",
    }


def get_guest_faces(guest_id: str) -> list[dict]:
    """Retorna las fotos enroladas para un invitado."""
    guest_id = guest_id.strip().upper()
    faces = _embeddings_cache.get(guest_id, [])
    result = []
    for f in faces:
        result.append({
            "image_id": f["image_id"],
            "created_at": f.get("created_at"),
            "score": f.get("score"),
            "url": f"/api/guest/{guest_id}/face-image/{f['image_id']}",
            "thumb_url": f"/api/guest/{guest_id}/face-image/{f['image_id']}?thumb=1",
        })
    return result


def delete_guest_face(guest_id: str, image_id: str | None = None) -> bool:
    """Elimina una o todas las fotos y embeddings de un invitado."""
    guest_id = guest_id.strip().upper()
    if guest_id not in _embeddings_cache:
        return False

    guest_dir = FACE_IMAGES_DIR / guest_id

    if not image_id:
        # Borrar todas
        del _embeddings_cache[guest_id]
        save_embeddings_to_disk()
        if guest_dir.exists():
            shutil.rmtree(guest_dir, ignore_errors=True)
        return True

    # Borrar una foto específica
    faces = _embeddings_cache[guest_id]
    target = next((f for f in faces if f["image_id"] == image_id), None)
    if not target:
        return False

    faces = [f for f in faces if f["image_id"] != image_id]
    if faces:
        _embeddings_cache[guest_id] = faces
    else:
        del _embeddings_cache[guest_id]

    save_embeddings_to_disk()

    # Eliminar archivos físicos
    for fn in (target.get("filename"), target.get("thumb_filename")):
        if fn:
            p = guest_dir / fn
            if p.exists():
                try:
                    p.unlink()
                except Exception:
                    pass

    return True


def get_enrolled_counts() -> dict[str, int]:
    """Retorna dict { guest_id: count } para todos los invitados."""
    return {gid: len(faces) for gid, faces in _embeddings_cache.items()}


def match_face(img_input, threshold: float = DEFAULT_COSINE_THRESHOLD) -> dict:
    """
    Busca coincidencias para el rostro presente en `img_input`.
    Calcula similitud coseno contra todos los vectores de todos los usuarios registrados.
    Para cada usuario con múltiples fotos (2-4 fotos), toma el máximo de similitud.
    """
    img_bgr = decode_image_input(img_input)
    if img_bgr is None:
        return {"matched": False, "reason": "invalid_image", "message": "Imagen no válida"}

    extracted = extract_face_feature(img_bgr)
    if not extracted:
        return {"matched": False, "reason": "no_face", "message": "No se detectó rostro"}

    query_vec, aligned_face, bbox, det_score = extracted
    query_arr = np.array(query_vec, dtype=np.float32)

    if not _embeddings_cache:
        return {
            "matched": False,
            "reason": "no_enrolled_faces",
            "message": "No hay rostros registrados en el sistema",
            "bbox": bbox,
        }

    best_guest_id = None
    best_similarity = -1.0

    for gid, faces in _embeddings_cache.items():
        if not faces:
            continue
        # Calcular similitud contra cada vector del usuario
        user_sims = []
        for face_record in faces:
            stored_vec = np.array(face_record["embedding"], dtype=np.float32)
            # Producto punto (similitud coseno ya que ambos están normalizados a norma L2 = 1)
            sim = float(np.dot(query_arr, stored_vec))
            user_sims.append(sim)

        max_user_sim = max(user_sims) if user_sims else -1.0
        if max_user_sim > best_similarity:
            best_similarity = max_user_sim
            best_guest_id = gid

    is_match = best_similarity >= threshold

    return {
        "matched": is_match,
        "guest_id": best_guest_id if is_match else None,
        "candidate_id": best_guest_id,
        "similarity": round(best_similarity, 4),
        "threshold": threshold,
        "bbox": bbox,
        "detection_score": round(det_score, 3),
        "message": "Rostro identificado exitosamente" if is_match else "Rostro no reconocido",
    }
