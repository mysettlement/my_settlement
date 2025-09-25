from aiogram import Router, types, F, Bot
from aiogram.filters import Command, CommandStart, or_f, and_f
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode, parse_mode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, insert
from sqlalchemy.orm import selectinload

import logging
from datetime import datetime

from config import setup_logging, settings
from db import SessionLocal
import core
import models
from mfunc import can_click_button, can_start_work, format_reward_text, start_work, end_work, get_work_remaining_time, can_choose_craft, work_in_progress, work_timeout_tasks, work_start_time, work_in_progress, active_games

bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, disable_notification=True, link_preview_is_disabled=True)
    )
router = Router()
db_session: AsyncSession = None
log = setup_logging(logging.getLogger(__name__))



@router.message(or_f(Command("my_id"), F.text.lower() == "мой айди", F.text.lower() == "@mysettlementbot мой айди"))
async def my_id_command(message: types.Message):
    #* Обработка команды /my_id
    user = await core.user_getOrCreate(message.from_user)
    text = (
        f"👤 <b>{user.name}</b>\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💬 <code>{user.user_id}</code>\n"
    )
    await message.answer(text)
    log.debug(f"{message.chat.id} | Функция my_id_command() выполнена")

@router.message(F.chat.type == "private")
async def private_handler(message: types.Message):
    #* Обработка личных сообщений
    user = await core.user_getOrCreate(message.from_user)
    if message.chat.type == "private":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="➕ Добавить", url=f"https://t.me/{settings.BOT_USERNAME}?startgroup=new")
                ]
            ]
        )
        
        await message.answer(text="<b>Здрав будь!</b> Я вестник для игры в 🛖 <b>Поселения</b>.\nЧтоб в сходку свою меня позвать, <b>на знак ниже ткни:</b>", reply_markup=kb)
        log.debug(f"{message.chat.id} | Функция private_handler() выполнена")
        return




@router.my_chat_member()
async def bot_added_to_chat_event(event: types.ChatMemberUpdated):
    #* Приветствие при добавлении бота в группу
    chat = event.chat
    if event.new_chat_member.status in ["member", "administrator"]:
        log.debug(f"{chat.id} | Бот добавлен в группу {chat.title}")
        
        
        welcome_text = (
                f'🏰 <b>Добро пожаловать в игру "Поселения"!</b>\n\n'
                f"🛖 Для начала игры используйте команду /start\n"
            )
        
        if event.new_chat_member.status == "member":
            welcome_text += (
                "\n⚠️ Пожалуйста, <b>назначьте меня администратором</b> с правами на закрепление и удаление сообщений, <b>чтобы я мог полноценно функционировать!</b>\n"
            )
        
        
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="❓ Помощь",
                        switch_inline_query_current_chat="Помощь"
                    ),
                    InlineKeyboardButton(
                        text="🚶‍➡️ Осмотреть поселение",
                        switch_inline_query_current_chat="Этот город"
                    )
                ]
            ]
        )

        await event.answer(welcome_text, reply_markup=kb)
        log.debug(f"{event.chat.id} | Функция bot_added_to_chat_event() выполнена")
    if event.new_chat_member.status in ["left", "kicked"]:
        log.debug(f"{chat.id} | Бот удален из группы {chat.title}")

@router.message(or_f(CommandStart(), Command("town"), F.text.lower() == "этот город", F.text.lower() == "@mysettlementbot этот город"))
async def start_command(message: types.Message):
    #* Обработка команды /start
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)
    
    
    if not settler:
        log.error(f"Не удалось получить или создать поселенца для пользователя {message.from_user.id} в функции start_command()")
        await message.answer("❌ Беда приключилась, вести о тебе не сысканы. Погоди малость, опосля пытай снова.")
        return
    
    async with SessionLocal() as session:
        result = await session.execute(
            select(models.Settlement)
            .options(selectinload(models.Settlement.members), selectinload(models.Settlement.owner))
            .where(models.Settlement.id == settlement.id)
        )
        updated_settlement = result.scalars().first()
        if updated_settlement:
            settlement.members = updated_settlement.members
            settlement.owner = updated_settlement.owner
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="👤 Мой профиль", switch_inline_query_current_chat="Профиль")]])
    text = f"<b>{settlement.name}</b>\n👥{len(settlement.members)} 👑 <b>{settlement.owner.name or (f"User {settlement.owner.user_id}" if settlement.owner else "Отсутствует")}</b>"
    await message.answer(text, reply_markup=kb)
    log.debug(f"{message.chat.id} | Функция start_command() выполнена")

