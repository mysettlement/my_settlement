from __future__ import annotations

import re

import asyncpg

from app import config


VALID_DB_NAME = re.compile(r"^[A-Za-z0-9_]+$")


async def ensure_test_database_exists() -> None:
    db_name = config.settings.DB_NAME
    if not VALID_DB_NAME.fullmatch(db_name):
        raise ValueError(f"Unsafe test database name: {db_name}")

    connection = await asyncpg.connect(
        user=config.settings.DB_USER,
        password=config.settings.DB_PASS,
        host=config.settings.DB_HOST,
        port=config.settings.DB_PORT,
        database="postgres",
    )
    try:
        exists = await connection.fetchval(
            "SELECT 1 FROM pg_database WHERE datname = $1",
            db_name,
        )
        if not exists:
            await connection.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await connection.close()
