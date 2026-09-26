import logging
from decimal import Decimal, ROUND_HALF_UP

from data_engine.models.bono_externo import BonoExterno
from data_engine.services.transform.bono_externo import RegistroBonoExterno, FUENTE

logger = logging.getLogger(__name__)

_CAMPOS_DECIMAL = [
    "monto", "tasa_caratula_fija", "tasa_bono_tesoro",
    "tasa_local_tesoro_chile", "precio", "yield_emision", "spread_caratula",
]
_CAMPOS_A_COMPARAR = _CAMPOS_DECIMAL + [
    "fecha_vencimiento", "es_reapertura", "moneda", "tasa_caratula_raw",
    "spread_nota_referencia", "pago_intereses", "vigencia",
]


def _cuantizar(valor: Decimal, decimal_places: int) -> Decimal:
    exponente = Decimal(1).scaleb(-decimal_places)
    return valor.quantize(exponente, rounding=ROUND_HALF_UP)


def _valor_normalizado(instancia_o_registro, campo: str, decimal_places_por_campo: dict):
    valor = getattr(instancia_o_registro, campo)
    if campo in _CAMPOS_DECIMAL and valor is not None:
        return _cuantizar(valor, decimal_places_por_campo[campo])
    return valor


def _detectar_cambios(instancia: BonoExterno, registro: RegistroBonoExterno) -> dict:
    decimal_places_por_campo = {
        campo: instancia._meta.get_field(campo).decimal_places for campo in _CAMPOS_DECIMAL
    }
    cambios = {}
    for campo in _CAMPOS_A_COMPARAR:
        valor_actual = getattr(instancia, campo)
        valor_nuevo = _valor_normalizado(registro, campo, decimal_places_por_campo)
        if valor_actual != valor_nuevo:
            cambios[campo] = (valor_actual, valor_nuevo)
    return cambios


def guardar(registros: list[RegistroBonoExterno]) -> dict:
    creados = 0
    actualizados = 0
    sin_cambios = 0

    decimal_places_por_campo = {
        campo: BonoExterno._meta.get_field(campo).decimal_places for campo in _CAMPOS_DECIMAL
    }

    for registro in registros:
        defaults = {
            campo: _valor_normalizado(registro, campo, decimal_places_por_campo)
            for campo in _CAMPOS_A_COMPARAR
        }
        defaults["fuente"] = FUENTE

        instancia, fue_creado = BonoExterno.objects.get_or_create(
            nombre_bono=registro.nombre_bono,
            fecha_emision=registro.fecha_emision,
            defaults=defaults,
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
                "Cambio detectado en BonoExterno (%s, %s): %s",
                registro.nombre_bono, registro.fecha_emision, cambios,
            )
        else:
            sin_cambios += 1

    return {"creados": creados, "actualizados": actualizados, "sin_cambios": sin_cambios}