@router.message(or_f(Command("me"), F.text.lower() == "профиль", F.text.lower() == "@mysettlementbot профиль"))
async def me_command(message: types.Message):
    #* Обработка команды /me
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)

    async with SessionLocal() as session:
        user_settings = await core.settings_getOrCreate(user, session)
        craft_text = f"{settler.profession.emoji} {settler.profession.name}" if settler.profession else "❓ Без дела"
        can_choose, when = can_choose_craft(settler.last_profession_change)
        can_work, work_countdown = core.can_work_now(settler)
        
        kb = InlineKeyboardBuilder()
        buttons = []
        buttons.append(InlineKeyboardButton(text="🪭 Косметика", switch_inline_query_current_chat="Косметика"))
        buttons.append(InlineKeyboardButton(text="📦 Инвентарь", switch_inline_query_current_chat="Инвентарь"))
        buttons.append(InlineKeyboardButton(text="🕒 Лишняя мера", switch_inline_query_current_chat="Лишняя мера"))
        buttons.append(InlineKeyboardButton(text=f"{settler.profession.emoji} Трудиться", switch_inline_query_current_chat="Трудиться")) if settler.profession and can_work else None
        buttons.append(InlineKeyboardButton(text="💼 Выбрать ремесло", switch_inline_query_current_chat="Выбрать ремесло")) if can_choose else None
        kb.row(*buttons, width=2)
        
        
        if user_settings.compact_style:
            text = (
                f"👤 <b>{user.name}</b> — {craft_text}\n"
                f"💡 {settler.level} — {settler.emoji} <b>{settler.rank}</b>\n"
                f"(🗂 <b>{round(settler.exp)}/{round(settler.target_exp)}</b>) | "
                f"📄 {f'<b>{settler.quote}/{settler.target_quote}</b>' if not settler.quote_is_completed else f'{settler.target_quote}/{settler.target_quote}'} {'(⏳) ' if settler.overtime_is_toggled else ''}| "
                f"💰 <b>{round(settler.balance)}</b> ({'<b>' if settler.income != 0 else ''}{round(settler.income)}/день{'</b>' if settler.income != 0 else ''})\n"
                f"\n {(settler.profession.emoji + ' Трудиться можно через <b>' + work_countdown + '</b> ⚠️') if (settler.profession and not can_work) else ((settler.profession.emoji + ' <b>Можно трудиться</b> ✅') if settler.profession else '')} "
            )
        else:
            text = (
                f"👤 <b>{user.name}</b>\n"
                f"🛠 <b>Ремесло:</b> {craft_text}\n"
                f"💡 <b>Уровень:</b> {settler.level}\n"
                f"🗂 <b>Опыт:</b> {round(settler.exp)}/{round(settler.target_exp)}\n"
                f"🏷 <b>Ранг:</b> {settler.emoji} {settler.rank}\n"
                f"📄 <b>Мера:</b> {f'<b>{settler.quote}/{settler.target_quote}</b>' if not settler.quote_is_completed else f'{settler.target_quote}/{settler.target_quote}'} {'(⏳ Мера лишняя взята)' if settler.overtime_is_toggled else ''}\n"
                f"💰 <b>Баланс:</b> {round(settler.balance)} ({'<b>' if settler.income != 0 else ''}{round(settler.income)}/день{'</b>' if settler.income != 0 else ''})\n"
                f"\n {(settler.profession.emoji + ' Трудиться можно через <b>' + work_countdown + '</b> ⚠️') if (settler.profession and not can_work) else ((settler.profession.emoji + ' <b>Можно трудиться</b> ✅') if settler.profession else '')} "
            )
        
        await message.answer(text, reply_markup=kb.as_markup())
    log.debug(f"{message.chat.id} | Функция me_command() выполнена")

@router.message(or_f(Command("cosmetics"), F.text.lower() == "косметика", F.text.lower() == "@mysettlementbot косметика"))
async def cosmetics_command(message: types.Message):
    #* Обработка команды /cosmetics
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)
    
    if not settler:
        log.error(f"Не удалось получить или создать поселенца для пользователя {message.from_user.id} в функции cosmetics_command()")
        await message.answer("❌ Беда приключилась, вести о тебе не сысканы. Погоди малость, опосля пытай снова.")
        return

    text = f"🪭 <b>Доступная косметика</b>\n\n"
    text += f"🎭 <b>Текущий эмодзи:</b> {settler.emoji}\n"
    
    all_emojis = []
    if settler.rank_emoji_available:
        all_emojis.extend(settler.rank_emoji_available)
    if settler.special_emoji_available:
        all_emojis.extend(settler.special_emoji_available)
    
    all_emojis = list(dict.fromkeys(all_emojis))
    
    if not all_emojis:
        text += "\n❌ Нет доступных эмодзи"
        await message.answer(text=text)
        return
    
    # Кнопки для каждого эмодзи
    kb_buttons = []
    for i in range(0, len(all_emojis), 3):
        row = []
        for j in range(3):
            if i + j < len(all_emojis):
                emoji = all_emojis[i + j]
                row.append(InlineKeyboardButton(
                    text=f"{emoji} {'✅' if emoji == settler.emoji else ''}", 
                    callback_data=f"cosmetics_select_{emoji}"
                ))
        kb_buttons.append(row)
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await message.answer(text=text, reply_markup=kb)
    log.debug(f"{message.chat.id} | Функция cosmetics_command() выполнена")

