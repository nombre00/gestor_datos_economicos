from collections import defaultdict
from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from data_engine.models import (
    ComposicionDeudaAcreedor,
    ComposicionDeudaMoneda,
    SerieHistoricaDeuda,
    StockTituloDeuda,
    BonoExterno,
    BonoLocal, 
    IndicadorEconomico
)
from data_engine.models.stock_titulo_deuda import Instrumento, Tenedor
from data_engine.models.bono_externo import Moneda as MonedaBonoExterno, Vigencia
from data_engine.models.bono_local import Status, TipoInstrumento



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


def _a_float(valor):
    return float(valor) if valor is not None else None


class BonosExternosView(APIView):
    """Lista completa de bonos externos para la tabla."""

    def get(self, request):
        bonos = BonoExterno.objects.order_by("fecha_vencimiento", "nombre_bono")
        datos = [
            {
                "nombre_bono": b.nombre_bono,
                "moneda": b.moneda,
                "fecha_emision": b.fecha_emision.isoformat(),
                "fecha_vencimiento": b.fecha_vencimiento.isoformat(),
                "es_reapertura": b.es_reapertura,
                "monto": float(b.monto),
                "tasa_caratula": b.tasa_caratula_raw,
                "spread": _a_float(b.spread_caratula),
                "spread_nota": b.spread_nota_referencia,
                "yield_emision": _a_float(b.yield_emision),
                "vigencia": b.vigencia,
                "vigencia_etiqueta": b.get_vigencia_display(),
            }
            for b in bonos
        ]
        return Response(datos)


class BonosExternosVencimientosView(APIView):
    """Monto vigente que vence por año, una serie por moneda.
    Rellena los años intermedios sin vencimientos con 0 para no esconder los huecos."""

    def get(self, request):
        filas = (
            BonoExterno.objects
            .filter(vigencia=Vigencia.VIGENTE)
            .values("fecha_vencimiento", "moneda", "monto")
        )

        acumulado = defaultdict(lambda: defaultdict(float))
        for f in filas:
            acumulado[f["moneda"]][f["fecha_vencimiento"].year] += float(f["monto"])

        if not acumulado:
            return Response({"categorias": [], "series": []})

        anios_con_dato = {a for por_anio in acumulado.values() for a in por_anio}
        anios = list(range(min(anios_con_dato), max(anios_con_dato) + 1))
        etiquetas = dict(MonedaBonoExterno.choices)

        series = [
            {
                "nombre": etiquetas.get(moneda, moneda),
                "datos": [por_anio.get(a, 0) for a in anios],
            }
            for moneda, por_anio in sorted(acumulado.items())
        ]
        return Response({"categorias": [str(a) for a in anios], "series": series})


class BonosExternosSpreadView(APIView):
    """Puntos (plazo al emitir, spread, año de emisión) para el scatter.
    Excluye los bonos sin spread (tasa variable)."""

    def get(self, request):
        bonos = (
            BonoExterno.objects
            .filter(spread_caratula__isnull=False)
            .order_by("fecha_emision")
        )
        datos = [
            {
                "nombre_bono": b.nombre_bono,
                "moneda": b.moneda,
                "plazo_anios": round((b.fecha_vencimiento - b.fecha_emision).days / 365.25, 2),
                "spread": float(b.spread_caratula),
                "anio_emision": b.fecha_emision.year,
                "es_reapertura": b.es_reapertura,
            }
            for b in bonos
        ]
        return Response(datos)


def _monto_bono_local(colocado, emitido):
    """El monto colocado es lo que realmente se vendió y se va a pagar.
    Los bonos antiguos (hasta ~2011) solo tienen monto emitido."""
    return colocado if colocado is not None else emitido


