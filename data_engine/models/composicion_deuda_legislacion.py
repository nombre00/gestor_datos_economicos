"""
composicion_deuda_legislacion.py (modelo)

Composición de la deuda pública por legislación (interna/externa), a cierre
de cada año (mas el corte parcial a sep-2025). Fuente: Ministerio de
Hacienda, archivo Composicion_de_la_Deuda_sep-2025.xlsx, hoja "Legislación".

Mismos supuestos que los otros dos: montos ya en millones de USD, sin campo
de moneda separado.
"""

from __future__ import annotations

from django.db import models


class ComposicionDeudaLegislacion(models.Model):
    class Categoria(models.TextChoices):
        DEUDA_INTERNA = "deuda_interna", "Deuda Interna"
        DEUDA_EXTERNA = "deuda_externa", "Deuda Externa"

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
                name="unique_composicion_legislacion_corte_categoria",
            )
        ]
        indexes = [models.Index(fields=["anio", "categoria"])]

    def __str__(self) -> str:
        return f"{self.get_categoria_display()} — {self.fecha_corte}"