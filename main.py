import asyncio
import logging
import os
import random

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.methods.set_my_name import SetMyName

import config
import handlers
import db
import tasks
from exceptions import ErrorMiddleware
    
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

    tasks.scheduler.add_job(tasks.day_reset, "cron", hour=0, minute=0)

    try:
        tasks.scheduler.start()

        #! Flood control
        # smile = random.choice(["🔷", "🔵", "🌀", "🫐", "🐬"])
        # await bot(SetMyName(name=f"🛖 Моё Поселение! {smile}", language_code="ru"))
        # await bot(SetMyName(name=f"🛖 My Settlement! {smile}", language_code="en"))
        log.info("🟢 Бот запущен!")
        await dp.start_polling(bot)
    finally:
        # cry = random.choice(["🔺", "🔴", "㊙️", "🍒", "🏮"])
        # await bot(SetMyName(name=f"🛖 Моё Поселение! {cry}", language_code="ru"))
        # await bot(SetMyName(name=f"🛖 My Settlement! {cry}", language_code="en"))
        for task in handlers.work_timeout_tasks.values():
            task.cancel()
        handlers.work_timeout_tasks.clear()
        await bot.session.close()
        tasks.scheduler.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🔴 Бот остановлен пользователем")
    except Exception as e:
        log.critical(f"Критическая ошибка: {e}")