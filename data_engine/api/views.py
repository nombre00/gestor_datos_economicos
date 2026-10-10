from collections import defaultdict

from rest_framework.response import Response
from rest_framework.views import APIView

from data_engine.models import ComposicionDeudaAcreedor


class ComposicionAcreedorView(APIView):
    def get(self, request):
        etiquetas = dict(ComposicionDeudaAcreedor._meta.get_field("categoria").choices)

        filas = (
            ComposicionDeudaAcreedor.objects
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

        return Response({"categorias": [str(a) for a in anios], "series": series})