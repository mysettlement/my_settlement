import logging
import time
import asyncio
import pytz
import re
import arrow
from pymorphy3 import MorphAnalyzer
from typing import Optional, NamedTuple
from wordfreq import zipf_frequency
from langdetect import detect, DetectorFactory
from rapidfuzz import process, fuzz, utils
from functools import lru_cache
from typing import Dict, Union, Callable
from datetime import datetime, timedelta
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot, types
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter
from aiogram.client.default import DefaultBotProperties

from app.config import setup_logging, settings
from app.gamer import Harvesting, Hitting, Timer, Catch, Alternation, Workflow
from app.middlewares import GroupOwnerError
import app.models as models



bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
GameType = Union[Harvesting, Hitting, Catch, Alternation, Timer, Workflow]
active_games: Dict[str, GameType] = {}
log = setup_logging(logging.getLogger(__name__))
morph = MorphAnalyzer()


#* Система ограничений
work_in_progress: Dict[int, bool] = {}  # Блокировка работы по чатам
last_work_end_time: Dict[int, float] = {}  # Время завершения последней работы по чатам
work_start_time: Dict[int, float] = {}  # Время начала работы по чатам
work_timeout_tasks: Dict[int, asyncio.Task] = {}  # Задачи таймаута работы по чатам
user_last_click_time: Dict[str, float] = {}  # Последнее нажатие кнопки для каждого пользователя


DetectorFactory.seed = 0

SUPPORTED_LANGS = {
    'ru', 'en', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'pl', 'uk', 'cs', 'tr', 'sv', 'no', 'da', 'fi',
    'hu', 'ro', 'hr', 'sr', 'sl', 'sk', 'bg', 'el', 'he', 'ar', 'fa', 'hi', 'bn', 'ta', 'te',
    'mr', 'ur', 'th', 'ko', 'ja', 'zh'
}

KNOWN_TYPOS: Dict[str, str] = {
    
}

class TextCommand(BaseFilter):
    def __init__(self, *aliases: str):
        self.aliases = [a.lower() for a in aliases]

    async def __call__(self, message: Message, user: models.User) -> bool:
        if not message.text or message.text.startswith("/"):
            return False

        bot_mention = f"@{settings.BOT_USERNAME}".lower()
        text = message.text.lower().replace(bot_mention, "").strip()

        if text in self.aliases:
            return True

        if not getattr(user, "allow_typos", False):
            return False

        processed_text = utils.default_process(text)

        from app.utils import KNOWN_TYPOS
        if processed_text in KNOWN_TYPOS and KNOWN_TYPOS[processed_text] in self.aliases:
            return True

        match = process.extractOne(
            processed_text,
            self.aliases,
            scorer=fuzz.QRatio
        )

        if match:
            command, score, _ = match
            len_ratio = len(processed_text) / len(command)
            
            if 0.7 <= len_ratio <= 1.3 and score >= settings.TYPOS_PERCENT:
                log.debug(f"{message.chat.id} | {message.from_user.id} | Схожесть с «{command}» {round(score, 2)}%/{settings.TYPOS_PERCENT}%: {message.text}")
                return True

        return False

async def is_meaningful(text: str, length: int = 3, words_amount: int = 1) -> bool:
    if not text:
        return False

    text = text.strip()
    if len(text) < length:
        return False

    lower_text = text.lower()
    if re.fullmatch(r"[\W\d_]+", lower_text):
        return False
    if re.fullmatch(r"(.)\1{3,}", lower_text):
        return False

    words = lower_text.split()
    if len(words) > words_amount and len(set(words)) == 1:
        return False

    try:
        detected_lang = detect(text)
        lang = detected_lang if detected_lang in SUPPORTED_LANGS else 'ru' 
    except:
        lang = 'ru'

    meaningful = 0
    total = 0
    for w in words:
        w_clean = re.sub(r"[^\w" + (r"а-яё" if lang == "ru" else r"") + r"]", "", w)
        if not w_clean:
            continue
        total += 1
        freq = zipf_frequency(w_clean, lang)
        if freq >= 1.5:
            meaningful += 1

    if total == 0:
        return False

    return (meaningful / total) >= 0.4


