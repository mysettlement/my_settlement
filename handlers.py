from aiogram import Router, types, F, Bot
from aiogram.filters import Command, CommandStart, or_f
from aiogram.types import InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

import logging
from datetime import datetime

from config import setup_logging, settings
from db import SessionLocal
import core
from gamer import Workflow, Harvesting, Hitting, Catch, Alternation
import models
from mfunc import active_games
import mfunc

bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, disable_notification=True, link_preview_is_disabled=True)
    )
router = Router()
log = setup_logging(logging.getLogger(__name__))



@router.message(or_f(Command("my_id"), F.text.lower() == "мой айди", F.text.lower() == "@mysettlementbot мой айди"))
async def my_id_command(message: types.Message):
    #* Обработка команды /my_id
    user = await core.user_getOrCreate(message.from_user)
    compact_style = user.compact_style
    if compact_style:
        text = (
            f"👤 <b>{user.name}</b>\n"
            f"🆔 <code>{user.id}</code>\n"
            f"💬 <code>{user.telegram_id}</code>\n"
        )
    else:
        text = (
            f"👤 <b>{user.name}</b>\n"
            f"🆔 Internal: <code>{user.id}</code>\n"
            f"💬 Telegram: <code>{user.telegram_id}</code>\n"
        )
    await message.answer(text)

@router.message(or_f(Command("me"), F.text.lower() == "профиль", F.text.lower() == "@mysettlementbot профиль", F.text.lower() == "my profile", F.text.lower() == "@mysettlementbot my profile"))
async def me_command(message: types.Message):
    #* Обработка команды /me
    user = await core.user_getOrCreate(message.from_user)

    compact_style = user.compact_style
    kb = InlineKeyboardBuilder()
    buttons = []

    if message.chat.type == "supergroup" or message.chat.type == "group":
        settlement = await core.settlement_getOrCreate(message.chat)
        settler = await core.settler_getOrCreate(user, settlement)
        craft_text = f"{settler.profession.emoji} {settler.profession.name}" if settler.profession else "❓ Без дела"
        can_choose, when = mfunc.can_choose_craft(settler.last_profession_change)
        can_work, work_countdown = core.can_work_now(settler)
        
        if compact_style:
            text = (
                f"👤 <b>{user.name}</b> — {craft_text}\n"
                f"💡 {settler.level} — {settler.emoji} <b>{settler.rank}</b>\n"
                f"🗂 <b>{round(settler.exp)}/{round(settler.target_exp)}</b> | "
                f"📄 {f'<b>{settler.quote}/{settler.target_quote}</b>' if not settler.quote_is_completed else f'{settler.target_quote}/{settler.target_quote}'} {'(⏳) ' if settler.overtime_is_toggled else ''}| "
                f"💰 <b>{round(settler.balance)}</b> ({'<b>' if settler.income != 0 else ''}{round(settler.income)}/день{'</b>' if settler.income != 0 else ''})\n"
                f"\n{(settler.profession.emoji + ' Трудиться можно через <b>' + work_countdown + '</b> ⚠️') if (settler.profession and not can_work) else ((settler.profession.emoji + ' <b>Можно трудиться</b> ✅') if settler.profession else '')}"
            )

            buttons.append(InlineKeyboardButton(text="🪭", switch_inline_query_current_chat="Косметика"))
            buttons.append(InlineKeyboardButton(text="📦", switch_inline_query_current_chat="Инвентарь"))
            buttons.append(InlineKeyboardButton(text="🕒", switch_inline_query_current_chat="Лишняя мера"))
            buttons.append(InlineKeyboardButton(text=f"{settler.profession.emoji}", switch_inline_query_current_chat="Трудиться")) if settler.profession and can_work else None
            buttons.append(InlineKeyboardButton(text="💼", switch_inline_query_current_chat="Выбрать ремесло")) if can_choose else None
            
        else:
            text = (
                f"👤 <b>{user.name}</b>\n"
                f"🛠 <b>Ремесло:</b> {craft_text}\n"
                f"💡 <b>Уровень:</b> {settler.level}\n"
                f"🗂 <b>Опыт:</b> {round(settler.exp)}/{round(settler.target_exp)}\n"
                f"🏷 <b>Ранг:</b> {settler.emoji} {settler.rank}\n"
                f"📄 <b>Мера:</b> {f'<b>{settler.quote}/{settler.target_quote}</b>' if not settler.quote_is_completed else f'{settler.target_quote}/{settler.target_quote}'} {'(⏳ Лишняя мера взята)' if settler.overtime_is_toggled else ''}\n"
                f"💰 <b>Баланс:</b> {round(settler.balance)} ({'<b>' if settler.income != 0 else ''}{round(settler.income)}/день{'</b>' if settler.income != 0 else ''})\n"
                f"\n {(settler.profession.emoji + ' Трудиться можно через <b>' + work_countdown + '</b> ⚠️') if (settler.profession and not can_work) else ((settler.profession.emoji + ' <b>Можно трудиться</b> ✅') if settler.profession else '')} "
            )

            buttons.append(InlineKeyboardButton(text="🪭 Косметика", switch_inline_query_current_chat="Косметика"))
            buttons.append(InlineKeyboardButton(text="📦 Инвентарь", switch_inline_query_current_chat="Инвентарь"))
            buttons.append(InlineKeyboardButton(text="🕒 Лишняя мера", switch_inline_query_current_chat="Лишняя мера"))
            buttons.append(InlineKeyboardButton(text=f"{settler.profession.emoji} Трудиться", switch_inline_query_current_chat="Трудиться")) if settler.profession and can_work else None
            buttons.append(InlineKeyboardButton(text="💼 Выбрать ремесло", switch_inline_query_current_chat="Выбрать ремесло")) if can_choose else None
        
        kb.row(*buttons, width=2)
        await message.answer(text, reply_markup=kb.as_markup())

    elif message.chat.type == "private":
        if compact_style:
            text = (
                f"👤 <b>{user.name}</b>\n"
                f"🆔 <code>{user.id}</code>\n"
                f"💬 <code>{user.telegram_id}</code>\n"
            )
        else:
            text = (
                f"👤 <b>{user.name}</b>\n"
                f"🆔 Internal: <code>{user.id}</code>\n"
                f"💬 Telegram: <code>{user.telegram_id}</code>\n"
            )
        await message.answer(text)


