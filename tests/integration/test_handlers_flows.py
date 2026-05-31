from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, update

import app.db as app_db
from app import handlers, models
from app.i18n import create_translator_hub
from tests.support.aiogram_builders import build_chat, build_user
from tests.support.factories import (
    create_building_type,
    create_profession,
    create_resource,
    create_settlement,
    create_settler,
    create_user,
    grant_resource,
)


pytestmark = pytest.mark.integration


def _translator():
    return create_translator_hub().get_translator_by_locale("ru")


class FakeMessage:
    def __init__(
        self,
        *,
        from_user,
        chat,
        text: str = "",
        reply_to_message=None,
        location=None,
    ):
        self.from_user = from_user
        self.chat = chat
        self.text = text
        self.reply_to_message = reply_to_message
        self.location = location
        self.answer = AsyncMock()
        self.reply = AsyncMock()
        self.delete = AsyncMock()
        self.edit_text = AsyncMock()
        self.edit_reply_markup = AsyncMock()


class FakeCallback:
    def __init__(self, *, from_user, message, data: str):
        self.from_user = from_user
        self.message = message
        self.data = data
        self.answer = AsyncMock()


@pytest.mark.asyncio
async def test_private_settings_and_timezone_handlers(db_session, monkeypatch):
    i18n = _translator()
    tg_user = build_user(user_id=1101, first_name="Private")
    chat = build_chat(chat_id=1101, chat_type="private", title=None)
    user = await create_user(db_session, telegram_id=tg_user.id, name=tg_user.full_name)
    user.language = "ru"
    user.timezone = "Europe/Berlin"
    await db_session.commit()

    message = FakeMessage(from_user=tg_user, chat=chat)
    await handlers.private_handler(message, user, command=SimpleNamespace(args="ref_42"), i18n=i18n)
    assert message.answer.await_count == 1

    await handlers.private_handler(message, user, command=SimpleNamespace(args="menu_settings_language"), i18n=i18n)
    assert message.reply.await_count >= 1

    await handlers.show_settings_menu(message, user, i18n=i18n)
    assert message.reply.await_count >= 2

    callback_message = FakeMessage(
        from_user=tg_user,
        chat=chat,
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=tg_user.id)),
    )
    callback = FakeCallback(from_user=tg_user, message=callback_message, data="settings:compact_style")
    await handlers.settings_callback(callback, i18n)
    callback.answer.assert_awaited()
    callback.message.edit_text.assert_awaited()

    await handlers.show_settings_menu(message, user, submenu="timezone", i18n=i18n)
    await handlers.show_settings_menu(message, user, submenu="language", i18n=i18n)

    ask_callback = FakeCallback(from_user=tg_user, message=callback_message, data="ask_location")
    await handlers.ask_location_callback(ask_callback, i18n)
    ask_callback.message.delete.assert_awaited()

    monkeypatch.setattr(handlers, "tf", SimpleNamespace(timezone_at=lambda lng, lat: "Europe/Berlin"))
    location_message = FakeMessage(
        from_user=tg_user,
        chat=chat,
        location=SimpleNamespace(latitude=52.5, longitude=13.4),
    )
    await handlers.location_handler(location_message, i18n)
    location_message.reply.assert_awaited()

    set_tz_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data="set_tz:Europe/Berlin",
    )
    await handlers.set_tz_callback(set_tz_callback, i18n)
    set_tz_callback.message.edit_text.assert_awaited()


