from sqlalchemy import text, insert, select, update
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from aiogram import types
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Union
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


async def resource_getByEmoji(emoji: str, session: AsyncSession) -> models.Resource:
    #* Получение ресурса по эмодзи
    result = await session.execute(
        select(models.Resource).where(models.Resource.emoji == emoji)
    )
    resource = result.scalars().first()
    if not resource:
        raise ValueError(f"Ресурс с эмодзи '{emoji}' не найден")
    return resource

def resource_getRandomQuantity(resource: models.Resource) -> int:
    if random.random() > models.RARITY_DROP_PROBABILITIES[resource.rarity]:
        return 0

    min_qty, max_qty = models.RARITY_QUANTITY_RANGES[resource.rarity]
    return random.randint(min_qty, max_qty)

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

async def settlement_getOrCreate(chat: types.Chat):
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
                    log.debug(f"{settlement.id} | ✅ Создано поселение: {settlement.name} ({settlement.chat_id})")
                    return settlement
                except Exception as e:
                    log.warning(f"Ошибка при создании поселения: {e}")
                    await session.rollback()
                    
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
                        log.debug(f"{db_settlement.id} | ✅ Найдено существующее поселение: {db_settlement.name} ({db_settlement.chat_id})")
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
                
                log.debug(f"{settlement.id} | ✅ Создан поселец: {settler.id}")
                return settler
    except Exception as e:
        raise SettlerCreationError(f"Ошибка при создании/получении поселенца {user.id} в поселении {settlement.id}: {str(e)}", user_id=user.id)

async def settler_addExp(settler: models.Settler, session: AsyncSession, exp: int):
    current = await session.get(models.Settler, settler.id)
    if not current:
        result = await session.execute(select(models.Settler).where(models.Settler.id == settler.id))
        current = result.scalars().first()
        if not current:
            raise ValueError(f"Settler with id={settler.id} not found in DB")

    current.exp += exp
    log.debug(f"{current.settlement_id} | {current.user_id} | 🗂 Опыт увеличен: +{exp} ({current.exp}/{current.target_exp})")

    text = None
    while current.exp >= current.target_exp:
        old_rank = current.rank
        old_emoji = current.rank_emoji_available[0] if current.rank_emoji_available else "❓"
        current.level += 1
        current.exp -= current.target_exp

        # перерасчёт опыта и ранга
        if settler.level < 15:
            settler.target_exp = 2 * settler.level + 7
            settler.rank = "Крестьянин"
        elif settler.level < 30:
            settler.target_exp = 5 * settler.level - 38
            settler.rank = "Вольный"
        elif settler.level < 45:
            settler.target_exp = 9 * settler.level - 158
            settler.rank = "Старейшина"
        elif settler.level < 60:
            settler.rank = "Дворянин"
        else:
            settler.rank = "Лорд"

        user_result = await session.execute(
            select(models.User).where(models.User.id == current.user_id)
        )
        user = user_result.scalars().first()
        user_name = user.name if user else f"User {current.user_id}"

        text = f"🎉 <b>{user_name}</b> повысил уровень до <b>{current.level}</b>!\n"
        log.debug(f"{current.settlement_id} | {current.user_id} | ⬆️ Новый уровень: {current.level}")

        if old_rank != current.rank:
            rank_emojis = {
                "Крестьянин": ["🧑‍🌾", "👨‍🌾", "👩‍🌾"],
                "Вольный": ["🌾", "🌱", "🍃"],
                "Старейшина": ["🕍", "⛩", "🏺"],
                "Дворянин": ["🏰", "🏯", "🏛"],
                "Лорд": ["👑", "🏰", "⚔️", "🛡"]
            }
            new_rank_emojis = rank_emojis.get(current.rank, [])
            current.rank_emoji_available = new_rank_emojis
            flag_modified(current, 'rank_emoji_available')

            text += f"<b>🔼 Новый ранг:</b> {old_emoji} {old_rank} → {new_rank_emojis[0] if new_rank_emojis else '❓'} <b>{current.rank}</b>!"
            log.debug(f"{current.settlement_id} | {current.user_id} | 🔼 Новый ранг: {current.rank}")

    await session.flush()
    refreshed = await session.get(models.Settler, current.id)
    await session.refresh(refreshed, ["user", "settlement"])

    if text:
        await bot.send_message(refreshed.settlement.chat_id, text)

    return refreshed

async def settler_addMoney(settler: models.Settler, settlement: models.Settlement, session: AsyncSession, money: int):
    result = await session.execute(
        select(models.Settler).where(models.Settler.id == settler.id)
    )
    current_settler = result.scalars().first()
    if not current_settler:
        return None

    current_settler.balance += money
    await session.commit()
    await session.refresh(current_settler, ["user", "settlement"])
    log.debug(f"{settlement.id} | {current_settler.user_id} | 💰 Деньги получены: +{money} ({current_settler.balance})")
    return current_settler

async def settler_addResource(settler: models.Settler, session: AsyncSession, quantity: int = None, resource: models.Resource = None, emoji: str = None) -> Tuple[models.Resource, int]:
    #* Добавление ресурса поселенцу
    resource = await resource_getByEmoji(emoji, session) if not resource else resource
    
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
    
    await session.execute(
        update(models.Resource).where(models.Resource.id == resource.id).values(
            received=models.Resource.received + quantity
        )
    )
    
    log.debug(f"{settler.settlement_id} | {settler.user_id} | 📥 Ресурс получен: {resource.emoji} x{quantity}")

    return resource, quantity

