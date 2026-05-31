from __future__ import annotations

from sqlalchemy import select

import pytest

import app.db as app_db
from app import models


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_init_db_creates_reference_data_and_is_idempotent(db_session):
    await app_db.init_db()
    await app_db.init_db()

    async with app_db.SessionLocal() as session:
        resources = (await session.execute(select(models.Resource))).scalars().all()
        professions = (await session.execute(select(models.Profession))).scalars().all()
        building_types = (await session.execute(select(models.BuildingType))).scalars().all()

    assert len(resources) >= 5
    assert len({resource.emoji for resource in resources}) == len(resources)
    assert len(professions) >= 5
    assert len(building_types) >= 2
