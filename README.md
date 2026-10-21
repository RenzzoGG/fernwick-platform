# Fernwick Platform

Sistema de cotizaciones de **Fernwick Home Cleaning**, un negocio de limpieza ficticio de concepto (proyecto de portafolio). La landing ([fernwick.renzzogg.com](https://fernwick.renzzogg.com)) envía cotizaciones a esta API, y un panel de administración permite gestionarlas.

- `api/` — Python + FastAPI + PostgreSQL (SQLAlchemy 2.0, Alembic, pytest).
- `admin/` — panel en React + Vite + Tailwind CSS (fase 6).
- `docs/DESIGN.md` — diseño completo: modelo de datos, endpoints, seguridad, fases y despliegue.

## API: desarrollo local

### Requisitos

- Python **3.14** (la versión está fijada en `api/.python-version`; Railway usa la misma).
- PostgreSQL con una base `fernwick` a la que tu usuario de Linux pueda entrar por socket Unix (`psql -d fernwick` funciona sin contraseña).

### Primera vez

```bash
cd api
python3 -m venv .venv                     # crea el entorno virtual (no se commitea)
source .venv/bin/activate                 # actívalo; el prompt muestra (.venv)
pip install -r requirements-dev.txt       # dependencias de la app + pruebas, versiones exactas
cp .env.example .env                      # configuración local (no se commitea); ajusta DATABASE_URL si hace falta
```

### Levantar la API

```bash
cd api
source .venv/bin/activate
uvicorn app.main:app --reload             # --reload reinicia al guardar cambios
```

- Salud: `curl http://localhost:8000/health` → `{"status":"ok","db":"ok"}` (responde `503` si PostgreSQL no está disponible).
- Documentación interactiva: [http://localhost:8000/docs](http://localhost:8000/docs) (desde WSL se abre en el navegador de Windows). Se desactiva con `ENVIRONMENT=production`.

### Correr las pruebas

```bash
cd api
source .venv/bin/activate
pytest -v
```

Las pruebas usan la base del `DATABASE_URL` de `.env`, así que PostgreSQL debe estar corriendo (`sudo service postgresql start` en WSL).

### Variables de entorno

| Variable | Ejemplo | Para qué |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `test` o `production` (en producción no hay `/docs`) |
| `DATABASE_URL` | `postgresql+psycopg://renzzo@/fernwick?host=/var/run/postgresql` | Conexión a PostgreSQL |

La lista completa (incluidas las de fases futuras) está en `docs/DESIGN.md` §5.6.