@router.callback_query(F.data.startswith("cosmetics_select_"))
async def cosmetics_select(callback: types.CallbackQuery):
    #* Обработка выбора эмодзи
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)
    
    emoji = callback.data.split("_")[2]

    async with SessionLocal() as session:
        result = await session.execute(
            select(models.Settler).where(models.Settler.id == settler.id)
        )
        db_settler = result.scalars().first()
        if db_settler:
            db_settler.emoji = emoji
            await session.commit()
            await session.refresh(db_settler, ["user", "settlement"])
            log.debug(f"{callback.message.chat.id} | {user.id} | ✅ Эмодзи изменен: {emoji}")

    await callback.answer(text=f"🪭 Косметика применена: {emoji}")
    
    
    all_emojis = []
    if settler.rank_emoji_available:
        all_emojis.extend(settler.rank_emoji_available)
    if settler.special_emoji_available:
        all_emojis.extend(settler.special_emoji_available)
    
    all_emojis = list(dict.fromkeys(all_emojis))
    kb_buttons = []
    
    for i in range(0, len(all_emojis), 3):
        row = []
        for j in range(3):
            if i + j < len(all_emojis):
                emoji = all_emojis[i + j]
                row.append(InlineKeyboardButton(
                    text=f"{emoji} {'✅' if emoji == db_settler.emoji else ''}", 
                    callback_data=f"cosmetics_select_{emoji}"
                ))
        kb_buttons.append(row)
    
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons)
    await callback.message.edit_text(text=f"🪭 <b>Доступная косметика</b>\n\n🎭 <b>Текущий эмодзи:</b> {emoji}", reply_markup=kb)
    log.debug(f"{callback.message.chat.id} | Функция cosmetics_select() выполнена")

@router.message(or_f(Command("overtime"), F.text.lower() == "лишняя мера", F.text.lower() == "@mysettlementbot лишняя мера"))
async def overtime_command(message: types.Message):
    #* Обработка команды /overtime
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)
    
    reset_countdown = core.get_daily_reset_countdown()
    text = f"🕒 <b>Лишняя мера</b>\n\n"
    if settler.level < 2:
        text += f"ℹ️ Коль добра тебе мало, можешь <b>лишнюю меру</b> взять. С каждой лишней мерой работа тяжелеет, мудрости меньше наберёшь, но грошей столько же получишь. Коль <b>не поспеешь труд свершить</b> до нового дня (🕒 {reset_countdown}), на тебя <b>виру</b> наложат в 💰 <b>20</b>.\n\n"
    async with SessionLocal() as session:
        user_settings = await core.settings_getOrCreate(user, session)
        
        kb = InlineKeyboardMarkup(inline_keyboard=[])
        if settler.overtime_is_toggled and not settler.quote_is_completed:
            if user_settings.compact_style:
                text += f"🔘 {settler.overtime_count} (🕒 {core.get_daily_reset_countdown()}) | 📄 <b>{settler.quote}/{settler.target_quote}</b>"
            else:
                text += f"Состояние лишней меры: ⚪️ Деятельно\nСколько лишней меры взято: {settler.overtime_count} (🕒 {core.get_daily_reset_countdown()} до новой меры осталось)\n📄 Мера: <b>{settler.quote}/{settler.target_quote}</b>"
        elif not settler.overtime_is_toggled and not settler.quote_is_completed:
            text += f"⚠️ Лишнюю меру брать можно, токмо основную 📄 меру свершив!"
        else:
            if user_settings.compact_style:
                text += f"🔘 {settler.overtime_count}"
            else:
                text += f"Состояние лишней меры: 🔘 Неактивный\nСколько лишней меры взято: {settler.overtime_count}"
            kb.inline_keyboard.append([InlineKeyboardButton(text="🕒 Взять лишнюю меру", callback_data="overtime_take")])

    
    await message.answer(text, reply_markup=kb)
    log.debug(f"{message.chat.id} | Функция overtime_command() выполнена")

@router.callback_query(F.data == "overtime_take")
async def overtime_take(callback: types.CallbackQuery):
    #* Обработка кнопки "взять лишнюю меру"
    async with SessionLocal() as session:
        user = await core.user_getOrCreate(callback.from_user)
        settlement = await core.settlement_getOrCreate(callback.message.chat, user)
        settler = await core.settler_getOrCreate(user, settlement)

        await session.execute(
            update(models.Settler)
            .where(models.Settler.id == settler.id)
            .values(
                overtime_is_toggled=True,
                overtime_count=settler.overtime_count + 1,
                quote_is_completed=False,
                quote=0,
                target_quote=round((settler.level * 0.85 + 6) + (2 * (settler.overtime_count + 1)))
            )
        )
        
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 🔄 Лишняя мера взята: 0/{round((settler.level * 0.85 + 6) + (2 * (settler.overtime_count + 1)))}")
        await session.commit()
        
        reset_countdown = core.get_daily_reset_countdown()
        await callback.message.edit_text(f"⏳ <b>Мера лишняя взялась!</b>\nПора тебе осталась 🕒 <b>{reset_countdown}</b> чтоб новую меру исполнить!")
        log.debug(f"{callback.message.chat.id} | Функция overtime_take() выполнена")

