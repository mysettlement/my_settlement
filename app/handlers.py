from __future__ import annotations

from aiogram import Router, types, F, Bot
from aiogram.filters import Command, CommandObject, CommandStart, or_f, and_f
from aiogram.types import InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.client.default import DefaultBotProperties
from aiogram.utils.keyboard import InlineKeyboardBuilder

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

import logging
import arrow
import html
from typing import TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
from timezonefinder import TimezoneFinder

if TYPE_CHECKING:
    from stub import TranslatorRunner

from app.config import setup_logging, settings
from app.db import SessionLocal
from app.gamer import Workflow, Hitting, Catch, Alternation, ProgressBar
from app.i18n import I18nMiddleware, LANGUAGES_MAP, create_translator_hub
from app.utils import active_games, fuzzy, format_count
from app import utils, core, models

bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML, disable_notification=True, link_preview_is_disabled=True)
    )
router = Router()
log = setup_logging(logging.getLogger(__name__))
tf = TimezoneFinder()


# ================= Private chats ================

@router.my_chat_member()
async def bot_added_to_chat_event(event: types.ChatMemberUpdated):
    #* Приветствие при добавлении бота в группу
    chat = event.chat
    kb = InlineKeyboardBuilder()
    i18n = create_translator_hub().get_translator_by_locale("ru")

    if event.new_chat_member.status in ["left", "kicked"]:
        log.debug(f"{chat.id} | Бот исключен из группы {chat.title}")
        try:
            await bot.send_message(
                chat_id=event.from_user.id,
                text=(
                    "🏰 " + i18n.text.other.bot.left(chat_title=chat.title)
                ),
                reply_markup=InlineKeyboardBuilder()
                .button(text="✍️ " + i18n.button.other.bot.left.survey(), url="https://tally.so/r/2EXdND")
                .as_markup()
            )
        except:
            log.debug(f"Не удалось отправить опрос пользователю {event.from_user.id}")
        return
    
    if event.old_chat_member.status not in ["member", "administrator", "restricted"] and event.new_chat_member.status in ["member", "administrator"]:
        text_log = (f"{chat.id} | Бот добавлен в группу {chat.title}")

        text = (
            "🏰 " + i18n.text.other.bot.added() + "\n\n"
        )

        kb.button(text="❓ " + i18n.button.other.bot.help(), switch_inline_query_current_chat=i18n.button.other.bot.help())
        kb.button(text="🚶‍➡️ " + i18n.button.other.bot.inspect(), switch_inline_query_current_chat=i18n.button.other.bot.inspect())

        if event.new_chat_member.status == "member":
            text += "\n\n⚠️ " + i18n.text.other.bot.added.no_admin()
            text_log += " без прав администратора!"
        
    
    elif event.new_chat_member.status == "administrator" and event.old_chat_member.status in ["member", "restricted"]:
        text = "✅ " + i18n.text.other.bot.promoted()
        text_log = f"{chat.id} | Бот назначен администратором"
    
    elif event.new_chat_member.status in ["member", "restricted"] and event.old_chat_member.status == "administrator":
        text = "⚠️ " + i18n.text.other.bot.added.no_admin()
        text_log = f"{chat.id} | Бот снят с администратора"
    
    await event.answer(text, reply_markup=kb.as_markup())
    log.debug(text_log)


@fuzzy("мой айди", "my id", "мій айді", "мой ид", "мій ід")
@router.message(or_f(Command("my_id"), F.text.lower().in_({"мой айди", "мой ид", f"@{settings.BOT_USERNAME} мой айди", "my id", f"@{settings.BOT_USERNAME} my id", "мій айді", "мій ід", f"@{settings.BOT_USERNAME} мій айді", f"@{settings.BOT_USERNAME} мій ід"})))
async def my_id_command(message: types.Message, i18n: TranslatorRunner):
    #* Показать ID пользователя
    user = await core.user_getOrCreate(message.from_user)
    await show_id_menu(message, user, i18n)
    
async def show_id_menu(message: types.Message, user: models.User, i18n: TranslatorRunner = None):
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
            f"🆔 {i18n.text.settler.id.internal()}: {user.id}\n"
            f"💬 {i18n.text.settler.id.telegram()}: {user.telegram_id}\n"
        )
    await message.answer(text)


@fuzzy("лик", "мой лик", "my profile", "моя подоба")
@router.message(or_f(Command("me"), F.text.lower().in_({"лик", f"@{settings.BOT_USERNAME} лик", "мой лик", f"@{settings.BOT_USERNAME} мой лик", "my profile", f"@{settings.BOT_USERNAME} my profile", "моя подоба", f"@{settings.BOT_USERNAME} моя подоба"})))
async def me_command(message: types.Message, i18n: TranslatorRunner):
    #* Профиль поселенца
    user = await core.user_getOrCreate(message.from_user)

    compact_style = user.compact_style
    kb = InlineKeyboardBuilder()

    if message.chat.type == "supergroup" or message.chat.type == "group":
        settlement = await core.settlement_getOrCreate(message.chat)
        settler = await core.settler_getOrCreate(user, settlement)
        craft_text = f"{settler.profession.emoji} {settler.profession.name}" if settler.profession else "❓ " + i18n.text.settler.profile.craft.none()
        can_choose, when = utils.can_choose_craft(settler.last_profession_change)
        can_work, work_countdown = core.settler_canWorkNow(settler)
        
        if compact_style:
            text = (
                f"👤 <b>{user.name}</b> — {craft_text}\n"
                f"💡 {settler.level} — {settler.emoji} <b>{settler.rank}</b>\n"
                f"🗂 <b>{round(settler.exp)}/{round(settler.target_exp)}</b> | "
                f"📄 {f'<b>{settler.quote}/{settler.target_quote}</b>' if not settler.quote_is_completed else f'{settler.target_quote}/{settler.target_quote}'} {'(⏳) ' if settler.overtime_is_toggled and not settler.quote_is_completed else ''}| "
                f"💰 <b>{round(settler.balance)}</b>\n"
                f"\n{(settler.profession.emoji + ': <b>' + work_countdown + '</b> 🕒') if (settler.profession and not can_work) else ((settler.profession.emoji + ': ✅') if settler.profession else '')}"
            )

            kb.button(text="🪭", switch_inline_query_current_chat="Обличья")
            kb.button(text="📦", switch_inline_query_current_chat="Скарб")
            kb.button(text="🕒", switch_inline_query_current_chat="Страда")
            kb.button(text=f"{settler.profession.emoji}", switch_inline_query_current_chat="Трудиться") if settler.profession and can_work else None
            kb.button(text="💼", switch_inline_query_current_chat="Выбрать ремесло") if can_choose else None
            
        else:
            overtime_hint = f" (⏳ {i18n.text.settler.profile.overtime.hint()})" if settler.overtime_is_toggled and not settler.quote_is_completed else ""
            quote_display = f"<b>{settler.quote}/{settler.target_quote}</b>" if not settler.quote_is_completed else f"{settler.target_quote}/{settler.target_quote}"
            text = (
                f"👤 <b>{user.name}</b>\n"
                f"🛠 {i18n.text.settler.profile.full.craft()}: {craft_text}\n"
                f"💡 {i18n.text.settler.profile.full.level()}: {settler.level}\n"
                f"🗂 {i18n.text.settler.profile.full.exp()}: {round(settler.exp)}/{round(settler.target_exp)}\n"
                f"🏷 {i18n.text.settler.profile.full.rank()}: {settler.emoji} {settler.rank}\n"
                f"📄 {i18n.text.settler.profile.full.quote()}: {quote_display}{overtime_hint}\n"
                f"💰 {i18n.text.settler.profile.full.balance()}: {format_count(round(settler.balance), 'куна')}\n"
                f"\n{(settler.profession.emoji + ' ' + i18n.text.settler.profile.work.cooldown(countdown=work_countdown) + ' 🕒') if (settler.profession and not can_work) else ((settler.profession.emoji + ' ' + i18n.text.settler.profile.work.ready() + ' ✅') if settler.profession else '')} "
            )

            kb.button(text="🪭 " + i18n.button.settler.cosmetics(), switch_inline_query_current_chat="Обличья")
            kb.button(text="📦 " + i18n.button.settler.inventory(), switch_inline_query_current_chat="Скарб")
            kb.button(text="🕒 " + i18n.button.settler.overtime(), switch_inline_query_current_chat="Страда")
            kb.button(text=f"{settler.profession.emoji} " + i18n.button.settler.work(), switch_inline_query_current_chat="Трудиться") if settler.profession and can_work else None
            kb.button(text="💼 " + i18n.button.settler.choose_craft(), switch_inline_query_current_chat="Выбрать ремесло") if can_choose else None
        
        kb.adjust(2)
        await message.answer(text, reply_markup=kb.as_markup())

    elif message.chat.type == "private":
        await show_id_menu(message, user, i18n)


