from sqlalchemy import text, insert, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from aiogram import types
from datetime import datetime, timedelta
import logging
import random

from exceptions import GroupOwnerError, UserCreationError, SettlementCreationError, SettlerCreationError
from config import setup_logging, settings
from db import SessionLocal
from main import bot
import models
import mfunc


session = SessionLocal()
log = setup_logging(logging.getLogger(__name__))




async def user_getOrCreate(telegram_user: types.User):
    #* Получение или создание пользователя
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                select(models.User).where(models.User.telegram_id == telegram_user.id)
            )
            db_user = result.scalars().first()
            if db_user:
                # Обновление имени пользователя, если оно изменилось
                telegram_name = getattr(telegram_user, 'full_name', None) or f"User {telegram_user.id}"
                if not db_user.name or db_user.name != telegram_name:
                    db_user.name = telegram_name
                    await session.commit()
                await session.commit()
                return db_user
            else:
                user = models.User(
                    telegram_id=telegram_user.id,
                    name=getattr(telegram_user, 'full_name', None) or f"User {telegram_user.id}"
                )
                session.add(user)
                await session.commit()
                await session.refresh(user)
                log.debug(f"✅ Создан пользователь: {user.telegram_id}")
                return user
    except Exception as e:
        raise UserCreationError(f"Ошибка при создании/получении пользователя {telegram_user.id}: {str(e)}", telegram_user_id=telegram_user.id)

async def settlement_getOrCreate(chat: types.Chat, user: models.User):
    #* Получение или создание поселения
    try:
        async with SessionLocal() as session:
            if chat.type == "private":
                log.debug(f"{chat.id} | Поселение не может быть создано в private чате")
                return None
            
            result = await session.execute(
                select(models.Settlement)
                .options(
                    selectinload(models.Settlement.members),
                    selectinload(models.Settlement.owner)
                )
                .where(models.Settlement.chat_id == chat.id)
            )

            db_settlement = result.scalars().first()

            if db_settlement:
                await session.commit()
                return db_settlement
            else:
                # Получение владельца группы
                group_owner = await mfunc.get_group_owner(chat.id)
                if not group_owner:
                    raise SettlementCreationError(f"Не удалось получить владельца группы {chat.id}", chat_id=chat.id)
                
                owner_user = await user_getOrCreate(group_owner)
                if not owner_user:
                    raise SettlementCreationError(f"Не удалось создать пользователя-владельца группы {chat.id}", chat_id=chat.id)
                
                try:
                    settlement = models.Settlement(
                        chat_id=chat.id,
                        name=chat.title or f"Поселение {chat.id}",
                        owner_id=owner_user.id
                    )
                    session.add(settlement)
                    await session.commit()
                    await session.refresh(settlement, ['members', 'owner'])
                    log.debug(f"{settlement.chat_id} | ✅ Создано поселение: {settlement.name}")
                    return settlement
                except Exception as e:
                    log.warning(f"Ошибка при создании поселения: {e}")
                    await session.rollback()
                    
                    # Повторный поиск поселения
                    result = await session.execute(
                        select(models.Settlement)
                        .options(
                            selectinload(models.Settlement.members),
                            selectinload(models.Settlement.owner)
                        )
                        .where(models.Settlement.chat_id == chat.id)
                    )
                    db_settlement = result.scalars().first()
                    if db_settlement:
                        log.debug(f"{db_settlement.chat_id} | ✅ Найдено существующее поселение: {db_settlement.name}")
                        return db_settlement
                    else:
                        raise SettlementCreationError(f"Не удалось найти или создать поселение для чата {chat.id}", chat_id=chat.id)
    except (GroupOwnerError, UserCreationError, SettlementCreationError):
        raise
    except Exception as e:
        raise SettlementCreationError(f"Неожиданная ошибка при создании/получении поселения {chat.id}: {str(e)}", chat_id=chat.id)

async def settler_getOrCreate(user: models.User, settlement: models.Settlement):
    #* Получение или создание поселенца
    try:
        async with SessionLocal() as session:
            result = await session.execute(
                select(models.Settler)
                .options(selectinload(models.Settler.profession))
                .where(models.Settler.user_id == user.id, models.Settler.settlement_id == settlement.id)
            )
            db_settler = result.scalars().first()
            if db_settler:
                await session.commit()
                return db_settler
            else:
                settler = models.Settler(
                    user_id=user.id,
                    settlement_id=settlement.id
                )
                session.add(settler)
                settler.rank_emoji_available = ["🧑‍🌾", "👨‍🌾", "👩‍🌾"]
                await session.commit()
                await session.refresh(settler, ['user', 'settlement', 'profession'])
                
                log.debug(f"{settlement.chat_id} | ✅ Создан поселец: {settler.id}")
                return settler
    except Exception as e:
        raise SettlerCreationError(f"Ошибка при создании/получении поселенца {user.id} в поселении {settlement.id}: {str(e)}", user_id=user.id)