async def get_group_owner(chat_id: int) -> types.User:
    try:
        chat_admins = await bot.get_chat_administrators(chat_id)
        for admin in chat_admins:
            if admin.status == "creator":
                return admin.user
        raise GroupOwnerError(f"Не удалось найти владельца группы {chat_id}", chat_id=chat_id)
    except GroupOwnerError:
        raise
    except Exception as e:
        raise GroupOwnerError(f"Ошибка API Telegram при получении владельца группы {chat_id}: {str(e)}", chat_id=chat_id)

def get_daily_reset_countdown(timezone: str) -> str:
    now = arrow.now(timezone or "UTC")
    next_midnight = now.shift(days=1).floor('day')
    return format_relative_time(next_midnight, now=now, disable_affixes=True)


async def format_reward_text(earned: dict) -> str:
    if not earned:
        return "✖️ Пусто"
    
    text = "\n".join(f"{resource}: {quantity:+}" for resource, quantity in earned.items())
    
    return text

def format_bonuses_text(bonuses: dict) -> tuple[bool, str]:
    """
    Преобразует JSON бонусов в текст, сгруппированный по цели (Всего -> Категории -> Ресурсы)
    и отсортированный по типу (📦 -> 📦 -> 🍀).
    """
    if not bonuses:
        return False, "Нет бонусов"
    
    PRIORITY = {
        "modifier": 1,   # 📦
        "multiplier": 2, # 📦
        "chance": 3      # 🍀
    }
    
    ICONS = {
        1: "📦",
        2: "📦",
        3: "🍀"
    }

    def parse_key_type(key: str) -> int:
        if "quantity_modifier" in key: return PRIORITY["modifier"]
        if "quantity_multiplier" in key: return PRIORITY["multiplier"]
        if "chance_multiplier" in key: return PRIORITY["chance"]
        return 99

    grouped_data = {} 

    for key, val in bonuses.items():
        prio = parse_key_type(key)
        is_pct = "multiplier" in key or "chance" in key
        
        if isinstance(val, (int, float)):
            target = "__global__"
            if target not in grouped_data: grouped_data[target] = []
            grouped_data[target].append({
                "prio": prio,
                "val": val,
                "is_pct": is_pct
            })
        
        elif isinstance(val, dict):
            for target_name, target_val in val.items():
                if target_name not in grouped_data: grouped_data[target_name] = []
                grouped_data[target_name].append({
                    "prio": prio,
                    "val": target_val,
                    "is_pct": is_pct
                })

    sorted_targets = sorted(grouped_data.keys(), key=lambda x: (0 if x == "__global__" else 1, x))

    lines = []

    for target in sorted_targets:
        bonuses_list = sorted(grouped_data[target], key=lambda x: x["prio"])
        
        for item in bonuses_list:
            val = item["val"]
            icon = ICONS.get(item["prio"], "❓")
            
            if item["is_pct"]:
                val_str = f"{int(val * 100):+}%"
            else:
                val_str = f"{val:+}"

            if target == "__global__":
                lines.append(f"• <b>{val_str} всего</b> ({icon})")
            else:
                lines.append(f"• {target}: <b>{val_str}</b> ({icon})")

    if not lines:
        return False, "Нет явных бонусов"

    return True, "\n".join(lines)

def format_relative_time(target: Union[datetime, int, timedelta], now: Union[datetime, arrow.Arrow] = None, disable_affixes: bool = False) -> str:
    now = arrow.get(now) if now is not None else arrow.now()
    
    if isinstance(target, int):
        target = arrow.now().shift(seconds=target)
    
    elif isinstance(target, timedelta):
        target = arrow.get((now or arrow.now()) + target)

    result = arrow.get(target)
    return result.humanize(other=now, locale='ru', only_distance=disable_affixes)

def format_count(count: int, word: str) -> str:
    """
    Автоматически согласует слово с числом.
    Например: 2, 'куна' -> '2 куны'
              5, 'куна' -> '5 кун'
    """
    parsed_word = morph.parse(word)[0]
    
    agreed_word = parsed_word.make_agree_with_number(count).word
    
    return f"{count} {agreed_word}"


