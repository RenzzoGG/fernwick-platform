# Fernwick Platform

Sistema de cotizaciones de **Fernwick Home Cleaning**, un negocio de limpieza ficticio de concepto (proyecto de portafolio). La landing ([fernwick.renzzogg.com](https://fernwick.renzzogg.com)) envía cotizaciones a esta API, y un panel de administración permite gestionarlas.

- `api/` — Python + FastAPI + PostgreSQL (SQLAlchemy 2.0, Alembic, pytest).
- `admin/` — panel en React + Vite + Tailwind CSS (fase 7).
- `docs/DESIGN.md` — diseño completo: modelo de datos, endpoints, seguridad, fases y despliegue.

## API: desarrollo local

### Requisitos

- Python **3.14** (la versión está fijada en `api/.python-version`; Railway usa la misma).
- PostgreSQL con dos bases a las que tu usuario de Linux pueda entrar por socket Unix sin contraseña (`psql -d fernwick` funciona):
  - `fernwick` — desarrollo.
  - `fernwick_test` — pruebas (pytest la vacía y la recrea; su nombre debe terminar en `_test`).

### Primera vez

```bash
cd api
python3 -m venv .venv                     # crea el entorno virtual (no se commitea)
source .venv/bin/activate                 # actívalo; el prompt muestra (.venv)
pip install -r requirements-dev.txt       # dependencias de la app + pruebas, versiones exactas
cp .env.example .env                      # configuración local (no se commitea); ajusta las URLs si hace falta
alembic upgrade head                      # crea las tablas en la base de DATABASE_URL
python -m app.cli seed-demo               # (opcional) datos ficticios para la cuenta demo
```

### Levantar la API

```bash
cd api
source .venv/bin/activate
uvicorn app.main:app --reload             # --reload reinicia al guardar cambios
```

- Salud: `curl http://localhost:8000/health` → `{"status":"ok","db":"ok"}` (responde `503` si PostgreSQL no está disponible).
- Documentación interactiva: [http://localhost:8000/docs](http://localhost:8000/docs) (desde WSL se abre en el navegador de Windows). Se desactiva con `ENVIRONMENT=production`.

### Base de datos: migraciones y datos demo

El esquema de la base lo definen los modelos (`app/models/`) y lo aplican las migraciones de Alembic (`alembic/versions/`). Nunca se crean ni modifican tablas a mano.

```bash
cd api
source .venv/bin/activate
alembic upgrade head                      # aplica las migraciones pendientes
alembic current                           # muestra en qué migración está la base
alembic downgrade -1                      # revierte la última migración
alembic upgrade head --sql                # muestra el SQL sin ejecutarlo
```

Tras cambiar un modelo:

```bash
alembic revision --autogenerate -m "describir el cambio"   # genera la migración comparando modelos y base
# revisar y ajustar a mano el archivo generado en alembic/versions/
alembic upgrade head
alembic check                             # confirma que modelos y base coinciden
```

**Datos demo:** `python -m app.cli seed-demo` crea el usuario `demo@fernwick.example` (sin contraseña utilizable) y 40 cotizaciones ficticias con notas e historial. Es idempotente: cada ejecución borra las cotizaciones demo y las vuelve a crear, con fechas relativas a hoy, sin tocar las cotizaciones reales.

### Correr las pruebas

```bash
cd api
source .venv/bin/activate
pytest -v
```

Las pruebas usan la base de `TEST_DATABASE_URL` (`fernwick_test`), nunca la de desarrollo, así que PostgreSQL debe estar corriendo (`sudo service postgresql start` en WSL):

- Al empezar, revierten y aplican todas las migraciones desde cero.
- Cada prueba corre dentro de una transacción que se revierte al terminar: la base queda vacía.
- Si el nombre de la base no termina en `_test`, pytest se niega a correr.

### Variables de entorno

| Variable | Ejemplo | Para qué |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `test` o `production` (en producción no hay `/docs`) |
| `DATABASE_URL` | `postgresql+psycopg://renzzo@/fernwick?host=/var/run/postgresql` | Conexión a PostgreSQL (API y Alembic) |
| `TEST_DATABASE_URL` | `postgresql+psycopg://renzzo@/fernwick_test?host=/var/run/postgresql` | Base de pruebas (solo pytest) |

La lista completa (incluidas las de fases futuras) está en `docs/DESIGN.md` §5.6.
