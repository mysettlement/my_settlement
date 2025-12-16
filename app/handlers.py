from aiogram import Router, types, F, Bot
from aiogram.filters import Command, CommandObject, CommandStart, or_f, and_f
from aiogram.types import InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

import logging
from datetime import datetime

from app.config import setup_logging, settings
from app.db import SessionLocal
import app.core as core
from app.gamer import Workflow, Harvesting, Hitting, Catch, Alternation, ProgressBar
import app.models as models
from app.mfunc import active_games, fuzzy
import app.mfunc as mfunc

bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, disable_notification=True, link_preview_is_disabled=True)
    )
router = Router()
log = setup_logging(logging.getLogger(__name__))



# ================= Private chats ================

@router.my_chat_member()
async def bot_added_to_chat_event(event: types.ChatMemberUpdated):
    #* Приветствие при добавлении бота в группу
    chat = event.chat
    kb = InlineKeyboardBuilder()

    if event.new_chat_member.status in ["left", "kicked"]:
        log.debug(f"{chat.id} | Бот исключен из группы {chat.title}")
        try:
            await bot.send_message(
                chat_id=event.from_user.id,
                text=(
                    f"🏰 <b>Я покинул стены поселения «{chat.title}»...</b>\n"
                    "Буду признателен, если расскажешь, что пошло не так.\n"
                    "Это поможет мне стать лучше для других правителей."
                ),
                reply_markup=InlineKeyboardBuilder()
                .add(InlineKeyboardButton(text="✍️ Пройти опрос (1 мин)", url="https://tally.so/r/2EXdND"))
                .as_markup()
            )
        except:
            log.debug(f"Не удалось отправить опрос пользователю {event.from_user.id}")
        return
    
    if event.old_chat_member.status not in ["member", "administrator", "restricted"] and event.new_chat_member.status in ["member", "administrator"]:
        text_log = (f"{chat.id} | Бот добавлен в группу {chat.title}")

        text = (
            "🏰 <b>Добро пожаловать в игру «Поселения»!</b>\n\n"
            "🛖 Для начала игры используйте команду /start"
        )

        kb.add(InlineKeyboardButton(text="❓ Помощь", switch_inline_query_current_chat="Помощь"))
        kb.add(InlineKeyboardButton(text="🚶‍➡️ Осмотреть поселение", switch_inline_query_current_chat="Осмотреть поселение"))

        if event.new_chat_member.status == "member":
            text += "\n\n⚠️ Пожалуйста, <b>назначьте меня администратором</b> с правами на <i>закрепление</i> и <i>удаление</i> сообщений, <b>чтобы я мог полноценно функционировать!</b>"
            text_log += " без прав администратора!"
        
    
    elif event.new_chat_member.status == "administrator" and event.old_chat_member.status in ["member", "restricted"]:
        text = "✅ <b>Спасибо</b>, что назначили меня администратором!"
        text_log = f"{chat.id} | Бот назначен администратором"
    
    elif event.new_chat_member.status in ["member", "restricted"] and event.old_chat_member.status == "administrator":
        text = "⚠️ Пожалуйста, <b>назначьте меня администратором</b> с правами на <i>закрепление</i> и <i>удаление</i> сообщений, <b>чтобы я мог полноценно функционировать!</b>"
        text_log = f"{chat.id} | Бот снят с администратора"
    
    await event.answer(text, reply_markup=kb.as_markup())
    log.debug(text_log)



@fuzzy("мой айди", "my id", "мій айді", "мой ид", "мій ід")
@router.message(or_f(Command("my_id"), F.text.lower().in_({"мой айди", "мой ид", f"@{settings.BOT_USERNAME} мой айди", "my id", f"@{settings.BOT_USERNAME} my id", "мій айді", "мій ід", f"@{settings.BOT_USERNAME} мій айді", f"@{settings.BOT_USERNAME} мій ід"})))
async def my_id_command(message: types.Message):
    #* Показать ID пользователя
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

