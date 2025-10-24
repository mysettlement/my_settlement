#!/usr/bin/env python3
"""
Скрипт для полной перезагрузки базы данных
Удаляет все таблицы и данные, затем пересоздает схему
"""

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

from config import settings, setup_logging
import models
from database import Base

import logging

log = setup_logging(logging.getLogger(__name__))

async def reset_database():
    """Полностью перезагружает базу данных - удаляет все и пересоздает"""
    
    engine = create_async_engine(
        url=settings.DB_URL,
        pool_size=20
    )
    
    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """))
            
            tables = [row[0] for row in result.fetchall()]
            log.info(f"🔍 Найдено таблиц: {', '.join(tables)}")
            
            if tables:
                for table in tables:
                    try:
                        await conn.execute(text(f'DROP TABLE IF EXISTS "{table}" CASCADE'))
                    except Exception as e:
                        log.warning(f"⚠️  Не удалось удалить таблицу {table}: {e}")
                log.info("✅ Все таблицы удалены")
            else:
                log.info("ℹ️  Таблицы для удаления не найдены")
            await conn.run_sync(Base.metadata.create_all)
            
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """))
            
            tables = [row[0] for row in result.fetchall()]
            log.info(f"📋 Созданные таблицы: {', '.join(tables)}")
        
    except Exception as e:
        log.error(f"❌ Ошибка при перезагрузке базы данных: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    
    # Запрашиваем подтверждение
    confirm = input("Вы уверены, что хотите продолжить? (yes/no): ").lower().strip()
    
    if confirm in ["no", "n", "нет", "н"]:
        log.info("❌ Операция отменена пользователем")
    else:
        asyncio.run(reset_database())
