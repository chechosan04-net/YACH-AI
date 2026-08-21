import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from google import genai

st.set_page_config(page_title="Dashboard descriptivo con IA", layout="wide")

st.title("YACH-AI · Dashboard descriptivo con interpretación de IA")
st.write(
    "Sube un archivo CSV o Excel y obtén estadística descriptiva "
    "junto con una interpretación en lenguaje natural generada por IA."
)

# --- 1. Carga de datos ---
archivo = st.file_uploader("Sube tu archivo de datos", type=["csv", "xlsx"])

if archivo is not None:
    if archivo.name.endswith(".csv"):
        df = pd.read_csv(archivo)
    else:
        df = pd.read_excel(archivo)

    st.subheader("Vista previa de los datos")
    st.dataframe(df.head())

    columnas_numericas = df.select_dtypes(include=np.number).columns.tolist()

    if not columnas_numericas:
        st.warning("No se encontraron columnas numéricas en el archivo.")
    else:
        columna = st.selectbox("Selecciona la variable a analizar", columnas_numericas)
        datos = df[columna].dropna()

        # --- 2. Estadística descriptiva ---
        estadisticas = {
            "Media": round(datos.mean(), 2),
            "Mediana": round(datos.median(), 2),
            "Desviación estándar": round(datos.std(), 2),
            "Mínimo": round(datos.min(), 2),
            "Máximo": round(datos.max(), 2),
            "Q1 (25%)": round(datos.quantile(0.25), 2),
            "Q3 (75%)": round(datos.quantile(0.75), 2),
            "Percentil 90": round(datos.quantile(0.90), 2),
        }

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Estadísticas descriptivas")
            st.table(pd.DataFrame(estadisticas.items(), columns=["Medida", "Valor"]))

        with col2:
            st.subheader("Distribución")
            fig, ax = plt.subplots()
            ax.hist(datos, bins=15, edgecolor="black")
            ax.set_xlabel(columna)
            ax.set_ylabel("Frecuencia")
            st.pyplot(fig)

        st.subheader("Diagrama de caja (boxplot)")
        fig2, ax2 = plt.subplots(figsize=(6, 2))
        ax2.boxplot(datos, vert=False)
        ax2.set_xlabel(columna)
        st.pyplot(fig2)

        # --- 3. Interpretación con IA (capa separada del cálculo) ---
        st.subheader("Interpretación generada por IA")
        st.caption(
            "La IA no calcula los números de arriba; solo los interpreta. "
            "El cálculo estadístico ya quedó hecho con pandas/numpy."
        )

        if st.button("Generar interpretación"):
            with st.spinner("Consultando a la IA..."):
                cliente = genai.Client(api_key=st.secrets["GEMINI_API_KEY"])

                prompt = f"""
Analiza las siguientes estadísticas descriptivas de la variable "{columna}":
{estadisticas}

Escribe una interpretación breve (máximo 150 palabras) en español, dirigida a
un lector no técnico, explicando qué dicen estos números sobre los datos:
tendencia central, dispersión y posibles valores atípicos. No inventes cifras
que no aparezcan en los datos proporcionados.
"""

                respuesta = cliente.models.generate_content(
                    model="gemini-flash-latest",
                    contents=prompt,
                )

                st.write(respuesta.text)
else:
    st.info("Esperando que subas un archivo para comenzar el análisis.")
