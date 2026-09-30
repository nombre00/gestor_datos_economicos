from data_engine.services.transform.bono_local import transformar
from data_engine.repositories.bono_local import guardar


def ingerir() -> dict:
    registros = transformar()
    return guardar(registros)