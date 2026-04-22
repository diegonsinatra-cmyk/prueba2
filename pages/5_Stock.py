"""
P�gina B5 — Stock actual por planta y material.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.express as px
from utils.helpers import get_stock_planta, get_usuarios_por_tipo, fmt_kg

st.set_page_config(page_title="B5 · Stock", page_icon="📦", layout="wide")
st.markdown("# 📦 B5 · Inventario de Stock")
st.markdown("Material clasificado disponible para venta, por planta.")
st.divider()

tratadores = get_usuarios_por_tipo("tratador")
planta_sel = st.selectbox(
    "Filtrar por planta (opcional)",
    options=[None] + tratadores,
    format_func=lambda u: "Todas las plantas" if u is None else u.nombre
)

planta_id = planta_sel.usuario_id if planta_sel else None
stock = get_stock_planta(planta_id)

if not stock:
    st.info("Sin stock disponible. Registrá pesadas en Clasificación (B4).")
    st.stop()

df = pd.DataFrame(stock)
total = df["stock_kg"].sum()

c1, c2, c3 = st.columns(3)
c1.metric("Stock Total", fmt_kg(total))
c2.metric("Materiales distintos", len(df))
c3.metric("Categorías", df["categoria"].nunique())

st.divider()

col_t, col_g = st.columns([1.4, 1])

with col_t:
    st.subheader("Detalle por material")
    df_show = df[["categoria", "material", "planta", "stock_kg"]].copy()
    df_show.columns = ["Categoría", "Material", "Planta", "Stock (kg)"]
    df_show = df_show.sort_values("Stock (kg)", ascending=False)
    st.dataframe(df_show, use_container_width=True, hide_index=True, height=420)

with col_g:
    st.subheader("Distribución")
    df_top = df.nlargest(10, "stock_kg")
    fig = px.bar(
        df_top, x="stock_kg", y="material", orientation="h",
        color="categoria",
        color_discrete_sequence=px.colors.qualitative.Set2,
        labels={"stock_kg": "kg", "material": ""},
    )
    fig.update_layout(
        plot_bgcolor="#161b22", paper_bgcolor="#161b22",
        font_color="#e6edf3", height=380,
        xaxis=dict(gridcolor="#2a3441"),
        yaxis=dict(gridcolor="#2a3441"),
        legend=dict(bgcolor="#161b22"),
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)
