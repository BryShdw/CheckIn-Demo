# config.py
# ─────────────────────────────────────────────────────────────────────────────
# Configuración del sistema de registro con enlace compartido de Microsoft OneDrive
#
# CÓMO CONFIGURAR TU ENLACE DE ONEDRIVE:
#   1. Sube tu archivo 'guests.csv' a tu OneDrive (web o app).
#   2. Haz clic derecho en el archivo -> "Compartir" (Share).
#   3. Asegúrate de seleccionar "Cualquier persona que tenga el vínculo puede ver"
#      (o "Cualquier persona con el enlace").
#   4. Copia el vínculo generado.
#   5. Pégalo aquí abajo en ONEDRIVE_SHARED_URL.
#
# Si dejas la URL vacía (""), el sistema funcionará en modo offline usando
# automáticamente el archivo local 'guests.csv' como respaldo.
# ─────────────────────────────────────────────────────────────────────────────

# Enlace compartido público/de lectura de OneDrive para guests.csv (dejar vacío para configurar desde /admin o usar offline)
ONEDRIVE_SHARED_URL = ""


# Archivo de cache local: copia guardada tras la última descarga exitosa de OneDrive
LOCAL_CACHE_CSV = "guests_cache.csv"

# Archivo CSV local de respaldo (usado si no hay internet o no hay URL configurada)
LOCAL_FALLBACK_CSV = "guests.csv"

# Nombre del evento (aparece en la etiqueta impresa en la QL-800)
EVENT_NAME = "EVENTO DEMO 2026"