@router.message(or_f(Command("settings"), F.text.lower() == "настройки", F.text.lower() == "@mysettlementbot настройки", F.text.lower() == "settings", F.text.lower() == "@mysettlementbot settings"))
async def settings_command(message: types.Message):
    #* Обработка команды /settings
    user = await core.user_getOrCreate(message.from_user)
    kb = InlineKeyboardBuilder()
    buttons = []

    compact_style = user.compact_style
    show_hints = user.show_hints
    #TODO: XXX = user.XXX

    buttons.append(InlineKeyboardButton(text=f"{"🎩" if compact_style else '🎩 Стиль'}: {'🤏' if compact_style else '🤲'}", callback_data="settings:compact_style"))
    buttons.append(InlineKeyboardButton(text=f"{"ℹ️" if compact_style else 'ℹ️ Подсказки'}: {'✅' if show_hints else '❌'}", callback_data="settings:show_hints"))
    kb.row(*buttons, width=2)
    
    text = f"⚙️ <b>Настройки</b>"
    text += f"\n🎩 Стиль сообщений: <b>{'🤏 Компактный' if compact_style else '🤲 Развёрнутый'}</b>"
    text += f"\nℹ️ Подсказки: <b>{'✅ Включены' if show_hints else '❌ Выключены'}</b>"
    #TODO: text += f"\n"
    text += "\n\nℹ️ Настройки сохраняются для каждого пользователя отдельно." if user.show_hints else ""
    
    await message.reply(text=text, reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data.startswith("settings:"))
