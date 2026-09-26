from data_engine.services.transform.bono_externo import transformar
from data_engine.repositories.bono_externo import guardar


def ingerir() -> dict:
    registros = transformar()
    return guardar(registros)