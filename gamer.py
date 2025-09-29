from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder
import asyncio
import random
import copy



class Harvesting:
    #* Harvesting - шаг со сбором
    def __init__(self, objects, rules, size=5, 
                 status_text_func=None, lose_text="❌ Проигрыш!", 
                 win_text="🏆 Победа!", continue_text="✅ Продолжайте!"):
        self.size = size
        self.objects = objects
        self.rules = rules
        self.status_text_func = status_text_func
        self.lose_text = lose_text
        self.win_text = win_text
        self.continue_text = continue_text
        self.game_over = False
        self.won = False
        self._reset_field()

    def _reset_field(self):
        self.field = [[random.choice(self.objects) for _ in range(self.size)] for _ in range(self.size)]
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
                    callback_data=f"harvest:{i}:{j}"
                ))
            kb.row(*row, width=self.size)
        return kb.as_markup()

    def click(self, i, j):
        if self.game_over:
            return "game_over"
            
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
    
    def get_status_text(self):
        if self.status_text_func:
            return self.status_text_func(self)
    
    def copy(self):
        return Harvesting(
            objects=copy.deepcopy(self.objects),
            rules=copy.deepcopy(self.rules),
            size=self.size,
            status_text_func=self.status_text_func,
            lose_text=self.lose_text,
            win_text=self.win_text,
            continue_text=self.continue_text
        )

class Hitting:
    #* Hitting - шаг с целью
    def __init__(self, target="🐰", empty="🕳️", size=3, rounds=5, 
                 status_text_func=None, hit_text="🎯 Попадание!", 
                 miss_text="💥 Промах!", win_text="🏆 Победа!"):
        self.size = size
        self.target = target
        self.empty = empty
        self.rounds = rounds
        self.current_round = 1
        self.score = 0
        self.target_position = None
        self.field = [empty] * size
        self.game_over = False
        self.won = False
        self.status_text_func = status_text_func
        self.hit_text = hit_text
        self.miss_text = miss_text
        self.win_text = win_text
        self._place_target()
    
    def _place_target(self):
        # Избегаем размещения цели в той же позиции, если размер поля больше 1
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
                callback_data=f"hit:{i}"
            ))
        kb.adjust(self.size)
        return kb.as_markup()
    
    def click(self, position):
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
                return "hit"
        else:
            self.game_over = True
            self.won = False
            return "miss"
    
    def get_status_text(self):
        if self.status_text_func:
            return self.status_text_func(self)
    
    def copy(self):
        return Hitting(
            target=self.target,
            empty=self.empty,
            size=self.size,
            rounds=self.rounds,
            status_text_func=self.status_text_func,
            hit_text=self.hit_text,
            miss_text=self.miss_text,
            win_text=self.win_text
        )

class TimerStep:
    #* TimerStep - шаг с таймером
    def __init__(self, button_text="⏰ Начать", button2_text="⏳ Ожидание...", duration=30, 
                 status_text_func=None, start_text="⏰ Начато!", 
                 complete_text="✅ Завершено!"):
        self.button_text = button_text
        self.button2_text = button2_text
        self.duration = duration
        self.status_text_func = status_text_func
        self.start_text = start_text
        self.complete_text = complete_text
        self.started = False
        self.completed = False
        self.start_time = None
    
    def render_keyboard(self):
        kb = InlineKeyboardBuilder()
        if not self.started:
            kb.add(types.InlineKeyboardButton(
                text=self.button_text,
                callback_data="timer:start"
            ))
        elif self.started and not self.completed:
            kb.add(types.InlineKeyboardButton(
                text=self.button2_text,
                callback_data="timer:wait"
            ))
        return kb.as_markup()
    
    def click(self, action):
        if action == "start" and not self.started:
            self.started = True
            self.start_time = asyncio.get_running_loop().time()
            return "started"
        elif action == "wait":
            if self.started and not self.completed:
                current_time = asyncio.get_running_loop().time()
                if current_time - self.start_time >= self.duration:
                    self.completed = True
                    return "completed"
                else:
                    return "waiting"
        return "invalid"
    
    def get_status_text(self):
        if self.status_text_func:
            return self.status_text_func(self)
        return "Таймер не настроен"
    
    def get_remaining_time(self):
        if self.started and not self.completed:
            current_time = asyncio.get_running_loop().time()
            remaining = self.duration - (current_time - self.start_time)
            return max(0, int(remaining))
        return 0
    
    def copy(self):
        return TimerStep(
            button_text=self.button_text,
            button2_text=self.button2_text,
            duration=self.duration,
            status_text_func=self.status_text_func,
            start_text=self.start_text,
            complete_text=self.complete_text
        )

