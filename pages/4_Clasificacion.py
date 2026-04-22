"""
P�gina B4 — Clasificación (Pool por planta)
El operador carga pesadas de material clasificado en cualquier momento.
NO se vincula a ningún lote específico.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, date
from models.database import (
    get_session, PeriodoClasificacion, PesadaClasificacion,
    RechazoPool, EventoAuditoria, Lote
)
from utils.helpers import (
    get_usuarios_por_tipo, get_materiales_no_mezclados,
    get_periodo_abierto, calcular_balance_periodo,
    actualizar_stock, fmt_kg
)
from sqlalchemy import func

st.set_page_config(page_title="B4 · Clasificación", page_icon="⚖️", layout="wide")
st.markdown("# ⚖️ B4 · Clasificación — Pool de Planta")
st.markdown("El material se clasifica en el pool general de la planta, sin asociarse a un lote específico.")
st.divider()

tratadores  = get_usuarios_por_tipo("tratador")
materiales  = get_materiales_no_mezclados()

if not tratadores:
    st.warning("No hay plantas/tratadores registrados.")
    st.stop()

# ─── SELECTOR DE PLANTA ───────────────────────────────────────────────────────
planta_sel = st.selectbox(
    "Planta de trabajo",
    options=tratadores,
    format_func=lambda u: u.nombre
)

# ─── PERÍODO ACTIVO ───────────────────────────────────────────────────────────
periodo = get_periodo_abierto(planta_sel.usuario_id)

col_per, col_btn = st.columns([3, 1])
with col_per:
    if periodo:
        st.success(f"📅 Período activo: **{periodo.nombre}** — desde {periodo.fecha_inicio.strftime('%d/%m/%Y')}")
    else:
        st.warning("⚠️ No hay período abierto para esta planta. Abrí uno antes de cargar pesadas.")

with col_btn:
    if not periodo:
        if st.button("➕ Abrir nuevo período", use_container_width=True):
            st.session_state["abrir_periodo"] = True
    else:
        if st.button("🔒 Cerrar período", use_container_width=True, type="secondary"):
            st.session_state["cerrar_periodo"] = periodo.periodo_id

# Modal: abrir período
if st.session_state.get("abrir_periodo"):
    with st.form("form_nuevo_periodo"):
        st.subheader("Abrir nuevo período de clasificación")
        nombre_p  = st.text_input("Nombre del período", value=f"Mes {datetime.today().strftime('%B %Y')}")
        fecha_ini = st.date_input("Fecha de inicio", value=date.today())
        operador  = st.selectbox("Operador responsable", options=tratadores, format_func=lambda u: u.nombre)
        sub_p = st.form_submit_button("Abrir período")
    if sub_p:
        db = get_session()
        try:
            p = PeriodoClasificacion(
                planta_id=planta_sel.usuario_id,
                nombre=nombre_p,
                fecha_inicio=fecha_ini,
                created_by=operador.usuario_id,
            )
            db.add(p)
            db.commit()
            st.success(f"✅ Período '{nombre_p}' abierto.")
            st.session_state.pop("abrir_periodo", None)
            st.rerun()
        except Exception as e:
            db.rollback(); st.error(str(e))
        finally:
            db.close()

# Cerrar período
if st.session_state.get("cerrar_periodo"):
    pid = st.session_state["cerrar_periodo"]
    db = get_session()
    try:
        p = db.query(PeriodoClasificacion).filter_by(periodo_id=pid).first()
        p.estado   = "cerrado"
        p.fecha_fin = date.today()
        db.commit()
        st.success("Período cerrado.")
        st.session_state.pop("cerrar_periodo", None)
        st.rerun()
    except Exception as e:
        db.rollback(); st.error(str(e))
    finally:
        db.close()

if not periodo:
    st.stop()

st.divider()
tab_pesada, tab_rechazo, tab_balance, tab_historial = st.tabs([
    "⚖️ Cargar Pesada", "🗑️ Registrar Rechazo", "📊 Balance del Período", "📋 Historial"
])

# ─── CARGAR PESADA ────────────────────────────────────────────────────────────
with tab_pesada:
    st.subheader("Nueva pesada de material clasificado")
    st.caption("Esta pesada ingresa al pool general de la planta, no a un lote específico.")

    with st.form("form_pesada"):
        c1, c2, c3 = st.columns(3)
        with c1:
            mat_sel = st.selectbox(
                "Material *",
                options=materiales,
                format_func=lambda m: f"{m.subcategoria} ({m.categoria})"
            )
            calidad = st.selectbox("Calidad", ["Primera", "Segunda", "Tercera", "Sin clasificar"])
        with c2:
            peso = st.number_input("Peso (kg) *", min_value=0.1, max_value=50000.0, value=100.0, step=0.5)
            operador = st.selectbox("Operador *", options=tratadores, format_func=lambda u: u.nombre)
        with c3:
            obs = st.text_area("Observaciones", height=100)

        submitted = st.form_submit_button("⚖️ Registrar Pesada", use_container_width=True)

    if submitted:
        db = get_session()
        try:
            pesada = PesadaClasificacion(
                periodo_id=periodo.periodo_id,
                planta_id=planta_sel.usuario_id,
                material_id=mat_sel.material_id,
                operador_id=operador.usuario_id,
                peso_kg=peso,
                calidad=calidad,
                observaciones=obs,
            )
            db.add(pesada)
            actualizar_stock(db, planta_sel.usuario_id, mat_sel.material_id, peso)
            evento = EventoAuditoria(
                periodo_id=periodo.periodo_id,
                usuario_id=operador.usuario_id,
                tipo_evento="pesada_clasificacion",
                instancia_b=4,
                descripcion=f"{mat_sel.subcategoria}: {peso} kg. Calidad: {calidad}.",
            )
            db.add(evento)
            db.commit()
            st.success(f"✅ Pesada registrada: **{mat_sel.subcategoria}** — {peso:.1f} kg")
            st.rerun()
        except Exception as e:
            db.rollback(); st.error(str(e))
        finally:
            db.close()

# ─── REGISTRAR RECHAZO ────────────────────────────────────────────────────────
with tab_rechazo:
    st.subheader("Registrar material de rechazo")
    with st.form("form_rechazo"):
        c1, c2 = st.columns(2)
        with c1:
            peso_r   = st.number_input("Peso de rechazo (kg) *", min_value=0.1, value=50.0, step=0.5)
            tipo_r   = st.selectbox("Tipo de rechazo", ["General", "Húmedo", "Peligroso", "Mixto no recuperable"])
            operador_r = st.selectbox("Operador *", options=tratadores, format_func=lambda u: u.nombre, key="op_rech")
        with c2:
            destino  = st.text_input("Destino final", placeholder="CEAMSE / Relleno Sanitario Norte")
            manif    = st.text_input("Número de manifiesto", placeholder="MAN-2025-001")
            obs_r    = st.text_area("Observaciones", height=68)
        sub_r = st.form_submit_button("🗑️ Registrar Rechazo", use_container_width=True)

    if sub_r:
        db = get_session()
        try:
            rec = RechazoPool(
                periodo_id=periodo.periodo_id,
                planta_id=planta_sel.usuario_id,
                operador_id=operador_r.usuario_id,
                peso_kg=peso_r,
                tipo_rechazo=tipo_r,
                destino_final=destino,
                numero_manifiesto=manif,
            )
            db.add(rec)
            evento = EventoAuditoria(
                periodo_id=periodo.periodo_id,
                usuario_id=operador_r.usuario_id,
                tipo_evento="rechazo_registrado",
                instancia_b=7,
                descripcion=f"Rechazo: {peso_r} kg. Tipo: {tipo_r}. Destino: {destino}.",
            )
            db.add(evento)
            db.commit()
            st.success(f"✅ Rechazo registrado: {peso_r:.1f} kg → {destino or 'pendiente destino'}")
            st.rerun()
        except Exception as e:
            db.rollback(); st.error(str(e))
        finally:
            db.close()

# ─── BALANCE DEL PERÍODO ──────────────────────────────────────────────────────
with tab_balance:
    st.subheader(f"Balance de masas — {periodo.nombre}")

    bal = calcular_balance_periodo(periodo.periodo_id)

    # Mostrar lotes descargados en el período
    db = get_session()
    lotes_periodo = (
        db.query(Lote)
          .filter(
              Lote.planta_id == planta_sel.usuario_id,
              Lote.estado.in_(["descargado", "en_planta"]),
              Lote.fecha_descarga >= datetime.combine(periodo.fecha_inicio, datetime.min.time())
          ).all()
    )
    db.close()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Descargas del período",  fmt_kg(bal.get("total_descarga", 0)),
              help="Suma de todos los lotes descargados en este período")
    c2.metric("Material clasificado",   fmt_kg(bal.get("total_clasificado", 0)),
              delta=f"{bal.get('pct_clasificado', 0)}%")
    c3.metric("Rechazo",                fmt_kg(bal.get("total_rechazo", 0)),
              delta=f"{bal.get('pct_rechazo', 0)}%", delta_color="inverse")
    c4.metric("Diferencia (no asignada)", fmt_kg(abs(bal.get("diferencia", 0))),
              delta="✅ Cuadrado" if bal.get("balance_ok") else "⚠️ Pendiente")

    dif = bal.get("diferencia", 0)
    total_d = bal.get("total_descarga", 0)
    pct_asignado = ((bal.get("total_clasificado", 0) + bal.get("total_rechazo", 0)) / total_d * 100) if total_d else 0
    st.progress(min(pct_asignado / 100, 1.0), text=f"{pct_asignado:.1f}% del material descargado asignado")

    if bal.get("balance_ok"):
        st.success("✅ Balance cuadrado para este período.")
    elif dif > 0:
        st.warning(f"⚠️ Quedan **{fmt_kg(dif)}** de material descargado sin registrar como clasificado o rechazo.")
    else:
        st.error(f"❌ Se clasificaron **{fmt_kg(abs(dif))}** más de lo que ingresó. Revisá los registros.")

    # Lotes del período
    if lotes_periodo:
        st.markdown(f"**Lotes descargados en este período ({len(lotes_periodo)})**")
        rows_l = [{
            "Código":    l.codigo_lote,
            "Generador": l.generador.nombre if l.generador else "—",
            "Descarga (kg)": float(l.peso_descarga_kg or 0),
            "Fecha":     l.fecha_descarga.strftime("%d/%m/%Y") if l.fecha_descarga else "",
        } for l in lotes_periodo]
        st.dataframe(pd.DataFrame(rows_l), use_container_width=True, hide_index=True)
    else:
        st.info("No hay lotes descargados en el rango de fechas de este período.")

# ─── HISTORIAL DE PESADAS ─────────────────────────────────────────────────────
with tab_historial:
    db = get_session()
    pesadas = (db.query(PesadaClasificacion)
                 .filter_by(periodo_id=periodo.periodo_id)
                 .order_by(PesadaClasificacion.fecha.desc())
                 .all())
    db.close()

    if pesadas:
        rows = [{
            "Material":  p.material.subcategoria if p.material else "—",
            "Categoría": p.material.categoria if p.material else "—",
            "Peso (kg)": float(p.peso_kg),
            "Calidad":   p.calidad or "—",
            "Operador":  p.operador.nombre if p.operador else "—",
            "Fecha":     p.fecha.strftime("%d/%m/%Y %H:%M") if p.fecha else "",
        } for p in pesadas]
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Gráfico acumulado por material
        df_agg = df.groupby("Material")["Peso (kg)"].sum().reset_index().sort_values("Peso (kg)", ascending=True)
        fig = px.bar(df_agg, x="Peso (kg)", y="Material", orientation="h",
                     color_discrete_sequence=["#39d353"])
        fig.update_layout(
            plot_bgcolor="#161b22", paper_bgcolor="#161b22",
            font_color="#e6edf3", height=300,
            margin=dict(l=0, r=10, t=10, b=0),
            xaxis=dict(gridcolor="#2a3441"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No hay pesadas registradas en este período aún.")
