"""
Página B1 — Generación
Actor: Generador (municipio / gran generador)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
from datetime import datetime
from models.database import get_session, Lote, EventoAuditoria
from utils.helpers import get_usuarios_por_tipo, generar_codigo_lote, fmt_kg

st.set_page_config(page_title="B1 · Generación", page_icon="🏭", layout="wide")

st.markdown("# 🏭 B1 · Generación")
st.markdown("Registro de solicitud de retiro y estimación de volumen.")
st.divider()

tab_nuevo, tab_listar = st.tabs(["➕ Nueva Solicitud", "📋 Solicitudes Existentes"])

# ─── NUEVA SOLICITUD ──────────────────────────────────────────────────────────
with tab_nuevo:
    generadores = get_usuarios_por_tipo("generador")
    if not generadores:
        st.warning("No hay generadores registrados. Agregue usuarios desde la BD.")
        st.stop()

    with st.form("form_generacion"):
        st.subheader("Nueva Solicitud de Retiro")
        c1, c2 = st.columns(2)
        with c1:
            generador = st.selectbox(
                "Generador *",
                options=generadores,
                format_func=lambda u: f"{u.nombre} ({u.cuit})"
            )
            peso_estimado = st.number_input(
                "Peso estimado (kg) *", min_value=1.0, max_value=100000.0,
                value=500.0, step=10.0
            )
        with c2:
            descripcion_carga = st.text_area(
                "Descripción de la carga",
                placeholder="Ej: Residuo seco de recolección diferenciada, bolsones azules…",
                height=100,
            )
            fecha_retiro = st.date_input("Fecha estimada de retiro *", value=datetime.today())

        observaciones = st.text_area("Observaciones adicionales", height=60)
        submitted = st.form_submit_button("📤 Registrar Solicitud", use_container_width=True)

    if submitted:
        codigo = generar_codigo_lote()
        db = get_session()
        try:
            lote = Lote(
                codigo_lote=codigo,
                generador_id=generador.usuario_id,
                peso_estimado_kg=peso_estimado,
                estado="generado",
                observaciones=f"{descripcion_carga}\n{observaciones}".strip(),
                fecha_generacion=datetime.combine(fecha_retiro, datetime.min.time()),
            )
            db.add(lote)
            db.flush()
            evento = EventoAuditoria(
                lote_id=lote.lote_id,
                usuario_id=generador.usuario_id,
                tipo_evento="solicitud_generacion",
                instancia_b=1,
                descripcion=f"Solicitud creada. Peso estimado: {peso_estimado} kg",
            )
            db.add(evento)
            db.commit()
            st.success(f"✅ Solicitud registrada correctamente. Código: **{codigo}**")
            st.balloons()
        except Exception as e:
            db.rollback()
            st.error(f"Error al registrar: {e}")
        finally:
            db.close()

# ─── LISTAR ───────────────────────────────────────────────────────────────────
with tab_listar:
    import pandas as pd
    db = get_session()
    lotes = db.query(Lote).filter_by(estado="generado").order_by(Lote.fecha_generacion.desc()).all()
    db.close()

    if not lotes:
        st.info("No hay solicitudes en estado 'generado'.")
    else:
        rows = []
        for l in lotes:
            rows.append({
                "Código": l.codigo_lote,
                "Generador": l.generador.nombre if l.generador else "—",
                "Peso Estimado (kg)": float(l.peso_estimado_kg or 0),
                "Fecha Solicitud": l.fecha_generacion.strftime("%d/%m/%Y") if l.fecha_generacion else "",
                "Observaciones": (l.observaciones or "")[:60],
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption(f"Total: {len(rows)} solicitudes pendientes de retiro")
