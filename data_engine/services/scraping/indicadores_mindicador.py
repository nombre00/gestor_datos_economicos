import json
import logging
import time
from datetime import date
from pathlib import Path

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

URL_BASE = "https://mindicador.cl/api"
CARPETA_CRUDOS = Path(settings.BASE_DIR).parent / "datasets" / "raw" / "indicadores"


def obtener_serie_anual(indicador, anio, intentos=5, timeout=60):
    """Pide un año completo de un indicador directamente a la API.
    Reintenta con espera creciente porque la API a veces responde muy lento."""
    url = f"{URL_BASE}/{indicador}/{anio}"
    for intento in range(1, intentos + 1):
        try:
            respuesta = requests.get(url, timeout=timeout)
            respuesta.raise_for_status()
            return respuesta.json()
        except requests.RequestException as error:
            if intento == intentos:
                raise
            espera = 3 * intento
            logger.warning(
                "Falló %s (intento %s/%s): %s. Reintentando en %ss",
                url, intento, intentos, error, espera,
            )
            time.sleep(espera)


def _ruta_crudo(indicador, anio):
    """Los años cerrados se guardan como 'uf_2025.json'. El año en curso se guarda
    como 'uf_2026_parcial.json' porque todavía le faltan días: así, cuando el año
    termine, ese archivo no se confunde con uno completo y se vuelve a descargar."""
    if anio < date.today().year:
        return CARPETA_CRUDOS / f"{indicador}_{anio}.json"
    return CARPETA_CRUDOS / f"{indicador}_{anio}_parcial.json"


def obtener_serie_anual_con_copia_local(indicador, anio):
    """Si el año está cerrado y ya tenemos su archivo, lo lee del disco sin consultar
    la API. Si no, lo pide a la API y guarda la respuesta cruda.
    Devuelve (datos, consulto_api)."""
    ruta = _ruta_crudo(indicador, anio)
    anio_cerrado = anio < date.today().year

    if anio_cerrado and ruta.exists():
        return json.loads(ruta.read_text(encoding="utf-8")), False

    datos = obtener_serie_anual(indicador, anio)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    return datos, True


def obtener_series(indicador, anio_desde, anio_hasta, pausa=1.0):
    """Recorre los años usando la copia local cuando existe.
    Solo hace pausa cuando realmente consultó la API."""
    respuestas = []
    for anio in range(anio_desde, anio_hasta + 1):
        datos, consulto_api = obtener_serie_anual_con_copia_local(indicador, anio)
        respuestas.append(datos)
        if consulto_api:
            time.sleep(pausa)
    return respuestas