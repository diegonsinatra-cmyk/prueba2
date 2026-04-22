"""
Datos semilla para inicializar la base de datos con materiales y usuarios demo.
"""
from models.database import init_db, get_session, Material, Usuario


MATERIALES = [
    # MEZCLADO (entrada B3)
    {"categoria": "Mezclado", "subcategoria": "Residuo Seco Mezclado", "descripcion": "Material sin clasificar proveniente de recolección", "es_mezclado": True},
    # PAPEL / CARTÓN
    {"categoria": "Papel/Cartón", "subcategoria": "Cartón de primera",      "descripcion": "Cartón ondulado limpio, sin humedad"},
    {"categoria": "Papel/Cartón", "subcategoria": "Cartón de segunda",      "descripcion": "Cartón con humedad o impurezas leves"},
    {"categoria": "Papel/Cartón", "subcategoria": "Papel blanco",           "descripcion": "Papel de oficina, impreso"},
    {"categoria": "Papel/Cartón", "subcategoria": "Papel de diario",        "descripcion": "Periódicos y revistas"},
    # PLÁSTICOS
    {"categoria": "Plásticos", "subcategoria": "PET Cristal",               "descripcion": "Botellas PET transparentes"},
    {"categoria": "Plásticos", "subcategoria": "PET Color",                 "descripcion": "Botellas PET de color"},
    {"categoria": "Plásticos", "subcategoria": "PEAD Natural",              "descripcion": "Polietileno de alta densidad natural"},
    {"categoria": "Plásticos", "subcategoria": "PEAD Color",                "descripcion": "Polietileno de alta densidad de color"},
    {"categoria": "Plásticos", "subcategoria": "Film LDPE",                 "descripcion": "Polietileno de baja densidad, film"},
    {"categoria": "Plásticos", "subcategoria": "Polipropileno",             "descripcion": "PP general"},
    {"categoria": "Plásticos", "subcategoria": "Telgopor/EPS",              "descripcion": "Poliestireno expandido"},
    # VIDRIO
    {"categoria": "Vidrio", "subcategoria": "Vidrio blanco",                "descripcion": "Vidrio incoloro limpio"},
    {"categoria": "Vidrio", "subcategoria": "Vidrio color",                 "descripcion": "Vidrio verde, ámbar u otro color"},
    # METALES
    {"categoria": "Metales", "subcategoria": "Aluminio",                    "descripcion": "Latas de aluminio y perfiles"},
    {"categoria": "Metales", "subcategoria": "Hierro/Acero",                "descripcion": "Latas de acero, chatarra ferrosa"},
    {"categoria": "Metales", "subcategoria": "Cobre",                       "descripcion": "Cables y piezas de cobre"},
    # RAEES
    {"categoria": "RAEE", "subcategoria": "Pequeños electrodomésticos",     "descripcion": "Electrónica menor"},
    {"categoria": "RAEE", "subcategoria": "Celulares/Computadoras",         "descripcion": "IT y telecomunicaciones"},
    # RECHAZO
    {"categoria": "Rechazo", "subcategoria": "Rechazo general",             "descripcion": "Material sin valor recuperable", "es_mezclado": False},
    {"categoria": "Rechazo", "subcategoria": "Rechazo peligroso",           "descripcion": "Requiere gestión especial"},
]

USUARIOS_DEMO = [
    {"nombre": "Municipio de San Martín",   "tipo_actor": "generador",     "cuit": "30-12345678-9", "email": "rsu@smaratin.gob.ar"},
    {"nombre": "Supermercado Mayorista SRL","tipo_actor": "generador",     "cuit": "30-98765432-1", "email": "logistica@mayorista.com"},
    {"nombre": "Transporte Verde S.A.",     "tipo_actor": "transportista", "cuit": "30-11223344-5", "email": "operaciones@tverde.com.ar"},
    {"nombre": "Logística Circular SRL",    "tipo_actor": "transportista", "cuit": "30-55667788-2", "email": "admin@lcircular.com"},
    {"nombre": "Cooperativa El Recupero",   "tipo_actor": "tratador",      "cuit": "33-44556677-8", "email": "planta@elrecupero.coop"},
    {"nombre": "Planta RSU Norte",          "tipo_actor": "tratador",      "cuit": "30-33221100-6", "email": "contacto@planranorte.com"},
    {"nombre": "Reciclados del Plata S.A.", "tipo_actor": "comprador",     "cuit": "30-77889900-3", "email": "compras@rdelplata.com"},
    {"nombre": "PaperMax Argentina",        "tipo_actor": "comprador",     "cuit": "30-66554433-7", "email": "insumos@papermax.com.ar"},
]


def seed_database():
    init_db()
    db = get_session()
    try:
        # Materiales
        if db.query(Material).count() == 0:
            for m in MATERIALES:
                mat = Material(
                    categoria=m["categoria"],
                    subcategoria=m["subcategoria"],
                    descripcion=m.get("descripcion", ""),
                    es_mezclado=m.get("es_mezclado", False),
                    unidad="kg"
                )
                db.add(mat)
            db.commit()
            print(f"✓ {len(MATERIALES)} materiales creados")

        # Usuarios demo
        if db.query(Usuario).count() == 0:
            for u in USUARIOS_DEMO:
                usr = Usuario(
                    nombre=u["nombre"],
                    tipo_actor=u["tipo_actor"],
                    cuit=u["cuit"],
                    email=u["email"],
                )
                db.add(usr)
            db.commit()
            print(f"✓ {len(USUARIOS_DEMO)} usuarios demo creados")

    except Exception as e:
        db.rollback()
        print(f"Error en seed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
    print("Base de datos inicializada correctamente.")
