"""
composicion_deuda_moneda.py (modelo)

Composición de la deuda pública por moneda de denominación, a cierre de
cada año (mas el corte parcial a sep-2025). Fuente: Ministerio de Hacienda,
archivo Composicion_de_la_Deuda_sep-2025.xlsx, hoja "Moneda".

Los montos ya vienen en millones de USD (confirmado cruzando el total de
este archivo contra el valor bruta/usd de SerieHistoricaDeuda), por lo que
a diferencia de SerieHistoricaDeuda no existe un campo de moneda separado
aquí: la "moneda" en este dataset es la categoría en sí (a qué moneda está
denominada la deuda), no la unidad en la que se reporta el monto.
"""

from __future__ import annotations

from django.db import models


class ComposicionDeudaMoneda(models.Model):
    class Categoria(models.TextChoices):
        DOLARES_USA = "dolares_usa", "Dólares USA"
        UF = "uf", "Unidades de Fomento Chile"
        PESOS = "pesos", "Pesos"
        UNIDAD_CUENTA_BID = "unidad_cuenta_bid", "Unidad de Cuenta BID"
        UNIDAD_CANASTA_BIRF = "unidad_canasta_birf", "Unidad de Canasta BIRF"
        YEN_JAPONES = "yen_japones", "Yen Japonés"
        EUROS = "euros", "Euros"
        MARCO_ALEMAN = "marco_aleman", "Marco Alemán"
        OTRAS = "otras", "Otras"

    anio = models.PositiveSmallIntegerField()
    fecha_corte = models.DateField()
    categoria = models.CharField(max_length=32, choices=Categoria.choices)
    monto_millones = models.DecimalField(max_digits=18, decimal_places=6)
    es_corte_parcial = models.BooleanField(default=False)
    fuente = models.CharField(max_length=64, default="hacienda_composicion_deuda")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["fecha_corte", "categoria"],
                name="unique_composicion_moneda_corte_categoria",
            )
        ]
        indexes = [models.Index(fields=["anio", "categoria"])]

    def __str__(self) -> str:
        return f"{self.get_categoria_display()} — {self.fecha_corte}"