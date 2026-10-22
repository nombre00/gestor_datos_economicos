from django.db import models


class MedidaCuentaNacional(models.TextChoices):
    NOMINAL = "nominal", "Precios corrientes"
    REAL = "real", "Volumen a precios del año anterior encadenado"


# Claves cortas (2.a parte del código del Banco Central), para no escribirlas a mano
CLAVE_PIB = "PIB"
CLAVE_DEMANDA_INTERNA = "DDI"
CLAVE_CONSUMO_HOGARES = "CPR"
CLAVE_CONSUMO_GOBIERNO = "COG"
CLAVE_FBCF = "FKF"
CLAVE_EXPORTACIONES = "XBS"
CLAVE_IMPORTACIONES = "IBS"


class CuentaNacionalGastoQuerySet(models.QuerySet):
    def serie(self, clave, medida=MedidaCuentaNacional.NOMINAL):
        """Serie anual de un componente del gasto en una medida, ordenada por año."""
        return (
            self.filter(clave=clave, medida=medida)
            .order_by("anio")
            .values("anio", "valor")
        )


class CuentaNacionalGasto(models.Model):
    """Gasto del PIB (Banco Central, cuentas nacionales, series empalmadas referencia 2018),
    anual desde 1996. Tabla larga: una fila por año y serie.
    Valores en miles de millones de pesos.
    OJO: en la medida real (volumen encadenado) los componentes NO suman el PIB."""

    anio = models.PositiveSmallIntegerField()
    codigo = models.CharField(max_length=40)    # código BCCh completo: F033.COG.FLU.N.CLP.EP18.0.T
    clave = models.CharField(max_length=10)     # parte corta del código: COG
    medida = models.CharField(max_length=10, choices=MedidaCuentaNacional.choices)
    nombre = models.CharField(max_length=150)
    nivel = models.PositiveSmallIntegerField()  # 0 = agregado, 1, 2, 3 = más detalle
    orden = models.PositiveSmallIntegerField()  # posición de la fila en el cuadro nominal
    valor = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    fuente = models.CharField(max_length=100, default="bcch_ccnn_gasto_pib")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    objects = CuentaNacionalGastoQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["anio", "codigo"], name="uniq_cuenta_nacional_gasto")
        ]
        indexes = [
            models.Index(fields=["clave", "medida"]),
            models.Index(fields=["anio"]),
        ]

    def __str__(self):
        return f"{self.anio} | {self.clave} | {self.medida}: {self.valor}"