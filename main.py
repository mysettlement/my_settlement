import asyncio
import logging
import random
from contextlib import suppress, asynccontextmanager
import uvicorn # Нужно добавить uvicorn в requirements.txt

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from app.admin import setup_panel

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties

import app.config as config
import app.handlers as handlers
import app.db as db
import app.utils as utils
import app.tasks as tasks
from app.exceptions import ErrorMiddleware
from app.i18n import create_translator_hub, I18nMiddleware

log = config.setup_logging(logging.getLogger(__name__))

bot = Bot(
    token=config.settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher()

# === Логика фильтрации логов ===
class ConnectionErrorFilter(logging.Filter):
    def filter(self, record):
        message = record.getMessage()
        ignored_phrases = [
            "Server disconnected",
            "Failed to fetch updates",
            "Sleep for",
            "bot was kicked from the supergroup chat",
            "TelegramForbiddenError"
        ]
        return not any(phrase in message for phrase in ignored_phrases)

def setup_aiogram_logging():
    aiogram_logger = logging.getLogger("aiogram")
    aiogram_logger.setLevel(logging.WARNING)
    connection_filter = ConnectionErrorFilter()
    for handler in aiogram_logger.handlers:
        handler.addFilter(connection_filter)

async def set_bot_status(bot: Bot, mood: str):
    if config.settings.BOT_USERNAME != "mysettlementbot":
        return
    emojis = {
        "happy": ["🌀", "🫐", "🐬"],
        "sad": ["㊙️", "🍒", "🏮"]
    }
    selected_emoji = random.choice(emojis.get(mood, ["🤖"]))
    with suppress(TelegramBadRequest, Exception):
        await bot.set_my_name(
            name=f"🛖 Моё Поселение! {selected_emoji}", 
            language_code="ru"
        )

# === Жизненный цикл ===
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- STARTUP ---
    setup_aiogram_logging()
    await db.init_db()

    dp.message.middleware(ErrorMiddleware())
    dp.callback_query.middleware(ErrorMiddleware())
    dp.message.middleware(I18nMiddleware(create_translator_hub()))
    dp.callback_query.middleware(I18nMiddleware(create_translator_hub()))
    dp.include_router(handlers.router)

    tasks.scheduler.add_job(tasks.day_reset, 'cron', hour='*', minute=0, coalesce=True, misfire_grace_time=3600)
    tasks.scheduler.add_job(tasks.remind_overtime, "cron", hour="*", minute=0, coalesce=True, misfire_grace_time=3600)
    try:
        tasks.scheduler.start()
    except Exception as e:
        log.error(f"Ошибка запуска планировщика: {e}")

    await set_bot_status(bot, "happy")
    
    polling_task = asyncio.create_task(
        dp.start_polling(bot, handle_signals=False) 
    )
    
    log.info("🟢 Бот запущен!")
    
    yield
    
    # --- SHUTDOWN ---
    log.info("🟡 Завершение работы...")
    
    polling_task.cancel()
    try:
        await polling_task
    except asyncio.CancelledError:
        pass

    if tasks.scheduler.running:
        tasks.scheduler.shutdown(wait=False)

    for task in utils.work_timeout_tasks.values():
        task.cancel()
    utils.work_timeout_tasks.clear()

    await set_bot_status(bot, "sad")
    await bot.session.close()
    log.info("🔴 Бот остановлен!")

app = FastAPI(lifespan=lifespan)
@app.get("/")
async def root():
    return RedirectResponse(url="/admin")
setup_panel(app)

if __name__ == "__main__":
    try:
        uvicorn.run(app, host="0.0.0.0", port=3480)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.critical(e, exc_info=True)