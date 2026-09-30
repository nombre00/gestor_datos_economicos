import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from data_engine.models.bono_local import TipoInstrumento, Status
from data_engine.services.scraping.bonos_locales_hacienda import obtener_tablas_crudas

FUENTE = "hacienda_bonos_locales"

MESES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12,
}


@dataclass
class RegistroBonoLocal:
    nombre_bono: str
    anio: int
    fecha_emision: date
    fecha_vencimiento: date
    es_reapertura: bool
    tipo_instrumento: str
    madurez_anios: int | None
    monto_emitido: Decimal | None
    monto_colocado: Decimal | None
    tasa_caratula: Decimal
    paga_intereses_raw: str | None
    status: str


def _normalizar_nombre_campo(nombre: str) -> str:
    """Colapsa espacios y quita notas al pie pegadas al nombre del campo,
    ej. 'Monto Emitido Moneda Origen (6)' -> 'Monto Emitido Moneda Origen'."""
    nombre = re.sub(r"\s+", " ", nombre).strip()
    return re.sub(r"\s*\(\d+\)\s*$", "", nombre)


def _parsear_fecha_hacienda(fecha_str: str) -> date:
    """Igual que en BonoExterno, más soporte de 'sept' (4 letras) y de
    fechas sin cero inicial ('1-abr-23'), que sí se encontraron acá."""
    dia_str, mes_str, anio_str = fecha_str.strip().split("-")
    dia = int(dia_str)
    mes = MESES[mes_str.lower()]
    anio = 1999 if anio_str == "99" else 2000 + int(anio_str)
    return date(anio, mes, dia)


def _limpiar_paga_intereses(valor) -> str | None:
    """Bug conocido de la fuente (tabla 2024): algunas celdas quedaron con
    un valor de tasa en vez de fechas de pago (error de copia desde
    'Tasa carátula'). No se puede reconstruir el valor real -> None."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    if texto.lower() == "n.a." or texto == "":
        return None
    if re.fullmatch(r"[\d,]+%", texto):
        return None
    return texto


def _parsear_monto(valor) -> Decimal | None:
    """'13.000 (2)' -> 13000; 'NaN' -> None. La nota al pie se descarta
    (corrige el monto real en algunos casos, pero no se persiste aparte
    por ahora)."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = re.sub(r"\s*\(\d+\)\s*$", "", str(valor).strip())
    texto = texto.replace(".", "")
    if texto == "" or texto.lower() == "nan":
        return None
    return Decimal(texto)


def _parsear_porcentaje(valor: str) -> Decimal:
    return Decimal(str(valor).strip().replace("%", "").replace(",", "."))


def _parsear_madurez(valor) -> int | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    return int(float(valor))


def _normalizar_status(valor: str) -> str:
    texto = valor.strip().lower()
    return Status.VIGENTE if texto.startswith("vigente") else Status.VENCIDO


def _detectar_tipo_instrumento(nombre_bono: str) -> str:
    nombre_upper = nombre_bono.strip().upper()
    if nombre_upper.startswith("BTP"):
        return TipoInstrumento.BTP
    if nombre_upper.startswith("BTU"):
        return TipoInstrumento.BTU
    if nombre_upper.startswith("LETRA"):
        return TipoInstrumento.LETRA
    raise ValueError(f"No se pudo determinar el tipo de instrumento para: {nombre_bono!r}")


def _limpiar_tabla_individual(tabla: pd.DataFrame) -> pd.DataFrame:
    columnas = tabla.columns.tolist()
    campo_col = columnas[0]

    tabla = tabla.copy()
    tabla[campo_col] = tabla[campo_col].apply(_normalizar_nombre_campo)
    tabla = tabla.set_index(campo_col)

    tabla_t = tabla.transpose()
    tabla_t.index = pd.MultiIndex.from_tuples(tabla_t.index, names=["anio", "nombre_bono"])
    tabla_t = tabla_t.reset_index()
    return tabla_t


def _limpiar_tablas_crudas(tablas: list[pd.DataFrame]) -> pd.DataFrame:
    tablas_limpias = [_limpiar_tabla_individual(t) for t in tablas]
    df = pd.concat(tablas_limpias, ignore_index=True)

    df["anio"] = df["anio"].astype(int)
    df["nombre_bono"] = df["nombre_bono"].str.replace(r"\.\d+$", "", regex=True)

    return df


def transformar() -> list[RegistroBonoLocal]:
    tablas = obtener_tablas_crudas()
    df = _limpiar_tablas_crudas(tablas)

    # es_reapertura: se detecta comparando (nombre_bono, fecha_emision,
    # fecha_vencimiento) a través de los distintos 'anio' -- la primera
    # aparición cronológica es la emisión original, cualquier repetición
    # posterior es una reapertura (ya no siempre lleva la palabra en el
    # nombre, a diferencia de BonoExterno).
    df["fecha_emision_parseada"] = df["Fecha emisión"].apply(_parsear_fecha_hacienda)
    df["fecha_vencimiento_parseada"] = df["Fecha vencimiento"].apply(_parsear_fecha_hacienda)
    df = df.sort_values("anio")
    claves = list(zip(df["nombre_bono"], df["fecha_emision_parseada"], df["fecha_vencimiento_parseada"]))
    vistas = set()
    es_reapertura_list = []
    for clave in claves:
        es_reapertura_list.append(clave in vistas)
        vistas.add(clave)
    df["es_reapertura"] = es_reapertura_list

    registros = []
    for _, fila in df.iterrows():
        registros.append(RegistroBonoLocal(
            nombre_bono=fila["nombre_bono"],
            anio=fila["anio"],
            fecha_emision=fila["fecha_emision_parseada"],
            fecha_vencimiento=fila["fecha_vencimiento_parseada"],
            es_reapertura=fila["es_reapertura"],
            tipo_instrumento=_detectar_tipo_instrumento(fila["nombre_bono"]),
            madurez_anios=_parsear_madurez(fila["Madurez (años)"]),
            monto_emitido=_parsear_monto(fila["Monto Emitido Moneda Origen"]),
            monto_colocado=_parsear_monto(fila["Monto Colocado"]),
            tasa_caratula=_parsear_porcentaje(fila["Tasa carátula (%a.)"]),
            paga_intereses_raw=_limpiar_paga_intereses(fila["Paga intereses"]),
            status=_normalizar_status(fila["Status"]),
        ))

    return registros