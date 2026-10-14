from __future__ import annotations

from app import core, models


def test_effective_bonuses_add_multipliers_from_all_sources():
    settler_bonuses = core.BonusSet()
    settler_bonuses.add_bonus({
        "global_quantity_multiplier": 0.5,
        "category_quantity_multiplier": {"Еда": 0.5},
        "resource_quantity_multiplier": {"🌾": 0.5},
    })
    settlement_bonuses = core.BonusSet()
    settlement_bonuses.add_bonus({
        "category_quantity_multiplier": {"Еда": 0.5},
        "resource_quantity_multiplier": {"🌾": 0.5},
    })

    effective = core._get_effective_bonuses(models.LootItem(emoji="🌾"), settler_bonuses, settlement_bonuses)

    assert effective.global_qty_mult == 0.5
    assert effective.category_qty_mult == {"Еда": 1.0}
    assert effective.resource_qty_mult == {"🌾": 1.0}


def test_effective_bonuses_respect_source_flags():
    settler_bonuses = core.BonusSet()
    settler_bonuses.add_bonus({"global_quantity_modifier": 2})
    settlement_bonuses = core.BonusSet()
    settlement_bonuses.add_bonus({"global_quantity_modifier": 3})
    item = models.LootItem(emoji="🌾", affected_by_settlement_bonuses=False)

    effective = core._get_effective_bonuses(item, settler_bonuses, settlement_bonuses)

    assert effective.global_qty_mod == 2
