"""
Página B3 — Descarga en Planta
Actor: Tratador (cooperativa / planta)
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import datetime
from models.database import get_session, Lote, EventoAuditoria
from utils.helpers import get_usuarios_por_tipo

st.set_page_config(page_title="B3 · Descarga en Planta", page_icon="📥", layout="wide")
st.markdown("# 📥 B3 · Descarga en Planta")
st.markdown("Pesaje oficial de entrada. Genera el **lote definitivo** para clasificación.")
st.divider()

tab_reg, tab_list = st.tabs(["✏️ Registrar Descarga", "📋 Lotes en Planta"])

with tab_reg:
    db = get_session()
    lotes_ruta = db.query(Lote).filter_by(estado="en_ruta").order_by(Lote.fecha_recoleccion.desc()).all()
    db.close()
    tratadores = get_usuarios_por_tipo("tratador")

    if not lotes_ruta:
        st.info("No hay lotes en ruta pendientes de descarga.")
        st.stop()
    if not tratadores:
        st.warning("No hay plantas/tratadores registrados.")
        st.stop()

    with st.form("form_descarga"):
        st.subheader("Registrar Ingreso a Planta")
        c1, c2 = st.columns(2)
        with c1:
            lote_sel = st.selectbox(
                "Lote en ruta *",
                options=lotes_ruta,
                format_func=lambda l: f"{l.codigo_lote} · {float(l.peso_recolectado_kg or 0):.0f} kg"
            )
            planta = st.selectbox(
                "Planta receptora *",
                options=tratadores,
                format_func=lambda u: u.nombre
            )
        with c2:
            peso_descarga = st.number_input(
                "Peso en báscula de planta (kg) *",
                min_value=1.0, max_value=200000.0, value=470.0, step=1.0,
                help="Este es el peso oficial que se usará para el balance de clasificación"
            )
            fecha_descarga = st.date_input("Fecha de descarga", value=datetime.today())

        st.info(
            f"⚠️ El peso ingresado aquí (**báscula de planta**) será el valor de referencia "
            f"para la validación del balance en la etapa de clasificación (B4). "
            f"La suma de todas las fracciones debe ser igual a este valor."
        )

        obs = st.text_area("Observaciones", height=60)
        submitted = st.form_submit_button("📥 Confirmar Descarga", use_container_width=True)

    if submitted:
        db = get_session()
        try:
            lote = db.query(Lote).filter_by(lote_id=lote_sel.lote_id).first()
            prev_peso = float(lote.peso_recolectado_kg or 0)
            diferencia = peso_descarga - prev_peso
            lote.planta_id        = planta.usuario_id
            lote.peso_descarga_kg = peso_descarga
            lote.estado           = "descargado"
            lote.fecha_descarga   = datetime.combine(fecha_descarga, datetime.min.time())
            if obs:
                lote.observaciones = (lote.observaciones or "") + f"\nB3 | {obs}"

            evento = EventoAuditoria(
                lote_id=lote.lote_id,
                usuario_id=planta.usuario_id,
                tipo_evento="descarga_planta",
                instancia_b=3,
                descripcion=(
                    f"Peso descarga: {peso_descarga} kg. "
                    f"Diferencia con recolección: {diferencia:+.1f} kg."
                ),
            )
            db.add(evento)
            db.commit()

            if abs(diferencia) > prev_peso * 0.05:
                st.warning(
                    f"⚠️ Diferencia de **{diferencia:+.1f} kg** respecto al peso recolectado "
                    f"({prev_peso:.0f} kg). Considere registrar la discrepancia."
                )
            st.success(f"✅ Descarga registrada. Lote **{lote.codigo_lote}** listo para clasificación (B4).")
        except Exception as e:
            db.rollback()
            st.error(f"Error: {e}")
        finally:
            db.close()

with tab_list:
    db = get_session()
    lotes = db.query(Lote).filter(
        Lote.estado.in_(["descargado", "en_planta"])
    ).order_by(Lote.fecha_descarga.desc()).all()
    db.close()
    if not lotes:
        st.info("No hay lotes descargados en planta.")
    else:
        rows = [{
            "Codigo":               l.codigo_lote,
            "Planta":               l.planta.nombre if l.planta else "-",
            "Recolectado (kg)":     float(l.peso_recolectado_kg or 0),
            "Descarga (kg)":        float(l.peso_descarga_kg or 0),
            "Dif (kg)":             round(float(l.peso_descarga_kg or 0) - float(l.peso_recolectado_kg or 0), 1),
            "Fecha":                l.fecha_descarga.strftime("%d/%m/%Y") if l.fecha_descarga else "",
        } for l in lotes]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        total = sum(r["Descarga (kg)"] for r in rows)
        st.caption(f"Total descargado: {total:,.1f} kg en {len(rows)} lotes")
