# --- Resource Regeneration (per tile move) ---
REGEN_SP_PER_TILE = 5
REGEN_MANA_PER_TILE = 10
REGEN_HP_PER_TILE = 10

# --- Base Resources ---
BASE_HP = 100
BASE_MANA = 50
BASE_SP = 30

# --- Stat Multipliers ---
STRENGTH_MULTIPLIER = 0.2
DEXTERITY_MULTIPLIER = 0.4
INTELLIGENCE_DMG_MULTIPLIER = 0.2
INTELLIGENCE_EFFECT_MULTIPLIER = 0.4
AGILITY_MULTIPLIER = 0.2
WISDOM_MULTIPLIER = 0.4
ENDURANCE_HP_PER_POINT = 10
ENDURANCE_MANA_PER_POINT = 5
ENDURANCE_SP_PER_POINT = 5
CHARISMA_SONG_MULTIPLIER = 0.2
CHARISMA_BUFF_MULTIPLIER = 0.4

# --- Leveling ---
STAT_POINTS_PER_LEVEL = 5
SKILL_UNLOCK_INTERVAL = 5
TALENT_UNLOCK_INTERVAL = 10
PERFECT_ENCOUNTER_XP_BONUS = 0.10

# --- Combat Turn Rules ---
MAX_ATTACKS_PER_TURN = 1
MAX_BUFFS_PER_TURN = 1
MAX_ITEMS_PER_TURN = 1

# --- Armor ---
ARMOR_REDUCTION_CONSTANT = 500
MAX_AR_BY_SLOT = {
    "head": 100, "shoulders": 90, "chest": 110,
    "gloves": 80, "legs": 90, "feet": 80,
}

# --- Weapon/Armor Rarity ---
RARITY_TIERS = ["poor", "common", "uncommon", "rare", "epic", "legendary"]

WEAPON_DAMAGE_RANGES = {
    "poor": (3, 11), "common": (9, 16), "uncommon": (13, 21),
    "rare": (18, 26), "epic": (23, 31), "legendary": (28, 36),
}

WEAPON_DROP_CHANCES = {
    "poor": 50.9, "common": 30.0, "uncommon": 10.0,
    "rare": 5.0, "epic": 4.0, "legendary": 0.1,
}

ARMOR_RARITY_MULTIPLIERS = {
    "common": (1.1, 1.5), "uncommon": (1.5, 2.0), "rare": (2.0, 2.5),
    "epic": (2.5, 3.0), "legendary": (3.0, 5.0),
}

# --- Stat Affix Rules ---
STAT_AFFIX_RULES = {
    "poor": {"count": 0, "multipliers": []},
    "common": {"count": 0, "multipliers": []},
    "uncommon": {"count": 1, "multipliers": [1]},
    "rare": {"count": 2, "multipliers": [2, 1]},
    "epic": {"count": 3, "multipliers": [3, 2, 1]},
    "legendary": {"count": 3, "multipliers": [3, 3, 2]},
}

AFFIX_BASE_PER_FLOOR_GROUP = 1

# --- Scenario Chances ---
SCENARIO_NEGATIVE_CHANCE = 33
SCENARIO_POSITIVE_CHANCE = 33
SCENARIO_NEUTRAL_CHANCE = 34
ENCOUNTER_CHANCE_PER_TILE = 60

# --- Flee ---
BASE_FLEE_CHANCE = 30
AGILITY_FLEE_BONUS = 1

# --- Combat ---
UNARMED_DAMAGE_MIN = 5
UNARMED_DAMAGE_MAX = 10
THRUST_STUN_CHANCE = 10
THRUST_DAMAGE_MULTIPLIER = 0.7
ENEMY_TYPES = ["goblin", "feral_rat"]
LOOT_DROP_CHANCE = 0.5
BURN_DAMAGE_PER_TURN = 5
BLEED_DAMAGE_PER_TURN = 3
POISON_DAMAGE_PER_TURN = 4

# --- Stats List ---
ALL_STATS = [
    "strength", "dexterity", "intelligence", "agility",
    "wisdom", "endurance", "charisma",
]
