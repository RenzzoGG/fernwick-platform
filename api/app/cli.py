"""Comandos de administración. Uso: python -m app.cli <comando>

Comandos:
  seed-demo                   Crea (o reinicia) los datos ficticios de la cuenta demo.
  create-admin --email EMAIL  Crea un administrador (pide la contraseña sin mostrarla).
"""

import argparse
import getpass
import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal, owner_session
from app.models import Quote, QuoteNote, QuoteStatusChange, User
from app.models.base import HOME_SIZES, SERVICES
from app.models.user import DEMO_EMAIL
from app.services.auth import AdminCreationError, create_admin

DEMO_QUOTE_COUNT = 40
# Semilla fija: cada ejecución genera exactamente las mismas cotizaciones
RANDOM_SEED = 42

FIRST_NAMES = [
    "Olivia", "Liam", "Emma", "Noah", "Ava", "Elijah", "Sophia", "James", "Isabella", "Lucas",
    "Mia", "Mason", "Harper", "Ethan", "Amelia", "Logan", "Ella", "Aiden", "Grace", "Caleb",
]
LAST_NAMES = [
    "Carter", "Bennett", "Hayes", "Morgan", "Reed", "Brooks", "Foster", "Ward", "Price", "Coleman",
    "Hughes", "Parker", "Sullivan", "Russell", "Griffin", "Hayward", "Ellis", "Barnes", "Fisher", "Porter",
]
AREA_CODES = ["212", "312", "415", "617", "646", "718", "773", "917"]
MESSAGES = [
    "We have two cats, please use pet-safe products.",
    "Key is with the building concierge.",
    "Please focus on the kitchen and bathrooms.",
    "Moving out at the end of the month, need the deposit back!",
    "Mornings work best for us.",
    "There is a small dog that is very friendly.",
    None,
    None,
]
NOTES = {
    "contacted": [
        "Called the client, sent a price estimate by email.",
        "Left a voicemail and followed up by email.",
        "Client asked about eco-friendly products, confirmed we use them.",
    ],
    "scheduled": [
        "Visit confirmed, team of two assigned.",
        "Scheduled for the preferred date, client will leave the key.",
    ],
    "closed": [
        "Job completed, client very happy.",
        "Client decided to postpone; closing for now.",
        "Completed and invoiced. Offered a recurring plan.",
    ],
}
# Peso (porcentaje) de cada servicio en los datos demo (reparto realista: la mayoría pide limpiezas
# normales, recurrentes o profundas; post-obra y oficinas son poco frecuentes).
# Van por nombre y no por posición: si se agrega un servicio sin peso, falla con KeyError.
SERVICE_WEIGHTS = {
    "standard": 35,
    "recurring": 25,
    "deep": 20,
    "move": 12,
    "office": 5,
    "post-renovation": 3,
}
# Tamaños de vivienda (todos menos "office", que solo corresponde al servicio de oficinas)
HOME_ONLY_SIZES = [size for size in HOME_SIZES if size != "office"]
# Caminos de estados posibles hasta cada estado final
STATUS_PATHS = {
    "new": [[]],
    "contacted": [["contacted"]],
    "scheduled": [["contacted", "scheduled"]],
    "closed": [["contacted", "scheduled", "closed"], ["contacted", "closed"]],
}


def _pick_status(rng: random.Random, days_ago: int) -> str:
    # Las cotizaciones recientes suelen estar sin atender; las antiguas, cerradas
    if days_ago <= 3:
        weights = [70, 25, 5, 0]
    elif days_ago <= 20:
        weights = [15, 35, 35, 15]
    else:
        weights = [5, 10, 25, 60]
    return rng.choices(["new", "contacted", "scheduled", "closed"], weights=weights)[0]


def _service_list(rng: random.Random, count: int) -> list[str]:
    """Lista de `count` servicios en la proporción exacta de SERVICE_WEIGHTS, en orden aleatorio.

    No se sortea cada servicio por separado: con solo 40 cotizaciones el azar podría dejar,
    p. ej., más "recurring" que "standard". Se reparte con el método del mayor resto:
    cada servicio recibe la parte entera de su cuota y las cotizaciones que sobran van a
    los de mayor fracción, así la suma da exactamente `count`.
    """
    total = sum(SERVICE_WEIGHTS[service] for service in SERVICES)
    quotas = {service: SERVICE_WEIGHTS[service] * count / total for service in SERVICES}
    counts = {service: int(quota) for service, quota in quotas.items()}
    leftover = count - sum(counts.values())
    for service in sorted(SERVICES, key=lambda s: quotas[s] - counts[s], reverse=True)[:leftover]:
        counts[service] += 1

    services = [service for service in SERVICES for _ in range(counts[service])]
    rng.shuffle(services)
    return services


def _pick_home_size(rng: random.Random, service: str) -> str:
    # Una oficina se cotiza como "office"; una casa nunca tiene tamaño "office"
    return "office" if service == "office" else rng.choice(HOME_ONLY_SIZES)