@fuzzy("настройки", "settings", "налаштування")
@router.message(or_f(Command("settings"), F.text.lower().in_({"настройки", f"@{settings.BOT_USERNAME} настройки", "settings", f"@{settings.BOT_USERNAME} settings", "налаштування", f"@{settings.BOT_USERNAME} налаштування"})))
async def settings_command(message: types.Message, i18n: TranslatorRunner):
    #* Настройки пользователя
    user = await core.user_getOrCreate(message.from_user)
    await show_settings_menu(message, user, i18n=i18n)
    
@router.callback_query(F.data.startswith("settings:"))
async def settings_callback(callback: types.CallbackQuery, i18n: TranslatorRunner):
    #* Callback-кнопки настроек
    if callback.message.reply_to_message and callback.from_user.id != callback.message.reply_to_message.from_user.id:
        await callback.answer("⚠️ " + i18n.callback.common.dont_touch(), True)
        return
    
    user = await core.user_getOrCreate(callback.from_user)
    menu = callback.data.split(":", 1)[1]

    await show_settings_menu(callback.message, user, menu, callback, i18n)

@dataclass
class SettingConf:
    emoji: str
    label_key: str
    is_boolean: bool = True
    on_emoji: str = "✅"
    off_emoji: str = "☑️"
    on_text_key: str = "common-on"
    off_text_key: str = "common-off"
    options_map: dict[str, str] = field(default_factory=dict)

SETTINGS_MAP = {
    "compact_style": SettingConf(
        "🎩", 
        "constant-settings-label-style",
        on_emoji="🤏", 
        off_emoji="🤲", 
        on_text_key="constant-settings-style-compact",
        off_text_key="constant-settings-style-full"
    ),
    "show_hints": SettingConf(
        "ℹ️", 
        "constant-settings-label-hints", 
        on_text_key="constant-settings-common-enabled", 
        off_text_key="constant-settings-common-disabled"
    ),
    "allow_typos": SettingConf(
        "✍️", 
        "constant-settings-label-typos", 
        on_text_key="constant-settings-common-account", 
        off_text_key="constant-settings-common-ignore"
    ),
    "timezone": SettingConf("🌍", "constant-settings-label-timezone", is_boolean=False),
    "language": SettingConf("🗣", "constant-settings-label-language", is_boolean=False, options_map=LANGUAGES_MAP),
}

