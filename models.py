from sqlalchemy import func, Table, Column, Integer, BigInteger, String, ForeignKey, PickleType, Boolean, Enum as SAEnum, DateTime, Float
from sqlalchemy.sql import text
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.ext.mutable import MutableList
from typing import List, Optional, Dict, Callable, Any
from enum import Enum
from dataclasses import dataclass, field
import copy
import random

from gamer import Step, Hitting, Timer, Workflow, Harvesting, Catch, Alternation, ProgressBar


Base = declarative_base()


#* === ПЕРЕЧИСЛЕНИЯ ===
class RarityLevel(str, Enum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"

RARITY_DROP_PROBABILITIES = {
    RarityLevel.COMMON: 70 / 100.0,
    RarityLevel.UNCOMMON: 45 / 100.0,
    RarityLevel.RARE: 10 / 100.0,
    RarityLevel.EPIC: 3 / 100.0,
    RarityLevel.LEGENDARY: 0.1 / 100.0
}

RARITY_QUANTITY_RANGES = {
    RarityLevel.COMMON: (2, 5),
    RarityLevel.UNCOMMON: (2, 4),
    RarityLevel.RARE: (1, 3),
    RarityLevel.EPIC: (1, 2),
    RarityLevel.LEGENDARY: (1, 1)
}



#* === СВЯЗУЮЩИЕ ТАБЛИЦЫ ===
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



#* === МОДЕЛИ ===
class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True) # внутренний id
    telegram_id = Column(BigInteger, unique=True, index=True) # id пользователя в телеграме
    name = Column(String)
    compact_style = Column(Boolean, server_default="False")
    show_hints = Column(Boolean, server_default="True")

    owned = relationship("Settlement", back_populates="owner")
    memberships = relationship("Settler", back_populates="user")

class Settlement(Base):
    __tablename__ = "settlements"

    id = Column(BigInteger, primary_key=True, index=True)
    chat_id = Column(BigInteger, unique=True, index=True)
    name = Column(String)
    owner_id = Column(BigInteger, ForeignKey("users.id"))
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    last_name_change = Column(DateTime, server_default=text("to_timestamp(0)"), nullable=False)

    owner = relationship("User", back_populates="owned")
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
    last_profession_change = Column(DateTime, server_default=text("to_timestamp(0)"), nullable=False)

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
    from_resource = Column(String, nullable=True, default=None)
    for_resource = Column(String, nullable=True, default=None)
    rarity = Column(SAEnum(RarityLevel), default=RarityLevel.COMMON, nullable=False)
    received = Column(Integer, server_default="0")
    spent = Column(Integer, server_default="0")

class Profession(Base):
    __tablename__ = "professions"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, unique=True)
    emoji = Column(String, nullable=True)
    description = Column(String, nullable=True)
    crafts = Column(String, nullable=True, default=None)
    collects = Column(String, nullable=True, default=None)
    required_level = Column(Integer)



#* === РАБОТЫ ===

