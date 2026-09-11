import logging
from decimal import Decimal, ROUND_HALF_UP

from data_engine.models.stock_titulo_deuda import StockTituloDeuda
from data_engine.services.transform.stock_titulo_deuda import RegistroStockTituloDeuda, FUENTE

logger = logging.getLogger(__name__)

_CAMPOS_A_COMPARAR = ["monto_miles_millones_clp"]


def _cuantizar(valor: Decimal, decimal_places: int) -> Decimal:
    exponente = Decimal(1).scaleb(-decimal_places)
    return valor.quantize(exponente, rounding=ROUND_HALF_UP)


def _detectar_cambios(instancia: StockTituloDeuda, registro: RegistroStockTituloDeuda) -> dict:
    cambios = {}
    for campo in _CAMPOS_A_COMPARAR:
        valor_actual = getattr(instancia, campo)
        decimal_places = instancia._meta.get_field(campo).decimal_places
        valor_nuevo_normalizado = _cuantizar(getattr(registro, campo), decimal_places)
        if valor_actual != valor_nuevo_normalizado:
            cambios[campo] = (valor_actual, valor_nuevo_normalizado)
    return cambios


def guardar(registros: list[RegistroStockTituloDeuda]) -> dict:
    creados = 0
    actualizados = 0
    sin_cambios = 0

    decimal_places = StockTituloDeuda._meta.get_field("monto_miles_millones_clp").decimal_places

    for registro in registros:
        monto_cuantizado = _cuantizar(registro.monto_miles_millones_clp, decimal_places)

        instancia, fue_creado = StockTituloDeuda.objects.get_or_create(
            instrumento=registro.instrumento,
            tenedor=registro.tenedor,
            tipo_fila=registro.tipo_fila,
            anio=registro.anio,
            trimestre=registro.trimestre,
            defaults={
                "fecha_corte": registro.fecha_corte,
                "monto_miles_millones_clp": monto_cuantizado,
                "fuente": FUENTE,
            },
        )

        if fue_creado:
            creados += 1
            continue

        cambios = _detectar_cambios(instancia, registro)
        if cambios:
            for campo, (_antes, despues) in cambios.items():
                setattr(instancia, campo, despues)
            instancia.save()
            actualizados += 1
            logger.warning(
                "Cambio detectado en StockTituloDeuda (%s, %s, %s, %s-T%s): %s",
                registro.instrumento, registro.tenedor, registro.tipo_fila,
                registro.anio, registro.trimestre, cambios,
            )
        else:
            sin_cambios += 1

    return {"creados": creados, "actualizados": actualizados, "sin_cambios": sin_cambios}