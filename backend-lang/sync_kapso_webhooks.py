"""Script standalone: pone al día los eventos del webhook de cada número ya conectado en Kapso.

Uso:
    uv run python sync_kapso_webhooks.py

Los webhooks se crean al conectar el número. Si después se agrega un evento a
NUMBER_WEBHOOK_EVENTS (kapso_onboarding.py), los números ya conectados no lo reciben hasta
correr este script. Es idempotente: se puede correr varias veces.
"""
import asyncio
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "src"))

from sqlalchemy import text

from core.config import get_settings
from core.database import AsyncSessionLocal
from services.kapso_onboarding import NUMBER_WEBHOOK_EVENTS, KapsoError, KapsoPlatformClient


async def main() -> None:
    s = get_settings()
    client = KapsoPlatformClient(s.kapso_api_key, s.kapso_base_url)
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT phone_number_id, kapso_webhook_id FROM channels WHERE kapso_webhook_id IS NOT NULL"
        ))).mappings().fetchall()
    print(f"Números con webhook: {len(rows)}")
    for row in rows:
        try:
            await client.update_phone_number_webhook(
                row["phone_number_id"], row["kapso_webhook_id"], events=NUMBER_WEBHOOK_EVENTS)
            print(f"  ok     {row['phone_number_id']}")
        except KapsoError as e:
            print(f"  error  {row['phone_number_id']}  ({e})")


if __name__ == "__main__":
    asyncio.run(main())
