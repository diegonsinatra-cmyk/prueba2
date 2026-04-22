"""
Script de migracion - corrige datos existentes en la BD.
Ejecutar UNA sola vez: python3 migrar_datos.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from models.database import init_db, get_session, Lote, PeriodoClasificacion, Base, engine

def migrar():
    # Asegura que las tablas nuevas existen
    init_db()
    db = get_session()
    try:
        # 1. Corregir lotes con estado "en_planta" -> "descargado"
        lotes_viejos = db.query(Lote).filter_by(estado="en_planta").all()
        for l in lotes_viejos:
            l.estado = "descargado"
        print(f"  Lotes corregidos en_planta -> descargado: {len(lotes_viejos)}")

        # 2. Eliminar periodos duplicados (dejar solo el mas reciente por planta)
        periodos = db.query(PeriodoClasificacion).order_by(
            PeriodoClasificacion.planta_id,
            PeriodoClasificacion.created_at.desc()
        ).all()

        vistos = set()
        duplicados = []
        for p in periodos:
            key = (p.planta_id, p.nombre)
            if key in vistos:
                duplicados.append(p)
            else:
                vistos.add(key)

        for p in duplicados:
            db.delete(p)
        print(f"  Periodos duplicados eliminados: {len(duplicados)}")

        # 3. Reabrir periodos cerrados sin pesadas (para que se puedan usar)
        for p in db.query(PeriodoClasificacion).filter_by(estado="cerrado").all():
            if len(p.pesadas) == 0 and len(p.rechazos) == 0:
                p.estado = "abierto"
                p.fecha_fin = None
                print(f"  Periodo reabierto: {p.nombre} ({p.planta_id[:8]}...)")

        db.commit()
        print("\nMigracion completada.")

        # Verificar resultado
        print("\n=== ESTADO FINAL ===")
        for l in db.query(Lote).all():
            print(f"  Lote {l.codigo_lote} | estado={l.estado} | descarga={l.peso_descarga_kg} kg")
        for p in db.query(PeriodoClasificacion).all():
            print(f"  Periodo '{p.nombre}' | estado={p.estado} | planta={p.planta_id[:8]}...")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    migrar()
