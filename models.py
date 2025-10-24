from sqlalchemy import Table, Column, Integer, BigInteger, String, ForeignKey, PickleType, Boolean, Enum as SAEnum
from sqlalchemy.orm import relationship, Mapped, mapped_column, declarative_base
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.ext.hybrid import hybrid_property
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from typing import ClassVar

from database import Base
from gamer import Hitting, TimerStep, Workflow, Harvesting, Catch, Milking



# === ПЕРЕЧИСЛЕНИЯ ===
class RarityLevel(str, Enum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"

RARITY_DROP_PROBABILITIES = {
    RarityLevel.COMMON: 50 / 100.0,
    RarityLevel.UNCOMMON: 35 / 100.0,
    RarityLevel.RARE: 8 / 100.0,
    RarityLevel.EPIC: 3.5 / 100.0,
    RarityLevel.LEGENDARY: 0.5 / 100.0
}

RARITY_QUANTITY_RANGES = {
    RarityLevel.COMMON: (3, 5),
    RarityLevel.UNCOMMON: (2, 4),
    RarityLevel.RARE: (1, 3),
    RarityLevel.EPIC: (1, 2),
    RarityLevel.LEGENDARY: (1, 1)
}



# === СВЯЗУЮЩИЕ ТАБЛИЦЫ ===
user_settlements = Table(
    "user_settlements",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.id"), primary_key=True),
    Column("settlement_id", BigInteger, ForeignKey("settlements.id"), primary_key=True)
)

settler_resources = Table(
    "settler_resources",
    Base.metadata,
    Column("settler_id", BigInteger, ForeignKey("settlers.id"), primary_key=True),
    Column("resource_id", BigInteger, ForeignKey("resources.id"), primary_key=True),
    Column("quantity", Integer, default=0)
)



# === МОДЕЛИ ===
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True) # внутренний id
    user_id = Column(BigInteger, unique=True, index=True) # id пользователя в телеграме
    name = Column(String)
    compact_style = Column(Boolean, server_default="False")
    owned_settlements = relationship("Settlement", back_populates="owner")
    memberships = relationship("Settler", back_populates="user")

class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(BigInteger, primary_key=True, index=True)
    chat_id = Column(BigInteger, unique=True, index=True)
    name = Column(String)
    owner_id = Column(BigInteger, ForeignKey("users.id"))
    owner = relationship("User", back_populates="owned_settlements")
    members = relationship("Settler", back_populates="settlement")

class Settler(Base):
    __tablename__ = "settlers"

    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id")) # внутренний id
    settlement_id = Column(BigInteger, ForeignKey("settlements.id"))

    level = Column(Integer, server_default="0")
    exp = Column(Integer, server_default="0")
    target_exp = Column(Integer, server_default="7")
    rank = Column(String, server_default="Крестьянин")
    emoji = Column(String, server_default="🧑‍🌾")
    rank_emoji_available = Column(MutableList.as_mutable(PickleType), default=[])
    special_emoji_available = Column(MutableList.as_mutable(PickleType), default=[])

    profession_id = Column(BigInteger, ForeignKey("professions.id"), nullable=True)
    work_is_completed = Column(Boolean, server_default="False")
    last_work_time = Column(BigInteger, server_default="0")
    last_profession_change = Column(BigInteger, server_default="0")

    quote = Column(Integer, server_default="0")
    target_quote = Column(Integer, server_default="6")
    quote_is_completed = Column(Boolean, server_default="False")

    overtime_count = Column(Integer, server_default="0")
    overtime_is_toggled = Column(Boolean, server_default="False")

    balance = Column(Integer, server_default="0")
    income = Column(Integer, server_default="0")

    user = relationship("User", back_populates="memberships")
    settlement = relationship("Settlement", back_populates="members")
    resources = relationship("Resource", secondary=settler_resources, backref="settlers")
    profession = relationship("Profession", backref="settlers")