@dataclass
class Work:
    id: str
    name: str
    emoji: str
    profession_id: Optional[int] = None
    requirements: Dict[str, Any] = field(default_factory=dict)  # {"🎋": 3, "level": 2}
    steps: List[Step] = field(default_factory=list) # [Hitting(...), Timer(...)]
    rewards: Dict[str, Any] = field(default_factory=dict)  # {"resource": "🌾", "quantity": lambda: random.randint(2, 5)}
    texts: Dict[str, str | Callable] = field(default_factory=dict)  # {"step_0_status": "Работай!", "complete": "Работа выполнена!"}
    answer_texts: Dict[str, Any] = field(default_factory=dict) # {"hit": "Попадение!", "miss": "Промах!"}
    cooldown_on_fail: bool = True 
    _workflow: Optional[Workflow] = None

    def build(self) -> Workflow:
        if self._workflow:
            copied_workflow = self._workflow.copy()
            copied_workflow.reset()
            if hasattr(copied_workflow, '_workflow_status_func'):
                copied_workflow.get_status_text = lambda: copied_workflow._workflow_status_func(copied_workflow)
            return copied_workflow
        steps = [copy.deepcopy(step) for step in self.steps]

        workflow = Workflow(
            steps=steps,
            name=f"{self.emoji} {self.name}",
        ).build_with_context(self.id)

        for i, step in enumerate(steps):
            step_key = f"step_{i}_status"
            if step_key in self.texts:
                status_value = self.texts[step_key]
                
                if callable(status_value):
                    step._status_text_func = status_value
                    def make_status_text_func(step_obj):
                        def get_status_text():
                            try:
                                return step_obj._status_text_func(step_obj)
                            except TypeError:
                                try:
                                    return step_obj._status_text_func()
                                except Exception:
                                    return str(step_obj._status_text_func)
                        return get_status_text
                    step.get_status_text = make_status_text_func(step)
                else:
                    def make_status_text_func_str(text_val):
                        def get_status_text():
                            return str(text_val)
                        return get_status_text
                    step.get_status_text = make_status_text_func_str(status_value)

        def workflow_status(workflow_self):
            if workflow_self.completed:
                complete_val = self.texts.get("complete", f"{self.emoji} {self.name} завершена!")
                if callable(complete_val):
                    try:
                        return complete_val()
                    except TypeError:
                        try:
                            return complete_val(workflow_self)
                        except Exception:
                            return str(complete_val)
                return str(complete_val)

            current_idx = workflow_self.current_step
            current_step = workflow_self.get_current_step()
            
            val = self.texts.get(f"step_{current_idx}_status", None)
            if val is not None:
                if callable(val):
                    try:
                        return val(current_step)
                    except TypeError:
                        try:
                            return val()
                        except Exception:
                            return str(val)
                return str(val)
            
            if current_step and hasattr(current_step, 'get_status_text'):
                try:
                    result = current_step.get_status_text()
                    if result:
                        return result
                except Exception:
                    pass
            
            return "В процессе..."

        workflow._workflow_status_func = workflow_status
        workflow.get_status_text = lambda: workflow_status(workflow)

        self._workflow = workflow
        copied_workflow = workflow.copy()
        copied_workflow.reset()
        if hasattr(copied_workflow, '_workflow_status_func'):
            copied_workflow.get_status_text = lambda: copied_workflow._workflow_status_func(copied_workflow)
        return copied_workflow

    def get_answer_text(self, result: str, step_idx: int, workflow=None, step=None) -> Optional[str]:
        key_combo = f"step_{step_idx}_{result}"
        entry = None
        if key_combo in self.answer_texts:
            entry = self.answer_texts[key_combo]

        if entry is None:
            step_key = f"step_{step_idx}"
            step_entry = self.answer_texts.get(step_key)
            if isinstance(step_entry, dict):
                entry = step_entry.get(result)

        if entry is None:
            entry = self.answer_texts.get(result)

        if entry is None:
            return None

        if callable(entry):
            try:
                return str(entry())
            except TypeError:
                try:
                    return str(entry(workflow))
                except TypeError:
                    try:
                        return str(entry(step))
                    except Exception:
                        return str(entry)
            except Exception:
                return str(entry)

        return str(entry)


WORKS_REGISTRY: Dict[str, Work] = {}

def register_work(work: Work):
    WORKS_REGISTRY[work.id] = work
    return work