async def settings_callback(callback: types.CallbackQuery):
    #* Обработка callback-кнопок настроек
    if callback.from_user.id != callback.message.reply_to_message.from_user.id:
        await callback.answer("❌ Не тронь чужой снасти!", True)
        return
    
    action = callback.data.split(":", 1)[1]
    kb = InlineKeyboardBuilder()
    buttons = []
    
    async with SessionLocal() as session:
        result = await session.execute(
            select(models.User).where(models.User.telegram_id == callback.from_user.id)
        )
        user = result.scalars().first()
        
        if not user:
            await callback.answer("❌ Пользователь не найден", True)
            return
        
        compact_style = user.compact_style
        show_hints = user.show_hints
        
        if action == "compact_style":
            user.compact_style = not user.compact_style
            await session.commit()
            compact_style = user.compact_style
            log.debug(f"{user.telegram_id} | 🎩 compact_style > {compact_style}")
            await callback.answer(f"🎩 Стиль сообщений > {"🤏 Компактный" if compact_style else "🤲 Развёрнутый"}")

        elif action == "show_hints":
            user.show_hints = not user.show_hints
            await session.commit()
            show_hints = user.show_hints
            log.debug(f"{user.telegram_id} | ℹ️ show_hints > {show_hints}")
            await callback.answer(f"ℹ️ Подсказки > {'✅ Включены' if show_hints else '❌ Выключены'}")
        
        #TODO: if action == "XXX":
        
    buttons.append(InlineKeyboardButton(text=f"{"🎩" if compact_style else '🎩 Стиль'}: {'🤏' if compact_style else '🤲'}", callback_data="settings:compact_style"))
    buttons.append(InlineKeyboardButton(text=f"{"ℹ️" if compact_style else 'ℹ️ Подсказки'}: {'✅' if show_hints else '❌'}", callback_data="settings:show_hints"))
    
    text = f"⚙️ <b>Настройки</b>"
    text += f"\n🎩 Стиль сообщений: <b>{"🤏 Компактный" if compact_style else "🤲 Развёрнутый"}</b>"
    text += f"\nℹ️ Подсказки: <b>{'✅ Включены' if show_hints else '❌ Выключены'}</b>"
    #TODO: text += f"\n"
    text += "\n\nℹ️ Настройки сохраняются для каждого пользователя отдельно." if user.show_hints else ""

    kb.row(*buttons, width=2)
    try:
        await callback.message.edit_text(text=text, reply_markup=kb.as_markup())
    except Exception as e:
        await callback.message.edit_reply_markup(reply_markup=kb.as_markup())

@router.message(or_f(Command("help"), F.text.lower() == "помощь", F.text.lower() == "@mysettlementbot помощь", F.text.lower() == "help", F.text.lower() == "@mysettlementbot help"))
async def help_command(message: types.Message):
    help_text = (
        "🛖 <b>Моё Поселение!</b> — текстовая MMORPG о жизни общины.\n"
        "Ты выбираешь ремесло, трудишься в мини-играх и развиваешь поселенца.\n\n"
        "▶️ <b>Как играть</b>\n"
        "• /start — начать и осмотреть поселение\n"
        "• /me — профиль и действия\n"
        "• /choose_craft — выбрать ремесло\n"
        "• /craft — начать работу\n\n"
        '<a href="https://mysettlement.github.io/">📚 Полные гайды</a>'
    )
    await message.answer(help_text)


@router.message(F.chat.type == "private")
async def private_handler(message: types.Message):
    #* Обработка личных сообщений
    kb = InlineKeyboardBuilder()
    buttons = []
    buttons.append(InlineKeyboardButton(text="➕ Добавить", url=f"https://t.me/{settings.BOT_USERNAME}?startgroup=new"))
    kb.row(*buttons)
    
    await message.answer(text="<b>Здрав будь!</b> Я вестник для игры в 🛖 <b>Поселения</b>.\nЧтоб в сходку свою меня позвать, <b>на знак ниже ткни:</b>", reply_markup=kb.as_markup())