def can_click_button(user_key: str) -> bool:
    current_time = time.time()
    last_click = user_last_click_time.get(user_key, 0)
    
    if current_time - last_click < 1.3:
        return False
    
    user_last_click_time[user_key] = current_time
    return True

def can_choose_craft(last_profession_change) -> tuple[bool, str]:
    last = arrow.get(last_profession_change or 0)
    now = arrow.now()
    
    cooldown_end = last.shift(hours=settings.CRAFT_COOLDOWN_HOURS)
    
    if cooldown_end > now:
        return False, cooldown_end.humanize(other=now, locale='ru', only_distance=True)
        
    return True, ""

async def timeout_work(chat_id: int):
    try:
        await asyncio.sleep(settings.WORK_TIMEOUT_SECONDS)
        
        if work_in_progress.get(chat_id, False):
            end_work(chat_id)
            
            user_keys_to_remove = [key for key in active_games.keys() if key.startswith(f"{chat_id}_")]
            for user_key in user_keys_to_remove:
                active_games.pop(user_key, None)
            
            log.warning(f"{chat_id} | ⏰ Труд автоматически отменён по таймауту")
            
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.error(f"{chat_id} | Ошибка в таймауте труда: {e}")
    finally:
        work_timeout_tasks.pop(chat_id, None)

def get_work_remaining_time(chat_id: int) -> int:
    if chat_id not in work_start_time:
        return 0
    
    elapsed = time.time() - work_start_time[chat_id]
    remaining = 180 - elapsed  # 3 минуты = 180 секунд
    return max(0, int(remaining))

def can_start_work(chat_id: int) -> tuple[bool, str]:
    global work_in_progress, last_work_end_time
    
    if work_in_progress.get(chat_id, False):
        return False, "⏳ Уж кто-то в сей сходке трудится. Жди, покуда дело свершится!"
    
    current_time = time.time()
    last_end_time = last_work_end_time.get(chat_id, 0)
    if current_time - last_end_time < 10:
        remaining = 10 - (current_time - last_end_time)
        return False, f"⏳ Передышка меж трудом: {remaining:.0f}с.\nℹ️ Кулдаун накладывается из-за ограничений Telegram. Чтобы избежать непредвиденных ошибок, пожалуйста, подождите."
    
    return True, ""

def start_work(chat_id: int):
    global work_in_progress, work_start_time, work_timeout_tasks
    work_in_progress[chat_id] = True
    work_start_time[chat_id] = time.time()
    
    if chat_id in work_timeout_tasks:
        work_timeout_tasks[chat_id].cancel()
    
    work_timeout_tasks[chat_id] = asyncio.create_task(timeout_work(chat_id))

def end_work(chat_id: int):
    work_in_progress[chat_id] = False
    last_work_end_time[chat_id] = time.time()
    
    if chat_id in work_timeout_tasks:
        work_timeout_tasks[chat_id].cancel()
        del work_timeout_tasks[chat_id]
    
    work_start_time.pop(chat_id, None)

async def mark_work_completed(settler: models.Settler, session: AsyncSession, chat_id: int):
    current_time = arrow.now().int_timestamp
    await session.execute(
        update(models.Settler)
        .where(models.Settler.id == settler.id)
        .values(work_is_completed=True, last_work_time=current_time)
    )
        
    await session.commit()
    log.debug(f"{chat_id} | {settler.user_id} | 💼 Работа завершена")


async def notify_developers(message: str):
    if not settings.ENABLE_DEVELOPERS_NOTIFY:
        return
    
    for dev_id in settings.DEVELOPER_IDS:
        try:
            await bot.send_message(dev_id, message)
        except Exception as e:
            log.error(f"Ошибка при отправке сообщения разработчику {dev_id}: {e}")

def get_timezones_at_hour(target_hour: int) -> list[str]:
    target_timezones = []
    for tz_name in pytz.common_timezones:
        try:
            if arrow.now(tz_name).hour == target_hour:
                target_timezones.append(tz_name)
        except Exception:
            continue
    return target_timezones