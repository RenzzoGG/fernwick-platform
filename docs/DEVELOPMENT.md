# Fernwick Platform — Guía de desarrollo

Guía práctica para trabajar en el proyecto en local: comandos, ejemplos con `curl`, migraciones, pruebas y variables. El resumen en inglés está en el [README](../README.md).

Sistema de cotizaciones de **Fernwick Home Cleaning**, un negocio de limpieza ficticio de concepto (proyecto de portafolio). La landing ([fernwick.renzzogg.com](https://fernwick.renzzogg.com)) envía cotizaciones a esta API, y un panel de administración permite gestionarlas.

- `api/` — Python + FastAPI + PostgreSQL (SQLAlchemy 2.0, Alembic, pytest).
- `admin/` — panel en React + TypeScript + Vite + Tailwind CSS.
- `docs/DESIGN.md` — diseño completo: modelo de datos, endpoints, seguridad, fases y despliegue (ver también [Despliegue](#despliegue-railway--cloudflare)).

## API: desarrollo local

### Requisitos

- Python **3.14** (la versión está fijada en `api/.python-version`; Railway usa la misma).
- PostgreSQL con dos bases a las que tu usuario de Linux pueda entrar por socket Unix sin contraseña (`psql -d fernwick` funciona):
  - `fernwick` — desarrollo.
  - `fernwick_test` — pruebas (pytest la vacía y la recrea; su nombre debe terminar en `_test`).
- Tu usuario de PostgreSQL es el dueño de las tablas y necesita, una sola vez, `CREATEROLE` (la migración `0003` crea los roles `fernwick_app` y `fernwick_demo`) y `BYPASSRLS` (las migraciones, `seed-demo` y las pruebas escriben filas reales y demo):

  ```bash
  sudo -u postgres psql -c "ALTER ROLE $USER CREATEROLE BYPASSRLS"
  ```

### Primera vez

```bash
cd api
python3 -m venv .venv                     # crea el entorno virtual (no se commitea)
source .venv/bin/activate                 # actívalo; el prompt muestra (.venv)
pip install -r requirements-dev.txt       # dependencias de la app + pruebas, versiones exactas
cp .env.example .env                      # configuración local (no se commitea); ajusta las URLs si hace falta
# genera un JWT_SECRET y escríbelo directo en .env, sin mostrarlo en pantalla
# (obligatorio; sin él ni la API ni Alembic arrancan):
sed -i "s|^JWT_SECRET=.*|JWT_SECRET=$(python -c 'import secrets; print(secrets.token_urlsafe(48))')|" .env
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

### Autenticación del panel

Crear el primer administrador (pide la contraseña dos veces sin mostrarla; 12 a 128 caracteres):

```bash
python -m app.cli create-admin --email tu-email@example.com
```

Con la API levantada:

```bash
# Login de admin → token (válido JWT_EXPIRE_MINUTES minutos)
curl -s -X POST http://localhost:8000/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "tu-email@example.com", "password": "tu contraseña"}'
# {"access_token":"eyJ...","token_type":"bearer","expires_in":3600,"role":"admin"}

# Cuenta demo (sin contraseña; requiere DEMO_ENABLED=true y haber corrido seed-demo)
curl -s -X POST http://localhost:8000/v1/auth/demo

# Quién soy: rutas privadas con el header Authorization
TOKEN=$(curl -s -X POST http://localhost:8000/v1/auth/demo | sed -E 's/.*"access_token":"([^"]+)".*/\1/')
curl -s http://localhost:8000/v1/auth/me -H "Authorization: Bearer $TOKEN"
# {"id":1,"email":"demo@fernwick.example","role":"demo"}
```

- Email o contraseña incorrectos, usuario inactivo o intento de entrar al demo con contraseña → `401` con el mismo mensaje.
- Sin token, token vencido, manipulado o de un usuario desactivado → `401`. Rol sin permiso → `403`.
- Límites por IP: login 10 por minuto, demo 20 por minuto → `429` con `Retry-After`.
- `/v1/auth/demo` responde `404` si `DEMO_ENABLED=false` o si falta el usuario demo.
- En `/docs`, el botón **Authorize** permite pegar un token y probar las rutas privadas.

### Endpoints del panel

Todas exigen token. El **demo solo ve cotizaciones ficticias** y el **admin solo las reales** (el filtro lo aplica la capa de servicios). Cambiar estado y agregar notas es **solo para admin**.

```bash
TOKEN=...   # de /v1/auth/login (admin) o /v1/auth/demo
H="Authorization: Bearer $TOKEN"

# Lista: filtros, búsqueda (nombre, email o teléfono por dígitos), paginación y orden
curl -s "http://localhost:8000/v1/quotes" -H "$H"
curl -s "http://localhost:8000/v1/quotes?status=new&page=2&page_size=50&sort=preferred_date" -H "$H"
curl -s "http://localhost:8000/v1/quotes?q=lovelace" -H "$H"
curl -s "http://localhost:8000/v1/quotes?q=555-0142" -H "$H"     # encuentra "(305) 555-0142"
# {"items":[{"id":286,"name":"...","status":"new","created_at":"...Z",...}],"total":1,"page":1,"page_size":20}

# Detalle con notas e historial de estados
curl -s http://localhost:8000/v1/quotes/286 -H "$H"

# Cambiar estado (solo admin; mismo estado → 409)
curl -s -X PATCH http://localhost:8000/v1/quotes/286/status -H "$H" \
  -H 'Content-Type: application/json' -d '{"status": "contacted"}'

# Agregar una nota interna (solo admin) → 201
curl -s -X POST http://localhost:8000/v1/quotes/286/notes -H "$H" \
  -H 'Content-Type: application/json' -d '{"body": "Llamar el lunes"}'

# Métricas: totales por estado y servicio, y los últimos 30 días (con ceros)
curl -s http://localhost:8000/v1/metrics/summary -H "$H"
```

- `status`: `new`, `contacted`, `scheduled` o `closed`. `sort`: `created_at`, `-created_at` (por defecto), `preferred_date` o `-preferred_date`. `page_size`: 1 a 100 (por defecto 20). `q`: 2 a 100 caracteres.
- Cualquier otro valor, un `sort` fuera de la lista o un parámetro desconocido → `422`.
- Sin token → `401`. Demo intentando escribir → `403`. Id que no existe **o que no es visible** para el usuario (p. ej. el demo pidiendo una cotización real) → `404`, con el mismo mensaje.

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

**Datos demo:** `python -m app.cli seed-demo` (corre como el dueño, `MIGRATIONS_DATABASE_URL` o `DATABASE_URL`) crea el usuario `demo@fernwick.example` (sin contraseña utilizable) y 40 cotizaciones ficticias con notas e historial, con un reparto realista de servicios (sobre todo `standard`, `recurring` y `deep`; pocas `office` y `post-renovation`). Es idempotente: cada ejecución borra las cotizaciones demo y las vuelve a crear, con fechas relativas a hoy, sin tocar las cotizaciones reales.

### Roles y Row-Level Security: comprobarlo a mano

La API trabaja con dos roles sin privilegios (`docs/DESIGN.md` §3): `fernwick_app` (admin y formulario: solo filas reales) y `fernwick_demo` (solo lectura de filas demo). En local entras como el dueño, que salta RLS, y cada transacción de la API hace `SET LOCAL ROLE`. Con psql puedes hacer lo mismo (todo dentro de `BEGIN … ROLLBACK`, no cambia nada):

```sql
-- psql -d fernwick
BEGIN;
SET LOCAL ROLE fernwick_app;
SELECT current_user, is_demo, count(*) FROM quotes GROUP BY 1, 2;  -- solo is_demo = f (0 filas si aún no hay reales)
UPDATE quotes SET status = 'closed' WHERE is_demo;                  -- UPDATE 0: las demo "no existen"
ROLLBACK;

BEGIN;
SET LOCAL ROLE fernwick_demo;
SELECT current_user, is_demo, count(*) FROM quotes GROUP BY 1, 2;  -- solo is_demo = t (40 tras seed-demo)
SELECT id, email FROM users;                                        -- solo demo@fernwick.example
SELECT password_hash FROM users;                                    -- ERROR: permission denied for table users
ROLLBACK;

BEGIN;
SET LOCAL ROLE fernwick_demo;
UPDATE quotes SET status = 'closed';                                -- ERROR: permission denied for table quotes
ROLLBACK;

BEGIN;
SET LOCAL ROLE fernwick_app;
INSERT INTO quotes (name, email, phone, service, home_size, preferred_date, is_demo)
VALUES ('Ana Ruiz', 'ana@example.com', '212-555-0100', 'standard', '2-bed', current_date, true);
-- ERROR: new row violates row-level security policy for table "quotes"
ROLLBACK;
```

Y fuera de cualquier transacción, `SELECT current_user;` vuelve a ser tu usuario: `SET LOCAL` dura solo hasta el `COMMIT`/`ROLLBACK`.

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
| `CORS_ORIGINS` | `http://localhost:8080,http://localhost:5173` | Orígenes que pueden llamar a la API desde el navegador, separados por comas (nunca `*`; vacío = ninguno) |
| `BUSINESS_TIMEZONE` | `America/New_York` | Zona del negocio: define qué es "hoy" para validar `preferred_date` |
| `JWT_SECRET` | *(genera uno)* | Clave para firmar los tokens; obligatoria, ≥ 32 bytes: `python -c "import secrets; print(secrets.token_urlsafe(48))"`. Nunca se commitea |
| `JWT_EXPIRE_MINUTES` | `60` | Duración de los tokens de acceso |
| `DEMO_ENABLED` | `true` | Activa `POST /v1/auth/demo` (por defecto `false`) |
| `CLIENT_IP_HEADER` | `none` | De dónde sale la IP del visitante para el límite de solicitudes: `none` (IP de la conexión), `x-forwarded-for` o `cf-connecting-ip` (producción). Con `none` los encabezados de proxy se ignoran |

La lista completa (incluidas las de fases futuras) está en `docs/DESIGN.md` §5.6.

## Panel de administración: desarrollo local

React 19 + TypeScript + Vite + Tailwind CSS v4 + React Router, con `fetch` nativo. La interfaz está en inglés, igual que la landing.

### Requisitos

- Node.js 24 y npm 11 (con los que se generó `package-lock.json`).
- La API corriendo en `http://localhost:8000`, con `http://localhost:5173` en `CORS_ORIGINS`. Para "View demo" hace falta además `DEMO_ENABLED=true` y haber corrido `seed-demo`.

### Primera vez

```bash
cd admin
npm ci                    # instala exactamente lo de package-lock.json
cp .env.example .env      # VITE_API_URL (no es secreta: queda dentro del JavaScript publicado)
```

### Comandos

```bash
npm run dev         # http://localhost:5173, con recarga al guardar
npm run typecheck   # solo verifica los tipos (tsc --noEmit)
npm run build       # tsc --noEmit + vite build → dist/ (falla si falta VITE_API_URL)
npm run preview     # sirve dist/ en http://localhost:4173 para revisar el build
```

- **Dependencias**: versiones exactas (`.npmrc` con `save-exact=true`). Cualquier paquete nuevo necesita aprobación (CLAUDE.md).
- **Tipos de la API**: están en `src/api/types.ts`, escritos a mano a partir de `api/app/schemas/`. Si cambia un esquema, se actualizan en el mismo commit.
- **Sesión**: el token se guarda en memoria y en `sessionStorage`, así sobrevive a F5 pero se borra al cerrar la pestaña. El panel vuelve al login, con el aviso *"Your session has expired"*, en tres casos:
  - cuando vence el token, por un temporizador basado en `expires_in`;
  - cuando la API responde 401 a cualquier petición;
  - si al recargar la página `/auth/me` falla.
  
  Después de volver a entrar, regresa a la página donde estaba (`?next=`).
- **Páginas**: `/dashboard` (métricas; es la página de inicio), `/quotes` (lista) y `/quotes/:id` (detalle). El admin cambia el estado (con confirmación) y agrega notas desde el detalle; el demo ve lo mismo sin controles de edición.
- **Escrituras rechazadas**: si la API responde `403` (p. ej. una escritura forzada desde la consola con la cuenta demo), el panel muestra *"This account is read-only"* y vuelve a pedir `/auth/me`. Si el estado ya era ese (`409`, quizá otro admin lo cambió), relee la cotización y lo avisa.

## Despliegue (Railway + Cloudflare)

- Tres servicios en un proyecto de Railway: **Postgres**, **api** (Root Directory `/api`) y **admin** (Root Directory `/admin`, sitio estático con Caddy). Dominios: [fernwick-api.renzzogg.com](https://fernwick-api.renzzogg.com) y [fernwick-admin.renzzogg.com](https://fernwick-admin.renzzogg.com), detrás de Cloudflare.
- **La configuración de cada servicio se pone a mano en *Settings* de Railway**: start, pre-deploy, healthcheck, watch paths, reinicio y sleep. Los valores exactos están en `docs/DESIGN.md` §8.1. No hay `railway.json` en el repo: Railway declaró obsoleto *Config as Code* (los servicios nuevos no pueden activarlo y deja de leerse el 2026-12-01), y por ahora no se usa su reemplazo, *Infrastructure as Code*.
- Variables, orden del primer despliegue (migración, contraseña de `fernwick_app`, seed demo y admin), Cloudflare y prueba de humo: `docs/DESIGN.md` §8.2–§8.5.
- Cada push a `main` despliega los servicios cuyos *watch paths* cambiaron.
