import asyncio
import logging
import random
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties

from app.core import user_getOrCreate
import app.config as config
import app.handlers as handlers
import app.db as db
import app.utils as utils
import app.tasks as tasks
import app.telegram_gateway as telegram_gateway
from app.middlewares import ErrorMiddleware, UserMiddleware
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
        await telegram_gateway.set_my_name(
            name=f"🛖 Моё Поселение! {selected_emoji}", 
            language_code="ru"
        )

async def setup_runtime(dispatcher: Dispatcher, bot: Bot, initialize_db: bool = True):
    setup_aiogram_logging()
    telegram_gateway.configure_bot(bot)
    if initialize_db:
        await db.init_db()

    if not getattr(dispatcher, "_my_settlement_runtime_configured", False):
        dispatcher.message.middleware(ErrorMiddleware())
        dispatcher.callback_query.middleware(ErrorMiddleware())
        dispatcher.update.middleware(I18nMiddleware(create_translator_hub()))
        dispatcher.update.outer_middleware(UserMiddleware(user_getOrCreate=user_getOrCreate))
        dispatcher.include_router(handlers.router)
        dispatcher._my_settlement_runtime_configured = True

    tasks.scheduler.add_job(
        tasks.day_reset,
        "cron",
        id="day_reset",
        hour="*",
        minute=0,
        coalesce=True,
        misfire_grace_time=3600,
        replace_existing=True,
    )
    tasks.scheduler.add_job(
        tasks.remind_overtime,
        "cron",
        id="remind_overtime",
        hour="*",
        minute=0,
        coalesce=True,
        misfire_grace_time=3600,
        replace_existing=True,
    )
    if not tasks.scheduler.running:
        try:
            tasks.scheduler.start()
        except Exception as e:
            log.error(f"Ошибка запуска планировщика: {e}")

    await set_bot_status(bot, "happy")
    log.info("🟢 Бот запущен!")


async def shutdown_runtime(bot: Bot, close_bot_session: bool = True):
    log.info("🟡 Завершение работы...")

    if tasks.scheduler.running:
        tasks.scheduler.shutdown(wait=False)

    utils.reset_runtime_state()

    await set_bot_status(bot, "sad")
    if close_bot_session:
        await bot.session.close()
    log.info("🔴 Бот остановлен!")


# === Жизненный цикл ===
async def main():
    await setup_runtime(dp, bot)

    try:
        await dp.start_polling(bot)
    finally:
        await shutdown_runtime(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as e:
        log.critical(e, exc_info=True)
