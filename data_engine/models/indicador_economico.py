from django.db import models


class Indicador(models.TextChoices):
    UF = "uf", "Unidad de Fomento"
    DOLAR = "dolar", "Dólar observado"
    EURO = "euro", "Euro"


class IndicadorEconomicoQuerySet(models.QuerySet):
    def valor_al(self, indicador, fecha):
        """Último valor publicado en o antes de `fecha`.
        El dólar y el euro no se publican fines de semana ni festivos, por eso no
        se busca la fecha exacta. Devuelve el objeto (o None) para que quien lo use
        sepa qué fecha se aplicó realmente."""
        return (
            self.filter(indicador=indicador, fecha__lte=fecha)
            .order_by("-fecha")
            .first()
        )

    def ultimo(self, indicador):
        return self.filter(indicador=indicador).order_by("-fecha").first()


class IndicadorEconomico(models.Model):
    indicador = models.CharField(max_length=10, choices=Indicador.choices)
    fecha = models.DateField()
    valor = models.DecimalField(max_digits=12, decimal_places=2)  # pesos chilenos

    fuente = models.CharField(max_length=50, default="mindicador")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    objects = IndicadorEconomicoQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["indicador", "fecha"], name="uniq_indicador_fecha")
        ]
        indexes = [models.Index(fields=["indicador", "fecha"])]

    def __str__(self):
        return f"{self.indicador} {self.fecha}: {self.valor}"