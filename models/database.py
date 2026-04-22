"""
Modelos de base de datos para el sistema RSU.
Usa SQLite para desarrollo local; cambiar DATABASE_URL para PostgreSQL en producción.

LÓGICA DE TRAZABILIDAD:
  B1-B3: trazabilidad 1:1 por lote (generación → recolección → descarga en planta)
  B4-B7: pool libre por planta. El operador carga pesadas de material clasificado
          sin asociarlas a un lote específico. El balance cierra por período:
          sum(peso_descarga lotes del período) = sum(clasificado) + sum(rechazo)
"""
import uuid
from datetime import datetime
from sqlalchemy import (
    create_engine, Column, String, Numeric, Boolean,
    DateTime, SmallInteger, Text, ForeignKey, Date
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = "sqlite:///rsu_app.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False)
Base = declarative_base()


# ─────────────────────────────────────────
# TABLAS B1-B3: Trazabilidad por lote
# ─────────────────────────────────────────

class Usuario(Base):
    __tablename__ = "usuarios"
    usuario_id  = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nombre      = Column(String(200), nullable=False)
    tipo_actor  = Column(String(20),  nullable=False)
    cuit        = Column(String(13),  unique=True)
    email       = Column(String(150))
    activo      = Column(Boolean, default=True)
    created_at  = Column(DateTime, default=datetime.utcnow)

    lotes_generados     = relationship("Lote", foreign_keys="Lote.generador_id",     back_populates="generador",     lazy="select")
    lotes_transportados = relationship("Lote", foreign_keys="Lote.transportista_id", back_populates="transportista", lazy="select")
    lotes_planta        = relationship("Lote", foreign_keys="Lote.planta_id",        back_populates="planta",        lazy="select")


class Material(Base):
    __tablename__ = "materiales"
    material_id  = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    categoria    = Column(String(50),  nullable=False)
    subcategoria = Column(String(100), nullable=False)
    descripcion  = Column(Text)
    es_mezclado  = Column(Boolean, default=False)
    unidad       = Column(String(10), default="kg")


class Lote(Base):
    """Unidad de trazabilidad B1-B3. Ciclo termina al llegar a 'descargado'."""
    __tablename__ = "lotes"
    lote_id             = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    codigo_lote         = Column(String(30), unique=True, nullable=False)
    generador_id        = Column(String(36), ForeignKey("usuarios.usuario_id"))
    transportista_id    = Column(String(36), ForeignKey("usuarios.usuario_id"))
    planta_id           = Column(String(36), ForeignKey("usuarios.usuario_id"))
    peso_estimado_kg    = Column(Numeric(10, 2))
    peso_recolectado_kg = Column(Numeric(10, 2))
    peso_descarga_kg    = Column(Numeric(10, 2))
    estado              = Column(String(20), default="generado")  # generado|en_ruta|descargado
    observaciones       = Column(Text)
    fecha_generacion    = Column(DateTime, default=datetime.utcnow)
    fecha_recoleccion   = Column(DateTime)
    fecha_descarga      = Column(DateTime)
    created_at          = Column(DateTime, default=datetime.utcnow)

    generador     = relationship("Usuario", foreign_keys=[generador_id],     back_populates="lotes_generados",     lazy="joined")
    transportista = relationship("Usuario", foreign_keys=[transportista_id], back_populates="lotes_transportados", lazy="joined")
    planta        = relationship("Usuario", foreign_keys=[planta_id],        back_populates="lotes_planta",        lazy="joined")


# ─────────────────────────────────────────
# TABLAS B4-B7: Pool por planta y período
# ─────────────────────────────────────────

class PeriodoClasificacion(Base):
    """
    Período de trabajo (default mensual, el operador puede abrirlo/cerrarlo).
    Agrupa pesadas de clasificación y es la base del balance de masas.
    """
    __tablename__ = "periodos_clasificacion"
    periodo_id   = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    planta_id    = Column(String(36), ForeignKey("usuarios.usuario_id"), nullable=False)
    nombre       = Column(String(100), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin    = Column(Date)
    estado       = Column(String(20), default="abierto")  # abierto|cerrado
    created_by   = Column(String(36), ForeignKey("usuarios.usuario_id"))
    created_at   = Column(DateTime, default=datetime.utcnow)

    planta    = relationship("Usuario", foreign_keys=[planta_id],  lazy="joined")
    creador   = relationship("Usuario", foreign_keys=[created_by], lazy="joined")
    pesadas   = relationship("PesadaClasificacion", back_populates="periodo", lazy="select", cascade="all, delete-orphan")
    rechazos  = relationship("RechazoPool",         back_populates="periodo", lazy="select", cascade="all, delete-orphan")
    ventas    = relationship("Venta",               back_populates="periodo", lazy="select")


class PesadaClasificacion(Base):
    """
    Pesada individual de material clasificado.
    Pertenece al pool de la planta — NO vinculada a ningún lote.
    """
    __tablename__ = "pesadas_clasificacion"
    pesada_id     = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    periodo_id    = Column(String(36), ForeignKey("periodos_clasificacion.periodo_id"), nullable=False)
    planta_id     = Column(String(36), ForeignKey("usuarios.usuario_id"), nullable=False)
    material_id   = Column(String(36), ForeignKey("materiales.material_id"), nullable=False)
    operador_id   = Column(String(36), ForeignKey("usuarios.usuario_id"))
    peso_kg       = Column(Numeric(10, 2), nullable=False)
    calidad       = Column(String(50))
    observaciones = Column(Text)
    fecha         = Column(DateTime, default=datetime.utcnow)

    periodo  = relationship("PeriodoClasificacion", back_populates="pesadas", lazy="joined")
    material = relationship("Material", lazy="joined")
    planta   = relationship("Usuario",  foreign_keys=[planta_id],   lazy="joined")
    operador = relationship("Usuario",  foreign_keys=[operador_id], lazy="joined")


class RechazoPool(Base):
    """Rechazo registrado a nivel de pool/período."""
    __tablename__ = "rechazos_pool"
    rechazo_id        = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    periodo_id        = Column(String(36), ForeignKey("periodos_clasificacion.periodo_id"), nullable=False)
    planta_id         = Column(String(36), ForeignKey("usuarios.usuario_id"), nullable=False)
    operador_id       = Column(String(36), ForeignKey("usuarios.usuario_id"))
    peso_kg           = Column(Numeric(10, 2), nullable=False)
    tipo_rechazo      = Column(String(100))
    destino_final     = Column(String(200))
    numero_manifiesto = Column(String(50))
    fecha             = Column(DateTime, default=datetime.utcnow)
    validado          = Column(Boolean, default=False)

    periodo  = relationship("PeriodoClasificacion", back_populates="rechazos", lazy="joined")
    planta   = relationship("Usuario", foreign_keys=[planta_id],   lazy="joined")
    operador = relationship("Usuario", foreign_keys=[operador_id], lazy="joined")


class StockActual(Base):
    """Stock disponible por material y planta. Se actualiza con pesadas y ventas."""
    __tablename__ = "stock_actual"
    stock_id    = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    planta_id   = Column(String(36), ForeignKey("usuarios.usuario_id"), nullable=False)
    material_id = Column(String(36), ForeignKey("materiales.material_id"), nullable=False)
    peso_kg     = Column(Numeric(10, 2), nullable=False, default=0)
    updated_at  = Column(DateTime, default=datetime.utcnow)

    planta   = relationship("Usuario",  lazy="joined")
    material = relationship("Material", lazy="joined")


class Venta(Base):
    """Egreso comercial del pool de la planta. Vinculada al período, no al lote."""
    __tablename__ = "ventas"
    venta_id           = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    periodo_id         = Column(String(36), ForeignKey("periodos_clasificacion.periodo_id"))
    planta_id          = Column(String(36), ForeignKey("usuarios.usuario_id"), nullable=False)
    comprador_id       = Column(String(36), ForeignKey("usuarios.usuario_id"))
    material_id        = Column(String(36), ForeignKey("materiales.material_id"), nullable=False)
    numero_remito      = Column(String(50))
    peso_vendido_kg    = Column(Numeric(10, 2), nullable=False)
    precio_por_kg      = Column(Numeric(10, 4))
    moneda             = Column(String(3), default="ARS")
    fecha_venta        = Column(DateTime, default=datetime.utcnow)
    validado_comprador = Column(Boolean, default=False)

    periodo   = relationship("PeriodoClasificacion", back_populates="ventas",  lazy="joined")
    planta    = relationship("Usuario",  foreign_keys=[planta_id],    lazy="joined")
    comprador = relationship("Usuario",  foreign_keys=[comprador_id], lazy="joined")
    material  = relationship("Material", lazy="joined")
    certificado = relationship("Certificado", back_populates="venta", uselist=False, lazy="joined")

    @property
    def total(self):
        if self.precio_por_kg and self.peso_vendido_kg:
            return float(self.precio_por_kg) * float(self.peso_vendido_kg)
        return 0.0


class Certificado(Base):
    __tablename__ = "certificados"
    cert_id       = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    venta_id      = Column(String(36), ForeignKey("ventas.venta_id"))
    emisor_id     = Column(String(36), ForeignKey("usuarios.usuario_id"))
    tipo_cert     = Column(String(30))
    numero        = Column(String(50), unique=True)
    fecha_emision = Column(DateTime, default=datetime.utcnow)
    observaciones = Column(Text)

    venta  = relationship("Venta",   back_populates="certificado", lazy="joined")
    emisor = relationship("Usuario", lazy="joined")


class EventoAuditoria(Base):
    __tablename__ = "eventos_auditoria"
    evento_id   = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    lote_id     = Column(String(36), ForeignKey("lotes.lote_id"),                          nullable=True)
    periodo_id  = Column(String(36), ForeignKey("periodos_clasificacion.periodo_id"),       nullable=True)
    usuario_id  = Column(String(36), ForeignKey("usuarios.usuario_id"))
    tipo_evento = Column(String(50))
    instancia_b = Column(SmallInteger)
    descripcion = Column(Text)
    created_at  = Column(DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────
# INIT DB
# ─────────────────────────────────────────
def init_db():
    Base.metadata.create_all(bind=engine)

def get_session():
    return SessionLocal()
