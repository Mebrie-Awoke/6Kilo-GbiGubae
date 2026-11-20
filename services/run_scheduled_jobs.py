"""CLI entry point used by the external GitHub Actions scheduler."""
import asyncio
import logging

from services.durable_broadcasts import run_scheduled_broadcasts
from loader import bot
from db.session import engine


async def main() -> None:
    try:
        runs, deliveries = await run_scheduled_broadcasts(bot)
        logging.info(
            "Scheduled worker finished: %s new run(s), %s delivery attempt(s).",
            runs,
            deliveries,
        )
    finally:
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
