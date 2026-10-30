from django.db import models


class InstrumentoTasa(models.TextChoices):
    TPM = "tpm", "Tasa de política monetaria"
    BONO_PESOS = "bono_pesos", "Bonos en pesos (BCP/BTP)"
    BONO_UF = "bono_uf", "Bonos en UF (BCU/BTU)"
    PRC = "prc", "Pagarés reajustables con cupones del BCCh (PRC, en UF)"
    PRBC = "prbc", "Pagarés reajustables del BCCh (PRBC, en UF)"
    CAPTACION = "captacion", "Tasa de captación del sistema financiero"


class TipoTasa(models.TextChoices):
    NOMINAL = "nominal", "Nominal (en pesos)"
    REAL = "real", "Real (sobre UF)"


class TasaInteresMercadoQuerySet(models.QuerySet):
    def serie(self, instrumento, plazo_anios=None, plazo_etiqueta=None, tipo=None):
        """Serie mensual de una tasa, ordenada por fecha.
        - Bonos y PRC: se identifican por plazo_anios.
        - PRBC y captación: por plazo_etiqueta (ej. "30 a 89 días").
        - La captación en pesos y en UF comparten instrumento y plazo: se distinguen con tipo.
        - TPM: sin plazo; trae real (1997-2001) y nominal (2001-) salvo que se pase tipo."""
        filtro = {"instrumento": instrumento, "plazo_anios": plazo_anios, "plazo_etiqueta": plazo_etiqueta}
        if tipo is not None:
            filtro["tipo"] = tipo
        return (
            self.filter(**filtro)
            .order_by("fecha")
            .values("fecha", "valor", "tipo")
        )


class TasaInteresMercado(models.Model):
    """Tasas de interés mensuales del Banco Central (BDE), en porcentaje anual, promedio del mes.
    - TPM desde 1997: REAL (indexada a UF) hasta jul-2001, NOMINAL desde sep-2001 (ago-2001 excluido).
    - Bonos BCP/BTP y BCU/BTU de mercado secundario desde 2002.
    - PRC (UF, 8-20 años) y PRBC (UF, 90 días) de licitación, 1987-2008. Los PRC pagan capital en cuotas:
      un PRC a 20 años se comporta como un bono de menor duración.
    - Captación del sistema financiero en pesos y en UF desde 1982 (tasas de bancos, no del Fisco).
    Una fila por mes y serie; los meses sin dato no se guardan."""

    fecha = models.DateField()                  # primer día del mes
    codigo = models.CharField(max_length=40)    # código BCCh: F022.BUF.TIS.AN10.UF.Z.D
    instrumento = models.CharField(max_length=12, choices=InstrumentoTasa.choices)
    plazo_anios = models.PositiveSmallIntegerField(null=True, blank=True)   # bonos y PRC
    plazo_etiqueta = models.CharField(max_length=30, null=True, blank=True)  # PRBC y captación
    tipo = models.CharField(max_length=10, choices=TipoTasa.choices)
    nombre = models.CharField(max_length=100)   # "Bono en UF a 10 años", "Captación en pesos, 30 a 89 días"
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