@pytest.mark.asyncio
async def test_start_rename_buildings_and_bonuses_handlers(db_session, monkeypatch):
    i18n = _translator()
    tg_user = build_user(user_id=2101, first_name="Mayor")
    chat = build_chat(chat_id=-2101, chat_type="supergroup", title="Old Village")
    monkeypatch.setattr(handlers.core.utils, "get_group_owner", AsyncMock(return_value=tg_user))

    message = FakeMessage(from_user=tg_user, chat=chat, text="/start")
    await handlers.start_command(message, i18n)
    message.answer.assert_awaited()

    async with app_db.SessionLocal() as session:
        settlement = (
            await session.execute(
                select(models.Settlement).where(models.Settlement.chat_id == chat.id)
            )
        ).scalars().one()
        owner = (
            await session.execute(
                select(models.User).where(models.User.telegram_id == tg_user.id)
            )
        ).scalars().one()
        settler = (
            await session.execute(
                select(models.Settler).where(models.Settler.user_id == owner.id)
            )
        ).scalars().one()

        profession = await create_profession(session, emoji="🌻", name="Землепашец")
        metal = await create_resource(session, name="Сырьё", emoji="🔩", category="Материалы")
        ore = await create_resource(session, name="Руда", emoji="🪨", category="Материалы")
        await grant_resource(session, settler=settler, resource=metal, quantity=20)
        await grant_resource(session, settler=settler, resource=ore, quantity=25)

        await session.execute(
            update(models.Settler)
            .where(models.Settler.id == settler.id)
            .values(profession_id=profession.id)
        )
        building_type = await create_building_type(
            session,
            name="Градская Ферма",
            emoji="🏛🌾",
            is_private=False,
            bonuses={"global_quantity_modifier": 1},
            required_professions={"🌻": 1},
            costs={metal: 10, ore: 20},
        )
        await session.commit()

    rename_message = FakeMessage(from_user=tg_user, chat=chat, text="rename")
    await handlers.name_settlement(rename_message, command=SimpleNamespace(args="New Village"), i18n=i18n)
    rename_message.answer.assert_awaited()

    owner_user = await handlers.core.user_getOrCreate(tg_user)
    settlement = await handlers.core.settlement_getOrCreate(chat)
    await handlers.show_buildings_menu(rename_message, owner_user, settlement, "town", i18n=i18n)
    assert rename_message.answer.await_count >= 1

    callback_message = FakeMessage(
        from_user=tg_user,
        chat=chat,
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=tg_user.id)),
    )

    for data in [
        "bld_list:town",
        f"bld_preview:{building_type.id}:town",
        f"bld_start:{building_type.id}:town",
    ]:
        callback = FakeCallback(from_user=tg_user, message=callback_message, data=data)
        await handlers.buildings_callback(callback, i18n)

    async with app_db.SessionLocal() as session:
        building = (await session.execute(select(models.Building))).scalars().first()

    view_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data=f"bld_view:{building.id}:town",
    )
    await handlers.buildings_callback(view_callback, i18n)

    bonuses_message = FakeMessage(from_user=tg_user, chat=chat, text="/bonuses")
    await handlers.bonuses_command(bonuses_message, owner_user, i18n)
    bonuses_message.answer.assert_awaited()


@pytest.mark.asyncio
async def test_cosmetics_overtime_inventory_and_craft_handlers(db_session, monkeypatch):
    i18n = _translator()
    tg_user = build_user(user_id=3101, first_name="Crafter")
    user = await create_user(
        db_session,
        telegram_id=tg_user.id,
        name=tg_user.full_name,
        timezone="Europe/Berlin",
    )
    settlement = await create_settlement(db_session, owner=user, chat_id=-3101, name="Craft Town")
    settler = await create_settler(
        db_session,
        user=user,
        settlement=settlement,
        level=3,
        quote_is_completed=True,
    )
    settler.rank_emoji_available = ["🧑‍🌾", "👨‍🌾"]
    settler.special_emoji_available = ["😎"]
    food = await create_resource(db_session, name="Зерно", emoji="🌾")
    await grant_resource(db_session, settler=settler, resource=food, quantity=3)
    profession = await create_profession(db_session, emoji="📔", name="Знахарь")
    await db_session.commit()

    group_chat = build_chat(chat_id=settlement.chat_id, chat_type="supergroup", title=settlement.name)

    cosmetics_message = FakeMessage(from_user=tg_user, chat=group_chat, text="/cosmetics")
    await handlers.cosmetics_command(cosmetics_message, user, i18n)
    cosmetics_message.reply.assert_awaited()

    callback_message = FakeMessage(
        from_user=tg_user,
        chat=group_chat,
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=tg_user.id)),
    )
    cosmetics_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data="cosmetics_select_😎",
    )
    await handlers.cosmetics_select(cosmetics_callback, i18n)
    cosmetics_callback.message.edit_text.assert_awaited()

    monkeypatch.setattr(handlers.utils, "get_daily_reset_countdown", lambda timezone: "1h")
    overtime_message = FakeMessage(from_user=tg_user, chat=group_chat, text="/overtime")
    await handlers.overtime_command(overtime_message, user, i18n)
    overtime_message.reply.assert_awaited()

    overtime_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data="overtime_take",
    )
    await handlers.overtime_take(overtime_callback, i18n)
    overtime_callback.message.edit_text.assert_awaited()

    inventory_message = FakeMessage(from_user=tg_user, chat=group_chat, text="/inventory")
    await handlers.inventory_command(inventory_message, user, i18n)
    inventory_message.answer.assert_awaited()

    choose_message = FakeMessage(from_user=tg_user, chat=group_chat, text="/choose_craft")
    await handlers.choose_craft_command(choose_message, user, i18n)
    choose_message.reply.assert_awaited()

    select_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data=f"select_craft:{profession.id}",
    )
    await handlers.select_craft_callback(select_callback, i18n)
    select_callback.message.edit_text.assert_awaited()

    craft_message = FakeMessage(from_user=tg_user, chat=group_chat, text="/craft")
    await handlers.craft_command(craft_message, user, i18n)
    craft_message.reply.assert_awaited()


