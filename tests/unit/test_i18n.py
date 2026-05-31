from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import app.db as app_db
from app.i18n import I18nMiddleware, create_translator_hub


pytestmark = pytest.mark.unit


def _write_locale(base_dir: Path, language: str, text: str) -> None:
    language_dir = base_dir / language
    language_dir.mkdir(parents=True, exist_ok=True)
    (language_dir / "common.ftl").write_text(text, encoding="utf-8")


class _FakeExecuteResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


class _FakeSession:
    def __init__(self, value):
        self.value = value
        self.execute_calls = 0

    async def execute(self, stmt):
        self.execute_calls += 1
        return _FakeExecuteResult(self.value)


class _FakeSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_create_translator_hub_uses_custom_locales(tmp_path):
    _write_locale(tmp_path, "ru", "simple-message = Privet")
    _write_locale(tmp_path, "uk", "simple-message = Vitayu")
    _write_locale(tmp_path, "en", "simple-message = Hello")

    hub = create_translator_hub(tmp_path)
    translator = hub.get_translator_by_locale("en")

    assert translator.get("simple-message") == "Hello"


@pytest.mark.asyncio
async def test_i18n_middleware_prefers_db_language_and_caches(tmp_path, monkeypatch):
    _write_locale(tmp_path, "ru", "simple-message = Privet")
    _write_locale(tmp_path, "uk", "simple-message = Vitayu")
    _write_locale(tmp_path, "en", "simple-message = Hello")

    fake_session = _FakeSession("uk")
    monkeypatch.setattr(app_db, "SessionLocal", lambda: _FakeSessionContext(fake_session))
    middleware = I18nMiddleware(create_translator_hub(tmp_path))

    async def handler(event, data):
        return data["i18n"].get("simple-message")

    event_user = SimpleNamespace(id=10, language_code="en")
    result_one = await middleware(handler, SimpleNamespace(), {"event_from_user": event_user})
    result_two = await middleware(handler, SimpleNamespace(), {"event_from_user": event_user})

    assert result_one == "Vitayu"
    assert result_two == "Vitayu"
    assert fake_session.execute_calls == 1


@pytest.mark.asyncio
async def test_i18n_middleware_falls_back_to_event_language_and_en(tmp_path, monkeypatch):
    _write_locale(tmp_path, "ru", "simple-message = Privet")
    _write_locale(tmp_path, "uk", "simple-message = Vitayu")
    _write_locale(tmp_path, "en", "simple-message = Hello")

    monkeypatch.setattr(app_db, "SessionLocal", lambda: _FakeSessionContext(_FakeSession(None)))
    middleware = I18nMiddleware(create_translator_hub(tmp_path))

    async def handler(event, data):
        return data["i18n"].get("simple-message")

    unsupported_user = SimpleNamespace(id=11, language_code="zz")
    supported_user = SimpleNamespace(id=12, language_code="ru")

    assert await middleware(handler, SimpleNamespace(), {"event_from_user": unsupported_user}) == "Hello"
    assert await middleware(handler, SimpleNamespace(), {"event_from_user": supported_user}) == "Privet"
