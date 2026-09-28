import pandas as pd

URL_BONOS_LOCALES = "https://www.hacienda.cl/areas-de-trabajo/finanzas-internacionales/oficina-de-la-deuda-publica/estadisticas/caracteristicas-financieras-bonos-locales"


def obtener_tablas_crudas() -> list[pd.DataFrame]:
    """Descarga la página de Bonos Locales y devuelve cada tabla HTML
    tal cual viene, sin limpiar. La limpieza/transformación es responsabilidad
    de la capa de transform, no de esta."""
    return pd.read_html(URL_BONOS_LOCALES)