from __future__ import annotations

from datetime import datetime

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


async def create_user(
    session: AsyncSession,
    *,
    telegram_id: int = 1000,
    name: str = "Tester",
    language: str | None = "ru",
    timezone: str = "Europe/Kiev",
):
    user = models.User(
        telegram_id=telegram_id,
        name=name,
        language=language,
        timezone=timezone,
    )
    session.add(user)
    await session.flush()
    return user


async def create_settlement(
    session: AsyncSession,
    *,
    owner: models.User,
    chat_id: int = -1000,
    name: str = "Village",
):
    settlement = models.Settlement(
        chat_id=chat_id,
        name=name,
        owner_id=owner.id,
    )
    session.add(settlement)
    await session.flush()
    return settlement


async def create_profession(
    session: AsyncSession,
    *,
    name: str = "Землепашец",
    emoji: str = "🌻",
    required_level: int = 0,
    crafts: str | None = None,
    collects: str | None = None,
):
    profession = models.Profession(
        name=name,
        emoji=emoji,
        required_level=required_level,
        crafts=crafts,
        collects=collects,
    )
    session.add(profession)
    await session.flush()
    return profession


async def create_settler(
    session: AsyncSession,
    *,
    user: models.User,
    settlement: models.Settlement,
    profession: models.Profession | None = None,
    level: int = 0,
    quote: int = 0,
    target_quote: int = 6,
    balance: int = 0,
    overtime_is_toggled: bool = False,
    quote_is_completed: bool = False,
):
    settler = models.Settler(
        user_id=user.id,
        settlement_id=settlement.id,
        profession_id=profession.id if profession else None,
        level=level,
        quote=quote,
        target_quote=target_quote,
        balance=balance,
        overtime_is_toggled=overtime_is_toggled,
        quote_is_completed=quote_is_completed,
    )
    session.add(settler)
    await session.flush()
    return settler


async def create_resource(
    session: AsyncSession,
    *,
    name: str,
    emoji: str,
    category: str = "Еда",
    rarity: models.RarityLevel = models.RarityLevel.COMMON,
):
    resource = models.Resource(
        name=name,
        emoji=emoji,
        category=category,
        rarity=rarity,
    )
    session.add(resource)
    await session.flush()
    return resource


async def grant_resource(
    session: AsyncSession,
    *,
    settler: models.Settler,
    resource: models.Resource,
    quantity: int,
):
    await session.execute(
        insert(models.settler_resources).values(
            settler_id=settler.id,
            resource_id=resource.id,
            quantity=quantity,
        )
    )
    await session.flush()


async def create_building_type(
    session: AsyncSession,
    *,
    name: str = "Ферма",
    emoji: str = "🏠🌾",
    is_private: bool = False,
    bonuses: dict | None = None,
    required_professions: dict | None = None,
    costs: dict[models.Resource, int] | None = None,
    construction_time: int = 60,
):
    building_type = models.BuildingType(
        name=name,
        emoji=emoji,
        is_private=is_private,
        bonuses=bonuses or {},
        required_professions=required_professions or {},
        construction_time=construction_time,
        max_level=5,
    )
    session.add(building_type)
    await session.flush()

    for resource, quantity in (costs or {}).items():
        await session.execute(
            models.building_type_costs.insert().values(
                building_type_id=building_type.id,
                resource_id=resource.id,
                quantity=quantity,
            )
        )
    await session.flush()
    return building_type


async def create_building(
    session: AsyncSession,
    *,
    building_type: models.BuildingType,
    settlement: models.Settlement,
    owner: models.Settler | None = None,
    under_construction_until: datetime | None = None,
):
    building = models.Building(
        building_type_id=building_type.id,
        settlement_id=settlement.id,
        owner_id=owner.id if owner else None,
        under_construction_until=under_construction_until,
    )
    session.add(building)
    await session.flush()
    return building
