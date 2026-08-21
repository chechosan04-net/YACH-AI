# YACH-AI

Dashboard descriptivo con interpretación de IA

App en Streamlit que recibe un CSV o Excel, calcula estadística descriptiva
(media, mediana, desviación estándar, cuartiles, percentil 90) y genera una
interpretación en lenguaje natural usando la API de Claude.

## Cómo probarla en tu computador

1. Instala las dependencias:
   ```
   pip install -r requirements.txt
   ```

2. Consigue una API key en https://console.anthropic.com (sección "API Keys").

3. Crea el archivo `.streamlit/secrets.toml` dentro de esta carpeta con:
   ```
   ANTHROPIC_API_KEY = "tu-api-key-aqui"
   ```

4. Corre la app:
   ```
   streamlit run app.py
   ```

5. Se abre en el navegador. Sube un CSV o Excel con al menos una columna
   numérica (por ejemplo tus datos de Edad/Ventas/Satisfacción, o los de
   visitantes del museo) y prueba el botón "Generar interpretación".

## Cómo desplegarla gratis (para entregar un link funcional)

1. Sube esta carpeta a un repositorio de GitHub.
2. Entra a https://share.streamlit.io y conecta tu cuenta de GitHub.
3. Selecciona el repositorio y el archivo `app.py`.
4. En "Advanced settings" → "Secrets", pega:
   ```
   ANTHROPIC_API_KEY = "tu-api-key-aqui"
   ```
5. Dale a "Deploy". En un par de minutos tienes un link público para entregar.

## Ideas para ampliarlo (si te sobra tiempo)

- Permitir seleccionar varias columnas a la vez y comparar sus estadísticas.
- Agregar un gráfico de correlación entre dos variables numéricas.
- Guardar el historial de interpretaciones generadas en la sesión.
- Cambiar el prompt para pedirle a la IA recomendaciones accionables, no solo
  descripción.