@pytest.mark.asyncio
async def test_work_promo_and_quote_handlers(db_session, monkeypatch):
    i18n = _translator()
    tg_user = build_user(user_id=4101, first_name="Worker")
    recipient_user = build_user(user_id=4102, first_name="Recipient")
    user = await create_user(db_session, telegram_id=tg_user.id, name=tg_user.full_name)
    recipient = await create_user(db_session, telegram_id=recipient_user.id, name=recipient_user.full_name)
    settlement = await create_settlement(db_session, owner=user, chat_id=-4101, name="Work Town")
    profession = await create_profession(db_session, emoji="🐾", name="Ловчий")
    settler = await create_settler(db_session, user=user, settlement=settlement, profession=profession, level=3)
    recipient_settler = await create_settler(db_session, user=recipient, settlement=settlement)
    await db_session.commit()

    chat = build_chat(chat_id=settlement.chat_id, chat_type="supergroup", title=settlement.name)
    callback_message = FakeMessage(
        from_user=tg_user,
        chat=chat,
        reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=tg_user.id)),
    )
    user_key = f"{chat.id}_{tg_user.id}"

    class FakeWorkflow:
        def __init__(self, result: str, completed: bool = False):
            self.result = result
            self.completed = completed
            self.game_over = False
            self.steps = [object()]
            self.current_step = 0

        def get_current_step(self):
            return None

        def click(self, action):
            return self.result

        def get_status_text(self):
            return "status"

        def get_keyboard(self):
            return InlineKeyboardBuilder().button(text="ok", callback_data="noop").as_markup()

    handlers.active_games[user_key] = FakeWorkflow("continue")
    monkeypatch.setattr(handlers.utils, "can_click_button", lambda key: True)
    monkeypatch.setattr(handlers.utils, "get_work_remaining_time", lambda chat_id: 10)
    continue_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data="work:catcher_fishing:0:0",
    )
    await handlers.work_callback(continue_callback, i18n)
    continue_callback.message.edit_text.assert_awaited()

    handlers.active_games[user_key] = FakeWorkflow("win", completed=True)
    monkeypatch.setattr(handlers.core, "settler_applyRewards", AsyncMock(return_value={"🌾": 1}))
    monkeypatch.setattr(handlers.utils, "mark_work_completed", AsyncMock())
    win_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data="work:catcher_fishing:0:0",
    )
    await handlers.work_callback(win_callback, i18n)
    win_callback.message.edit_text.assert_awaited()

    handlers.active_games[user_key] = FakeWorkflow("lose")
    lose_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data="work:catcher_fishing:0:0",
    )
    await handlers.work_callback(lose_callback, i18n)
    lose_callback.message.edit_text.assert_awaited()

    monkeypatch.setattr(handlers.utils, "get_work_remaining_time", lambda chat_id: 0)
    handlers.active_games[user_key] = FakeWorkflow("continue")
    expired_callback = FakeCallback(
        from_user=tg_user,
        message=callback_message,
        data="work:catcher_fishing:0:0",
    )
    await handlers.work_callback(expired_callback, i18n)
    expired_callback.answer.assert_awaited()

    monkeypatch.setattr(handlers.settings, "DEVELOPER_IDS", [tg_user.id])
    original_settlement_get_or_create = handlers.core.settlement_getOrCreate
    original_settler_get_or_create = handlers.core.settler_getOrCreate
    promo_message = FakeMessage(
        from_user=tg_user,
        chat=chat,
        text="!дать 🌾 2",
        reply_to_message=SimpleNamespace(from_user=recipient_user),
    )
    monkeypatch.setattr(handlers.core, "settlement_getOrCreate", AsyncMock(return_value=settlement))
    monkeypatch.setattr(handlers.core, "settler_getOrCreate", AsyncMock(return_value=recipient_settler))
    await handlers.promo_command(promo_message, i18n)
    promo_message.answer.assert_awaited()

    monkeypatch.setattr(handlers.utils, "is_meaningful", AsyncMock(return_value=True))
    monkeypatch.setattr(handlers.core.utils, "get_group_owner", AsyncMock(return_value=tg_user))
    monkeypatch.setattr(handlers.core, "settlement_getOrCreate", original_settlement_get_or_create)
    monkeypatch.setattr(handlers.core, "settler_getOrCreate", original_settler_get_or_create)
    monkeypatch.setattr(handlers.core, "settler_updateQuote", AsyncMock())
    quote_message = FakeMessage(from_user=tg_user, chat=chat, text="Это осмысленное сообщение")
    await handlers.quote_handler(quote_message)
    handlers.core.settler_updateQuote.assert_awaited()
