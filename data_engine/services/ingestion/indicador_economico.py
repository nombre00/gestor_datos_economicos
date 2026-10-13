import logging
from datetime import date

from data_engine.repositories.indicador_economico import guardar
from data_engine.services.scraping.indicadores_mindicador import obtener_series
from data_engine.services.transform.indicador_economico import transformar

logger = logging.getLogger(__name__)

# Primer año disponible en mindicador para cada indicador
ANIO_INICIO = {"uf": 1977, "dolar": 1984, "euro": 1999}


def ingerir(indicadores=None, anio_desde=None, anio_hasta=None):
    """Sin argumentos: carga histórica completa de los 3 indicadores.
    Para actualizar solo lo reciente: ingerir(anio_desde=date.today().year)."""
    anio_hasta = anio_hasta or date.today().year
    resumen_total = {}

    for indicador in indicadores or ANIO_INICIO:
        desde = anio_desde or ANIO_INICIO[indicador]
        respuestas = obtener_series(indicador, desde, anio_hasta)
        registros = transformar(respuestas, indicador)
        resumen = guardar(registros)
        logger.info("%s: %s", indicador, resumen)
        resumen_total[indicador] = resumen

    return resumen_total