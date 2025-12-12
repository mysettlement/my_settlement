import logging
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import Any, Callable, Optional, List, Dict
from abc import ABC, abstractmethod
import asyncio
import random
import copy

from app.config import setup_logging


logger = logging.getLogger(__name__)
log = setup_logging(logger)



class Step(ABC):
    def __init__(self):
        self.game_over = False
        self.won = False
        self.on_complete: Optional[Callable[[], None]] = None
        self.work_id: Optional[str] = None
        self.step_idx: Optional[int] = None
    
    def set_context(self, work_id: str, step_idx: int):
        self.work_id = work_id
        self.step_idx = step_idx

    def _make_callback_data(self, *parts: str) -> str:
        if self.work_id is None or self.step_idx is None:
            raise ValueError("Установите контекст работы и шага перед созданием callback data.\nset_context(work_id, step_idx)")
        return f"work:{self.work_id}:{self.step_idx}:" + ":".join(parts)

    def get_status_text(self) -> str:
        """Возвращает текст статуса шага. По умолчанию пустой — переопределяется в Work.build()"""
        return ""

    def reset(self):
        self.game_over = False
        self.won = False
        
    @abstractmethod
    def click(self, action: Any) -> str:
        pass

    @abstractmethod
    def copy(self) -> 'Step':
        pass
    

class Harvesting(Step):
    def __init__(self, objects, rules, size=5, required_at_least_one=None):
        super().__init__()
        self.size = size
        self.objects = objects
        self.rules = rules
        self.required_at_least_one = required_at_least_one
        self._reset_field()
    
    def _reset_field(self):
        self.field = [[random.choice(self.objects) for _ in range(self.size)] for _ in range(self.size)]
        if self.required_at_least_one:
            required = self.required_at_least_one
            if isinstance(required, str):
                required = [required]
            has_required = any(cell in required for row in self.field for cell in row)
            if not has_required:
                i = random.randint(0, self.size - 1)
                j = random.randint(0, self.size - 1)
                self.field[i][j] = random.choice(required)
        self.game_over = False
        self.won = False
    
    def render_keyboard(self):
        kb = InlineKeyboardBuilder()
        for i in range(self.size):
            row = []
            for j in range(self.size):
                cell = self.field[i][j]
                row.append(types.InlineKeyboardButton(
                    text=cell,
                    callback_data=self._make_callback_data(str(i), str(j))
                ))
            kb.row(*row, width=self.size)
        return kb.as_markup()
    
    def click(self, position: str):
        if self.game_over:
            return "game_over"
        
        i, j = map(int, position.split(":"))
        cell = self.field[i][j]
        
        if cell in self.rules.get("forbidden", []):
            self.game_over = True
            self.won = False
            return "lose"
        
        if cell in self.rules.get("click", {}):
            self.field[i][j] = self.rules["click"][cell]

        if self.rules["win_check"](self.field):
            self.game_over = True
            self.won = True
            return "win"

        return "continue"
    
    def copy(self):
        return copy.deepcopy(self)
    
    def reset(self):
        super().reset()
        self._reset_field()
    
class Hitting(Step):
    def __init__(self, target, empty=" ", size=3, rounds=8):
        super().__init__()
        self.target = target
        self.empty = empty
        self.size = size
        self.rounds = rounds
        self.current_round = 1
        self.score = 0
        self.target_position = None
        self.field = [empty] * size
        self._place_target()
    
    def _place_target(self):
        if self.size > 1:
            new_position = random.randint(0, self.size - 1)
            while new_position == self.target_position:
                new_position = random.randint(0, self.size - 1)
            self.target_position = new_position
        else:
            self.target_position = 0
        
        self.field = [self.empty] * self.size
        self.field[self.target_position] = self.target
    
    def render_keyboard(self):
        kb = InlineKeyboardBuilder()
        for i in range(self.size):
            kb.add(types.InlineKeyboardButton(
                text=self.field[i],
                callback_data=self._make_callback_data(str(i))
            ))
        kb.adjust(self.size)
        return kb.as_markup()
    
    def click(self, position: int):
        if self.game_over:
            return "game_over"
        
        if position == self.target_position:
            self.score += 1
            self.current_round += 1
            
            if self.current_round > self.rounds:
                self.game_over = True
                self.won = True
                return "win"
            else:
                self._place_target()
                return "continue"
        else:
            self.game_over = True
            self.won = False
            return "lose"
        
    def copy(self):
        return copy.deepcopy(self)
    
    def reset(self):
        super().reset()
        self.current_round = 1
        self.score = 0
        self.target_position = None
        self._place_target()

class Catch(Step):
    def __init__(self, target, empty=" ", size=5, rounds=8):
        super().__init__()
        self.target = target
        self.empty = empty
        self.size = size
        self.rounds = rounds
        self.current_round = 1
        self.score = 0
        self.target_position = None
        self._place_target()

    def _place_target(self):
        new_position = random.randint(0, self.size * self.size - 1)
        while new_position == self.target_position:
            new_position = random.randint(0, self.size * self.size - 1)
        self.target_position = new_position
        self.field = [self.empty] * (self.size * self.size)
        self.field[self.target_position] = self.target

    def render_keyboard(self):
        kb = InlineKeyboardBuilder()
        for i in range(self.size):
            row = []
            for j in range(self.size):
                idx = i * self.size + j
                row.append(types.InlineKeyboardButton(
                    text=self.field[idx],
                    callback_data=self._make_callback_data(str(idx))
                ))
            kb.row(*row, width=self.size)
        return kb.as_markup()

    def click(self, position: int):
        if self.game_over:
            return "game_over"
        if position == self.target_position:
            self.score += 1
            self.current_round += 1
            if self.current_round > self.rounds:
                self.game_over = True
                self.won = True
                return "win"
            else:
                self._place_target()
                return "continue"
        else:
            self.game_over = True
            self.won = False
            return "miss"
        
    def copy(self):
        return copy.deepcopy(self)

    def reset(self):
        super().reset()
        self.current_round = 1
        self.score = 0
        self.target_position = None
        self._place_target()

