from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import URL, text

import logging

from config import settings, setup_logging
import models
from database import Base


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
        await conn.run_sync(Base.metadata.create_all)
        async with SessionLocal() as session:
            resources_to_add = [
                {"name": "Зерно", "emoji": "🌾", "description": "Основной продукт земледелия", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 1
                {"name": "Картофель", "emoji": "🥔", "description": "Корнеплод для питания", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 2
                {"name": "Грибы", "emoji": "🍄‍🟫", "description": "Лесные грибы", "category": "Еда", "rarity": models.RarityLevel.UNCOMMON}, # 3
                {"name": "Ягоды", "emoji": "🫐", "description": "Разнообразные собранные в лесу ягоды", "category": "Еда", "rarity": models.RarityLevel.UNCOMMON}, # 4
                {"name": "Рыба", "emoji": "🐟", "description": "Пойманная в реке рыба", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 5
                {"name": "Шерсть", "emoji": "☁️", "description": "Шерсть овец для создания ткани (🧺)", "category": "Материалы", "rarity": models.RarityLevel.COMMON}, # 6
                {"name": "Молоко", "emoji": "🥛", "description": "Молоко полученное из коровы", "category": "Еда", "rarity": models.RarityLevel.COMMON}, # 6
                {"name": "Ткань", "emoji": "🧺", "description": "Ткань из шерсти (☁️) для создания бинтов (🩹) и одежды", "category": "Материалы", "rarity": models.RarityLevel.UNCOMMON}, # 7
                {"name": "Лён", "emoji": "🪴", "description": '<a href="https://ru.wikipedia.org/wiki/Лён">Лён</a> для создания <a href="https://ru.wikipedia.org/wiki/Льняное_масло">лечебных масел</a> и пропитывания ими ткани (🧺) для создания бинтов (🩹)', "category": "Материалы", "rarity": models.RarityLevel.COMMON}, # 8
                {"name": "Кора", "emoji": "🎋", "description": 'Кора <a href="https://ru.wikipedia.org/wiki/Осина">осиного дерева</a> для создания лечебных отваров (🍵)', "category": "Материалы", "rarity": models.RarityLevel.UNCOMMON}, # 9
                {"name": "Отвар", "emoji": "🍵", "description": "Целебный отвар из коры осины (🎋) для лечения болезней", "category": "Лекарства", "rarity": models.RarityLevel.UNCOMMON}, # 10 - 3 отвара для лечения болезни
                {"name": "Бинт", "emoji": "🩹", "description": "Пропитанная лечебными маслами из льна (🪴) ткань для перевязки ран", "category": "Лекарства", "rarity": models.RarityLevel.RARE}, # 11 - 1 бинт для лечения раны
                {"name": "Сигара", "emoji": "🚬", "description": "ток для админов", "category": "прочитал лох", "rarity": models.RarityLevel.COMMON} # 12
            ]
            for resource in resources_to_add:
                resource_data = resource.copy()
                resource_data['rarity'] = resource['rarity'].value
                await session.execute(text("INSERT INTO resources (name, emoji, description, category, rarity) VALUES (:name, :emoji, :description, :category, :rarity) ON CONFLICT (name) DO NOTHING"), resource_data)
 
            professions_to_add = [
                {"name": "Землепашец", "emoji": "🌻", "description": "Жнёт 🌾/🥔/🍄‍🟫/🫐 упорно трудясь в поле али лесу.", "required_level": 0}, # 1
                {"name": "Ловчий", "emoji": "🐾", "description": "В лесу силки ставит, зверя бьёт да рыбу сетью тянет, скотину пасёт, чтоб 🐟/🍖/🥛/☁️ в общину нести.", "required_level": 0}, # 2
                {"name": "Знахарь", "emoji": "📔", "description": "Внемлет мольбам селян, варит 🍵/🩹, собирая 🪴/🎋 своими руками.", "required_level": 0} # 3
            ]
            for profession in professions_to_add:
                await session.execute(text("INSERT INTO professions (name, emoji, description, required_level) VALUES (:name, :emoji, :description, :required_level) ON CONFLICT (name) DO NOTHING"), profession)

            await session.commit()
        log.info("База данных инициализирована.")
        