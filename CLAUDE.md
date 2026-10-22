# CLAUDE.md

Reglas de trabajo para este repositorio.

## Sobre el proyecto

- **Fernwick Platform**: sistema de cotizaciones de Fernwick Home Cleaning, un negocio de limpieza **ficticio** de concepto. Forma parte del portafolio de Renzzo (renzzogg.com) y se muestra en vivo a clientes de Upwork.
- La landing vive en otro repo (`~/proyectos/fernwick-home-cleaning`, en **fernwick.renzzogg.com**) y envía las cotizaciones a esta API. Ese repo tiene su propio `CLAUDE.md`; si una tarea lo toca, se siguen sus reglas.
- Dos partes en este repo:
  - `api/`: Python + FastAPI, PostgreSQL, SQLAlchemy 2.0 + Alembic, JWT, pytest → **fernwick-api.renzzogg.com**.
  - `admin/`: panel en React + Vite + Tailwind CSS → **fernwick-admin.renzzogg.com**.
- Desplegado en **Railway** (PostgreSQL de Railway + un servicio por carpeta). Cada push a `main` se publica en vivo.
- Desarrollo local: PostgreSQL en Ubuntu (WSL), base `fernwick` (y `fernwick_test` para las pruebas).

## Diseño

- **`docs/DESIGN.md` es la fuente de verdad**: modelo de datos, endpoints, seguridad, estructura, fases y despliegue. Léelo antes de cada fase.
- Si una decisión cambia durante la construcción, actualiza `docs/DESIGN.md` en el mismo commit que el cambio.
- Se construye **por fases** (§7 de DESIGN.md). No adelantes trabajo de fases futuras sin preguntar.

## Forma de trabajo

- Soy estudiante de Ingeniería de Software (aprendiendo Python y bases de datos avanzadas) y quiero aprender: **explica las decisiones importantes antes de implementarlas** (qué opciones hay, cuál recomiendas y por qué).
- Al escribir código, explica brevemente los conceptos nuevos (p. ej. una dependencia de FastAPI, una política de RLS, una migración) y por qué se hacen así.
- Comentarios en el código en español, claros y sin exceso.

## Stack y dependencias

- Solo las tecnologías listadas arriba. **No agregues dependencias nuevas** (pip o npm) sin mi aprobación explícita.
- Versiones **exactas**: `==` en `requirements.txt` y sin `^`/`~` en `package.json`. Usa `npm ci` para instalar lo del lockfile.

## Git

- Trabajamos directo en la rama `main`, **sin crear ramas nuevas**.
- Haz commits **locales** con mensajes claros en español.
- **NUNCA** hagas `git push` ni ningún otro comando que suba cambios al remoto. El push lo hago yo.

## Secretos

- **Nunca** subas secretos al repo: contraseñas, `JWT_SECRET`, URLs de base de datos con credenciales, tokens.
- Los archivos `.env` están en `.gitignore` y **no se commitean**. Solo se versionan los `.env.example`, con los nombres de las variables y valores de ejemplo.
- Antes de cada commit revisa `git status` y `git diff --staged` para confirmar que no va ningún secreto.
- No escribas secretos en el código, en migraciones, en tests ni en logs. Toda la configuración se lee de variables de entorno.
- **Nunca** leas ni uses secretos del `.env` (`JWT_SECRET`, contraseñas, etc.) para generar tokens o hacerte pasar por un usuario. Para probar como admin, crea un admin de prueba en `fernwick_test` o usa los fixtures de las pruebas. Si hace falta probar contra la base `fernwick` con mi usuario, pídeme que lo haga yo.

## Reporte al terminar cada tarea

Al terminar cada tarea, entrega un **REPORTE** con:

1. Qué hiciste.
2. Archivos creados / modificados / borrados.
3. Commits hechos (hash y mensaje).
4. Problemas o dudas.
5. Siguientes pasos sugeridos.