class Alternation(Step):
    def __init__(self, target="💧", target_presses=10):
        super().__init__()
        self.target = target
        self.target_presses = target_presses
        self.current_presses = 0
        self.last_pressed_side = -1  # -1 - не определено, 0 - лево, 1 - право
    
    def render_keyboard(self):
        kb = InlineKeyboardBuilder()
        kb.row(
            types.InlineKeyboardButton(text=self.target, callback_data=self._make_callback_data("0")),
            types.InlineKeyboardButton(text=self.target, callback_data=self._make_callback_data("1")),
            width=2
        )
        return kb.as_markup()
    
    def click(self, side: int):
        if self.game_over:
            return "game_over"

        if side == self.last_pressed_side:
            self.game_over = True
            self.won = False
            return "lose"

        self.last_pressed_side = side
        self.current_presses += 1

        if self.current_presses >= self.target_presses:
            self.game_over = True
            self.won = True
            return "win"

        return "continue"
        
    def copy(self):
        return copy.deepcopy(self)
    
    def reset(self):
        super().reset()
        self.current_presses = 0
        self.last_pressed_side = -1

class Timer(Step):
    def __init__(self, button_text, button2_text, duration=30):
        super().__init__()
        self.button_text = button_text
        self.button2_text = button2_text
        self.duration = duration
        self.started = False
        self.completed = False
        self.start_time = None

    def get_remaining_time(self) -> int:
        if not self.started:
            return self.duration
        elapsed = asyncio.get_running_loop().time() - self.start_time
        remaining = max(0, int(self.duration - elapsed))
        return remaining
    
    def render_keyboard(self):
        kb = InlineKeyboardBuilder()
        action = "start" if not self.started else "wait"
        kb.add(types.InlineKeyboardButton(
            text=self.button_text if not self.started else self.button2_text,
            callback_data=self._make_callback_data(action)
        ))
        return kb.as_markup()
    
    def click(self, action: str):
        if action == "start" and not self.started:
            self.started = True
            self.start_time = asyncio.get_running_loop().time()
            return "continue"
        elif action == "wait" and self.started and not self.completed:
            if asyncio.get_running_loop().time() - self.start_time >= self.duration:
                self.completed = True
                return "win"
        return "game_over"
        
    def copy(self):
        return copy.deepcopy(self)
    
    def reset(self):
        super().reset()
        self.started = False
        self.completed = False
        self.start_time = None

class ProgressBar(Step):
    def __init__(self, line_length=5, bar_length=10, target="✂️", empty=" ", line="☁️"):
        super().__init__()
        self.bar_length = bar_length
        self.target = target
        self.empty = empty
        self.line = line
        self.current = 0
        self.line_length = line_length

    def render_keyboard(self):
        kb = InlineKeyboardBuilder()
        for i in range(self.bar_length):
            if i == self.current:
                cell = self.target
            elif i < self.current:
                cell = self.empty
            else:
                cell = self.line
            kb.add(types.InlineKeyboardButton(text=cell, callback_data=self._make_callback_data(str(i))))
        kb.adjust(self.line_length)
        return kb.as_markup()

    def click(self, position: int):
        if self.game_over:
            return "game_over"

        if position == self.current:
            self.current += 1
            if self.current >= self.bar_length:
                self.game_over = True
                self.won = True
                return "win"
            return "continue"
        
        else:
            self.game_over = True
            self.won = False
            return "lose"
    
    def copy(self):
        return copy.deepcopy(self)
    
    def reset(self):
        super().reset()
        self.current = 0
        self.game_over = False
        self.won = False
        self.lose = False


class Workflow(Step):
    def __init__(self, steps, name="work"):
        super().__init__()
        self.steps = steps
        self.name = name
        self.current_step = 0
        self.completed = False
        self.failed = False

    def build_with_context(self, work_id: str):
        for idx, step in enumerate(self.steps):
            step.set_context(work_id, idx)
            if isinstance(step, Workflow):
                step.build_with_context(work_id)
        return self

    def get_current_step(self) -> Optional[Step]:
        return self.steps[self.current_step] if self.current_step < len(self.steps) else None

    def get_status_text(self) -> str:
        if self.completed:
            return ""

        current = self.get_current_step()
        return current.get_status_text() if current else ""

    def next_step(self) -> str:
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.completed = True
            self.won = True
            self.game_over = True
            return "win"
        return "continue"

    def get_keyboard(self):
        current = self.get_current_step()
        return current.render_keyboard() if current else None

    def click(self, action: Any) -> str:
        if self.game_over:
            return "game_over"

        current = self.get_current_step()
        if not current:
            return "game_over"

        result = current.click(action)

        if result == "win":
            return self.next_step()
        elif result == "lose":
            self.failed = True
            self.game_over = True
            self.won = False
            return "lose"

        return result  # continue

    def copy(self):
        return copy.deepcopy(self)
    
    def reset(self):
        super().reset()
        self.current_step = 0
        self.completed = False
        self.failed = False
        for step in self.steps:
            if hasattr(step, "reset"):
                step.reset()