@router.message(or_f(Command("inventory"), F.text.lower() == "инвентарь", F.text.lower() == "@mysettlementbot инвентарь"))
async def inventory_command(message: types.Message):
    #* Обработка команды /inventory
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)

    text = f"📦 <b>Инвентарь</b>\n\n"
    
    async with SessionLocal() as session:
        user_settings = await core.settings_getOrCreate(user, session)
        result = await session.execute(
            select(models.settler_resources.c.resource_id, models.settler_resources.c.quantity, models.Resource.name, models.Resource.emoji, models.Resource.category)
            .join(models.Resource, models.settler_resources.c.resource_id == models.Resource.id)
            .where(models.settler_resources.c.settler_id == settler.id)
        )
        resources_data = result.all()
        
        if not resources_data:
            text += "❌ Пусто"
            if settler.level < 2:
                text += "\n\nℹ️ Ресурсы могут добывать разные специалисты, а также их можно получить в награду за выполнение событий."
            await message.answer(text=text)
            return
        
        categories = {}
        for row in resources_data:
            resource_id, quantity, resource_name, resource_emoji, category = row
            if category not in categories:
                categories[category] = []
            if user_settings.compact_style:
                categories[category].append(f"{resource_emoji}: {quantity}")
            else:
                categories[category].append(f"{resource_emoji} {resource_name}: {quantity}")
        
        for category, items in categories.items():
            text += f"<b>{category}:</b>\n{' '.join(items)}\n\n"
    
    await message.answer(text=text)
    log.debug(f"{message.chat.id} | Функция inventory_command() выполнена")

# @router.message(or_f(Command("income"), F.text.lower() == "доход", F.text.lower() == "@mysettlementbot доход"))
# async def income_command(message: types.Message):
#     #* Обработка команды /income
#     user = await core.user_getOrCreate(message.from_user)
#     settlement = await core.settlement_getOrCreate(message.chat, user)
#     settler = await core.settler_getOrCreate(user, settlement)

#     #TODO: Перечисление источников дохода
#     log.debug(f"{message.chat.id} | Функция income_command() выполнена")


@router.message(or_f(Command("choose_craft"), F.text.lower() == "выбрать ремесло", F.text.lower() == "@mysettlementbot выбрать ремесло"))
async def choose_craft_command(message: types.Message):
    #* Обработка команды /craft
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)

    async with SessionLocal() as session:
        result = await session.execute(select(models.Profession))
        professions = result.scalars().all()
    
    if not professions:
        await message.answer('❌ Нет доступных ремесел. Обратитесь к <a href="https://t.me/megatocha">создателю.</a>')
        return
    
    can_choose, when = True, ""
    if settler.profession_id:
            can_choose, when = can_choose_craft(settler.last_profession_change)
    
    text = f"💼 <b>Выбор ремесла</b>\n{'⚠️ Сменить ремесло можно через <b>' + when + '</b>\n' if not can_choose and settler.profession else ''}\n"
    kb = InlineKeyboardBuilder()

    async with SessionLocal() as session:
        user_settings = await core.settings_getOrCreate(user, session)
    buttons = []
    for prof in professions:
        if settler.level >= prof.required_level:
            if user_settings.compact_style:
                text += f"{prof.emoji} <b>{prof.name}:</b> {prof.description}\n{'✅' if settler.profession_id == prof.id else '☑️'} (<b>{settler.level}/{prof.required_level}</b>💡)\n\n"
            else:
                text += f"{prof.emoji} <b>{prof.name}:</b> {prof.description}\n{'✅ <b>Выбрано</b>' if settler.profession_id == prof.id else '☑️ Доступно'} (Требуется уровень <b>{settler.level}/{prof.required_level}</b>💡)\n\n"
            buttons.append(InlineKeyboardButton(text=f"Выбрать {prof.emoji} {prof.name}", callback_data=f"select_craft:{prof.id}")) if settler.profession_id != prof.id and can_choose else None
        else:
            if user_settings.compact_style:
                text += f"{prof.emoji} {prof.name}: {prof.description}\n🔒 ({settler.level}/<b>{prof.required_level}</b>💡)\n\n"
            else:
                text += f"{prof.emoji} {prof.name}: {prof.description}\n🔒 Недоступно (Требуется уровень {settler.level}/<b>{prof.required_level}</b>💡)\n\n"
    
    kb.row(*buttons, width=2)
    await message.reply(text=text, reply_markup=kb.as_markup(), disable_notification=True)
    log.debug(f"{message.chat.id} | Функция choose_craft_command() выполнена")

@router.callback_query(F.data.startswith("select_craft:"))
async def select_craft_callback(callback: types.CallbackQuery):
    prof_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        user = await core.user_getOrCreate(callback.from_user)
        settlement = await core.settlement_getOrCreate(callback.message.chat, user)
        settler = await core.settler_getOrCreate(user, settlement)

        if callback.from_user.id != callback.message.reply_to_message.from_user.id:
            await callback.answer("❌ Не тронь чужой снасти!", True)
            return
        
        if settler.profession_id == prof_id:
            await callback.answer("❌ Ты уж сие ремесло избрал! Аль сменить хочешь, то другую избери.")
            return
        
        prof_result = await session.execute(select(models.Profession).where(models.Profession.id == prof_id))
        profession = prof_result.scalars().first()
        
        if not profession or settler.level < profession.required_level:
            await callback.answer(f"❌ Ремесло сие тебе не по плечу! ({settler.level}/<b>{profession.required_level}</b>)")
            return
        if settler.profession_id:
            can_choose, when = can_choose_craft(settler.last_profession_change)
            if not can_choose:
                await callback.answer(f"❌Недавно ты ремесло своё сменил, человече! Новое дело взять можно, как {when} придёт.", True)
        
        await session.execute(
            update(models.Settler)
            .where(models.Settler.id == settler.id)
            .values(profession_id=prof_id, last_profession_change=int(datetime.now().timestamp()))
        )
        await session.commit()
        
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{profession.emoji} Трудиться", switch_inline_query_current_chat="Трудиться")]])
        await callback.message.edit_text(f"✅ <b>{callback.from_user.full_name}</b> ремесло себе избрал: {profession.emoji} <b>{profession.name}!</b>", reply_markup=kb)
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💼 Выбрано ремесло: {profession.name}")
    log.debug(f"{callback.message.chat.id} | Функция select_craft_callback() выполнена")

