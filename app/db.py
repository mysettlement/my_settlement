from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text, select

import logging

from app.config import settings, setup_logging
from app.models import Base
import app.models as models
import app.utils as utils


log = setup_logging(logging.getLogger(__name__))

engine = create_async_engine(
    url=settings.DB_URL,
    pool_size=20
)

SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

@asynccontextmanager
async def try_session(session: AsyncSession | None = None):
    """
    Если сессия передана — использует её (не закрывая).
    Если нет — создает новую, использует и закрывает.
    """
    if session:
        yield session
    else:
        async with SessionLocal() as new_session:
            yield new_session


async def init_db():
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """))
            
            tables = [row[0] for row in result.fetchall()]
            if not tables:
                log.warning("🛠️ Таблицы не найдены. Пересоздание...")
                await utils.notify_developers("⚠️ <b>Таблицы в базе данных не найдены.</b>\nВыполняется пересоздание...")
                await conn.run_sync(Base.metadata.create_all)
                
                result = await conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                """))
                
                tables = [row[0] for row in result.fetchall()]
                log.info(f"📋 Созданные таблицы: {', '.join(tables)}.")
            else:
                log.info(f"🔍 Найдены таблицы: {', '.join(tables)}.")

    except Exception as e:
        log.error(f"❌ Ошибка при перезагрузке базы данных: {e}")
        await utils.notify_developers(f"❌ Ошибка при перезагрузке базы данных: {e}")
        raise


    try:
        async with SessionLocal() as session:
            resources_data = [
                {"name": "Зерно", "emoji": "🌾", "description": "Основной продукт земледелия", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 
                {"name": "Картофель", "emoji": "🥔", "description": "Корнеплод для питания", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 
                {"name": "Грибы", "emoji": "🍄‍🟫", "description": "Лесные грибы", "category": "Еда", "rarity": models.RarityLevel.UNCOMMON}, # 
                {"name": "Ягоды", "emoji": "🫐", "description": "Разнообразные собранные в лесу ягоды", "category": "Еда", "rarity": models.RarityLevel.UNCOMMON}, # 
                {"name": "Рыба", "emoji": "🐟", "description": "Пойманная в реке рыба", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 
                {"name": "Шерсть", "emoji": "☁️", "description": "Шерсть овец для создания ткани (🧺)", "category": "Материалы", "for_resource": "🧺", "rarity": models.RarityLevel.COMMON}, # 
                {"name": "Молоко", "emoji": "🥛", "description": "Полученное из коровы молоко", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 
                {"name": "Мясо", "emoji": "🍖", "description": "Полученное из животного мясо", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 
                {"name": "Ткань", "emoji": "🧺", "description": "Ткань из шерсти (☁️) для создания бинтов (🩹) и одежды", "category": "Материалы", "from_resource": "☁️", "for_resource": "🩹", "rarity": models.RarityLevel.UNCOMMON}, # 
                {"name": "Нити", "emoji": "🧵", "description": "Нитки из шерсти (☁️) для пошива одежды", "category": "Материалы", "from_resource": "☁️", "rarity": models.RarityLevel.UNCOMMON}, # 
                {"name": "Руда", "emoji": "🪨", "description": "Руда из земли для получения сырья (🔩)", "category": "Материалы", "for_resource": "🔩", "rarity": models.RarityLevel.COMMON}, #
                {"name": "Сырьё", "emoji": "🔩", "description": "Сырьё из руды (🪨) для создания мебели", "category": "Материалы", "from_resource": "🪨", "rarity": models.RarityLevel.UNCOMMON}, # 
                {"name": "Лён", "emoji": "🪴", "description": '<a href="https://ru.wikipedia.org/wiki/Лён">Лён</a> для создания <a href="https://ru.wikipedia.org/wiki/Льняное_масло">лечебных масел</a> и пропитывания ими ткани (🧺) для создания бинтов (🩹)', "category": "Материалы", "for_resource": "🩹", "rarity": models.RarityLevel.COMMON}, # 
                {"name": "Кора", "emoji": "🎋", "description": 'Кора <a href="https://ru.wikipedia.org/wiki/Осина">осинового дерева</a> для создания лечебных отваров (🍵)', "category": "Материалы", "for_resource": "🍵", "rarity": models.RarityLevel.UNCOMMON}, # 
                {"name": "Отвар", "emoji": "🍵", "description": "Целебный отвар из коры осины (🎋) для лечения болезней", "category": "Лекарства", "from_resource": "🎋", "rarity": models.RarityLevel.UNCOMMON}, #  - 3 отвара для лечения болезни
                {"name": "Бинт", "emoji": "🩹", "description": "Пропитанная лечебными маслами из льна (🪴) ткань (🧺) для перевязки ран", "category": "Лекарства", "from_resource": "🪴+🧺", "rarity": models.RarityLevel.RARE}, #  - 1 бинт для лечения раны
            ]
            stmt = select(models.Resource.emoji)
            existing_res_names = (await session.execute(stmt)).scalars().all()
            existing_res_set = set(existing_res_names)
            if existing_res_set:
                log.info(f"🔍 Найдены ресурсы: {', '.join(existing_res_set)}")

            new_resources = []
            added_res = []
            for res in resources_data:
                if res["emoji"] not in existing_res_set:
                    new_resources.append(models.Resource(**res))
                    added_res.append(f"{res['emoji']} {res['name']}")
            
            if new_resources:
                session.add_all(new_resources)
                await session.flush()
                log.info(f"📋 Добавлены ресурсы: {', '.join(added_res)}.")
            
            all_resources = await session.execute(select(models.Resource))
            resources_map = {r.emoji: r for r in all_resources.scalars().all()}
            

            professions_data = [
                {"name": "Землепашец", "emoji": "🌻", "description": "Жнёт 🌾/🥔/🍄‍🟫/🫐 упорно трудясь в поле али лесу.", "collects": "🌾/🥔/🍄‍🟫/🫐", "required_level": 0}, # 1
                {"name": "Знахарь", "emoji": "📔", "description": "Внемлет мольбам селян, варит 🍵/🩹, собирая 🪴/🎋 своими руками.", "crafts": "🍵/🩹", "collects": "🪴/🎋", "required_level": 0}, # 2
                {"name": "Ловчий", "emoji": "🐾", "description": "В лесу силки ставит, зверя бьёт да рыбу сетью тянет, скотину пасёт, чтоб 🐟/🍖/🥛/☁️ в общину нести.", "collects": "🐟/🍖/🥛/☁️", "required_level": 0}, # 3
                {"name": "Ремесленник", "emoji": "⚒️", "description": "", "crafts": "🧺/🧵/🔩", "required_level": 0}, # 4
                {"name": "Мастеровой", "emoji": "🧰", "description": "", "crafts": "🥾/🧥/🪑/🗡", "required_level": 0} # 5
            ]
            stmt = select(models.Profession.emoji)
            existing_prof_emojis = (await session.execute(stmt)).scalars().all()
            existing_prof_set = set(existing_prof_emojis)
            if existing_prof_set:
                log.info(f"🔍 Найдены профессии: {', '.join(existing_prof_set)}")

            new_profs = []
            added_profs = []
            for prof in professions_data:
                if prof["emoji"] not in existing_prof_set:
                    new_profs.append(models.Profession(**prof))
                    added_profs.append(f"{prof['emoji']} {prof['name']}")

            if new_profs:
                session.add_all(new_profs)
                await session.flush()
                log.info(f"📋 Добавлены профессии: {', '.join(added_profs)}.")

            
            buildings_data = [
                {
                    "name": "Ферма",
                    "emoji": "🏠🌾",
                    "description": "Позволяет землепашцам собирать дополнительные <b>Зерно</b> 🌾 и <b>Картофель</b> 🥔.",
                    "is_private": False,
                    "max_level": 5,
                    "construction_time": 60,
                    "costs": {
                        "🔩": 10,
                        "🪨": 20
                    },
                    "required_professions": {"🌻": 3, "⚒️": 1},
                    "bonuses": {
                        "resource_quantity_modifier": {"🌾": 1, "🥔": 1},
                        "resource_chance_multiplier": {"🍄‍🟫": 0.1, "🫐": 0.1}
                    }
                },
                {
                    "name": "Рыбная Лавка",
                    "emoji": "🏠🐟",
                    "description": "Позволяет ловчим собирать дополнительную Рыбу 🐟.",
                    "is_private": False,
                    "max_level": 5,
                    "construction_time": 60,
                    "costs": {
                        "🔩": 10,
                        "🪨": 20
                    },
                    "required_professions": {"🐾": 3, "⚒️": 1},
                    "bonuses": {
                        "resource_quantity_modifier": {"🐟": 1}
                    }
                }
            ]

            added_buildings = []
            for b_data in buildings_data:
                stmt = select(models.BuildingType).where(models.BuildingType.emoji == b_data["emoji"])
                existing_b = (await session.execute(stmt)).scalar_one_or_none()
                log.debug(f"{b_data['emoji']} {b_data['name']} - {'Найдено' if existing_b else 'Не найдено'}")

                if not existing_b:
                    new_building = models.BuildingType(
                        name=b_data["name"],
                        emoji=b_data["emoji"],
                        description=b_data["description"],
                        is_private=b_data.get("is_private", True),
                        max_level=b_data["max_level"],
                        construction_time=b_data["construction_time"],
                        required_professions=b_data.get("required_professions", {}),
                        bonuses=b_data.get("bonuses", {})
                    )
                    session.add(new_building)
                    await session.flush()

                    costs = b_data.get("costs", {})
                    for res_emoji, qty in costs.items():
                        res_obj = resources_map.get(res_emoji)
                        if res_obj:
                            await session.execute(
                                models.building_type_costs.insert().values(
                                    building_type_id=new_building.id,
                                    resource_id=res_obj.id,
                                    quantity=qty
                                )
                            )
                        else:
                            log.warning(f"⚠️ Не найден ресурс {res_emoji} для здания {b_data['emoji']} {b_data['name']}")
                    added_buildings.append(f"{b_data['emoji']} {b_data['name']}")
            if added_buildings:
                log.info(f"📋 Добавлены чертежи: {', '.join(added_buildings)}.")


            await session.commit()
            log.info("База данных инициализирована.")
    
    except Exception as e:
        log.error(f"❌ Ошибка при инициализации базы данных: {e}")
        await utils.notify_developers(f"❌ Ошибка при инициализации базы данных: {e}")
        await session.rollback()
        raise
        