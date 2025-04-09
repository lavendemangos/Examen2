import streamlit as st
import yfinance as yf
import altair as alt
import pandas as pd
import google.generativeai as genai
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
from pandas.tseries.offsets import DateOffset

# ====== Configuración de página ======
st.set_page_config(page_title="Buscador de Empresas", layout="wide")

# ====== Estilos personalizados ======
st.markdown(
    """
    <style>
    body {
        background-color: #1e1e2f;
        color: #ddddff;
    }
    .stButton>button {
        background-color: #6A0DAD;
        color: white;
    }
    .stSelectbox>div>div>div {
        color: black;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ====== Sidebar - Inputs ======
with st.sidebar:
    symbol = st.text_input("Símbolo de la acción (ej. AAPL)", placeholder="Buscar...")
    intervalo = st.selectbox("Intervalo de precios:", ["6mo", "1y", "5y", "max"])
    usar_velas = st.checkbox("Mostrar gráfico de velas")
    buscar = st.button("Buscar")

# ====== Título principal ======
st.markdown("<h1 style='text-align:center; color:#6A0DAD;'>Buscador de Acciones del Mercado</h1>", unsafe_allow_html=True)
st.divider()

# ====== Lógica principal ======
if buscar and symbol.strip():
    with st.spinner("🔄 Consultando y procesando datos..."):
        try:
            ticker = yf.Ticker(symbol.strip().upper())
            info = ticker.get_info()

            if not info or info.get("regularMarketPrice") is None:
                st.error("❌ Ticker inválido. Por favor revise e intente de nuevo.")
            else:
                nombre_largo = info.get("longName", "NA")
                descripcion = info.get("longBusinessSummary", "NA")
                sector = info.get("sector", "NA")
                industria = info.get("industry", "NA")
                pais = info.get("country", "NA")

                texto_para_traducir = (
                    f"Descripción:\n{descripcion}\n\nSector: {sector}\nIndustria: {industria}\nPaís: {pais}"
                )
                prompt_completo = (
                    "Traduce al español de forma clara, profesional y sin encabezados el siguiente texto técnico sobre una empresa. "
                    "Incluye la descripción y un resumen, muestra el sector, la industria y el país: en un texto a parte\n\n"
                    + texto_para_traducir
                )

                try:
                    model = genai.GenerativeModel("models/gemini-1.5-pro")
                    genai.configure(api_key="AIzaSyAt3B4Xa7FRqbreSwXrEWnbHtMWW-O4EqI")
                    respuesta_completa = model.generate_content(prompt_completo)
                    texto_traducido = respuesta_completa.text
                except Exception as gemini_error:
                    texto_traducido = (
                        "⚠️ No se pudo traducir la información debido a un límite de uso en la API de Gemini.\n\n"
                        "Por favor, intente más tarde o revise su cuota de uso en: https://ai.google.dev/gemini-api/docs/rate-limits"
                    )

                with st.container():
                    st.header("📋 Información General")
                    st.markdown(f"## {nombre_largo}")
                    st.markdown(f"**Información traducida:**\n\n{texto_traducido}")
                    st.divider()

                hist = ticker.history(period=intervalo).reset_index()
                hist["MA20"] = hist["Close"].rolling(window=20).mean()
                hist["UpperBB"] = hist["MA20"] + 2 * hist["Close"].rolling(window=20).std()
                hist["LowerBB"] = hist["MA20"] - 2 * hist["Close"].rolling(window=20).std()

                with st.container():
                    st.header("📈 Historial de Precios")

                    if usar_velas:
                        fig = go.Figure(data=[go.Candlestick(
                            x=hist["Date"],
                            open=hist["Open"],
                            high=hist["High"],
                            low=hist["Low"],
                            close=hist["Close"]
                        )])
                        fig.update_layout(height=400, xaxis_rangeslider_visible=False)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        lineas = alt.Chart(hist).mark_line().encode(
                            x="Date:T",
                            y=alt.Y("Close:Q", title="Precio de cierre"),
                            tooltip=["Date:T", "Close:Q", "MA20:Q"]
                        ).properties(height=300)

                        ma20 = alt.Chart(hist).mark_line(strokeDash=[4,4], color="orange").encode(
                            x="Date:T",
                            y="MA20:Q"
                        )

                        upper = alt.Chart(hist).mark_line(strokeDash=[2,2], color="gray").encode(
                            x="Date:T",
                            y="UpperBB:Q"
                        )

                        lower = alt.Chart(hist).mark_line(strokeDash=[2,2], color="gray").encode(
                            x="Date:T",
                            y="LowerBB:Q"
                        )

                        barras = alt.Chart(hist).mark_bar(opacity=0.3).encode(
                            x="Date:T",
                            y=alt.Y("Volume:Q", title="Volumen"),
                            tooltip=["Date:T", "Volume:Q"]
                        ).properties(height=100)

                        chart = (lineas + ma20 + upper + lower) & barras
                        st.altair_chart(chart, use_container_width=True)

                    st.divider()

                with st.container():
                    st.header("📊 Métricas de Desempeño")

                    def calcular_cagr(precio_inicio, precio_final, años):
                        if precio_inicio > 0 and años > 0:
                            return (precio_final / precio_inicio) ** (1 / años) - 1
                        return None

                    rendimientos = {"Periodo": [], "Rendimiento Anualizado (CAGR)": []}
                    hoy = hist["Date"].max()

                    for años in [1, 3, 5]:
                        fecha_inicio = hoy - DateOffset(years=años)
                        datos_periodo = hist[hist["Date"] >= fecha_inicio]

                        if len(datos_periodo) > 0:
                            precio_inicio = datos_periodo.iloc[0]["Close"]
                            precio_final = datos_periodo.iloc[-1]["Close"]
                            cagr = calcular_cagr(precio_inicio, precio_final, años)
                            rendimiento = f"{cagr * 100:.2f}%" if cagr is not None else "Datos no disponibles"
                        else:
                            rendimiento = "Datos no disponibles"

                        rendimientos["Periodo"].append(f"{años} año(s)")
                        rendimientos["Rendimiento Anualizado (CAGR)"].append(rendimiento)

                    st.dataframe(pd.DataFrame(rendimientos))
                    st.markdown("**¿Qué significa esto?** El CAGR muestra el crecimiento promedio compuesto anual de la acción en los últimos años.")

                    rendimientos_diarios = hist["Close"].pct_change().dropna()
                    desviacion_std_diaria = np.std(rendimientos_diarios)
                    volatilidad_anual = desviacion_std_diaria * np.sqrt(252)

                    st.metric(label="📉 Volatilidad Anualizada", value=f"{volatilidad_anual * 100:.2f}%")
                    st.markdown("**¿Qué significa esto?** Esta métrica representa la volatilidad histórica del activo, medida por la desviación estándar de los rendimientos diarios.")

        except Exception as e:
            st.error(f"No se pudo obtener la información. Error: {str(e)}")
else:
    st.warning("Por favor, ingresa un símbolo válido en la barra lateral.")
