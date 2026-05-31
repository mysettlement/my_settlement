from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import arrow
import pytest
from sqlalchemy import select

import app.db as app_db
from app import core, models
from app.gamer import ProgressBar
from tests.support.aiogram_builders import build_chat, build_message, build_user
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
async def test_resource_lookup_and_random_quantity(db_session, monkeypatch):
    resource = await create_resource(db_session, name="Зерно", emoji="🌾", rarity=models.RarityLevel.COMMON)
    await db_session.commit()

    assert await core.resource_getByEmoji(db_session, "🌾") is not None
    assert await core.resource_getByEmoji(None, "🌾") is not None

    monkeypatch.setattr(core.random, "random", lambda: 0.0)
    monkeypatch.setattr(core.random, "randint", lambda start, end: end)
    assert await core.resource_getRandomQuantity(resource) == models.RARITY_QUANTITY_RANGES[models.RarityLevel.COMMON][1]

    monkeypatch.setattr(core.random, "random", lambda: 2.0)
    assert await core.resource_getRandomQuantity(resource) == 0


@pytest.mark.asyncio
async def test_building_scope_and_requirements(db_session):
    owner = await create_user(db_session, telegram_id=5101)
    second_user = await create_user(db_session, telegram_id=5102)
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5101)
    profession = await create_profession(db_session, emoji="🌻")
    settler = await create_settler(db_session, user=owner, settlement=settlement, profession=profession)
    other_settler = await create_settler(db_session, user=second_user, settlement=settlement)
    resource = await create_resource(db_session, name="Руда", emoji="🪨", category="Материалы")
    await grant_resource(db_session, settler=settler, resource=resource, quantity=5)
    building_type = await create_building_type(
        db_session,
        name="Scope Farm",
        emoji="🏠1",
        is_private=False,
        required_professions={"🌻": 1},
        costs={resource: 3},
    )
    private_type = await create_building_type(
        db_session,
        name="Private Barn",
        emoji="🏠2",
        is_private=True,
    )
    await create_building(db_session, building_type=building_type, settlement=settlement)
    await create_building(db_session, building_type=private_type, settlement=settlement, owner=settler)
    await db_session.commit()

    town_buildings = await core.building_getByScope(settlement, settler, "town", db_session)
    my_buildings = await core.building_getByScope(settlement, settler, "my", db_session)
    assert len(town_buildings) == 1
    assert len(my_buildings) == 1

    ok_prof, prof_text, ok_res, cost_text = await core.building_checkRequirements(
        settlement,
        settler,
        building_type,
        db_session,
    )
    assert ok_prof is True
    assert ok_res is True
    assert "🌻" in prof_text
    assert "🪨" in cost_text

    missing_prof, _, _, _ = await core.building_checkRequirements(
        settlement,
        other_settler,
        building_type,
        db_session,
    )
    assert missing_prof is True

    unknown_type = await create_building_type(
        db_session,
        name="Unknown Guild",
        emoji="🏚",
        required_professions={"❓": 1},
    )
    await db_session.commit()

    missing_prof, prof_text, _, _ = await core.building_checkRequirements(
        settlement,
        settler,
        unknown_type,
        db_session,
    )
    assert missing_prof is False
    assert "Неизвестная профессия" in prof_text


@pytest.mark.asyncio
async def test_settler_add_money_resource_and_dispatch(db_session, monkeypatch):
    owner = await create_user(db_session, telegram_id=5201)
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5201)
    settler = await create_settler(db_session, user=owner, settlement=settlement)
    resource = await create_resource(db_session, name="Зерно", emoji="🌾")
    await db_session.commit()

    assert await core.settler_addMoney(settler, db_session, 5) == 5

    success, label = await core.settler_updateResource(settler, db_session, "🌾", 3)
    assert success is True
    assert label == "🌾 3"

    fail, _ = await core.settler_updateResource(settler, db_session, "🌾", -10, check_if_enough=True)
    assert fail is False

    monkeypatch.setattr(core, "settler_addExp", AsyncMock())
    obtained = await core.settler_add(settler, db_session, "💰", 2)
    assert obtained == {"💰": 2}
    obtained = await core.settler_add(settler, db_session, "🗂", 2)
    assert obtained == {"🗂": 2}
    core.settler_addExp.assert_awaited()


