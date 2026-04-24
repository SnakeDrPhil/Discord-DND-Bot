"""Dungeon engine: map loading, movement, scenarios, encounters, fog of war."""

import json
import random
from typing import Optional

from src.game.constants import (
    ALL_STATS,
    CURSE_DURATION,
    CURSE_STAT_PENALTY,
    ENCOUNTER_CHANCE_PER_TILE,
    MAX_CURSES,
    REGEN_HP_PER_TILE,
    REGEN_MANA_PER_TILE,
    REGEN_SP_PER_TILE,
    SCENARIO_NEGATIVE_CHANCE,
    SCENARIO_POSITIVE_CHANCE,
)
from src.utils.data_loader import get_floor, get_scenarios


# ── Direction helpers ──────────────────────────────────────────────

DIRECTION_DELTAS = {
    "north": (-1, 0),
    "south": (1, 0),
    "east": (0, 1),
    "west": (0, -1),
}


# ── Map helpers ────────────────────────────────────────────────────

def load_floor(floor_number: int) -> Optional[dict]:
    """Load floor data. Returns None if floor doesn't exist."""
    return get_floor(floor_number)


def get_tile(floor_data: dict, row: int, col: int) -> Optional[str]:
    """Get tile type at (row, col). Returns None if out of bounds."""
    if row < 0 or col < 0:
        return None
    try:
        return floor_data["tiles"][row][col]
    except IndexError:
        return None


def is_passable(tile_type: Optional[str]) -> bool:
    """Returns True if the tile can be walked on."""
    return tile_type is not None and tile_type != "wall"


def get_valid_moves(floor_data: dict, row: int, col: int) -> dict:
    """Return dict of valid directions -> (new_row, new_col)."""
    moves = {}
    for direction, (dr, dc) in DIRECTION_DELTAS.items():
        nr, nc = row + dr, col + dc
        tile = get_tile(floor_data, nr, nc)
        if is_passable(tile):
            moves[direction] = (nr, nc)
    return moves


# ── Resource regeneration ──────────────────────────────────────────

def apply_regen(player: dict) -> dict:
    """Calculate per-tile resource regen. Returns player field updates."""
    updates = {}
    new_hp = min(player["hp"] + REGEN_HP_PER_TILE, player["max_hp"])
    new_mana = min(player["mana"] + REGEN_MANA_PER_TILE, player["max_mana"])
    new_sp = min(player["sp"] + REGEN_SP_PER_TILE, player["max_sp"])
    if new_hp != player["hp"]:
        updates["hp"] = new_hp
    if new_mana != player["mana"]:
        updates["mana"] = new_mana
    if new_sp != player["sp"]:
        updates["sp"] = new_sp
    return updates


def regen_message(updates: dict) -> str:
    """Build a regen summary string."""
    parts = []
    if "hp" in updates:
        parts.append(f"+{REGEN_HP_PER_TILE} HP")
    if "mana" in updates:
        parts.append(f"+{REGEN_MANA_PER_TILE} Mana")
    if "sp" in updates:
        parts.append(f"+{REGEN_SP_PER_TILE} SP")
    return ", ".join(parts) if parts else "Resources full."


# ── Encounter chance ───────────────────────────────────────────────

def get_encounter_chance(player: dict) -> int:
    """Return effective encounter chance, accounting for talents."""
    base = ENCOUNTER_CHANCE_PER_TILE
    talents = json.loads(player.get("selected_talents", "[]"))
    if "rogue_silent_steps" in talents:
        base = int(base * 0.85)
    return base


def roll_path_encounter(player: dict) -> bool:
    """Roll for random encounter on a path tile. Returns True if combat."""
    chance = get_encounter_chance(player)
    return random.randint(1, 100) <= chance


def get_encounter_level(floor: int) -> int:
    """Enemy level based on floor number, capped at 20."""
    return min(floor, 20)


# ── Scenario resolution ───────────────────────────────────────────

