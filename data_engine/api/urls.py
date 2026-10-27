from django.urls import path 

from data_engine.models import ComposicionDeudaAcreedor, ComposicionDeudaMoneda

from .views import (
    BonosExternosSpreadView,
    BonosExternosVencimientosView,
    BonosExternosView,
    ComposicionView,
    SerieHistoricaView,
    TenedoresGobiernoView,
    TenedoresPlazoView,
    BonosLocalesTasaView,
    BonosLocalesVencimientosView,
    BonosLocalesView,
    BonosPanoramaView,
    SerieHistoricaResumenView,
    EjecucionFiscalView,
    FinanciamientoView,
)

urlpatterns = [
    path("composicion/acreedor/", ComposicionView.as_view(modelo=ComposicionDeudaAcreedor)),
    path("composicion/moneda/", ComposicionView.as_view(modelo=ComposicionDeudaMoneda)),
    path("serie-historica/", SerieHistoricaView.as_view()),
    path("tenedores/gobierno/", TenedoresGobiernoView.as_view()),
    path("tenedores/plazo/", TenedoresPlazoView.as_view()),
    path("bonos/externos/", BonosExternosView.as_view()),
    path("bonos/externos/vencimientos/", BonosExternosVencimientosView.as_view()),
    path("bonos/externos/spread/", BonosExternosSpreadView.as_view()),
    path("bonos/locales/", BonosLocalesView.as_view()),
    path("bonos/locales/vencimientos/", BonosLocalesVencimientosView.as_view()),
    path("bonos/locales/tasa/", BonosLocalesTasaView.as_view()),
    path("bonos/panorama/", BonosPanoramaView.as_view()),
    path("serie-historica/resumen/", SerieHistoricaResumenView.as_view()),
    path("presupuesto/ejecucion-fiscal/", EjecucionFiscalView.as_view()),
    path("presupuesto/financiamiento/", FinanciamientoView.as_view()),
]