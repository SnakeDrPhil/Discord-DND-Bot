"""Item generation engine: procedural weapons, armor, stat affixes, loot."""

import json
import random
from typing import Optional

from src.game.constants import (
    ALL_STATS,
    ARMOR_RARITY_MULTIPLIERS,
    BOSS_LOOT_RULES,
    EQUIPMENT_SELL_VALUES,
    LOOT_DROP_CHANCE,
    MAX_AR_BY_SLOT,
    RARITY_TIERS,
    STAT_AFFIX_RULES,
    WEAPON_DAMAGE_RANGES,
    WEAPON_DROP_CHANCES,
)
from src.utils.data_loader import get_armor, get_loot_table, get_weapons


# ── Rarity Rolling ─────────────────────────────────────────────────

def roll_rarity() -> str:
    """Roll a rarity tier using weighted distribution."""
    roll = random.uniform(0, 100)
    cumulative = 0.0
    for rarity, chance in WEAPON_DROP_CHANCES.items():
        cumulative += chance
        if roll <= cumulative:
            return rarity
    return "poor"


# ── Stat Affixes ───────────────────────────────────────────────────

def get_affix_base(floor: int) -> int:
    """Base affix value increases by 1 every 5 floors."""
    return 1 + (floor - 1) // 5


def generate_stat_affixes(rarity: str, floor: int) -> list:
    """Generate random stat affixes for an item."""
    rules = STAT_AFFIX_RULES.get(rarity)
    if not rules or rules["count"] == 0:
        return []
    base = get_affix_base(floor)
    stats = random.sample(ALL_STATS, rules["count"])
    affixes = []
    for i, stat in enumerate(stats):
        value = base * rules["multipliers"][i]
        affixes.append({"stat": stat, "value": value})
    return affixes


# ── Sell Values ────────────────────────────────────────────────────

def calculate_sell_value(item_type: str, rarity: str) -> int:
    """Calculate sell price for a generated item."""
    base = EQUIPMENT_SELL_VALUES.get(rarity, 1)
    if item_type == "weapon":
        return base * 2
    return base


def get_sell_price(item_data: dict) -> int:
    """Get sell price for any item_data dict."""
    if item_data.get("type") in ("weapon", "armor"):
        return item_data.get("sell_value", 1)
    if item_data.get("type") == "valuable":
        return random.randint(
            item_data.get("gold_min", 1),
            item_data.get("gold_max", 1))
    return 1


# ── Weapon Generation ─────────────────────────────────────────────

def generate_weapon(base_weapon: dict, rarity: str, floor: int) -> dict:
    """Generate a complete weapon item with rarity damage and affixes."""
    dmg_min, dmg_max = WEAPON_DAMAGE_RANGES[rarity]
    affixes = generate_stat_affixes(rarity, floor)
    sell = calculate_sell_value("weapon", rarity)
    if rarity in ("poor", "common"):
        name = base_weapon["name"]
    else:
        name = f"{rarity.capitalize()} {base_weapon['name']}"
    return {
        "type": "weapon",
        "base_id": base_weapon["id"],
        "name": name,
        "class_theme": base_weapon["class_theme"],
        "hand_type": base_weapon["hand_type"],
        "casting": base_weapon.get("casting", False),
        "damage_type": base_weapon.get("damage_type", "slash"),
        "rarity": rarity,
        "damage_min": dmg_min,
        "damage_max": dmg_max,
        "stat_affixes": affixes,
        "floor_found": floor,
        "sell_value": sell,
    }


# ── Armor Generation ──────────────────────────────────────────────

def generate_armor(base_armor: dict, rarity: str, floor: int) -> dict:
    """Generate a complete armor item with rarity AR and affixes."""
    base_ar = random.randint(base_armor["ar_min"], base_armor["ar_max"])
    if rarity in ARMOR_RARITY_MULTIPLIERS:
        mult_min, mult_max = ARMOR_RARITY_MULTIPLIERS[rarity]
        mult = random.uniform(mult_min, mult_max)
        ar = int(base_ar * mult)
    else:
        ar = base_ar
    max_ar = MAX_AR_BY_SLOT.get(base_armor["slot"], 100)
    ar = min(ar, max_ar)

    affixes = generate_stat_affixes(rarity, floor)
    sell = calculate_sell_value("armor", rarity)
    if rarity in ("poor", "common"):
        name = base_armor["name"]
    else:
        name = f"{rarity.capitalize()} {base_armor['name']}"
    return {
        "type": "armor",
        "base_id": base_armor["id"],
        "name": name,
        "armor_type": base_armor["armor_type"],
        "slot": base_armor["slot"],
        "allowed_classes": base_armor["allowed_classes"],
        "rarity": rarity,
        "armor_rating": ar,
        "stat_affixes": affixes,
        "floor_found": floor,
        "sell_value": sell,
    }


