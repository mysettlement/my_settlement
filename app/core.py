from dataclasses import dataclass, field
from sqlalchemy import or_, text, insert, select, update, func
from sqlalchemy.orm import selectinload
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from aiogram import types
from datetime import datetime, timedelta
from typing import Dict, Tuple, Union, Optional, List
import logging
import random

from app.exceptions import GroupOwnerError, UserCreationError, SettlementCreationError, SettlerCreationError
from app.config import setup_logging, settings
from app.db import SessionLocal
from main import bot
import app.models as models
import app.mfunc as mfunc

log = setup_logging(logging.getLogger(__name__))


async def resource_getByEmoji(session: AsyncSession | None, emoji: str) -> models.Resource | None:
    if session is None:
        async with SessionLocal() as new_session:
            result = await new_session.execute(
                select(models.Resource).filter_by(emoji=emoji)
            )
            return result.scalars().first()

    result = await session.execute(
        select(models.Resource).filter_by(emoji=emoji)
    )
    return result.scalars().first()

async def resource_getRandomQuantity(resource: models.Resource) -> int:
    #* Получение случайного количества ресурса на основе его редкости
    if random.random() > models.RARITY_DROP_PROBABILITIES[resource.rarity]:
        return 0

    min_qty, max_qty = models.RARITY_QUANTITY_RANGES[resource.rarity]
    return random.randint(min_qty, max_qty)



async def building_getByScope(settlement: models.Settlement, settler: models.Settler, scope: str, session: AsyncSession):
    """Получает список построек в зависимости от контекста (городские/личные)."""
    stmt = select(models.Building).options(selectinload(models.Building.type))
    
    if scope == "town":
        stmt = stmt.join(models.BuildingType).where(
            models.Building.settlement_id == settlement.id,
            models.Building.owner_id == None
        )
    else:
        stmt = stmt.where(
            models.Building.owner_id == settler.id
        )
    
    result = await session.execute(stmt)
    return result.scalars().all()

async def building_checkRequirements(settlement: models.Settlement, settler: models.Settler, building_type: models.BuildingType, session: AsyncSession, compact_style: bool = False) -> tuple[bool, str, bool, str]:
    # ==== 1. ПРОВЕРКА РЕСУРСОВ ====
    cost_stmt = select(models.building_type_costs.c.resource_id, models.building_type_costs.c.quantity)\
        .where(models.building_type_costs.c.building_type_id == building_type.id)
    costs = (await session.execute(cost_stmt)).all()
    
    can_afford_resources = True
    cost_text_list = []
    
    if not costs:
        cost_text = "Бесплатно!"
    else:
        for r_id, req_qty in costs:
            res = await session.get(models.Resource, r_id)
            
            has_stmt = select(models.settler_resources.c.quantity).where(
                models.settler_resources.c.settler_id == settler.id, 
                models.settler_resources.c.resource_id == r_id
            )
            has_qty = (await session.execute(has_stmt)).scalar() or 0
            
            is_enough_res = has_qty >= req_qty
            emoji_status = "✅" if is_enough_res else "☑️"
            
            if not is_enough_res:
                can_afford_resources = False

            res_name = res.name if not compact_style else ""
            r_text = f"[{emoji_status}] {res.emoji} "
            if is_enough_res:
                r_text += f"{res_name} ({has_qty}/{req_qty})"
            else:
                r_text += f"<b>{res_name} ({has_qty}/{req_qty})</b>"
            
            cost_text_list.append(r_text)

        cost_text = "\n".join(cost_text_list)


    # ==== 2. ПРОВЕРКА ПРОФЕССИЙ ====
    required_profs_dict = building_type.required_professions or {}
    
    global_prof_success = True
    prof_text_lines = []

    if not required_profs_dict:
        prof_text = "Никто не требуется!"
    else:
        needed_emojis = list(required_profs_dict.keys())

        profs_stmt = select(models.Profession).where(models.Profession.emoji.in_(needed_emojis))
        found_profs = (await session.execute(profs_stmt)).scalars().all()
        
        prof_map = {p.emoji: p for p in found_profs}

        for req_emoji, req_qty in required_profs_dict.items():
            
            prof_obj = prof_map.get(req_emoji)

            if not prof_obj:
                prof_text_lines.append(f"❓ Неизвестная профессия ({req_emoji})")
                global_prof_success = False
                continue

            count_stmt = select(func.count(models.Settler.id)).where(
                models.Settler.settlement_id == settlement.id,
                models.Settler.profession_id == prof_obj.id
            )
            current_count = (await session.execute(count_stmt)).scalar() or 0

            is_enough_profs = current_count >= req_qty
            
            if not is_enough_profs:
                global_prof_success = False

            prof_name = prof_obj.name
            emoji_status = "✅" if is_enough_profs else "☑️"
            line = f"[{emoji_status}] {prof_obj.emoji} "
            if is_enough_profs:
                line += f"{prof_name} ({current_count}/{req_qty})"
            else:
                line += f"<b>{prof_name} ({current_count}/{req_qty})</b>"
            
            prof_text_lines.append(line)

        prof_text = "\n".join(prof_text_lines)

    return global_prof_success, prof_text, can_afford_resources, cost_text

