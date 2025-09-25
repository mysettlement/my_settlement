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
    
    log.warning("🚨 НАЧИНАЕМ ПОЛНУЮ ПЕРЕЗАГРУЗКУ БАЗЫ ДАННЫХ!")
    log.warning("⚠️  ВСЕ ДАННЫЕ БУДУТ УДАЛЕНЫ!")
    
    engine = create_async_engine(
        url=settings.DB_URL,
        pool_size=20
    )
    
    try:
        async with engine.begin() as conn:
            # Удаляем все таблицы
            log.info("🗑️  Удаление всех таблиц...")
            await conn.run_sync(Base.metadata.drop_all)
            log.info("✅ Все таблицы удалены")
            
            # Создаем таблицы заново
            log.info("🏗️  Создание новых таблиц...")
            await conn.run_sync(Base.metadata.create_all)
            log.info("✅ Таблицы пересозданы")
            
            # Проверяем, что таблицы созданы
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_type = 'BASE TABLE'
            """))
            
            tables = [row[0] for row in result.fetchall()]
            log.info(f"📋 Созданные таблицы: {', '.join(tables)}")
            
        log.info("🎉 База данных успешно перезагружена!")
        log.info("✨ Все данные очищены, схема пересоздана")
        
    except Exception as e:
        log.error(f"❌ Ошибка при перезагрузке базы данных: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print("=" * 60)
    print("🔄 СКРИПТ ПЕРЕЗАГРУЗКИ БАЗЫ ДАННЫХ")
    print("=" * 60)
    print("⚠️  ВНИМАНИЕ: Все данные будут удалены!")
    print()
    
    # Запрашиваем подтверждение
    confirm = input("Вы уверены, что хотите продолжить? (yes/no): ").lower().strip()
    
    if confirm in ["no", "n", "нет", "н"]:
        print("❌ Операция отменена пользователем")
    else:
        print("🚀 Запуск перезагрузки...")
        asyncio.run(reset_database())