def catcher_milking() -> Work:
    # Шаг 1: Успокоение коровы (Harvesting)
    step1 = Harvesting(
        objects=["🐄", "💢", "💢", " "],
        rules={
            "forbidden": ["💢"],
            "click": {"🐄": " "},
            "win_check": lambda field: not any(cell == "🐄" for row in field for cell in row)
        },
        size=3,
        required_at_least_one="🐄"
    )

    # Шаг 2: Доение (Alternation)
    step2 = Alternation(target="💧", target_presses=10)

    return Work(
        id="catcher_milking",
        name="Доение коровы",
        emoji="🪣",
        profession_id=3,
        steps=[step1, step2],
        rewards={
            "🥛": None,
            "exp": None
        },
        texts={
            "step_0_status": lambda: "🪣 <b>Успокой корову:</b>\nПогладь 🐄",
            "step_1_status": lambda step: f"🐮 <b>Доение коровы:</b>\nЧередуй нажим на ручки: 💧💧\n<b>{getattr(step, 'current_presses', 0)}/{step.target_presses}</b>",
            "complete": "🥛 <b>Молоко собрано!</b>",
            "lose": "🐄 Куда же ты лезешь! Всё, теперь то она точно не успокоится!"
        },
        answer_texts={
            "step_0": {
                "continue": "✅ Тихо-тихо — поглаживай корову, она успокоится.",
                "win": "🐄 Корова полностью спокойна!"
            },
            "step_1": {
                "continue": lambda: f"✅ Хм... Какая там ручка дальше? {'Правая?' if random.choice([True, False]) else 'Левая?'}"
            },
            "lose": "🐄 Корова лягнула! Она ещё не скоро тебя к себе подпустит!",
            "win": "🥛 Ведро наполнено! Корове нужно время прежде чем ты сможешь подоить её ещё раз."
        }
    )
register_work(catcher_milking())

def catcher_fishing() -> Work:
    step1 = Catch(
        target="🐟",
        rounds=8
    )
    
    return Work(
        id="catcher_fishing",
        name="Рыбалка",
        emoji="🎣",
        profession_id=3,
        steps=[step1],
        rewards={
            "🐟": None,
            "exp": None
        },
        texts={
            "step_0_status": lambda step: f"🎣 <b>Лови рыбу — осталось {step.rounds - step.current_round + 1}/{step.rounds}</b>",
            "complete": "🐟 <b>Рыба поймана!</b>",
            "lose": "💀 <b>Рыба сорвалась!</b>"
        },
        answer_texts={
            "win": "🐟 Рыба поймана!",
            "lose": "💀 Рыба сорвалась!"
        }
    )
register_work(catcher_fishing())

def catcher_shearing() -> Work:
    # Шаг 1: Стрижка овцы (ProgressBar)
    step1 = ProgressBar(line_length=5, bar_length=15)
    return Work(
        id="catcher_shearing",
        name="Стрижка овцы",
        emoji="🐑",
        profession_id=3,
        steps=[step1],
        rewards={
            "☁️": None,
            "exp": None
            },
        texts={
            "step_0_status": lambda step: f"✂️ <b>Стриги овцу:</b>\Используй ножницы аккуратно!",
            "complete": "☁️ <b>Шерсть собрана!</b>",
            "lose": "💀 <b>Овца испугалась и убежала!</b>"
        },
        answer_texts={
            "continue": "✅ Овечка лысеет...",
            "win": "☁️ Шерсть собрана!",
            "lose": "💀 Овца испугалась и убежала!"
        }
    )
register_work(catcher_shearing())

def farmer_harvest_grain() -> Work:
    # Шаг 1: Сбор урожая (Harvesting)
    step1 = Harvesting(
        objects=["🌾", "🌱", "🥔", "🍄‍🟫", "🫐"],
        rules={
            "forbidden": ["🌱"],
            "click": {
                "🌾": " ",
                "🥔": " ",
                "🍄‍🟫": " ",
                "🫐": " "
            },
            "win_check": lambda field: not any(
                cell in ["🌾", "🥔", "🍄‍🟫", "🫐"] for row in field for cell in row
            )
        },
        size=4,
        required_at_least_one="🌾"
    )

    return Work(
        id="farmer_harvest_grain",
        name="Сбор урожая",
        emoji="🌾",
        profession_id=1,
        steps=[step1],
        rewards={
            "🌾": None,
            "🥔": None,
            "🍄‍🟫": None,
            "🫐": None,
            "exp": None
        },
        texts={
            "step_0_status": lambda: "🌾 <b>Собери урожай:</b>\nЖни только созревшие культуры!",
            "complete": "🌾 <b>Урожай собран!</b>",
            "lose": "🌱 <b>Ты срезал росток! Нужно быть внимательнее.</b>"
        },
        answer_texts={
            "continue": "✅ Отлично! Продолжай косить!",
            "lose": "🌱 Ты срезал росток! Нужно быть внимательнее.",
            "win": "🌾 Урожай собран! Теперь можно отдохнуть."
        }
    )
