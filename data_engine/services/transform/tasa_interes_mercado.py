import logging
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd

from data_engine.models.tasa_interes_mercado import InstrumentoTasa as Instrumento
from data_engine.models.tasa_interes_mercado import TipoTasa as Tipo

logger = logging.getLogger(__name__)

SEIS_DECIMALES = Decimal("0.000001")

# Familia = 2.a parte del código del Banco Central (F022.BUF.TIS.AN10.UF.Z.D -> BUF).
FAMILIAS = {
    "TPM": Instrumento.TPM,
    "BCLP": Instrumento.BONO_PESOS,
    "BUF": Instrumento.BONO_UF,
    "PRC": Instrumento.PRC,
    "PRBC": Instrumento.PRBC,
    "CAP": Instrumento.CAPTACION,
}
TIPO_FIJO = {
    Instrumento.BONO_PESOS: Tipo.NOMINAL,
    Instrumento.BONO_UF: Tipo.REAL,
    Instrumento.PRC: Tipo.REAL,
    Instrumento.PRBC: Tipo.REAL,
}
# TPL/TPD: facilidades permanentes (siempre TPM ± 0,25).
# PDBC: en este cuadro es el PRBC a 360 días, con 112 meses sin dato.
FAMILIAS_IGNORADAS = {"TPL", "TPD", "PDBC"}

# Plazos que no son años enteros (4.a parte del código)
ETIQUETAS_PLAZO = {
    "D089": "30 a 89 días",
    "D090": "90 días",
    "AN01": "90 días a 1 año",
    "AN03": "1 a 3 años",
    "MA03": "más de 3 años",
}
TIPO_POR_REAJUSTE = {"NO": Tipo.NOMINAL, "RE": Tipo.REAL, "UF": Tipo.REAL}

# El 9-ago-2001 la TPM pasó de tasa indexada a UF (real) a tasa en pesos (nominal).
# Agosto 2001 es un promedio de ambas y se excluye.
MES_NOMINALIZACION_TPM = date(2001, 8, 1)

# Porcentaje; fuera de esto avisamos. Amplio porque la captación nominal llegó a ~67% en 1982-85.
RANGO_PLAUSIBLE = (-5, 80)


def _a_decimal(valor):
    return Decimal(str(valor)).quantize(SEIS_DECIMALES, rounding=ROUND_HALF_UP)


def _tipo_tpm(fecha):
    if fecha < MES_NOMINALIZACION_TPM:
        return Tipo.REAL
    if fecha > MES_NOMINALIZACION_TPM:
        return Tipo.NOMINAL
    return None   # agosto 2001: mezcla, se excluye


def _plazos(instrumento, partes):
    """Devuelve (plazo_anios, plazo_etiqueta) según el instrumento y el código."""
    if instrumento == Instrumento.TPM:
        return None, None
    if instrumento in (Instrumento.BONO_PESOS, Instrumento.BONO_UF, Instrumento.PRC):
        return int(partes[3].removeprefix("AN")), None   # AN10 -> 10 años
    etiqueta = ETIQUETAS_PLAZO.get(partes[3])
    if etiqueta is None:
        raise ValueError(f"Plazo no reconocido en el código {'.'.join(partes)!r}")
    return None, etiqueta


def _nombre(instrumento, tipo, plazo_anios, plazo_etiqueta):
    if instrumento == Instrumento.TPM:
        return "Tasa de política monetaria"
    if instrumento in (Instrumento.BONO_PESOS, Instrumento.BONO_UF):
        moneda = "pesos" if instrumento == Instrumento.BONO_PESOS else "UF"
        return f"Bono en {moneda} a {plazo_anios} {'año' if plazo_anios == 1 else 'años'}"
    if instrumento == Instrumento.PRC:
        return f"PRC en UF a {plazo_anios} años"
    if instrumento == Instrumento.PRBC:
        return f"PRBC en UF a {plazo_etiqueta}"
    moneda = "pesos" if tipo == Tipo.NOMINAL else "UF"
    return f"Captación en {moneda}, {plazo_etiqueta}"


def leer_archivo(ruta):
    """Un Excel de la BDE (tasas, frecuencia mensual) -> lista de dicts (una fila por mes y serie).
    Los meses sin dato no generan fila. Las series de flujo (montos) se ignoran."""
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
        if familia in FAMILIAS_IGNORADAS or partes[2] == "FLU":
            continue
        if familia not in FAMILIAS:
            raise ValueError(f"{ruta.name}: serie no reconocida {codigo!r}")

        instrumento = FAMILIAS[familia]
        plazo_anios, plazo_etiqueta = _plazos(instrumento, partes)
        if instrumento == Instrumento.CAPTACION:
            tipo_fijo = TIPO_POR_REAJUSTE[partes[4]]
        else:
            tipo_fijo = TIPO_FIJO.get(instrumento)   # None en la TPM: se decide por fecha

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
                "plazo_anios": plazo_anios,
                "plazo_etiqueta": plazo_etiqueta,
                "tipo": tipo,
                "nombre": _nombre(instrumento, tipo, plazo_anios, plazo_etiqueta),
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
    """Los Excel de tasas del Banco Central -> lista única de registros."""
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