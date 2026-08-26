"""
utils.py
Capa de datos del dashboard: carga de archivos, limpieza, normalización
geográfica, parsing de moneda y estadística descriptiva.

Principio de diseño (heredado de la app original): esta capa SOLO calcula
con pandas/numpy. La IA (en app.py) nunca toca estos cálculos, solo los
interpreta en lenguaje natural.
"""

import io
import unicodedata
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Columnas esperadas del "Sistema de Registro de Visitantes"
# ---------------------------------------------------------------------------
COLUMNAS_ESPERADAS = [
    "Fecha de la visita",
    "Visitantes adultos",
    "Visitantes niños",
    "Dependencia",
    "Nombre de organización",
    "Tipo de organización",
    "País de procedencia",
    "Departamento",
    "Municipio",
    "Responsable de la visita",
    "Contacto",
    "Ingreso/tarifa",
]

DIAS_ES = {
    "Monday": "Lunes", "Tuesday": "Martes", "Wednesday": "Miércoles",
    "Thursday": "Jueves", "Friday": "Viernes", "Saturday": "Sábado",
    "Sunday": "Domingo",
}
ORDEN_DIAS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]

# Abreviaturas geográficas conocidas en este tipo de formulario.
ABREVIATURAS_DEPARTAMENTO = {"ant": "Antioquia", "cund": "Cundinamarca", "vall": "Valle del Cauca"}
ABREVIATURAS_MUNICIPIO = {"med": "Medellín", "bog": "Bogotá"}


# ---------------------------------------------------------------------------
# Carga robusta de archivos
# ---------------------------------------------------------------------------
def cargar_archivo(archivo_subido):
    """
    Lee un CSV o Excel probando separadores/codificaciones comunes en
    formularios colombianos (';' + latin-1) sin asumir un único formato.
    Devuelve (dataframe, advertencias: list[str]).
    """
    advertencias = []
    nombre = archivo_subido.name.lower()

    if nombre.endswith((".xlsx", ".xls")):
        df = pd.read_excel(archivo_subido)
    else:
        crudo = archivo_subido.read()
        df = None
        intentos = [
            dict(sep=";", encoding="latin-1"),
            dict(sep=";", encoding="utf-8"),
            dict(sep=",", encoding="utf-8"),
            dict(sep=",", encoding="latin-1"),
        ]
        for opciones in intentos:
            try:
                df = pd.read_csv(io.BytesIO(crudo), **opciones)
                if df.shape[1] > 1:  # separador correcto -> más de 1 columna
                    break
            except Exception:
                continue
        if df is None or df.shape[1] <= 1:
            raise ValueError(
                "No fue posible leer el archivo con los separadores/codificaciones "
                "conocidos (';' o ',', UTF-8 o Latin-1)."
            )

    df.columns = [str(c).strip() for c in df.columns]

    faltantes = [c for c in COLUMNAS_ESPERADAS if c not in df.columns]
    if faltantes:
        advertencias.append(
            "El archivo no tiene todas las columnas del formato esperado. "
            f"Faltan: {', '.join(faltantes)}. Algunas secciones del dashboard "
            "podrían no mostrarse."
        )
    return df, advertencias


# ---------------------------------------------------------------------------
# Limpieza y transformación
# ---------------------------------------------------------------------------
def _quitar_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )


def normalizar_texto_geografico(serie: pd.Series, abreviaturas: dict) -> tuple[pd.Series, int]:
    """
    Normaliza una columna de texto (Departamento/Municipio) sin depender de
    una lista fija de nombres oficiales: agrupa variantes que son iguales al
    quitarles tildes y mayúsculas/minúsculas (p. ej. 'Popayán'/'Popayan'),
    expande abreviaturas conocidas ('Ant' -> 'Antioquia') y elige como forma
    canónica la variante más frecuente dentro de cada grupo.
    Devuelve (serie_normalizada, número_de_valores_corregidos).
    """
    original = serie.astype(str).str.strip()

    def expandir(valor):
        clave = _quitar_tildes(valor).lower()
        return abreviaturas.get(clave, valor)

    expandida = original.apply(expandir)
    clave_normalizada = expandida.apply(lambda v: _quitar_tildes(v).lower())

    canonicos = expandida.groupby(clave_normalizada).agg(lambda s: s.value_counts().idxmax())
    resultado = clave_normalizada.map(canonicos)

    cambios = int((resultado != original).sum())
    return resultado, cambios


