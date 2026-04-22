"""
Página B2 — Recolección
Actor: Transportista
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import datetime
from models.database import get_session, Lote, EventoAuditoria
from utils.helpers import get_usuarios_por_tipo

st.set_page_config(page_title="B2 · Recolección", page_icon="🚛", layout="wide")
st.markdown("# 🚛 B2 · Recolección")
st.markdown("Registro de hoja de ruta, peso bruto recolectado y remito de carga.")
st.divider()

tab_reg, tab_list = st.tabs(["✏️ Registrar Recolección", "📋 Ver Rutas"])

with tab_reg:
    db = get_session()
    lotes_gen = db.query(Lote).filter_by(estado="generado").order_by(Lote.fecha_generacion.desc()).all()
    db.close()

    transportistas = get_usuarios_por_tipo("transportista")

    if not lotes_gen:
        st.info("No hay solicitudes de retiro pendientes (estado 'generado').")
        st.stop()

    with st.form("form_recoleccion"):
        st.subheader("Registrar Salida de Recolección")
        c1, c2 = st.columns(2)
        with c1:
            lote_sel = st.selectbox(
                "Lote / Solicitud *",
                options=lotes_gen,
                format_func=lambda l: f"{l.codigo_lote} — {l.generador.nombre if l.generador else 'Sin generador'}"
            )
            transportista = st.selectbox(
                "Transportista *",
                options=transportistas,
                format_func=lambda u: f"{u.nombre}"
            )
        with c2:
            peso_recolectado = st.number_input(
                "Peso bruto recolectado (kg) *",
                min_value=1.0, max_value=200000.0, value=480.0, step=5.0
            )
            numero_remito = st.text_input("Número de remito", placeholder="REM-0001-00001")
            fecha_recoleccion = st.date_input("Fecha de recolección", value=datetime.today())

        patente = st.text_input("Patente del vehículo", placeholder="AB 123 CD")
        obs = st.text_area("Observaciones de ruta", height=60)
        submitted = st.form_submit_button("🚛 Registrar Salida", use_container_width=True)

    if submitted:
        db = get_session()
        try:
            lote = db.query(Lote).filter_by(lote_id=lote_sel.lote_id).first()
            lote.transportista_id     = transportista.usuario_id
            lote.peso_recolectado_kg  = peso_recolectado
            lote.estado               = "en_ruta"
            lote.fecha_recoleccion    = datetime.combine(fecha_recoleccion, datetime.min.time())
            if obs or numero_remito or patente:
                lote.observaciones = (lote.observaciones or "") + f"\nB2 | Remito:{numero_remito} | Patente:{patente} | {obs}"

            evento = EventoAuditoria(
                lote_id=lote.lote_id,
                usuario_id=transportista.usuario_id,
                tipo_evento="recoleccion_registrada",
                instancia_b=2,
                descripcion=f"Peso bruto: {peso_recolectado} kg. Remito: {numero_remito}. Patente: {patente}",
            )
            db.add(evento)
            db.commit()
            st.success(f"✅ Recolección registrada. Lote **{lote.codigo_lote}** en ruta.")
        except Exception as e:
            db.rollback()
            st.error(f"Error: {e}")
        finally:
            db.close()

with tab_list:
    db = get_session()
    lotes_ruta = db.query(Lote).filter_by(estado="en_ruta").order_by(Lote.fecha_recoleccion.desc()).all()
    db.close()
    if not lotes_ruta:
        st.info("No hay lotes en ruta actualmente.")
    else:
        rows = [{
            "Código": l.codigo_lote,
            "Generador": l.generador.nombre if l.generador else "—",
            "Transportista": l.transportista.nombre if l.transportista else "—",
            "Peso Bruto (kg)": float(l.peso_recolectado_kg or 0),
            "Fecha": l.fecha_recoleccion.strftime("%d/%m/%Y") if l.fecha_recoleccion else "",
        } for l in lotes_ruta]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
