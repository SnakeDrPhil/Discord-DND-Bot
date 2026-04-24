"""Load and query static JSON game data files."""

import json
import os
from typing import Optional, Union

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_cache: dict = {}


def _load(filename: str) -> Union[list, dict]:
    """Load a JSON file from the data directory, with caching."""
    if filename not in _cache:
        filepath = os.path.join(_DATA_DIR, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            _cache[filename] = json.load(f)
    return _cache[filename]


def clear_cache():
    """Clear the data cache (useful for testing)."""
    _cache.clear()


# --- Skills ---

def get_skills(class_name: Optional[str] = None) -> list:
    """Return skills, optionally filtered by class."""
    skills = _load("skills.json")
    if class_name:
        return [s for s in skills if s["class"] == class_name]
    return skills


def get_skill_by_id(skill_id: str) -> Optional[dict]:
    """Return a single skill by its ID."""
    for s in _load("skills.json"):
        if s["id"] == skill_id:
            return s
    return None


# --- Talents ---

def get_talents(class_name: Optional[str] = None) -> list:
    """Return talents, optionally filtered by class."""
    talents = _load("talents.json")
    if class_name:
        return [t for t in talents if t["class"] == class_name]
    return talents


def get_talent_by_id(talent_id: str) -> Optional[dict]:
    """Return a single talent by its ID."""
    for t in _load("talents.json"):
        if t["id"] == talent_id:
            return t
    return None


# --- Weapons ---

def get_weapons(class_theme: Optional[str] = None) -> list:
    """Return weapons, optionally filtered by class theme."""
    weapons = _load("weapons.json")
    if class_theme:
        return [w for w in weapons if w["class_theme"] == class_theme]
    return weapons


# --- Armor ---

def get_armor(
    class_name: Optional[str] = None,
    slot: Optional[str] = None,
    armor_type: Optional[str] = None,
) -> list:
    """Return armor, optionally filtered by class, slot, or armor type."""
    items = _load("armor.json")
    if class_name:
        items = [a for a in items if class_name in a["allowed_classes"]]
    if slot:
        items = [a for a in items if a["slot"] == slot]
    if armor_type:
        items = [a for a in items if a["armor_type"] == armor_type]
    return items


# --- Consumables ---

def get_consumables(category: Optional[str] = None) -> list:
    """Return consumables, optionally filtered by category."""
    items = _load("consumables.json")
    if category:
        return [c for c in items if c["category"] == category]
    return items


# --- Enemies ---

def get_enemies(enemy_type: Optional[str] = None, level: Optional[int] = None) -> list:
    """Return enemy data, optionally filtered by type and/or level."""
    enemies = _load("enemies.json")
    if enemy_type:
        enemies = [e for e in enemies if e["type"] == enemy_type]
    if level is not None:
        enemies = [e for e in enemies if e["level"] == level]
    return enemies


# --- Loot Tables ---

def get_loot_table(enemy_type: str) -> list:
    """Return the loot table for a given enemy type."""
    tables = _load("loot_tables.json")
    return tables.get(enemy_type, [])


# --- XP Thresholds ---

def get_xp_thresholds() -> list:
    """Return all XP thresholds."""
    return _load("xp_thresholds.json")


def get_xp_for_level(level: int) -> Optional[int]:
    """Return total XP needed to reach a given level."""
    for entry in _load("xp_thresholds.json"):
        if entry["level"] == level:
            return entry["total_xp_needed"]
    return None


# --- Classes ---

def get_classes() -> list:
    """Return all class definitions."""
    return _load("classes.json")


def get_class(class_id: str) -> Optional[dict]:
    """Return a single class definition by ID."""
    for c in _load("classes.json"):
        if c["id"] == class_id:
            return c
    return None


# --- Maps ---

def get_floor(floor_number: int) -> Optional[dict]:
    """Return a floor definition by floor number."""
    maps = _load("maps.json")
    for floor in maps["floors"]:
        if floor["floor"] == floor_number:
            return floor
    return None


# --- Scenarios ---

def get_weapon_by_id(weapon_id: str) -> Optional[dict]:
    """Return a single weapon by its ID."""
    for w in _load("weapons.json"):
        if w["id"] == weapon_id:
            return w
    return None


def get_boss(boss_type: str) -> Optional[dict]:
    """Return boss enemy data by type."""
    for e in _load("enemies.json"):
        if e["type"] == boss_type and e.get("is_boss"):
            return e
    return None


def get_armor_by_id(armor_id: str) -> Optional[dict]:
    """Return a single armor piece by its ID."""
    for a in _load("armor.json"):
        if a["id"] == armor_id:
            return a
    return None


def get_scenarios(category: Optional[str] = None) -> Union[list, dict]:
    """Return scenario events, optionally filtered by category."""
    data = _load("scenarios.json")
    if category:
        return data.get(category, [])
    return data
