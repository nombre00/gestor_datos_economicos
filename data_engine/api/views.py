from collections import defaultdict

from rest_framework.response import Response
from rest_framework.views import APIView

from data_engine.models import (
    ComposicionDeudaAcreedor,
    ComposicionDeudaMoneda,
    SerieHistoricaDeuda,
)


def _armar_series(modelo):
    """Pivot genérico para cualquier tabla de composición: años como categorías
    y una serie por categoría, sin el corte parcial."""
    etiquetas = dict(modelo._meta.get_field("categoria").choices)

    filas = (
        modelo.objects
        .filter(es_corte_parcial=False)
        .order_by("anio")
        .values("anio", "categoria", "monto_millones")
    )

    anios = sorted({f["anio"] for f in filas})
    por_categoria = defaultdict(dict)
    for f in filas:
        por_categoria[f["categoria"]][f["anio"]] = float(f["monto_millones"])

    series = [
        {
            "nombre": etiquetas.get(categoria, categoria),
            "datos": [datos.get(anio, 0) for anio in anios],
        }
        for categoria, datos in por_categoria.items()
    ]

    return {"categorias": [str(a) for a in anios], "series": series}


class ComposicionView(APIView):
    modelo = None  # cada ruta indica qué modelo usar

    def get(self, request):
        return Response(_armar_series(self.modelo))


class SerieHistoricaView(APIView):
    def get(self, request):
        moneda = request.query_params.get("moneda", "usd")
        if moneda not in ("usd", "clp"):
            return Response({"detail": "moneda debe ser 'usd' o 'clp'"}, status=400)

        etiquetas = dict(SerieHistoricaDeuda._meta.get_field("tipo_deuda").choices)

        filas = (
            SerieHistoricaDeuda.objects
            .filter(moneda=moneda, es_corte_parcial=False)
            .order_by("anio")
            .values("anio", "tipo_deuda", "monto_millones")
        )

        anios = sorted({f["anio"] for f in filas})
        por_tipo = defaultdict(dict)
        for f in filas:
            por_tipo[f["tipo_deuda"]][f["anio"]] = float(f["monto_millones"])

        series = [
            {
                "nombre": etiquetas.get(tipo, tipo.capitalize()),
                "datos": [datos.get(anio) for anio in anios],
            }
            for tipo, datos in por_tipo.items()
        ]

        return Response({"categorias": [str(a) for a in anios], "series": series})