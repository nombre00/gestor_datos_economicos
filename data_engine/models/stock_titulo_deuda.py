from django.db import models


class Instrumento(models.TextChoices):
    # Intermediación Financiera (plazo <= 365 días)
    PAGARES_BANCO_CENTRAL = "pagares_banco_central", "Pagarés de Banco Central"
    CERTIFICADOS_DEPOSITO_PLAZO = "certificados_deposito_plazo", "Certificados de depósitos a plazo"
    EFECTOS_COMERCIO = "efectos_comercio", "Efectos de comercio"
    # Renta Fija (plazo > 365 días)
    BONOS_BANCO_CENTRAL = "bonos_banco_central", "Bonos de Banco Central"
    BONOS_BANCOS_COOPERATIVAS = "bonos_bancos_cooperativas", "Bonos de Bancos y cooperativas"
    BONOS_OTROS_INTERMEDIARIOS_FINANCIEROS = "bonos_otros_intermediarios_financieros", "Bonos de Otros intermediarios financieros"
    BONOS_EMPRESAS_NO_FINANCIERAS = "bonos_empresas_no_financieras", "Bonos de Empresas no financieras"
    BONOS_GOBIERNO_GENERAL = "bonos_gobierno_general", "Bonos de Gobierno general"
    BONOS_NO_RESIDENTES = "bonos_no_residentes", "Bonos de No residentes (Mercado local)"

    @property
    def sector_emisor(self) -> str:
        """Derivado, no persistido: de qué bloque del Excel viene el instrumento."""
        intermediacion_financiera = {
            Instrumento.PAGARES_BANCO_CENTRAL,
            Instrumento.CERTIFICADOS_DEPOSITO_PLAZO,
            Instrumento.EFECTOS_COMERCIO,
        }
        return "intermediacion_financiera" if self in intermediacion_financiera else "renta_fija"


class Tenedor(models.TextChoices):
    BANCO_CENTRAL = "banco_central", "Banco Central"
    BANCOS_COOPERATIVAS = "bancos_cooperativas", "Bancos y cooperativas"
    FONDOS_MUTUOS_INVERSION = "fondos_mutuos_inversion", "Fondos mutuos y de inversión"
    OTROS_INTERMEDIARIOS_FINANCIEROS = "otros_intermediarios_financieros", "Otros intermediarios financieros"
    FONDOS_PENSIONES = "fondos_pensiones", "Fondos de pensiones"
    COMPANIAS_SEGUROS = "companias_seguros", "Compañías de seguros"
    GOBIERNO_GENERAL = "gobierno_general", "Gobierno general"
    OTROS_SECTORES_RESIDENTES = "otros_sectores_residentes", "Otros sectores residentes"
    INVERSIONISTAS_EXTRANJEROS = "inversionistas_extranjeros", "Inversionistas extranjeros"


class TipoFila(models.TextChoices):
    TOTAL_INSTRUMENTO = "total_instrumento", "Total del instrumento"
    TENEDOR = "tenedor", "Detalle por tenedor"
    SUBCONJUNTO = "subconjunto", "Subconjunto no aditivo (ej. Comprado en el ML)"


class StockTituloDeudaQuerySet(models.QuerySet):
    def tenedores_reales(self):
        """Excluye TOTAL_INSTRUMENTO y SUBCONJUNTO — solo filas de tenedor
        que se pueden sumar sin inflar el total."""
        return self.filter(tipo_fila=TipoFila.TENEDOR)

    def fin_de_anio(self):
        """Solo trimestre IV — comparable con los datasets anuales de Hacienda.
        Un año en curso (sin trimestre IV publicado aún) simplemente no aparece."""
        return self.filter(trimestre=4)

    def total_por_instrumento(self, instrumento: str, anio: int, trimestre: int):
        """Suma los tenedores reales de un instrumento en un período específico.
        Sirve también como chequeo cruzado contra la fila TOTAL_INSTRUMENTO ya guardada."""
        return self.tenedores_reales().filter(
            instrumento=instrumento, anio=anio, trimestre=trimestre
        ).aggregate(total=models.Sum("monto_miles_millones_clp"))["total"]


class StockTituloDeudaManager(models.Manager):
    def get_queryset(self):
        return StockTituloDeudaQuerySet(self.model, using=self._db)

    def tenedores_reales(self):
        return self.get_queryset().tenedores_reales()

    def fin_de_anio(self):
        return self.get_queryset().fin_de_anio()

    def total_por_instrumento(self, instrumento: str, anio: int, trimestre: int):
        return self.get_queryset().total_por_instrumento(instrumento, anio, trimestre)


class StockTituloDeuda(models.Model):
    instrumento = models.CharField(max_length=50, choices=Instrumento.choices)
    tenedor = models.CharField(max_length=50, choices=Tenedor.choices, null=True, blank=True)
    tipo_fila = models.CharField(max_length=20, choices=TipoFila.choices)

    anio = models.PositiveSmallIntegerField()
    trimestre = models.PositiveSmallIntegerField()  # 1-4
    fecha_corte = models.DateField()

    monto_miles_millones_clp = models.DecimalField(max_digits=18, decimal_places=6)

    fuente = models.CharField(max_length=100, default="bcentral_emv_4")
    fecha_carga = models.DateTimeField(auto_now_add=True)

    objects = StockTituloDeudaManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["instrumento", "tenedor", "tipo_fila", "anio", "trimestre"],
                name="uniq_stock_titulo_deuda",
            )
        ]
        indexes = [
            models.Index(fields=["anio", "trimestre"]),
            models.Index(fields=["instrumento", "tenedor"]),
        ]

    def __str__(self):
        tenedor_str = self.get_tenedor_display() if self.tenedor else "(total instrumento)"
        return f"{self.get_instrumento_display()} / {tenedor_str} — {self.anio}-{self.trimestre}"