import io
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_option_menu import option_menu

from utils import (
    ABREVIATURAS_DEPARTAMENTO,
    ABREVIATURAS_MUNICIPIO,
    DIAS_ES,
    ORDEN_DIAS,
    cargar_archivo,
    detectar_outliers_iqr,
    estadisticas_descriptivas,
    faltan_columnas,
    preparar_datos,
)

# ---------------------------------------------------------------------------
# Configuración de página y estilo
# ---------------------------------------------------------------------------
st.set_page_config(page_title="YACH-AI · Dashboard de Visitantes", page_icon="🏛️", layout="wide")

PALETA = ["#C9A227", "#2E86AB", "#E0693E", "#6FB98F", "#8E6C9C", "#4C5B7A"]
COLOR_NAVY = "#101B34"
COLOR_GOLD = "#C9A227"
COLOR_TEAL = "#2E86AB"
COLOR_CORAL = "#E0693E"

st.markdown(
    f"""
    <style>
    section[data-testid="stSidebar"] {{
        background-color: {COLOR_NAVY};
    }}
    section[data-testid="stSidebar"] * {{
        color: #E7EAF2 !important;
    }}
    section[data-testid="stSidebar"] .stButton button {{
        background-color: {COLOR_GOLD};
        color: {COLOR_NAVY} !important;
        border: none;
        font-weight: 600;
        width: 100%;
    }}
    div[data-testid="stMetric"], .kpi-card {{
        background: #FFFFFF;
        border-radius: 10px;
        padding: 16px 18px;
        box-shadow: 0 1px 4px rgba(16,27,52,0.10);
        border-left: 5px solid {COLOR_GOLD};
    }}
    .kpi-title {{
        font-size: 0.78rem;
        color: #6B7280;
        text-transform: uppercase;
        letter-spacing: .04em;
    }}
    .kpi-value {{
        font-size: 1.7rem;
        font-weight: 700;
        color: {COLOR_NAVY};
        margin-top: 2px;
    }}
    .kpi-sub {{
        font-size: 0.75rem;
        color: #8A93A6;
        margin-top: 2px;
    }}
    h1, h2, h3 {{
        color: {COLOR_NAVY};
    }}
    .bloque-ia {{
        background: #FBF7EC;
        border: 1px solid {COLOR_GOLD};
        border-radius: 10px;
        padding: 18px 20px;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Helpers de presentación
# ---------------------------------------------------------------------------
def formatear_cop(valor):
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return "—"
    return f"$ {valor:,.0f}".replace(",", ".")


def tarjeta_kpi_html(titulo, valor, sub="", color=COLOR_GOLD):
    return f"""
    <div class="kpi-card" style="border-left-color:{color}">
        <div class="kpi-title">{titulo}</div>
        <div class="kpi-value">{valor}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """


def fila_kpis(items):
    cols = st.columns(len(items))
    for col, (titulo, valor, sub, color) in zip(cols, items):
        with col:
            st.markdown(tarjeta_kpi_html(titulo, valor, sub, color), unsafe_allow_html=True)


def estilizar(fig, altura=380):
    fig.update_layout(
        colorway=PALETA,
        font=dict(family="Segoe UI, sans-serif", color=COLOR_NAVY),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=10, r=10, t=40, b=10),
        height=altura,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    return fig


def tabla_estadisticas(datos, titulo):
    stats = estadisticas_descriptivas(datos)
    if not stats:
        st.info("No hay datos suficientes para calcular estadísticas.")
        return
    st.markdown(f"**{titulo}**")
    st.table(pd.DataFrame(stats.items(), columns=["Medida", "Valor"]))


# ---------------------------------------------------------------------------
# Capa de IA (solo interpreta; nunca calcula)
# ---------------------------------------------------------------------------
def obtener_cliente_ia():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key)
    except Exception:
        return None


def generar_texto_ia(cliente, prompt):
    respuesta = cliente.models.generate_content(model="gemini-flash-latest", contents=prompt)
    return respuesta.text


# ---------------------------------------------------------------------------
# Sidebar: carga de archivo
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🏛️ YACH-AI")
    st.caption("Dashboard descriptivo con interpretación de IA")
    archivo = st.file_uploader("Sube tu archivo de visitantes", type=["csv", "xlsx"])
    normalizar_geo = True
    if archivo is not None:
        normalizar_geo = st.checkbox(
            "Normalizar Departamento / Municipio",
            value=True,
            help="Agrupa variantes como 'Bog'/'Bogotá'/'bogotá' en un único valor.",
        )

if archivo is None:
    st.title("YACH-AI · Dashboard de Visitantes de Museo")
    st.write(
        "Sube el archivo CSV o Excel del Sistema de Registro de Visitantes en la "
        "barra lateral para comenzar. El dashboard incluye:"
    )
    st.markdown(
        "- 📊 **Resumen general** — KPIs y tendencias de afluencia\n"
        "- 👥 **Visitantes** — estadística descriptiva, outliers y correlaciones\n"
        "- 🌎 **Procedencia** — país, departamento y municipio\n"
        "- 💰 **Ingresos** — tarifas y tendencia de recaudo\n"
        "- 🏢 **Organizaciones** — tipo de organización y dependencias\n"
        "- 🧹 **Calidad de datos** — completitud y correcciones aplicadas\n"
        "- 🤖 **Interpretación IA** — lectura en lenguaje natural de los números\n"
        "- 📁 **Datos y exportación** — tabla filtrable y descarga"
    )
    st.stop()

# ---------------------------------------------------------------------------
# Carga y preparación (cacheada por contenido del archivo)
# ---------------------------------------------------------------------------
@st.cache_data(show_spinner="Procesando archivo...")
def procesar(contenido: bytes, nombre: str, normalizar: bool):
    envoltorio = io.BytesIO(contenido)
    envoltorio.name = nombre
    df_crudo, advertencias = cargar_archivo(envoltorio)
    df_limpio, reporte = preparar_datos(df_crudo, normalizar_geografia=normalizar)
    return df_crudo, df_limpio, reporte, advertencias


contenido_archivo = archivo.getvalue()
try:
    df_crudo, df, reporte_calidad, advertencias = procesar(contenido_archivo, archivo.name, normalizar_geo)
except Exception as e:
    st.error(f"No fue posible procesar el archivo: {e}")
    st.stop()

for adv in advertencias:
    st.warning(adv)

# ---------------------------------------------------------------------------
# Sidebar: navegación y filtros
# ---------------------------------------------------------------------------
with st.sidebar:
    st.divider()
    pagina = option_menu(
        menu_title=None,
        options=[
            "Resumen general", "Visitantes", "Procedencia", "Ingresos",
            "Organizaciones", "Calidad de datos", "Interpretación IA", "Datos y exportación",
        ],
        icons=[
            "speedometer2", "people-fill", "globe-americas", "cash-coin",
            "building", "clipboard-check", "robot", "table",
        ],
        default_index=0,
        styles={
            "container": {"padding": "0", "background-color": "transparent"},
            "icon": {"color": COLOR_GOLD, "font-size": "15px"},
            "nav-link": {"font-size": "13.5px", "text-align": "left", "margin": "2px", "color": "#E7EAF2"},
            "nav-link-selected": {"background-color": COLOR_GOLD, "color": COLOR_NAVY},
        },
    )
    st.divider()
    st.markdown("**Filtros**")

    tiene_fecha = "Fecha" in df.columns and df["Fecha"].notna().any()
    if tiene_fecha:
        f_min, f_max = df["Fecha"].min().date(), df["Fecha"].max().date()
        rango_fechas = st.date_input(
            "Rango de fechas", value=(f_min, f_max), min_value=f_min, max_value=f_max, key="filtro_fechas"
        )
    else:
        rango_fechas = None

    def opciones(col):
        return sorted(df[col].dropna().unique().tolist()) if col in df.columns else []

    dep_sel = st.multiselect("Dependencia", opciones("Dependencia"), key="filtro_dependencia")
    pais_sel = st.multiselect("País de procedencia", opciones("País de procedencia"), key="filtro_pais")
    depto_sel = st.multiselect("Departamento", opciones("Departamento"), key="filtro_departamento")

    if st.button("🔄 Reiniciar filtros"):
        for k in ["filtro_fechas", "filtro_dependencia", "filtro_pais", "filtro_departamento"]:
            st.session_state.pop(k, None)
        st.rerun()

# Aplicar filtros
df_f = df.copy()
if tiene_fecha and isinstance(rango_fechas, tuple) and len(rango_fechas) == 2:
    ini, fin = pd.to_datetime(rango_fechas[0]), pd.to_datetime(rango_fechas[1])
    df_f = df_f[(df_f["Fecha"] >= ini) & (df_f["Fecha"] <= fin)]
if dep_sel:
    df_f = df_f[df_f["Dependencia"].isin(dep_sel)]
if pais_sel:
    df_f = df_f[df_f["País de procedencia"].isin(pais_sel)]
if depto_sel:
    df_f = df_f[df_f["Departamento"].isin(depto_sel)]

if df_f.empty:
    st.warning("No hay registros que coincidan con los filtros seleccionados.")
    st.stop()

# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------
st.markdown(f"### {pagina}")
st.caption(f"{len(df_f):,} registros filtrados de {len(df):,} totales".replace(",", "."))

variables_numericas = [c for c in ["Visitantes adultos", "Visitantes niños", "Total visitantes", "Ingreso"] if c in df_f.columns]

# ===========================================================================
# PÁGINA: Resumen general
# ===========================================================================
if pagina == "Resumen general":
    total_visitas = len(df_f)
    total_visitantes = int(df_f["Total visitantes"].sum()) if "Total visitantes" in df_f else 0
    ingreso_total = df_f["Ingreso"].sum() if "Ingreso" in df_f else np.nan
    promedio_grupo = df_f["Total visitantes"].mean() if "Total visitantes" in df_f else np.nan
    pct_intl = (
        100 * df_f.loc[df_f["País de procedencia"] != "Colombia", "Total visitantes"].sum() / total_visitantes
        if total_visitantes and "País de procedencia" in df_f else 0
    )

    fila_kpis([
        ("Total de visitas", f"{total_visitas:,}".replace(",", "."), "registros en el periodo", COLOR_GOLD),
        ("Total visitantes", f"{total_visitantes:,}".replace(",", "."), "adultos + niños", COLOR_TEAL),
        ("Ingreso total", formatear_cop(ingreso_total), "tarifas recaudadas", COLOR_CORAL),
        ("Promedio por visita", f"{promedio_grupo:,.1f}".replace(",", "."), "visitantes/registro", "#6FB98F"),
        ("Visitantes internacionales", f"{pct_intl:.1f}%", "del total de visitantes", "#8E6C9C"),
    ])

    st.write("")
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Afluencia por día")
        if tiene_fecha:
            serie = df_f.groupby(df_f["Fecha"].dt.date).agg(
                visitas=("Fecha", "count"), visitantes=("Total visitantes", "sum")
            ).reset_index()
            fig = go.Figure()
            fig.add_bar(x=serie["Fecha"], y=serie["visitas"], name="Nº de visitas", marker_color=COLOR_GOLD)
            fig.add_trace(go.Scatter(x=serie["Fecha"], y=serie["visitantes"], name="Total visitantes",
                                      yaxis="y2", mode="lines+markers", line=dict(color=COLOR_NAVY)))
            fig.update_layout(yaxis=dict(title="Nº de visitas"), yaxis2=dict(title="Visitantes", overlaying="y", side="right"))
            st.plotly_chart(estilizar(fig), width="stretch")
        else:
            st.info("El archivo no tiene columna de fecha reconocible.")

    with c2:
        st.subheader("Visitas por día de la semana")
        if tiene_fecha:
            conteo = df_f["Día de semana"].value_counts().reindex(ORDEN_DIAS).fillna(0)
            fig = px.bar(x=conteo.index, y=conteo.values, labels={"x": "", "y": "Nº de visitas"})
            st.plotly_chart(estilizar(fig), width="stretch")

    c3, c4 = st.columns(2)
    with c3:
        st.subheader("Visitantes por dependencia")
        if "Dependencia" in df_f.columns:
            g = df_f.groupby("Dependencia")["Total visitantes"].sum().sort_values(ascending=True)
            fig = px.bar(g, x=g.values, y=g.index, orientation="h", labels={"x": "Total visitantes", "y": ""})
            st.plotly_chart(estilizar(fig), width="stretch")

    with c4:
        st.subheader("Top 5 organizaciones por visitantes")
        if "Nombre de organización" in df_f.columns:
            top = (
                df_f.dropna(subset=["Nombre de organización"])
                .groupby("Nombre de organización")["Total visitantes"].sum()
                .sort_values(ascending=False).head(5).reset_index()
            )
            if top.empty:
                st.info("No hay organizaciones identificadas en los registros filtrados.")
            else:
                st.table(top.rename(columns={"Nombre de organización": "Organización", "Total visitantes": "Visitantes"}))

# ===========================================================================
# PÁGINA: Visitantes
# ===========================================================================
elif pagina == "Visitantes":
    variable = st.selectbox("Variable a analizar en detalle", variables_numericas)
    datos = df_f[variable].dropna()

    col1, col2 = st.columns([1, 2])
    with col1:
        tabla_estadisticas(datos, f"Estadísticas — {variable}")
    with col2:
        fig = px.histogram(datos, nbins=15, labels={"value": variable})
        fig.update_layout(showlegend=False)
        st.plotly_chart(estilizar(fig, 300), width="stretch")

    st.subheader("Diagrama de caja (boxplot)")
    fig_box = px.box(datos, points="outliers", labels={"value": variable})
    fig_box.update_layout(showlegend=False)
    st.plotly_chart(estilizar(fig_box, 220), width="stretch")

    st.subheader("Valores atípicos (regla 1.5×IQR)")
    mascara, lim_inf, lim_sup = detectar_outliers_iqr(df_f[variable])
    n_outliers = int(mascara.sum())
    st.caption(f"Rango típico: [{lim_inf:.1f}, {lim_sup:.1f}] · {n_outliers} registro(s) fuera de rango")
    if n_outliers:
        cols_mostrar = [c for c in ["Fecha de la visita", "Dependencia", "Nombre de organización", variable] if c in df_f.columns]
        st.dataframe(df_f.loc[mascara, cols_mostrar], width="stretch", hide_index=True)

    if {"Visitantes adultos", "Visitantes niños"}.issubset(df_f.columns):
        st.subheader("Relación adultos vs. niños por visita")
        color_col = "Dependencia" if "Dependencia" in df_f.columns else None
        fig_sc = px.scatter(
            df_f, x="Visitantes adultos", y="Visitantes niños", size="Total visitantes",
            color=color_col, hover_data=["Fecha de la visita"] if "Fecha de la visita" in df_f.columns else None,
        )
        st.plotly_chart(estilizar(fig_sc, 400), width="stretch")

    cols_corr = [c for c in variables_numericas if c in df_f.columns]
    if len(cols_corr) >= 2:
        st.subheader("Correlación entre variables numéricas")
        corr = df_f[cols_corr].corr().round(2)
        fig_corr = px.imshow(corr, text_auto=True, color_continuous_scale=["#F4F5F9", COLOR_TEAL, COLOR_NAVY])
        st.plotly_chart(estilizar(fig_corr, 350), width="stretch")

# ===========================================================================
# PÁGINA: Procedencia
# ===========================================================================
elif pagina == "Procedencia":
    if "País de procedencia" in df_f.columns:
        total_v = df_f["Total visitantes"].sum() if "Total visitantes" in df_f else len(df_f)
        pct_nacional = 100 * df_f.loc[df_f["País de procedencia"] == "Colombia", "Total visitantes"].sum() / total_v if total_v else 0
        fila_kpis([
            ("Países de origen", f"{df_f['País de procedencia'].nunique()}", "distintos", COLOR_GOLD),
            ("Visitantes nacionales", f"{pct_nacional:.1f}%", "de Colombia", COLOR_TEAL),
            ("Visitantes internacionales", f"{100 - pct_nacional:.1f}%", "de otros países", COLOR_CORAL),
        ])

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Distribución por país")
        if "País de procedencia" in df_f.columns:
            g = df_f.groupby("País de procedencia")["Total visitantes"].sum().reset_index()
            fig = px.pie(g, names="País de procedencia", values="Total visitantes", hole=0.55)
            st.plotly_chart(estilizar(fig, 380), width="stretch")
    with c2:
        st.subheader("Top 10 departamentos")
        if "Departamento" in df_f.columns:
            g = df_f.groupby("Departamento")["Total visitantes"].sum().sort_values(ascending=False).head(10)
            fig = px.bar(g, x=g.index, y=g.values, labels={"x": "", "y": "Total visitantes"})
            st.plotly_chart(estilizar(fig, 380), width="stretch")

    st.subheader("Departamento → Municipio")
    if {"Departamento", "Municipio"}.issubset(df_f.columns):
        g = df_f.groupby(["Departamento", "Municipio"])["Total visitantes"].sum().reset_index()
        fig = px.treemap(g, path=["Departamento", "Municipio"], values="Total visitantes",
                          color="Total visitantes", color_continuous_scale=["#F4F5F9", COLOR_GOLD, COLOR_NAVY])
        st.plotly_chart(estilizar(fig, 420), width="stretch")

# ===========================================================================
# PÁGINA: Ingresos
# ===========================================================================
elif pagina == "Ingresos":
    if "Ingreso" not in df_f.columns:
        st.warning("El archivo no tiene una columna de ingreso/tarifa reconocible.")
    else:
        ingreso_total = df_f["Ingreso"].sum()
        ingreso_prom_visita = df_f["Ingreso"].mean()
        ingreso_prom_visitante = ingreso_total / df_f["Total visitantes"].sum() if "Total visitantes" in df_f and df_f["Total visitantes"].sum() else np.nan
        fila_kpis([
            ("Ingreso total", formatear_cop(ingreso_total), "periodo filtrado", COLOR_GOLD),
            ("Promedio por visita", formatear_cop(ingreso_prom_visita), "tarifa promedio", COLOR_TEAL),
            ("Promedio por visitante", formatear_cop(ingreso_prom_visitante), "ingreso/persona", COLOR_CORAL),
            ("Tarifa máxima", formatear_cop(df_f["Ingreso"].max()), "en una sola visita", "#6FB98F"),
        ])

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Ingreso por día")
            if tiene_fecha:
                serie = df_f.groupby(df_f["Fecha"].dt.date)["Ingreso"].sum().reset_index()
                fig = px.area(serie, x="Fecha", y="Ingreso")
                st.plotly_chart(estilizar(fig), width="stretch")
        with c2:
            st.subheader("Ingreso por dependencia")
            if "Dependencia" in df_f.columns:
                g = df_f.groupby("Dependencia")["Ingreso"].sum().sort_values(ascending=True)
                fig = px.bar(g, x=g.values, y=g.index, orientation="h", labels={"x": "Ingreso", "y": ""})
                st.plotly_chart(estilizar(fig), width="stretch")

        col1, col2 = st.columns([1, 2])
        with col1:
            tabla_estadisticas(df_f["Ingreso"], "Estadísticas — Ingreso")
        with col2:
            fig = px.box(df_f, x="Ingreso", points="outliers")
            st.plotly_chart(estilizar(fig, 260), width="stretch")

        if "Total visitantes" in df_f.columns:
            st.subheader("Relación tamaño del grupo vs. ingreso")
            fig = px.scatter(df_f, x="Total visitantes", y="Ingreso",
                              color="Dependencia" if "Dependencia" in df_f.columns else None)
            st.plotly_chart(estilizar(fig, 380), width="stretch")

# ===========================================================================
# PÁGINA: Organizaciones
# ===========================================================================
elif pagina == "Organizaciones":
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Tipo de organización")
        if "Tipo de organización" in df_f.columns:
            serie = df_f["Tipo de organización"].fillna("No especificado").value_counts()
            fig = px.pie(names=serie.index, values=serie.values, hole=0.55)
            st.plotly_chart(estilizar(fig, 360), width="stretch")
    with c2:
        st.subheader("Visitas por dependencia")
        if "Dependencia" in df_f.columns:
            serie = df_f["Dependencia"].value_counts()
            fig = px.bar(x=serie.index, y=serie.values, labels={"x": "", "y": "Nº de visitas"})
            st.plotly_chart(estilizar(fig, 360), width="stretch")

    st.subheader("Organizaciones con mayor ingreso")
    if {"Nombre de organización", "Ingreso"}.issubset(df_f.columns):
        top = (
            df_f.dropna(subset=["Nombre de organización"])
            .groupby("Nombre de organización")
            .agg(Visitas=("Nombre de organización", "count"), Visitantes=("Total visitantes", "sum"), Ingreso=("Ingreso", "sum"))
            .sort_values("Ingreso", ascending=False).head(10).reset_index()
        )
        top["Ingreso"] = top["Ingreso"].apply(formatear_cop)
        st.dataframe(top, width="stretch", hide_index=True)
    else:
        st.info("No hay suficientes datos de organización/ingreso en los registros filtrados.")

    if "Nombre de organización" in df_f.columns:
        pct_sin_nombre = 100 * df_f["Nombre de organización"].isna().mean()
        st.caption(f"{pct_sin_nombre:.1f}% de los registros filtrados no tienen organización identificada "
                   "(probablemente visitantes individuales).")

# ===========================================================================
# PÁGINA: Calidad de datos
# ===========================================================================
elif pagina == "Calidad de datos":
    fila_kpis([
        ("Filas totales", f"{reporte_calidad['filas_totales']:,}".replace(",", "."), "en el archivo original", COLOR_GOLD),
        ("Filas duplicadas", f"{reporte_calidad['filas_duplicadas']}", "detectadas", COLOR_CORAL),
        ("Correcciones geográficas", f"{reporte_calidad['correcciones_geograficas']}", "valores normalizados", COLOR_TEAL),
        ("Completitud promedio", f"{100 * (1 - df.isna().mean().mean()):.1f}%", "de todas las columnas", "#6FB98F"),
    ])

    st.subheader("Valores faltantes por columna")
    nulos = df_crudo.isna().mean().sort_values(ascending=False) * 100
    nulos = nulos[nulos > 0]
    if nulos.empty:
        st.success("No se detectaron valores faltantes en el archivo original.")
    else:
        fig = px.bar(x=nulos.values, y=nulos.index, orientation="h", labels={"x": "% de valores faltantes", "y": ""})
        st.plotly_chart(estilizar(fig, 320), width="stretch")

    st.subheader("Ejemplos de normalización geográfica")
    st.caption("Se agrupan variantes de escritura (tildes, mayúsculas, abreviaturas) en un único valor canónico.")
    ejemplos = []
    for col, abrevs in [("Departamento", ABREVIATURAS_DEPARTAMENTO), ("Municipio", ABREVIATURAS_MUNICIPIO)]:
        if col in df_crudo.columns and col in df.columns:
            comp = pd.DataFrame({"original": df_crudo[col].astype(str).str.strip(), "normalizado": df[col]})
            comp = comp[comp["original"] != comp["normalizado"]].drop_duplicates()
            if not comp.empty:
                comp.insert(0, "Columna", col)
                ejemplos.append(comp)
    if ejemplos:
        st.dataframe(pd.concat(ejemplos, ignore_index=True), width="stretch", hide_index=True)
    else:
        st.info("No se encontraron variantes que corregir (o la normalización está desactivada).")

# ===========================================================================
# PÁGINA: Interpretación IA
# ===========================================================================
elif pagina == "Interpretación IA":
    st.caption(
        "La IA no calcula los números que ves aquí; solo los interpreta. "
        "Todo el cálculo estadístico ya quedó hecho con pandas/numpy, y solo se le "
        "envían estadísticas agregadas — nunca datos de contacto personal."
    )
    cliente_ia = obtener_cliente_ia()
    if cliente_ia is None:
        st.warning(
            "No se encontró una `GEMINI_API_KEY` configurada en `st.secrets`. "
            "Agrégala en `.streamlit/secrets.toml` para habilitar esta sección."
        )
    else:
        st.markdown('<div class="bloque-ia">', unsafe_allow_html=True)
        st.markdown("#### 📋 Resumen ejecutivo del periodo filtrado")
        if st.button("Generar resumen ejecutivo"):
            with st.spinner("Consultando a la IA..."):
                resumen = {
                    "periodo": f"{df_f['Fecha'].min().date()} a {df_f['Fecha'].max().date()}" if tiene_fecha else "no disponible",
                    "total_visitas": int(len(df_f)),
                    "total_visitantes": int(df_f["Total visitantes"].sum()) if "Total visitantes" in df_f else None,
                    "ingreso_total_cop": float(df_f["Ingreso"].sum()) if "Ingreso" in df_f else None,
                    "dependencia_mas_frecuente": df_f["Dependencia"].mode().iat[0] if "Dependencia" in df_f and not df_f["Dependencia"].mode().empty else None,
                    "pais_principal": df_f["País de procedencia"].mode().iat[0] if "País de procedencia" in df_f and not df_f["País de procedencia"].mode().empty else None,
                    "dia_semana_mas_visitado": df_f["Día de semana"].mode().iat[0] if "Día de semana" in df_f and not df_f["Día de semana"].mode().empty else None,
                }
                prompt = f"""
Eres un analista de datos de un museo. A partir de este resumen agregado, ya
calculado (no debes recalcular ni inventar cifras nuevas):
{resumen}
Redacta un resumen ejecutivo en español (máximo 180 palabras) dirigido a la
dirección del museo: afluencia general, comportamiento del recaudo,
procedencia de los visitantes y algún patrón temporal relevante. Tono
profesional y claro para un lector no técnico. No inventes cifras que no
aparezcan en el resumen proporcionado.
"""
                st.write(generar_texto_ia(cliente_ia, prompt))
        st.markdown("</div>", unsafe_allow_html=True)

        st.write("")
        st.markdown('<div class="bloque-ia">', unsafe_allow_html=True)
        st.markdown("#### 🔍 Interpretación de una variable específica")
        variable_ia = st.selectbox("Variable", variables_numericas, key="variable_ia")
        if st.button("Generar interpretación de la variable"):
            with st.spinner("Consultando a la IA..."):
                stats = estadisticas_descriptivas(df_f[variable_ia])
                prompt = f"""
Analiza las siguientes estadísticas descriptivas de la variable "{variable_ia}"
para un museo:
{stats}
Escribe una interpretación breve (máximo 150 palabras) en español, dirigida a
un lector no técnico, explicando qué dicen estos números sobre los datos:
tendencia central, dispersión y posibles valores atípicos. No inventes cifras
que no aparezcan en los datos proporcionados.
"""
                st.write(generar_texto_ia(cliente_ia, prompt))
        st.markdown("</div>", unsafe_allow_html=True)

# ===========================================================================
# PÁGINA: Datos y exportación
# ===========================================================================
elif pagina == "Datos y exportación":
    mostrar_contacto = st.checkbox(
        "Mostrar información de contacto (responsable y teléfono)", value=False,
        help="Por buenas prácticas de manejo de datos personales, esta información se oculta por defecto.",
    )
    columnas_ocultas = [] if mostrar_contacto else [c for c in ["Responsable de la visita", "Contacto"] if c in df_f.columns]
    st.dataframe(df_f.drop(columns=columnas_ocultas), width="stretch", hide_index=True)

    st.download_button(
        "⬇️ Descargar datos filtrados (CSV)",
        data=df_f.drop(columns=columnas_ocultas).to_csv(index=False, sep=";").encode("utf-8-sig"),
        file_name="visitantes_filtrado.csv",
        mime="text/csv",
    )
