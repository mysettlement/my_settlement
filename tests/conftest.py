from __future__ import annotations

import os
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import NullPool


ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_env_file(env_path: Path, *, override: bool) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        if override or key not in os.environ:
            os.environ[key] = value


_load_env_file(ROOT_DIR / ".env.test", override=False)
_load_env_file(ROOT_DIR / ".env.test.local", override=True)

import app.db as app_db
import app.utils as app_utils
from app import config
from app.models import Base
from tests.support.database import ensure_test_database_exists


@pytest.fixture(autouse=True)
def cleanup_runtime_state():
    app_utils.reset_runtime_state()
    yield
    app_utils.reset_runtime_state()


@pytest_asyncio.fixture
async def test_engine():
    try:
        await ensure_test_database_exists()
    except Exception as exc:
        pytest.skip(f"PostgreSQL test database is unavailable: {exc}")

    engine, _ = app_db.create_engine_and_sessionmaker(
        config.settings.DB_URL,
        poolclass=NullPool,
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(test_engine, monkeypatch):
    async with test_engine.begin() as connection:
        await connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await connection.execute(text("CREATE SCHEMA public"))
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=test_engine,
        expire_on_commit=False,
    )

    monkeypatch.setattr(app_db, "engine", test_engine)
    monkeypatch.setattr(app_db, "SessionLocal", session_factory)

    async with session_factory() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def seeded_reference_data(db_session):
    await app_db.init_db()
    async with app_db.SessionLocal() as session:
        yield session
