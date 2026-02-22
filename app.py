import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, time, date
import requests

# CONFIGURACIÓN INTERFAZ
st.set_page_config(page_title="Monitor XSP 0DTE", layout="wide")
st.title("📊 Monitor Profesional XSP 0DTE")

# BARRA LATERAL - CONFIGURACIÓN
st.sidebar.header("Configuración de Usuario")
api_key = st.sidebar.text_input("", value="d6d2nn1r01qgk7mkblh0d6d2nn1r01qgk7mkblhg", type="password")
capital = st.sidebar.number_input("Capital de la Cuenta (€)", min_value=100.0, value=25000.0, step=100.0)
riesgo_pct = st.sidebar.slider("Riesgo por sesión (%)", 0.5, 5.0, 2.0) / 100

def check_noticias_auto(key):
    if not key: return []
    eventos_prohibidos = ["CPI", "FED", "FOMC", "NFP", "POWELL", "UNEMPLOYMENT", "INTEREST RATE", "PPI", "EARNINGS"]
    hoy = str(date.today())
    url = f"https://finnhub.io{hoy}&to={hoy}&token={key}"
    try:
        response = requests.get(url)
        data = response.json().get('economicCalendar', [])
        return [ev['event'] for ev in data if ev['country'] == 'US' and ev['impact'] == 'high' 
                and any(k in ev['event'].upper() for k in eventos_prohibidos)]
    except: return []

def obtener_datos():
    tickers = {"XSP": "^XSP", "VIX": "^VIX", "VIX9D": "^VIX9D", "VVIX": "^VVIX", "VIX1D": "^VIX1D"}
    vals = {}
    for k, v in tickers.items():
        t = yf.Ticker(v)
        df = t.history(period="1d", interval="1m")
        if not df.empty:
            vals[k] = {"actual": df['Close'].iloc[-1], "apertura": df['Open'].iloc[0]}
        else: vals[k] = {"actual": 0, "apertura": 0}
    return vals

def calcular_strikes_y_alas(precio, vix, delta_target):
    sigma_1d = (vix / 100) / (252**0.5)
    mult = 1.65 if delta_target == 5 else 1.88
    distancia = precio * sigma_1d * mult
    vendido_up = round(precio + distancia)
    vendido_down = round(precio - distancia)
    ancho_alas = 3 if vix < 14 else 5
    return vendido_up, vendido_down, ancho_alas

# LÓGICA PRINCIPAL
if st.button('🚀 Ejecutar Análisis'):
    with st.spinner('Consultando datos de mercado...'):
        ahora = datetime.now().time()
        
        # 1. Validación Horaria
        if ahora < time(16, 15):
            st.warning("⚠️ AVISO: No se ha llegado a la hora de confirmación (16:15 ESP). Los datos pueden no ser definitivos.")

        # 2. Noticias
        noticias = check_noticias_auto(api_key)
        if noticias:
            st.error(f"🚫 DÍA DE NOTICIAS CRÍTICAS: {', '.join(noticias)}. NO OPERAR.")
        else:
            d = obtener_datos()
            if d["XSP"]["actual"] == 0:
                st.error("Error al obtener datos. ¿Está el mercado abierto?")
            else:
                xsp, vix, vvix = d["XSP"]["actual"], d["VIX"]["actual"], d["VVIX"]["actual"]
                rango_ap = abs((xsp - d["XSP"]["apertura"]) / d["XSP"]["apertura"] * 100)
                
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("XSP Actual", f"{xsp:.2f}", f"{rango_ap:.2f}%")
                col2.metric("VIX", f"{vix:.2f}")
                col3.metric("VVIX", f"{vvix:.2f}")
                col4.metric("VIX1D", f"{d['VIX1D']['actual']:.2f}")

                # 3. Filtros Tramo 1
                st.subheader("Análisis de Filtros (Tramo 1)")
                c1 = d["VIX1D"]["actual"] < d["VIX9D"]["actual"] < vix
                c2 = vix < 16
                c3 = vvix < 88
                c4 = rango_ap < 0.40

                f_col1, f_col2 = st.columns(2)
                with f_col1:
                    st.write(f"{'✅' if c1 else '❌'} Estructura VIX1D < VIX9D < VIX")
                    st.write(f"{'✅' if c2 else '❌'} VIX < 16")
                with f_col2:
                    st.write(f"{'✅' if c3 else '❌'} VVIX < 88")
                    st.write(f"{'✅' if c4 else '❌'} Rango Inicial < 0.40%")

                # 4. Estrategia Sugerida
                st.divider()
                st.subheader("🎯 Estrategia Recomendada")

                if vvix > 125:
                    st.error(">>> NO OPERAR: VVIX EXTREMO (>125)")
                
                elif c1 and c2 and c3 and c4:
                    st_up, st_dw, ancho = calcular_strikes_y_alas(xsp, vix, 5)
                    riesgo_neto_por_contrato = (ancho * (2/3)) * 100 
                    num_contratos = int((capital * riesgo_pct) // riesgo_neto_por_contrato)
                    num_contratos = max(1, num_contratos)
                    
                    st.success(f"**TRAMO 1: IRON CONDOR (Delta 5)**")
                    st.write(f"• **Strikes:** CALL {st_up} | PUT {st_dw}")
                    st.write(f"• **Regla 1/3:** Alas de {ancho} puntos (Crédito objetivo: {ancho/3:.2f}€)")
                    st.info(f"💡 **Gestión:** Operar {num_contratos} contrato(s). Stop-loss si XSP toca {xsp*1.008:.2f} / {xsp*0.992:.2f}")

                elif d["VIX1D"]["actual"] > d["VIX9D"]["actual"] or vvix > 105 or rango_ap > 0.75:
                    es_alcista = xsp > d["XSP"]["apertura"]
                    st_up, st_dw, ancho = calcular_strikes_y_alas(xsp, vix, 3)
                    strike_v = st_dw if es_alcista else st_up
                    riesgo_neto_por_contrato = (ancho * (2/3)) * 100
                    num_contratos = max(1, int((capital * riesgo_pct) // riesgo_neto_por_contrato))
                    
                    st.info(f"**TRAMO 2: SPREAD VERTICAL (Delta 3)**")
                    st.write(f"• **Dirección:** {'ALCISTA (Vender Put)' if es_alcista else 'BAJISTA (Vender Call)'}")
                    st.write(f"• **Strike Vendido:** {strike_v} | Alas: {ancho} pts")
                    st.write(f"• **Contratos:** {num_contratos}")

                else:
                    st.warning(">>> SIN SEÑAL CLARA: El mercado no cumple parámetros de alta probabilidad.")

st.sidebar.info("Nota: Yahoo Finance tiene un retraso de 15 min en datos gratuitos.")
