import logging
import time
import asyncio
import pytz
import re
from typing import Optional, NamedTuple
from wordfreq import zipf_frequency
from langdetect import detect, DetectorFactory
from rapidfuzz import process, fuzz
from functools import lru_cache
from typing import Dict, Union, Callable
from datetime import datetime, timedelta
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import Bot, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import setup_logging, settings
from app.gamer import Harvesting, Hitting, Timer, Catch, Alternation, Workflow
from app.exceptions import GroupOwnerError
import app.models as models



bot = Bot(
    token=settings.BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
GameType = Union[Harvesting, Hitting, Catch, Alternation, Timer, Workflow]
active_games: Dict[str, GameType] = {}
log = setup_logging(logging.getLogger(__name__))


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


class FuzzyMatch(NamedTuple):
    matched: bool
    command: Optional[str]
    score: int

def fuzzy(*aliases: str):
    def wrapper(func: Callable):
        func.__fuzzy_aliases__ = tuple(a.lower() for a in aliases)
        return func
    return wrapper

async def is_text_command(message, user, commands: dict[str, Callable], *, threshold: int = 90.1) -> FuzzyMatch:
    if not message.text or message.text.startswith("/"):
        return FuzzyMatch(False, None, 0)

    if not getattr(user, "allow_typos", False):
        return FuzzyMatch(False, None, 0)

    text = message.text.lower().strip()

    match = process.extractOne(
        text,
        commands.keys(),
        scorer=fuzz.WRatio
    )

    if not match:
        return FuzzyMatch(False, None, 0)

    command_text, score, _ = match

    if score < threshold:
        return FuzzyMatch(False, command_text, score)

    return FuzzyMatch(True, command_text, score)
    

async def get_group_owner(chat_id: int) -> types.User:
    try:
        chat_admins = await bot.get_chat_administrators(chat_id)
        for admin in chat_admins:
            if admin.status == "creator":
                return admin.user
        if chat_admins:
            return chat_admins[0].user
        raise GroupOwnerError(f"Не удалось найти владельца группы {chat_id}", chat_id=chat_id)
    except GroupOwnerError:
        raise
    except Exception as e:
        raise GroupOwnerError(f"Ошибка API Telegram при получении владельца группы {chat_id}: {str(e)}", chat_id=chat_id)

def get_daily_reset_countdown() -> str:
    now = datetime.now(pytz.timezone('Europe/Kiev'))
    
    next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    time_diff = next_midnight - now
    
    hours = int(time_diff.total_seconds() // 3600)
    minutes = int((time_diff.total_seconds() % 3600) // 60)
    
    return f"{hours}ч. {minutes}м." if hours > 0 else f"{minutes}м."

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

def format_reward_text(earned: dict, exp_gained: int = 0) -> str:
    if not earned and exp_gained == 0:
        return ""
    
    parts = []
    if earned:
        earned_text = " | ".join(f"{resource.emoji}: +{quantity}" for resource, quantity in earned.items())
        parts.append(earned_text)
    
    if exp_gained > 0:
        parts.append(f"🗂: +{exp_gained}")
    
    return f"📦 <b>Получено:</b>\n" + "\n".join(parts)

async def format_relative_time(target: datetime, now: Optional[datetime] = None) -> str:
    """
    Возвращает читаемую строку вида:
    - только что
    - 5 минут назад
    - 1 час назад
    - 3 дня назад
    - 2 года назад
    - через 10 минут
    - через 1 день
    - через 5 лет
    """
    if now is None:
        now = datetime.now(target.tzinfo)

    delta = target - now
    is_future = delta.total_seconds() > 0
    total_seconds = abs(int(delta.total_seconds()))

    if total_seconds == 0:
        return "сейчас"

    years = total_seconds // (365 * 24 * 3600)
    remaining = total_seconds % (365 * 24 * 3600)
    days = remaining // (24 * 3600)
    remaining = remaining % (24 * 3600)
    hours = remaining // 3600
    remaining = remaining % 3600
    minutes = remaining // 60

    parts = []

    # Годы
    if years > 0:
        if years == 1:
            parts.append("1 год")
        elif 2 <= years <= 4:
            parts.append(f"{years} года")
        else:
            parts.append(f"{years} лет")

    # Дни
    if days > 0:
        if days == 1:
            parts.append("1 день")
        elif 2 <= days <= 4:
            parts.append(f"{days} дня")
        else:
            parts.append(f"{days} дней")

    # Часы
    if hours > 0:
        if hours == 1:
            parts.append("1 час")
        elif 2 <= hours <= 4:
            parts.append(f"{hours} часа")
        else:
            parts.append(f"{hours} часов")

    # Минуты
    if minutes > 0 and (total_seconds < 365 * 24 * 3600 or years == 0):
        if minutes == 1:
            parts.append("1 минуту")
        elif 2 <= minutes <= 4:
            parts.append(f"{minutes} минуты")
        elif minutes % 10 in (2, 3, 4) and minutes not in (12, 13, 14):
            parts.append(f"{minutes} минуты")
        else:
            parts.append(f"{minutes} минут")

    # Менее минуты
    if not parts:
        result = "через несколько секунд" if is_future else "только что"
    else:
        text = ", ".join(parts)
        result = ("через " + text) if is_future else (text + " назад")

    return result

def can_click_button(user_key: str) -> bool:
    current_time = time.time()
    last_click = user_last_click_time.get(user_key, 0)
    
    if current_time - last_click < 1.3:
        return False
    
    user_last_click_time[user_key] = current_time
    return True

def can_choose_craft(last_profession_change) -> tuple[bool, str]:
    now_ts = int(datetime.now().timestamp())
    last_ts = int(last_profession_change.timestamp()) or 0
    cooldown = int(timedelta(hours=settings.CRAFT_COOLDOWN_HOURS).total_seconds())
    if last_ts and now_ts - last_ts < cooldown:
        remaining = cooldown - (now_ts - last_ts)
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        minutes = (remaining % 3600) // 60
        when = f"{days}д. {hours}ч. {minutes}м." if days > 0 else (f"{hours}ч. {minutes}м." if hours > 0 else f"{minutes}м.")
        return False, when
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
    current_time = int(datetime.now().timestamp())
    await session.execute(
        update(models.Settler)
        .where(models.Settler.id == settler.id)
        .values(work_is_completed=True, last_work_time=current_time)
    )
        
    await session.commit()
    log.debug(f"{chat_id} | {settler.user_id} | 💼 Работа завершена")

