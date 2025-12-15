import logging
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


# === НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ===

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # -- CONFIG SETTINGS --
    LOGS_PATH: str = "logs/"
    TURN_ON_COLORS: bool = True
    
    # -- USER SETTINGS --
    BOT_TOKEN: str
    BOT_USERNAME: str # Без @ или t.me/. Пример: mysettlementbot
    
    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    ADMIN_IDS: list[int]
    TYPOS_PERCENT: int = 80 # Процент допустимых опечаток в командах. Меньше 60 не рекомендуется.
    WORK_COOLDOWN_HOURS: float = 0.03 # Кулдаун на работу
    WORK_TIMEOUT_SECONDS: int = 180 # Таймаут выполнения работы
    CRAFT_COOLDOWN_HOURS: float = 0.03 # Кулдаун на смену профессии
    SETTLEMENT_NAME_CHANGE_COOLDOWN_HOURS: float = 0.1 # Кулдаун на смену названия поселения

    @property
    def DB_URL(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()


# === НАСТРОЙКА ЛОГИРОВАНИЯ ===

class Colors:
    # Основные цвета
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Цвета текста
    BLACK = '\033[30m'
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Яркие цвета
    BRIGHT_BLACK = '\033[90m'
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'
    
    # Цвета фона
    BG_BLACK = '\033[40m'
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'
    BG_MAGENTA = '\033[45m'
    BG_CYAN = '\033[46m'
    BG_WHITE = '\033[47m'

#? Можно ли изменять? Да!
class Changeable:
    # Цвета для разных уровней логирования
    COLORS = {
        'DEBUG': Colors.BRIGHT_BLACK,
        'INFO': Colors.BRIGHT_GREEN,
        'WARNING': Colors.BRIGHT_YELLOW,
        'ERROR': Colors.BRIGHT_RED,
        'CRITICAL': Colors.BRIGHT_RED + Colors.BOLD
    }

    # Эмодзи для разных уровней логирования
    EMOJIS = {
        'DEBUG': '🔍 ',
        'INFO': 'ℹ️  ',
        'WARNING': '⚠️  ',
        'ERROR': '❌ ',
        'CRITICAL': '🚨 '
    }

    # Форматы даты и времени
    FILE_DATEFMT = '%Y-%m-%d %H:%M:%S'
    CONSOLE_DATEFMT = '%H:%M:%S'


class ColoredFormatter(logging.Formatter):
    def format(self, record):
        # Базовое форматирование
        log_message = super().format(record)
        
        # Добавляем цвета для консольного вывода
        if hasattr(record, 'levelname') and record.levelname in Changeable.COLORS:
            color = Changeable.COLORS[record.levelname]
            reset = Colors.RESET

            # Эмодзи для разных уровней
            if Changeable.EMOJIS:
                emoji = Changeable.EMOJIS.get(record.levelname, '')
            else:
                emoji = ''
            
            # Сообщение с цветом и эмодзи
            formatted_message = f"{color}{emoji}{log_message}{reset}"
            return formatted_message
        
        return log_message

def setup_logging(logger):
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    path = settings.LOGS_PATH
    os.makedirs(path, exist_ok=True)
    
    # Форматтер для файла (без цветов)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(message)s',
        datefmt=Changeable.FILE_DATEFMT
    )
    
    # Форматтер для консоли (с цветами)
    if Changeable.COLORS:
        console_formatter = ColoredFormatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt=Changeable.CONSOLE_DATEFMT
        )
    else:
        console_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt=Changeable.CONSOLE_DATEFMT
    )
    
    # Обработчик для файла
    file_handler = logging.FileHandler(
        path + f"{logger.name}.log", 
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.DEBUG)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger
