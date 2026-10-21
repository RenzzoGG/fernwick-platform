"""Comandos de administración. Uso: python -m app.cli <comando>

Comandos:
  seed-demo   Crea (o reinicia) los datos ficticios de la cuenta demo.
"""

import argparse
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Quote, QuoteNote, QuoteStatusChange, User
from app.models.base import HOME_SIZES, SERVICES

DEMO_EMAIL = "demo@fernwick.example"  # .example es un dominio reservado: nunca será real
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
    demo_user_id = _ensure_demo_user(session)

    # Borra solo las filas demo. ON DELETE CASCADE elimina también sus notas e historial.
    session.execute(delete(Quote).where(Quote.is_demo))

    quotes = []
    for i in range(DEMO_QUOTE_COUNT):
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        days_ago = rng.randint(0, 59)
        created_at = now - timedelta(days=days_ago, hours=rng.randint(0, 23), minutes=rng.randint(0, 59))
        final_status = _pick_status(rng, days_ago)

        quote = Quote(
            name=f"{first} {last}",
            email=f"{first}.{last}{i}@example.com".lower(),
            # 555-0100 a 555-0199: rango reservado para números ficticios en EE. UU.
            phone=f"({rng.choice(AREA_CODES)}) 555-01{rng.randint(0, 99):02d}",
            service=rng.choice(SERVICES),
            home_size=rng.choice(HOME_SIZES),
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
    args = parser.parse_args()

    if args.command == "seed-demo":
        # session.begin(): hace commit al terminar el bloque, o rollback si hubo un error.
        # Así el reinicio es atómico: nunca quedan los datos demo a medias.
        with SessionLocal() as session, session.begin():
            counts = seed_demo(session)
        print(
            f"Datos demo listos: {counts['quotes']} cotizaciones, "
            f"{counts['notes']} notas y {counts['status_changes']} cambios de estado."
        )


if __name__ == "__main__":
    main()
