from django.db import models


class InstrumentoTasa(models.TextChoices):
    TPM = "tpm", "Tasa de política monetaria"
    BONO_PESOS = "bono_pesos", "Bonos en pesos (BCP/BTP)"
    BONO_UF = "bono_uf", "Bonos en UF (BCU/BTU)"


class TipoTasa(models.TextChoices):
    NOMINAL = "nominal", "Nominal (en pesos)"
    REAL = "real", "Real (sobre UF)"


class TasaInteresMercadoQuerySet(models.QuerySet):
    def serie(self, instrumento, plazo_anios=None):
        """Serie mensual de una tasa, ordenada por fecha. Para la TPM no se pasa plazo."""
        return (
            self.filter(instrumento=instrumento, plazo_anios=plazo_anios)
            .order_by("fecha")
            .values("fecha", "valor", "tipo")
        )


class TasaInteresMercado(models.Model):
    """Tasas de interés mensuales del Banco Central (BDE): TPM desde 1997 y tasas de mercado
    secundario de bonos en pesos y en UF desde 2002. Promedio simple del mes, en porcentaje.
    Una fila por mes y serie; los meses sin dato no se guardan.
    OJO: la TPM es REAL (indexada a UF) hasta jul-2001 y NOMINAL desde sep-2001;
    ago-2001 se excluye porque mezcla ambas."""

    fecha = models.DateField()                  # primer día del mes
    codigo = models.CharField(max_length=40)    # código BCCh: F022.BUF.TIS.AN10.UF.Z.D
    instrumento = models.CharField(max_length=12, choices=InstrumentoTasa.choices)
    plazo_anios = models.PositiveSmallIntegerField(null=True, blank=True)   # null en la TPM
    tipo = models.CharField(max_length=10, choices=TipoTasa.choices)
    nombre = models.CharField(max_length=100)   # "Bono en UF a 10 años"
    valor = models.DecimalField(max_digits=10, decimal_places=6)

    fuente = models.CharField(max_length=100, default="bcch_bde_tasas")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    objects = TasaInteresMercadoQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["fecha", "codigo"], name="uniq_tasa_interes_mercado")
        ]
        indexes = [
            models.Index(fields=["instrumento", "plazo_anios"]),
            models.Index(fields=["fecha"]),
        ]

    def __str__(self):
        return f"{self.fecha:%Y-%m} | {self.nombre} ({self.tipo}): {self.valor}"