async def settler_withdrawResource(settler: models.Settler, session: AsyncSession, emoji: str, quantity: int):
    #* Изъятие ресурса у поселенца
    resource = await resource_getByEmoji(emoji, session)
    
    existing_result = await session.execute(
        select(models.settler_resources.c.quantity).where(
            models.settler_resources.c.settler_id == settler.id,
            models.settler_resources.c.resource_id == resource.id
        )
    )
    exist = existing_result.scalar() or 0
    
    if exist < quantity:
        return False, f"⚠️ Недостаточно ресурсов: {resource.emoji} {exist}/{quantity}"
    
    await session.execute(
        update(models.settler_resources).where(
            models.settler_resources.c.settler_id == settler.id,
            models.settler_resources.c.resource_id == resource.id
        ).values(quantity=models.settler_resources.c.quantity - quantity)
    )
    
    await session.execute(
        update(models.Resource).where(models.Resource.id == resource.id).values(
            spent=models.Resource.spent + quantity
        )
    )
    
    log.debug(f"{settler.settlement.id} | {settler.user_id} | 📤 Ресурс снят: {resource.emoji} x{quantity}")
    return True, f"{resource.emoji} {quantity}"

async def quote_update(settler: models.Settler, settlement: models.Settlement, session: AsyncSession, add_quote: int = 0):
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
            updated_settler = await settler_addExp(current_settler, session, earned_xp)
            
            if updated_settler:
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
            log.debug(f"{settlement.id} | {current_settler.user_id} | ✅ Мера исполнена: {current_settler.quote}/{current_settler.target_quote}")

    log.debug(f"{settlement.id} | {current_settler.user_id} | 🔄 Мера обновлена: {current_settler.quote}/{current_settler.target_quote}")
    await session.commit()
    await session.refresh(current_settler, ["user", "settlement"])

def can_work_now(settler: models.Settler) -> tuple[bool, str]:
    current_time = datetime.now()
    
    if settler.last_work_time == 0:
        return True, ""

    last_work_time = datetime.fromtimestamp(settler.last_work_time)
    cooldown = timedelta(hours=settings.WORK_COOLDOWN_HOURS)
    time_since_work = current_time - last_work_time

    if settler.work_is_completed and time_since_work < cooldown:
        remaining = cooldown - time_since_work
        total_seconds = int(remaining.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return False, f"{hours}ч. {minutes}м. {seconds}с."
        elif minutes > 0:
            return False, f"{minutes}м. {seconds}с."
        else:
            return False, f"{seconds}с."

    return True, ""

async def start_workflow(
    message_or_callback: Union[types.Message, types.CallbackQuery],
    work: models.Work,
    user: models.User,
    settler: models.Settler
):
    is_message = True if isinstance(message_or_callback, types.Message) else False
    chat_id = message_or_callback.chat.id if is_message else message_or_callback.message.chat.id
    user_key = f"{chat_id}_{user.telegram_id}"

    can_work, countdown = can_work_now(settler)
    if not can_work:
        text = f"⏳ Труд уж завершён. Новая работа появится через: {countdown}"
        await message_or_callback.answer(text) if is_message else await message_or_callback.answer(text, show_alert=True)
        return False
    
    can_start, error = mfunc.can_start_work(chat_id)
    if not can_start:
        await message_or_callback.answer(error) if is_message else await message_or_callback.answer(error, show_alert=True)
        return False
    
    async with SessionLocal() as session:
        for emoji, qty in work.requirements.items():
            if emoji == "level":
                if settler.level < qty:
                    text = f"⚠️ Сие дело тебе не по плечу. 💡 Требуемый уровень: {settler.level}/{qty}"
                    await message_or_callback.answer(text) if is_message else await message_or_callback.answer(text, show_alert=True)
                    return False
                continue
            success, result = await settler_withdrawResource(settler, session, emoji, qty)
            if not success:
                await message_or_callback.answer(result) if is_message else await message_or_callback.answer(text, show_alert=True)
            return success
        await session.commit()
    
    mfunc.start_work(chat_id)
    workflow = work.build()
    mfunc.active_games[user_key] = workflow

    remaining = mfunc.get_work_remaining_time(chat_id)
    text = f"{work.emoji} <b>{work.name}</b>\n\n{workflow.get_status_text()}\n\n⏳ Осталось <b>{remaining} секунд</b>"

    kb = workflow.get_keyboard()
    if is_message:
        await message_or_callback.answer(text, reply_markup=kb)
    else:
        await message_or_callback.answer(f"{work.emoji} {work.name}!")
        await message_or_callback.message.edit_text(text, reply_markup=kb)
    
    log.debug(f"{settler.settlement_id} | {user.id} | 🚧 Работа начата: {work.name}")
    return True

async def apply_rewards(work: models.Work, settler: models.Settler, session: AsyncSession) -> Tuple[Dict[models.Resource, int], int]:
    obtained: Dict[models.Resource, int] = {}
    exp = 0

    for key, value in work.rewards.items():
        if key == "exp":
            exp = value() if callable(value) else int(value) if value is not None else random.randint(1, 3)
            if exp > 0:
                await settler_addExp(settler, session, exp)
            continue

        resource = await resource_getByEmoji(key, session)
        if not resource:
            continue

        if callable(value):
            qty = value()
        elif value is not None:
            qty = int(value)
        else:
            qty = resource_getRandomQuantity(resource)

        if qty <= 0:
            continue

        added_resource, added_qty = await settler_addResource(settler, session, qty, resource)
        obtained[added_resource] = added_qty

    await session.commit()
    return obtained, exp