@router.my_chat_member()
async def bot_added_to_chat_event(event: types.ChatMemberUpdated):
    #* Приветствие при добавлении бота в группу
    chat = event.chat
    if event.new_chat_member.status in ["member", "administrator"]:
        log.debug(f"{chat.id} | Бот добавлен в группу {chat.title}")
        
        
        welcome_text = (
                '🏰 <b>Добро пожаловать в игру "Поселения"!</b>\n\n',
                "🛖 Для начала игры используйте команду /start"
            )
        
        if event.new_chat_member.status == "member":
            welcome_text += (
                "\n\n⚠️ Пожалуйста, <b>назначьте меня администратором</b> с правами на закрепление и удаление сообщений, <b>чтобы я мог полноценно функционировать!</b>\n"
            )
        
        
        kb = InlineKeyboardBuilder()
        buttons = []
        buttons.append(InlineKeyboardButton(text="❓ Помощь", switch_inline_query_current_chat="Помощь"))
        buttons.append(InlineKeyboardButton(text="🚶‍➡️ Осмотреть поселение", switch_inline_query_current_chat="Осмотреть город"))
        kb.row(*buttons)

        await event.answer(welcome_text, reply_markup=kb.as_markup())
    if event.new_chat_member.status in ["left", "kicked"]:
        log.debug(f"{chat.id} | Бот удален из группы {chat.title}")


@router.message(or_f(CommandStart(), Command("town"), F.text.lower() == "осмотреть город", F.text.lower() == "@mysettlementbot осмотреть город", F.text.lower() == "town", F.text.lower() == "@mysettlementbot town"))
async def start_command(message: types.Message):
    #* Обработка команды /start
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
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
    
    kb = InlineKeyboardBuilder()
    buttons = []
    buttons.append(InlineKeyboardButton(text="👤 Профиль", switch_inline_query_current_chat="Профиль"))
    kb.row(*buttons, width=2)

    text = (
        f"<b>{settlement.name}</b>\n"
        f"👥{len(settlement.members)} 👑 <b>{settlement.owner.name or (f"User {settlement.owner.telegram_id}" if settlement.owner else "Отсутствует")}</b>"
    )
    await message.answer(text, reply_markup=kb.as_markup())


@router.message(or_f(Command("cosmetics"), F.text.lower() == "косметика", F.text.lower() == "@mysettlementbot косметика", F.text.lower() == "cosmetics", F.text.lower() == "@mysettlementbot cosmetics"))
async def cosmetics_command(message: types.Message):
    #* Обработка команды /cosmetics
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)
    
    if not settler:
        log.error(f"Не удалось получить или создать поселенца для пользователя {message.from_user.id} в функции cosmetics_command()")
        await message.answer("❌ Беда приключилась, вести о тебе не сысканы. Погоди малость, опосля пытай снова.")
        return

    text = f"🪭 <b>Доступная косметика</b>\n\n🎭 <b>Текущий эмодзи</b>: {settler.emoji}"
    
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
    
    buttons = []
    for i in range(0, len(all_emojis), 3):
        for j in range(3):
            if i + j < len(all_emojis):
                emoji = all_emojis[i + j]
                buttons.append(InlineKeyboardButton(text=f"{emoji}{' ✅' if emoji == settler.emoji else ''}", callback_data=f"cosmetics_select_{emoji}"))
    
    kb = InlineKeyboardBuilder().row(*buttons)
    await message.answer(text=text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("cosmetics_select_"))