def parsear_moneda(serie: pd.Series) -> pd.Series:
    """Convierte strings tipo ' $ 130.000 ' (formato colombiano) a float."""
    return (
        serie.astype(str)
        .str.replace(r"[^\d,.\-]", "", regex=True)
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .replace("", np.nan)
        .astype(float)
    )


def preparar_datos(df_crudo: pd.DataFrame, normalizar_geografia: bool = True):
    """
    Aplica toda la limpieza y devuelve (df_limpio, reporte_calidad: dict).
    No lanza excepción si faltan columnas opcionales; se adapta.
    """
    df = df_crudo.copy()
    df.columns = [str(c).strip() for c in df.columns]
    reporte = {"correcciones_geograficas": 0, "filas_duplicadas": 0, "filas_totales": len(df)}

    reporte["filas_duplicadas"] = int(df.duplicated().sum())

    if "Fecha de la visita" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha de la visita"], format="%d/%m/%Y", errors="coerce")
        if df["Fecha"].isna().any():
            df["Fecha"] = df["Fecha"].fillna(
                pd.to_datetime(df["Fecha de la visita"], errors="coerce")
            )
        df["Día de semana"] = df["Fecha"].dt.day_name().map(DIAS_ES)

    for col in ["Visitantes adultos", "Visitantes niños"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if {"Visitantes adultos", "Visitantes niños"}.issubset(df.columns):
        df["Total visitantes"] = df["Visitantes adultos"] + df["Visitantes niños"]

    if "Ingreso/tarifa" in df.columns:
        df["Ingreso"] = parsear_moneda(df["Ingreso/tarifa"])

    if normalizar_geografia:
        for col, abrevs in [
            ("Departamento", ABREVIATURAS_DEPARTAMENTO),
            ("Municipio", ABREVIATURAS_MUNICIPIO),
        ]:
            if col in df.columns:
                df[col], cambios = normalizar_texto_geografico(df[col].fillna(""), abrevs)
                reporte["correcciones_geograficas"] += cambios

    for col in ["Nombre de organización", "Tipo de organización", "Departamento", "Municipio", "Responsable de la visita"]:
        if col in df.columns:
            df[col] = df[col].replace("", np.nan)

    reporte["valores_nulos"] = df[COLUMNAS_ESPERADAS].isna().sum().to_dict() if not faltan_columnas(df) else df.isna().sum().to_dict()
    return df, reporte


def faltan_columnas(df: pd.DataFrame) -> bool:
    return any(c not in df.columns for c in COLUMNAS_ESPERADAS)


# ---------------------------------------------------------------------------
# Estadística descriptiva (idéntica en espíritu a la app original)
# ---------------------------------------------------------------------------
def estadisticas_descriptivas(datos: pd.Series) -> dict:
    datos = datos.dropna()
    if datos.empty:
        return {}
    return {
        "Media": round(datos.mean(), 2),
        "Mediana": round(datos.median(), 2),
        "Desviación estándar": round(datos.std(), 2),
        "Mínimo": round(datos.min(), 2),
        "Máximo": round(datos.max(), 2),
        "Q1 (25%)": round(datos.quantile(0.25), 2),
        "Q3 (75%)": round(datos.quantile(0.75), 2),
        "Percentil 90": round(datos.quantile(0.90), 2),
    }


def detectar_outliers_iqr(datos: pd.Series):
    """Regla de Tukey (1.5 * IQR). Devuelve (mascara_outliers, limite_inf, limite_sup)."""
    datos_validos = datos.dropna()
    q1, q3 = datos_validos.quantile([0.25, 0.75])
    iqr = q3 - q1
    lim_inf, lim_sup = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    mascara = (datos < lim_inf) | (datos > lim_sup)
    return mascara.fillna(False), lim_inf, lim_sup
