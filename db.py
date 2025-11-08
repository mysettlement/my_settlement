from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import URL, text

import logging

from config import settings, setup_logging
import models
from models import Base


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


async def init_db():
    async with engine.begin() as conn:
        async with SessionLocal() as session:
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
                        log.info("🛠️ Таблицы не найдены. Пересоздание...")
                        await conn.run_sync(Base.metadata.create_all)
                        
                        result = await conn.execute(text("""
                            SELECT table_name 
                            FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_type = 'BASE TABLE'
                        """))
                        
                        tables = [row[0] for row in result.fetchall()]
                        log.info(f"📋 Созданные таблицы: {', '.join(tables)}")
                    else:
                        log.info(f"🔍 Найдено таблиц: {', '.join(tables)}")
                
            except Exception as e:
                log.error(f"❌ Ошибка при перезагрузке базы данных: {e}")
                raise

            resources_to_add = [
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
                {"name": "Сырьё", "emoji": "🔩", "description": "Сырьё из руды (🪨) для создания мебели", "category": "Материалы", "from_resource": "🪨", "rarity": models.RarityLevel.UNCOMMON}, # 
                {"name": "Лён", "emoji": "🪴", "description": '<a href="https://ru.wikipedia.org/wiki/Лён">Лён</a> для создания <a href="https://ru.wikipedia.org/wiki/Льняное_масло">лечебных масел</a> и пропитывания ими ткани (🧺) для создания бинтов (🩹)', "category": "Материалы", "for": "🩹", "rarity": models.RarityLevel.COMMON}, # 
                {"name": "Кора", "emoji": "🎋", "description": 'Кора <a href="https://ru.wikipedia.org/wiki/Осина">осиного дерева</a> для создания лечебных отваров (🍵)', "category": "Материалы", "for_resource": "🍵", "rarity": models.RarityLevel.UNCOMMON}, # 
                {"name": "Отвар", "emoji": "🍵", "description": "Целебный отвар из коры осины (🎋) для лечения болезней", "category": "Лекарства", "from_resource": "🎋", "rarity": models.RarityLevel.UNCOMMON}, #  - 3 отвара для лечения болезни
                {"name": "Бинт", "emoji": "🩹", "description": "Пропитанная лечебными маслами из льна (🪴) ткань (🧺) для перевязки ран", "category": "Лекарства", "from_resource": "🪴+🧺", "rarity": models.RarityLevel.RARE}, #  - 1 бинт для лечения раны
            ]
            for resource in resources_to_add:
                resource_data = resource.copy()
                resource_data['rarity'] = resource['rarity'].value
                if 'from_resource' not in resource_data:
                    resource_data['from_resource'] = None
                if 'for_resource' not in resource_data:
                    resource_data['for_resource'] = None
                await session.execute(text("INSERT INTO resources (name, emoji, description, category, from_resource, for_resource, rarity) VALUES (:name, :emoji, :description, :category, :from_resource, :for_resource, :rarity) ON CONFLICT (name) DO NOTHING"), resource_data)
 
            professions_to_add = [
                {"name": "Землепашец", "emoji": "🌻", "description": "Жнёт 🌾/🥔/🍄‍🟫/🫐 упорно трудясь в поле али лесу.", "collects": "🌾/🥔/🍄‍🟫/🫐", "required_level": 0}, # 1
                {"name": "Знахарь", "emoji": "📔", "description": "Внемлет мольбам селян, варит 🍵/🩹, собирая 🪴/🎋 своими руками.", "crafts": "🍵/🩹", "collects": "🪴/🎋", "required_level": 0}, # 2
                {"name": "Ловчий", "emoji": "🐾", "description": "В лесу силки ставит, зверя бьёт да рыбу сетью тянет, скотину пасёт, чтоб 🐟/🍖/🥛/☁️ в общину нести.", "collects": "🐟/🍖/🥛/☁️", "required_level": 0}, # 3
                {"name": "Ремесленник", "emoji": "⚒️", "description": "", "crafts": "🧺/🧵/🔩", "required_level": 0}, # 4
                {"name": "Мастеровой", "emoji": "🧰", "description": "", "crafts": "🥾/🧥/🪑/🗡", "required_level": 0} # 5
            ]

            for profession in professions_to_add:
                profession_data = profession.copy()
                if 'crafts' not in profession_data:
                    profession_data['crafts'] = None
                if 'collects' not in profession_data:
                    profession_data['collects'] = None
                await session.execute(text("INSERT INTO professions (name, emoji, description, crafts, collects, required_level) VALUES (:name, :emoji, :description, :crafts, :collects, :required_level) ON CONFLICT (name) DO NOTHING"), profession_data)

            await session.commit()
        log.info("База данных инициализирована.")
        