@fuzzy("профиль", "мой профиль", "my profile", "мій профіль")
@router.message(or_f(Command("me"), F.text.lower().in_({"профиль", f"@{settings.BOT_USERNAME} профиль", "мой профиль", f"@{settings.BOT_USERNAME} мой профиль", "my profile", f"@{settings.BOT_USERNAME} my profile", "мій профіль", f"@{settings.BOT_USERNAME} мій профіль"})))
async def me_command(message: types.Message):
    #* Профиль поселенца
    user = await core.user_getOrCreate(message.from_user)

    compact_style = user.compact_style
    kb = InlineKeyboardBuilder()

    if message.chat.type == "supergroup" or message.chat.type == "group":
        settlement = await core.settlement_getOrCreate(message.chat)
        settler = await core.settler_getOrCreate(user, settlement)
        craft_text = f"{settler.profession.emoji} {settler.profession.name}" if settler.profession else "❓ Лодырь"
        can_choose, when = mfunc.can_choose_craft(settler.last_profession_change)
        can_work, work_countdown = core.settler_canWorkNow(settler)
        
        if compact_style:
            text = (
                f"👤 <b>{user.name}</b> — {craft_text}\n"
                f"💡 {settler.level} — {settler.emoji} <b>{settler.rank}</b>\n"
                f"🗂 <b>{round(settler.exp)}/{round(settler.target_exp)}</b> | "
                f"📄 {f'<b>{settler.quote}/{settler.target_quote}</b>' if not settler.quote_is_completed else f'{settler.target_quote}/{settler.target_quote}'} {'(⏳) ' if settler.overtime_is_toggled and not settler.quote_is_completed else ''}| "
                f"💰 <b>{round(settler.balance)}</b> ({'<b>' if settler.income != 0 else ''}{round(settler.income)}/день{'</b>' if settler.income != 0 else ''})\n"
                f"\n{(settler.profession.emoji + ': <b>' + work_countdown + '</b> 🕒') if (settler.profession and not can_work) else ((settler.profession.emoji + ': ✅') if settler.profession else '')}"
            )

            kb.add(InlineKeyboardButton(text="🪭", switch_inline_query_current_chat="Косметика"))
            kb.add(InlineKeyboardButton(text="📦", switch_inline_query_current_chat="Инвентарь"))
            kb.add(InlineKeyboardButton(text="🕒", switch_inline_query_current_chat="Лишняя мера"))
            kb.add(InlineKeyboardButton(text=f"{settler.profession.emoji}", switch_inline_query_current_chat="Трудиться")) if settler.profession and can_work else None
            kb.add(InlineKeyboardButton(text="💼", switch_inline_query_current_chat="Выбрать ремесло")) if can_choose else None
            
        else:
            text = (
                f"👤 <b>{user.name}</b>\n"
                f"🛠 <b>Ремесло:</b> {craft_text}\n"
                f"💡 <b>Уровень:</b> {settler.level}\n"
                f"🗂 <b>Опыт:</b> {round(settler.exp)}/{round(settler.target_exp)}\n"
                f"🏷 <b>Ранг:</b> {settler.emoji} {settler.rank}\n"
                f"📄 <b>Мера:</b> {f'<b>{settler.quote}/{settler.target_quote}</b>' if not settler.quote_is_completed else f'{settler.target_quote}/{settler.target_quote}'} {'(⏳ Лишняя мера взята)' if settler.overtime_is_toggled and not settler.quote_is_completed else ''}\n"
                f"💰 <b>Баланс:</b> {round(settler.balance)} ({'<b>' if settler.income != 0 else ''}{round(settler.income)}/день{'</b>' if settler.income != 0 else ''})\n"
                f"\n {(settler.profession.emoji + ' Трудиться можно через <b>' + work_countdown + '</b> 🕒') if (settler.profession and not can_work) else ((settler.profession.emoji + ' <b>Можно трудиться</b> ✅') if settler.profession else '')} "
            )

            kb.add(InlineKeyboardButton(text="🪭 Косметика", switch_inline_query_current_chat="Косметика"))
            kb.add(InlineKeyboardButton(text="📦 Инвентарь", switch_inline_query_current_chat="Инвентарь"))
            kb.add(InlineKeyboardButton(text="🕒 Лишняя мера", switch_inline_query_current_chat="Лишняя мера"))
            kb.add(InlineKeyboardButton(text=f"{settler.profession.emoji} Трудиться", switch_inline_query_current_chat="Трудиться")) if settler.profession and can_work else None
            kb.add(InlineKeyboardButton(text="💼 Выбрать ремесло", switch_inline_query_current_chat="Выбрать ремесло")) if can_choose else None
        
        kb.adjust(2)
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


