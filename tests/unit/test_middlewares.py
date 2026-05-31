from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.middlewares import ErrorMiddleware, GroupOwnerError, UserMiddleware
from tests.support.aiogram_builders import build_message


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_error_middleware_handles_domain_error():
    middleware = ErrorMiddleware()
    event = build_message()
    object.__setattr__(event, "answer", AsyncMock())

    async def handler(event, data):
        raise GroupOwnerError("missing owner", chat_id=-100)

    result = await middleware(handler, event, {})

    assert result is None
    event.answer.assert_awaited()


@pytest.mark.asyncio
async def test_error_middleware_suppresses_known_telegram_noise():
    middleware = ErrorMiddleware()
    event = build_message()
    object.__setattr__(event, "answer", AsyncMock())

    async def handler(event, data):
        raise RuntimeError("message is not modified")

    result = await middleware(handler, event, {})
    assert result is None


@pytest.mark.asyncio
async def test_error_middleware_reraises_unknown_errors():
    middleware = ErrorMiddleware()
    event = build_message()
    object.__setattr__(event, "answer", AsyncMock())

    async def handler(event, data):
        raise RuntimeError("unexpected")

    with pytest.raises(RuntimeError):
        await middleware(handler, event, {})


@pytest.mark.asyncio
async def test_user_middleware_injects_user():
    created_user = SimpleNamespace(id=1)
    get_or_create = AsyncMock(return_value=created_user)
    middleware = UserMiddleware(user_getOrCreate=get_or_create)
    event_user = SimpleNamespace(id=42)

    async def handler(event, data):
        return data["user"]

    result = await middleware(handler, SimpleNamespace(), {"event_from_user": event_user})
    assert result == created_user
    get_or_create.assert_awaited_once_with(event_user)
