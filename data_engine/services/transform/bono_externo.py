import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

import pandas as pd

from data_engine.models.bono_externo import Moneda, PagoIntereses, Vigencia
from data_engine.services.scraping.bonos_externos_hacienda import obtener_tablas_crudas

FUENTE = "hacienda_bonos_externos"

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}


@dataclass
class RegistroBonoExterno:
    nombre_bono: str
    fecha_emision: date
    fecha_vencimiento: date
    es_reapertura: bool
    moneda: str
    monto: Decimal
    tasa_caratula_raw: str
    tasa_caratula_fija: Decimal | None
    tasa_bono_tesoro: Decimal | None
    tasa_local_tesoro_chile: Decimal | None
    precio: Decimal
    yield_emision: Decimal
    spread_caratula: Decimal | None
    spread_nota_referencia: str | None
    pago_intereses: str
    vigencia: str


def _normalizar_nombre_columna(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre).strip()


def _parsear_fecha_hacienda(fecha_str: str) -> date:
    """Parsea fechas en español (ene/feb/.../dic), con año de 2 o 4 dígitos.
    Único caso de 2 dígitos que es 19xx en este dataset es "99" (año 1999);
    todo el resto de años de 2 dígitos es 20xx, incluidos vencimientos
    lejanos como "61" (2061) que un umbral genérico interpretaría mal."""
    dia_str, mes_str, anio_str = fecha_str.strip().split("-")
    dia = int(dia_str)
    mes = MESES[mes_str.lower()]
    if len(anio_str) == 2:
        anio = 1999 if anio_str == "99" else 2000 + int(anio_str)
    else:
        anio = int(anio_str)
    return date(anio, mes, dia)