@fuzzy("настройки", "settings", "налаштування")
@router.message(or_f(Command("settings"), F.text.lower().in_({"настройки", f"@{settings.BOT_USERNAME} настройки", "settings", f"@{settings.BOT_USERNAME} settings", "налаштування", f"@{settings.BOT_USERNAME} налаштування"})))
async def settings_command(message: types.Message):
    #* Настройки пользователя
    user = await core.user_getOrCreate(message.from_user)
    kb = InlineKeyboardBuilder()
    buttons = []

    compact_style = user.compact_style
    show_hints = user.show_hints
    allow_typos = user.allow_typos
    #TODO: XXX = user.XXX

    buttons.append(InlineKeyboardButton(text=f"{'🎩' if compact_style else '🎩 Стиль'}: {'🤏' if compact_style else '🤲'}", callback_data="settings:compact_style"))
    buttons.append(InlineKeyboardButton(text=f"{'ℹ️' if compact_style else 'ℹ️ Подсказки'}: {'✅' if show_hints else '❌'}", callback_data="settings:show_hints"))
    buttons.append(InlineKeyboardButton(text=f"{'✍️' if compact_style else '✍️ Опечатки'}: {'✅' if allow_typos else '❌'}", callback_data="settings:allow_typos"))
    #TODO: buttons.append(InlineKeyboardButton(text=f"{'' if compact_style else ''}: {'✅' if XXX else '❌'}", callback_data="settings:XXX"))
    kb.row(*buttons, width=2)
    
    text = f"⚙️ <b>Настройки</b>"
    text += f"\n🎩 Стиль: <b>{'🤏 Компактный' if compact_style else '🤲 Развёрнутый'}</b>"
    text += f"\nℹ️ Подсказки: <b>{'✅ Включены' if show_hints else '❌ Выключены'}</b>"
    text += f"\n✍️ Опечатки: <b>{'✅ Учитывать' if allow_typos else '❌ Не учитывать'}</b>"
    #TODO: text += f"\n XXX: <b>{'✅' if XXX else '❌'}</b>"
    text += "\n\nℹ️ Настройки сохраняются для каждого пользователя отдельно." if user.show_hints else ""
    #TODO: text += '<a href="https://">📖 Подробнее о настройках</a>'
    
    await message.reply(text=text, reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data.startswith("settings:"))
