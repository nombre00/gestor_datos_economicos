from data_engine.services.transform.stock_titulo_deuda import transformar
from data_engine.repositories.stock_titulo_deuda import guardar


def ingerir(path_excel: str) -> dict:
    registros = transformar(path_excel)
    return guardar(registros)