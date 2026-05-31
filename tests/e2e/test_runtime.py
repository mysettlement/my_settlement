from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from aiogram import Dispatcher
import pytest

import app.tasks as tasks
import app.telegram_gateway as telegram_gateway
import app.utils as utils
import main


pytestmark = pytest.mark.e2e


@pytest.mark.asyncio
async def test_setup_runtime_registers_jobs_and_configures_gateway(monkeypatch):
    dispatcher = Dispatcher()
    fake_bot = SimpleNamespace(session=SimpleNamespace(close=AsyncMock()))

    monkeypatch.setattr(main, "set_bot_status", AsyncMock())
    monkeypatch.setattr(main.db, "init_db", AsyncMock())
    tasks.scheduler.remove_all_jobs()

    await main.setup_runtime(dispatcher, fake_bot, initialize_db=False)

    assert dispatcher._my_settlement_runtime_configured is True
    assert tasks.scheduler.get_job("day_reset") is not None
    assert tasks.scheduler.get_job("remind_overtime") is not None
    assert telegram_gateway.get_bot() is fake_bot

    await main.shutdown_runtime(fake_bot, close_bot_session=False)


@pytest.mark.asyncio
async def test_shutdown_runtime_clears_state_and_closes_session(monkeypatch):
    fake_bot = SimpleNamespace(session=SimpleNamespace(close=AsyncMock()))
    monkeypatch.setattr(main, "set_bot_status", AsyncMock())

    utils.active_games["chat_1"] = "workflow"
    utils.work_timeout_tasks[1] = SimpleNamespace(cancel=lambda: None)
    utils.work_in_progress[1] = True

    await main.shutdown_runtime(fake_bot)

    assert utils.active_games == {}
    assert utils.work_timeout_tasks == {}
    fake_bot.session.close.assert_awaited_once()
