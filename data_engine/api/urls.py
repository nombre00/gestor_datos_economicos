from django.urls import path

from .views import ComposicionAcreedorView

urlpatterns = [
    path("composicion/acreedor/", ComposicionAcreedorView.as_view()),
]