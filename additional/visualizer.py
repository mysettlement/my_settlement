#!/usr/bin/env python3
"""
Скрипт для визуализации SQLAlchemy моделей
Использует библиотеку sqlalchemy-data-model-visualizer для создания SVG диаграмм
"""

import logging
import os
import sys
from pathlib import Path

# Добавляем родительскую директорию в путь для импорта модулей
sys.path.append(str(Path(__file__).parent.parent))

try:
    from sqlalchemy_data_model_visualizer import generate_data_model_diagram, add_web_font_and_interactivity
except ImportError:
    print("Ошибка: библиотека sqlalchemy-data-model-visualizer не установлена.")
    print("Установите её командой: pip install sqlalchemy-data-model-visualizer")
    sys.exit(1)

try:
    import config
    from models import User, Settlement, Settler
    
    # Настройка логирования
    logger = logging.getLogger(__name__)
    log = config.setup_logging(logger)
except Exception as e:
    # Fallback настройка логирования если config недоступен
    from models import User, Settlement, Settler
    
    logging.basicConfig(
        level=logging.INFO,
        format='ℹ️  %(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    log = logger


def create_diagram():
    """
    Создает SVG диаграмму для всех SQLAlchemy моделей в проекте
    """
    try:
        # Список всех моделей для визуализации
        models = [
            User,
            Settlement, 
            Settler
        ]
        
        # Имя выходного файла
        output_file = "settlement_data_model_diagram"
        
        log.info("Начинаем создание диаграммы моделей...")
        
        # Генерируем базовую диаграмму
        generate_data_model_diagram(
            models=models,
            output_file=output_file,
            add_labels=True
        )
        
        log.info(f"Базовая диаграмма создана: {output_file}.svg")
        
        # Создаем интерактивную версию с веб-шрифтами
        interactive_file = f"{output_file}_interactive.svg"
        add_web_font_and_interactivity(
            f"{output_file}.svg", 
            interactive_file
        )
        
        log.info(f"Интерактивная диаграмма создана: {interactive_file}")
        
        # Проверяем, что файлы созданы
        base_file = Path(f"{output_file}.svg")
        interactive_file_path = Path(interactive_file)
        
        if base_file.exists():
            log.info(f"✅ Базовая диаграмма сохранена: {base_file.absolute()}")
        else:
            log.error(f"❌ Не удалось создать базовую диаграмму: {base_file}")
            
        if interactive_file_path.exists():
            log.info(f"✅ Интерактивная диаграмма сохранена: {interactive_file_path.absolute()}")
        else:
            log.error(f"❌ Не удалось создать интерактивную диаграмму: {interactive_file_path}")
            
        return True
        
    except Exception as e:
        log.error(f"Ошибка при создании диаграммы: {e}")
        return False


def main():
    """
    Основная функция для запуска визуализатора
    """
    log.info("🚀 Запуск визуализатора SQLAlchemy моделей")
    
    # Проверяем наличие моделей
    try:
        from models import User, Settlement, Settler
        log.info("✅ Модели успешно импортированы")
    except ImportError as e:
        log.error(f"❌ Ошибка импорта моделей: {e}")
        return False
    
    # Создаем диаграмму
    success = create_diagram()
    
    if success:
        log.info("🎉 Визуализация завершена успешно!")
    else:
        log.error("❌ Визуализация завершилась с ошибками")
        
    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log.info("⏹️  Визуализация прервана пользователем")
        sys.exit(1)
    except Exception as e:
        log.critical(f"💥 Критическая ошибка: {e}")
        sys.exit(1)
