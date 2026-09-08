# Rutas principales del proyecto.

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    # A medida que definan data_engine/api/urls.py, se agrega acá:
    # path("api/", include("data_engine.api.urls")),
]