@router.message(or_f(Command("craft"), F.text.lower() == "трудиться", F.text.lower() == "@mysettlementbot трудиться"))
async def craft_command(message: types.Message):
    #* Обработка команды /craft
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)
    
    if not settler.profession_id:
        await message.answer("❌ Ты ещё ремесла не избрал.", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💼 Выбрать ремесло", switch_inline_query_current_chat="Выбрать ремесло")]]))
        return
    
    can_work, work_countdown = core.can_work_now(settler)
    if not can_work:
        await message.answer(f"🗞 Труд уж свершён, добрый люд! Новое дело взять можно, как {work_countdown} пройдёт.")
        return
    
    can_start, error_msg = can_start_work(message.chat.id)
    if not can_start:
        await message.answer(f"{error_msg}")
        return
    
    
    if settler.profession.emoji == "🌻":  # 🌻 Землепашец
        start_work(message.chat.id)
        workflow_or_step = models.WorkflowWork.get_ploughman_harvesting().copy()
        
        user_key = f"{message.chat.id}_{user.user_id}"
        active_games[user_key] = workflow_or_step
        remaining_time = get_work_remaining_time(message.chat.id)
        text = f"🌻 <b>Поле для пахоты:</b>\nЖните 🌾/🥔/🍄‍🟫/🫐. Токмо не троньте саженцы 🌱 — они ещё сил набирают!\n\n⏰ <b>Пора вам осталась:</b> {remaining_time}с"
        
    elif settler.profession.emoji == "📔":  # 📔 Знахарь
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🪴 Сбор трав", callback_data="select_work:healer:herbs"), InlineKeyboardButton(text="🍵 Приготовление отвара", callback_data="select_work:healer:tea"), width=2)
        kb.adjust(1)
        await message.reply("Избери труд 📔 <b>Знахаря:</b>", reply_markup=kb.as_markup(), disable_notification=True)
        return
    
    elif settler.profession.emoji == "🐾": # 🐾 Ловчий
        kb = InlineKeyboardBuilder()
        kb.row(InlineKeyboardButton(text="🎣 Рыбалка", callback_data="select_work:catcher:fishing"), width=2)
        kb.adjust(1)
        await message.reply("Избери труд 🐾 <b>Ловчего:</b>", reply_markup=kb.as_markup(), disable_notification=True)
        return
    
    else:
        text = "❌ Ремесло твоё покуда без дела стоит. Жди вестей новых!"
        await message.answer(text)
        return
    
    kb = workflow_or_step.render_keyboard()
    await message.answer(text, reply_markup=kb)

    log.debug(f"{message.chat.id} | Функция craft_command() выполнена")

@router.callback_query(F.data.startswith("select_work:"))
async def work_selection_callback(callback: types.CallbackQuery):
    #* Выбор работы по ремеслу
    _, profession_key, work_key = callback.data.split(":")
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)

    if callback.from_user.id != callback.message.reply_to_message.from_user.id:
            await callback.answer("❌ Не тронь чужой снасти!", True)
            return

    if not settler.profession_id or settler.profession_id != 2:
        await callback.answer("Сие дело твоему ремеслу не по плечу.", True)
        return
    
    can_work, work_countdown = core.can_work_now(settler)
    if not can_work:
        await callback.answer(f"🗞 Труд уж свершён, добрый люд! Новое дело взять можно, как {work_countdown} пройдёт.")
        return
    
    can_start, error_msg = can_start_work(callback.message.chat.id)
    if not can_start:
        await callback.answer(f"{error_msg}")
        return

    user_key = f"{callback.message.chat.id}_{user.user_id}"

    if profession_key == "healer": # 📔 Знахарь
        if work_key == "herbs":
            start_work(callback.message.chat.id)
            step = models.WorkflowWork.get_healer_herb_gathering().copy()
            active_games[user_key] = step
            remaining_time = get_work_remaining_time(callback.message.chat.id)
            text = f"🪴 <b>Травозбор:</b>\nСобирай 🪴/🎋!\n⏰ Пора тебе осталась <b>3 мин</b>."
            kb = step.render_keyboard()
            await callback.message.edit_text(text, reply_markup=kb)
            await callback.answer("Начинаем сбор трав! 🪴")
            return
        elif work_key == "tea":
            async with SessionLocal() as session:
                bark_resource = await core.get_resource_by_emoji("🎋", session)
                
                settler_resources = await session.execute(
                    select(models.settler_resources).where(
                        models.settler_resources.c.settler_id == settler.id,
                        models.settler_resources.c.resource_id == bark_resource.id
                    )
                )
                settler_bark = settler_resources.first()
                if not settler_bark or settler_bark.quantity < 3:
                    await callback.answer("❌ Мало коры собрано (надобно 3 🎋).", True)
                    return
                await session.execute(
                    update(models.settler_resources)
                    .where(
                        models.settler_resources.c.settler_id == settler.id,
                        models.settler_resources.c.resource_id == bark_resource.id
                    )
                    .values(quantity=models.settler_resources.c.quantity -3)
                )
                await session.commit()

            start_work(callback.message.chat.id)
            workflow = models.WorkflowWork.get_tea_brewing_workflow().copy()
            active_games[user_key] = workflow
            remaining_time = get_work_remaining_time(callback.message.chat.id)
            text = f"🍵 <b>Приготовление отвара:</b>\nШаг <b>1/2:</b> Измельчение коры 🎋\n⏰ У вас есть <b>3 мин</b>."
            kb = workflow.render_keyboard()
            await callback.message.edit_text(text, reply_markup=kb)
            await callback.answer("Приступаем к приготовлению отвара! 🍵")
            return
        
    elif profession_key == "catcher": # 🐾 Ловчий
        if work_key == "fishing":
            start_work(callback.message.chat.id)
            step = models.WorkflowWork.get_catcher_fishing().copy()
            active_games[user_key] = step
            remaining_time = get_work_remaining_time(callback.message.chat.id)
            text = f"🎣 <b>Рыбалка:</b>\nЛови 🐟!\n⏰ Пора тебе осталась <b>3 мин</b>."
            kb = step.render_keyboard()
            await callback.message.edit_text(text, reply_markup=kb)
            await callback.answer("Начинаем рыбалку! 🎣")
            return
    else:
        await callback.answer("Неизвестный труд.", True)
        return

