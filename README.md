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
uvicorn app.main:app --reload --no-proxy-headers   # --reload reinicia al guardar cambios
```

- `--no-proxy-headers`: Uvicorn no toca la IP del cliente; la app decide si confía en `X-Forwarded-For`/`CF-Connecting-IP` según `CLIENT_IP_HEADER` (ver DESIGN §5.5).
- Salud: `curl http://localhost:8000/health` → `{"status":"ok","db":"ok"}` (responde `503` si PostgreSQL no está disponible).
- Documentación interactiva: [http://localhost:8000/docs](http://localhost:8000/docs) (desde WSL se abre en el navegador de Windows). Se desactiva con `ENVIRONMENT=production`.

### Probar el formulario público

`POST /v1/public/quotes` guarda una cotización enviada desde la landing. Con la API levantada:

```bash
curl -i -X POST http://localhost:8000/v1/public/quotes \
  -H 'Content-Type: application/json' \
  -d '{
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "phone": "(212) 555-0100",
        "service": "deep",
        "home_size": "3-bed",
        "preferred_date": "'"$(date -d '+7 days' +%F)"'",
        "message": "We have a cat."
      }'
# HTTP/1.1 201 Created
# {"id":42,"created_at":"2026-10-22T02:40:51.310448Z"}
```

- `service`: `standard`, `recurring`, `deep`, `move`, `office` o `post-renovation`. `home_size`: `studio`, `2-bed`, `3-bed`, `4-bed` u `office`. `message` es opcional.
- Si el JSON trae `status`, `is_demo`, `id`, fechas o cualquier campo desconocido → `422`. Un dato inválido (email, teléfono con menos de 10 dígitos, fecha pasada…) también da `422`, con el campo en `detail[].loc`.
- `website` es el honeypot: si llega con valor, responde `201` pero no guarda nada.
- Cuerpo de más de 10 KB → `413`. Más de 5 solicitudes por minuto (o 20 por día) desde la misma IP → `429` con `Retry-After`. El límite vive en memoria: reiniciar `uvicorn` lo borra.
- Solo los orígenes de `CORS_ORIGINS` pueden llamar a la API desde un navegador.

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

**Datos demo:** `python -m app.cli seed-demo` crea el usuario `demo@fernwick.example` (sin contraseña utilizable) y 40 cotizaciones ficticias con notas e historial, con un reparto realista de servicios (sobre todo `standard`, `recurring` y `deep`; pocas `office` y `post-renovation`). Es idempotente: cada ejecución borra las cotizaciones demo y las vuelve a crear, con fechas relativas a hoy, sin tocar las cotizaciones reales.

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
| `CORS_ORIGINS` | `http://localhost:8000,http://localhost:5173` | Orígenes que pueden llamar a la API desde el navegador, separados por comas (nunca `*`; vacío = ninguno) |
| `BUSINESS_TIMEZONE` | `America/New_York` | Zona del negocio: define qué es "hoy" para validar `preferred_date` |
| `CLIENT_IP_HEADER` | `none` | De dónde sale la IP del visitante para el límite de solicitudes: `none` (IP de la conexión), `x-forwarded-for` o `cf-connecting-ip` (producción). Con `none` los encabezados de proxy se ignoran |

La lista completa (incluidas las de fases futuras) está en `docs/DESIGN.md` §5.6.
