from fluentogram import TranslatorHub, FluentTranslator
from fluent_compiler.bundle import FluentBundle

from typing import Any, Dict, Awaitable, Callable, Optional
import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from sqlalchemy import select

from app.db import SessionLocal
from app.models import User as DBUser
from app import config


log = config.setup_logging(logging.getLogger(__name__))

LANGUAGES_MAP = {
    "ru": "Русский", 
    "uk": "Українська 🇺🇦", 
    "en": "English 🇬🇧"
}

def create_translator_hub() -> TranslatorHub:
    translator_hub = TranslatorHub(
        locales_map={
            "ru": ("ru", "uk", "en"),
            "uk": ("uk", "ru", "en"),
            "en": ("en", "ru", "uk"),
        },
        translators=[
            FluentTranslator(
                locale="ru",
                translator=FluentBundle.from_files("ru-RU", filenames=["locales/ru/settings.ftl", "locales/ru/common.ftl", "locales/ru/craft.ftl"]),
            ),
            FluentTranslator(
                locale="uk",
                translator=FluentBundle.from_files("uk-UA", filenames=["locales/uk/settings.ftl", "locales/uk/common.ftl", "locales/uk/craft.ftl"]),
            ),
            FluentTranslator(
                locale="en",
                translator=FluentBundle.from_files("en-US", filenames=["locales/en/settings.ftl", "locales/en/common.ftl", "locales/en/craft.ftl"]),
            ),
        ],
        root_locale="ru",
    )
    return translator_hub


class I18nMiddleware(BaseMiddleware):
    def __init__(self, translator_hub: TranslatorHub):
        self.hub = translator_hub
        self.cache: Dict[int, str] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user: Optional[User] = data.get("event_from_user")
        
        if not user:
            data["i18n"] = self.hub.get_translator_by_locale("en")
            return await handler(event, data)

        lang_code = self.cache.get(user.id)

        if lang_code is None:
            async with SessionLocal() as session:
                result = await session.execute(
                    select(DBUser.language).where(DBUser.telegram_id == user.id)
                )
                db_lang = result.scalar_one_or_none()
                
                if db_lang:
                    lang_code = db_lang
                else:
                    lang_code = user.language_code if user.language_code in LANGUAGES_MAP else "en"
                
                self.cache[user.id] = lang_code

        if lang_code not in LANGUAGES_MAP:
            lang_code = "en"

        data["i18n"] = self.hub.get_translator_by_locale(lang_code)
        data["i18n_middleware"] = self
        
        return await handler(event, data)