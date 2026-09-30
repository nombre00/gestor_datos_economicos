from django.db import models


class TipoInstrumento(models.TextChoices):
    BTP = "btp", "Bono de Tesorería en Pesos"
    BTU = "btu", "Bono de Tesorería en UF"
    LETRA = "letra", "Letra del Tesoro"

    @property
    def moneda_unidad(self) -> str:
        """Derivado, no persistido: BTU se mide en UF, el resto en CLP."""
        return "uf" if self == TipoInstrumento.BTU else "clp"


class Status(models.TextChoices):
    VIGENTE = "vigente", "Vigente"
    VENCIDO = "vencido", "Vencido"


class BonoLocal(models.Model):
    nombre_bono = models.CharField(max_length=100)
    anio = models.PositiveSmallIntegerField()
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    es_reapertura = models.BooleanField(default=False)

    tipo_instrumento = models.CharField(max_length=10, choices=TipoInstrumento.choices)

    madurez_anios = models.PositiveSmallIntegerField(null=True, blank=True)
    monto_emitido = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)
    monto_colocado = models.DecimalField(max_digits=18, decimal_places=6, null=True, blank=True)

    tasa_caratula = models.DecimalField(max_digits=8, decimal_places=4)
    paga_intereses_raw = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)

    fuente = models.CharField(max_length=100, default="hacienda_bonos_locales")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["nombre_bono", "fecha_emision", "fecha_vencimiento", "anio"],
                name="uniq_bono_local",
            )
        ]
        indexes = [
            models.Index(fields=["fecha_emision"]),
            models.Index(fields=["tipo_instrumento"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.nombre_bono} ({self.fecha_emision})"