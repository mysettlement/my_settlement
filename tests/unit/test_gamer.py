from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.gamer import Alternation, Catch, Harvesting, Hitting, ProgressBar, Timer, Workflow


pytestmark = pytest.mark.unit


def test_harvesting_requires_context_before_keyboard_render():
    harvesting = Harvesting(
        objects=["🌾"],
        rules={"forbidden": [], "click": {"🌾": " "}, "win_check": lambda field: True},
        size=1,
    )

    with pytest.raises(ValueError):
        harvesting.render_keyboard()


def test_harvesting_click_wins_and_resets(monkeypatch):
    monkeypatch.setattr("app.gamer.random.choice", lambda values: values[0])
    monkeypatch.setattr("app.gamer.random.randint", lambda start, end: start)

    harvesting = Harvesting(
        objects=["🌾"],
        rules={
            "forbidden": [],
            "click": {"🌾": " "},
            "win_check": lambda field: field[0][0] == " ",
        },
        size=1,
        required_at_least_one="🌾",
    )
    harvesting.set_context("work", 0)

    assert harvesting.click("0:0") == "win"
    assert harvesting.game_over is True
    harvesting.reset()
    assert harvesting.game_over is False
    assert harvesting.field[0][0] == "🌾"


def test_hitting_flow_wins_then_game_over(monkeypatch):
    positions = iter([0, 1, 0])
    monkeypatch.setattr("app.gamer.random.randint", lambda start, end: next(positions))

    hitting = Hitting(target="🎯", size=2, rounds=2)
    hitting.set_context("work", 0)

    assert hitting.click(0) == "continue"
    assert hitting.click(1) == "win"
    assert hitting.click(1) == "game_over"


def test_catch_miss_marks_game_over(monkeypatch):
    monkeypatch.setattr("app.gamer.random.randint", lambda start, end: 3)

    catch = Catch(target="🐟", size=2, rounds=1)
    catch.set_context("work", 0)

    assert catch.click(0) == "miss"
    assert catch.game_over is True
    assert catch.won is False


def test_alternation_and_progress_bar_fail_on_wrong_action():
    alternation = Alternation(target_presses=2)
    alternation.set_context("work", 0)
    assert alternation.click(0) == "continue"
    assert alternation.click(0) == "lose"

    progress = ProgressBar(bar_length=3)
    progress.set_context("work", 1)
    assert progress.click(1) == "lose"
    progress.reset()
    assert progress.click(0) == "continue"


@pytest.mark.asyncio
async def test_timer_completes_with_fake_loop(monkeypatch):
    loop = SimpleNamespace(now=100.0)
    loop.time = lambda: loop.now
    monkeypatch.setattr(asyncio, "get_running_loop", lambda: loop)

    timer = Timer(button_text="Start", button2_text="Wait", duration=5)
    timer.set_context("work", 0)

    assert timer.click("start") == "continue"
    loop.now += 6
    assert timer.click("wait") == "win"
    assert timer.completed is True


def test_workflow_transitions_and_reset(monkeypatch):
    positions = iter([0, 1])
    monkeypatch.setattr("app.gamer.random.randint", lambda start, end: next(positions))

    workflow = Workflow(
        steps=[Hitting(target="🎯", size=2, rounds=1), Alternation(target_presses=1)],
        name="Test flow",
    ).build_with_context("test-work")

    assert workflow.click(0) == "continue"
    assert workflow.click(0) == "win"
    assert workflow.completed is True

    workflow.reset()
    assert workflow.completed is False
    assert workflow.current_step == 0
