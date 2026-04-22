"""
P�gina B6 — Ventas del pool de planta.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import pandas as pd
from datetime import datetime
from models.database import (
    get_session, Venta, Certificado, EventoAuditoria, StockActual
)
from utils.helpers import (
    get_usuarios_por_tipo, get_periodo_abierto,
    get_stock_planta, actualizar_stock, fmt_kg, fmt_ars
)

st.set_page_config(page_title="B6 · Ventas", page_icon="💰", layout="wide")
st.markdown("# 💰 B6 · Ventas")
st.divider()

tratadores  = get_usuarios_por_tipo("tratador")
compradores = get_usuarios_por_tipo("comprador")

tab_venta, tab_validar, tab_cert, tab_historial = st.tabs([
    "➕ Registrar Venta", "✅ Validar Recepción", "📜 Emitir Certificado", "📋 Historial"
])

# ─── REGISTRAR VENTA ──────────────────────────────────────────────────────────
with tab_venta:
    planta_sel = st.selectbox("Planta vendedora *", options=tratadores, format_func=lambda u: u.nombre)
    periodo = get_periodo_abierto(planta_sel.usuario_id)
    stock = get_stock_planta(planta_sel.usuario_id)
    stock_disp = [s for s in stock if s["stock_kg"] > 0]

    if not stock_disp:
        st.info("Sin stock disponible para esta planta. Registrá pesadas en Clasificación (B4).")
    elif not compradores:
        st.warning("No hay compradores registrados.")
    else:
        with st.form("form_venta"):
            st.subheader("Nueva venta de material")
            c1, c2 = st.columns(2)
            with c1:
                mat_sel = st.selectbox(
                    "Material a vender *",
                    options=stock_disp,
                    format_func=lambda s: f"{s['material']} — stock: {s['stock_kg']:.0f} kg"
                )
                comprador = st.selectbox("Comprador *", options=compradores, format_func=lambda u: u.nombre)
            with c2:
                max_kg = float(mat_sel["stock_kg"])
                peso_v = st.number_input("Peso a vender (kg) *", min_value=0.1, max_value=max_kg,
                                         value=min(100.0, max_kg), step=0.5)
                precio = st.number_input("Precio por kg (ARS)", min_value=0.0, value=50.0, step=5.0)
                remito = st.text_input("Número de remito", placeholder="REM-B-0001")
                fecha_v = st.date_input("Fecha", value=datetime.today())

            sub = st.form_submit_button("💰 Registrar Venta", use_container_width=True)

        if sub:
            db = get_session()
            try:
                venta = Venta(
                    periodo_id=periodo.periodo_id if periodo else None,
                    planta_id=planta_sel.usuario_id,
                    comprador_id=comprador.usuario_id,
                    material_id=mat_sel["material_id"],
                    numero_remito=remito,
                    peso_vendido_kg=peso_v,
                    precio_por_kg=precio,
                    fecha_venta=datetime.combine(fecha_v, datetime.min.time()),
                )
                db.add(venta)
                actualizar_stock(db, planta_sel.usuario_id, mat_sel["material_id"], -peso_v)
                db.add(EventoAuditoria(
                    periodo_id=periodo.periodo_id if periodo else None,
                    usuario_id=comprador.usuario_id,
                    tipo_evento="venta_registrada",
                    instancia_b=6,
                    descripcion=f"Venta: {mat_sel['material']} {peso_v} kg → {comprador.nombre}. Total: ARS {peso_v*precio:.2f}",
                ))
                db.commit()
                st.success(f"✅ Venta registrada. Total: **{fmt_ars(peso_v * precio)}**")
                st.rerun()
            except Exception as e:
                db.rollback(); st.error(str(e))
            finally:
                db.close()

# ─── VALIDAR RECEPCIÓN ────────────────────────────────────────────────────────
with tab_validar:
    db = get_session()
    pendientes = db.query(Venta).filter_by(validado_comprador=False).order_by(Venta.fecha_venta.desc()).all()
    db.close()

    if not pendientes:
        st.info("No hay ventas pendientes de validación.")
    else:
        for v in pendientes:
            mat_nombre = v.material.subcategoria if v.material else "—"
            comp_nombre = v.comprador.nombre if v.comprador else "—"
            with st.expander(f"🧾 {mat_nombre} — {float(v.peso_vendido_kg):.0f} kg — {comp_nombre} — {v.fecha_venta.strftime('%d/%m/%Y') if v.fecha_venta else ''}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Remito:** {v.numero_remito or '—'}")
                c2.write(f"**$/kg:** {float(v.precio_por_kg or 0):.2f}")
                c3.write(f"**Total:** {fmt_ars(v.total)}")
                if st.button("✅ Confirmar recepción", key=f"val_{v.venta_id}"):
                    db = get_session()
                    try:
                        venta_db = db.query(Venta).filter_by(venta_id=v.venta_id).first()
                        venta_db.validado_comprador = True
                        db.commit()
                        st.success("Recepción confirmada.")
                        st.rerun()
                    except Exception as e:
                        db.rollback(); st.error(str(e))
                    finally:
                        db.close()

# ─── CERTIFICADOS ─────────────────────────────────────────────────────────────
with tab_cert:
    db = get_session()
    validadas_sin_cert = (db.query(Venta)
                           .filter_by(validado_comprador=True)
                           .filter(Venta.certificado == None)
                           .all())
    db.close()

    if not validadas_sin_cert:
        st.info("No hay ventas validadas sin certificado.")
    else:
        with st.form("form_cert"):
            venta_c = st.selectbox(
                "Venta a certificar",
                options=validadas_sin_cert,
                format_func=lambda v: (
                    f"{v.material.subcategoria if v.material else '?'} "
                    f"— {float(v.peso_vendido_kg):.0f} kg "
                    f"— {v.comprador.nombre if v.comprador else '?'}"
                )
            )
            c1, c2 = st.columns(2)
            with c1:
                tipo_c  = st.selectbox("Tipo", ["disposicion_final", "reciclado", "valorizacion"])
                numero_c = st.text_input("Número de certificado", placeholder="CERT-2025-0001")
            with c2:
                emisor_c = st.selectbox("Emisor", options=compradores, format_func=lambda u: u.nombre)
                obs_c    = st.text_area("Observaciones", height=68)
            sub_c = st.form_submit_button("📜 Emitir Certificado", use_container_width=True)

        if sub_c:
            db = get_session()
            try:
                db.add(Certificado(
                    venta_id=venta_c.venta_id,
                    emisor_id=emisor_c.usuario_id,
                    tipo_cert=tipo_c,
                    numero=numero_c,
                    observaciones=obs_c,
                ))
                db.commit()
                st.success(f"✅ Certificado **{numero_c}** emitido.")
            except Exception as e:
                db.rollback(); st.error(str(e))
            finally:
                db.close()

# ─── HISTORIAL ────────────────────────────────────────────────────────────────
with tab_historial:
    db = get_session()
    ventas = db.query(Venta).order_by(Venta.fecha_venta.desc()).limit(50).all()
    db.close()
    if ventas:
        rows = [{
            "Remito":    v.numero_remito or "—",
            "Material":  v.material.subcategoria if v.material else "—",
            "Planta":    v.planta.nombre if v.planta else "—",
            "Comprador": v.comprador.nombre if v.comprador else "—",
            "Peso (kg)": float(v.peso_vendido_kg),
            "$/kg":      float(v.precio_por_kg or 0),
            "Total ARS": round(v.total, 2),
            "Validado":  "✅" if v.validado_comprador else "⏳",
            "Cert.":     "📜" if v.certificado else "—",
            "Fecha":     v.fecha_venta.strftime("%d/%m/%Y") if v.fecha_venta else "",
        } for v in ventas]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("Sin ventas registradas.")
