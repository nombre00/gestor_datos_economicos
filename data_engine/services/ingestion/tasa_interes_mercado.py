import logging
from pathlib import Path

from django.conf import settings

from data_engine.repositories.tasa_interes_mercado import guardar
from data_engine.services.transform.tasa_interes_mercado import transformar

logger = logging.getLogger(__name__)

PATRONES_ARCHIVOS = [
    "BCCh Tasas bonos*.xlsx",
    "BCCh TPM*.xlsx",
    "BCCh Tasas PRC*.xlsx",
    "BCCh Tasas captacion*.xlsx",
]


def ingerir(carpeta=None):
    carpeta = Path(carpeta) if carpeta else Path(settings.BASE_DIR).parent / "datasets" / "raw"
    rutas = [ruta for patron in PATRONES_ARCHIVOS for ruta in sorted(carpeta.glob(patron))]
    if not rutas:
        raise FileNotFoundError(f"No hay archivos {PATRONES_ARCHIVOS} en {carpeta}")

    logger.info("Archivos: %s", [r.name for r in rutas])
    registros = transformar(rutas)
    resumen = guardar(registros)
    logger.info("Tasas de interés (BCCh): %s", resumen)
    return resumen