async def show_settings_menu(message: types.Message, user: models.User, submenu: str = None, callback: types.CallbackQuery = None, i18n: TranslatorRunner = None):
    kb = InlineKeyboardBuilder()
    
    current_conf = SETTINGS_MAP.get(submenu)
    menu_label_text = i18n.get(current_conf.label_key) if current_conf else ""

    async with SessionLocal() as session:
        user = await session.merge(user)
        
        if current_conf and current_conf.is_boolean:
            current_val = getattr(user, submenu)
            new_val = not current_val
            setattr(user, submenu, new_val)
            
            key_to_translate = current_conf.on_text_key if new_val else current_conf.off_text_key
            status_text = i18n.get(key_to_translate)

            toast_text = f"{current_conf.emoji} {menu_label_text} > {status_text}"
            
            log.debug(f"{user.telegram_id} | {current_conf.emoji} {submenu} > {new_val}")
            
            await session.commit()
            if callback:
                await callback.answer(toast_text)
            
            submenu = None 

    if submenu == "timezone":
        last_change = arrow.get(user.last_tz_change) or arrow.get(datetime.min)
        unlock_time = last_change.shift(days=settings.TZ_CHANGE_COOLDOWN_DAYS)
        now = arrow.now()
        
        if now < unlock_time:
            time_left = utils.format_relative_time(unlock_time, now)
            await callback.answer("⏳ " + i18n.callback.settings.timezone.error.locked(time_left=time_left), show_alert=True)
            return

        determine_text = "📍 " + i18n.button.settings.timezone.determine()
        if message.chat.type == "private":
            kb.button(text=determine_text, callback_data="ask_location", style="primary")
        else:
            kb.button(text=determine_text, url=f"https://t.me/{settings.BOT_USERNAME}?start=menu_settings_timezone", style="primary")
        
        kb.button(text="🔙 " + i18n.button.common.back(), callback_data="settings:default")

        text = f"{current_conf.emoji} <b>{menu_label_text}</b>\n\n" + i18n.text.settings.timezone.title(
            timezone=str(user.timezone or "UTC"),
            cooldown=settings.TZ_CHANGE_COOLDOWN_DAYS
        )
        
        if callback: await callback.answer()

    elif submenu == "language":
        for code, name in LANGUAGES_MAP.items():
            is_selected = (user.language == code)
            style = "success" if is_selected else "primary"
            btn_text = f"✅ {name}" if is_selected else name
            
            kb.button(text=btn_text, callback_data=f"set_lang:{code}", style=style)
        
        kb.button(text="🔙 " + i18n.button.common.back(), callback_data="settings:default")
        kb.adjust(2)

        tg_user = callback.from_user if callback else message.from_user
        lang_code = user.language if user.language is not None else tg_user.language_code
        lang_name = LANGUAGES_MAP.get(lang_code, lang_code)

        text = f"{current_conf.emoji} <b>{menu_label_text}</b>\n" + i18n.text.settings.language.title(
            lang_name=lang_name
        )
        
        if callback: await callback.answer()

    elif not submenu or submenu == "default":
        lines = ["⚙️ <b>" + i18n.text.settings.title() + "</b>\n" + i18n.text.settings.subtitle(), ""]
        
        for key, item_conf in SETTINGS_MAP.items():
            val = getattr(user, key)
            
            item_label = i18n.get(item_conf.label_key)
            
            btn_text = f"{item_conf.emoji}"
            if not user.compact_style:
                btn_text += f" {item_label}"
            
            if item_conf.is_boolean:
                status_key = item_conf.on_text_key if val else item_conf.off_text_key
                display_val = i18n.get(status_key)
                
                status_emoji = item_conf.on_emoji if val else item_conf.off_emoji
                
                btn_text += f": {status_emoji}"
                
                lines.append(f"{item_conf.emoji} {item_label}: {status_emoji} <b>{display_val}</b>")
            else:
                if item_conf.options_map and val in item_conf.options_map:
                    display_val = item_conf.options_map[val]
                else:
                    display_val = val if val is not None else i18n.text.common.none()
                
                lines.append(f"{item_conf.emoji} {item_label}: <b>{display_val}</b>")
            
            style = "success" if (item_conf.is_boolean and val) else "primary"
            kb.button(text=btn_text, callback_data=f"settings:{key}", style=style)

        kb.adjust(2)
        text = "\n".join(lines)
        
    if callback:
        try:
            await message.edit_text(text=text, reply_markup=kb.as_markup())
        except TelegramBadRequest:
            await message.edit_reply_markup(reply_markup=kb.as_markup())
    else:
        await message.reply(text=text, reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data == "ask_location")
async def ask_location_callback(callback: types.CallbackQuery, i18n: TranslatorRunner):
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="📍 " + i18n.button.settings.timezone.share_location(), request_location=True), types.KeyboardButton(text=i18n.button.other.bot.cancel())]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.delete()
    await callback.message.answer(i18n.text.settings.timezone.determine(), reply_markup=kb)

@router.message(and_f(F.chat.type == "private", F.location))
async def location_handler(message: types.Message, i18n: TranslatorRunner):
    lat = message.location.latitude
    lon = message.location.longitude
    
    timezone = tf.timezone_at(lng=lon, lat=lat)
    
    if not timezone:
        await message.reply(
            "⚠️ " + i18n.text.settings.timezone.error.determine(), 
            reply_markup=InlineKeyboardBuilder().button(text="🔙 " + i18n.button.common.back(), callback_data="settings:timezone").as_markup()
        )
        return
    
    await message.reply(
        "✅ " + i18n.text.settings.timezone.determined(timezone=timezone), 
        reply_markup=InlineKeyboardBuilder().button(text=i18n.button.settings.timezone.set(), callback_data=f"set_tz:{timezone}", style="success").as_markup()
    )

@router.callback_query(F.data.startswith("set_tz:"))
async def set_tz_callback(callback: types.CallbackQuery, i18n: TranslatorRunner):    
    tz_name = callback.data.split(":")[1]

    async with SessionLocal() as session:
        result = await session.execute(select(models.User).where(models.User.telegram_id == callback.from_user.id))
        user = result.scalars().first()
        last_change = arrow.get(user.last_tz_change) or arrow.get(datetime.min)
        unlock_time = last_change.shift(days=settings.TZ_CHANGE_COOLDOWN_DAYS)
        now = arrow.now()
        if now < unlock_time:
            time_left = utils.format_relative_time(unlock_time, now)
            await callback.answer("⏳ " + i18n.callback.settings.timezone.error.locked(time_left=time_left), show_alert=True)
            return

        user.timezone = tz_name
        user.last_tz_change = datetime.now()
        await session.commit()
    
    log.debug(f"{user.telegram_id} | 🌍 timezone > {tz_name}")

    await callback.answer("✅ " + i18n.callback.settings.timezone.changed())
    await callback.message.edit_reply_markup()
    await callback.message.edit_text(text="✅ " + i18n.text.settings.timezone.changed(tz_name=tz_name), reply_markup=InlineKeyboardBuilder().button(text="🔙 " + i18n.button.common.back(), callback_data="settings:default").as_markup())


@router.callback_query(F.data.startswith("set_lang:"))
async def set_language(callback: types.CallbackQuery, i18n_middleware: I18nMiddleware, i18n: TranslatorRunner):
    if callback.from_user.id != callback.message.reply_to_message.from_user.id:
        await callback.answer("⚠️ " + i18n.callback.common.dont_touch(), True)
        return
    
    lang_code = callback.data.split(":")[1]
    if lang_code not in LANGUAGES_MAP:
        await callback.answer("⚠️ " + i18n.callback.other.lang_not_found(lang_code=lang_code), show_alert=True)
        return

    async with SessionLocal() as session:
        user = await core.user_getOrCreate(callback.from_user, session=session)
        user.language = lang_code
        await session.commit()
    
    i18n_middleware.cache[user.telegram_id] = lang_code
    i18n = i18n_middleware.hub.get_translator_by_locale(lang_code)
    
    lang_name = LANGUAGES_MAP.get(lang_code, lang_code)

    log.debug(f"{user.telegram_id} | 🗣 language > {lang_code}")
    await callback.answer("✅ " + i18n.callback.settings.language.changed(lang_name=lang_name))
    await show_settings_menu(callback.message, user, "language", callback, i18n)


@router.message(F.text.lower() == "отмена")
async def cancel_location(message: types.Message, i18n: TranslatorRunner):
    await message.answer(i18n.text.other.cancel(), reply_markup=types.ReplyKeyboardRemove())

@fuzzy("help", "помощь", "допомога")
@router.message(or_f(Command("help"), F.text.lower().in_({"помощь", f"@{settings.BOT_USERNAME} помощь", "help", f"@{settings.BOT_USERNAME} help", "допомога", f"@{settings.BOT_USERNAME} допомога"})))
async def help_command(message: types.Message, i18n: TranslatorRunner):
    #* Помощь и руководство по игре
    help_text = (
        "🛖 " + i18n.text.other.help()
    )
    await message.answer(help_text)