async def cosmetics_select(callback: types.CallbackQuery):
    #* Обработка выбора эмодзи
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat)
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
    if db_settler.rank_emoji_available:
        all_emojis.extend(db_settler.rank_emoji_available)
    if db_settler.special_emoji_available:
        all_emojis.extend(db_settler.special_emoji_available)
    
    all_emojis = list(dict.fromkeys(all_emojis))
    buttons = []
    for i in range(0, len(all_emojis), 3):
        for j in range(3):
            if i + j < len(all_emojis):
                emoji_btn = all_emojis[i + j]
                buttons.append(InlineKeyboardButton(
                    text=f"{emoji_btn}{' ✅' if emoji_btn == db_settler.emoji else ''}", 
                    callback_data=f"cosmetics_select_{emoji_btn}"
                ))
    
    kb = InlineKeyboardBuilder().row(*buttons).as_markup()
    await callback.message.edit_text(text=f"🪭 <b>Доступная косметика</b>\n\n🎭 <b>Текущий эмодзи</b>: {db_settler.emoji}", reply_markup=kb)


@router.message(or_f(Command("overtime"), F.text.lower() == "лишняя мера", F.text.lower() == "@mysettlementbot лишняя мера", F.text.lower() == "overtime", F.text.lower() == "@mysettlementbot overtime"))
async def overtime_command(message: types.Message):
    #* Обработка команды /overtime
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)
    
    daily_reset_countdown = mfunc.get_daily_reset_countdown()
    compact_style = user.compact_style
    overtime_count=settler.overtime_count
    quote = settler.quote
    target_quote = settler.target_quote
    buttons = []
    kb = InlineKeyboardBuilder()

    text = f"🕒 <b>Лишняя мера</b>\n"
    text += f"ℹ️ Коль добра тебе мало, можешь <b>лишнюю меру</b> взять. С каждой лишней мерой работа тяжелеет, мудрости меньше наберёшь, но грошей столько же получишь. Коль <b>не поспеешь труд свершить</b> до нового дня (🕒 {daily_reset_countdown}), на тебя <b>виру</b> наложат в 💰 <b>20</b>.\n\n" if settler.level < 2 and user.show_hints == True else ""
    if settler.overtime_is_toggled and not settler.quote_is_completed:
        if compact_style:
            text += f"🔘 {overtime_count} (🕒 {daily_reset_countdown}) | 📄 <b>{quote}/{target_quote}</b>"
        else:
            text += f"Состояние лишней меры: ⚪️ <b>Активна</b>\nСколько лишней меры взято: {overtime_count} (🕒 <b>{daily_reset_countdown}</b>осталось до новой меры)\n📄 Мера: <b>{quote}/{target_quote}</b>"
    elif not settler.overtime_is_toggled and not settler.quote_is_completed:
        text += "⚠️ Лишнюю меру брать можно, токмо основную 📄 меру свершив!"
    else:
        if compact_style:
            text += f"🔘 {overtime_count}"
        else:
            text += f"Состояние лишней меры: 🔘 <b>Неактивна</b>\nСколько лишней меры взято: {overtime_count}"
        buttons.append(InlineKeyboardButton(text="🕒 Взять лишнюю меру", callback_data="overtime_take"))

    kb.row(*buttons)
    await message.answer(text, reply_markup=kb.as_markup())


@router.callback_query(F.data == "overtime_take")
async def overtime_take(callback: types.CallbackQuery):
    #* Обработка кнопки "взять лишнюю меру"
    async with SessionLocal() as session:
        user = await core.user_getOrCreate(callback.from_user)
        settlement = await core.settlement_getOrCreate(callback.message.chat)
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
        
        reset_countdown = mfunc.get_daily_reset_countdown()
        await callback.message.edit_text(f"⏳ <b>Мера лишняя взялась!</b>\nПора тебе осталась 🕒 <b>{reset_countdown}</b> чтоб новую меру исполнить!")