async def building_startBuilding(settler: models.Settler, building_type_id: int, scope: str, session: AsyncSession) -> tuple[bool, str]:
    """Начало строительства."""
    stmt = select(models.BuildingType).options(selectinload(models.BuildingType.costs)).where(models.BuildingType.id == building_type_id)
    b_type = (await session.execute(stmt)).scalars().first()
    
    if not b_type:
        return False, "⚠️ Чертеж не найден."

    settlement = await session.get(models.Settlement, settler.settlement_id)
    is_prof_enough, prof_text, is_res_enough, res_text = await building_checkRequirements(settlement, settler, b_type, session)
    if not is_prof_enough or not is_res_enough:
        return False, "\n".join(filter(None, [prof_text, res_text]))

    missing = []
    
    stmt_costs = select(models.building_type_costs.c.resource_id, models.building_type_costs.c.quantity).where(
        models.building_type_costs.c.building_type_id == b_type.id
    )
    costs_res = (await session.execute(stmt_costs)).all()
    
    for res_id, qty in costs_res:
        has_stmt = select(models.settler_resources.c.quantity).where(
            models.settler_resources.c.settler_id == settler.id,
            models.settler_resources.c.resource_id == res_id
        )
        has_qty = (await session.execute(has_stmt)).scalar() or 0
        if has_qty < qty:
            res_obj = await session.get(models.Resource, res_id)
            missing.append(f"{res_obj.emoji} {qty - has_qty}")

    if missing:
        return False, f"⚠️ Недостаточно ресурсов: {', '.join(missing)}!"

    for res_id, qty in costs_res:
        await session.execute(
            update(models.settler_resources)
            .where(
                models.settler_resources.c.settler_id == settler.id,
                models.settler_resources.c.resource_id == res_id
            )
            .values(quantity=models.settler_resources.c.quantity - qty)
        )

    finish_time = datetime.now() + timedelta(seconds=b_type.construction_time)
    
    new_building = models.Building(
        building_type_id=b_type.id,
        settlement_id=settler.settlement_id,
        owner_id=settler.id if scope == "my" or scope == "private" or scope == "settler" or scope == "personal" else None,
        level=1,
        under_construction_until=finish_time
    )
    session.add(new_building)
    await session.commit()
    
    return True, f"<b>🏗 Стройка началась!</b>\n{b_type.emoji} <b>{b_type.name}</b> будет готов <b>{mfunc.format_relative_time(b_type.construction_time)}</b>."