@router.message(or_f(and_f(F.chat.type == "private", CommandStart()), F.chat.type == "private"))
async def private_handler(message: types.Message, command: CommandObject = None, i18n: TranslatorRunner = None):
    #* Личные сообщения и рефералы
    user = await core.user_getOrCreate(message.from_user)
    if command and command.args:
        args = command.args
        args_list = args.split("_")
        
        if args.startswith("ref_"):
            referrer_id = args_list[1]
            await message.answer("👋 " + i18n.text.other.referral() + f"{referrer_id}")
            return
        
        if args.startswith("menu_"):
            _, menu, submenu = args_list + [None]*(3 - len(args_list))
            log.debug(f"{message.from_user.id} | Вызвано меню: {menu} -> {submenu}")
            if menu == "settings":
                await show_settings_menu(message, user, submenu, i18n=i18n)
            elif menu == "id":
                await show_id_menu(message, user)

            return
        
        # elif args.startswith("work_"):
        # _, work_id,  = args.split("_")

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ " + i18n.button.other.add(), url=f"https://t.me/{settings.BOT_USERNAME}?startgroup=new")
    kb.button(text="⚙️ " + i18n.text.settings.title(), callback_data="settings:default")
    
    await message.reply(text="🛖 " + i18n.text.other.private.greeting(), reply_markup=kb.as_markup())



# ================= Group chats ================

@fuzzy("осмотреть город", "осмотреть поселение", "мое поселение", "моё поселение", "town")
@router.message(or_f(CommandStart(), Command("town"), F.text.lower().in_({"осмотреть город", f"@{settings.BOT_USERNAME} осмотреть город", "осмотреть поселение", f"@{settings.BOT_USERNAME} осмотреть поселение", "town", f"@{settings.BOT_USERNAME} town"})))
async def start_command(message: types.Message, i18n: TranslatorRunner):
    #* Осмотр поселения / старт игры
    async with SessionLocal() as session:
        user = await core.user_getOrCreate(message.from_user, session=session)
        settlement = await core.settlement_getOrCreate(message.chat, session=session)
        settler = await core.settler_getOrCreate(user, settlement, session=session)

        await session.refresh(settlement, ['members'])

    kb = InlineKeyboardBuilder()
    kb.button(text="👤 " + i18n.button.settlement.profile(), switch_inline_query_current_chat="Лик")
    if settlement.owner.telegram_id == message.from_user.id:
        kb.row(InlineKeyboardButton(text="📜 " + i18n.button.settlement.rename(), switch_inline_query_current_chat="Переименовать поселение"), InlineKeyboardButton(text="🏗 " + i18n.button.settlement.buildings(), switch_inline_query_current_chat="Городские постройки"))

    owner_name = settlement.owner.name or (i18n.text.settlement.view.owner.fallback(telegram_id=settlement.owner.telegram_id) if settlement.owner else i18n.text.settlement.view.owner.missing())
    text = (
        f"<b>{settlement.name}</b> (основан {utils.format_relative_time(settlement.created_at)})\n"
        f"👥{len(settlement.members)} 👑 <b>{owner_name}</b>"
    )
    await message.answer(text, reply_markup=kb.as_markup())

@router.message(or_f(Command("name_settlement"), F.text.lower().startswith(("назвать поселение", f"@{settings.BOT_USERNAME} назвать поселение", "переименовать поселение", f"@{settings.BOT_USERNAME} переименовать поселение", "name settlement", f"@{settings.BOT_USERNAME} name settlement", "назвати поселення", f"@{settings.BOT_USERNAME} назвати поселення"))))
async def name_settlement(message: types.Message, command: CommandObject = None, i18n: TranslatorRunner = None):
    #* Смена имени поселения
    raw_new_name = ""
    if command:
        raw_new_name = command.args
    else:
        txt = message.text
        for trigger in ["назвать поселение", f"@{settings.BOT_USERNAME} назвать поселение", "переименовать поселение", f"@{settings.BOT_USERNAME} переименовать поселение", "name settlement", f"@{settings.BOT_USERNAME} name settlement", "назвати поселення", f"@{settings.BOT_USERNAME} назвати поселення"]:
            if txt.lower().startswith(trigger):
                raw_new_name = txt[len(trigger):].strip()
                break
    
    if not raw_new_name:
        await message.answer("⚠️ " + i18n.text.settlement.rename.empty())
        return

    if len(raw_new_name) > 30 or len(raw_new_name) < 3:
        await message.answer("⚠️ " + i18n.text.settlement.rename.length())
        return

    new_name = html.escape(raw_new_name)

    user = await core.user_getOrCreate(message.from_user)
    
    async with SessionLocal() as session:
        result = await session.execute(
            select(models.Settlement)
            .options(selectinload(models.Settlement.owner))
            .where(models.Settlement.chat_id == message.chat.id)
        )
        settlement = result.scalars().first()

        if not settlement:
            return

        if not settlement.owner or settlement.owner.telegram_id != message.from_user.id:
            await message.answer("⚠️ " + i18n.text.settlement.rename.not_owner())
            return

        now = arrow.now()
        last_change = arrow.get(settlement.last_name_change) if settlement.last_name_change else arrow.get(datetime.min)
        cooldown_expires = last_change.shift(hours=settings.SETTLEMENT_NAME_CHANGE_COOLDOWN_HOURS)

        if now < cooldown_expires:
            remaining_time = utils.format_relative_time(cooldown_expires, now)
            await message.answer(
                "📜 " + i18n.text.settlement.rename.cooldown(time_left=remaining_time)
            )
            return

        old_name = settlement.name
        if new_name == old_name:
            await message.answer(
                "📜 " + i18n.text.settlement.rename.same(old_name=old_name, new_name=new_name)
            )
            return
        
        settlement.name = new_name
        settlement.last_name_change = datetime.now()
        
        await session.commit()
        
        await message.answer(
            "📜 " + i18n.text.settlement.rename.success(old_name=old_name, new_name=new_name)
        )
        log.debug(f"{message.chat.id} | Переименовано поселение {old_name} -> {new_name}")


@fuzzy("городские постройки", "town buildings", "міські будівлі")
@router.message(or_f(Command("town_buildings"), F.text.lower().in_({"городские постройки", f"@{settings.BOT_USERNAME} городские постройки", "town buildings", f"@{settings.BOT_USERNAME} town buildings", "міські будівлі", f"@{settings.BOT_USERNAME} міські будівлі"})))
async def town_buildings_command(message: types.Message, i18n: TranslatorRunner):
    #* Городские постройки (только для мэра)
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)

    await show_buildings_menu(message, user, settlement, "town", i18n=i18n)

