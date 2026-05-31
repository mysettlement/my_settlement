from fluentogram import TranslatorHub, FluentTranslator
from pathlib import Path
from fluent_compiler.bundle import FluentBundle

from typing import Any, Dict, Awaitable, Callable, Optional
from functools import lru_cache
import logging

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from sqlalchemy import select

import app.db as app_db
from app.models import User as DBUser
from app import config


log = config.setup_logging(logging.getLogger(__name__))

LANGUAGES_MAP = {
    "ru": "Русский", 
    "uk": "Українська 🇺🇦", 
    "en": "English 🇬🇧"
}

@lru_cache(maxsize=None)
def _create_translator_hub_cached(base_dir: str) -> TranslatorHub:
    locale_config = {
        "ru": "ru-RU",
        "uk": "uk-UA",
        "en": "en-US",
    }
    
    translators = []
    base_path = Path(base_dir)

    for lang_code, full_locale in locale_config.items():
        lang_dir = base_path / lang_code
        filenames = [str(path) for path in lang_dir.glob("*.ftl")]
        
        translators.append(
            FluentTranslator(
                locale=lang_code,
                translator=FluentBundle.from_files(full_locale, filenames=filenames),
            )
        )

    return TranslatorHub(
        locales_map={
            "ru": ("ru", "uk", "en"),
            "uk": ("uk", "ru", "en"),
            "en": ("en", "ru", "uk"),
        },
        translators=translators,
        root_locale="ru",
    )


def create_translator_hub(locales_path: Path | None = None) -> TranslatorHub:
    base_dir = locales_path or (Path(__file__).resolve().parent.parent / "locales")
    return _create_translator_hub_cached(str(base_dir.resolve()))


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
            async with app_db.SessionLocal() as session:
                result = await session.execute(
                    select(DBUser.language).where(DBUser.telegram_id == user.id)
                )
                db_lang = result.scalar_one_or_none()
                
                if db_lang:
                    lang_code = db_lang
                else:
                    lang_code = user.language_code
                
                self.cache[user.id] = lang_code

        if lang_code not in LANGUAGES_MAP:
            lang_code = "en"

        data["i18n"] = self.hub.get_translator_by_locale(lang_code)
        data["i18n_middleware"] = self
        
        return await handler(event, data)
