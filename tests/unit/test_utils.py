from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import arrow
import pytest

from app import utils
from app.middlewares import GroupOwnerError


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_text_command_matches_exact_and_fuzzy(monkeypatch):
    command = utils.TextCommand("my id", "мой айди")
    message = SimpleNamespace(
        text="my id",
        chat=SimpleNamespace(id=1),
        from_user=SimpleNamespace(id=2),
    )
    user = SimpleNamespace(allow_typos=False)

    assert await command(message, user) is True

    monkeypatch.setattr(
        utils.process,
        "extractOne",
        lambda processed_text, aliases, scorer: ("my id", 95, 0),
    )
    typo_message = SimpleNamespace(
        text="myid",
        chat=SimpleNamespace(id=1),
        from_user=SimpleNamespace(id=2),
    )
    typo_user = SimpleNamespace(allow_typos=True)

    assert await command(typo_message, typo_user) is True


@pytest.mark.asyncio
async def test_text_command_negative_and_known_typo_branches(monkeypatch):
    command = utils.TextCommand("my id")
    user = SimpleNamespace(allow_typos=False)

    slash_message = SimpleNamespace(
        text="/start",
        chat=SimpleNamespace(id=1),
        from_user=SimpleNamespace(id=2),
    )
    assert await command(slash_message, user) is False

    typo_message = SimpleNamespace(
        text="myyd",
        chat=SimpleNamespace(id=1),
        from_user=SimpleNamespace(id=2),
    )
    assert await command(typo_message, user) is False

    typo_user = SimpleNamespace(allow_typos=True)
    monkeypatch.setitem(utils.KNOWN_TYPOS, "myyd", "my id")
    assert await command(typo_message, typo_user) is True

    monkeypatch.delitem(utils.KNOWN_TYPOS, "myyd", raising=False)
    monkeypatch.setattr(utils.process, "extractOne", lambda processed_text, aliases, scorer: None)
    assert await command(typo_message, typo_user) is False


@pytest.mark.asyncio
async def test_is_meaningful_uses_detected_language(monkeypatch):
    monkeypatch.setattr(utils, "detect", lambda text: "en")
    monkeypatch.setattr(utils, "zipf_frequency", lambda word, lang: 2.5 if word in {"hello", "world"} else 0.0)

    assert await utils.is_meaningful("hello world") is True
    assert await utils.is_meaningful("!!!!") is False
    assert await utils.is_meaningful("aaaaa") is False