async def settler_addExp(settler: models.Settler, settlement: models.Settlement, session: AsyncSession, exp: int):
    result = await session.execute(
        select(models.Settler).where(models.Settler.id == settler.id)
    )
    current_settler = result.scalars().first()
    if not current_settler:
        return None
            
    current_settler.exp += exp
    log.debug(f"{settlement.chat_id} | {current_settler.user_id} | 🗂 Опыт увеличен: +{exp} ({current_settler.exp}/{current_settler.target_exp})")

    text = None
    while current_settler.exp >= current_settler.target_exp:
        old_rank = current_settler.rank
        old_emoji = current_settler.rank_emoji_available[0] if current_settler.rank_emoji_available else "❓"
        current_settler.level += 1
        current_settler.exp -= current_settler.target_exp

        # перерасчёт опыта и ранга
        if current_settler.level <= 16:
            current_settler.target_exp = 2 * current_settler.level + 7
            current_settler.rank = "Крестьянин"
        elif current_settler.level <= 31:
            current_settler.target_exp = 5 * current_settler.level - 38
            current_settler.rank = "Вольный"
        elif current_settler.level <= 46:
            current_settler.target_exp = 9 * current_settler.level - 158
            current_settler.rank = "Старейшина"
        elif current_settler.level <= 61:
            current_settler.rank = "Дворянин"
        else:
            current_settler.rank = "Лорд"

        user_result = await session.execute(
            select(models.User).where(models.User.id == current_settler.user_id)
        )
        user = user_result.scalars().first()
        user_name = user.name if user else f"User {current_settler.user_id}"
        
        text = f"🎉 <b>{user_name}</b> повысил уровень до <b>{current_settler.level}</b>!\n"
        log.debug(f"{settlement.chat_id} | {current_settler.user_id} | ⬆️ Новый уровень: {current_settler.level}")

        if old_rank != current_settler.rank:
            rank_emojis = {
                "Крестьянин": ["🧑‍🌾", "👨‍🌾", "👩‍🌾"],
                "Вольный": ["🌾", "🌱", "🍃"],
                "Старейшина": ["🕍", "⛩", "🏺"],
                "Дворянин": ["🏰", "🏯", "🏛"],
                "Лорд": ["👑", "🏰", "⚔️", "🛡"]
            }
            new_rank_emojis = rank_emojis.get(current_settler.rank, [])
            current_settler.rank_emoji_available = new_rank_emojis
            flag_modified(current_settler, 'rank_emoji_available')

            text += f"<b>⬆️ Новый ранг:</b> {old_emoji} {old_rank} → {new_rank_emojis[0] if new_rank_emojis else '❓'} <b>{current_settler.rank}</b>!"
            log.debug(f"{settlement.chat_id} | {current_settler.user_id} | 🔼 Новый ранг: {current_settler.rank}")

    await session.flush()
    await session.refresh(current_settler, ["user", "settlement"])

    if text:
        await bot.send_message(settlement.chat_id, text)

    return current_settler

async def settler_addMoney(settler: models.Settler, settlement: models.Settlement, session: AsyncSession, money: int):
    result = await session.execute(
        select(models.Settler).where(models.Settler.id == settler.id)
    )
    current_settler = result.scalars().first()
    if not current_settler:
        return None

    current_settler.balance += money
    await session.flush()
    await session.refresh(current_settler, ["user", "settlement"])
    log.debug(f"{settlement.chat_id} | {current_settler.user_id} | 💰 Деньги получены: +{money} ({current_settler.balance})")
    return current_settler

async def update_quote(settler: models.Settler, settlement: models.Settlement, session: AsyncSession, add_quote: int = 0):
    result = await session.execute(
        select(models.Settler).where(models.Settler.id == settler.id)
    )
    current_settler = result.scalars().first()
    if not current_settler:
        return None

    if settler.overtime_is_toggled:
        current_settler.target_quote = round((current_settler.level * 0.85 + 6) + (2 * settler.overtime_count))
    else:
        current_settler.target_quote = round(current_settler.level * 0.85 + 6)

    if not current_settler.quote_is_completed:
        current_settler.quote += add_quote
        if current_settler.quote >= current_settler.target_quote:
            current_settler.quote_is_completed = True
            user_result = await session.execute(
                select(models.User).where(models.User.id == current_settler.user_id)
            )
            user = user_result.scalars().first()
            

            if current_settler.level <= 16:
                rexp = random.randint(1, 3)
                earned_xp = current_settler.level * 0.50 + rexp
                rmoney = random.randint(2, 4)
            elif current_settler.level <= 31:
                rexp = random.randint(2, 5)
                earned_xp = current_settler.level * 0.40 + rexp
                rmoney = random.randint(3, 7)
            else:
                rexp = random.randint(4, 9)
                earned_xp = current_settler.level * 0.20 + rexp
                rmoney = random.randint(5, 13)
                
            earned_money = current_settler.level + rmoney

            await settler_addMoney(current_settler, settlement, session, earned_money)
            if current_settler.overtime_is_toggled:
                earned_xp *= 0.2
            updated_settler = await settler_addExp(current_settler, settlement, session, earned_xp)
            
            if updated_settler:
                # При повышении уровня сбрасываем квоту и пересчитываем целевую квоту
                current_settler.quote = 0
                if current_settler.overtime_is_toggled:
                    current_settler.target_quote = round((updated_settler.level * 0.85 + 6) + (2 * current_settler.overtime_count))
                else:
                    current_settler.target_quote = round(updated_settler.level * 0.85 + 6)
            
            text = (
                f"🎉 <b>{user.name if user else f'User {current_settler.user_id}'}</b> исполнил меру <b>{current_settler.target_quote}/{current_settler.target_quote}</b>!"
                f"\n🗂: +{round(earned_xp)} | 💰: +{round(earned_money)}" if earned_xp > 0 else f"\n💰: +{round(earned_money)}"
                f"\nℹ️ Чтоб в мудрости возрасти, доведётся каталог 🗂 до конца довести; каталог 🗂 опыт заменяет" if updated_settler.level <= 2 and user.show_hints else ""
            )
            
            await bot.send_message(settlement.chat_id, text)
            log.debug(f"{settlement.chat_id} | {current_settler.user_id} | ✅ Мера исполнена: {current_settler.quote}/{current_settler.target_quote}")

    log.debug(f"{settlement.chat_id} | {current_settler.user_id} | 🔄 Мера обновлена: {current_settler.quote}/{current_settler.target_quote}")
    await session.commit()
    await session.refresh(current_settler, ["user", "settlement"])

