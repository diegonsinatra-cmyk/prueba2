# ♻️ Sistema RSU — Trazabilidad de Residuos Sólidos Urbanos

App funcional en Python + Streamlit para gestión y trazabilidad completa
de residuos sólidos urbanos desde generación hasta disposición final.

---

## 🚀 Instalación y Ejecución

### 1. Clonar / descomprimir el proyecto

```bash
cd rsu_app
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv .venv

# Linux / Mac
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar la app

```bash
streamlit run app.py
```

La app abre automáticamente en `http://localhost:8501`

---

## 📁 Estructura del Proyecto

```
rsu_app/
├── app.py                    ← Dashboard principal (página de inicio)
├── requirements.txt
├── rsu_app.db                ← Base de datos SQLite (se crea al primer run)
│
├── models/
│   └── database.py           ← Modelos SQLAlchemy (todas las tablas)
│
├── utils/
│   ├── seed.py               ← Datos iniciales (materiales + usuarios demo)
│   └── helpers.py            ← Funciones de balance, KPIs, helpers
│
└── pages/                    ← Páginas del flujo B1 → B7
    ├── 1_Generacion.py       ← B1: Solicitud de retiro (Generador)
    ├── 2_Recoleccion.py      ← B2: Hoja de ruta y peso bruto (Transportista)
    ├── 3_Descarga_Planta.py  ← B3: Pesaje oficial en planta (Tratador)
    ├── 4_Clasificacion.py    ← B4: Fraccionamiento por tipología ★
    ├── 5_Stock.py            ← B5: Inventario de material clasificado
    ├── 6_Ventas.py           ← B6: Venta + validación + certificados
    └── 7_Reportes.py         ← B7: Rechazo, auditoría, balance Sankey
```

---

## 🗃️ Base de Datos

- **Motor**: SQLite (archivo `rsu_app.db`) — listo para desarrollo local.
- **Producción**: cambiar `DATABASE_URL` en `models/database.py` por una
  conexión PostgreSQL: `postgresql://user:pass@host/dbname`

### Tablas principales

| Tabla                  | Descripción                                      |
|------------------------|--------------------------------------------------|
| `usuarios`             | Actores del sistema (generador/transportista/etc)|
| `materiales`           | Catálogo de tipologías (Plásticos, Cartón, etc.) |
| `lotes`                | Unidad de trazabilidad (B1 → B6)                |
| **`lote_fracciones`**  | ★ **Tabla de conversión** — corazón del sistema  |
| `stock_movimientos`    | Kardex de entradas y salidas por material        |
| `ventas`               | Egresos comerciales con precio y remito          |
| `certificados`         | Documentos de disposición final / reciclado      |
| `rechazos_disposicion` | Registro de material no recuperable              |
| `eventos_auditoria`    | Log inmutable de todas las acciones              |

---

## ⚖️ Lógica de Balance de Masas

### Validación en Clasificación (B4)
```
∑ lote_fracciones.peso_kg WHERE lote_id = X  ≤  lotes.peso_descarga_kg
```
La app bloquea la carga si la suma de fracciones supera el peso de descarga.

### Balance de Inventario
```
Stock Final = Total Clasificado − Total Vendido − Total Rechazo
```
Visible en **B5 · Stock** y en el gráfico Sankey de **Reportes**.

---

## 👥 Actores y Acceso

| Actor          | Páginas principales          |
|----------------|------------------------------|
| Generador      | B1 · Generación              |
| Transportista  | B2 · Recolección             |
| Tratador       | B3, B4, B5 y gestión rechazo |
| Comprador      | B6 Validar + Certificados    |

> Para autenticación multi-usuario en producción, integrar
> `streamlit-authenticator` o un sistema OAuth.

---

## 🔧 Extensiones Sugeridas

- [ ] Autenticación por rol (streamlit-authenticator)
- [ ] Export a Excel/PDF de reportes
- [ ] API REST con FastAPI para integración con sistemas externos
- [ ] Geolocalización de nodos generadores (Folium/deck.gl)
- [ ] Alertas automáticas por balance incompleto
- [ ] Migrar a PostgreSQL para multi-usuario concurrente