def _ensure_demo_user(session: Session) -> int:
    """Crea el usuario demo si no existe y devuelve su id (idempotente)."""
    # INSERT ... ON CONFLICT DO NOTHING: si ya existe un email igual (sin distinguir
    # mayúsculas, según el índice único lower(email)), no hace nada y no da error.
    # password_hash "!" no es un hash válido: nadie puede entrar con contraseña a esta cuenta.
    session.execute(
        insert(User)
        .values(email=DEMO_EMAIL, password_hash="!", role="demo")
        .on_conflict_do_nothing(index_elements=[func.lower(User.email)])
    )
    return session.scalar(select(User.id).where(func.lower(User.email) == DEMO_EMAIL))


def seed_demo(session: Session, now: datetime | None = None) -> dict[str, int]:
    """Reinicia los datos demo: borra las cotizaciones demo y las vuelve a crear.

    No hace commit: quien la llama decide (el comando hace commit; las pruebas, rollback).
    """
    now = now or datetime.now(timezone.utc)
    rng = random.Random(RANDOM_SEED)
    # Generador aparte para servicio y tamaño: cambiar sus pesos no altera el resto de los
    # datos (nombres, fechas, estados), que siguen saliendo de `rng`
    service_rng = random.Random(RANDOM_SEED + 1)
    services = _service_list(service_rng, DEMO_QUOTE_COUNT)
    demo_user_id = _ensure_demo_user(session)

    # Borra solo las filas demo. ON DELETE CASCADE elimina también sus notas e historial.
    session.execute(delete(Quote).where(Quote.is_demo))

    quotes = []
    for i in range(DEMO_QUOTE_COUNT):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        days_ago = rng.randint(0, 59)
        created_at = now - timedelta(days=days_ago, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        final_status = _pick_status(rng, days_ago)
        service = services[i]
        home_size = _pick_home_size(service_rng, service)

        quote = Quote(
            name=f"{first} {last}",
            email=f"{first}.{last}{i}@example.com".lower(),
            # 555-0100 a 555-0199: rango reservado para números ficticios en EE. UU.
            phone=f"({rng.choice(AREA_CODES)}) 555-01{rng.randint(0, 99):02d}",
            service=service,
            home_size=home_size,
            preferred_date=(created_at + timedelta(days=rng.randint(2, 21))).date(),
            message=rng.choice(MESSAGES),
            status=final_status,
            is_demo=True,
            created_at=created_at,
            updated_at=created_at,
        )

        # Historial coherente con el estado final: new -> contacted -> ... con fechas crecientes
        previous, changed_at = "new", created_at
        for status in rng.choice(STATUS_PATHS[final_status]):
            changed_at = min(changed_at + timedelta(hours=rng.randint(2, 48)), now)
            quote.status_changes.append(
                QuoteStatusChange(
                    from_status=previous,
                    to_status=status,
                    changed_by=demo_user_id,
                    is_demo=True,
                    changed_at=changed_at,
                )
            )
            quote.notes.append(
                QuoteNote(
                    body=rng.choice(NOTES[status]),
                    author_id=demo_user_id,
                    is_demo=True,
                    created_at=changed_at,
                )
            )
            previous = status
        quote.updated_at = changed_at
        quotes.append(quote)

    session.add_all(quotes)
    session.flush()  # envía los INSERT dentro de la transacción actual (sin commit)

    return {
        "quotes": len(quotes),
        "notes": sum(len(q.notes) for q in quotes),
        "status_changes": sum(len(q.status_changes) for q in quotes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Comandos de Fernwick API")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("seed-demo", help="crea o reinicia los datos ficticios de la cuenta demo")
    admin_parser = subcommands.add_parser("create-admin", help="crea un usuario administrador")
    admin_parser.add_argument("--email", required=True)
    args = parser.parse_args()

    if args.command == "seed-demo":
        # session.begin(): hace commit al terminar el bloque, o rollback si hubo un error.
        # Así el reinicio es atómico: nunca quedan los datos demo a medias.
        # Como dueño: borra y crea filas demo, algo que RLS no le permite al rol de la API.
        with owner_session() as session, session.begin():
            counts = seed_demo(session)
        print(
            f"Datos demo listos: {counts['quotes']} cotizaciones, "
            f"{counts['notes']} notas y {counts['status_changes']} cambios de estado."
        )
    elif args.command == "create-admin":
        # getpass: lee sin mostrar lo que se escribe. La contraseña no va como argumento
        # porque quedaría en el historial de la terminal y en la lista de procesos.
        password = getpass.getpass("Contraseña: ")
        if getpass.getpass("Repite la contraseña: ") != password:
            sys.exit("Las contraseñas no coinciden.")
        try:
            with SessionLocal() as session, session.begin():
                user = create_admin(session, args.email, password)
                # Se leen antes de cerrar la sesión (después el objeto ya no está ligado a ella)
                email, user_id = user.email, user.id
        except AdminCreationError as exc:
            sys.exit(str(exc))
        print(f"Administrador creado: {email} (id {user_id}).")


if __name__ == "__main__":
    main()