async def settings_callback(callback: types.CallbackQuery):
    #* Callback-кнопки настроек
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
        allow_typos = user.allow_typos
        #TODO: XXX = user.XXX
        
        if action == "compact_style":
            user.compact_style = not compact_style; compact_style = not compact_style
            log.debug(f"{user.telegram_id} | 🎩 compact_style > {compact_style}")
            await callback.answer(f"🎩 Стиль > {"🤏 Компактный" if compact_style else "🤲 Развёрнутый"}")

        elif action == "show_hints":
            user.show_hints = not show_hints; show_hints = not show_hints
            log.debug(f"{user.telegram_id} | ℹ️ show_hints > {show_hints}")
            await callback.answer(f"ℹ️ Подсказки > {'✅ Включены' if show_hints else '❌ Выключены'}")
        
        elif action == "allow_typos":
            user.allow_typos = not allow_typos; allow_typos = not allow_typos
            log.debug(f"{user.telegram_id} | 🎩 allow_typos > {allow_typos}")
            await callback.answer(f"✍️ Опечатки > {'✅ Учитывать' if allow_typos else '❌ Не учитывать'}")
        
        #TODO: elif action == "XXX":

        await session.commit()

    buttons.append(InlineKeyboardButton(text=f"{'🎩' if compact_style else '🎩 Стиль'}: {'🤏' if compact_style else '🤲'}", callback_data="settings:compact_style"))
    buttons.append(InlineKeyboardButton(text=f"{'ℹ️' if compact_style else 'ℹ️ Подсказки'}: {'✅' if show_hints else '❌'}", callback_data="settings:show_hints"))
    buttons.append(InlineKeyboardButton(text=f"{'✍️' if compact_style else '✍️ Опечатки'}: {'✅' if allow_typos else '❌'}", callback_data="settings:allow_typos"))
    #TODO: buttons.append(InlineKeyboardButton(text=f"{'' if compact_style else ''}: {'✅' if XXX else '❌'}", callback_data="settings:XXX"))
    
    text = f"⚙️ <b>Настройки</b>"
    text += f"\n🎩 Стиль: <b>{'🤏 Компактный' if compact_style else '🤲 Развёрнутый'}</b>"
    text += f"\nℹ️ Подсказки: <b>{'✅ Включены' if show_hints else '❌ Выключены'}</b>"
    text += f"\n✍️ Опечатки: <b>{'✅ Учитывать' if allow_typos else '❌ Не учитывать'}</b>"
    #TODO: text += f"\n XXX: <b>{'✅' if XXX else '❌'}</b>"
    text += "\n\nℹ️ Настройки сохраняются для каждого пользователя отдельно." if user.show_hints else ""
    #TODO: text += '<a href="https://">📖 Подробнее о настройках</a>'

    kb.row(*buttons, width=2)
    try:
        await callback.message.edit_text(text=text, reply_markup=kb.as_markup())
    except Exception as e:
        await callback.message.edit_reply_markup(reply_markup=kb.as_markup())

@fuzzy("help", "помощь", "допомога")
@router.message(or_f(Command("help"), F.text.lower().in_({"помощь", f"@{settings.BOT_USERNAME} помощь", "help", f"@{settings.BOT_USERNAME} help", "допомога", f"@{settings.BOT_USERNAME} допомога"})))
async def help_command(message: types.Message):
    #* Помощь и руководство по игре
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


@router.message(or_f(and_f(F.chat.type == "private", CommandStart()), F.chat.type == "private"))
async def private_handler(message: types.Message, command: CommandObject = None):
    #* Личные сообщения и рефералы
    if command and command.args:
        args = command.args
        
        if args.startswith("ref_"):
            referrer_id = args.split("_")[1]
            await message.answer(f"👋 Тебя пригласил поселенец с ID: {referrer_id}")
            return
        
        if args.startswith("survey_"):
            chat_id = args.split("_")[1]
        
        # elif args.startswith("work_"):
        # _, work_id,  = args.split("_")

    kb = InlineKeyboardBuilder()
    kb.add(InlineKeyboardButton(text="➕ Добавить", url=f"https://t.me/{settings.BOT_USERNAME}?startgroup=new"))
    
    await message.answer(text="<b>Здрав будь!</b> Я вестник для игры в 🛖 <b>Поселения</b>.\nЧтоб в сходку свою меня позвать, <b>на знак ниже ткни:</b>", reply_markup=kb.as_markup())



# ================= Group chats ================