class BonosLocalesView(APIView):
    """Lista completa de bonos locales para la tabla (una fila por colocación)."""

    def get(self, request):
        bonos = BonoLocal.objects.order_by("fecha_vencimiento", "nombre_bono", "anio")
        datos = []
        for b in bonos:
            monto = _monto_bono_local(b.monto_colocado, b.monto_emitido)
            datos.append({
                "nombre_bono": b.nombre_bono,
                "anio": b.anio,
                "tipo": b.tipo_instrumento,
                "tipo_etiqueta": b.get_tipo_instrumento_display(),
                "unidad": TipoInstrumento(b.tipo_instrumento).moneda_unidad,
                "fecha_emision": b.fecha_emision.isoformat(),
                "fecha_vencimiento": b.fecha_vencimiento.isoformat(),
                "es_reapertura": b.es_reapertura,
                "monto": _a_float(monto),
                "monto_es_colocado": b.monto_colocado is not None,
                "tasa_caratula": float(b.tasa_caratula),
                "paga_intereses": b.paga_intereses_raw,
                "status": b.status,
                "status_etiqueta": b.get_status_display(),
            })
        return Response(datos)


class BonosLocalesVencimientosView(APIView):
    """Monto vigente que vence por año y por tipo, en millones de CLP.
    Los BTU (miles de UF) se valorizan con la UF de la fecha de corte (hoy),
    y además se entrega la serie de BTU en su unidad nativa (miles de UF)."""

    def get(self, request):
        uf = IndicadorEconomico.objects.valor_al("uf", date.today())
        if uf is None:
            return Response(
                {"detail": "No hay valor de UF cargado; corre la ingesta de indicadores."},
                status=503,
            )
        valor_uf = float(uf.valor)

        filas = (
            BonoLocal.objects
            .filter(status=Status.VIGENTE)
            .values("tipo_instrumento", "fecha_vencimiento", "monto_emitido", "monto_colocado")
        )

        en_clp = defaultdict(lambda: defaultdict(float))
        btu_en_uf = defaultdict(float)
        for f in filas:
            monto = _monto_bono_local(f["monto_colocado"], f["monto_emitido"])
            if monto is None:
                continue
            monto = float(monto)
            anio = f["fecha_vencimiento"].year
            tipo = f["tipo_instrumento"]

            if tipo == TipoInstrumento.BTU.value:
                btu_en_uf[anio] += monto
                # miles de UF -> millones de CLP: monto * 1.000 * UF / 1.000.000
                en_clp[tipo][anio] += monto * valor_uf / 1000
            else:
                en_clp[tipo][anio] += monto

        if not en_clp:
            return Response({
                "categorias": [], "series": [], "serie_btu_uf": [],
                "fecha_valorizacion": uf.fecha.isoformat(), "valor_uf": valor_uf,
            })

        anios_con_dato = {a for por_anio in en_clp.values() for a in por_anio}
        anios = list(range(min(anios_con_dato), max(anios_con_dato) + 1))
        etiquetas = dict(TipoInstrumento.choices)

        series = [
            {
                "nombre": etiquetas[tipo.value],
                "datos": [en_clp[tipo.value].get(a, 0) for a in anios],
            }
            for tipo in TipoInstrumento
            if tipo.value in en_clp
        ]

        return Response({
            "categorias": [str(a) for a in anios],
            "series": series,
            "serie_btu_uf": [btu_en_uf.get(a, 0) for a in anios],
            "fecha_valorizacion": uf.fecha.isoformat(),
            "valor_uf": valor_uf,
        })


class BonosLocalesTasaView(APIView):
    """Puntos (plazo al emitir, tasa carátula, tipo) para el scatter.
    Sin Letras (cupón cero, tasa 0%) y sin reaperturas: una reapertura tiene
    la misma tasa y vencimiento que el bono original, solo duplicaría el punto."""

    def get(self, request):
        bonos = (
            BonoLocal.objects
            .filter(es_reapertura=False)
            .exclude(tipo_instrumento=TipoInstrumento.LETRA)
            .order_by("fecha_emision")
        )
        datos = [
            {
                "nombre_bono": b.nombre_bono,
                "tipo": b.tipo_instrumento,
                "tipo_etiqueta": b.get_tipo_instrumento_display(),
                "plazo_anios": round((b.fecha_vencimiento - b.fecha_emision).days / 365.25, 2),
                "tasa": float(b.tasa_caratula),
                "anio_emision": b.fecha_emision.year,
            }
            for b in bonos
        ]
        return Response(datos)