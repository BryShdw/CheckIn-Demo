import base64
import json
import logging
import os
import shutil
import urllib.request
from datetime import datetime
from threading import RLock
import cv2
import numpy as np

from app.config import Config
from app.extensions import db
from app.models.face_profile import FaceProfile
from app.models.guest import Guest

log = logging.getLogger(__name__)

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

YUNET_MODEL_PATH = Config.MODELS_DIR / "face_detection_yunet.onnx"
SFACE_MODEL_PATH = Config.MODELS_DIR / "face_recognition_sface.onnx"

DEFAULT_COSINE_THRESHOLD = Config.DEFAULT_FACE_THRESHOLD
MIN_AMBIGUITY_MARGIN = 0.040

_face_lock = RLock()
_detector_instance = None
_recognizer_instance = None
_embeddings_cache: dict[str, list[dict]] = {}  # { guest_code: [ { image_id, embedding, ... } ] }


def _download_model_if_missing(path, url, name):
    if not path.exists():
        Config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        log.info(f"Descargando modelo {name} desde {url}...")
        try:
            urllib.request.urlretrieve(url, path)
            log.info(f"Modelo {name} guardado en {path}")
        except Exception as e:
            log.error(f"Error descargando {name}: {e}")
            raise


def init_face_service():
    """Inicializa YuNet y SFace, y precarga los embeddings desde la base de datos MySQL."""
    global _detector_instance, _recognizer_instance
    with _face_lock:
        if _detector_instance is not None and _recognizer_instance is not None:
            return

        Config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        Config.FACE_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

        _download_model_if_missing(YUNET_MODEL_PATH, YUNET_URL, "YuNet Face Detector")
        _download_model_if_missing(SFACE_MODEL_PATH, SFACE_URL, "SFace Face Recognizer")

        log.info("Inicializando OpenCV YuNet y SFace...")
        _detector_instance = cv2.FaceDetectorYN.create(
            str(YUNET_MODEL_PATH),
            "",
            (320, 320),
            score_threshold=0.45,
            nms_threshold=0.3,
            top_k=5,
        )

        _recognizer_instance = cv2.FaceRecognizerSF.create(
            str(SFACE_MODEL_PATH),
            "",
        )

        reload_embeddings_from_db()


def reload_embeddings_from_db(event_id: int | None = None):
    """Recarga la caché de embeddings en memoria directamente desde la base de datos MySQL para el evento activo."""
    global _embeddings_cache
    with _face_lock:
        _embeddings_cache = {}
        try:
            if event_id is None:
                from app.services.guest_service import get_or_create_active_event
                ev = get_or_create_active_event()
                event_id = ev.id if ev else None

            if event_id:
                profiles = FaceProfile.query.join(Guest).filter(Guest.event_id == event_id).all()
            else:
                profiles = FaceProfile.query.all()

            for p in profiles:
                guest = p.guest
                if not guest:
                    continue
                code = guest.guest_code
                if code not in _embeddings_cache:
                    _embeddings_cache[code] = []
                emb = p.get_embedding()
                if emb:
                    _embeddings_cache[code].append({
                        "image_id": p.image_id,
                        "filename": p.filename,
                        "thumb_filename": p.thumb_filename,
                        "embedding": emb,
                        "score": p.quality_score or 1.0,
                    })
            log.info(f"Servicio facial listo. Invitados con rostros enrolados en MySQL: {len(_embeddings_cache)}")
        except Exception as e:
            log.warning(f"No se pudieron cargar perfiles faciales desde MySQL: {e}")


def extract_face_feature(img_bgr: np.ndarray, min_area: int = 2500):
    """Detecta el rostro principal y extrae el embedding normalizado de 128 dimensiones."""
    if img_bgr is None or img_bgr.size == 0:
        return None

    h, w = img_bgr.shape[:2]
    max_dim = 640
    scale = 1.0
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        work_img = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    else:
        work_img = img_bgr

    wh, ww = work_img.shape[:2]

    with _face_lock:
        if _detector_instance is None or _recognizer_instance is None:
            init_face_service()
        _detector_instance.setInputSize((ww, wh))
        _, faces = _detector_instance.detect(work_img)

    if faces is None or len(faces) == 0:
        return None

    # Seleccionar el rostro en primer plano: mayor área con confianza confiable
    best_face = None
    max_area = -1.0
    scaled_min_area = int(min_area * (scale * scale))

    for face in faces:
        score = face[14]
        area = face[2] * face[3]
        if area >= scaled_min_area and score >= 0.40:
            if area > max_area:
                max_area = area
                best_face = face

    if best_face is None:
        best_score = -1.0
        for face in faces:
            score = face[14]
            area = face[2] * face[3]
            if area >= scaled_min_area and score > best_score:
                best_score = score
                best_face = face

    if best_face is None:
        return None

    if scale != 1.0:
        actual_face = best_face.copy()
        actual_face[0:14] /= scale
    else:
        actual_face = best_face

    with _face_lock:
        aligned_face = _recognizer_instance.alignCrop(img_bgr, actual_face)
        feature = _recognizer_instance.feature(aligned_face)

    norm = np.linalg.norm(feature)
    if norm > 1e-6:
        feature_norm = (feature / norm).flatten()
    else:
        feature_norm = feature.flatten()

    bbox = [int(actual_face[0]), int(actual_face[1]), int(actual_face[2]), int(actual_face[3])]
    score = float(actual_face[14])
    return feature_norm, aligned_face, bbox, score