@pytest.mark.asyncio
async def test_bonus_set_and_reward_helpers(monkeypatch):
    settler_bonuses = core.BonusSet()
    settler_bonuses.add_bonus(
        {
            "global_chance_multiplier": 0.1,
            "resource_quantity_modifier": {"🌾": 1},
        }
    )
    settlement_bonuses = core.BonusSet()
    settlement_bonuses.add_bonus(
        {
            "global_quantity_multiplier": 0.5,
            "resource_chance_multiplier": {"🌾": 0.2},
        }
    )
    settler_bonuses.merge(settlement_bonuses)
    data = settler_bonuses.to_dict()
    assert data["global_chance_multiplier"] == 0.1

    item = models.LootItem(emoji="🌾", min_qty=2, max_qty=2, qty_is_fixed=True, chance=0.5)
    effective = core._get_effective_bonuses(item, settler_bonuses, settlement_bonuses)
    assert effective.resource_qty_mod["🌾"] == 1

    resource = models.Resource(name="Зерно", emoji="🌾", category="Еда", rarity=models.RarityLevel.COMMON)
    monkeypatch.setattr(core.random, "random", lambda: 0.0)
    assert await core._roll_chance(item, resource, effective) is True

    qty = await core._calculate_quantity(item, resource, effective)
    assert qty >= 2


@pytest.mark.asyncio
async def test_building_check_requirements_without_costs_or_professions(db_session):
    owner = await create_user(db_session, telegram_id=5251)
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5251)
    settler = await create_settler(db_session, user=owner, settlement=settlement)
    building_type = await create_building_type(
        db_session,
        name="Free Square",
        emoji="🆓",
    )
    await db_session.commit()

    ok_prof, prof_text, ok_res, cost_text = await core.building_checkRequirements(
        settlement,
        settler,
        building_type,
        db_session,
    )

    assert ok_prof is True
    assert ok_res is True
    assert prof_text == "Никто не требуется!"
    assert cost_text == "Бесплатно!"


@pytest.mark.asyncio
async def test_building_start_building_error_paths(db_session, monkeypatch):
    owner = await create_user(db_session, telegram_id=5271)
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5271)
    settler = await create_settler(db_session, user=owner, settlement=settlement)
    resource = await create_resource(db_session, name="Доски", emoji="🪵", category="Материалы")
    building_type = await create_building_type(
        db_session,
        name="Shed",
        emoji="🛖",
        costs={resource: 2},
    )
    await db_session.commit()

    success, text = await core.building_startBuilding(settler, 999999, "town", db_session)
    assert success is False
    assert "Чертеж не найден" in text

    monkeypatch.setattr(core, "building_checkRequirements", AsyncMock(return_value=(False, "need profession", True, "")))
    success, text = await core.building_startBuilding(settler, building_type.id, "town", db_session)
    assert success is False
    assert "need profession" in text

    monkeypatch.setattr(core, "building_checkRequirements", AsyncMock(return_value=(True, "", True, "")))
    success, text = await core.building_startBuilding(settler, building_type.id, "town", db_session)
    assert success is False
    assert "Недостаточно ресурсов" in text
    assert "🪵" in text


@pytest.mark.asyncio
async def test_settler_update_resource_random_and_missing_paths(db_session, monkeypatch):
    owner = await create_user(db_session, telegram_id=5281)
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5281)
    settler = await create_settler(db_session, user=owner, settlement=settlement)
    resource = await create_resource(db_session, name="Зерно", emoji="🌾")
    await db_session.commit()

    max_qty = models.RARITY_QUANTITY_RANGES[resource.rarity][1]
    monkeypatch.setattr(core.random, "randint", lambda start, end: end)

    success, label = await core.settler_updateResource(settler, db_session, "🌾", quantity=None)
    assert success is True
    assert label == f"🌾 {max_qty}"

    success, text = await core.settler_updateResource(settler, db_session, "❌", 1)
    assert success is False
    assert "не найден" in text

    ghost_settler = SimpleNamespace(id=999999)
    success, text = await core.settler_updateResource(
        ghost_settler,
        db_session,
        "🌾",
        1,
        resource=resource,
    )
    assert success is False
    assert "Поселенец не найден" in text


@pytest.mark.asyncio
async def test_private_chat_and_missing_settler_short_circuits(db_session):
    private_chat = build_chat(chat_id=999, chat_type="private", title=None)
    assert await core.settlement_getOrCreate(private_chat) is None

    owner = await create_user(db_session, telegram_id=5289, name="Ghost owner")
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5289)
    await db_session.commit()

    ghost_settler = SimpleNamespace(id=999999)
    assert await core.settler_addMoney(ghost_settler, db_session, 5) is None
    assert await core.settler_updateQuote(ghost_settler, settlement, db_session, add_quote=1) is None


