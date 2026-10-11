from collections import defaultdict

from rest_framework.response import Response
from rest_framework.views import APIView

from data_engine.models import (
    ComposicionDeudaAcreedor,
    ComposicionDeudaMoneda,
    SerieHistoricaDeuda,
    StockTituloDeuda
)
from data_engine.models.stock_titulo_deuda import Instrumento, Tenedor



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


def _armar_respuesta_trimestral(acumulado, etiquetas):
    """acumulado: {clave: {fecha_corte: monto}} -> formato {categorias, series}.
    Descarta los trimestres sin ningún dato (2008-T1, donde la fuente trae todo en 0)."""
    fechas = sorted({fecha for por_fecha in acumulado.values() for fecha in por_fecha})
    fechas = [
        f for f in fechas
        if sum(por_fecha.get(f, 0) for por_fecha in acumulado.values()) > 0
    ]

    series = [
        {
            "nombre": etiquetas.get(clave, clave),
            "datos": [por_fecha.get(f, 0) for f in fechas],
        }
        for clave, por_fecha in acumulado.items()
    ]
    categorias = [f"{f.year}-T{(f.month - 1) // 3 + 1}" for f in fechas]
    return {"categorias": categorias, "series": series}


class TenedoresGobiernoView(APIView):
    def get(self, request):
        etiquetas = dict(Tenedor.choices)
        filas = (
            StockTituloDeuda.objects.tenedores_reales()
            .filter(instrumento=Instrumento.BONOS_GOBIERNO_GENERAL)
            .order_by("fecha_corte")
            .values("fecha_corte", "tenedor", "monto_miles_millones_clp")
        )

        acumulado = defaultdict(lambda: defaultdict(float))
        for f in filas:
            acumulado[f["tenedor"]][f["fecha_corte"]] += float(f["monto_miles_millones_clp"])

        return Response(_armar_respuesta_trimestral(acumulado, etiquetas))


class TenedoresPlazoView(APIView):
    def get(self, request):
        etiquetas = {
            "intermediacion_financiera": "Intermediación financiera (corto plazo)",
            "renta_fija": "Renta fija (largo plazo)",
        }
        filas = (
            StockTituloDeuda.objects.tenedores_reales()
            .order_by("fecha_corte")
            .values("fecha_corte", "instrumento", "monto_miles_millones_clp")
        )

        acumulado = defaultdict(lambda: defaultdict(float))
        for f in filas:
            sector = Instrumento(f["instrumento"]).sector_emisor
            acumulado[sector][f["fecha_corte"]] += float(f["monto_miles_millones_clp"])

        return Response(_armar_respuesta_trimestral(acumulado, etiquetas))