def match_face(img_bgr: np.ndarray, threshold: float = DEFAULT_COSINE_THRESHOLD) -> tuple[str | None, float, list | None, float]:
    """Compara el rostro de la imagen con la base de embeddings precargada en memoria."""
    extracted = extract_face_feature(img_bgr)
    if extracted is None:
        return None, 0.0, None, 0.0

    feat, _, bbox, det_score = extracted
    with _face_lock:
        if not _embeddings_cache:
            return None, 0.0, bbox, 0.0

        scores = []
        for guest_code, face_list in _embeddings_cache.items():
            if not face_list:
                continue
            guest_max = max(float(np.dot(feat, np.array(f["embedding"], dtype=np.float32))) for f in face_list)
            scores.append((guest_code, guest_max))

    if not scores:
        return None, 0.0, bbox, 0.0

    scores.sort(key=lambda x: x[1], reverse=True)
    best_code, best_sim = scores[0]
    top2_sim = scores[1][1] if len(scores) > 1 else 0.0

    if best_sim >= threshold and (best_sim - top2_sim) >= MIN_AMBIGUITY_MARGIN:
        return best_code, best_sim, bbox, top2_sim

    return None, best_sim, bbox, top2_sim


def enroll_guest_face(guest: Guest, img_bgr: np.ndarray) -> tuple[bool, str, dict | None]:
    """Enrola una fotografía para un invitado, guardando el embedding y miniatura base64 directamente en MySQL (sin escribir en disco)."""
    init_face_service()
    extracted = extract_face_feature(img_bgr)
    if extracted is None:
        return False, "No se detectó un rostro claro en la imagen.", None

    feat, aligned, bbox, score = extracted

    # Codificar la miniatura alineada en base64 en memoria (cero archivos en disco)
    thumb_data = None
    try:
        _, enc_buf = cv2.imencode(".jpg", aligned, [cv2.IMWRITE_JPEG_QUALITY, 85])
        thumb_data = "data:image/jpeg;base64," + base64.b64encode(enc_buf).decode("ascii")
    except Exception as e:
        log.warning(f"No se pudo generar miniatura base64: {e}")

    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19]
    image_id = f"img_{ts_str}"
    raw_fname = f"{image_id}.jpg"
    thumb_fname = f"{image_id}_aligned.jpg"

    profile = FaceProfile(
        guest_id=guest.id,
        image_id=image_id,
        filename=raw_fname,
        thumb_filename=thumb_fname,
        thumb_data=thumb_data,
        embedding_json=json.dumps(feat.tolist()),
        quality_score=score,
    )
    db.session.add(profile)
    db.session.commit()

    with _face_lock:
        if guest.guest_code not in _embeddings_cache:
            _embeddings_cache[guest.guest_code] = []
        _embeddings_cache[guest.guest_code].append({
            "image_id": image_id,
            "filename": raw_fname,
            "thumb_filename": thumb_fname,
            "thumb_data": thumb_data,
            "embedding": feat.tolist(),
            "score": score,
        })

    return True, "Rostro enrolado correctamente.", profile.to_dict()


def delete_guest_face(guest: Guest, image_id: str | None = None) -> bool:
    """Elimina perfiles faciales de un invitado en MySQL y en memoria (sin archivos en disco)."""
    with _face_lock:
        query = FaceProfile.query.filter_by(guest_id=guest.id)
        if image_id:
            query = query.filter_by(image_id=image_id)
        profiles = query.all()

        for p in profiles:
            db.session.delete(p)

        db.session.commit()

        if guest.guest_code in _embeddings_cache:
            if image_id:
                _embeddings_cache[guest.guest_code] = [f for f in _embeddings_cache[guest.guest_code] if f["image_id"] != image_id]
                if not _embeddings_cache[guest.guest_code]:
                    del _embeddings_cache[guest.guest_code]
            else:
                del _embeddings_cache[guest.guest_code]

    return True


def delete_all_enrolled_faces() -> dict:
    """Elimina todas las fotos de enrolamiento en MySQL y resetea la memoria de IA."""
    global _embeddings_cache
    with _face_lock:
        count = FaceProfile.query.count()
        FaceProfile.query.delete()
        db.session.commit()
        _embeddings_cache = {}

        if Config.FACE_IMAGES_DIR.exists():
            for item in Config.FACE_IMAGES_DIR.iterdir():
                try:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    elif item.is_file() and not item.name.startswith("."):
                        item.unlink()
                except Exception as e:
                    pass
                    log.warning(f"Error limpiando {item.name}: {e}")

        log.info(f"Se eliminaron todas las fotos faciales de {count} perfiles.")
        return {"success": True, "deleted_count": count}


def get_enrolled_counts() -> dict[str, int]:
    """Retorna dict { guest_code: count } de rostros activos en memoria."""
    with _face_lock:
        return {code: len(faces) for code, faces in _embeddings_cache.items()}