@fuzzy("осмотреть город", "осмотреть поселение", "мое поселение", "моё поселение", "town")
@router.message(or_f(CommandStart(), Command("town"), F.text.lower().in_({"осмотреть город", f"@{settings.BOT_USERNAME} осмотреть город", "осмотреть поселение", f"@{settings.BOT_USERNAME} осмотреть поселение", "town", f"@{settings.BOT_USERNAME} town"})))
async def start_command(message: types.Message):
    #* Осмотр поселения / старт игры
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
        f"<b>{settlement.name}</b> (основан {await mfunc.format_relative_time(settlement.created_at)})\n"
        f"👥{len(settlement.members)} 👑 <b>{settlement.owner.name or (f"User {settlement.owner.telegram_id}" if settlement.owner else "Отсутствует")}</b>"
    )
    await message.answer(text, reply_markup=kb.as_markup())


# @fuzzy("назвать поселение", "name settlement")
# @router.message(or_f(Command("name_settlement"), F.text.startswith.lower().in_({"назвать поселение", f"@{settings.BOT_USERNAME} назвать поселение", "name settlement", f"@{settings.BOT_USERNAME} name settlement"})))
# async def name_settlement(message: types.Message):
#     #* Смена имени поселения
#     user = await core.user_getOrCreate(message.from_user)
#     settlement = await core.settlement_getOrCreate(message.chat)
#     settler = await core.settler_getOrCreate(user, settlement)
#     if not settler:
#         log.error(f"Не удалось получить или создать поселенца для пользователя {message.from_user.id} в функции name_settlement()")
#         await message.answer("⚠️ Беда приключилась, вести о тебе не сысканы. Погоди малость, опосля пытай снова.")
#         return
    
#     owner = settlement.owner
#     if not owner:
#         log.error(f"Не удалось получить владельца поселения чата {message.chat.id} в функции name_settlement()")
#         await message.answer("⚠️ Беда приключилась, вести мэре не сысканы. Погоди малость, опосля пытай снова.")
#         return
    
#     if owner.telegram_id != message.from_user.id:
#         await message.answer("⚠️ Управлять поселением токмо мэр может! Иди своим путём, простолюдин.")
#         return
    
#     delta = datetime.now() - settlement.last_name_change
#     hours = delta.seconds // 3600
#     if hours < config.SETTLEMENT_NAME_CHANGE_COOLDOWN_HOURS:
#         await message.answer(f"📜<b>Встань, {owner}, но не радуйся прежде времени.</b>\n\nСлово твоё услышано, однако милости на этот раз не будет.\nЯ вижу, что прошение о новом имени ты принёс, но <b>отказываю тебе твёрдо и окончательно</b>:📌\nПоселение твоё лишь недавно, по моей же воле, получило имя <b>{new_name}</b>, и древний обычай велит ждать ещё <b>{mfunc.format_relative_time(settlement.last_name_change)}</b>, прежде чем вновь тревожить печати, грамоты и память народную. Пусть имя это остаётся нерушимым, как скала, и служит людям многие лета без новых перемен.\nПусть под нынешним знаменем <b>{new_name}</b> град наш крепнет и цветёт, а не мечется меж новых слов, словно лист на ветру.\n\n<b>Да здравствует {new_name} — и да пребудет оно неизменным!</b>💪\n🏰Возвращайся в свой град с миром и передай всем: воля моя такова, и точка.")
#         return

#     new_name = message.text.split("")[1] #! Исправить!
#     old_name = settlement.name
#     if new_name == old_name:
#         message.answer(f"📜<b>Что за шутки, мэр?</b>\n\nТы просишь переименовать град из <b>{old_name}</b> в… <b>{new_name}</b>? Но ведь это одно и то же имя!\nМенять его на то же самое — всё равно что воду в ступе толочь.\n\n❌<b>Отказываю!</b> Пусть остаётся как есть.\n\n<b>Да здравствует {new_name} — и без лишних бумаг!</b>💪\n🏰Иди с миром и больше не трать пергамент понапрасну.")
#         return
    
#     settlement.name = new_name
#     settlement.last_name_change = datetime.now()

