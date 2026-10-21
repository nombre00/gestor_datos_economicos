from django.db import models


class UnidadEstadoOperaciones(models.TextChoices):
    NOMINAL = "nominal", "Millones de pesos de cada año"
    REAL = "real", "Millones de pesos reales (de anio_base)"
    PCT_PIB = "pct_pib", "Porcentaje del PIB"


# Conceptos clave, para no escribir la ruta a mano en otras partes del código
CONCEPTO_TOTAL_INGRESOS = "TOTAL INGRESOS"
CONCEPTO_TOTAL_GASTOS = "TOTAL GASTOS"
CONCEPTO_BALANCE = "PRESTAMO NETO/ENDEUDAMIENTO NETO"
CONCEPTO_INTERESES = "GASTOS > Intereses"


class EstadoOperacionesQuerySet(models.QuerySet):
    def serie(self, concepto, unidad=UnidadEstadoOperaciones.PCT_PIB):
        """Serie anual de un concepto en una unidad, ordenada por año."""
        return (
            self.filter(concepto=concepto, unidad=unidad)
            .order_by("anio")
            .values("anio", "valor")
        )


class EstadoOperacionesGobiernoCentral(models.Model):
    """Estado de Operaciones del Gobierno Central Total (DIPRES), anual desde 1990.
    Tabla larga: una fila por año, concepto y unidad.
    OJO: en pct_pib el valor está en PORCENTAJE (22,19 = 22,19% del PIB), tal como lo
    publica la DIPRES; distinto de SerieHistoricaDeuda.pct_pib, que guarda fracción."""

    anio = models.PositiveSmallIntegerField()
    concepto = models.CharField(max_length=255)   # ruta jerárquica: "GASTOS > Intereses"
    nombre = models.CharField(max_length=150)     # último tramo de la ruta: "Intereses"
    nivel = models.PositiveSmallIntegerField()    # 0 = total, 1, 2, 3 = más detalle
    orden = models.PositiveSmallIntegerField()    # posición de la fila en el cuadro original
    unidad = models.CharField(max_length=10, choices=UnidadEstadoOperaciones.choices)
    anio_base = models.PositiveSmallIntegerField(null=True, blank=True)  # solo para unidad real
    valor = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True)

    fuente = models.CharField(max_length=100, default="dipres_estado_operaciones_gct")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    objects = EstadoOperacionesQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["anio", "concepto", "unidad"], name="uniq_estado_operaciones_gct"
            )
        ]
        indexes = [
            models.Index(fields=["concepto", "unidad"]),
            models.Index(fields=["anio"]),
        ]

    def __str__(self):
        return f"{self.anio} | {self.concepto} | {self.unidad}: {self.valor}"