@fuzzy("мои постройки", "my buildings", "мої будівлі")
@router.message(or_f(Command("my_buildings"), F.text.lower().in_({"мои постройки", f"@{settings.BOT_USERNAME} мои постройки", "my buildings", f"@{settings.BOT_USERNAME} my buildings", "мої будівлі", f"@{settings.BOT_USERNAME} мої будівлі"})))
async def my_buildings_command(message: types.Message, i18n: TranslatorRunner):
    #* Личные постройки
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    
    await show_buildings_menu(message, user, settlement, "my", i18n=i18n)

async def show_buildings_menu(message: types.Message, user: models.User, settlement: models.Settlement, scope: str, is_edit: bool = False, i18n: TranslatorRunner = None):
    """Общая функция для показа меню списка построек"""
    settler = await core.settler_getOrCreate(user, settlement)
    
    async with SessionLocal() as session:
        buildings = await core.building_getByScope(settlement, settler, scope, session)
        
        text = ("🏙 " + i18n.text.buildings.town.title()) if scope == "town" else ("🏡 " + i18n.text.buildings.my.title()) if i18n else ("🏙 <b>Городские постройки</b>" if scope == "town" else "🏡 <b>Мои постройки</b>")
        
        kb = InlineKeyboardBuilder()
        
        if not buildings:
            text += "\n\n🕸 " + (i18n.text.buildings.empty() if i18n else "Пока здесь пусто.")
        else:
            for b in buildings:
                time_left = utils.format_relative_time(b.under_construction_until) if not b.is_ready else None
                if b.is_ready:
                    status = "✅" if user.compact_style else "✅ " + (i18n.text.buildings.status.active() if i18n else "Активно")
                else:
                    status = f"⏳ ({time_left})" if user.compact_style else "⏳ " + (i18n.text.buildings.status.construction(time_left=time_left) if i18n else f"Построится {time_left}")
                text += f"\n\n{b.type.emoji} <b>{b.type.name}</b> ({b.level}/{b.type.max_level}):" + f"\n{status}\n" if not user.compact_style else f"{status}\n"
                btn_text = f"{b.type.emoji} {b.type.name} ({'✅' if b.is_ready else '⏳'})"
                kb.button(text=btn_text, callback_data=f"bld_view:{b.id}:{scope}")
            
        kb.adjust(2)
        
        kb.row(InlineKeyboardButton(text="🏗 " + (i18n.button.buildings.blueprints() if i18n else "Чертежи"), callback_data=f"bld_list:{scope}"))
        
        if is_edit:
            await message.edit_text(text, reply_markup=kb.as_markup())
        else:
            await message.answer(text, reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("bld_"))
async def buildings_callback(callback: types.CallbackQuery, i18n: TranslatorRunner):
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat)
    settler = await core.settler_getOrCreate(user, settlement)
    
    parts = callback.data.split(":")
    action = parts[0]
    
    compact_style = user.compact_style
    
    # === ВОЗВРАТ В МЕНЮ ===
    if action == "bld_menu":
        scope = parts[1]
        await show_buildings_menu(callback.message, user, settlement, scope, is_edit=True, i18n=i18n)

    # === КАТАЛОГ ЧЕРТЕЖЕЙ ===
    elif action == "bld_list":
        scope = parts[1]
        
        async with SessionLocal() as session:
            stmt = select(models.BuildingType)
            all_types = (await session.execute(stmt)).scalars().all()
            
            text = f"🏗 " + i18n.text.buildings.catalog.title() + f" ({(i18n.text.buildings.catalog.scope.town() if not compact_style else '🏙') if scope == 'town' else (i18n.text.buildings.catalog.scope.my() if not compact_style else '🏡')})\n\n"
            
            kb = InlineKeyboardBuilder()
            buttons = []
            
            for bt in all_types:
                if scope == "town" and bt.is_private:
                    continue
                if scope == "my" and not bt.is_private:
                    continue
                
                is_prof_enough, _, is_res_enough, _ = await core.building_checkRequirements(settlement, settler, bt, session, compact_style)
                
                status_icon = "☑️" if is_prof_enough and is_res_enough else "🔒"
                if compact_style:
                    buttons.append(InlineKeyboardButton(text=f"[{status_icon}] {bt.emoji}", callback_data=f"bld_preview:{bt.id}:{scope}"))
                else:
                    buttons.append(InlineKeyboardButton(text=f"[{status_icon}] {bt.emoji} {bt.name}", callback_data=f"bld_preview:{bt.id}:{scope}"))
            
            if not buttons:
                text += "🕸 " + i18n.text.buildings.empty()
            
            kb.row(*buttons, width=2)
            kb.row(InlineKeyboardButton(text="🔙 " + i18n.button.common.back(), callback_data=f"bld_menu:{scope}"))
            
            await callback.message.edit_text(text, reply_markup=kb.as_markup())
    
    # === ПРОСМОТР КОНКРЕТНОЙ ПОСТРОЙКИ ===
    elif action == "bld_view":
        building_id = int(parts[1])
        scope = parts[2]
        
        async with SessionLocal() as session:
            stmt = select(models.Building).options(selectinload(models.Building.type)).where(models.Building.id == building_id)
            building = (await session.execute(stmt)).scalars().first()
            
            if not building:
                await callback.answer("🏚 " + i18n.text.buildings.not_found(), show_alert=True)
                await show_buildings_menu(callback.message, user, settlement, scope, is_edit=True, i18n=i18n)
                return

            if compact_style:
                status_text = "⚪️" if building.is_ready else f"🔨 <b>{utils.format_relative_time(building.under_construction_until)}</b>"
            else:
                status_text = ("⚪️ " + i18n.text.buildings.view.active()) if building.is_ready else ("🔨 " + i18n.text.buildings.view.construction(time_left=utils.format_relative_time(building.under_construction_until)))
            
            has_bonuses, bonuses = utils.format_bonuses_text(building.type.bonuses)
            
            text = (
                f"{building.type.emoji} <b>{building.type.name}</b> ({building.level}/{building.type.max_level}) {status_text}\n"
                f"{building.type.description}\n\n"
                f"🎁 " + i18n.text.buildings.view.bonuses() + f"\n{bonuses}"
            )
            
            kb = InlineKeyboardBuilder()
            kb.button(text="🔙 " + i18n.button.common.back(), callback_data=f"bld_menu:{scope}")
            
            await callback.message.edit_text(text, reply_markup=kb.as_markup())

    # === ПРЕВЬЮ ПЕРЕД СТРОЙКОЙ ===
    elif action == "bld_preview":
        bt_id = int(parts[1])
        scope = parts[2]

        cost_text = []
        is_res_enough = True
        is_mayor = True
        if scope == "town" and not settlement.owner or settlement.owner.telegram_id != callback.from_user.id:
            is_mayor = False
    
        async with SessionLocal() as session:
            stmt = select(models.BuildingType).where(models.BuildingType.id == bt_id)
            bt = (await session.execute(stmt)).scalars().first()
                      
            is_prof_enough, prof_text, is_res_enough, res_text = await core.building_checkRequirements(
                settlement, settler, bt, session, compact_style
            )
            has_bonuses, bonuses = utils.format_bonuses_text(bt.bonuses)

            lines = [
                f"{bt.emoji} <b>{bt.name}</b>",
                f"{bt.description}",
                ""
            ]

            req_content = "\n".join(filter(None, [prof_text, res_text]))

            if req_content:
                lines.append(f"🔨 " + i18n.text.buildings.preview.requirements())
                lines.append(f"{req_content}")
                lines.append("")

            if has_bonuses:
                lines.append(f"🎁 " + i18n.text.buildings.preview.bonuses())
                lines.append(f"{bonuses}")
                lines.append("")

            lines.append("⏳ " + i18n.text.buildings.preview.time(time=bt.construction_time))

            text = "\n".join(lines)

            kb = InlineKeyboardBuilder()

            if is_res_enough and is_prof_enough:
                if (scope != "town" or is_mayor):
                    kb.button(
                        text="🔨 " + i18n.button.buildings.build(), 
                        callback_data=f"bld_start:{bt.id}:{scope}"
                    )
                
            
            kb.row(InlineKeyboardButton(text="🔙 " + i18n.button.buildings.back_blueprints(), callback_data=f"bld_list:{scope}"))
            
            await callback.message.edit_text(text, reply_markup=kb.as_markup())

    # === ЗАПУСК СТРОЙКИ ===
    elif action == "bld_start":
        bt_id = int(parts[1])
        scope = parts[2]

        if scope == "town" and (not settlement.owner or settlement.owner.telegram_id != callback.from_user.id):
            await callback.answer("⚠️ " + i18n.callback.buildings.build.only_mayor(), show_alert=True)
            await show_buildings_menu(callback.message, user, settlement, scope, is_edit=True, i18n=i18n)
            return
        
        async with SessionLocal() as session:
            is_prof_enough, msg = await core.building_startBuilding(settler, bt_id, scope, session)
            
            if is_prof_enough:
                await callback.answer("✅ " + i18n.callback.buildings.build.success(), show_alert=False)
                await show_buildings_menu(callback.message, user, settlement, scope, is_edit=True, i18n=i18n)
            else:
                await callback.answer(f"{msg}", show_alert=True)