def roll_scenario_type() -> str:
    """Roll for scenario category: negative, positive, or neutral."""
    roll = random.randint(1, 100)
    if roll <= SCENARIO_NEGATIVE_CHANCE:
        return "negative"
    elif roll <= SCENARIO_NEGATIVE_CHANCE + SCENARIO_POSITIVE_CHANCE:
        return "positive"
    return "neutral"


def pick_scenario(category: str) -> dict:
    """Pick a random scenario event from the given category."""
    events = get_scenarios(category)
    return random.choice(events)


def resolve_scenario(player: dict, active_effects: list) -> dict:
    """
    Roll and resolve a full scenario event. Returns result dict with all
    changes to apply.
    """
    category = roll_scenario_type()
    event = pick_scenario(category)
    return apply_scenario_effect(event, category, player, active_effects)


def apply_scenario_effect(event: dict, category: str, player: dict,
                          active_effects: list) -> dict:
    """Apply a scenario event's effect. Returns result dict."""
    effect = event["effect"]
    etype = effect["type"]
    result = {
        "category": category,
        "event": event,
        "player_updates": {},
        "effect_updates": None,
        "items_gained": [],
        "items_lost_count": 0,
        "death": False,
        "combat": False,
        "combat_hp_penalty": 0,
        "xp": 0,
        "gold_change": 0,
        "messages": [event["message"]],
    }

    if etype == "none":
        pass

    elif etype == "hp_loss":
        new_hp = max(0, player["hp"] - effect["value"])
        result["player_updates"]["hp"] = new_hp
        if new_hp <= 0:
            result["death"] = True
            result["messages"].append("The damage was fatal!")

    elif etype == "mana_loss":
        result["player_updates"]["mana"] = max(0, player["mana"] - effect["value"])

    elif etype == "sp_loss":
        result["player_updates"]["sp"] = max(0, player["sp"] - effect["value"])

    elif etype == "hp_gain":
        gain = int(player["max_hp"] * effect["percent"] / 100)
        result["player_updates"]["hp"] = min(player["hp"] + gain, player["max_hp"])
        result["messages"].append(f"+{gain} HP")

    elif etype == "mana_gain":
        gain = int(player["max_mana"] * effect["percent"] / 100)
        result["player_updates"]["mana"] = min(player["mana"] + gain, player["max_mana"])
        result["messages"].append(f"+{gain} Mana")

    elif etype == "sp_gain":
        gain = int(player["max_sp"] * effect["percent"] / 100)
        result["player_updates"]["sp"] = min(player["sp"] + gain, player["max_sp"])
        result["messages"].append(f"+{gain} SP")

    elif etype == "full_restore":
        result["player_updates"]["hp"] = player["max_hp"]
        result["player_updates"]["mana"] = player["max_mana"]
        result["player_updates"]["sp"] = player["max_sp"]

    elif etype == "gold_gain":
        amount = random.randint(effect["min"], effect["max"])
        result["gold_change"] = amount
        result["player_updates"]["gold"] = player["gold"] + amount
        result["messages"].append(f"+{amount} Gold")

    elif etype == "gold_loss":
        lost = max(1, int(player["gold"] * effect["percent"] / 100))
        result["gold_change"] = -lost
        result["player_updates"]["gold"] = max(0, player["gold"] - lost)
        result["messages"].append(f"-{lost} Gold")

    elif etype == "xp_gain":
        amount = random.randint(effect["min"], effect["max"])
        result["xp"] = amount
        result["messages"].append(f"+{amount} XP")

    elif etype == "item_gain":
        item_id = random.choice(effect["item_pool"])
        result["items_gained"].append(item_id)

    elif etype == "item_loss":
        result["items_lost_count"] = 1

    elif etype == "curse":
        curse_count = sum(1 for e in active_effects if e.get("type") == "curse")
        if curse_count >= MAX_CURSES:
            result["messages"].append("But you already bear the maximum number of curses!")
        else:
            stat = random.choice(ALL_STATS)
            new_effect = {
                "type": "curse",
                "stat": stat,
                "value": CURSE_STAT_PENALTY,
                "combats_remaining": CURSE_DURATION,
            }
            updated = list(active_effects) + [new_effect]
            result["effect_updates"] = updated
            result["messages"].append(
                f"Cursed! -{CURSE_STAT_PENALTY}% {stat.capitalize()} for {CURSE_DURATION} combats."
            )

    elif etype == "blessing":
        new_effect = {
            "type": "blessing",
            "stat": effect["stat"],
            "value": effect["value"],
            "combats_remaining": effect["combats"],
        }
        updated = list(active_effects) + [new_effect]
        result["effect_updates"] = updated

    elif etype == "stat_debuff":
        for stat in effect["stats"]:
            new_effect = {
                "type": "stat_debuff",
                "stat": stat,
                "value": effect["value"],
                "combats_remaining": effect["combats"],
            }
            active_effects = list(active_effects) + [new_effect]
        result["effect_updates"] = active_effects

    elif etype == "combat":
        result["combat"] = True
        hp_pen = effect.get("hp_penalty", 0)
        if hp_pen > 0:
            new_hp = max(1, player["hp"] - hp_pen)
            result["player_updates"]["hp"] = new_hp
            result["combat_hp_penalty"] = hp_pen

    elif etype == "death":
        chance = effect.get("chance", 15)
        if random.randint(1, 100) <= chance:
            result["death"] = True
            result["messages"].append("The trap was lethal! You have been slain.")
        else:
            result["messages"].append("You narrowly avoid a deadly trap!")

    return result