@router.message(or_f(Command("inventory"), F.text.lower() == "инвентарь", F.text.lower() == "@mysettlementbot инвентарь", F.text.lower() == "inventory", F.text.lower() == "@mysettlementbot inventory"))
async def inventory_command(message: types.Message):
    #* Обработка команды /inventory
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    text = f"📦 <b>Инвентарь</b>\n\n"
    
    async with SessionLocal() as session:
        compact_style = user.compact_style
        result = await session.execute(
            select(models.settler_resources.c.resource_id, models.settler_resources.c.quantity, models.Resource.name, models.Resource.emoji, models.Resource.category)
            .join(models.Resource, models.settler_resources.c.resource_id == models.Resource.id)
            .where(models.settler_resources.c.settler_id == settler.id)
        )
        resources_data = result.all()
        
        if not resources_data:
            text += "❌ Пусто"
            if settler.level < 2 and user.show_hints == True:
                text += "\n\nℹ️ Ресурсы могут добывать разные специалисты, а также их можно получить в награду за выполнение событий."
            await message.answer(text=text)
            return
        
        categories = {}
        for row in resources_data:
            resource_id, quantity, resource_name, resource_emoji, category = row
            if category not in categories:
                categories[category] = []
            if compact_style:
                categories[category].append(f"{resource_emoji}: {quantity}")
            else:
                categories[category].append(f"{resource_emoji} {resource_name}: {quantity}")
        
        for category, items in categories.items():
            text += f"<b>{category}:</b>\n{' '.join(items)}\n\n"
    
    await message.answer(text=text)


@router.message(or_f(Command("choose_craft"), F.text.lower() == "выбрать ремесло", F.text.lower() == "@mysettlementbot выбрать ремесло", F.text.lower() == "choose craft", F.text.lower() == "@mysettlementbot choose craft"))
async def choose_craft_command(message: types.Message):
    #* Обработка команды /craft
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    async with SessionLocal() as session:
        result = await session.execute(select(models.Profession))
        professions = result.scalars().all()
    
    if not professions:
        await message.answer('❌ Нет доступных ремесел. Обратитесь к <a href="https://t.me/megatocha">создателю.</a>')
        return
    
    can_choose, when = True, ""
    if settler.profession_id:
            can_choose, when = mfunc.can_choose_craft(settler.last_profession_change)
    
    text = f"💼 <b>Выбор ремесла</b>\n{'⚠️ Сменить ремесло можно через <b>' + when + '</b>\n' if not can_choose and settler.profession else ''}\n"
    kb = InlineKeyboardBuilder()

    async with SessionLocal() as session:
        compact_style = user.compact_style
    buttons = []
    for prof in professions:
        if settler.level >= prof.required_level:
            if compact_style:
                text += f"{prof.emoji} <b>{prof.name}:</b> {prof.description}\n{'✅' if settler.profession_id == prof.id else '☑️'} <b>{settler.level}/{prof.required_level}</b>💡\n\n"
            else:
                text += f"{prof.emoji} <b>{prof.name}:</b> {prof.description}\n{'✅ <b>Выбрано</b>' if settler.profession_id == prof.id else '☑️ Доступно'} (Требуется уровень <b>{settler.level}/{prof.required_level}</b>💡)\n\n"
            buttons.append(InlineKeyboardButton(text=f"{prof.emoji} {prof.name}", callback_data=f"select_craft:{prof.id}")) if settler.profession_id != prof.id and can_choose else None
        else:
            if compact_style:
                text += f"{prof.emoji} {prof.name}: {prof.description}\n🔒 {settler.level}/<b>{prof.required_level}</b>💡\n\n"
            else:
                text += f"{prof.emoji} {prof.name}: {prof.description}\n🔒 Недоступно (Требуется уровень {settler.level}/<b>{prof.required_level}</b>💡)\n\n"
    
    kb.row(*buttons, width=2)
    await message.reply(text=text, reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data.startswith("select_craft:"))