@fuzzy("бонусы", "bonuses", "эффекты", "бонуси","ефекти")
@router.message(or_f(Command("bonuses"), Command("effects"), F.text.lower().in_({"бонусы", f"@{settings.BOT_USERNAME} бонусы", "bonuses", "эффекты", f"@{settings.BOT_USERNAME} эффекты", f"@{settings.BOT_USERNAME} bonuses", "бонуси", f"@{settings.BOT_USERNAME} бонуси", "ефекти", f"@{settings.BOT_USERNAME} ефекти"})))
async def bonuses_command(message: types.Message, i18n: TranslatorRunner):
    #* Просмотр активных эффектов
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    async with SessionLocal() as session:
        bonuses = core.BonusSet()

        personal, settlement = await core.setter_getBonuses(settler, session)
        
        bonuses.merge(personal)
        bonuses.merge(settlement)
        
        data = bonuses.to_dict()
        
        has_bonuses, text_bonuses = utils.format_bonuses_text(data)
    
    text = f"✨ " + i18n.text.other.effects.title(name=user.name) + "\n\n"
    
    if not has_bonuses:
        text += i18n.text.other.effects.empty()
        if user.show_hints:
            text += "\n\nℹ️ " + i18n.text.other.effects.hint()
    else:
        text += text_bonuses

    await message.answer(text)


@fuzzy("лепота", "обличья", "косметика", "cosmetics", "оздоба", "врода")
@router.message(or_f(Command("cosmetics"), F.text.lower().in_({"лепота", f"@{settings.BOT_USERNAME} лепота", "обличья", f"@{settings.BOT_USERNAME} обличья", "оздоба", f"@{settings.BOT_USERNAME} оздоба", "врода", f"@{settings.BOT_USERNAME} врода", "cosmetics", f"@{settings.BOT_USERNAME} cosmetics"})))
async def cosmetics_command(message: types.Message, i18n: TranslatorRunner):
    #* Лепота поселенца
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)
    
    if not settler:
        log.error(f"Не удалось получить или создать поселенца для пользователя {message.from_user.id} в функции cosmetics_command()")
        await message.answer("❌ " + i18n.text.settler.error.not_found())
        return

    text = f"🪭 " + i18n.text.settler.cosmetics.title() + f"\n\n🎭 " + i18n.text.settler.cosmetics.current(emoji=settler.emoji)
    
    all_emojis = []
    if settler.rank_emoji_available:
        all_emojis.extend(settler.rank_emoji_available)
    if settler.special_emoji_available:
        all_emojis.extend(settler.special_emoji_available)
    
    all_emojis = list(dict.fromkeys(all_emojis))
    
    if not all_emojis:
        text += "\n❌ " + i18n.text.settler.cosmetics.none()
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
async def cosmetics_select(callback: types.CallbackQuery, i18n: TranslatorRunner):
    #* Выбор эмодзи косметики
    if callback.from_user.id != callback.message.reply_to_message.from_user.id:
        await callback.answer("⚠️ " + i18n.callback.common.dont_touch(), True)
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

    await callback.answer(text=f"🪭 " + i18n.text.settler.cosmetics.accepted(emoji=emoji))
    
    
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
    await callback.message.edit_text(text=f"🪭 " + i18n.text.settler.cosmetics.title() + f"\n\n🎭 " + i18n.text.settler.cosmetics.current(emoji=db_settler.emoji), reply_markup=kb)


