from __future__ import annotations

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings


_bot: Bot | None = None


def configure_bot(bot: Bot | None) -> None:
    global _bot
    _bot = bot


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
    return _bot


async def send_message(chat_id: int, text: str, **kwargs):
    return await get_bot().send_message(chat_id=chat_id, text=text, **kwargs)


async def get_chat_administrators(chat_id: int):
    return await get_bot().get_chat_administrators(chat_id)


async def set_my_name(name: str, language_code: str = "ru"):
    return await get_bot().set_my_name(name=name, language_code=language_code)