# ── Dungeon effect helpers ─────────────────────────────────────────

def apply_dungeon_effects_to_player(player: dict, effects: list) -> dict:
    """
    Return a modified copy of player stats with active curses/blessings applied.
    Does NOT modify the original player dict.
    """
    modified = dict(player)
    for eff in effects:
        stat = eff.get("stat")
        if not stat or stat not in ALL_STATS:
            continue
        if eff["type"] == "curse":
            reduction = int(modified[stat] * eff["value"] / 100)
            modified[stat] = max(1, modified[stat] - reduction)
        elif eff["type"] == "blessing":
            bonus = int(modified[stat] * eff["value"] / 100)
            modified[stat] = modified[stat] + bonus
        elif eff["type"] == "stat_debuff":
            modified[stat] = max(1, modified[stat] - eff["value"])
    return modified


def tick_dungeon_effects(effects: list) -> list:
    """Decrement combats_remaining for all effects. Remove expired ones."""
    remaining = []
    for eff in effects:
        eff["combats_remaining"] -= 1
        if eff["combats_remaining"] > 0:
            remaining.append(eff)
    return remaining


# ── Map rendering ──────────────────────────────────────────────────

TILE_EMOJIS = {
    "start":  "\U0001f7e2",   # green circle
    "path":   "\u2b1c",       # white square
    "wall":   "\u2b1b",       # black square
    "sr":     "\U0001f7e3",   # purple circle
    "combat": "\U0001f534",   # red circle
    "boss":   "\U0001f480",   # skull
    "exit":   "\U0001f6aa",   # door
}
FOG_EMOJI = "\u2b1b"          # black square for unexplored
PLAYER_EMOJI = "\U0001f9d9"   # mage emoji for player


def render_map(floor_data: dict, visited: list, position: tuple) -> str:
    """Render the dungeon map as an emoji grid string."""
    visited_set = {(v[0], v[1]) for v in visited}
    lines = []
    for r, row in enumerate(floor_data["tiles"]):
        line = ""
        for c, tile in enumerate(row):
            if (r, c) == tuple(position):
                line += PLAYER_EMOJI
            elif tile == "wall":
                line += TILE_EMOJIS["wall"]
            elif (r, c) in visited_set:
                line += TILE_EMOJIS.get(tile, "\u2b1c")
            else:
                line += FOG_EMOJI
        lines.append(line)
    return "\n".join(lines)


MAP_LEGEND = (
    "\U0001f9d9 You | \u2b1c Path | \u2b1b Wall/Fog\n"
    "\U0001f7e3 Scenario | \U0001f534 Combat | \U0001f480 Boss | \U0001f6aa Exit"
)
