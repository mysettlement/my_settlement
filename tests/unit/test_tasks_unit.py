from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app import tasks


pytestmark = pytest.mark.unit


class _AsyncContextManager:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


@pytest.mark.asyncio
async def test_availability_check_logs():
    await tasks.availability_check()


@pytest.mark.asyncio
async def test_remind_overtime_returns_early(monkeypatch):
    monkeypatch.setattr(tasks, "get_timezones_at_hour", lambda hour: [])
    sender = AsyncMock()
    monkeypatch.setattr(tasks.telegram_gateway, "send_message", sender)

    await tasks.remind_overtime()
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_day_reset_returns_early(monkeypatch):
    monkeypatch.setattr(tasks, "get_timezones_at_hour", lambda hour: [])
    sender = AsyncMock()
    monkeypatch.setattr(tasks.telegram_gateway, "send_message", sender)

    await tasks.day_reset()
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_remind_overtime_logs_query_error(monkeypatch):
    class BrokenSession:
        async def execute(self, stmt):
            raise RuntimeError("db failure")

    logger = Mock()
    monkeypatch.setattr(tasks, "get_timezones_at_hour", lambda hour: ["Europe/Berlin"])
    monkeypatch.setattr(tasks.app_db, "SessionLocal", lambda: _AsyncContextManager(BrokenSession()))
    monkeypatch.setattr(tasks.log, "error", logger)

    await tasks.remind_overtime()

    logger.assert_called_once()


@pytest.mark.asyncio
async def test_remind_overtime_logs_send_error(monkeypatch):
    settler = SimpleNamespace(
        user=SimpleNamespace(telegram_id=1, name="Tester"),
        settlement=SimpleNamespace(chat_id=-1000),
        quote=1,
        target_quote=3,
    )

    class SessionWithSettlers:
        async def execute(self, stmt):
            return _ScalarResult([settler])

    sender = AsyncMock(side_effect=RuntimeError("send failure"))
    logger = Mock()
    monkeypatch.setattr(tasks, "get_timezones_at_hour", lambda hour: ["Europe/Berlin"])
    monkeypatch.setattr(tasks.app_db, "SessionLocal", lambda: _AsyncContextManager(SessionWithSettlers()))
    monkeypatch.setattr(tasks.telegram_gateway, "send_message", sender)
    monkeypatch.setattr(tasks.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr(tasks.log, "error", logger)

    await tasks.remind_overtime()

    sender.assert_awaited_once()
    logger.assert_called_once()


@pytest.mark.asyncio
async def test_day_reset_logs_when_no_settlers_found(monkeypatch):
    class EmptySession:
        async def execute(self, stmt):
            return _ScalarResult([])

    logger = Mock()
    monkeypatch.setattr(tasks, "get_timezones_at_hour", lambda hour: ["Europe/Berlin"])
    monkeypatch.setattr(tasks.app_db, "SessionLocal", lambda: _AsyncContextManager(EmptySession()))
    monkeypatch.setattr(tasks.log, "debug", logger)

    await tasks.day_reset()

    assert any("нет активных игроков" in call.args[0] for call in logger.call_args_list)


@pytest.mark.asyncio
async def test_day_reset_logs_query_error(monkeypatch):
    class BrokenSession:
        async def execute(self, stmt):
            raise RuntimeError("db failure")

    logger = Mock()
    monkeypatch.setattr(tasks, "get_timezones_at_hour", lambda hour: ["Europe/Berlin"])
    monkeypatch.setattr(tasks.app_db, "SessionLocal", lambda: _AsyncContextManager(BrokenSession()))
    monkeypatch.setattr(tasks.log, "error", logger)

    await tasks.day_reset()

    logger.assert_called_once()
