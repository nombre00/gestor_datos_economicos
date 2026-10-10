from django.urls import path

from data_engine.models import ComposicionDeudaAcreedor, ComposicionDeudaMoneda

from .views import ComposicionView, SerieHistoricaView

urlpatterns = [
    path("composicion/acreedor/", ComposicionView.as_view(modelo=ComposicionDeudaAcreedor)),
    path("composicion/moneda/", ComposicionView.as_view(modelo=ComposicionDeudaMoneda)),
    path("serie-historica/", SerieHistoricaView.as_view()),
]