@router.callback_query(F.data.startswith("harvest:"))
async def harvest_callback(callback: types.CallbackQuery):
    #* Обработка callback-кнопок для шага сбора
    _, i, j = callback.data.split(":")
    
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)
    
    user_key = f"{callback.message.chat.id}_{user.user_id}"
    
    if not can_click_button(user_key):
        await callback.answer("⏳ Погоди миг единый меж трудами!")
        return
    
    remaining_time = get_work_remaining_time(callback.message.chat.id)
    if remaining_time <= 0:
        await callback.answer("⏰ Пора труда миновала! Дело отложено.", True)
        await callback.message.edit_text("⏰ Долго ты без дела стоял! Труд отложен.")
        return
    
    game = active_games.get(user_key)
    
    if not game:
        await callback.answer("❌ Дело не сыскано. Может, ты уж его свершил, али вовсе не твоё то дело?")
        return
    
    result = game.click(int(i), int(j))

    if result == "lose":
        text = f"{game.get_status_text()}"
        await callback.message.edit_text(text)
        await callback.answer(game.lose_text)
        async with SessionLocal() as session:
            await core.end_work(settler, callback.message.chat.id, session, settler.profession, rewards={}, mark_work_completed=True)
        active_games.pop(user_key, None)
        end_work(callback.message.chat.id)
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💀 Собирательство испорчено!")
        
    elif result == "win":
        text = f"{game.get_status_text()}"
        await callback.message.edit_text(text)
        await callback.answer(game.win_text)
        async with SessionLocal() as session:
            earned, exp_gained = await core.end_work(settler, callback.message.chat.id, session, settler.profession, 
                                        mark_work_completed=True)
            if earned or exp_gained > 0:
                await callback.message.edit_text(text + format_reward_text(earned, exp_gained))
        
        active_games.pop(user_key, None)
        end_work(callback.message.chat.id)
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💼 Труд завершён!")
        
    elif result == "continue":
        text = f"{game.get_status_text()}"
        kb = game.render_keyboard()
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer(game.continue_text)
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 🌾 Собрано...")
        
    elif result == "game_over":
        await callback.answer("Ход уже завершён!")
        return

    await callback.answer()
    log.debug(f"{callback.message.chat.id} | Функция harvest_callback() выполнена")