register_work(farmer_harvest_grain())

def healer_tea_brewing() -> Work:
    # Шаг 1: Измельчение коры (Hitting)
    step1 = Hitting(
        target="🎋",
        size=3,
        rounds=6
    )
    
    # Шаг 2: Заваривание (Timer)
    step2 = Timer(
        duration=40,
        button_text="💧 Налейте кипяток",
        button2_text="⌛️ Ожидайте..."
    )

    return Work(
        id="healer_tea_brewing",
        name="Приготовление отвара",
        emoji="🍵",
        profession_id=2,  # ID профессии "Травник"
        steps=[step1, step2],
        requirements={
            "🎋": 3
        },
        rewards={
            "🍵": 1,
            "exp": None
        },
        texts={
            "step_0_status": lambda step: f"🥣 <b>Измельчение коры</b> — осталось {step.rounds - step.current_round + 1}/{step.rounds}\nИзмельчи кору ступкой! 🎋",
            "step_1_status": lambda step: f"🍵 <b>Заваривание отвара...</b>\n Осталось <b>{step.get_remaining_time()}с</b>" if step.started and not step.completed else ("💧 Налей кипяток для заваривания" if not step.started else "🍵 Отвар готов!"),
            "complete": "🍵 <b>Отвар готов!</b>",
            "lose": "💀 Отвар испорчен!"
        },
        answer_texts={
            "step_0": {
                "continue": "🎋 Кора растоптана!",
                "lose": "💀 Кора испорчена!"
            },
            "step_1": {
                "continue": "🍵 Заваривание отвара...",
                "lose": "💀 Отвар испорчен!"
            },
            "win": "🍵 Отвар приготовлен!"
        },
        cooldown_on_fail=False
    )
register_work(healer_tea_brewing())

def healer_herb_gathering() -> Work:
    # Шаг 1: Сбор трав (Harvesting)
    step1 = Harvesting(
        objects=["🌿", "🌵", "🎋", "🪴"],
        rules={
            "forbidden": ["🌵"],
            "click": {
                "🌿": " ",
                "🎋": " ",
                "🪴": " "
            },
            "win_check": lambda field: not any(
                cell in ["🌿", "🎋", "🪴"] for row in field for cell in row
            )
        },
        size=4,
        required_at_least_one="🌿"
    )

    return Work(
        id="healer_herb_gathering",
        name="Сбор трав",
        emoji="🪴",
        profession_id=2,
        steps=[step1],
        rewards={
            "🎋": None,
            "🪴": None,
            "exp": None
        },
        texts={
            "step_0_status": lambda: "🪴 <b>Соберите травы:</b>\nСобирайте только полезные растения!",
            "complete": "🪴 <b>Травы собраны!</b>",
            "lose": "🌵 <b>Ты сорвал колючее, бесполезное растение! Все руки в иголках!</b>"
        },
        answer_texts={
            "continue": "✅ Отлично! Продолжайте сбор!",
            "lose": "🌵 Ты сорвал колючее растение! Все руки в иголках!",
            "win": "🪴 Травы собраны! Теперь можно приготовить отвар."
        }
    )
register_work(healer_herb_gathering())
