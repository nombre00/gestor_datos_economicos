from django.urls import path

from data_engine.models import ComposicionDeudaAcreedor, ComposicionDeudaMoneda

from .views import (
    ComposicionView,
    SerieHistoricaView,
    TenedoresGobiernoView,
    TenedoresPlazoView,
)

urlpatterns = [
    path("composicion/acreedor/", ComposicionView.as_view(modelo=ComposicionDeudaAcreedor)),
    path("composicion/moneda/", ComposicionView.as_view(modelo=ComposicionDeudaMoneda)),
    path("serie-historica/", SerieHistoricaView.as_view()),
    path("tenedores/gobierno/", TenedoresGobiernoView.as_view()),
    path("tenedores/plazo/", TenedoresPlazoView.as_view()),
]