@pytest.mark.asyncio
async def test_settler_update_quote_covers_middle_rank_branch(db_session, monkeypatch):
    sender = AsyncMock()
    monkeypatch.setattr(core.telegram_gateway, "send_message", sender)
    randint_values = iter([2, 3])
    monkeypatch.setattr(core.random, "randint", lambda start, end: next(randint_values))

    user = await create_user(db_session, telegram_id=5291, name="Journeyman")
    settlement = await create_settlement(db_session, owner=user, chat_id=-5291)
    target_quote = round(20 * 0.85 + 6)
    settler = await create_settler(
        db_session,
        user=user,
        settlement=settlement,
        level=20,
        quote=target_quote - 1,
        target_quote=target_quote,
    )
    settler.target_exp = 999
    await db_session.commit()

    await core.settler_updateQuote(settler, settlement, db_session, add_quote=1)
    await db_session.refresh(settler)

    assert settler.quote == 0
    assert settler.quote_is_completed is True
    assert settler.balance == 23
    sender.assert_awaited_once()


@pytest.mark.asyncio
async def test_settler_update_quote_covers_high_rank_overtime_branch(db_session, monkeypatch):
    sender = AsyncMock()
    monkeypatch.setattr(core.telegram_gateway, "send_message", sender)
    randint_values = iter([4, 5])
    monkeypatch.setattr(core.random, "randint", lambda start, end: next(randint_values))

    user = await create_user(db_session, telegram_id=5292, name="Veteran")
    settlement = await create_settlement(db_session, owner=user, chat_id=-5292)
    target_quote = round((40 * 0.85 + 6) + (2 * (1 + 1)))
    settler = await create_settler(
        db_session,
        user=user,
        settlement=settlement,
        level=40,
        quote=target_quote - 1,
        target_quote=target_quote,
        overtime_is_toggled=True,
    )
    settler.overtime_count = 1
    settler.target_exp = 999
    await db_session.commit()

    await core.settler_updateQuote(settler, settlement, db_session, add_quote=1)
    await db_session.refresh(settler)

    assert settler.quote == 0
    assert settler.quote_is_completed is True
    assert settler.target_quote == target_quote
    assert settler.balance == 45
    sender.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_workflow_requirement_and_callback_branches(db_session, monkeypatch):
    owner = await create_user(db_session, telegram_id=5293, name="Worker")
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5293)
    settler = await create_settler(db_session, user=owner, settlement=settlement, level=1)
    fiber = await create_resource(db_session, name="Волокно", emoji="🪢", category="Материалы")
    await db_session.commit()

    tg_user = build_user(user_id=owner.telegram_id, first_name="Worker")
    chat = build_chat(chat_id=settlement.chat_id, chat_type="supergroup", title=settlement.name)

    monkeypatch.setattr(core.utils, "can_start_work", lambda chat_id: (True, ""))
    monkeypatch.setattr(core.utils, "start_work", lambda chat_id: None)
    monkeypatch.setattr(core.utils, "get_work_remaining_time", lambda chat_id: 7)

    level_message = build_message(text="work", from_user=tg_user, chat=chat)
    object.__setattr__(level_message, "answer", AsyncMock())
    level_work = models.Work(
        id="need-level",
        name="Need Level",
        emoji="📚",
        requirements={"level": 5},
        steps=[ProgressBar(bar_length=1)],
        texts={"step_0_status": "go"},
    )
    assert await core.settler_startWorkflow(level_message, level_work, owner, settler) is False
    assert "Требуемая ступень" in level_message.answer.await_args.args[0]

    resource_message = build_message(text="work", from_user=tg_user, chat=chat, message_id=2)
    object.__setattr__(resource_message, "answer", AsyncMock())
    resource_work = models.Work(
        id="need-resource",
        name="Need Resource",
        emoji="🪢",
        requirements={"🪢": 1},
        steps=[ProgressBar(bar_length=1)],
        texts={"step_0_status": "go"},
    )
    assert await core.settler_startWorkflow(resource_message, resource_work, owner, settler) is False
    assert "Недостаточно ресурсов" in resource_message.answer.await_args.args[0]

    callback = SimpleNamespace(
        message=SimpleNamespace(chat=chat, edit_text=AsyncMock()),
        answer=AsyncMock(),
    )
    callback_work = models.Work(
        id="callback-work",
        name="Callback Work",
        emoji="🛠",
        requirements={},
        steps=[ProgressBar(bar_length=1)],
        texts={"step_0_status": "go"},
    )
    assert await core.settler_startWorkflow(callback, callback_work, owner, settler) is True
    callback.answer.assert_awaited_once_with("🛠 Callback Work!")
    callback.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_rewards_skips_failed_roll_and_ignores_empty_bonus_buildings(db_session, monkeypatch):
    monkeypatch.setattr(core.random, "random", lambda: 1.0)

    owner = await create_user(db_session, telegram_id=5294)
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5294)
    settler = await create_settler(db_session, user=owner, settlement=settlement)
    grain = await create_resource(db_session, name="Зерно", emoji="🌾")
    empty_bonus_type = await create_building_type(
        db_session,
        name="Empty Barn",
        emoji="🫙",
        bonuses={},
    )
    await create_building(db_session, building_type=empty_bonus_type, settlement=settlement)
    await db_session.commit()

    settler_bonuses, settlement_bonuses = await core.setter_getBonuses(settler, db_session)
    assert settler_bonuses.to_dict() == {}
    assert settlement_bonuses.to_dict() == {}

    work = models.Work(
        id="failed-roll",
        name="Failed Roll",
        emoji="🌾",
        rewards=[models.LootItem(emoji="🌾", chance=0.1)],
    )
    obtained = await core.settler_applyRewards(work, settler, db_session)
    assert obtained == {}


