"""
composicion_deuda.py (transform)

Transforma las 3 hojas del Excel "Composicion_de_la_Deuda_sep-2025.xlsx"
(Ministerio de Hacienda) — Moneda, Acreedor, Legislación — de formato ancho
(categorías como filas, años como columnas) a listas de dataclasses en
formato largo, listas para persistir vía repositories/composicion_deuda.py.

Decisión de diseño (misma que en serie_historica_deuda.py): las dataclasses
de este módulo NO dependen de Django. El modelo Django es la entidad de
persistencia; estas son la entidad de transporte en memoria, para poder
testear/correr en notebook sin levantar toda la config de Django.

Consecuencia de esa decisión: el mapeo de categoría (texto del Excel -> 
valor de choice) está duplicado acá en vez de leerse desde el TextChoices
del modelo. Es la misma deuda técnica ya aceptada con FUENTE en el otro
dataset: si el modelo cambia una etiqueta, hay que actualizar este
diccionario a mano. No hay todavía una tercera fuente de verdad compartida.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from data_engine.services.transform.common import (
    derretir_ancho_a_largo,
    parsear_monto_con_guion,
    resolver_anio_y_fecha,
)

FUENTE = "hacienda_composicion_deuda"  # debe coincidir EXACTO con el default en los 3 modelos

# Tolerancia al validar la suma de categorías contra la fila Total/Deuda
# Total del Excel. Necesaria porque en 2005-2009 Hacienda publicó ese total
# redondeado a entero mientras las categorías traen decimales completos
# (confirmado explorando el archivo real) -- no es un error del pipeline,
# es una inconsistencia de la fuente.
TOLERANCIA_VALIDACION_TOTAL = Decimal("2.0")


@dataclass
class RegistroComposicionDeudaMoneda:
    anio: int
    fecha_corte: date
    categoria: str
    monto_millones: Decimal
    es_corte_parcial: bool
    fuente: str = FUENTE


@dataclass
class RegistroComposicionDeudaAcreedor:
    anio: int
    fecha_corte: date
    categoria: str
    monto_millones: Decimal
    es_corte_parcial: bool
    fuente: str = FUENTE


@dataclass
class RegistroComposicionDeudaLegislacion:
    anio: int
    fecha_corte: date
    categoria: str
    monto_millones: Decimal
    es_corte_parcial: bool
    fuente: str = FUENTE


# Mapeo etiqueta EXACTA del Excel -> valor de categoria a persistir.
# Debe mantenerse sincronizado a mano con el TextChoices de cada modelo.
_CATEGORIAS_MONEDA = {
    "Dólares USA": "dolares_usa",
    "Unidades de Fomento Chile": "uf",
    "Pesos": "pesos",
    "Unidad de Cuenta BID": "unidad_cuenta_bid",
    "Unidad de Canasta BIRF": "unidad_canasta_birf",
    "Yen Japonés": "yen_japones",
    "Euros": "euros",
    "Marco Alemán": "marco_aleman",
    "Otras": "otras",
}

_CATEGORIAS_ACREEDOR = {
    "Banco Central de Chile": "banco_central_chile",
    "Banco Internacional de Reconstrucción y Fomento (BIRF)": "birf",
    "Banco Interamericano de Desarrollo (BID)": "bid",
    "Bonos": "bonos",
    "Eximbank Japón": "eximbank_japon",
    "BancoEstado de Chile": "bancoestado_chile",
    "Agencia Internacional de Desarrollo (AID)": "aid",
    "Otros": "otros",
}

_CATEGORIAS_LEGISLACION = {
    "Deuda Interna": "deuda_interna",
    "Deuda Externa": "deuda_externa",
}


def _validar_contra_total(df_categorias, fila_total, tolerancia=TOLERANCIA_VALIDACION_TOTAL):
    """Compara, columna por columna (cada columna es un período), la suma
    de todas las categorías contra la fila Total/Deuda Total del Excel.
    Lanza ValueError solo si la diferencia supera la tolerancia conocida."""
    for columna in df_categorias.columns[1:]:
        suma = sum(parsear_monto_con_guion(v) for v in df_categorias[columna])
        total = parsear_monto_con_guion(fila_total[columna])
        diferencia = abs(suma - total)
        if diferencia > tolerancia:
            raise ValueError(
                f"Suma de categorías no calza con el total en columna {columna!r}: "
                f"suma={suma}, total={total}, diferencia={diferencia}"
            )


def _transformar_hoja(path_excel, nombre_hoja, nombre_fila_total, mapeo_categorias, registro_cls):
    """Motor genérico compartido por las 3 hojas: lee la hoja, separa y
    valida su fila de total, convierte a formato largo, y arma la lista de
    dataclasses. Lo único que varía por hoja se recibe como parámetro."""
    df = pd.read_excel(path_excel, sheet_name=nombre_hoja, header=0)

    es_total = df[df.columns[0]] == nombre_fila_total
    fila_total = df[es_total].iloc[0]
    df_categorias = df[~es_total]

    _validar_contra_total(df_categorias, fila_total)

    largo = derretir_ancho_a_largo(df_categorias)

    registros = []
    for _, fila in largo.iterrows():
        etiqueta = fila["categoria"]
        if etiqueta not in mapeo_categorias:
            raise ValueError(f"Categoría no reconocida en hoja {nombre_hoja!r}: {etiqueta!r}")

        anio, fecha_corte, es_corte_parcial = resolver_anio_y_fecha(fila["periodo_raw"])
        registros.append(
            registro_cls(
                anio=anio,
                fecha_corte=fecha_corte,
                categoria=mapeo_categorias[etiqueta],
                monto_millones=parsear_monto_con_guion(fila["valor_raw"]),
                es_corte_parcial=es_corte_parcial,
            )
        )
    return registros


def transformar_moneda(path_excel) -> list[RegistroComposicionDeudaMoneda]:
    return _transformar_hoja(
        path_excel, "Moneda", "Total", _CATEGORIAS_MONEDA, RegistroComposicionDeudaMoneda
    )


def transformar_acreedor(path_excel) -> list[RegistroComposicionDeudaAcreedor]:
    return _transformar_hoja(
        path_excel, "Acreedor", "Deuda Total", _CATEGORIAS_ACREEDOR, RegistroComposicionDeudaAcreedor
    )


def transformar_legislacion(path_excel) -> list[RegistroComposicionDeudaLegislacion]:
    return _transformar_hoja(
        path_excel, "Legislación", "Deuda Total", _CATEGORIAS_LEGISLACION, RegistroComposicionDeudaLegislacion
    )