@router.callback_query(F.data.startswith("hit:"))
async def hitter_callback(callback: types.CallbackQuery):
    #* Обработка callback-кнопок для шага с попаданием
    _, position = callback.data.split(":")
    position = int(position)
    
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)
    
    user_key = f"{callback.message.chat.id}_{user.user_id}"
    
    if not can_click_button(user_key):
        await callback.answer("⏳ Погоди миг единый меж трудами!")
        return
    
    remaining_time = get_work_remaining_time(callback.message.chat.id)
    if remaining_time <= 0:
        await callback.answer("⏰ Пора труда миновала! Дело отложено.", True)
        await callback.message.edit_text("⏰ Долго ты без дела стоял! Труд отложен.")
        return
    
    workflow_or_step = active_games.get(user_key)
    
    if not workflow_or_step:
        await callback.answer("❌ Ход не сыскан. Может, ты его свершил, али вовсе не твой то ход?", True)
        return
    
    if hasattr(workflow_or_step, 'get_current_step'):
        workflow = workflow_or_step
        current_step = workflow.get_current_step()
        
        if not current_step or not hasattr(current_step, 'click'):
            await callback.answer("Неверный ход!")
            return
        
        old_field = current_step.field.copy() if hasattr(current_step, 'field') else None
        result = current_step.click(position)
        
        if result == "hit":
            text = f"{workflow.get_status_text()}"
            kb = workflow.render_keyboard()
            
            if old_field != current_step.field:
                await callback.message.edit_text(text, reply_markup=kb)
            else:
                log.debug(f"{callback.message.chat.id} | {settler.user_id} | 🎯 Попадание! Поле не изменилось")
            
            await callback.answer(current_step.hit_text)
            log.debug(f"{callback.message.chat.id} | {settler.user_id} | 🎯 Попадание! {current_step.score}/{current_step.rounds}")
            
        elif result == "miss":
            text = f"{workflow.get_status_text()}"
            await callback.message.edit_text(text)
            await callback.answer(current_step.miss_text)
            workflow.fail_workflow()
            active_games.pop(user_key, None)
            end_work(callback.message.chat.id)
            log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💀 Промах! Труд провален!")
            
        elif result == "win": # Работа завершена
            if workflow.next_step():
                # Workflow завершен
                text = f"{workflow.get_status_text()}"
                await callback.message.edit_text(text)
                await callback.answer(workflow.complete_text)
                
                # Выдаем награду
                async with SessionLocal() as session:
                    tea_resource = await core.get_resource_by_emoji("🍵", session)
                    earned, exp_gained = await core.end_work(settler, callback.message.chat.id, session, settler.profession, 
                                                rewards={tea_resource.id: 1}, mark_work_completed=True)
                    if earned or exp_gained > 0:
                        await callback.message.edit_text(text + format_reward_text(earned, exp_gained))
                    
                active_games.pop(user_key, None)
                end_work(callback.message.chat.id)
                log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💼 Труд завершён!")
            else: # Следующий шаг
                text = f"{workflow.get_status_text()}"
                kb = workflow.render_keyboard()
                await callback.message.edit_text(text, reply_markup=kb)
                await callback.answer(current_step.win_text)
                log.debug(f"{callback.message.chat.id} | {settler.user_id} | ➡️ Переход к следующему шагу")
                
        elif result == "game_over":
            await callback.answer("Ход уже завершён!")
            return
    
    else:
        # Поддержка одиночных мини-игр (например, 🎣 Catch), использующих callback "hit:idx"
        game = workflow_or_step
        if hasattr(game, 'click') and hasattr(game, 'render_keyboard'):
            result = game.click(position)
            if result == "hit":
                text = f"{game.get_status_text()}"
                kb = game.render_keyboard()
                await callback.message.edit_text(text, reply_markup=kb)
                await callback.answer(getattr(game, 'hit_text', "✅ Попадание!"))
                log.debug(f"{callback.message.chat.id} | {settler.user_id} | 🎯 Попадание!")
            elif result == "miss":
                text = f"{game.get_status_text()}"
                await callback.message.edit_text(text)
                await callback.answer(getattr(game, 'miss_text', "💥 Промах!"))
                async with SessionLocal() as session:
                    await core.end_work(settler, callback.message.chat.id, session, settler.profession, rewards={}, mark_work_completed=True)
                active_games.pop(user_key, None)
                end_work(callback.message.chat.id)
                log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💀 Игра проиграна!")
            elif result == "win":
                text = f"{game.get_status_text()}"
                await callback.message.edit_text(text)
                await callback.answer(getattr(game, 'win_text', "🏆 Победа!"))
                async with SessionLocal() as session:
                    earned, exp_gained = await core.end_work(settler, callback.message.chat.id, session, settler.profession, mark_work_completed=True)
                    if earned or exp_gained > 0:
                        await callback.message.edit_text(text + format_reward_text(earned, exp_gained))
                active_games.pop(user_key, None)
                end_work(callback.message.chat.id)
                log.debug(f"{callback.message.chat.id} | {settler.user_id} | 🐟 Ловля завершена!")
            elif result == "game_over":
                await callback.answer("Ход уже завершён!")
                return
            else:
                await callback.answer("Неверный ход!")
                return
        else:
            await callback.answer("Неверный ход!")
            return
    
    log.debug(f"{callback.message.chat.id} | Функция hitter_callback() выполнена")

@router.callback_query(F.data.startswith("timer:"))
async def timer_callback(callback: types.CallbackQuery):
    #* Обработка callback-кнопок для таймерных шагов
    _, action = callback.data.split(":")
    
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)
    
    user_key = f"{callback.message.chat.id}_{user.user_id}"
    
    if not can_click_button(user_key):
        await callback.answer("⏳ Погоди миг единый меж трудами!")
        return
    
    # Проверяем таймаут работы
    remaining_time = get_work_remaining_time(callback.message.chat.id)
    if remaining_time <= 0:
        await callback.answer("⏰ Пора труда миновала! Дело отложено.", True)
        await callback.message.edit_text("⏰ Долго ты без дела стоял! Труд отложен.")
        return
    
    workflow = active_games.get(user_key)
    
    if not workflow:
        await callback.answer("❌ Ход не сыскан. Может, ты его свершил, али вовсе не твой то ход?", True)
        return
    
    current_step = workflow.get_current_step()
    if not current_step or not hasattr(current_step, 'click'):
        await callback.answer("Неверный ход!")
        return
    
    result = current_step.click(action)
    
    if result == "started":
        text = f"{workflow.get_status_text()}"
        kb = workflow.render_keyboard()
        await callback.message.edit_text(text, reply_markup=kb)
        await callback.answer(current_step.start_text)
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | ⏰ Таймер запущен!")
        
    elif result == "completed":
        if workflow.next_step(): # Работа завершена
            text = f"{workflow.get_status_text()}"
            await callback.message.edit_text(text)
            await callback.answer(workflow.complete_text)
            
            async with SessionLocal() as session:
                tea_resource = await core.get_resource_by_emoji("🍵", session)
                earned, exp_gained = await core.end_work(settler, callback.message.chat.id, session, settler.profession, 
                                            rewards={tea_resource.id: 1}, mark_work_completed=True)
                if earned or exp_gained > 0:
                    await callback.message.edit_text(text + format_reward_text(earned, exp_gained))
                
            active_games.pop(user_key, None)
            end_work(callback.message.chat.id)
            log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💼 Труд завершён!")
        else: # Следующий шаг
            text = f"{workflow.get_status_text()}"
            kb = workflow.render_keyboard()
            await callback.message.edit_text(text, reply_markup=kb)
            await callback.answer(current_step.complete_text)
            log.debug(f"{callback.message.chat.id} | {settler.user_id} | ➡️ Переход к следующему шагу")
            
    elif result == "waiting":
        remaining = current_step.get_remaining_time()
        await callback.answer(f"⏳ Осталось: {remaining}с")
        
    elif result == "invalid":
        await callback.answer("Неверное действие!")
        return
    
    log.debug(f"{callback.message.chat.id} | Функция timer_callback() выполнена")