class Catch :
    #* Catch - шаг с целью попадания в 1 движущуюся цель
    def __init__(self, target="🎯", empty=" ", size=5,
                 rounds=3, status_text_func=None, hit_text="🎯 Попадание!",
                 miss_text="💥 Промах!", win_text="🏆 Победа!"):
        self.size = size
        self.target = target
        self.empty = empty
        self.rounds = rounds
        self.current_round = 1
        self.score = 0
        self.status_text_func = status_text_func
        self.hit_text = hit_text
        self.miss_text = miss_text
        self.win_text = win_text
        self.game_over = False
        self.won = False
        self.target_position = None
        self.field = [empty] * (size * size)
        self._place_target()

    def _place_target(self):
        self.target_position = random.randint(0, self.size * self.size - 1)
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
                    callback_data=f"hit:{idx}"
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
                return "hit"
        else:
            self.game_over = True
            self.won = False
            return "miss"

    def get_status_text(self):
        if self.status_text_func:
            return self.status_text_func(self)

    def copy(self):
        return Catch(
            target=self.target,
            empty=self.empty,
            size=self.size,
            rounds=self.rounds,
            status_text_func=self.status_text_func,
            hit_text=self.hit_text,
            miss_text=self.miss_text,
            win_text=self.win_text
        )

class Milking:
    #* Milking - шаг с для поочередного нажатия на 2 кнопки
    def __init__(self, target_presses=10, 
                 status_text_func=None, lose_text="🐮 Корова вас лягнула!", 
                 win_text="🪣 Ведро наполнено молоком!", continue_text="💧 Продолжайте доить..."):
        self.target_presses = target_presses
        self.status_text_func = status_text_func
        self.lose_text = lose_text
        self.win_text = win_text
        self.continue_text = continue_text
        self.game_over = False
        self.won = False
        self._reset()

    def _reset(self):
        self.current_presses = 0
        self.last_pressed_side = -1  # -1 - не определено, 0 - лево, 1 - право
        self.game_over = False
        self.won = False

    def render_keyboard(self):
        kb = InlineKeyboardBuilder()
        kb.row(
            types.InlineKeyboardButton(text="💧", callback_data="milking:0"),
            types.InlineKeyboardButton(text="💧", callback_data="milking:1"),
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
    
    def get_status_text(self):
        if self.status_text_func:
            return self.status_text_func(self)
        
        progress = int((self.current_presses / self.target_presses) * 10)
        progress_bar = f"[{'█' * progress}{'_' * (10 - progress)}]"
        return f"🐮 Дойка коровы...\nНаполнено: {self.current_presses}/{self.target_presses}\n{progress_bar}"

    def copy(self):
        return Milking(
            target_presses=self.target_presses,
            status_text_func=self.status_text_func,
            lose_text=self.lose_text,
            win_text=self.win_text,
            continue_text=self.continue_text
        )


class Workflow:
    #* Workflow - система многошаговых работ
    def __init__(self, steps, name="Работа", 
                 status_text_func=None, complete_text="🏆 Работа завершена!"):
        self.steps = steps  # Список шагов
        self.name = name
        self.status_text_func = status_text_func
        self.complete_text = complete_text
        self.current_step = 0
        self.completed = False
        self.failed = False
    
    def get_current_step(self):
        if self.current_step < len(self.steps):
            return self.steps[self.current_step]
        return None
    
    def next_step(self):
        self.current_step += 1
        if self.current_step >= len(self.steps):
            self.completed = True
            return True
        return False
    
    def fail_workflow(self):
        self.failed = True
    
    def reset_workflow(self):
        self.current_step = 0
        self.completed = False
        self.failed = False
        for step in self.steps:
            if hasattr(step, 'started'):
                step.started = False
            if hasattr(step, 'completed'):
                step.completed = False
            if hasattr(step, 'game_over'):
                step.game_over = False
            if hasattr(step, 'won'):
                step.won = False
    
    def render_keyboard(self):
        current_step = self.get_current_step()
        if current_step:
            return current_step.render_keyboard()
        return None
    
    def get_status_text(self):
        if self.status_text_func:
            return self.status_text_func(self)
        current_step = self.get_current_step()
        if current_step and hasattr(current_step, 'get_status_text'):
            return current_step.get_status_text()
        return f"{self.name} - Шаг {self.current_step + 1}/{len(self.steps)}"
    
    def copy(self):
        copied_steps = []
        for step in self.steps:
            if hasattr(step, 'copy'):
                copied_steps.append(step.copy())
            else:
                copied_steps.append(copy.deepcopy(step))
        
        return Workflow(
            steps=copied_steps,
            name=self.name,
            status_text_func=self.status_text_func,
            complete_text=self.complete_text
        )
