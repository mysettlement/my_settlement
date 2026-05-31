from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app import tasks
from tests.support.factories import create_settlement, create_settler, create_user


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_remind_overtime_batches_chat_mentions(db_session, monkeypatch):
    sender = AsyncMock()
    monkeypatch.setattr(tasks, "get_timezones_at_hour", lambda hour: ["Europe/Berlin"])
    monkeypatch.setattr(tasks.telegram_gateway, "send_message", sender)

    owner = await create_user(db_session, telegram_id=8000, timezone="Europe/Berlin")
    settlement = await create_settlement(db_session, owner=owner, chat_id=-8000)
    for idx in range(6):
        user = await create_user(
            db_session,
            telegram_id=8001 + idx,
            name=f"User {idx}",
            timezone="Europe/Berlin",
        )
        await create_settler(
            db_session,
            user=user,
            settlement=settlement,
            quote=idx,
            target_quote=10,
            overtime_is_toggled=True,
        )
    await db_session.commit()

    await tasks.remind_overtime()

    assert sender.await_count == 2
    first_call = sender.await_args_list[0]
    assert first_call.args[0] == -8000
    assert "Не забудьте выполнить страду" in first_call.args[1]


@pytest.mark.asyncio
async def test_day_reset_applies_fines_and_resets_quotes(db_session, monkeypatch):
    sender = AsyncMock()
    monkeypatch.setattr(tasks, "get_timezones_at_hour", lambda hour: ["Europe/Berlin"])
    monkeypatch.setattr(tasks.telegram_gateway, "send_message", sender)

    owner = await create_user(db_session, telegram_id=9000, timezone="Europe/Berlin")
    settlement = await create_settlement(db_session, owner=owner, chat_id=-9000)
    settler = await create_settler(
        db_session,
        user=owner,
        settlement=settlement,
        level=10,
        quote=4,
        target_quote=8,
        balance=100,
        overtime_is_toggled=True,
    )
    await db_session.commit()

    await tasks.day_reset()
    await db_session.refresh(settler)

    assert settler.quote == 0
    assert settler.quote_is_completed is False
    assert settler.overtime_is_toggled is False
    assert settler.overtime_count == 0
    assert settler.target_quote == round(settler.level * 0.85 + 6)
    assert settler.balance < 100
    sender.assert_awaited()
