import asyncio
import logging
import os
import random

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods.set_my_name import SetMyName

import app.config as config
import app.handlers as handlers
import app.db as db
import app.mfunc as mfunc
import app.tasks as tasks
from app.exceptions import ErrorMiddleware
    
bot = Bot(
    token=config.settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

logger = logging.getLogger(__name__)
log = config.setup_logging(logger)

def setup_aiogram_logging():
    #* Настраивает логирование aiogram для подавления ненужных сообщений
    aiogram_logger = logging.getLogger("aiogram")
    
    aiogram_logger.setLevel(logging.WARNING)
    
    class ConnectionErrorFilter(logging.Filter):
        def filter(self, record):
            message = record.getMessage()
            # Подавляем сообщения о разрыве соединения
            if "Server disconnected" in message:
                return False
            if "Failed to fetch updates" in message:
                return False
            if "Sleep for 1.000000 seconds" in message:
                return False
            # Подавляем ошибки о кике из группы
            if "bot was kicked from the supergroup chat" in message:
                return False
            if "TelegramForbiddenError" in message:
                return False
            return True
    
    connection_filter = ConnectionErrorFilter()
    
    for handler in aiogram_logger.handlers:
        handler.addFilter(connection_filter)
    
    if not aiogram_logger.handlers:
        handler = logging.StreamHandler()
        handler.addFilter(connection_filter)
        aiogram_logger.addHandler(handler)


async def main():
    setup_aiogram_logging()

    dp = Dispatcher()
    dp.message.middleware(ErrorMiddleware())
    dp.callback_query.middleware(ErrorMiddleware())
    dp.include_router(handlers.router)

    await db.init_db()

    tasks.scheduler.add_job(tasks.day_reset,
        "cron",
        hour=0,
        minute=0,
        coalesce=True,
        misfire_grace_time=3600
    )

    tasks.scheduler.add_job(tasks.remind_overtime,
        "cron",
        hour=19,
        minute=0,
        coalesce=True,
        misfire_grace_time=3600
    )
    
    tasks.scheduler.add_job(tasks.availability_check,
        "interval",
        minutes=30,
    )

    try:
        tasks.scheduler.start()

        await dp.start_polling(bot)
        if config.settings.BOT_USERNAME == "mysettlementbot":
            smile = random.choice(["🌀", "🫐", "🐬"])
            await bot.set_my_name(name=f"🛖 Моё Поселение! {smile}", language_code="ru")
        log.info("🟢 Бот запущен!")
    finally:
        for task in mfunc.work_timeout_tasks.values():
            task.cancel()
        mfunc.work_timeout_tasks.clear()
        tasks.scheduler.shutdown()
        if config.settings.BOT_USERNAME == "mysettlementbot":
            cry = random.choice(["㊙️", "🍒", "🏮"])
            await bot.set_my_name(name=f"🛖 Моё Поселение! {cry}", language_code="ru")
        await bot.session.close()
        log.info("🔴 Бот остановлен!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🔴 Скрипт остановлен")
    except Exception as e:
        log.critical(f"Критическая ошибка: {e}")