from datetime import date
from decimal import ROUND_HALF_UP, Decimal

DOS_DECIMALES = Decimal("0.01")


def _parsear_fecha(texto):
    """mindicador entrega la medianoche de Chile expresada en UTC
    (ej. '2025-12-31T03:00:00.000Z' o T04 en horario de invierno).
    Como 03:00/04:00 UTC sigue siendo el mismo día, los primeros 10 caracteres
    son la fecha correcta. Es más simple que convertir zonas horarias."""
    return date.fromisoformat(texto[:10])


def transformar(respuestas, indicador):
    """respuestas: lista de JSON anuales de mindicador -> lista de dicts listos para el repository.
    Se usa un dict por fecha para descartar duplicados si la fuente repite un día."""
    por_fecha = {}
    for respuesta in respuestas:
        for obs in respuesta.get("serie", []):
            fecha = _parsear_fecha(obs["fecha"])
            valor = Decimal(str(obs["valor"])).quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
            por_fecha[fecha] = valor

    return [
        {"indicador": indicador, "fecha": fecha, "valor": valor}
        for fecha, valor in sorted(por_fecha.items())
    ]