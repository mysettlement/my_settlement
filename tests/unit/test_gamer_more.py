from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.gamer import Alternation, Catch, Harvesting, Hitting, ProgressBar, Timer, Workflow


pytestmark = pytest.mark.unit


def test_render_keyboard_and_copy_for_all_steps(monkeypatch):
    monkeypatch.setattr("app.gamer.random.choice", lambda values: values[0])
    monkeypatch.setattr("app.gamer.random.randint", lambda start, end: start)

    harvesting = Harvesting(
        objects=["🌾", "🌱"],
        rules={"forbidden": ["🌱"], "click": {"🌾": " "}, "win_check": lambda field: False},
        size=2,
        required_at_least_one="🌾",
    )
    harvesting.set_context("work", 0)
    assert harvesting.render_keyboard().inline_keyboard
    assert harvesting.copy().field == harvesting.field

    hitting = Hitting(target="🎯", size=3, rounds=2)
    hitting.set_context("work", 1)
    assert hitting.render_keyboard().inline_keyboard
    assert hitting.copy().target == "🎯"
    hitting.reset()
    assert hitting.current_round == 1

    catch = Catch(target="🐟", size=2, rounds=2)
    catch.set_context("work", 2)
    assert catch.render_keyboard().inline_keyboard
    catch.reset()
    assert catch.current_round == 1

    alternation = Alternation(target_presses=3)
    alternation.set_context("work", 3)
    assert alternation.render_keyboard().inline_keyboard
    alternation.click(0)
    alternation.reset()
    assert alternation.current_presses == 0

    progress = ProgressBar(bar_length=4)
    progress.set_context("work", 4)
    assert progress.render_keyboard().inline_keyboard
    progress.click(0)
    progress.reset()
    assert progress.current == 0


@pytest.mark.asyncio
async def test_timer_render_keyboard_and_early_wait(monkeypatch):
    loop = SimpleNamespace(now=10.0)
    loop.time = lambda: loop.now
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)

    timer = Timer(button_text="Start", button2_text="Wait", duration=30)
    timer.set_context("work", 0)

    assert timer.render_keyboard().inline_keyboard
    assert timer.click("start") == "continue"
    assert timer.click("wait") == "game_over"
    timer.reset()
    assert timer.started is False


def test_workflow_getters_and_lose_branch(monkeypatch):
    monkeypatch.setattr("app.gamer.random.randint", lambda start, end: start)

    step = Hitting(target="🎯", size=1, rounds=2)
    workflow = Workflow([step], name="One step").build_with_context("wf")

    assert workflow.get_current_step() is step
    assert workflow.get_keyboard() is not None
    assert workflow.get_status_text() == ""
    assert workflow.click(0) == "continue"
    assert workflow.click(1) == "lose"
    assert workflow.failed is True
    assert workflow.won is False


def test_harvesting_injects_required_symbol_and_game_over_short_circuits(monkeypatch):
    choices = iter(["🌱", "🌾"])
    monkeypatch.setattr("app.gamer.random.choice", lambda values: next(choices))
    monkeypatch.setattr("app.gamer.random.randint", lambda start, end: 0)

    harvesting = Harvesting(
        objects=["🌱"],
        rules={"forbidden": ["🌱"], "click": {}, "win_check": lambda field: False},
        size=1,
        required_at_least_one=["🌾"],
    )

    assert harvesting.field[0][0] == "🌾"

    harvesting.set_context("work", 0)
    harvesting.field[0][0] = "🌱"
    assert harvesting.click("0:0") == "lose"
    assert harvesting.click("0:0") == "game_over"


@pytest.mark.asyncio
async def test_timer_remaining_time_and_nested_workflow_branches(monkeypatch):
    loop = SimpleNamespace(now=50.0)
    loop.time = lambda: loop.now
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)

    timer = Timer(button_text="Start", button2_text="Wait", duration=10)
    timer.set_context("timer", 0)
    assert timer.get_remaining_time() == 10

    assert timer.click("start") == "continue"
    loop.now += 4.2
    assert timer.get_remaining_time() == 5

    nested = Workflow([Workflow([Alternation(target_presses=1)], name="inner")], name="outer").build_with_context("wf")
    assert nested.steps[0].steps[0].work_id == "wf"
    assert nested.click(0) == "win"
    assert nested.click(0) == "game_over"

    empty = Workflow([], name="empty").build_with_context("empty")
    assert empty.get_keyboard() is None
    assert empty.click("anything") == "game_over"