# ── Equipment Stat Helpers ─────────────────────────────────────────

def calc_equipment_stat_bonuses(equipped_items: list) -> dict:
    """Sum all stat affixes from equipped items. Items are DB rows."""
    bonuses = {}
    for item in equipped_items:
        idata = json.loads(item["item_data"]) if isinstance(item["item_data"], str) else item["item_data"]
        for affix in idata.get("stat_affixes", []):
            stat = affix["stat"]
            bonuses[stat] = bonuses.get(stat, 0) + affix["value"]
    return bonuses


def get_total_armor_rating(equipped_items: list) -> int:
    """Sum AR from all equipped armor pieces. Items are DB rows."""
    total = 0
    for item in equipped_items:
        idata = json.loads(item["item_data"]) if isinstance(item["item_data"], str) else item["item_data"]
        if idata.get("type") == "armor":
            total += idata.get("armor_rating", 0)
    return total


def get_equipped_weapon_data(equipped_items: list) -> Optional[dict]:
    """Extract main_hand weapon data from equipped items list."""
    for item in equipped_items:
        if item.get("slot") == "main_hand":
            idata = json.loads(item["item_data"]) if isinstance(item["item_data"], str) else item["item_data"]
            if idata.get("type") == "weapon":
                return idata
    return None


# ── Loot Generation ────────────────────────────────────────────────

def generate_loot(enemies: list, floor: int, player_class: str) -> tuple:
    """
    Generate loot from killed enemies.
    Returns (gold, loot_items) where loot_items is a list of item dicts.
    """
    gold = 0
    loot = []

    for e in enemies:
        if not e.get("type"):
            continue

        # Enemy-specific drops (50% chance per enemy)
        if random.random() < LOOT_DROP_CHANCE:
            table = get_loot_table(e["type"])
            if table:
                drop = dict(random.choice(table))
                if "gold_min" in drop and "gold_max" in drop:
                    gv = random.randint(drop["gold_min"], drop["gold_max"])
                    drop["gold_value"] = gv
                    gold += gv
                loot.append(drop)

        # Equipment drop (50% chance per enemy)
        if random.random() < LOOT_DROP_CHANCE:
            rarity = roll_rarity()
            if random.random() < 0.5:
                weapons = get_weapons()
                base = random.choice(weapons)
                item = generate_weapon(base, rarity, floor)
            else:
                armor_list = get_armor(class_name=player_class)
                if not armor_list:
                    armor_list = get_armor()
                base = random.choice(armor_list)
                item = generate_armor(base, rarity, floor)
            loot.append(item)

    return gold, loot


def _roll_rarity_with_minimum(min_rarity: str) -> str:
    """Roll rarity but guarantee at least the minimum tier."""
    min_idx = RARITY_TIERS.index(min_rarity) if min_rarity in RARITY_TIERS else 0
    for _ in range(100):
        rarity = roll_rarity()
        if RARITY_TIERS.index(rarity) >= min_idx:
            return rarity
    return min_rarity


def generate_boss_loot(enemies: list, floor: int, player_class: str,
                       boss_type: str) -> tuple:
    """Generate loot from a boss kill. Guaranteed drops with higher rarity."""
    gold = 0
    loot = []
    rules = BOSS_LOOT_RULES.get(boss_type, {})
    min_rarity = rules.get("guaranteed_rarity_min", "rare")
    drop_count = rules.get("drop_count", 2)
    bonus_gold_range = rules.get("bonus_gold", (100, 250))

    # Boss-specific loot table drops (100% chance, not 50%)
    for e in enemies:
        if not e.get("type"):
            continue
        table = get_loot_table(e["type"])
        if table:
            drop = dict(random.choice(table))
            if "gold_min" in drop and "gold_max" in drop:
                gv = random.randint(drop["gold_min"], drop["gold_max"])
                drop["gold_value"] = gv
                gold += gv
            loot.append(drop)

    # Guaranteed equipment drops at minimum rarity
    for _ in range(drop_count):
        rarity = _roll_rarity_with_minimum(min_rarity)
        if random.random() < 0.5:
            weapons = get_weapons()
            base = random.choice(weapons)
            item = generate_weapon(base, rarity, floor)
        else:
            armor_list = get_armor(class_name=player_class)
            if not armor_list:
                armor_list = get_armor()
            base = random.choice(armor_list)
            item = generate_armor(base, rarity, floor)
        loot.append(item)

    # Bonus gold
    gold += random.randint(*bonus_gold_range)

    return gold, loot
