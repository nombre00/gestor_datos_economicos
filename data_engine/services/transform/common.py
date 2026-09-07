"""
common.py

Utilidades de parseo defensivo compartidas entre los distintos
transformadores de dataset. Pensado para crecer a medida que se
detecten patrones repetidos entre fuentes (ej. separador de miles
chileno, espacios non-breaking, nulos representados como '-', BOM
UTF-8, etc.) — no depende de ningún dataset en particular.
"""

from __future__ import annotations

import datetime
import re
from decimal import Decimal, InvalidOperation
from typing import Any


def parsear_monto(valor: Any) -> Decimal:
    """
    Convierte un valor de celda a Decimal, cubriendo variantes de
    formato numérico chileno mal serializado, ej:
    '\xa0\xa0\xa0\xa0-8.800.209' (espacios non-breaking + punto como
    separador de miles).
    """
    if isinstance(valor, (int, float)):
        # openpyxl ya entrega numérico limpio en la mayoría de los casos
        return Decimal(str(valor))

    if isinstance(valor, str):
        limpio = valor.replace("\xa0", "").strip()
        # Quita puntos usados como separador de miles: '-8.800.209' -> '-8800209'
        limpio = re.sub(r"(?<=\d)\.(?=\d{3}(\D|$))", "", limpio)
        try:
            return Decimal(limpio)
        except InvalidOperation as exc:
            raise ValueError(
                f"No se pudo parsear el monto: valor original={valor!r}, "
                f"limpio={limpio!r}"
            ) from exc

    raise TypeError(f"Tipo de dato inesperado para monto: {type(valor)} ({valor!r})")


def parsear_decimal_simple(valor: Any) -> Decimal:
    """Normaliza un float/int limpio (ej. % PIB) a Decimal, sin lógica
    defensiva adicional — para columnas que no presentan el problema
    de formato chileno."""
    return Decimal(str(valor))


def es_fila_parcial(valor_periodo: Any) -> bool:
    """
    Señal genérica para distinguir un corte parcial (fecha completa)
    de un período cerrado (ej. solo el año como int): True si la celda
    viene como datetime/date en vez de int.
    """
    return isinstance(valor_periodo, (datetime.datetime, datetime.date))


def resolver_anio_y_fecha(valor_periodo: Any) -> tuple[int, datetime.date, bool]:
    """Devuelve (anio, fecha_corte, es_corte_parcial) a partir del valor
    crudo de una columna de período, sea int (año cerrado) o datetime
    (corte parcial)."""
    if es_fila_parcial(valor_periodo):
        fecha = (
            valor_periodo.date()
            if isinstance(valor_periodo, datetime.datetime)
            else valor_periodo
        )
        return fecha.year, fecha, True

    anio = int(valor_periodo)
    fecha = datetime.date(anio, 12, 31)
    return anio, fecha, False