#     await message.answer(f"📜<b>Добро, верный мэр!</b>\n\nВстань с колен и подними чело своё — милость моя к тебе велика, а слово твоё услышано и принято с радостью.\nВижу я, что воля моя исполнена точно и в срок: отныне и во веки веков <b>поселение моё, прежде звавшееся {old_name}, носит новое славное имя — {new_name}!</b>📌\n🌄Пусть же это имя гремит от края до края земли моей, пусть в летописях золотом будет вписано, а в сердцах подданных моих — выжжено огнём вечной верности.\n🔔Люди ликуют, колокола гудят, а враги наши да трепещут, ибо под новым знаменем град наш станет ещё крепче и славнее!\n\n<b>Да здравствует {new_name}!</b>💪\nДа цветёт оно под дланью моей многие лета!🏞\nИди с миром и неси славу новую по всей земле!</b>")



@fuzzy("косметика", "cosmetics")
@router.message(or_f(Command("cosmetics"), F.text.lower().in_({"косметика", f"@{settings.BOT_USERNAME} косметика", "cosmetics", f"@{settings.BOT_USERNAME} cosmetics"})))
async def cosmetics_command(message: types.Message):
    #* Косметика поселенца
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
    await message.reply(text=text, reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data.startswith("cosmetics_select_"))
async def cosmetics_select(callback: types.CallbackQuery):
    #* Выбор эмодзи косметики
    if callback.from_user.id != callback.message.reply_to_message.from_user.id:
        await callback.answer("❌ Не тронь чужой снасти!", True)
        return
    
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


@fuzzy("лишняя мера", "overtime", "зайва міра")
@router.message(or_f(Command("overtime"), F.text.lower().in_({"лишняя мера", f"@{settings.BOT_USERNAME} лишняя мера", "overtime", f"@{settings.BOT_USERNAME} overtime", "зайва міра", f"@{settings.BOT_USERNAME} зайва міра"})))
async def overtime_command(message: types.Message):
    #* Лишняя мера поселенца
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
            text += f"Состояние лишней меры: ⚪️ <b>Активна</b>\nСколько лишней меры взято: {overtime_count} (🕒 <b>{daily_reset_countdown}</b> до новой меры)\n📄 Мера: <b>{quote}/{target_quote}</b>"
    elif not settler.overtime_is_toggled and not settler.quote_is_completed:
        text += "⚠️ Лишнюю меру брать можно, токмо основную 📄 меру свершив!"
    else:
        if compact_style:
            text += f"🔘 {overtime_count}"
        else:
            text += f"Состояние лишней меры: 🔘 <b>Неактивна</b>\nСколько лишней меры взято: {overtime_count}"
        buttons.append(InlineKeyboardButton(text="🕒 Взять лишнюю меру", callback_data="overtime_take"))

    kb.row(*buttons)
    await message.reply(text, reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data == "overtime_take")
async def overtime_take(callback: types.CallbackQuery):
    #* Взять лишнюю меру
    async with SessionLocal() as session:
        if callback.from_user.id != callback.message.reply_to_message.from_user.id:
            await callback.answer("⚠️ Не тронь чужой снасти!", True)
            return

        user = await core.user_getOrCreate(callback.from_user)
        settlement = await core.settlement_getOrCreate(callback.message.chat)
        settler = await core.settler_getOrCreate(user, settlement)

        if settler.overtime_is_toggled and not settler.quote_is_completed:
            await callback.answer("⚠️ Лишняя мера уже взята!", True)
            return

        new_quote = round((settler.level * 0.85 + 6) + (2 * (settler.overtime_count + 1)))

        await session.execute(
            update(models.Settler)
            .where(models.Settler.id == settler.id)
            .values(
                overtime_is_toggled=True,
                overtime_count=settler.overtime_count + 1,
                quote_is_completed=False,
                quote=0,
                target_quote=new_quote
            )
        )
        
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 🔄 Лишняя мера взята: 0/{new_quote}")
        await session.commit()
        
        reset_countdown = mfunc.get_daily_reset_countdown()
        await callback.message.edit_text(f"⏳ <b>Лишняя мера взята!</b> (📄 0/{new_quote})\nТебе осталось 🕒 <b>{reset_countdown}</b> чтоб новую меру исполнить!")