async def user_getOrCreate(telegram_user: types.User, session: AsyncSession | None = None) -> models.User:
    #* Получение или создание пользователя
    telegram_name = getattr(telegram_user, 'full_name', None) or f"User {telegram_user.id}"
    
    async with SessionLocal() as session:
        result = await session.execute(
            select(models.User).where(models.User.telegram_id == telegram_user.id)
        )
        db_user = result.scalars().first()

        if db_user:
            if not db_user.name or db_user.name != telegram_name:
                db_user.name = telegram_name
                await session.commit()
            return db_user

        try:
            user = models.User(
                telegram_id=telegram_user.id,
                name=telegram_name
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            log.debug(f"✅ Создан пользователь: {user.name} ({user.telegram_id})")
            return user
        except IntegrityError:
            await session.rollback()
            result = await session.execute(
                select(models.User).where(models.User.telegram_id == telegram_user.id)
            )
            return result.scalars().first()
        except Exception as e:
            raise UserCreationError(f"Ошибка при создании пользователя {telegram_user.id}: {str(e)}", telegram_user_id=telegram_user.id)



async def settlement_getOrCreate(chat: types.Chat):
    #* Получение или создание поселения
    if chat.type == "private":
        return None

    async with SessionLocal() as session:
        stmt = select(models.Settlement).options(
            selectinload(models.Settlement.members),
            selectinload(models.Settlement.owner)
        ).where(models.Settlement.chat_id == chat.id)
        
        db_settlement = (await session.execute(stmt)).scalars().first()
        if db_settlement:
            return db_settlement

        try:
            group_owner = await mfunc.get_group_owner(chat.id)
            if not group_owner:
                 raise SettlementCreationError(f"Не удалось найти владельца чата", chat_id=chat.id)

            owner_user = await user_getOrCreate(group_owner) 

            settlement = models.Settlement(
                chat_id=chat.id,
                name=chat.title or f"Поселение {chat.id}",
                owner_id=owner_user.id
            )
            session.add(settlement)
            await session.commit()
            await session.refresh(settlement, ['members', 'owner'])
            log.debug(f"{settlement.id} | ✅ Создано поселение: {settlement.name}")
            return settlement

        except IntegrityError:
            await session.rollback()
            db_settlement = (await session.execute(stmt)).scalars().first()
            if db_settlement:
                return db_settlement
            raise SettlementCreationError(f"Не удалось получить поселение после отката {chat.id}", chat_id=chat.id)
            
        except Exception as e:
            await session.rollback()
            raise SettlementCreationError(f"Ошибка поселения {chat.id}: {str(e)}", chat_id=chat.id)



async def settler_getOrCreate(user: models.User, settlement: models.Settlement):
    #* Получение или создание поселенца (защита от Race Condition)
    async with SessionLocal() as session:
        stmt = select(models.Settler).options(
            selectinload(models.Settler.profession)
        ).where(
            models.Settler.user_id == user.id, 
            models.Settler.settlement_id == settlement.id
        )

        db_settler = (await session.execute(stmt)).scalars().first()
        if db_settler:
            return db_settler

        try:
            settler = models.Settler(
                user_id=user.id,
                settlement_id=settlement.id
            )
            session.add(settler)
            
            await session.commit()
            await session.refresh(settler, ['user', 'settlement', 'profession'])
            log.debug(f"{settlement.id} | ✅ Создан поселенец: {settler.id}")
            return settler

        except IntegrityError:
            await session.rollback()
            db_settler = (await session.execute(stmt)).scalars().first()
            return db_settler
            
        except Exception as e:
            raise SettlerCreationError(f"Ошибка поселенца {user.id}: {str(e)}", user_id=user.id)

async def settler_addExp(settler: models.Settler, session: AsyncSession, exp: int):
    #* Добавление опыта поселенцу и обработка повышения уровня
    settler = await session.get(models.Settler, settler.id)

    user_result = await session.execute(
        select(models.User).where(models.User.id == settler.user_id)
    )
    user = user_result.scalars().first()

    settler.exp += exp
    log.debug(f"{settler.settlement_id} | {settler.user_id} | 🗂 Опыт увеличен: {exp:+} ({settler.exp}/{settler.target_exp})")

    text = None
    old_level = settler.level
    old_rank = settler.rank
    old_emoji = settler.rank_emoji_available[0] if settler.rank_emoji_available else "❓"

    while settler.exp >= settler.target_exp:
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
            settler.target_exp = 9 * settler.level - 320
            settler.rank = "Дворянин"
        else:
            settler.target_exp = 9 * settler.level - 450
            settler.rank = "Лорд"

        settler.level += 1
        settler.exp -= settler.target_exp

        text = f"🎉 <b>{user.name if user else f"User {settler.user_id}"}</b> повысил(а) уровень до <b>{settler.level}</b>! (🗂 {settler.exp}/{settler.target_exp})\n"
    
    if old_rank != settler.rank:
        rank_emojis = {
            "Крестьянин": ["🧑‍🌾", "👨‍🌾", "👩‍🌾"],
            "Вольный": ["🌾", "🌱", "🍃"],
            "Старейшина": ["🕍", "⛩", "🏺"],
            "Дворянин": ["🏰", "🏯", "🏛"],
            "Лорд": ["👑", "🏰", "⚔️", "🛡"]
        }
        new_rank_emojis = rank_emojis.get(settler.rank, [])
        settler.rank_emoji_available = new_rank_emojis
        settler.emoji = new_rank_emojis[0] if new_rank_emojis else "❓"
        flag_modified(settler, 'rank_emoji_available')

        text += f"<b>🔼 Новый титул:</b> {old_emoji} {old_rank} → {new_rank_emojis[0] if new_rank_emojis else '❓'} <b>{settler.rank}</b>!"
        log.debug(f"{settler.settlement_id} | {settler.user_id} | 🔼 Повышение титула: {settler.rank}")

    await session.flush()
    await session.refresh(settler, ["settlement"])

    if text:
        log.debug(f"{settler.settlement_id} | {settler.user_id} | ⬆️ Повышение уровня: {old_level} → {settler.level} (🗂 {settler.exp}/{settler.target_exp})")
        await bot.send_message(settler.settlement.chat_id, text)

    return settler

async def settler_addMoney(settler: models.Settler, session: AsyncSession, quantity: int):
    #* Добавление денег поселенцу
    current = await session.get(models.Settler, settler.id)
    if not current:
        return None

    current.balance += quantity
    await session.flush()
    await session.refresh(current, ["settlement"])
    log.debug(f"{current.settlement_id} | {current.user_id} | 💰 Деньги получены: {quantity:+} ({current.balance})")
    return quantity

async def settler_updateResource(settler: models.Settler, session: AsyncSession, emoji: str, quantity: int = None, resource: models.Resource = None, check_if_enough: bool = False) -> Tuple[bool, str]:
    #* Обновление ресурса поселенца (добавление/снятие)
    if not (resource := resource or await resource_getByEmoji(session, emoji)):
        return False, f"⚠️ Ресурс {emoji} не найден"

    if quantity is None:
        quantity = random.randint(*models.RARITY_QUANTITY_RANGES.get(resource.rarity, (1, 1)))
    
    settler = await session.get(models.Settler, settler.id)
    if not settler:
        return False, "⚠️ Поселенец не найден"

    table = models.settler_resources
    criteria = (table.c.settler_id == settler.id) & (table.c.resource_id == resource.id)
    current_qty = (await session.execute(select(table.c.quantity).where(criteria))).scalar() or 0

    if check_if_enough and quantity < 0 and (current_qty + quantity) < 0:
        return False, f"⚠️ Недостаточно ресурсов: {resource.emoji} {current_qty}/{abs(quantity)}"

    res = await session.execute(update(table).where(criteria).values(quantity=table.c.quantity + quantity))
    if res.rowcount == 0:
        await session.execute(insert(table).values(settler_id=settler.id, resource_id=resource.id, quantity=quantity))

    target_col, action = (models.Resource.received, "📥 Получен") if quantity > 0 else (models.Resource.spent, "📤 Снят")
    await session.execute(
        update(models.Resource).where(models.Resource.id == resource.id)
        .values({target_col: target_col + abs(quantity)})
    )

    await session.flush()
    if quantity > 0: await session.refresh(settler, ["settlement"])
    
    log.debug(f"{settler.settlement_id} | {settler.user_id} | {action} ресурс: {resource.emoji} {quantity:+}")
    return True, f"{resource.emoji} {abs(quantity)}"

async def settler_add(settler: models.Settler, session: AsyncSession, emoji: str, quantity: int = None) -> Dict[str, int]:
    #* Добавление ресурса/денег/опыта поселенцу
    obtained: Dict[str, int] = {}

    if emoji == "💰" or emoji == "balance":
        await settler_addMoney(settler, session, quantity)

    elif emoji == "🗂" or emoji == "exp":
        await settler_addExp(settler, session, quantity)

    else:
        success, _ = await settler_updateResource(settler, session, emoji, quantity)
    
    obtained[emoji] = quantity
    return obtained

async def settler_updateQuote(settler: models.Settler, settlement: models.Settlement, session: AsyncSession, add_quote: int = 0):
    #* Обновление меры поселенца и обработка её выполнения
    current = await session.get(models.Settler, settler.id)
    if not current:
        return None

    if settler.overtime_is_toggled:
        current.target_quote = round((settler.level * 0.85 + 6) + (2 * (settler.overtime_count + 1)))
    else:
        current.target_quote = round(current.level * 0.85 + 6)

    if not current.quote_is_completed:
        current.quote += add_quote
        if current.quote >= current.target_quote:
            current.quote_is_completed = True
            user_result = await session.execute(
                select(models.User).where(models.User.id == current.user_id)
            )
            user = user_result.scalars().first()
            
            if current.level <= 16:
                rexp = random.randint(1, 3)
                earned_xp = current.level * 0.45 + rexp
                rmoney = random.randint(2, 4)
            elif current.level <= 31:
                rexp = random.randint(2, 5)
                earned_xp = current.level * 0.35 + rexp
                rmoney = random.randint(3, 7)
            else:
                rexp = random.randint(4, 9)
                earned_xp = current.level * 0.20 + rexp
                rmoney = random.randint(5, 13)
                
            earned_money = current.level + rmoney

            await settler_addMoney(current, session, earned_money)
            if current.overtime_is_toggled:
                earned_xp *= 0.2
            await settler_addExp(current, session, earned_xp)
            
            if current:
                current.quote = 0
                if current.overtime_is_toggled:
                    current.target_quote = round((settler.level * 0.85 + 6) + (2 * (settler.overtime_count + 1)))
                else:
                    current.target_quote = round(current.level * 0.85 + 6)
            
            text = (
                f"📄 <b>{user.name if user else f'User {current.user_id}'}</b> исполнил меру <b>{current.target_quote}/{current.target_quote}</b>!"
                f"\n🗂: {round(earned_xp):+} | 💰: {round(earned_money):+}" if earned_xp > 0 else f"\n💰: {round(earned_money):+}"
                f"\nℹ️ Чтоб в мудрости возрасти, доведётся каталог 🗂 до конца довести; каталог 🗂 опыт заменяет" if current.level <= 2 and user.show_hints else ""
            )
            
            await bot.send_message(settlement.chat_id, text)
            log.debug(f"{settlement.id} | {current.user_id} | ✅ Мера исполнена: {current.quote}/{current.target_quote}")

    log.debug(f"{settlement.id} | {current.user_id} | 🔄 Мера обновлена: {current.quote}/{current.target_quote}")
    await session.commit()
    await session.refresh(current, ["user", "settlement"])


def settler_canWorkNow(settler: models.Settler) -> tuple[bool, str]:
    #* Проверка, может ли поселенец начать новую работу с учётом кулдауна
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

async def settler_startWorkflow(message_or_callback: Union[types.Message, types.CallbackQuery], work: models.Work, user: models.User, settler: models.Settler):
    #* Запуск рабочего процесса для поселенца
    is_message = True if isinstance(message_or_callback, types.Message) else False
    chat_id = message_or_callback.chat.id if is_message else message_or_callback.message.chat.id
    user_key = f"{chat_id}_{user.telegram_id}"

    can_work, countdown = settler_canWorkNow(settler)
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
            success, result = await settler_updateResource(settler, session, emoji, - qty, check_if_enough=True)
            if not success:
                await message_or_callback.answer(result) if is_message else await message_or_callback.answer(result, show_alert=True)
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

async def settler_applyRewards(work: models.Work, settler: models.Settler, session: AsyncSession) -> Dict[str, int]:
    #* Применение наград за работу поселенцу
    obtained: Dict[str, int] = {}
    settler = await session.get(models.Settler, settler.id)

    settler_bonuses, settlement_bonuses = await setter_getBonuses(settler, session)

    emojis_needed = [i.emoji for i in work.rewards if i.emoji not in ["exp", "🗂", "balance", "💰"]]
    resources_map = {}
    if emojis_needed:
        res_result = await session.execute(select(models.Resource).where(models.Resource.emoji.in_(emojis_needed)))
        resources_map = {r.emoji: r for r in res_result.scalars().all()}

    for item in work.rewards:
        resource = resources_map.get(item.emoji)

        effective_bonuses = _get_effective_bonuses(item, settler_bonuses, settlement_bonuses)

        if not await _roll_chance(item, resource, effective_bonuses):
            log.debug(f"{settler.settlement_id} | {settler.user_id} | Предмет не выпал: {item.emoji}")
            continue

        quantity = await _calculate_quantity(item, resource, effective_bonuses)

        await settler_add(settler, session, item.emoji, quantity)
        obtained[item.emoji] = quantity + obtained.get(item.emoji, 0)

    await session.commit()
    await session.refresh(settler, ["settlement"])
    log.debug(f"{settler.settlement_id} | {settler.user_id} | 🏆 Награды выданы за {work.emoji} {work.name}")
    return obtained


@dataclass
class BonusSet:
    # Шанс (аддитивный, +0.05)
    global_chance: float = 0.0
    category_chance: Dict[str, float] = field(default_factory=dict)
    resource_chance: Dict[str, float] = field(default_factory=dict)
    
    # Количество (флэт, +1)
    global_qty_mod: int = 0
    category_qty_mod: Dict[str, int] = field(default_factory=dict)
    resource_qty_mod: Dict[str, int] = field(default_factory=dict)
    
    # Количество (множитель, x1.1)
    global_qty_mult: float = 0.0
    category_qty_mult: Dict[str, float] = field(default_factory=dict)
    resource_qty_mult: Dict[str, float] = field(default_factory=dict)

    def add_bonus(self, bonuses: dict):
        self.global_chance += bonuses.get("global_chance_multiplier", 0.0)
        
        for category, value in bonuses.get("category_chance_multiplier", {}).items():
            self.category_chance[category] = self.category_chance.get(category, 0.0) + value
            
        for resource, value in bonuses.get("resource_chance_multiplier", {}).items():
            self.resource_chance[resource] = self.resource_chance.get(resource, 0.0) + value

        self.global_qty_mod += bonuses.get("global_quantity_modifier", 0)
        
        for category, value in bonuses.get("category_quantity_modifier", {}).items():
            self.category_qty_mod[category] = self.category_qty_mod.get(category, 0) + value
            
        for resource, value in bonuses.get("resource_quantity_modifier", {}).items():
            self.resource_qty_mod[resource] = self.resource_qty_mod.get(resource, 0) + value
            
        self.global_qty_mult += bonuses.get("global_quantity_multiplier", 0.0)
        
        for category, value in bonuses.get("category_quantity_multiplier", {}).items():
            self.category_qty_mult[category] = self.category_qty_mult.get(category, 0.0) + value
            
        for resource, value in bonuses.get("resource_quantity_multiplier", {}).items():
            self.resource_qty_mult[resource] = self.resource_qty_mult.get(resource, 0.0) + value

    def merge(self, other: "BonusSet"):
        """Складывает текущие показатели с другим BonusSet."""
        self.global_chance += other.global_chance
        self.global_qty_mod += other.global_qty_mod
        self.global_qty_mult += other.global_qty_mult
        
        for k, v in other.category_chance.items():
            self.category_chance[k] = self.category_chance.get(k, 0.0) + v
        for k, v in other.resource_chance.items():
            self.resource_chance[k] = self.resource_chance.get(k, 0.0) + v

        for k, v in other.category_qty_mod.items():
            self.category_qty_mod[k] = self.category_qty_mod.get(k, 0) + v
        for k, v in other.resource_qty_mod.items():
            self.resource_qty_mod[k] = self.resource_qty_mod.get(k, 0) + v

        for k, v in other.category_qty_mult.items():
            self.category_qty_mult[k] = self.category_qty_mult.get(k, 0.0) + v
        for k, v in other.resource_qty_mult.items():
            self.resource_qty_mult[k] = self.resource_qty_mult.get(k, 0.0) + v

    def to_dict(self) -> dict:
        """Превращает объект обратно в словарь для format_bonuses_text."""
        res = {}
        if self.global_chance: res["global_chance_multiplier"] = self.global_chance
        if self.category_chance: res["category_chance_multiplier"] = self.category_chance
        if self.resource_chance: res["resource_chance_multiplier"] = self.resource_chance
        
        if self.global_qty_mod: res["global_quantity_modifier"] = self.global_qty_mod
        if self.category_qty_mod: res["category_quantity_modifier"] = self.category_qty_mod
        if self.resource_qty_mod: res["resource_quantity_modifier"] = self.resource_qty_mod
        
        if self.global_qty_mult: res["global_quantity_multiplier"] = self.global_qty_mult
        if self.category_qty_mult: res["category_quantity_multiplier"] = self.category_qty_mult
        if self.resource_qty_mult: res["resource_quantity_multiplier"] = self.resource_qty_mult
        return res

async def setter_getBonuses(settler: models.Settler, session: AsyncSession) -> Tuple[BonusSet, BonusSet]:
    #* Получение бонусов поселенца и поселения от построек (в будущем артефактов, инструментов и событий)
    settler_bonuses = BonusSet()
    settlement_bonuses = BonusSet()

    stmt_settlement = select(models.Building).options(
        selectinload(models.Building.type)
    ).where(
        models.Building.settlement_id == settler.settlement_id,
        or_(
            models.Building.under_construction_until == None,
            models.Building.under_construction_until <= datetime.now()
        )
    )
    buildings = (await session.execute(stmt_settlement)).scalars().all()

    for b in buildings:
        if not b.type.bonuses:
            continue
        
        if b.owner_id == settler.id and b.type.is_private:
            settler_bonuses.add_bonus(b.type.bonuses)
        elif not b.type.is_private or b.owner_id is None:
            settlement_bonuses.add_bonus(b.type.bonuses)

    return settler_bonuses, settlement_bonuses

def _get_effective_bonuses(item: models.LootItem, settler_bonuses: BonusSet, settlement_bonuses: BonusSet) -> BonusSet:
    #* Создает итоговый набор бонусов для предмета, учитывая флаги affected_by
    effective = BonusSet()

    def merge(source: BonusSet):
        effective.global_chance += source.global_chance
        effective.global_qty_mod += source.global_qty_mod
        effective.global_qty_mult *= source.global_qty_mult
        
        for k, v in source.category_chance.items(): effective.category_chance[k] = effective.category_chance.get(k, 0.0) + v
        for k, v in source.resource_chance.items(): effective.resource_chance[k] = effective.resource_chance.get(k, 0.0) + v
        
        for k, v in source.category_qty_mod.items(): effective.category_qty_mod[k] = effective.category_qty_mod.get(k, 0) + v
        for k, v in source.resource_qty_mod.items(): effective.resource_qty_mod[k] = effective.resource_qty_mod.get(k, 0) + v
        
        for k, v in source.category_qty_mult.items(): effective.category_qty_mult[k] = effective.category_qty_mult.get(k, 1.0) * v
        for k, v in source.resource_qty_mult.items(): effective.resource_qty_mult[k] = effective.resource_qty_mult.get(k, 1.0) * v

    if item.affected_by_settler_bonuses:
        merge(settler_bonuses)
    if item.affected_by_settlement_bonuses:
        merge(settlement_bonuses)
        
    return effective

async def _roll_chance(item: models.LootItem, resource: Optional[models.Resource], bonuses: BonusSet) -> bool:
    #* Определяет, выпал ли предмет на основе шанса и бонусов
    base = item.chance
    if base is None:
        base = models.RARITY_DROP_PROBABILITIES.get(resource.rarity, 0.0) if resource else 1.0
    
    if base >= 1.0:
        return True
    
    modifier = 0.0
    if item.affected_by_luck:
        modifier += bonuses.global_chance

    resource = resource if resource else await resource_getByEmoji(None, item.emoji)
    category = resource.category if resource else ("Опыт" if item.emoji == "exp" or item.emoji == "🗂" else None)

    if category:
        modifier += bonuses.category_chance.get(category, 0.0)
    modifier += bonuses.resource_chance.get(item.emoji, 0.0)

    final_chance = min(base + modifier, 1.0)
    return random.random() <= final_chance

async def _calculate_quantity(item: models.LootItem, resource: Optional[models.Resource], bonuses: BonusSet) -> int:
    #* Вычисляет итоговое количество предмета с учётом бонусов
    if not item.min_qty and not item.max_qty:
        base = random.randint(models.RARITY_QUANTITY_RANGES.get(resource.rarity, (1, 1))[0] if resource else 1)
    else:
        base = item.min_qty if item.qty_is_fixed else random.randint(item.min_qty, item.max_qty)

    mult = 1.0
    mod = 0

    if item.affected_by_global_bonuses:
        mult += bonuses.global_qty_mult
        mod += bonuses.global_qty_mod

    resource = resource if resource else await resource_getByEmoji(None, item.emoji)
    category = resource.category if resource else ("Опыт" if item.emoji == "exp" or item.emoji == "🗂" else "Гроши" if item.emoji == "balance" or item.emoji == "💰" else None)

    if category:
        mult += bonuses.category_qty_mult.get(category, 0)
        mod += bonuses.category_qty_mod.get(category, 0)

    mult += bonuses.resource_qty_mult.get(item.emoji, 0)
    mod += bonuses.resource_qty_mod.get(item.emoji, 0)

    final_qty = int(base * mult + mod)
    return max(1, final_qty)
