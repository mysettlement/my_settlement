from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app import core, models
import app.telegram_gateway as telegram_gateway
from tests.support.aiogram_builders import build_chat, build_user
from tests.support.factories import (
    create_building,
    create_building_type,
    create_profession,
    create_resource,
    create_settlement,
    create_settler,
    create_user,
    grant_resource,
)


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_user_get_or_create_creates_and_updates_name(db_session):
    telegram_user = build_user(user_id=2001, first_name="Alice")
    created = await core.user_getOrCreate(telegram_user)
    assert created.telegram_id == 2001

    renamed_user = build_user(user_id=2001, first_name="Alicia")
    updated = await core.user_getOrCreate(renamed_user)
    assert updated.id == created.id
    assert updated.name == "Alicia"


@pytest.mark.asyncio
async def test_settlement_get_or_create_uses_group_owner(db_session, monkeypatch):
    owner = build_user(user_id=3001, first_name="Owner")
    monkeypatch.setattr(core.utils, "get_group_owner", AsyncMock(return_value=owner))

    chat = build_chat(chat_id=-3001, title="Owner village")
    settlement = await core.settlement_getOrCreate(chat)
    same_settlement = await core.settlement_getOrCreate(chat)

    assert settlement.id == same_settlement.id
    assert settlement.name == "Owner village"


@pytest.mark.asyncio
async def test_building_start_building_consumes_resources_and_creates_building(db_session):
    owner = await create_user(db_session, telegram_id=4001)
    profession = await create_profession(db_session, emoji="🌻")
    settlement = await create_settlement(db_session, owner=owner, chat_id=-4001)
    settler = await create_settler(
        db_session,
        user=owner,
        settlement=settlement,
        profession=profession,
    )
    metal = await create_resource(db_session, name="Сырьё", emoji="🔩", category="Материалы")
    ore = await create_resource(db_session, name="Руда", emoji="🪨", category="Материалы")
    await grant_resource(db_session, settler=settler, resource=metal, quantity=12)
    await grant_resource(db_session, settler=settler, resource=ore, quantity=25)

    building_type = await create_building_type(
        db_session,
        costs={metal: 10, ore: 20},
        required_professions={"🌻": 1},
    )
    await db_session.commit()

    success, text = await core.building_startBuilding(settler, building_type.id, "town", db_session)
    assert success is True
    assert "Стройка началась" in text

    quantities = (
        await db_session.execute(
            select(models.settler_resources.c.quantity).where(
                models.settler_resources.c.settler_id == settler.id
            )
        )
    ).scalars().all()
    assert sorted(quantities) == [2, 5]

    buildings = (await db_session.execute(select(models.Building))).scalars().all()
    assert len(buildings) == 1
    assert buildings[0].owner_id is None


@pytest.mark.asyncio
async def test_settler_add_exp_promotes_rank_and_notifies(db_session, monkeypatch):
    sender = AsyncMock()
    monkeypatch.setattr(telegram_gateway, "send_message", sender)

    user = await create_user(db_session, telegram_id=5001, name="Hero")
    settlement = await create_settlement(db_session, owner=user, chat_id=-5001)
    settler = await create_settler(
        db_session,
        user=user,
        settlement=settlement,
        level=15,
    )
    settler.rank = "Крестьянин"
    settler.exp = 37
    settler.target_exp = 37
    await db_session.commit()

    updated = await core.settler_addExp(settler, db_session, 1)

    assert updated.level == 16
    assert updated.rank == "Вольный"
    assert updated.emoji in {"🌾", "🌱", "🍃"}
    sender.assert_awaited_once()


@pytest.mark.asyncio
async def test_settler_update_quote_rewards_and_resets_progress(db_session, monkeypatch):
    sender = AsyncMock()
    monkeypatch.setattr(telegram_gateway, "send_message", sender)
    randint_values = iter([1, 2])
    monkeypatch.setattr(core.random, "randint", lambda start, end: next(randint_values))

    user = await create_user(db_session, telegram_id=6001, name="Worker")
    settlement = await create_settlement(db_session, owner=user, chat_id=-6001)
    settler = await create_settler(
        db_session,
        user=user,
        settlement=settlement,
        level=1,
        quote=6,
        target_quote=7,
    )
    await db_session.commit()

    await core.settler_updateQuote(settler, settlement, db_session, add_quote=1)
    await db_session.refresh(settler)

    assert settler.quote == 0
    assert settler.quote_is_completed is True
    assert settler.balance > 0
    sender.assert_awaited()


@pytest.mark.asyncio
async def test_settler_apply_rewards_uses_building_bonuses(db_session, monkeypatch):
    monkeypatch.setattr(core.random, "random", lambda: 0.0)

    owner = await create_user(db_session, telegram_id=7001)
    settlement = await create_settlement(db_session, owner=owner, chat_id=-7001)
    profession = await create_profession(db_session, emoji="🌻")
    settler = await create_settler(
        db_session,
        user=owner,
        settlement=settlement,
        profession=profession,
    )
    grain = await create_resource(db_session, name="Зерно", emoji="🌾")
    public_type = await create_building_type(
        db_session,
        name="Public farm",
        emoji="🏚🌾",
        bonuses={"resource_quantity_modifier": {"🌾": 1}},
    )
    private_type = await create_building_type(
        db_session,
        name="Private farm",
        emoji="🏡🌾",
        is_private=True,
        bonuses={"resource_chance_multiplier": {"🌾": 0.4}},
    )
    await create_building(db_session, building_type=public_type, settlement=settlement)
    await create_building(db_session, building_type=private_type, settlement=settlement, owner=settler)
    await db_session.commit()

    work = models.Work(
        id="reward-test",
        name="Reward test",
        emoji="🌾",
        rewards=[
            models.LootItem(
                emoji="🌾",
                min_qty=2,
                max_qty=2,
                qty_is_fixed=True,
                chance=0.6,
            )
        ],
    )

    obtained = await core.settler_applyRewards(work, settler, db_session)

    assert obtained["🌾"] == 3
