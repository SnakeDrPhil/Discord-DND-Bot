"""Level-up engine: XP processing, resource calculation, skill/talent slots."""

import json
from typing import Optional, Tuple

from src.db.models import get_player, update_player
from src.game.constants import (
    ENDURANCE_HP_PER_POINT,
    ENDURANCE_MANA_PER_POINT,
    ENDURANCE_SP_PER_POINT,
    SKILL_UNLOCK_INTERVAL,
    STAT_POINTS_PER_LEVEL,
    TALENT_UNLOCK_INTERVAL,
)
from src.utils.data_loader import get_xp_for_level


def calc_resource_maxes(class_data: dict, stats: dict) -> Tuple[int, int, int]:
    """Calculate max HP, Mana, SP respecting starting-stat exclusion rule.

    Only stat points allocated AFTER creation contribute to resource bonuses.
    Returns (max_hp, max_mana, max_sp).
    """
    starting = class_data["starting_stats"]
    base_hp = class_data["base_hp"]
    base_mana = class_data["base_mana"]
    base_sp = class_data["base_sp"]

    bonus_end = max(0, stats["endurance"] - starting["endurance"])
    bonus_int = max(0, stats["intelligence"] - starting["intelligence"])
    bonus_agi = max(0, stats["agility"] - starting["agility"])

    max_hp = base_hp + (bonus_end * ENDURANCE_HP_PER_POINT)
    max_mana = base_mana + (bonus_end * ENDURANCE_MANA_PER_POINT) + (bonus_int * 5)
    max_sp = base_sp + (bonus_end * ENDURANCE_SP_PER_POINT) + (bonus_agi * 1)

    return max_hp, max_mana, max_sp


def check_level_up(player: dict) -> list:
    """Check if a player has enough XP to level up.

    Returns a list of level-up events. Each event:
    {"new_level", "stat_points_awarded", "skill_unlocked", "talent_unlocked"}

    Does NOT modify the player dict or DB.
    """
    events = []
    current_level = player["level"]
    current_xp = player["xp"]

    while current_level < 20:
        xp_needed = get_xp_for_level(current_level + 1)
        if xp_needed is None or current_xp < xp_needed:
            break

        current_level += 1
        events.append({
            "new_level": current_level,
            "stat_points_awarded": STAT_POINTS_PER_LEVEL,
            "skill_unlocked": (current_level % SKILL_UNLOCK_INTERVAL == 0),
            "talent_unlocked": (current_level % TALENT_UNLOCK_INTERVAL == 0),
        })

    return events


def apply_level_ups(player: dict, events: list) -> dict:
    """Compute the DB update fields from level-up events.

    Returns a dict of fields to pass to update_player().
    """
    if not events:
        return {}

    final_level = events[-1]["new_level"]
    total_stat_points = sum(e["stat_points_awarded"] for e in events)

    return {
        "level": final_level,
        "unspent_stat_points": player["unspent_stat_points"] + total_stat_points,
    }


def get_skill_slots(level: int) -> int:
    """Number of skill choices a player should have at this level."""
    return level // SKILL_UNLOCK_INTERVAL


def get_talent_slots(level: int) -> int:
    """Number of talent choices a player should have at this level."""
    return level // TALENT_UNLOCK_INTERVAL


def get_pending_skill_slots(level: int, learned_count: int) -> int:
    """Number of skill choices the player hasn't made yet."""
    return max(0, get_skill_slots(level) - learned_count)


def get_pending_talent_slots(level: int, selected_count: int) -> int:
    """Number of talent choices the player hasn't made yet."""
    return max(0, get_talent_slots(level) - selected_count)


async def grant_xp(discord_id: str, amount: int) -> Tuple[dict, list]:
    """Grant XP to a player, process any level-ups, and persist.

    Returns (updated_player, level_up_events).
    """
    player = await get_player(discord_id)
    new_xp = player["xp"] + amount

    # Build a temporary dict for level check
    temp = dict(player)
    temp["xp"] = new_xp
    events = check_level_up(temp)
    updates = apply_level_ups(player, events)
    updates["xp"] = new_xp

    await update_player(discord_id, **updates)

    updated_player = await get_player(discord_id)
    return updated_player, events