class Resource(Base):
    __tablename__ = "resources"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, unique=True)
    emoji = Column(String, nullable=True)
    description = Column(String, nullable=True)
    category = Column(String)
    rarity = Column(SAEnum(RarityLevel), default=RarityLevel.COMMON, nullable=False)

class Profession(Base):
    __tablename__ = "professions"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, unique=True)
    emoji = Column(String, nullable=True)
    description = Column(String, nullable=True)
    required_level = Column(Integer)


# === РАБОТЫ ===

class WorkflowWork():
    #* Многошаговая работа
    tea_brewing_workflow = None
    milking_workflow = None
    
    @classmethod
    def get_ploughman_harvesting(cls):
        return Harvesting(
            objects=["🌾", "🥔", "🍄‍🟫", "🫐", "🌱", "🌱"],
            rules={
                "forbidden": ["🌱"],
                "click": {
                    "🌾": " ",
                    "🥔": " ",
                    "🍄‍🟫": " ",
                    "🫐": " "
                },
                "win_check": lambda field: not any(cell == "🌾" or cell == "🥔" or cell == "🍄‍🟫" or cell == "🫐" for row in field for cell in row)
            },
            size=4,
            status_text_func=lambda game: "🌻 <b>Поле для пахоты:</b>\nЖните 🌾/🥔/🍄‍🟫/🫐. Токмо не троньте саженцы 🌱 — они ещё сил набирают!" if not game.game_over else ("🌾 Поле очищено! Урожай собран!" if game.won else "💀 Урожай испорчен!"),
            lose_text="💀 Урожай испорчен!",
            win_text="🌾 Поле очищено!",
            continue_text="✅ Собрано!"
        )

    @classmethod
    def get_tea_brewing_workflow(cls):
        if cls.tea_brewing_workflow is None:
            
            # Шаг 1: Измельчение коры (Hitting)
            step1 = Hitting(
                target="🎋",
                empty=" ", 
                size=3,
                rounds=3,
                status_text_func=lambda game: f"🥣 <b>Измельчение коры</b> — осталось {game.rounds - game.current_round + 1}/{game.rounds}\nПоместите кору в ступку! 🎋" if not game.game_over else (f"✅ <b>Кора измельчена!</b> {game.score}/{game.rounds}" if game.won else f"💀 </b>Кора испорчена!</b> {game.score}/{game.rounds}"),
                hit_text="🎋 Кора добавлена!",
                miss_text="💀 Кора испорчена!",
                win_text="✅ Кора измельчена!"
            )
            
            # Шаг 2: Заваривание (TimerStep)
            step2 = TimerStep(
                button_text="💧 Налить кипяток",
                button2_text="🍵 Заваривается...",
                duration=30,
                status_text_func=lambda step: f"🍵 <b>Заваривание отвара...</b>\nОсталось: {step.get_remaining_time()}с" if step.started and not step.completed else ("💧 Налейте кипяток для заваривания" if not step.started else "🍵 Отвар готов!"),
                start_text="💧 Кипяток налит!",
                complete_text="🍵 Отвар готов!"
            )
            
            # Workflow
            cls.tea_brewing_workflow = Workflow(
                steps=[step1, step2],
                name="🍵 Приготовление отвара",
                status_text_func=lambda workflow: (workflow.get_current_step().get_status_text() if not workflow.completed else "🍵 <b>Отвар готов!</b>"),
                complete_text="🍵 Отвар готов!",
                cooldown_on_fail=False
            )
        
        return cls.tea_brewing_workflow

    @classmethod
    def get_healer_herb_gathering(cls):
        return Harvesting(
            objects=["🪴", "🎋", " ", " "],
            rules={
                "click": {
                    "🪴": " ",
                    "🎋": " "
                },
                "win_check": lambda field: not any(cell == "🪴" or cell == "🎋" for row in field for cell in row)
            },
            size=5,
            status_text_func=lambda game: "🪴 <b>Сбор трав:</b>\nСобирайте 🪴/🎋!" if not game.game_over else ("✅ <b>Травы собраны!</b>" if game.won else "💀 <b>Сбор не удался!</b>"),
            lose_text="💀 Сбор не удался!",
            win_text="🪴 Травы собраны!",
            continue_text="✅ Собрано!"
        )

    @classmethod
    def get_catcher_fishing(cls):
        return Catch(
            target="🐟",
            empty=" ",
            size=4,
            rounds=7,
            status_text_func=lambda game: (
                f"🎣 <b>Ловля</b> — осталось {game.rounds - game.current_round + 1}/{game.rounds}\nЖми на цель, коли увидишь 🐟!"
                if not game.game_over else (
                    f"✅ <b>Добрый улов!</b> {game.score}/{game.rounds}" if game.won else f"💀 <b>Рыба сорвалась!</b> {game.score}/{game.rounds}"
                )
            ),
            hit_text="✅ Попал!",
            miss_text="💀 Сорвалась!",
            win_text="🐟 Рыба уловлена!"
        )

    @classmethod
    def get_catcher_milking(cls):
        if cls.milking_workflow is None:
            # Шаг 1: Подготовка (Harvesting)
            step1 = Harvesting(
                objects=["🐄", "💢", "💢", " "],
                rules={
                    "forbidden": ["💢"],
                    "click": {"🐄": " "},
                    "win_check": lambda field: not any(cell == "🐄" for row in field for cell in row)
                },
                size=3,
                status_text_func=lambda game: "🪣 <b>Успокоение коровы:</b>\nПогладь корову 🐄" if not game.game_over else ("✅ <b>Корова успокоилась!</b>" if game.won else "💀 <b>Корова разозлилась!</b>"),
                lose_text="💀 Корова разозлилась!",
                win_text="✅ Корова успокоилась!",
                continue_text="✅ Продолжайте гладить...",
                required_at_least_one="🐄"
            )

            # Шаг 2: Доение (Milking)
            step2 = Milking(
                target_presses=10,
                status_text_func=lambda game: (
                    f"🐮 <b>Доение коровы:</b>\nЧередуй нажим на ручки: 💧💧\n<b>{game.current_presses}/{game.target_presses}</b>"
                    if not game.game_over else (
                        "🥛 <b>Ведро наполнено!</b>" if game.won else "💀 <b>Корова вас лягнула!</b>"
                    )
                ),
                lose_text="💀 Корова вас лягнула!",
                win_text="🥛 Ведро наполнено!",
                continue_text="✅ Продолжайте доить..."
            )

            # Workflow
            cls.milking_workflow = Workflow(
                steps=[step1, step2],
                name="🪣 Доение коровы",
                status_text_func=lambda workflow: (workflow.get_current_step().get_status_text() if not workflow.completed else "🥛 <b>Молоко собрано!</b>"),
                complete_text="🥛 Молоко собрано!",
                cooldown_on_fail=True
            )
        return cls.milking_workflow

# === PYDANTIC СХЕМЫ ===
class SettlementBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=30, example="Моё поселение")

class ResourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=15, example="Дерево")
    emoji: str = Field(..., min_length=1, max_length=2, example="🪵")
    description: str = None
    category: str = Field(..., min_length=1, max_length=30, example="Материалы")
    rarity: RarityLevel = RarityLevel.COMMON
    base_value: int = 0

    RARITY_TRANSLATIONS: ClassVar[dict[RarityLevel, str]] = {
        RarityLevel.COMMON: "🌿 Обильное",
        RarityLevel.UNCOMMON: "🐚 Невсякое",
        RarityLevel.RARE: "🍀 <b>Редкостное</b>",
        RarityLevel.EPIC: "🎍 <b>Диковинное</b>",
        RarityLevel.LEGENDARY: "🌈 <b>Сказочное</b>"
    }

    @computed_field
    def rarity_display(self) -> str:
        return self.RARITY_TRANSLATIONS[self.rarity]

class ProfessionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=20, example="Фермер")
    description: str = None
    required_level: int = 1
