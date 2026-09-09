"""
composicion_deuda_acreedor.py (modelo)

Composición de la deuda pública por tipo de acreedor, a cierre de cada año
(mas el corte parcial a sep-2025). Fuente: Ministerio de Hacienda, archivo
Composicion_de_la_Deuda_sep-2025.xlsx, hoja "Acreedor".

Mismos supuestos que ComposicionDeudaMoneda: montos ya en millones de USD,
sin campo de moneda separado.
"""

from __future__ import annotations

from django.db import models


class ComposicionDeudaAcreedor(models.Model):
    class Categoria(models.TextChoices):
        BANCO_CENTRAL_CHILE = "banco_central_chile", "Banco Central de Chile"
        BIRF = "birf", "Banco Internacional de Reconstrucción y Fomento (BIRF)"
        BID = "bid", "Banco Interamericano de Desarrollo (BID)"
        BONOS = "bonos", "Bonos"
        EXIMBANK_JAPON = "eximbank_japon", "Eximbank Japón"
        BANCOESTADO_CHILE = "bancoestado_chile", "BancoEstado de Chile"
        AID = "aid", "Agencia Internacional de Desarrollo (AID)"
        OTROS = "otros", "Otros"

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
                name="unique_composicion_acreedor_corte_categoria",
            )
        ]
        indexes = [models.Index(fields=["anio", "categoria"])]

    def __str__(self) -> str:
        return f"{self.get_categoria_display()} — {self.fecha_corte}"