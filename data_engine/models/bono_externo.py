from django.db import models


class Moneda(models.TextChoices):
    USD = "usd", "Dólar estadounidense"
    EUR = "eur", "Euro"
    CLP = "clp", "Peso chileno"


class PagoIntereses(models.TextChoices):
    SEMESTRAL = "semestral", "Semestral"
    TRIMESTRAL = "trimestral", "Trimestral"
    ANUAL = "anual", "Anual"


class Vigencia(models.TextChoices):
    VIGENTE = "vigente", "Vigente"
    VENCIDO = "vencido", "Vencido y pagado"


class BonoExterno(models.Model):
    nombre_bono = models.CharField(max_length=100)
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    es_reapertura = models.BooleanField(default=False)

    moneda = models.CharField(max_length=10, choices=Moneda.choices)
    monto = models.DecimalField(max_digits=18, decimal_places=6)

    tasa_caratula_raw = models.CharField(max_length=100)
    tasa_caratula_fija = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    tasa_bono_tesoro = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)
    tasa_local_tesoro_chile = models.DecimalField(max_digits=8, decimal_places=4, null=True, blank=True)

    precio = models.DecimalField(max_digits=8, decimal_places=4)
    yield_emision = models.DecimalField(max_digits=8, decimal_places=4)

    spread_caratula = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    spread_nota_referencia = models.CharField(max_length=20, null=True, blank=True)

    pago_intereses = models.CharField(max_length=20, choices=PagoIntereses.choices)
    vigencia = models.CharField(max_length=20, choices=Vigencia.choices)

    fuente = models.CharField(max_length=100, default="hacienda_bonos_externos")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["nombre_bono", "fecha_emision"], name="uniq_bono_externo")
        ]
        indexes = [
            models.Index(fields=["fecha_emision"]),
            models.Index(fields=["vigencia"]),
        ]

    def __str__(self):
        return f"{self.nombre_bono} ({self.fecha_emision})"