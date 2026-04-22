"""
P�gina B7 — Reportes, Balance y Auditoría.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, date
from models.database import (
    get_session, Lote, PeriodoClasificacion, PesadaClasificacion,
    RechazoPool, Venta, EventoAuditoria
)
from sqlalchemy import func
from utils.helpers import (
    get_usuarios_por_tipo, calcular_balance_periodo, fmt_kg, fmt_ars
)

st.set_page_config(page_title="Reportes & Auditoría", page_icon="📊", layout="wide")
st.markdown("# 📊 Reportes · Balance · Auditoría")
st.divider()

tratadores = get_usuarios_por_tipo("tratador")

tab_balance, tab_traz, tab_periodos, tab_audit = st.tabs([
    "⚖️ Balance de Masas", "🔍 Trazabilidad B1–B3", "📅 Períodos", "📋 Auditoría"
])

# ─── BALANCE DE MASAS ─────────────────────────────────────────────────────────
with tab_balance:
    st.subheader("Balance de masas por período")

    planta_bal = st.selectbox(
        "Planta", options=tratadores, format_func=lambda u: u.nombre, key="planta_bal"
    )

    db = get_session()
    periodos_planta = (db.query(PeriodoClasificacion)
                         .filter_by(planta_id=planta_bal.usuario_id)
                         .order_by(PeriodoClasificacion.fecha_inicio.desc())
                         .all())
    db.close()

    if not periodos_planta:
        st.info("No hay períodos registrados para esta planta.")
        st.stop()

    periodo_sel = st.selectbox(
        "Período",
        options=periodos_planta,
        format_func=lambda p: f"{p.nombre} ({'abierto' if p.estado=='abierto' else 'cerrado'})"
    )

    bal = calcular_balance_periodo(periodo_sel.periodo_id)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total descargado",    fmt_kg(bal.get("total_descarga", 0)))
    c2.metric("Clasificado",         fmt_kg(bal.get("total_clasificado", 0)),
              delta=f"{bal.get('pct_clasificado', 0)}%")
    c3.metric("Rechazo",             fmt_kg(bal.get("total_rechazo", 0)),
              delta=f"{bal.get('pct_rechazo', 0)}%", delta_color="inverse")
    c4.metric("Diferencia",          fmt_kg(abs(bal.get("diferencia", 0))),
              delta="OK" if bal.get("balance_ok") else "Revisar", delta_color="normal" if bal.get("balance_ok") else "inverse")

    st.divider()

    # Sankey
    td  = max(bal.get("total_descarga", 0),    0.01)
    tc  = max(bal.get("total_clasificado", 0), 0.01)
    tr  = max(bal.get("total_rechazo", 0),     0.01)
    tv  = max(bal.get("total_vendido", 0),     0.01)
    tes = max(tc - tv,                          0.01)

    fig = go.Figure(go.Sankey(
        node=dict(
            label=["Descargas\n(lotes)", "Clasificado", "Rechazo", "Vendido", "En Stock"],
            color=["#58d7e8", "#39d353", "#f85149", "#39d353", "#bc8cff"],
            pad=20, thickness=20,
        ),
        link=dict(
            source=[0, 0, 1, 1],
            target=[1, 2, 3, 4],
            value=[tc, tr, tv, tes],
            color=["rgba(57,211,83,0.3)", "rgba(248,81,73,0.3)",
                   "rgba(57,211,83,0.3)", "rgba(188,140,255,0.3)"],
        )
    ))
    fig.update_layout(
        title=f"Flujo de material — {periodo_sel.nombre}",
        plot_bgcolor="#161b22", paper_bgcolor="#161b22",
        font_color="#e6edf3", height=380,
    )
    st.plotly_chart(fig, use_container_width=True)

    # Pesadas del período por material
    db = get_session()
    pesadas = db.query(PesadaClasificacion).filter_by(periodo_id=periodo_sel.periodo_id).all()
    db.close()
    if pesadas:
        df_p = pd.DataFrame([{
            "Material":  p.material.subcategoria if p.material else "—",
            "Categoría": p.material.categoria if p.material else "—",
            "Peso (kg)": float(p.peso_kg),
            "Calidad":   p.calidad or "—",
            "Fecha":     p.fecha.strftime("%d/%m/%Y %H:%M") if p.fecha else "",
        } for p in pesadas])
        st.subheader("Pesadas del período")
        st.dataframe(df_p, use_container_width=True, hide_index=True)

# ─── TRAZABILIDAD B1-B3 ───────────────────────────────────────────────────────
with tab_traz:
    st.subheader("Trazabilidad de lotes B1 → B3")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fecha_desde = st.date_input("Desde", value=date(date.today().year, date.today().month, 1))
    with col_f2:
        fecha_hasta = st.date_input("Hasta", value=date.today())

    planta_traz = st.selectbox(
        "Planta (opcional)",
        options=[None] + tratadores,
        format_func=lambda u: "Todas" if u is None else u.nombre,
        key="planta_traz"
    )

    db = get_session()
    q = db.query(Lote).filter(
        Lote.fecha_generacion >= datetime.combine(fecha_desde, datetime.min.time()),
        Lote.fecha_generacion <= datetime.combine(fecha_hasta, datetime.max.time()),
    )
    if planta_traz:
        q = q.filter_by(planta_id=planta_traz.usuario_id)
    lotes = q.order_by(Lote.fecha_generacion.desc()).all()
    db.close()

    if not lotes:
        st.info("Sin lotes en el período seleccionado.")
    else:
        rows = [{
            "Código":            l.codigo_lote,
            "Estado":            l.estado.upper(),
            "Generador":         l.generador.nombre if l.generador else "—",
            "Transportista":     l.transportista.nombre if l.transportista else "—",
            "Planta":            l.planta.nombre if l.planta else "—",
            "Estimado (kg)":     float(l.peso_estimado_kg or 0),
            "Recolectado (kg)":  float(l.peso_recolectado_kg or 0),
            "Descarga (kg)":     float(l.peso_descarga_kg or 0),
            "Fecha generación":  l.fecha_generacion.strftime("%d/%m/%Y") if l.fecha_generacion else "",
            "Fecha descarga":    l.fecha_descarga.strftime("%d/%m/%Y") if l.fecha_descarga else "—",
        } for l in lotes]
        df_l = pd.DataFrame(rows)
        st.dataframe(df_l, use_container_width=True, hide_index=True)

        total_desc = df_l["Descarga (kg)"].sum()
        st.metric("Total descargado en el período", fmt_kg(total_desc))

# ─── PERÍODOS ─────────────────────────────────────────────────────────────────
with tab_periodos:
    st.subheader("Todos los períodos de clasificación")
    db = get_session()
    todos = db.query(PeriodoClasificacion).order_by(PeriodoClasificacion.fecha_inicio.desc()).all()
    db.close()

    if not todos:
        st.info("Sin períodos registrados.")
    else:
        rows = []
        for p in todos:
            bal = calcular_balance_periodo(p.periodo_id)
            rows.append({
                "Período":      p.nombre,
                "Planta":       p.planta.nombre if p.planta else "—",
                "Estado":       p.estado.upper(),
                "Inicio":       p.fecha_inicio.strftime("%d/%m/%Y"),
                "Fin":          p.fecha_fin.strftime("%d/%m/%Y") if p.fecha_fin else "—",
                "Descargas (kg)":    round(bal.get("total_descarga", 0), 1),
                "Clasificado (kg)":  round(bal.get("total_clasificado", 0), 1),
                "Rechazo (kg)":      round(bal.get("total_rechazo", 0), 1),
                "Balance":      "✅" if bal.get("balance_ok") else "⚠️",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ─── AUDITORÍA ────────────────────────────────────────────────────────────────
with tab_audit:
    st.subheader("Log de auditoría")
    db = get_session()
    eventos = db.query(EventoAuditoria).order_by(EventoAuditoria.created_at.desc()).limit(150).all()
    lotes_map = {l.lote_id: l.codigo_lote for l in db.query(Lote).all()}
    periodos_map = {p.periodo_id: p.nombre for p in db.query(PeriodoClasificacion).all()}
    db.close()

    if eventos:
        rows = [{
            "Fecha":       e.created_at.strftime("%d/%m/%Y %H:%M") if e.created_at else "",
            "Instancia":   f"B{e.instancia_b}" if e.instancia_b else "—",
            "Evento":      e.tipo_evento or "—",
            "Lote":        lotes_map.get(e.lote_id, "—"),
            "Período":     periodos_map.get(e.periodo_id, "—"),
            "Descripción": (e.descripcion or "")[:120],
        } for e in eventos]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=500)
    else:
        st.info("Sin eventos de auditoría.")
