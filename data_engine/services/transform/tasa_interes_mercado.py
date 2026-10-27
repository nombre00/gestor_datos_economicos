import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from data_engine.models.tasa_interes_mercado import InstrumentoTasa as Instrumento
from data_engine.models.tasa_interes_mercado import TipoTasa as Tipo

logger = logging.getLogger(__name__)

SEIS_DECIMALES = Decimal("0.000001")

# Familia = 2.a parte del código del Banco Central (F022.BUF.TIS.AN10.UF.Z.D -> BUF)
FAMILIAS = {
    "TPM": (Instrumento.TPM, None),
    "BCLP": (Instrumento.BONO_PESOS, Tipo.NOMINAL),
    "BUF": (Instrumento.BONO_UF, Tipo.REAL),
}
FAMILIAS_IGNORADAS = {"TPL", "TPD"}   # facilidades permanentes: siempre TPM ± 0,25

# El 9-ago-2001 la TPM pasó de tasa indexada a UF (real) a tasa en pesos (nominal).
# Agosto 2001 es un promedio de ambas y se excluye.
MES_NOMINALIZACION_TPM = date(2001, 8, 1)

RANGO_PLAUSIBLE = (-5, 30)   # porcentaje; fuera de esto avisamos


def _a_decimal(valor):
    return Decimal(str(valor)).quantize(SEIS_DECIMALES, rounding=ROUND_HALF_UP)


def _tipo_tpm(fecha):
    if fecha < MES_NOMINALIZACION_TPM:
        return Tipo.REAL
    if fecha > MES_NOMINALIZACION_TPM:
        return Tipo.NOMINAL
    return None   # agosto 2001: mezcla, se excluye


def _nombre(instrumento, plazo):
    if instrumento == Instrumento.TPM:
        return "Tasa de política monetaria"
    moneda = "pesos" if instrumento == Instrumento.BONO_PESOS else "UF"
    return f"Bono en {moneda} a {plazo} {'año' if plazo == 1 else 'años'}"


def leer_archivo(ruta):
    """Un Excel de la BDE (tasas, frecuencia mensual) -> lista de dicts (una fila por mes y serie).
    Los meses sin dato no generan fila."""
    cuadro = pd.read_excel(ruta, sheet_name="Cuadro", header=2)
    series = pd.read_excel(ruta, sheet_name="Series")

    cuadro = cuadro.dropna(subset=["Reg"]).reset_index(drop=True)
    if len(cuadro) != len(series):
        raise ValueError(
            f"{ruta.name}: {len(cuadro)} filas en Cuadro vs {len(series)} en Series"
        )

    # Columnas de meses. Si hay dos fechas en el mismo mes, se exportó diario: lo rechazamos.
    columnas_mes = [c for c in cuadro.columns if hasattr(c, "year")]
    meses = [(c.year, c.month) for c in columnas_mes]
    if len(set(meses)) != len(meses):
        raise ValueError(
            f"{ruta.name}: hay meses repetidos en las columnas; ¿se exportó diario en vez de mensual?"
        )

    registros = []
    for i, fila in cuadro.iterrows():
        codigo = str(series.at[i, "Serie"]).strip()
        partes = codigo.split(".")
        familia = partes[1]
        if familia in FAMILIAS_IGNORADAS:
            continue
        if familia not in FAMILIAS:
            raise ValueError(f"{ruta.name}: serie no reconocida {codigo!r}")

        instrumento, tipo_fijo = FAMILIAS[familia]
        plazo = None
        if instrumento != Instrumento.TPM:
            plazo = int(partes[3].removeprefix("AN"))   # AN10 -> 10

        for col in columnas_mes:
            valor = fila[col]
            if pd.isna(valor):
                continue
            fecha = date(col.year, col.month, 1)
            tipo = tipo_fijo or _tipo_tpm(fecha)
            if tipo is None:
                continue
            registros.append({
                "fecha": fecha,
                "codigo": codigo,
                "instrumento": instrumento,
                "plazo_anios": plazo,
                "tipo": tipo,
                "nombre": _nombre(instrumento, plazo),
                "valor": _a_decimal(valor),
            })

    return registros


def _validar(registros):
    """Control de calidad: avisa si alguna tasa está fuera de un rango razonable."""
    minimo, maximo = RANGO_PLAUSIBLE
    for r in registros:
        if not (minimo <= r["valor"] <= maximo):
            logger.warning(
                "Tasa fuera de rango: %s %s = %s", r["nombre"], r["fecha"], r["valor"]
            )


def transformar(rutas):
    """Los Excel de tasas (TPM, bonos en pesos y bonos en UF) -> lista única de registros."""
    registros, codigos_vistos = [], {}
    for ruta in rutas:
        del_archivo = leer_archivo(ruta)
        for codigo in {r["codigo"] for r in del_archivo}:
            if codigo in codigos_vistos:
                raise ValueError(
                    f"La serie {codigo} viene en dos archivos: "
                    f"{codigos_vistos[codigo].name} y {ruta.name}"
                )
            codigos_vistos[codigo] = ruta
        registros.extend(del_archivo)

    _validar(registros)
    return registros