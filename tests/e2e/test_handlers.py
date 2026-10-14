from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app import handlers, models
from app.i18n import create_translator_hub


pytestmark = pytest.mark.e2e


class FakeMessage:
    def __init__(self, *, chat_type: str = "group", from_user_id: int = 1):
        self.chat = SimpleNamespace(id=-1000, type=chat_type, title="Village")
        self.from_user = SimpleNamespace(id=from_user_id, full_name="Tester")
        self.answer = AsyncMock()
        self.reply = AsyncMock()


class FakeCallback:
    def __init__(self, *, from_user_id: int = 1, owner_user_id: int = 1, data: str = "select_work:catcher_fishing"):
        self.data = data
        self.from_user = SimpleNamespace(id=from_user_id, full_name="Tester")
        self.answer = AsyncMock()
        self.message = SimpleNamespace(
            chat=SimpleNamespace(id=-1000, type="group"),
            reply_to_message=SimpleNamespace(from_user=SimpleNamespace(id=owner_user_id)),
            edit_text=AsyncMock(),
            edit_reply_markup=AsyncMock(),
        )


def _translator():
    return create_translator_hub().get_translator_by_locale("ru")


@pytest.mark.asyncio
async def test_me_command_renders_profile(monkeypatch):
    message = FakeMessage()
    i18n = _translator()
    user = models.User(id=1, telegram_id=1, name="Tester", compact_style=False, show_hints=False)
    profession = models.Profession(id=3, emoji="🎣", name="Рыбак")
    settler = models.Settler(
        id=1,
        level=5,
        exp=2,
        target_exp=7,
        rank="Крестьянин",
        emoji="🧑‍🌾",
        profession_id=profession.id,
        profession=profession,
        quote=2,
        target_quote=6,
        balance=10,
        last_profession_change=datetime.now(timezone.utc),
    )

    monkeypatch.setattr(handlers.core, "settlement_getOrCreate", AsyncMock(return_value=models.Settlement(id=1, chat_id=-1000, name="Village")))
    monkeypatch.setattr(handlers.core, "settler_getOrCreate", AsyncMock(return_value=settler))
    monkeypatch.setattr(handlers.core, "settler_canWorkNow", lambda settler, fallback=False: (True, ""))
    monkeypatch.setattr(handlers.utils, "can_choose_craft", lambda *args, **kwargs: (True, ""))

    await handlers.me_command(message, user, i18n)

    message.answer.assert_awaited_once()
    response_text = message.answer.await_args.args[0]
    assert "Tester" in response_text
    assert "Рыбак" in response_text


@pytest.mark.asyncio
async def test_settings_callback_blocks_foreign_user():
    callback = FakeCallback(from_user_id=2, owner_user_id=1, data="settings:compact_style")

    await handlers.settings_callback(callback, _translator())

    callback.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_craft_command_without_profession_prompts_to_choose(monkeypatch):
    message = FakeMessage()
    i18n = _translator()
    user = models.User(id=1, telegram_id=1, name="Tester")
    settler = models.Settler(id=1, profession_id=None)

    monkeypatch.setattr(handlers.core, "settlement_getOrCreate", AsyncMock(return_value=models.Settlement(id=1, chat_id=-1000, name="Village")))
    monkeypatch.setattr(handlers.core, "settler_getOrCreate", AsyncMock(return_value=settler))

    await handlers.craft_command(message, user, i18n)

    message.answer.assert_awaited_once()
    response_text = message.answer.await_args.args[0]
    assert "ремес" in response_text.lower() or "проф" in response_text.lower()


@pytest.mark.asyncio
async def test_work_selection_callback_checks_user_and_starts_workflow(monkeypatch):
    callback = FakeCallback(from_user_id=1, owner_user_id=1)
    i18n = _translator()
    user = models.User(id=1, telegram_id=1, name="Tester")
    settlement = models.Settlement(id=1, chat_id=-1000, name="Village")
    profession = models.Profession(id=3, emoji="🐾", name="Ловчий")
    settler = models.Settler(id=1, profession_id=profession.id, profession=profession)

    monkeypatch.setattr(handlers.core, "user_getOrCreate", AsyncMock(return_value=user))
    monkeypatch.setattr(handlers.core, "settlement_getOrCreate", AsyncMock(return_value=settlement))
    monkeypatch.setattr(handlers.core, "settler_getOrCreate", AsyncMock(return_value=settler))
    starter = AsyncMock(return_value=True)
    monkeypatch.setattr(handlers.core, "settler_startWorkflow", starter)

    await handlers.work_selection_callback(callback, i18n)

    starter.assert_awaited_once()


@pytest.mark.asyncio
async def test_bot_rights_change_without_status_change_is_ignored():
    event = SimpleNamespace(
        chat=SimpleNamespace(id=-1000, title="Village"),
        from_user=SimpleNamespace(id=1),
        old_chat_member=SimpleNamespace(status="administrator"),
        new_chat_member=SimpleNamespace(status="administrator"),
        answer=AsyncMock(),
    )

    await handlers.bot_added_to_chat_event(event)

    event.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_id_menu_deep_link_renders_full_style():
    message = FakeMessage(chat_type="private")
    user = models.User(id=1, telegram_id=1, name="Tester", compact_style=False)
    command = SimpleNamespace(args="menu_id")

    await handlers.private_handler(message, user, command, _translator())

    message.answer.assert_awaited_once()
    assert "Telegram ID" in message.answer.await_args.args[0]


def test_works_are_bound_to_profession_emoji_not_database_id():
    catcher = models.Profession(id=1, emoji="🐾", name="Ловчий")
    farmer = models.Profession(id=3, emoji="🌻", name="Землепашец")
    fishing = models.WORKS_REGISTRY["catcher_fishing"]

    assert fishing.is_available_for(models.Settler(profession_id=catcher.id, profession=catcher)) is True
    assert fishing.is_available_for(models.Settler(profession_id=farmer.id, profession=farmer)) is False
    assert fishing.is_available_for(models.Settler(profession_id=None)) is False


@pytest.mark.asyncio
async def test_menu_callbacks_survive_deleted_command_message(monkeypatch):
    callback = FakeCallback(data="select_work:catcher_fishing")
    callback.message.reply_to_message = None
    user = models.User(id=1, telegram_id=1, name="Tester")
    monkeypatch.setattr(handlers.core, "user_getOrCreate", AsyncMock(return_value=user))
    monkeypatch.setattr(handlers.core, "settlement_getOrCreate", AsyncMock(return_value=models.Settlement(id=1, chat_id=-1000, name="Village")))
    monkeypatch.setattr(handlers.core, "settler_getOrCreate", AsyncMock(return_value=models.Settler(id=1)))
    starter = AsyncMock()
    monkeypatch.setattr(handlers.core, "settler_startWorkflow", starter)

    await handlers.work_selection_callback(callback, _translator())

    callback.answer.assert_awaited_once()
    starter.assert_not_awaited()