@fuzzy("инвентарь", "inventory", "інвентар")
@router.message(or_f(Command("inventory"), F.text.lower().in_({"инвентарь", f"@{settings.BOT_USERNAME} инвентарь", "inventory", f"@{settings.BOT_USERNAME} inventory", "інвентар", f"@{settings.BOT_USERNAME} інвентар"})))
async def inventory_command(message: types.Message):
    #* Инвентарь поселенца
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
            if settler.level < 5 and user.show_hints == True:
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
            text += f"<b>{category}:</b>\n{' | '.join(items)}\n\n"
    
    await message.answer(text=text)


@fuzzy("выбрать ремесло", "choose craft", "вибрати ремесло")
@router.message(or_f(Command("choose_craft"), F.text.lower().in_({"выбрать ремесло", f"@{settings.BOT_USERNAME} выбрать ремесло", "choose craft", f"@{settings.BOT_USERNAME} choose craft"})))
async def choose_craft_command(message: types.Message):
    #* Выбор ремесла поселенца
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
    #* Кнопка выбора ремесла
    prof_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        user = await core.user_getOrCreate(callback.from_user)
        settlement = await core.settlement_getOrCreate(callback.message.chat)
        settler = await core.settler_getOrCreate(user, settlement)

        if callback.from_user.id != callback.message.reply_to_message.from_user.id:
            await callback.answer("⚠️ Не тронь чужой снасти!", True)
            return
        
        if settler.profession_id == prof_id:
            await callback.answer("⚠️ Ты уж сие ремесло избрал! Аль сменить хочешь, то другое избери.")
            return
        
        prof_result = await session.execute(select(models.Profession).where(models.Profession.id == prof_id))
        profession = prof_result.scalars().first()
        
        if not profession or settler.level < profession.required_level:
            await callback.answer(f"⚠️ Ремесло сие тебе не по плечу! {settler.level}/<b>{profession.required_level}</b>💡")
            return
        if settler.profession_id:
            can_choose, when = mfunc.can_choose_craft(settler.last_profession_change)
            if not can_choose:
                await callback.answer(f"⚠️ Недавно ты ремесло своё сменил, человече! Новое взять можно, как <b>{when}</b> пройдёт.", True)
        
        await session.execute(
            update(models.Settler)
            .where(models.Settler.id == settler.id)
            .values(profession_id=prof_id, last_profession_change=datetime.now())
        )
        await session.commit()
        
        kb = InlineKeyboardBuilder().row(InlineKeyboardButton(text=f"{profession.emoji} Трудиться", switch_inline_query_current_chat="Трудиться"))
        await callback.message.edit_text(f"✅ <b>{callback.from_user.full_name}</b> ремесло себе избрал: {profession.emoji} <b>{profession.name}!</b>", reply_markup=kb.as_markup())
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💼 Выбрано ремесло: {profession.name}")

@fuzzy("трудиться", "craft", "трудитися", "працювати")
@router.message(or_f(Command("craft"), F.text.lower().in_({"трудиться", f"@{settings.BOT_USERNAME} трудиться", "craft", f"@{settings.BOT_USERNAME} craft", "трудитися", f"@{settings.BOT_USERNAME} трудитися", "працювати", f"@{settings.BOT_USERNAME} працювати"})))
async def craft_command(message: types.Message):
    #* Начало труда поселенца
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
        await core.settler_startWorkflow(message, available_works[0], user, settler)
        return
    
    kb = InlineKeyboardBuilder()
    for work in available_works:
        if user.compact_style:
            kb.add(InlineKeyboardButton(text=f"{work.emoji}", callback_data=f"select_work:{work.id}"))
        else:
            kb.add(InlineKeyboardButton(text=f"{work.emoji} {work.name}", callback_data=f"select_work:{work.id}"))
    kb.adjust(2)

    await message.reply(f"{settler.profession.emoji} <b>{settler.profession.name}:</b>", reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data.startswith("select_work:"))