@pytest.mark.asyncio
async def test_reward_helpers_use_default_chance_and_quantity(monkeypatch):
    resource = models.Resource(name="Руда", emoji="🪨", category="Материалы", rarity=models.RarityLevel.COMMON)
    bonuses = core.BonusSet()
    item = models.LootItem(emoji="🪨", chance=None)

    monkeypatch.setattr(core.random, "random", lambda: 0.0)
    monkeypatch.setattr(core.random, "randint", lambda start, end: end)

    assert await core._roll_chance(item, resource, bonuses) is True
    assert await core._calculate_quantity(item, resource, bonuses) == models.RARITY_QUANTITY_RANGES[resource.rarity][1]


@pytest.mark.asyncio
async def test_settler_can_work_and_start_workflow(db_session, monkeypatch):
    owner = await create_user(db_session, telegram_id=5301)
    settlement = await create_settlement(db_session, owner=owner, chat_id=-5301)
    settler = await create_settler(db_session, user=owner, settlement=settlement, level=5)
    herb = await create_resource(db_session, name="Трава", emoji="🪴")
    await grant_resource(db_session, settler=settler, resource=herb, quantity=5)
    await db_session.commit()

    future = arrow.now().shift(hours=1).int_timestamp
    settler.work_is_completed = True
    settler.last_work_time = future
    can_work, _ = core.settler_canWorkNow(settler, fallback=True)
    assert can_work is False

    settler.work_is_completed = False
    tg_user = build_user(user_id=owner.telegram_id, first_name="Worker")
    chat = build_chat(chat_id=settlement.chat_id, chat_type="supergroup", title=settlement.name)
    message = build_message(text="work", from_user=tg_user, chat=chat)
    object.__setattr__(message, "answer", AsyncMock())

    monkeypatch.setattr(core.utils, "can_start_work", lambda chat_id: (True, ""))
    monkeypatch.setattr(core.utils, "start_work", lambda chat_id: None)
    monkeypatch.setattr(core.utils, "get_work_remaining_time", lambda chat_id: 42)

    work = models.Work(
        id="core-start",
        name="Core Start",
        emoji="🛠",
        requirements={"🪴": 2},
        steps=[ProgressBar(bar_length=2)],
        texts={"step_0_status": "status"},
    )

    user = await core.user_getOrCreate(tg_user)
    result = await core.settler_startWorkflow(message, work, user, settler)
    assert result is True
    message.answer.assert_awaited()

    callback = SimpleNamespace(
        chat=chat,
        answer=AsyncMock(),
        message=SimpleNamespace(chat=chat, edit_text=AsyncMock()),
    )
    monkeypatch.setattr(core.utils, "can_start_work", lambda chat_id: (False, "busy"))
    assert await core.settler_startWorkflow(callback, work, user, settler) is False