async def select_craft_callback(callback: types.CallbackQuery):
    prof_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        user = await core.user_getOrCreate(callback.from_user)
        settlement = await core.settlement_getOrCreate(callback.message.chat)
        settler = await core.settler_getOrCreate(user, settlement)

        if callback.from_user.id != callback.message.reply_to_message.from_user.id:
            await callback.answer("❌ Не тронь чужой снасти!", True)
            return
        
        if settler.profession_id == prof_id:
            await callback.answer("❌ Ты уж сие ремесло избрал! Аль сменить хочешь, то другое избери.")
            return
        
        prof_result = await session.execute(select(models.Profession).where(models.Profession.id == prof_id))
        profession = prof_result.scalars().first()
        
        if not profession or settler.level < profession.required_level:
            await callback.answer(f"❌ Ремесло сие тебе не по плечу! {settler.level}/<b>{profession.required_level}</b>💡")
            return
        if settler.profession_id:
            can_choose, when = mfunc.can_choose_craft(settler.last_profession_change)
            if not can_choose:
                await callback.answer(f"❌Недавно ты ремесло своё сменил, человече! Новое взять можно, как {when} пройдёт.", True)
        
        await session.execute(
            update(models.Settler)
            .where(models.Settler.id == settler.id)
            .values(profession_id=prof_id, last_profession_change=int(datetime.now().timestamp()))
        )
        await session.commit()
        
        kb = InlineKeyboardBuilder().row(InlineKeyboardButton(text=f"{profession.emoji} Трудиться", switch_inline_query_current_chat="Трудиться"))
        await callback.message.edit_text(f"✅ <b>{callback.from_user.full_name}</b> ремесло себе избрал: {profession.emoji} <b>{profession.name}!</b>", reply_markup=kb.as_markup())
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💼 Выбрано ремесло: {profession.name}")

@router.message(or_f(Command("craft"), F.text.lower() == "трудиться", F.text.lower() == "@mysettlementbot трудиться", F.text.lower() == "craft", F.text.lower() == "@mysettlementbot craft"))
async def craft_command(message: types.Message):
    #* Обработка команды /craft
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)
    
    if not settler.profession_id:
        await message.answer("⚠️ Ты ещё ремесла не избрал.", reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="💼 Выбрать ремесло", switch_inline_query_current_chat="Выбрать ремесло")).as_markup())
        return
    
    available_works = [
        work for work in models.WORKS_REGISTRY.values()
        if work.profession_id == settler.profession_id
    ]

    if not available_works:
        await message.answer("⚠️ Твоё ремесло пока не имеет доступных трудов. Жди вестей новых!")
        return
    
    if len(available_works) == 1:
        await core.start_workflow(message, available_works[0], user, settler)
        return
    
    kb = InlineKeyboardBuilder()
    for work in available_works:
        kb.add(InlineKeyboardButton(text=f"{work.emoji} {work.name}", callback_data=f"start_workflow:{work.id}"))
    kb.adjust(2)

    await message.reply(f"{settler.profession.emoji} <b>{settler.profession.name}:</b>", reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data.startswith("select_work:"))
async def work_selection_callback(callback: types.CallbackQuery):
    work_id = callback.data.split(":", 1)[1]

    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    if callback.from_user.id != callback.message.reply_to_message.from_user.id:
        await callback.answer("⚠️ Не тронь чужой снасти!", True)
        return
    
    work = models.WORKS_REGISTRY.get(work_id)
    if not work:
        await callback.answer("⚠️ Труд не сыскан!", True)
        return
    
    if work.profession_id != settler.profession_id:
        await callback.answer("⚠️ Сие дело твоему ремеслу не по плечу!", True)
        return

    success = await core.start_workflow(callback, work, user, settler)
    if not success:
        return

