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


def parsear_monto_con_guion(valor):
    """Parsea un monto que puede venir como '-' (sin deuda reportada en esa
    categoría/período — confirmado que se comporta como 0 en las sumas de
    validación contra la fila Total del Excel) o como un número normal.

    A diferencia de parsear_monto(), este NO maneja separadores de miles ni
    espacios non-breaking: ese dataset (Composición de la Deuda) no los
    tiene. Si algún día aparecieran, se prefiere que esto falle explícito
    en vez de intentar adivinar un formato no confirmado."""
    if isinstance(valor, str) and valor.strip() == "-":
        return Decimal("0")
    return parsear_decimal_simple(valor)


def derretir_ancho_a_largo(df, columna_categoria="categoria"):
    """Convierte un DataFrame en formato ancho (una fila por categoría,
    columnas = períodos) a formato largo (una fila por observación).

    Asume que la primera columna del DataFrame trae las categorías (nombres
    de fila, ej. 'Dólares USA', 'Banco Central de Chile') y todas las demás
    columnas son períodos — años como int, o un Timestamp para el corte
    parcial (mismo patrón que ya manejas en resolver_anio_y_fecha, aplicable
    aquí sin cambios porque la señal datetime-vs-int es la misma, solo que
    ahora vive en el nombre de columna en vez de en una celda).

    No excluye ninguna fila (ej. 'Total') ni convierte los valores todavía —
    esa interpretación específica del dataset queda para quien llama."""
    df = df.rename(columns={df.columns[0]: columna_categoria})
    return df.melt(
        id_vars=[columna_categoria],
        var_name="periodo_raw",
        value_name="valor_raw",
    )