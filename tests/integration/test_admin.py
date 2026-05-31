from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from wtforms import Form
import app.db as app_db
from app.admin import AdminAuth, PythonListField
from app.config import settings


pytestmark = pytest.mark.integration
ADMIN_ENTRYPOINT_PATH = Path(__file__).resolve().parents[2] / "admin-entrypoint.py"


spec = importlib.util.spec_from_file_location("admin_entrypoint", ADMIN_ENTRYPOINT_PATH)
admin_entrypoint = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(admin_entrypoint)


class _FakeRequest:
    def __init__(self, form_data=None):
        self._form_data = form_data or {}
        self.session = {}

    async def form(self):
        return self._form_data


def test_python_list_field_parses_and_validates():
    class _DummyForm(Form):
        emojis = PythonListField("Emojis")

    field = _DummyForm().emojis
    field.process_formdata(["['😀', '😎']"])
    assert field.data == ["😀", "😎"]

    with pytest.raises(Exception):
        field.process_formdata(["not-a-list"])


@pytest.mark.asyncio
async def test_admin_auth_login_logout_and_authenticate():
    auth = AdminAuth(secret_key="secret")
    request = _FakeRequest({"username": settings.ADMIN_USERNAME, "password": settings.ADMIN_PASSWORD})

    assert await auth.login(request) is True
    assert await auth.authenticate(request) is True
    assert await auth.logout(request) is True
    assert request.session == {}


def test_create_admin_app_redirects_to_admin(test_engine, monkeypatch):
    monkeypatch.setattr(app_db, "engine", test_engine)
    app = admin_entrypoint.create_admin_app()
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)
    assert response.status_code in {302, 307}
    assert response.headers["location"] == "/admin"
