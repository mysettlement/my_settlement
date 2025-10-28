import logging
import time
import asyncio
import pytz
import re
from wordfreq import zipf_frequency
from typing import Dict, Union
from datetime import datetime, timedelta
from aiogram import types

from config import setup_logging
from gamer import Harvesting, Hitting, Workflow
from exceptions import GroupOwnerError
from main import bot
import models



GameType = Union[Harvesting, Hitting, Workflow]
active_games: Dict[str, GameType] = {}
log = setup_logging(logging.getLogger(__name__))

# Система ограничений
work_in_progress: Dict[int, bool] = {}  # Блокировка работы по чатам
last_work_end_time: Dict[int, float] = {}  # Время завершения последней работы по чатам
work_start_time: Dict[int, float] = {}  # Время начала работы по чатам
work_timeout_tasks: Dict[int, asyncio.Task] = {}  # Задачи таймаута работы по чатам
user_last_click_time: Dict[str, float] = {}  # Последнее нажатие кнопки для каждого пользователя



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

async def is_meaningful(text: str, length: int = 3, words_amount: int = 1, lang: str = "ru") -> bool:
    if not text:
        return False

    text = text.strip().lower()

    if len(text) < length: # слишком короткие (меньше 3 символов)
        return False
    if re.fullmatch(r"[\W\d_]+", text): # только смайлы/спецсимволы/цифры
        return False
    if re.fullmatch(r"(.)\1{3,}", text): # повтор одинаковых букв (ааааа, лоллллл, хахахах)
        return False
    words = text.split()
    if len(set(words)) == 1 and len(words) > words_amount: # повтор слов (привет привет привет)
        return False
    
    # --- Проверка частоты слов ---
    meaningful = 0
    total = 0
    for w in words:
        w = re.sub(r"[^\wа-яё]", "", w)
        if not w:
            continue
        total += 1
        freq = zipf_frequency(w, lang)
        if freq >= 1.5:  # нормальное слово
            meaningful += 1

    if total == 0:
        return False

    ratio = meaningful / total
    if ratio < 0.4:  # меньше 40% нормальных слов
        return False

    return True

def format_reward_text(earned: dict, exp_gained: int = 0) -> str:
    if not earned and exp_gained == 0:
        return ""
    
    reward_parts = []
    if earned:
        earned_text = " | ".join(f"{resource.emoji}: +{quantity}" for resource, quantity in earned.items())
        reward_parts.append(earned_text)
    
    if exp_gained > 0:
        reward_parts.append(f"🗂: +{exp_gained}")
    
    return f"\n\n📦 <b>Получено:</b>\n" + "\n".join(reward_parts)

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

def can_click_button(user_key: str) -> bool:
    current_time = time.time()
    last_click = user_last_click_time.get(user_key, 0)
    
    if current_time - last_click < 1.3:
        return False
    
    user_last_click_time[user_key] = current_time
    return True

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

async def timeout_work(chat_id: int):
    try:
        await asyncio.sleep(180)  # 3 минуты = 180 секунд
        
        if work_in_progress.get(chat_id, False):
            end_work(chat_id)
            
            user_keys_to_remove = [key for key in active_games.keys() if key.startswith(f"{chat_id}_")]
            for user_key in user_keys_to_remove:
                active_games.pop(user_key, None)
            
            log.warning(f"{chat_id} | ⏰ Труд автоматически отменён по таймауту (3 минуты)")
            
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

def can_choose_craft(last_profession_change) -> tuple[bool, str]:
    now_ts = int(datetime.now().timestamp())
    last_ts = last_profession_change or 0
    cooldown = int(timedelta(days=3).total_seconds())
    if last_ts and now_ts - last_ts < cooldown:
        remaining = cooldown - (now_ts - last_ts)
        days = remaining // 86400
        hours = (remaining % 86400) // 3600
        minutes = (remaining % 3600) // 60
        when = f"{days}д. {hours}ч. {minutes}м." if days > 0 else (f"{hours}ч. {minutes}м." if hours > 0 else f"{minutes}м.")
        return False, when
    return True, ""
