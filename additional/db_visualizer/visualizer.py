#!/usr/bin/env python3
"""
Скрипт для визуализации SQLAlchemy моделей
Использует библиотеку sqlalchemy-data-model-visualizer для создания SVG диаграмм
"""

import sys
from pathlib import Path
import os
import logging

# Add parent directory to Python path before imports
sys.path.append(str(Path(__file__).parent.parent))
os.environ["PATH"] += os.pathsep + 'C:/Users/pcs/programs/Graphviz/bin'

import app.config as config
from app.models import User, Settlement, Settler, Resource, Profession

try:
    from sqlalchemy_data_model_visualizer import generate_data_model_diagram
    import cairosvg
except ImportError as e:
    if "sqlalchemy-data-model-visualizer" in str(e):
        print("Ошибка: библиотека sqlalchemy-data-model-visualizer не установлена.")
        print("Установите её командой: pip install sqlalchemy-data-model-visualizer")
    elif "cairosvg" in str(e):
        print("Ошибка: библиотека cairosvg не установлена.")
        print("Установите её командой: pip install cairosvg")
    sys.exit(1)

try:
    # Настройка логирования
    logger = logging.getLogger(__name__)
    log = config.setup_logging(logger)
except Exception as e:
    
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
            Settler,
            Resource,
            Profession
        ]
        
        # Путь для сохранения файлов
        current_dir = Path(__file__).parent
        output_file = str(current_dir / "settlement_data_model_diagram")
        
        log.info("Начинаем создание диаграммы моделей...")
        
        # Генерируем базовую диаграмму
        generate_data_model_diagram(
            models=models,
            output_file=output_file,
            add_labels=True
        )
        
        # Проверяем, что файл создан
        base_file = Path(str(output_file) + ".svg")
        
        if base_file.exists():
            log.info(f"✅ Базовая диаграмма сохранена: {base_file.absolute()}")
            
            # Конвертируем SVG в PNG
            png_file = base_file.with_suffix('.png')
            try:
                cairosvg.svg2png(url=str(base_file), write_to=str(png_file))
                log.info(f"✅ PNG версия сохранена: {png_file.absolute()}")
            except Exception as e:
                log.error(f"❌ Ошибка при конвертации в PNG: {e}")
            
            # Открываем базовую диаграмму
            os.startfile(str(base_file.absolute()))
        else:
            log.error(f"❌ Не удалось создать базовую диаграмму: {base_file}")
            
        return True
        
    except Exception as e:
        log.error(f"Ошибка при создании диаграммы: {e}")
        return False


def main():
    """
    Основная функция для запуска визуализатора
    """
    log.info("🚀 Запуск визуализатора SQLAlchemy моделей")
    
    try:
        from app.models import User, Settlement, Settler
        log.info("✅ Модели успешно импортированы")
    except ImportError as e:
        log.error(f"❌ Ошибка импорта моделей: {e}")
        return False
    
    # Создаем диаграмму
    success = create_diagram()
    return success


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log.info("⏹️  Визуализация прервана пользователем")
        sys.exit(1)
    except Exception as e:
        log.critical(f"Критическая ошибка: {e}")
        sys.exit(1)
