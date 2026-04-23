"""Pure stat and combat formula functions. No DB or state dependencies."""

import math

from src.game.constants import (
    AGILITY_MULTIPLIER,
    ARMOR_REDUCTION_CONSTANT,
    CHARISMA_BUFF_MULTIPLIER,
    CHARISMA_SONG_MULTIPLIER,
    DEXTERITY_MULTIPLIER,
    ENDURANCE_HP_PER_POINT,
    ENDURANCE_MANA_PER_POINT,
    ENDURANCE_SP_PER_POINT,
    INTELLIGENCE_DMG_MULTIPLIER,
    INTELLIGENCE_EFFECT_MULTIPLIER,
    STRENGTH_MULTIPLIER,
    WISDOM_MULTIPLIER,
)


# --- Strength ---
def calc_bonus_physical_damage(strength: int) -> float:
    return strength * STRENGTH_MULTIPLIER


# --- Dexterity ---
def calc_double_strike_chance(dexterity: int) -> float:
    return dexterity * DEXTERITY_MULTIPLIER


# --- Intelligence ---
def calc_bonus_spell_damage(intelligence: int) -> float:
    return intelligence * INTELLIGENCE_DMG_MULTIPLIER


def calc_spell_effect_chance(intelligence: int) -> float:
    return intelligence * INTELLIGENCE_EFFECT_MULTIPLIER


# --- Agility ---
def calc_dodge_chance(agility: int) -> float:
    return agility * AGILITY_MULTIPLIER


# --- Wisdom ---
def calc_healing_bonus(wisdom: int) -> float:
    return wisdom * WISDOM_MULTIPLIER


def calc_buff_extend_chance(wisdom: int) -> float:
    return wisdom * WISDOM_MULTIPLIER


# --- Endurance ---
def calc_bonus_hp(endurance: int) -> int:
    return endurance * ENDURANCE_HP_PER_POINT


def calc_bonus_mana(endurance: int) -> int:
    return endurance * ENDURANCE_MANA_PER_POINT


def calc_bonus_sp(endurance: int) -> int:
    return endurance * ENDURANCE_SP_PER_POINT


# --- Charisma ---
def calc_song_bonus(charisma: int) -> float:
    return charisma * CHARISMA_SONG_MULTIPLIER


def calc_buff_duration_chance(charisma: int) -> float:
    return charisma * CHARISMA_BUFF_MULTIPLIER


# --- Derived Resources ---
def calc_max_hp(base_hp: int, endurance: int) -> int:
    return base_hp + calc_bonus_hp(endurance)


def calc_max_mana(base_mana: int, endurance: int) -> int:
    return base_mana + calc_bonus_mana(endurance)


def calc_max_sp(base_sp: int, endurance: int) -> int:
    return base_sp + calc_bonus_sp(endurance)


# --- Armor ---
def calc_armor_reduction(total_ar: int) -> float:
    """Returns damage reduction as a percentage (0-100)."""
    if total_ar <= 0:
        return 0.0
    return (total_ar / (total_ar + ARMOR_REDUCTION_CONSTANT)) * 100


# --- Duration ---
def calc_main_stat_duration(main_stat_value: int) -> int:
    """Calculate buff/debuff duration from main stat. Minimum 1 turn."""
    return max(1, math.floor(main_stat_value / 10))
