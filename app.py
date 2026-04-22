"""
App principal RSU - Dashboard
Ejecutar con: python3 -m streamlit run app.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from utils.seed import seed_database
from utils.helpers import get_kpis, get_stock_planta, fmt_kg, fmt_ars
from models.database import get_session, Lote
from sqlalchemy import func

st.set_page_config(
    page_title="Sistema RSU",
    page_icon="=?",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_resource
def init():
    seed_database()
init()

st.markdown("""
<style>
  [data-testid="stSidebar"] { background: #0d1117; }
  [data-testid="stSidebar"] * { color: #e6edf3 !important; }
  [data-testid="stMetric"] {
    background: #161b22; border: 1px solid #2a3441;
    border-radius: 10px; padding: 16px;
  }
  [data-testid="stMetricLabel"] { color: #7d8590 !important; font-size: 12px; }
  [data-testid="stMetricValue"] { color: #e6edf3 !important; }
  h1 { color: #39d353 !important; }
  h2, h3 { color: #e6edf3 !important; }
  .main { background: #0d1117; }
  .block-container { background: #0d1117; }
  [data-testid="stDataFrame"] { border: 1px solid #2a3441; border-radius: 8px; }
  .stButton > button {
    background: #1c2230; border: 1px solid #2a3441;
    color: #e6edf3; border-radius: 6px;
  }
  .stButton > button:hover { background: #39d353; color: #0d1117; border-color: #39d353; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("## Sistema RSU")
    st.markdown("**Trazabilidad de Residuos Solidos Urbanos**")
    st.divider()
    st.markdown("""
**Flujo de trabajo**
- B1 Generacion
- B2 Recoleccion
- B3 Descarga en Planta
- B4 Clasificacion (pool)
- B5 Stock
- B6 Ventas
- B7 Reportes y Balance
    """)
    st.divider()
    st.caption("v2.0 - SQLite local")

st.markdown("# Dashboard RSU")
st.markdown("**Centro de control de trazabilidad de residuos solidos urbanos**")
st.divider()

# KPIs
kpis = get_kpis()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Lotes Totales",      kpis["total_lotes"])
c2.metric("En ruta",            kpis["lotes_activos"])
c3.metric("Clasificado (total)", fmt_kg(kpis["total_clasificado"]))
c4.metric("Tasa Recuperacion",  f"{kpis['tasa_recuperacion']} %")
c5.metric("Ingresos ARS",       fmt_ars(kpis["ingresos_ars"]))

st.divider()

col_a, col_b = st.columns([1.2, 1])

with col_a:
    st.subheader("Stock Actual por Material")
    stock = get_stock_planta()
    if stock:
        df_stock = pd.DataFrame(stock)
        df_top = df_stock.nlargest(12, "stock_kg")
        fig = px.bar(
            df_top, x="stock_kg", y="material",
            orientation="h", color="categoria",
            color_discrete_sequence=px.colors.qualitative.Set2,
            labels={"stock_kg": "kg en stock", "material": ""},
        )
        fig.update_layout(
            plot_bgcolor="#161b22", paper_bgcolor="#161b22",
            font_color="#e6edf3", height=380,
            xaxis=dict(gridcolor="#2a3441"),
            yaxis=dict(gridcolor="#2a3441"),
            legend=dict(bgcolor="#161b22"),
            margin=dict(l=0, r=10, t=10, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin stock registrado aun. Carga pesadas en Clasificacion (B4).")

with col_b:
    st.subheader("Estado de Lotes (B1-B3)")
    db = get_session()
    estados = db.query(Lote.estado, func.count(Lote.lote_id)).group_by(Lote.estado).all()
    db.close()

    if estados:
        labels = [e[0] for e in estados]
        values = [e[1] for e in estados]
        colors = {
            "generado":   "#bc8cff",
            "en_ruta":    "#58d7e8",
            "descargado": "#39d353",
        }
        fig2 = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.55,
            marker_colors=[colors.get(l, "#888") for l in labels],
        ))
        fig2.update_layout(
            plot_bgcolor="#161b22", paper_bgcolor="#161b22",
            font_color="#e6edf3", height=380,
            margin=dict(l=0, r=0, t=10, b=0),
            legend=dict(bgcolor="#161b22"),
        )
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Sin lotes registrados aun.")

st.divider()

# Tabla ultimos lotes
st.subheader("Ultimos Lotes Registrados (B1-B3)")
db = get_session()
try:
    lotes = db.query(Lote).order_by(Lote.created_at.desc()).limit(20).all()
    rows = []
    for l in lotes:
        gen_nombre = l.generador.nombre if l.generador else "-"
        rows.append({
            "Codigo":           l.codigo_lote,
            "Estado":           l.estado.upper(),
            "Generador":        gen_nombre,
            "Estimado (kg)":    float(l.peso_estimado_kg or 0),
            "Recolectado (kg)": float(l.peso_recolectado_kg or 0),
            "Descarga (kg)":    float(l.peso_descarga_kg or 0),
            "Fecha":            l.fecha_generacion.strftime("%d/%m/%Y") if l.fecha_generacion else "",
        })
finally:
    db.close()

if rows:
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
else:
    st.info("Aun no hay lotes. Comenza por Generacion en el menu lateral.")

st.divider()
st.caption("Sistema RSU v2.0 - B1-B3 por lote | B4-B7 por pool de planta | Balance de masas por periodo")
