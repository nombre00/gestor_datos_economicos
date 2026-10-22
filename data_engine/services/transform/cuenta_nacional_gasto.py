import logging
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from data_engine.models.cuenta_nacional_gasto import (
    CLAVE_DEMANDA_INTERNA,
    CLAVE_EXPORTACIONES,
    CLAVE_IMPORTACIONES,
    CLAVE_PIB,
    MedidaCuentaNacional as Medida,
)

logger = logging.getLogger(__name__)

SEIS_DECIMALES = Decimal("0.000001")
ESPACIOS_POR_NIVEL = 3
MEDIDA_POR_LETRA = {"N": Medida.NOMINAL, "R": Medida.REAL}

# Nombres que no sirven para ambas medidas tal como vienen en el nominal
NOMBRES_FIJOS = {CLAVE_PIB: "Producto Interno Bruto"}   # el nominal dice "PIB a precios corrientes"


def _a_decimal(valor):
    if pd.isna(valor):
        return None
    return Decimal(str(valor)).quantize(SEIS_DECIMALES, rounding=ROUND_HALF_UP)


def _medida_del_codigo(codigo):
    """F033.COG.FLU.N.CLP.EP18.0.T -> la 4.a parte es N (nominal) o R (real)."""
    letra = codigo.split(".")[3]
    if letra not in MEDIDA_POR_LETRA:
        raise ValueError(f"Medida no reconocida en el código {codigo!r}")
    return MEDIDA_POR_LETRA[letra]


def leer_archivo(ruta):
    """Un Excel de la BDE (Gasto del PIB, anual) -> lista de dicts (una fila por año y serie)."""
    cuadro = pd.read_excel(ruta, sheet_name="Cuadro", header=2)
    series = pd.read_excel(ruta, sheet_name="Series")

    cuadro = cuadro.dropna(subset=["Reg"]).reset_index(drop=True)
    if len(cuadro) != len(series):
        raise ValueError(
            f"{ruta.name}: {len(cuadro)} filas en Cuadro vs {len(series)} en Series"
        )

    # Columnas de años. Si vienen trimestres (varias fechas en un mismo año), lo rechazamos:
    # este modelo guarda solo datos anuales.
    columnas_anio = [c for c in cuadro.columns if hasattr(c, "year")]
    anios = [c.year for c in columnas_anio]
    if len(set(anios)) != len(anios):
        raise ValueError(
            f"{ruta.name}: hay años repetidos en las columnas; ¿se exportó trimestral en vez de anual?"
        )

    registros = []
    for orden, (i, fila) in enumerate(cuadro.iterrows()):
        codigo = str(series.at[i, "Serie"]).strip()
        nombre_crudo = str(fila["Descripción series"]).replace("\xa0", " ")
        nivel = (len(nombre_crudo) - len(nombre_crudo.lstrip())) // ESPACIOS_POR_NIVEL

        for col in columnas_anio:
            registros.append({
                "anio": col.year,
                "codigo": codigo,
                "clave": codigo.split(".")[1],
                "medida": _medida_del_codigo(codigo),
                "nombre": nombre_crudo.strip(),
                "nivel": nivel,
                "orden": orden,
                "valor": _a_decimal(fila[col]),
            })

    return registros


def _homologar_nombres(registros):
    """Nominal y real escriben algunos nombres distinto ("Exportación Servicios" vs
    "Exportación servicios"). Usamos nombre, nivel y orden del nominal para ambas medidas,
    emparejando por clave. Si una clave solo existe en el real, conserva lo suyo.
    NOMBRES_FIJOS corrige los pocos nombres del nominal que mencionan la medida."""
    catalogo = {
        r["clave"]: (r["nombre"], r["nivel"], r["orden"])
        for r in registros
        if r["medida"] == Medida.NOMINAL
    }
    for r in registros:
        if r["clave"] in catalogo:
            r["nombre"], r["nivel"], r["orden"] = catalogo[r["clave"]]
        r["nombre"] = NOMBRES_FIJOS.get(r["clave"], r["nombre"])


def _validar(registros):
    """Control de calidad (solo nominal): demanda interna + exportaciones - importaciones = PIB.
    En la medida real no se valida: el volumen encadenado no es aditivo."""
    datos = defaultdict(dict)
    for r in registros:
        if r["medida"] == Medida.NOMINAL and r["valor"] is not None:
            datos[r["anio"]][r["clave"]] = float(r["valor"])

    tolerancia = 1.0   # miles de millones de pesos
    for anio in sorted(datos):
        d = datos[anio]
        try:
            diferencia = (
                d[CLAVE_DEMANDA_INTERNA] + d[CLAVE_EXPORTACIONES]
                - d[CLAVE_IMPORTACIONES] - d[CLAVE_PIB]
            )
        except KeyError as faltante:
            logger.warning("Falta la serie %s en %s", faltante, anio)
            continue
        if abs(diferencia) > tolerancia:
            logger.warning("La identidad del gasto no cuadra en %s: diferencia %.4f", anio, diferencia)


def transformar(rutas):
    """Los Excel del gasto del PIB (uno nominal y uno real) -> lista única de registros."""
    registros, medidas_vistas = [], {}
    for ruta in rutas:
        del_archivo = leer_archivo(ruta)
        medidas = {r["medida"] for r in del_archivo}
        if len(medidas) != 1:
            raise ValueError(f"{ruta.name} mezcla medidas: {medidas}")
        medida = medidas.pop()
        if medida in medidas_vistas:
            raise ValueError(
                f"Dos archivos con la misma medida ({medida}): "
                f"{medidas_vistas[medida].name} y {ruta.name}"
            )
        medidas_vistas[medida] = ruta
        registros.extend(del_archivo)

    _homologar_nombres(registros)
    _validar(registros)
    return registros