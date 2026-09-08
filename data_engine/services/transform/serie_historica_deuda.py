"""
serie_historica_deuda.py

Transformador específico para el dataset "Series Históricas de Deuda" 
(Ministerio de Hacienda). Convierte el Excel de origen (2 hojas, formato
ancho por año) en una lista de registros en formato largo, listos para
el modelo SerieHistoricaDeuda.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal
from datetime import date
from typing import Any

import pandas as pd

from data_engine.services.transform.common import (
    parsear_monto,
    parsear_decimal_simple,
    resolver_anio_y_fecha,
)

FUENTE = "hacienda_series_historicas_deuda"

# Columnas de la hoja "Deuda US$" (sin las 2 filas de header, por posición)
_COLS_USD = ["anio_raw", "bruta_monto", "bruta_pct_pib", "neta_monto", "neta_pct_pib"]

# Columnas de la hoja "Deuda Pesos" (sin %PIB — se completa desde la hoja USD)
_COLS_CLP = ["anio_raw", "bruta_monto", "neta_monto"]


@dataclass
class RegistroSerieHistoricaDeuda:
    anio: int
    fecha_corte: date
    tipo_deuda: str  # "bruta" | "neta"
    moneda: str  # "usd" | "clp"
    monto_millones: Decimal
    pct_pib: Decimal | None
    es_corte_parcial: bool
    fuente: str = FUENTE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _leer_hoja_usd(path_excel: str) -> pd.DataFrame:
    df = pd.read_excel(path_excel, sheet_name="Deuda US$", header=None, skiprows=2)
    df.columns = _COLS_USD
    return df


def _leer_hoja_clp(path_excel: str) -> pd.DataFrame:
    df = pd.read_excel(path_excel, sheet_name="Deuda Pesos", header=None, skiprows=2)
    df.columns = _COLS_CLP
    return df


def transformar(path_excel: str) -> list[RegistroSerieHistoricaDeuda]:
    """
    Punto de entrada del módulo. Lee el Excel de Series Históricas de
    Deuda y devuelve la lista de registros en formato largo, listos para
    ser persistidos por el repository correspondiente.
    """
    df_usd = _leer_hoja_usd(path_excel)
    df_clp = _leer_hoja_clp(path_excel)

    if len(df_usd) != len(df_clp):
        raise ValueError(
            f"Las hojas USD ({len(df_usd)} filas) y CLP ({len(df_clp)} filas) "
            "no tienen la misma cantidad de filas de datos; revisar el Excel."
        )

    registros: list[RegistroSerieHistoricaDeuda] = []

    for i, (fila_usd, fila_clp) in enumerate(
        zip(df_usd.itertuples(index=False), df_clp.itertuples(index=False))
    ):
        anio, fecha_corte, es_parcial = resolver_anio_y_fecha(fila_usd.anio_raw)
        anio_clp, _, _ = resolver_anio_y_fecha(fila_clp.anio_raw)

        if anio != anio_clp:
            raise ValueError(
                f"Desalineación entre hojas en la posición {i}: "
                f"USD trae año {anio}, CLP trae año {anio_clp}. "
                "Las hojas no están en el mismo orden; revisar el Excel "
                "antes de continuar (no se procesan datos parcialmente)."
            )

        # --- Deuda Bruta ---
        pct_pib_bruta = parsear_decimal_simple(fila_usd.bruta_pct_pib)

        registros.append(RegistroSerieHistoricaDeuda(
            anio=anio, fecha_corte=fecha_corte, tipo_deuda="bruta", moneda="usd",
            monto_millones=parsear_monto(fila_usd.bruta_monto),
            pct_pib=pct_pib_bruta, es_corte_parcial=es_parcial,
        ))
        registros.append(RegistroSerieHistoricaDeuda(
            anio=anio, fecha_corte=fecha_corte, tipo_deuda="bruta", moneda="clp",
            monto_millones=parsear_monto(fila_clp.bruta_monto),
            pct_pib=pct_pib_bruta, es_corte_parcial=es_parcial,
        ))

        # --- Deuda Neta ---
        pct_pib_neta = parsear_decimal_simple(fila_usd.neta_pct_pib)

        registros.append(RegistroSerieHistoricaDeuda(
            anio=anio, fecha_corte=fecha_corte, tipo_deuda="neta", moneda="usd",
            monto_millones=parsear_monto(fila_usd.neta_monto),
            pct_pib=pct_pib_neta, es_corte_parcial=es_parcial,
        ))
        registros.append(RegistroSerieHistoricaDeuda(
            anio=anio, fecha_corte=fecha_corte, tipo_deuda="neta", moneda="clp",
            monto_millones=parsear_monto(fila_clp.neta_monto),
            pct_pib=pct_pib_neta, es_corte_parcial=es_parcial,
        ))

    return registros