@pytest.mark.asyncio
async def test_is_meaningful_handles_fallback_and_repeated_words(monkeypatch):
    monkeypatch.setattr(utils, "detect", lambda text: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(utils, "zipf_frequency", lambda word, lang: 0.0)

    assert await utils.is_meaningful("") is False
    assert await utils.is_meaningful("  a ") is False
    assert await utils.is_meaningful("echo echo") is False
    assert await utils.is_meaningful("...") is False
    assert await utils.is_meaningful("???", length=1) is False


@pytest.mark.asyncio
async def test_get_group_owner_returns_creator_and_wraps_errors(monkeypatch):
    creator = SimpleNamespace(status="creator", user=SimpleNamespace(id=10))
    monkeypatch.setattr(utils.telegram_gateway, "get_chat_administrators", AsyncMock(return_value=[creator]))
    assert await utils.get_group_owner(-100) == creator.user

    monkeypatch.setattr(
        utils.telegram_gateway,
        "get_chat_administrators",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    with pytest.raises(GroupOwnerError):
        await utils.get_group_owner(-100)


@pytest.mark.asyncio
async def test_format_helpers(monkeypatch):
    text = await utils.format_reward_text({"🌾": 3, "💰": 2})
    assert "🌾: +3" in text
    assert "💰: +2" in text

    assert await utils.format_reward_text({}) == "✖️ Пусто"

    has_bonuses, bonuses_text = utils.format_bonuses_text(
        {
            "global_quantity_modifier": 2,
            "resource_chance_multiplier": {"🌾": 0.1},
        }
    )
    assert has_bonuses is True
    assert "всего" in bonuses_text
    assert "🌾" in bonuses_text

    has_bonuses, bonuses_text = utils.format_bonuses_text({"mystery": []})
    assert has_bonuses is False
    assert bonuses_text == "Нет явных бонусов"

    countdown = utils.get_daily_reset_countdown("UTC")
    assert isinstance(countdown, str)

    relative = utils.format_relative_time(datetime.now(timezone.utc), fallback=False)
    assert relative.startswith("<tg-time")
    assert isinstance(utils.format_relative_time(60, fallback=True), str)
    assert isinstance(utils.format_relative_time(arrow.utcnow().shift(minutes=1) - arrow.utcnow(), fallback=True), str)


def test_click_and_work_state_transitions(monkeypatch):
    timestamps = iter([100.0, 100.5, 102.0, 110.0, 110.0, 115.0, 115.0])
    monkeypatch.setattr(utils.time, "time", lambda: next(timestamps))
    monkeypatch.setattr(
        utils.asyncio,
        "create_task",
        lambda coro: (coro.close(), SimpleNamespace(cancel=lambda: None))[1],
    )

    assert utils.can_click_button("chat_user") is True
    assert utils.can_click_button("chat_user") is False
    assert utils.can_click_button("chat_user") is True

    can_start, _ = utils.can_start_work(10)
    assert can_start is True
    utils.start_work(10)
    can_start, message = utils.can_start_work(10)
    assert can_start is False
    assert "трудится" in message

    utils.end_work(10)
    can_start, message = utils.can_start_work(10)
    assert can_start is False
    assert "Передышка" in message


@pytest.mark.asyncio
async def test_timeout_work_resets_active_games(monkeypatch):
    monkeypatch.setattr(utils.settings, "WORK_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(asyncio, "sleep", AsyncMock())

    utils.work_in_progress[123] = True
    utils.active_games["123_1"] = "game"

    await utils.timeout_work(123)

    assert "123_1" not in utils.active_games
    assert utils.work_in_progress[123] is False


@pytest.mark.asyncio
async def test_timeout_work_handles_cancel_and_runtime_error(monkeypatch):
    monkeypatch.setattr(utils.settings, "WORK_TIMEOUT_SECONDS", 0)

    async def raise_cancelled(*args, **kwargs):
        raise asyncio.CancelledError()

    monkeypatch.setattr(asyncio, "sleep", raise_cancelled)
    await utils.timeout_work(321)

    async def raise_runtime(*args, **kwargs):
        raise RuntimeError("boom")

    logger = Mock()
    monkeypatch.setattr(asyncio, "sleep", raise_runtime)
    monkeypatch.setattr(utils.log, "error", logger)
    await utils.timeout_work(654)
    logger.assert_called_once()


def test_can_choose_craft_and_reset_runtime_state(monkeypatch):
    now = arrow.get("2026-01-01T00:00:00+00:00")
    monkeypatch.setattr(utils.arrow, "now", lambda *args, **kwargs: now)
    monkeypatch.setattr(utils.settings, "CRAFT_COOLDOWN_HOURS", 1)

    can_choose, _ = utils.can_choose_craft(now.shift(hours=-2).datetime, fallback=True)
    assert can_choose is True

    can_choose, countdown = utils.can_choose_craft(now.datetime, fallback=True)
    assert can_choose is False
    assert isinstance(countdown, str)

    utils.active_games["x"] = "game"
    utils.work_in_progress[1] = True
    utils.user_last_click_time["x"] = 1.0
    utils.reset_runtime_state()

    assert utils.active_games == {}
    assert utils.work_in_progress == {}
    assert utils.user_last_click_time == {}


def test_get_work_remaining_time_without_started_work(monkeypatch):
    assert utils.get_work_remaining_time(999) == 0

    monkeypatch.setitem(utils.work_start_time, 999, 100.0)
    monkeypatch.setattr(utils.time, "time", lambda: 120.0)
    assert utils.get_work_remaining_time(999) == 160


@pytest.mark.asyncio
async def test_mark_work_completed_and_notify_developers(monkeypatch):
    session = AsyncMock()
    settler = SimpleNamespace(id=5, user_id=10)
    monkeypatch.setattr(utils.arrow, "now", lambda: SimpleNamespace(int_timestamp=123456))

    await utils.mark_work_completed(settler, session, chat_id=1)

    session.execute.assert_awaited()
    session.commit.assert_awaited()

    monkeypatch.setattr(utils.settings, "ENABLE_DEVELOPERS_NOTIFY", True)
    monkeypatch.setattr(utils.settings, "DEVELOPER_IDS", [1, 2])
    sender = AsyncMock()
    monkeypatch.setattr(utils.telegram_gateway, "send_message", sender)
    await utils.notify_developers("ping")
    assert sender.await_count == 2

    monkeypatch.setattr(utils.settings, "ENABLE_DEVELOPERS_NOTIFY", False)
    await utils.notify_developers("skip")

    monkeypatch.setattr(utils.settings, "ENABLE_DEVELOPERS_NOTIFY", True)
    failing_sender = AsyncMock(side_effect=RuntimeError("boom"))
    logger = Mock()
    monkeypatch.setattr(utils.telegram_gateway, "send_message", failing_sender)
    monkeypatch.setattr(utils.log, "error", logger)
    await utils.notify_developers("ping")
    assert failing_sender.await_count == 2
    assert logger.call_count == 2


def test_get_timezones_at_hour(monkeypatch):
    monkeypatch.setattr(utils.pytz, "common_timezones", ["UTC", "Europe/Berlin"])

    def fake_now(timezone_name):
        if timezone_name == "Europe/Berlin":
            raise RuntimeError("broken tz")
        hour = 10 if timezone_name == "UTC" else 11
        return SimpleNamespace(hour=hour)

    monkeypatch.setattr(utils.arrow, "now", fake_now)
    assert utils.get_timezones_at_hour(10) == ["UTC"]