def _parsear_porcentaje(valor) -> Decimal | None:
    """Convierte '5,125%' -> Decimal('5.125'). Trata '-', 'N.A.', 'n.a.'
    y vacío/NaN como ausencia de dato."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    if texto in ("-", "N.A.", "n.a.", "", "nan"):
        return None
    texto = texto.replace("%", "").replace(",", ".")
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None


def _parsear_tasa_caratula_fija(texto_raw: str) -> Decimal | None:
    """Solo devuelve un valor si la tasa carátula es un porcentaje fijo puro
    (ej. '5,125%'). Tasas variables como 'Libor (3M) + 0,40%' devuelven None
    — el valor completo se conserva aparte en tasa_caratula_raw."""
    texto = texto_raw.strip()
    if re.fullmatch(r"[\d.,]+%", texto):
        return _parsear_porcentaje(texto)
    return None


def _parsear_monto(texto_raw: str) -> tuple[Decimal, str]:
    """'US$1.000' -> (1000, USD); '300 €' -> (300, EUR); '272.295' -> (272295, CLP).
    Quita notas al pie tipo '(6)' pegadas al final antes de parsear."""
    texto = re.sub(r"\(\d+\)\s*$", "", texto_raw.strip()).strip()
    if texto.startswith("US$"):
        moneda = Moneda.USD
        numero = texto.replace("US$", "")
    elif "€" in texto:
        moneda = Moneda.EUR
        numero = texto.replace("€", "").strip()
    else:
        moneda = Moneda.CLP
        numero = texto
    numero = numero.replace(".", "")  # punto de miles, estos montos no llevan decimales
    return Decimal(numero), moneda


def _parsear_spread(texto_raw) -> tuple[Decimal | None, str | None]:
    """'83 (2)' -> (83, '2'); '60(5)' -> (60, '5'); '-58' -> (-58, None);
    '137,5' -> (137.5, None); '-' -> (None, None)."""
    if texto_raw is None or (isinstance(texto_raw, float) and pd.isna(texto_raw)):
        return None, None
    texto = str(texto_raw).strip()
    if texto in ("-", "", "nan"):
        return None, None
    match = re.match(r"^(-?[\d,]+)\s*(?:\((\d+)\))?$", texto)
    if not match:
        return None, None
    numero_str, nota = match.groups()
    return Decimal(numero_str.replace(",", ".")), nota


def _normalizar_pago_intereses(texto_raw: str) -> str:
    """'Semestrales  (3)' -> SEMESTRAL; 'Anual'/'Anuales' -> ANUAL (mismo valor,
    la fuente usa ambas formas indistintamente)."""
    texto = re.sub(r"\(.*?\)", "", texto_raw).strip().lower()
    mapa = {
        "semestral": PagoIntereses.SEMESTRAL, "semestrales": PagoIntereses.SEMESTRAL,
        "trimestral": PagoIntereses.TRIMESTRAL, "trimestrales": PagoIntereses.TRIMESTRAL,
        "anual": PagoIntereses.ANUAL, "anuales": PagoIntereses.ANUAL,
    }
    return mapa[texto]


def _normalizar_vigencia(texto_raw: str) -> str:
    """'Vencido y pagado' / 'Vencido y Pagado' (mayúscula inconsistente en la
    fuente) -> VENCIDO; 'Vigente' -> VIGENTE."""
    texto = texto_raw.strip().lower()
    return Vigencia.VIGENTE if texto.startswith("vigente") else Vigencia.VENCIDO


def _limpiar_tablas_crudas(tablas: list[pd.DataFrame]) -> pd.DataFrame:
    """Reproduce toda la limpieza validada en el notebook de exploración:
    transponer cada tabla, concatenarlas, sacar duplicados exactos (la fuente
    repite un bloque completo de tabla), quitar el sufijo '.1' que pandas
    agrega a nombres de bono repetidos dentro de una misma tabla, y fusionar
    las columnas que la fuente escribe con nombres/espacios inconsistentes
    entre tablas."""
    tablas_transpuestas = []
    for tabla in tablas:
        tabla = tabla.copy()
        tabla["Emisiones"] = tabla["Emisiones"].apply(_normalizar_nombre_columna)
        tabla = tabla.set_index("Emisiones").transpose()
        tablas_transpuestas.append(tabla)

    df = pd.concat(tablas_transpuestas)
    df.index.name = "bono"
    df = df.reset_index()
    df = df.drop_duplicates()

    df["bono"] = df["bono"].str.replace(r"\.\d+$", "", regex=True)

    # Fusionar "Monto (MM US$)(1)" (bonos viejos) y "Monto (MM)" (bonos nuevos)
    df["monto_raw"] = df["Monto (MM US$)(1)"].fillna(df["Monto (MM)"])
    df = df.drop(columns=["Monto (MM US$)(1)", "Monto (MM)"])

    # Fusionar las dos columnas "Tasa bono Tesoro EE.UU. (% a.)" duplicadas
    posiciones_tesoro = [i for i, c in enumerate(df.columns) if c == "Tasa bono Tesoro EE.UU. (% a.)"]
    df["tasa_tesoro_raw"] = df.iloc[:, posiciones_tesoro].bfill(axis=1).iloc[:, 0]
    df = df.drop(df.columns[posiciones_tesoro], axis=1)

    # Corrección puntual documentada: pd.read_html() perdió la coma decimal
    # de este valor al inferir la columna como numérica. Verificado contra
    # la fuente (hacienda.cl, consultado 25-sep-2026): el valor real es
    # "137,5", no "1375".
    fila_global_2037 = df[(df["bono"] == "Global 2037 en USD") & (df["Fecha emisión"] == "13-ene-25")].index
    df.loc[fila_global_2037, "Spread carátula (pb)"] = "137,5"

    return df


def transformar() -> list[RegistroBonoExterno]:
    tablas = obtener_tablas_crudas()
    df = _limpiar_tablas_crudas(tablas)

    registros = []
    for _, fila in df.iterrows():
        monto, moneda = _parsear_monto(fila["monto_raw"])
        spread, spread_nota = _parsear_spread(fila["Spread carátula (pb)"])

        registros.append(RegistroBonoExterno(
            nombre_bono=fila["bono"],
            fecha_emision=_parsear_fecha_hacienda(fila["Fecha emisión"]),
            fecha_vencimiento=_parsear_fecha_hacienda(fila["Fecha vencimiento"]),
            es_reapertura="reapertura" in fila["bono"].lower(),
            moneda=moneda,
            monto=monto,
            tasa_caratula_raw=fila["Tasa carátula (% a.)"],
            tasa_caratula_fija=_parsear_tasa_caratula_fija(fila["Tasa carátula (% a.)"]),
            tasa_bono_tesoro=_parsear_porcentaje(fila["tasa_tesoro_raw"]),
            tasa_local_tesoro_chile=_parsear_porcentaje(fila.get("Tasa local bono Tesoro Chile (% a.)")),
            precio=_parsear_porcentaje(fila["Precio"]),
            yield_emision=_parsear_porcentaje(fila["Yield a la fecha de emisión"]),
            spread_caratula=spread,
            spread_nota_referencia=spread_nota,
            pago_intereses=_normalizar_pago_intereses(fila["Pago intereses"]),
            vigencia=_normalizar_vigencia(fila["Vigencia"]),
        ))

    return registros