async def work_selection_callback(callback: types.CallbackQuery):
    #* Кнопка выбора труда
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

    success = await core.settler_startWorkflow(callback, work, user, settler)
    if not success:
        return

@router.callback_query(F.data.startswith("work:"))
async def work_callback(callback: types.CallbackQuery):
    #* Callback-кнопки для работы
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
        if isinstance(current_step, (Hitting, Catch, Alternation, ProgressBar)):
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
            earned = await core.settler_applyRewards(work, settler, session)
            reward_text = await mfunc.format_reward_text(earned)
            await callback.message.edit_text(f"{status_text}\n\n📦 <b>Получено:</b>\n{reward_text}", reply_markup=None)
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


@router.message(F.text.lower().startswith("!дать"))
async def promo_command(message: types.Message):
    #* Выдача ресурса разработчиком
    if message.from_user.id not in settings.DEVELOPER_IDS:
        await message.answer("⚠️ Только разработчики могут выдавать ресурсы.")
        return

    try:
        _ , emoji, qty = message.text.split(" ")
        qty = int(qty)
    except:
        await message.answer(f"⚠️ Неверный формат команды.\n{emoji}: +{qty}\n<code>!дать эмодзи количество</code> (в ответ)")
        return
    
    try:
        recipient = message.reply_to_message.from_user
    except:
        recipient = message.from_user

    user = await core.user_getOrCreate(recipient)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)
    
    async with SessionLocal() as session:
        obtained = await core.settler_add(settler, session, emoji, qty)
        text = await mfunc.format_reward_text(obtained)

        await session.commit()
    
    await message.answer(f"🌟 <b>{message.from_user.full_name} получил(а):</b>\n{text}")


def collect_commands(router) -> dict[str, callable]:
    result = {}
    for handler in router.message.handlers:
        cb = handler.callback
        aliases = getattr(cb, "__fuzzy_aliases__", None)
        if not aliases:
            continue
        for alias in aliases:
            result[alias] = cb
    return result
FUZZY_COMMANDS = collect_commands(router)


@router.message(or_f(F.chat.type == "supergroup", F.chat.type == "group"))
async def quote_handler(message: types.Message):
    #* Обработка сообщений для меры
    user = await core.user_getOrCreate(message.from_user)
    match = await mfunc.is_text_command(
        message,
        user,
        FUZZY_COMMANDS,
        threshold=settings.TYPOS_PERCENT
    )
    
    if match.matched:
        handler = FUZZY_COMMANDS[match.command]
        await handler(message)
        log.debug(f"{message.chat.id} | {user.telegram_id} | 🔍 {message.text} → {match.command} ({match.score}%)")
        return
    
    log.debug(f"{message.chat.id} | {user.telegram_id} | 🔍 {message.text} / {match.log_text}")
    
    async with SessionLocal() as session:
        result = await session.execute(
            select(models.Settlement).where(models.Settlement.chat_id == message.chat.id)
        )
        settlement = result.scalars().first()
        
        if not settlement:
            return
            
        settler = await core.settler_getOrCreate(user, settlement)
        
        if not settler:
            log.error(f"Не удалось получить или создать поселенца для пользователя {message.from_user.id} во время quote_handler()")
            return
            
        try:
            if await mfunc.is_meaningful(message.text) and not settler.quote_is_completed:
                await core.settler_updateQuote(settler, settlement, session, 1)
                return
        except Exception as e:
            log.error(f"Ошибка в функции quote_handler(): {e}")
            return

