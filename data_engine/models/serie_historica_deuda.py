"""
Modelo Django para el dataset "Series Históricas de Deuda" (Ministerio de Hacienda). 

Corresponde al esquema acordado en la sesión de diseño:
    (anio, fecha_corte, tipo_deuda, moneda, monto_millones, pct_pib, es_corte_parcial, fuente)

Notas de diseño (por qué estas decisiones):
- monto_millones y pct_pib usan DecimalField, no FloatField: evita errores de
  redondeo binario en cifras financieras. max_digits=15 cubre montos hasta
  billones de millones (sobra margen); decimal_places=4 preserva la precisión
  observada en la fuente (ej. 74391.19172755352).
- pct_pib es nullable a nivel de fila porque, aunque conceptualmente depende
  solo de (anio, tipo_deuda) y no de la moneda, mantenemos una fila por
  moneda para no complejizar el esquema con una tabla adicional; se espera
  que ambas filas (USD y CLP) del mismo (anio, tipo_deuda) traigan el mismo
  valor de pct_pib.
- unique_together evita duplicados si se reingesta el mismo archivo (o una
  versión actualizada) más de una vez.
- fecha_carga (no estaba en el esquema original, ver justificación en la
  sesión de diseño) permite detectar si Hacienda revisó cifras históricas
  entre una carga y otra, sin sobrescribir silenciosamente el historial.
"""

from django.db import models


class SerieHistoricaDeuda(models.Model):
    class TipoDeuda(models.TextChoices):
        BRUTA = "bruta", "Deuda Bruta"
        NETA = "neta", "Deuda Neta"

    class Moneda(models.TextChoices):
        USD = "usd", "Dólares"
        CLP = "clp", "Pesos Chilenos"

    anio = models.PositiveSmallIntegerField(
        help_text="Año calendario del corte (ej. 2025 para el corte de septiembre 2025)."
    )
    fecha_corte = models.DateField(
        help_text="Fecha exacta del corte, ej. 2025-09-30 o 2024-12-31."
    )
    tipo_deuda = models.CharField(max_length=5, choices=TipoDeuda.choices)
    moneda = models.CharField(max_length=3, choices=Moneda.choices)
    monto_millones = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        help_text="Monto en millones de la moneda correspondiente. Puede ser negativo (deuda neta).",
    )
    pct_pib = models.DecimalField(
        max_digits=8,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Deuda como porcentaje del PIB. Indiferente a la moneda: mismo valor "
                  "esperado para USD y CLP dado el mismo (anio, tipo_deuda).",
    )
    es_corte_parcial = models.BooleanField(
        default=False,
        help_text="True cuando fecha_corte no es el cierre de un año calendario completo "
                  "(ej. el corte más reciente a mitad de período).",
    )
    fuente = models.CharField(
        max_length=100,
        default="hacienda_series_historicas_deuda",   # ← coincide con transform.FUENTE
        help_text="Identificador del dataset de origen.",
    )
    fecha_carga = models.DateTimeField(
        auto_now_add=True,
        help_text="Momento en que esta fila fue ingestada, para detectar revisiones "
                  "de cifras históricas entre cargas sucesivas del mismo archivo.",
    )

    class Meta:
        verbose_name = "Serie Histórica de Deuda"
        verbose_name_plural = "Series Históricas de Deuda"
        ordering = ["anio", "tipo_deuda", "moneda"]
        constraints = [
            models.UniqueConstraint(
                fields=["fecha_corte", "tipo_deuda", "moneda"],
                name="unique_deuda_corte_tipo_moneda",
            )
        ]
        indexes = [
            models.Index(fields=["anio", "tipo_deuda", "moneda"]),
        ]

    def __str__(self):
        return f"{self.anio} · {self.get_tipo_deuda_display()} · {self.get_moneda_display()}"