@router.callback_query(F.data.startswith("work:"))
async def work_callback(callback: types.CallbackQuery):
    #* Обработка callback-кнопок для работы
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    user_key = f"{callback.message.chat.id}_{user.telegram_id}"
    if not mfunc.can_click_button(user_key):
        await callback.answer("⏳ Погоди миг единый!")
        return
    
    remaining = mfunc.get_work_remaining_time(callback.message.chat.id)
    if remaining <= 0:
        await callback.answer("⏰ Пора труда миновала! Дело отложено.", True)
        await callback.message.edit_text("⏰ Долго ты без дела стоял! Труд отложен.")
        mfunc.end_work(callback.message.chat.id)
        active_games.pop(user_key, None)
        return
    
    workflow: Workflow = active_games.get(user_key)
    if not workflow or workflow.game_over:
        await callback.answer("⚠️ Дело не сыскано. Может, ты уж его свершил, али вовсе не твоё то дело?")
        return
    
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("⚠️ Неверный ход!")
        return
    
    _, work_id, step_idx_str, *action_parts = parts
    step_idx = int(step_idx_str)
    action = ":".join(action_parts) if action_parts else None
    log.debug(f"{callback.message.chat.id} | {user.id} | 🎭 Работа: {work_id}, Шаг: {step_idx}, Действие: {action}")
    
    work: models.Work = models.WORKS_REGISTRY.get(work_id)
    if not work:
        await callback.answer("⚠️ Труд не сыскан!")
        return
    
    if step_idx >= len(workflow.steps):
        await callback.answer("⚠️ Неверный шаг!")
        return

    current_step = workflow.get_current_step()
    converted_action = action
    if action is not None and current_step is not None:
        if isinstance(current_step, (Hitting, Catch, Alternation)):
            try:
                converted_action = int(action)
            except Exception:
                if isinstance(action, str) and ":" in action:
                    try:
                        converted_action = int(action.split(":")[-1])
                    except Exception:
                        converted_action = action
                else:
                    converted_action = action
        else:
            converted_action = action

    result = workflow.click(converted_action)
    try:
        step_obj = workflow.get_current_step()
    except Exception:
        step_obj = None
    answer_text = work.get_answer_text(result, step_idx, workflow, step_obj)
    if answer_text:
        await callback.answer(str(answer_text))

    if result == "win" and workflow.completed:
        status_text = workflow.get_status_text()
        async with SessionLocal() as session:
            earned, exp = await core.apply_rewards(work, settler, session, callback.message.chat.id)
            reward_text = mfunc.format_reward_text(earned, exp)
            await callback.message.edit_text(f"{status_text}\n\n{reward_text}", reply_markup=None)
            await mfunc.mark_work_completed(settler, session, callback.message.chat.id)
        
        active_games.pop(user_key, None)
        mfunc.end_work(callback.message.chat.id)

    elif result == "lose":
        status_text = None
        key_combo = f"step_{step_idx}_lose"
        if key_combo in work.texts:
            entry = work.texts[key_combo]
        else:
            step_key = f"step_{step_idx}"
            step_entry = work.texts.get(step_key)
            if isinstance(step_entry, dict):
                entry = step_entry.get("lose")
            else:
                entry = work.texts.get("lose")

        if entry is not None:
            if callable(entry):
                try:
                    status_text = entry()
                except TypeError:
                    try:
                        status_text = entry(workflow)
                    except TypeError:
                        try:
                            status_text = entry(step_obj)
                        except Exception:
                            status_text = str(entry)
                except Exception:
                    status_text = str(entry)
            else:
                status_text = str(entry)

        if not status_text:
            status_text = workflow.get_status_text()

        await callback.message.edit_text(status_text, reply_markup=None)
        if work.cooldown_on_fail:
            async with SessionLocal() as session:
                await mfunc.mark_work_completed(settler, session, callback.message.chat.id)
        active_games.pop(user_key, None)
        mfunc.end_work(callback.message.chat.id)
    else:
        status_text = workflow.get_status_text()
        kb = workflow.get_keyboard()
        await callback.message.edit_text(status_text, reply_markup=kb)
        




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
            if await mfunc.is_meaningful(message.text) and not settler.quote_is_completed:
                await core.quote_update(settler, settlement, session, 1)
                return
        except Exception as e:
            log.error(f"Ошибка в функции quote_handler(): {e}")
            return