@fuzzy("страда", "overtime", "понадмір", "зайва міра")
@router.message(or_f(Command("overtime"), F.text.lower().in_({"страда", f"@{settings.BOT_USERNAME} страда", "overtime", f"@{settings.BOT_USERNAME} overtime", "понадмір", f"@{settings.BOT_USERNAME} понадмір", "зайва міра", f"@{settings.BOT_USERNAME} зайва міра"})))
async def overtime_command(message: types.Message, i18n: TranslatorRunner):
    #* Страда поселенца
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)
    
    reset_countdown = utils.get_daily_reset_countdown(user.timezone)
    compact_style = user.compact_style
    overtime_count=settler.overtime_count
    quote = settler.quote
    target_quote = settler.target_quote
    buttons = []
    kb = InlineKeyboardBuilder()

    text = f"🕒 " + i18n.text.settler.overtime.title() + "\n"
    text += f"ℹ️ " + i18n.text.settler.overtime.hint(reset_countdown=reset_countdown) + "\n\n" if settler.level < 2 and user.show_hints == True else ""
    if settler.overtime_is_toggled and not settler.quote_is_completed:
        if compact_style:
            text += f"🔘 {overtime_count} (🕒 {reset_countdown}) | 📄 <b>{quote}/{target_quote}</b>"
        else:
            text += i18n.text.settler.overtime.status.active(overtime_count=overtime_count, reset_countdown=reset_countdown, quote=quote, target_quote=target_quote)
    elif not settler.overtime_is_toggled and not settler.quote_is_completed:
        text += "⚠️ " + i18n.text.settler.overtime.status.need_quota()
    else:
        if compact_style:
            text += f"🔘 {overtime_count}"
        else:
            text += i18n.text.settler.overtime.status.inactive(overtime_count=overtime_count)
        buttons.append(InlineKeyboardButton(text="🕒 " + i18n.button.settler.overtime.take(), callback_data="overtime_take"))

    kb.row(*buttons)
    await message.reply(text, reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data == "overtime_take")
async def overtime_take(callback: types.CallbackQuery, i18n: TranslatorRunner):
    #* Взять страду
    async with SessionLocal() as session:
        if callback.from_user.id != callback.message.reply_to_message.from_user.id:
            await callback.answer("⚠️ " + i18n.callback.common.dont_touch(), True)
            return

        user = await core.user_getOrCreate(callback.from_user)
        settlement = await core.settlement_getOrCreate(callback.message.chat)
        settler = await core.settler_getOrCreate(user, settlement)

        if settler.overtime_is_toggled and not settler.quote_is_completed:
            await callback.answer("⚠️ " + i18n.callback.settler.overtime.already(), True)
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
        
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 🔄 Страда взята: 0/{new_quote}")
        await session.commit()
        
        reset_countdown = utils.get_daily_reset_countdown(user.timezone)
        await callback.message.edit_text("⏳ " + i18n.text.settler.overtime.taken(new_quote=new_quote, reset_countdown=reset_countdown))


@fuzzy("скарб", "inventory", "інвентар", "инвентарь")
@router.message(or_f(Command("inventory"), F.text.lower().in_({"скарб", f"@{settings.BOT_USERNAME} скарб", "инвентарь", f"@{settings.BOT_USERNAME} инвентарь", "інвентар", f"@{settings.BOT_USERNAME} інвентар", "inventory", f"@{settings.BOT_USERNAME} inventory"})))
async def inventory_command(message: types.Message, i18n: TranslatorRunner):
    #* Скарб поселенца
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    text = f"📦 " + i18n.text.settler.inventory.title() + "\n\n"
    
    async with SessionLocal() as session:
        compact_style = user.compact_style
        result = await session.execute(
            select(models.settler_resources.c.resource_id, models.settler_resources.c.quantity, models.Resource.name, models.Resource.emoji, models.Resource.category)
            .join(models.Resource, models.settler_resources.c.resource_id == models.Resource.id)
            .where(models.settler_resources.c.settler_id == settler.id)
        )
        resources_data = result.all()
        
        if not resources_data:
            text += "❌ " + i18n.text.settler.inventory.empty()
            if settler.level < 5 and user.show_hints == True:
                text += "\n\nℹ️ " + i18n.text.settler.inventory.hint()
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
async def choose_craft_command(message: types.Message, i18n: TranslatorRunner):
    #* Выбор ремесла поселенца
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    async with SessionLocal() as session:
        result = await session.execute(select(models.Profession))
        professions = result.scalars().all()
    
    if not professions:
        await message.answer('❌ ' + i18n.text.craft.no_professions())
        return
    
    can_choose, when = True, ""
    if settler.profession_id:
            can_choose, when = utils.can_choose_craft(settler.last_profession_change)
    
    text = f"💼 " + i18n.text.craft.choose.title() + "\n" + ('⚠️ ' + i18n.text.craft.choose.cooldown(when=when) + '\n' if not can_choose and settler.profession else '') + "\n"
    kb = InlineKeyboardBuilder()

    async with SessionLocal() as session:
        compact_style = user.compact_style
    buttons = []
    for prof in professions:
        if settler.level >= prof.required_level:
            if compact_style:
                text += f"{prof.emoji} <b>{prof.name}:</b> {prof.description}\n{'✅' if settler.profession_id == prof.id else '☑️'} <b>{settler.level}/{prof.required_level}</b>💡\n\n"
            else:
                selected = i18n.text.craft.status.selected() if settler.profession_id == prof.id else i18n.text.craft.status.available()
                req_level = i18n.text.craft.status.required_level()
                text += f"{prof.emoji} <b>{prof.name}:</b> {prof.description}\n{'✅ ' + selected if settler.profession_id == prof.id else '☑️ ' + i18n.text.craft.status.available()} ({req_level} <b>{settler.level}/{prof.required_level}</b>💡)\n\n"
            buttons.append(InlineKeyboardButton(text=f"{prof.emoji} {prof.name}", callback_data=f"select_craft:{prof.id}")) if settler.profession_id != prof.id and can_choose else None
        else:
            if compact_style:
                text += f"{prof.emoji} {prof.name}: {prof.description}\n🔒 {settler.level}/<b>{prof.required_level}</b>💡\n\n"
            else:
                text += f"{prof.emoji} {prof.name}: {prof.description}\n🔒 " + i18n.text.craft.status.locked() + f" ({i18n.text.craft.status.required_level()} {settler.level}/<b>{prof.required_level}</b>💡)\n\n"
    
    kb.row(*buttons, width=2)
    await message.reply(text=text, reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data.startswith("select_craft:"))
async def select_craft_callback(callback: types.CallbackQuery, i18n: TranslatorRunner):
    #* Кнопка выбора ремесла
    prof_id = int(callback.data.split(":")[1])

    async with SessionLocal() as session:
        user = await core.user_getOrCreate(callback.from_user)
        settlement = await core.settlement_getOrCreate(callback.message.chat)
        settler = await core.settler_getOrCreate(user, settlement)

        if callback.from_user.id != callback.message.reply_to_message.from_user.id:
            await callback.answer("⚠️ " + i18n.callback.common.dont_touch(), True)
            return
        
        if settler.profession_id == prof_id:
            await callback.answer("⚠️ " + i18n.callback.craft.already_selected())
            return
        
        prof_result = await session.execute(select(models.Profession).where(models.Profession.id == prof_id))
        profession = prof_result.scalars().first()
        
        if not profession or settler.level < profession.required_level:
            await callback.answer("⚠️ " + i18n.callback.craft.level_too_low())
            return
        if settler.profession_id:
            can_choose, when = utils.can_choose_craft(settler.last_profession_change)
            if not can_choose:
                await callback.answer("⚠️ " + i18n.callback.craft.cooldown(when=when), True)
        
        await session.execute(
            update(models.Settler)
            .where(models.Settler.id == settler.id)
            .values(profession_id=prof_id, last_profession_change=datetime.now())
        )
        await session.commit()
        
        kb = InlineKeyboardBuilder().row(InlineKeyboardButton(text=profession.emoji + " " + i18n.callback.craft.craft(), switch_inline_query_current_chat=i18n.callback.craft.craft()))
        await callback.message.edit_text("✅ " + i18n.text.craft.selected.success(user_name=callback.from_user.full_name, profession_name=profession.name), reply_markup=kb.as_markup())
        log.debug(f"{callback.message.chat.id} | {settler.user_id} | 💼 Выбрано ремесло: {profession.name}")

