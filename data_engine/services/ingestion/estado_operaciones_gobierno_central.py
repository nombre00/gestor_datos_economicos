import logging
from pathlib import Path

from django.conf import settings

from data_engine.repositories.estado_operaciones_gobierno_central import guardar
from data_engine.services.transform.estado_operaciones_gobierno_central import transformar

logger = logging.getLogger(__name__)

PATRON_ARCHIVOS = "Estado Operaciones Gobierno Central Total*.xlsx"


def ingerir(carpeta=None):
    carpeta = Path(carpeta) if carpeta else Path(settings.BASE_DIR).parent / "datasets" / "raw"
    rutas = sorted(carpeta.glob(PATRON_ARCHIVOS))
    if not rutas:
        raise FileNotFoundError(f"No hay archivos '{PATRON_ARCHIVOS}' en {carpeta}")

    logger.info("Archivos: %s", [r.name for r in rutas])
    registros = transformar(rutas)
    resumen = guardar(registros)
    logger.info("Estado de Operaciones GCT: %s", resumen)
    return resumen