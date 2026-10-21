import logging
import re
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from data_engine.models.estado_operaciones_gobierno_central import (
    CONCEPTO_BALANCE,
    CONCEPTO_TOTAL_GASTOS,
    CONCEPTO_TOTAL_INGRESOS,
    UnidadEstadoOperaciones as Unidad,
)

logger = logging.getLogger(__name__)

SEIS_DECIMALES = Decimal("0.000001")
ESPACIOS_POR_NIVEL = 4


def _identificar_unidad(texto):
    """La celda A5 dice la unidad del archivo. Devuelve (unidad, anio_base)."""
    t = str(texto).strip()
    if t == "Porcentaje del PIB":
        return Unidad.PCT_PIB, None
    m = re.fullmatch(r"Millones de pesos de (\d{4})", t)
    if m:
        return Unidad.REAL, int(m.group(1))
    if t == "Millones de pesos":
        return Unidad.NOMINAL, None
    raise ValueError(f"Unidad no reconocida en la celda A5: {texto!r}")


def _a_decimal(valor):
    if pd.isna(valor):
        return None
    return Decimal(str(valor)).quantize(SEIS_DECIMALES, rounding=ROUND_HALF_UP)


def leer_archivo(ruta):
    """Un Excel GCT de la DIPRES -> lista de dicts (una fila por año y concepto)."""
    crudo = pd.read_excel(ruta, sheet_name=0, header=None)
    unidad, anio_base = _identificar_unidad(crudo.iat[4, 0])

    # Fila de los años: la que tiene 1990 en la columna B
    fila_anios = crudo.index[pd.to_numeric(crudo[1], errors="coerce") == 1990][0]
    columnas_anio = {
        col: int(anio)
        for col, anio in crudo.loc[fila_anios, 1:].items()
        if pd.notna(anio)
    }

    registros, pila, orden = [], [], 0
    for i in range(fila_anios + 1, len(crudo)):
        nombre_crudo = crudo.iat[i, 0]
        if not isinstance(nombre_crudo, str) or not nombre_crudo.strip():
            continue
        valores = pd.to_numeric(crudo.loc[i, list(columnas_anio)], errors="coerce")
        if valores.isna().all():
            continue   # título de sección, sin cifras

        # La jerarquía viene en la sangría: 4 espacios por nivel
        sangria = len(nombre_crudo) - len(nombre_crudo.lstrip(" "))
        nivel = sangria // ESPACIOS_POR_NIVEL
        nombre = nombre_crudo.strip()
        while pila and pila[-1][0] >= nivel:
            pila.pop()
        concepto = " > ".join([p[1] for p in pila] + [nombre])
        pila.append((nivel, nombre))
        orden += 1

        for col, anio in columnas_anio.items():
            registros.append({
                "anio": anio,
                "concepto": concepto,
                "nombre": nombre,
                "nivel": nivel,
                "orden": orden,
                "unidad": unidad,
                "anio_base": anio_base,
                "valor": _a_decimal(valores[col]),
            })

    return registros


def _validar(registros):
    """Control de calidad: total ingresos - total gastos = balance, en cada año y unidad.
    Avisa con warning en vez de detener la ingesta."""
    por_unidad = defaultdict(dict)
    for r in registros:
        if r["valor"] is not None:
            por_unidad[r["unidad"]][(r["anio"], r["concepto"])] = float(r["valor"])

    for unidad, datos in por_unidad.items():
        tolerancia = 0.01 if unidad == Unidad.PCT_PIB else 1.0   # pct vs millones de pesos
        anios = sorted({anio for anio, _ in datos})
        for anio in anios:
            try:
                diferencia = (
                    datos[(anio, CONCEPTO_TOTAL_INGRESOS)]
                    - datos[(anio, CONCEPTO_TOTAL_GASTOS)]
                    - datos[(anio, CONCEPTO_BALANCE)]
                )
            except KeyError as faltante:
                logger.warning("Falta %s en %s %s", faltante, unidad, anio)
                continue
            if abs(diferencia) > tolerancia:
                logger.warning(
                    "El balance no cuadra en %s %s: diferencia %.4f", unidad, anio, diferencia
                )


def transformar(rutas):
    """Varios Excel GCT (uno por unidad) -> lista única de registros validados."""
    registros, unidades_vistas = [], {}
    for ruta in rutas:
        del_archivo = leer_archivo(ruta)
        unidad = del_archivo[0]["unidad"]
        if unidad in unidades_vistas:
            raise ValueError(
                f"Dos archivos con la misma unidad ({unidad}): "
                f"{unidades_vistas[unidad].name} y {ruta.name}"
            )
        unidades_vistas[unidad] = ruta
        registros.extend(del_archivo)

    _validar(registros)
    return registros