@fuzzy("трудиться", "craft", "трудитися", "працювати")
@router.message(or_f(Command("craft"), F.text.lower().in_({"трудиться", f"@{settings.BOT_USERNAME} трудиться", "craft", f"@{settings.BOT_USERNAME} craft", "трудитися", f"@{settings.BOT_USERNAME} трудитися", "працювати", f"@{settings.BOT_USERNAME} працювати"})))
async def craft_command(message: types.Message, i18n: TranslatorRunner):
    #* Начало труда поселенца
    user = await core.user_getOrCreate(message.from_user)
    settlement = await core.settlement_getOrCreate(message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    available_works = [
        work for work in models.WORKS_REGISTRY.values()
        if work.profession_id == settler.profession_id or work.profession_id is None
    ]

    if not settler.profession_id:
        await message.answer("⚠️ " + i18n.text.craft.no_profession(), reply_markup=InlineKeyboardBuilder().row(InlineKeyboardButton(text="💼 " + i18n.button.settler.choose_craft(), switch_inline_query_current_chat="Выбрать ремесло")).as_markup())
        return

    if not available_works:
        await message.answer("🕸 " + i18n.text.craft.no_works())
        return
    
    kb = InlineKeyboardBuilder()
    for work in available_works:
        if user.compact_style:
            kb.button(text=f"{work.emoji}", callback_data=f"select_work:{work.id}")
        else:
            kb.button(text=f"{work.emoji} {work.name}", callback_data=f"select_work:{work.id}")
    kb.adjust(2)

    await message.reply(f"{settler.profession.emoji} <b>{settler.profession.name}:</b>", reply_markup=kb.as_markup(), disable_notification=True)

@router.callback_query(F.data.startswith("select_work:"))
async def work_selection_callback(callback: types.CallbackQuery, i18n: TranslatorRunner):
    #* Кнопка выбора труда
    work_id = callback.data.split(":", 1)[1]

    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    if callback.from_user.id != callback.message.reply_to_message.from_user.id:
        await callback.answer("⚠️ " + i18n.callback.common.dont_touch(), True)
        return
    
    work = models.WORKS_REGISTRY.get(work_id)
    if not work:
        await callback.answer("⚠️ " + i18n.callback.craft.work_not_found(), True)
        return
    
    if work.profession_id != settler.profession_id:
        await callback.answer("⚠️ " + i18n.callback.craft.wrong_profession(), True)
        return

    success = await core.settler_startWorkflow(callback, work, user, settler)
    if not success:
        return

@router.callback_query(F.data.startswith("work:"))
async def work_callback(callback: types.CallbackQuery, i18n: TranslatorRunner):
    #* Callback-кнопки для работы
    user = await core.user_getOrCreate(callback.from_user)
    settlement = await core.settlement_getOrCreate(callback.message.chat)
    settler = await core.settler_getOrCreate(user, settlement)

    user_key = f"{callback.message.chat.id}_{user.telegram_id}"
    if not utils.can_click_button(user_key):
        await callback.answer("⏳ " + i18n.callback.common.wait())
        return
    
    remaining = utils.get_work_remaining_time(callback.message.chat.id)
    if remaining <= 0:
        await callback.answer("⏰ " + i18n.callback.common.work.expired.toast(), True)
        await callback.message.edit_text("⏰ " + i18n.text.common.work.expired())
        utils.end_work(callback.message.chat.id)
        active_games.pop(user_key, None)
        return
    
    workflow: Workflow = active_games.get(user_key)
    if not workflow or workflow.game_over:
        await callback.answer("⚠️ " + i18n.callback.common.work.not_found())
        return
    
    parts = callback.data.split(":")
    if len(parts) < 4:
        await callback.answer("⚠️ " + i18n.callback.common.invalid_action())
        return
    
    _, work_id, step_idx_str, *action_parts = parts
    step_idx = int(step_idx_str)
    action = ":".join(action_parts) if action_parts else None
    log.debug(f"{callback.message.chat.id} | {user.id} | 🎭 Работа: {work_id}, Шаг: {step_idx}, Действие: {action}")
    
    work: models.Work = models.WORKS_REGISTRY.get(work_id)
    if not work:
        await callback.answer("⚠️ " + i18n.callback.craft.work_not_found())
        return
    
    if step_idx >= len(workflow.steps):
        await callback.answer("⚠️ " + i18n.callback.common.invalid_step())
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
            reward_text = await utils.format_reward_text(earned)
            await callback.message.edit_text(f"{status_text}\n\n📦 <b>" + i18n.text.common.received() + f":</b>\n{reward_text}", reply_markup=None)
            await utils.mark_work_completed(settler, session, callback.message.chat.id)
        
        active_games.pop(user_key, None)
        utils.end_work(callback.message.chat.id)

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
                await utils.mark_work_completed(settler, session, callback.message.chat.id)
        active_games.pop(user_key, None)
        utils.end_work(callback.message.chat.id)
    else:
        status_text = workflow.get_status_text()
        kb = workflow.get_keyboard()
        await callback.message.edit_text(status_text, reply_markup=kb)


@router.message(F.text.lower().startswith("!дать"))
async def promo_command(message: types.Message, i18n: TranslatorRunner):
    #* Выдача ресурса разработчиком
    if message.from_user.id not in settings.DEVELOPER_IDS:
        await message.answer("⚠️ " + i18n.text.other.promo.not_developer())
        return

    try:
        _ , emoji, qty = message.text.split(" ")
        qty = int(qty)
    except:
        await message.answer("⚠️ " + i18n.text.other.promo.bad_format())
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
        text = await utils.format_reward_text(obtained)

        await session.commit()

    await message.answer("🌟 " + i18n.text.other.promo.received(name=recipient.full_name) + f"\n{text}")


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
    match = await utils.is_text_command(
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
            if await utils.is_meaningful(message.text) and not settler.quote_is_completed:
                await core.settler_updateQuote(settler, settlement, session, 1)
                return
        except Exception as e:
            log.error(f"Ошибка в функции quote_handler(): {e}")
            return

