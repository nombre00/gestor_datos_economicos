# Main de la aplicación django que el programa referencia para funcionar.

from django.apps import AppConfig


class DataEngineConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "data_engine"