async def get_resource_by_emoji(emoji: str, session: AsyncSession) -> models.Resource:
    #* Получение ресурса по эмодзи
    result = await session.execute(
        select(models.Resource).where(models.Resource.emoji == emoji)
    )
    resource = result.scalars().first()
    if not resource:
        raise ValueError(f"Ресурс с эмодзи '{emoji}' не найден")
    return resource

async def settler_addResource(settler: models.Settler, settlement: models.Settlement, session: AsyncSession, emoji: str, quantity: int = None):
    #* Добавление ресурса поселенцу
    resource = await get_resource_by_emoji(emoji, session)
    
    if quantity is None:
        min_qty, max_qty = models.RARITY_QUANTITY_RANGES.get(resource.rarity, (1, 1))
        quantity = random.randint(min_qty, max_qty)
    
    existing_result = await session.execute(
        select(models.settler_resources).where(
            models.settler_resources.c.settler_id == settler.id,
            models.settler_resources.c.resource_id == resource.id
        )
    )
    existing = existing_result.first()
    
    if existing:
        await session.execute(
            update(models.settler_resources).where(
                models.settler_resources.c.settler_id == settler.id,
                models.settler_resources.c.resource_id == resource.id
            ).values(quantity=models.settler_resources.c.quantity + quantity)
        )
    else:
        await session.execute(
            insert(models.settler_resources).values(
                settler_id=settler.id,
                resource_id=resource.id,
                quantity=quantity
            )
        )
    
    log.debug(f"{settlement.chat_id} | {settler.user_id} | 📦 Ресурс добавлен: {resource.emoji} x{quantity}")
    return resource, quantity

def can_work_now(settler: models.Settler) -> tuple[bool, str]:
    #* Проверка доступности работы

    
    current_time = datetime.now()
    last_work_time = datetime.fromtimestamp(settler.last_work_time) if settler.last_work_time else datetime.min
    cooldown = timedelta(hours=settings.WORK_COOLDOWN_HOURS)
    
    if settler.work_is_completed:
        time_since_work = current_time - last_work_time
        if time_since_work < cooldown:
            remaining_time = cooldown - time_since_work
            hours = int(remaining_time.total_seconds() // 3600)
            minutes = int((remaining_time.total_seconds() % 3600) // 60)
            seconds = int(remaining_time.total_seconds() % 60)
            return False, f"{hours}ч. {minutes}м. {seconds}с." if hours > 0 else f"{minutes}м. {seconds}с." if minutes > 0 else f"{seconds}с."
    
    return True, ""

async def end_work(settler: models.Settler, chat_id: int, session: AsyncSession, mark_work_completed: bool = False):
    """
    Завершение работы - отмечает работу как выполненную и выдаёт опыт
    
    Args:
        settler: Поселенец
        chat_id: ID чата
        session: Сессия БД
        mark_work_completed: Отметить работу как выполненную
    """
    work_exp = 0
    
    if mark_work_completed:
        current_time = int(datetime.now().timestamp())
        await session.execute(
            update(models.Settler)
            .where(models.Settler.id == settler.id)
            .values(work_is_completed=True, last_work_time=current_time)
        )
        
        if settler.level <= 16:
            work_exp = random.randint(1, 2)
        elif settler.level <= 31:
            work_exp = random.randint(2, 3)
        else:
            work_exp = random.randint(3, 4)
        
        settlement_result = await session.execute(
            select(models.Settlement).where(models.Settlement.chat_id == chat_id)
        )
        settlement = settlement_result.scalars().first()
        
        if settlement:
            await settler_addExp(settler, settlement, session, work_exp)
    
    await session.commit()
    log.debug(f"{chat_id} | {settler.user_id} | 💼 Работа завершена, опыт: +{work_exp}")
    
    return work_exp