@router.message(or_f(Command("settings"), F.text.lower() == "настройки", F.text.lower() == "@mysettlementbot настройки"))
async def settings_command(message: types.Message):
    #* Обработка команды /settings
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat, user)
    settler = await core.settler_getOrCreate(user, settlement)

    async with SessionLocal() as session:
        user_settings = await core.settings_getOrCreate(user, session)

        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🎩 Стиль: {'🤏' if user_settings.compact_style else '🤲'}", callback_data="settings:messages_style")],
        ])
        
        text = f"⚙️ <b>Настройки</b>"
        text += f"\n🎩 Стиль сообщений: <b>{'🤏 Компактный' if user_settings.compact_style else '🤲 Развёрнутый'}</b>"
        text += "\n\nℹ️ Настройки сохраняются для каждого пользователя отдельно."
        
        await message.reply(text=text, reply_markup=kb, disable_notification=True)
        log.debug(f"{message.chat.id} | Функция settings_command() выполнена")

@router.callback_query(F.data.startswith("settings:"))
async def settings_callback(callback: types.CallbackQuery):
    #* Обработка callback-кнопок настроек
    user = await core.user_getOrCreate(callback.from_user)
    
    if callback.from_user.id != callback.message.reply_to_message.from_user.id:
        await callback.answer("❌ Не тронь чужой снасти!", True)
        return
    
    action = callback.data.split(":", 1)[1]
    
    async with SessionLocal() as session:
        user_settings = await core.settings_getOrCreate(user, session)
        
        if action == "messages_style":
            user_settings.compact_style = not user_settings.compact_style
            await session.commit()
            
            new_style = "🤏 Компактный" if user_settings.compact_style else "🤲 Развёрнутый"
            await callback.answer(f"🎩 Стиль сообщений изменён на {new_style}")
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🎩 Стиль: {'🤏' if user_settings.compact_style else '🤲'}", callback_data="settings:messages_style")],
        ])
        
        text = f"⚙️ <b>Настройки</b>"
        text += f"\n🎩 Стиль сообщений: <b>{'🤏 Компактный' if user_settings.compact_style else '🤲 Развёрнутый'}</b>"
        text += "\n\nℹ️ Настройки сохраняются для каждого пользователя отдельно."
        
        await callback.message.edit_text(text=text, reply_markup=kb)
        log.debug(f"{callback.message.chat.id} | Функция settings_callback() выполнена")


@router.message(or_f(Command("help"), F.text.lower() == "Помощь", F.text.lower() == "@mysettlementbot помощь"))
async def help_command(message: types.Message):
    help_text = (
        "<b>❓ Помощь</b>\n\n"
        'Добро пожаловать в игру <b>Моё поселение</b>! Это текстовая RPG, где вы — часть поселения.\n\n'
        "<b>Основные команды:</b>\n"
        "/start - Начать игру или перезапустить её\n"
        "/help - Показать это сообщение помощи\n"
        "/me - Показать профиль вашего поселенца\n"
        "/craft - Выполнить работу для получения ресурсов и опыта\n"
        "/inventory - Показать ваш инвентарь с ресурсами и предметами\n"
        "Если у вас возникнут вопросы или проблемы, не стесняйтесь обращаться за помощью!"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)




@router.message(or_f(F.chat.type == "supergroup", F.chat.type == "group"))
async def quote_handler(message: types.Message):
    #* Обработка сообщений для меры
    async with SessionLocal() as session:
        result = await session.execute(
            select(models.Settlement).where(models.Settlement.chat_id == message.chat.id)
        )
        settlement = result.scalars().first()
        
        if not settlement:
            return
            
        user = await core.user_getOrCreate(message.from_user)
        settler = await core.settler_getOrCreate(user, settlement)
        
        if not settler:
            log.error(f"Не удалось получить или создать поселенца для пользователя {message.from_user.id} во время quote_handler()")
            return
            
        try:
            if await core.is_meaningful(message.text) and not settler.quote_is_completed:
                await core.update_quote(settler, settlement, session, 1)
                return
        except Exception as e:
            log.error(f"Ошибка в функции quote_handler(): {e}")
            return