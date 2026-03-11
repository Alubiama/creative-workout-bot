"""Creative Workout Bot entry point."""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_BOT_TOKEN
from database.db import get_db, close_db
from handlers import start, incubation, stats
import report_v2
import session_v2
import ui_patch

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
BUILD_ID = "reset-fix-2026-03-10-01"

start.main_menu_keyboard = ui_patch.main_menu_keyboard
session_v2.difficulty_keyboard = ui_patch.difficulty_keyboard


async def main() -> None:
    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(start.router)
    dp.include_router(session_v2.router)
    dp.include_router(incubation.router)
    dp.include_router(stats.router)
    dp.include_router(report_v2.router)

    # Init DB
    await get_db()
    logger.info("Database initialised.")

    logger.info("Starting bot polling... build=%s", BUILD_ID)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await close_db()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

