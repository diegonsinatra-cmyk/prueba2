"""
Utilidades: generación de códigos, validaciones y consultas de balance.
"""
from datetime import datetime, date
from sqlalchemy import func
from models.database import (
    get_session, Lote, PesadaClasificacion, RechazoPool,
    StockActual, Material, Venta, Usuario, PeriodoClasificacion
)


def generar_codigo_lote() -> str:
    db = get_session()
    try:
        hoy = datetime.utcnow().strftime("%Y%m%d")
        prefijo = f"LOTE-{hoy}-"
        ultimo = (
            db.query(Lote)
            .filter(Lote.codigo_lote.like(f"{prefijo}%"))
            .order_by(Lote.codigo_lote.desc())
            .first()
        )
        n = int(ultimo.codigo_lote.split("-")[-1]) + 1 if ultimo else 1
        return f"{prefijo}{n:04d}"
    finally:
        db.close()


def get_usuarios_por_tipo(tipo: str) -> list:
    db = get_session()
    try:
        return db.query(Usuario).filter_by(tipo_actor=tipo, activo=True).all()
    finally:
        db.close()


def get_materiales_no_mezclados() -> list:
    db = get_session()
    try:
        return (db.query(Material)
                  .filter_by(es_mezclado=False)
                  .filter(Material.categoria != "Rechazo")
                  .order_by(Material.categoria, Material.subcategoria)
                  .all())
    finally:
        db.close()


def get_periodo_abierto(planta_id: str):
    """Devuelve el período abierto de una planta, o None."""
    db = get_session()
    try:
        return (db.query(PeriodoClasificacion)
                  .filter_by(planta_id=planta_id, estado="abierto")
                  .order_by(PeriodoClasificacion.fecha_inicio.desc())
                  .first())
    finally:
        db.close()


# ─────────────────────────────────────────
# BALANCE DE MASAS POR PERÍODO
# ─────────────────────────────────────────
def calcular_balance_periodo(periodo_id: str) -> dict:
    """
    Balance: sum(descargas lotes en período) = sum(clasificado) + sum(rechazo)
    Los lotes se vinculan al período por planta_id y fecha_descarga.
    """
    db = get_session()
    try:
        periodo = db.query(PeriodoClasificacion).filter_by(periodo_id=periodo_id).first()
        if not periodo:
            return {}

        # Lotes descargados en esta planta dentro del rango de fechas del período
        q_lotes = db.query(func.coalesce(func.sum(Lote.peso_descarga_kg), 0))\
                    .filter(Lote.planta_id == periodo.planta_id,
                            Lote.estado.in_(["descargado", "en_planta"]),
                            Lote.fecha_descarga >= datetime.combine(periodo.fecha_inicio, datetime.min.time()))
        if periodo.fecha_fin:
            q_lotes = q_lotes.filter(
                Lote.fecha_descarga <= datetime.combine(periodo.fecha_fin, datetime.max.time())
            )
        total_descarga = float(q_lotes.scalar())

        total_clasificado = float(
            db.query(func.coalesce(func.sum(PesadaClasificacion.peso_kg), 0))
              .filter_by(periodo_id=periodo_id).scalar()
        )
        total_rechazo = float(
            db.query(func.coalesce(func.sum(RechazoPool.peso_kg), 0))
              .filter_by(periodo_id=periodo_id).scalar()
        )
        total_vendido = float(
            db.query(func.coalesce(func.sum(Venta.peso_vendido_kg), 0))
              .filter_by(periodo_id=periodo_id).scalar()
        )

        diferencia = total_descarga - total_clasificado - total_rechazo

        return {
            "total_descarga":    total_descarga,
            "total_clasificado": total_clasificado,
            "total_rechazo":     total_rechazo,
            "total_vendido":     total_vendido,
            "diferencia":        diferencia,
            "balance_ok":        abs(diferencia) < 1.0,
            "pct_clasificado":   round(total_clasificado / total_descarga * 100, 1) if total_descarga else 0,
            "pct_rechazo":       round(total_rechazo    / total_descarga * 100, 1) if total_descarga else 0,
        }
    finally:
        db.close()


# ─────────────────────────────────────────
# STOCK ACTUAL
# ─────────────────────────────────────────
def get_stock_planta(planta_id: str = None) -> list[dict]:
    db = get_session()
    try:
        q = db.query(StockActual).filter(StockActual.peso_kg > 0)
        if planta_id:
            q = q.filter_by(planta_id=planta_id)
        rows = q.all()
        return [{
            "stock_id":    r.stock_id,
            "planta":      r.planta.nombre if r.planta else "—",
            "categoria":   r.material.categoria if r.material else "—",
            "material":    r.material.subcategoria if r.material else "—",
            "material_id": r.material_id,
            "planta_id":   r.planta_id,
            "stock_kg":    float(r.peso_kg),
        } for r in rows]
    finally:
        db.close()


def actualizar_stock(db, planta_id: str, material_id: str, delta_kg: float):
    """Suma o resta delta_kg del stock de un material en una planta."""
    stock = db.query(StockActual).filter_by(
        planta_id=planta_id, material_id=material_id
    ).first()
    if stock:
        stock.peso_kg = float(stock.peso_kg) + delta_kg
        stock.updated_at = datetime.utcnow()
    else:
        stock = StockActual(
            planta_id=planta_id,
            material_id=material_id,
            peso_kg=max(delta_kg, 0),
        )
        db.add(stock)


# ─────────────────────────────────────────
# KPIs GENERALES
# ─────────────────────────────────────────
def get_kpis() -> dict:
    db = get_session()
    try:
        total_lotes      = db.query(func.count(Lote.lote_id)).scalar() or 0
        lotes_activos    = db.query(func.count(Lote.lote_id)).filter(Lote.estado.in_(["en_ruta"])).scalar() or 0
        total_descarga   = float(db.query(func.coalesce(func.sum(Lote.peso_descarga_kg), 0)).scalar())
        total_clasificado = float(db.query(func.coalesce(func.sum(PesadaClasificacion.peso_kg), 0)).scalar())
        total_rechazo    = float(db.query(func.coalesce(func.sum(RechazoPool.peso_kg), 0)).scalar())
        total_vendido    = float(db.query(func.coalesce(func.sum(Venta.peso_vendido_kg), 0)).scalar())
        ingresos         = float(db.query(func.coalesce(
            func.sum(Venta.peso_vendido_kg * Venta.precio_por_kg), 0)).scalar())

        tasa = round(total_clasificado / total_descarga * 100, 1) if total_descarga else 0

        return {
            "total_lotes":       total_lotes,
            "lotes_activos":     lotes_activos,
            "total_descarga":    total_descarga,
            "total_clasificado": total_clasificado,
            "total_rechazo":     total_rechazo,
            "total_vendido":     total_vendido,
            "ingresos_ars":      ingresos,
            "tasa_recuperacion": tasa,
        }
    finally:
        db.close()


def fmt_kg(v: float) -> str:
    return f"{v:,.1f} kg"

def fmt_ars(v: float) -> str:
    return f"$ {v:,.2f}"
