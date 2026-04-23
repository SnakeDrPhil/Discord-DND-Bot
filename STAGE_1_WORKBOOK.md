# Stage 1 Workbook -- Foundation, Data Models & Bot Skeleton

**Purpose:** This document contains every piece of information needed to implement Stage 1 without referring back to the PDF. It is a self-contained build spec.

---

## Table of Contents

1. [Project Setup](#1-project-setup)
2. [Folder Structure](#2-folder-structure)
3. [Dependencies](#3-dependencies)
4. [Database Schema](#4-database-schema)
5. [Static Data: skills.json](#5-static-data-skillsjson)
6. [Static Data: talents.json](#6-static-data-talentsjson)
7. [Static Data: weapons.json](#7-static-data-weaponsjson)
8. [Static Data: armor.json](#8-static-data-armorjson)
9. [Static Data: consumables.json](#9-static-data-consumablesjson)
10. [Static Data: enemies.json](#10-static-data-enemiesjson)
11. [Static Data: loot_tables.json](#11-static-data-loot_tablesjson)
12. [Static Data: xp_thresholds.json](#12-static-data-xp_thresholdsjson)
13. [Static Data: classes.json](#13-static-data-classesjson)
14. [Static Data: maps.json](#14-static-data-mapsjson)
15. [Game Constants](#15-game-constants)
16. [Bot Skeleton](#16-bot-skeleton)
17. [Validation Checklist](#17-validation-checklist)

---

## 1. Project Setup

- **Language:** Python 3.11+
- **Discord Library:** discord.py (latest stable, v2.x) with slash command support
- **Database:** SQLite for development (single file, zero config), with aiosqlite for async access
- **ORM:** None initially -- use raw SQL via aiosqlite to keep it simple. Migrate to SQLAlchemy later if needed.
- **Data Format:** JSON for all static game data
- **Config:** `.env` file for secrets (bot token, DB path)
- **Entry point:** `bot.py`

---

## 2. Folder Structure

```
Discord-DND-Bot/
  bot.py                    # Entry point -- loads cogs, connects to Discord
  .env                      # BOT_TOKEN, DATABASE_PATH (git-ignored)
  .env.example              # Template for .env
  .gitignore                # .env, __pycache__, *.db, etc.
  requirements.txt          # Python dependencies

  src/
    __init__.py

    bot/
      __init__.py
      cogs/
        __init__.py
        general.py          # /ping, /help
        # Future cogs: character.py, combat.py, dungeon.py, inventory.py

    game/
      __init__.py
      constants.py          # All game constants (regen rates, base resources, multipliers)
      formulas.py           # Stat formulas, damage calc, armor reduction
      # Future: combat.py, dungeon.py, scenarios.py

    db/
      __init__.py
      database.py           # DB connection, init, migration functions
      models.py             # CRUD operations for players, inventories, etc.

    utils/
      __init__.py
      embeds.py             # Discord embed builder helpers
      data_loader.py        # Load and validate JSON data files

  data/
    skills.json
    talents.json
    weapons.json
    armor.json
    consumables.json
    enemies.json
    loot_tables.json
    xp_thresholds.json
    classes.json
    maps.json
```

---

## 3. Dependencies

```
# requirements.txt
discord.py>=2.3.0
python-dotenv>=1.0.0
aiosqlite>=0.19.0
```

---

## 4. Database Schema

### 4.1 players

```sql
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT UNIQUE NOT NULL,
    character_name TEXT NOT NULL,
    class TEXT NOT NULL,  -- warrior, rogue, mage, ranger, bard, cleric
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,

    -- Current resources
    hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    mana INTEGER NOT NULL,
    max_mana INTEGER NOT NULL,
    sp INTEGER NOT NULL,
    max_sp INTEGER NOT NULL,

    -- Stats (7 core stats)
    strength INTEGER NOT NULL,
    dexterity INTEGER NOT NULL,
    intelligence INTEGER NOT NULL,
    agility INTEGER NOT NULL,
    wisdom INTEGER NOT NULL,
    endurance INTEGER NOT NULL,
    charisma INTEGER NOT NULL,

    unspent_stat_points INTEGER NOT NULL DEFAULT 0,

    -- Progression
    learned_skills TEXT NOT NULL DEFAULT '[]',    -- JSON array of skill IDs
    selected_talents TEXT NOT NULL DEFAULT '[]',  -- JSON array of talent IDs

    -- Dungeon state
    current_floor INTEGER NOT NULL DEFAULT 1,
    position_x INTEGER NOT NULL DEFAULT 0,
    position_y INTEGER NOT NULL DEFAULT 0,
    in_dungeon INTEGER NOT NULL DEFAULT 0,  -- boolean 0/1

    -- Gold
    gold INTEGER NOT NULL DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 inventories

```sql
CREATE TABLE IF NOT EXISTS inventories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,       -- 'weapon', 'armor', 'consumable', 'loot'
    item_id TEXT NOT NULL,         -- References the ID in the corresponding JSON data
    item_data TEXT NOT NULL,       -- JSON: generated stats, rarity, affixes for this instance
    equipped INTEGER NOT NULL DEFAULT 0,  -- 0=in bag, 1=equipped
    slot TEXT,                     -- Equipment slot if equipped: 'head','shoulders','chest','gloves','legs','feet','main_hand','off_hand'
    quantity INTEGER NOT NULL DEFAULT 1,  -- For stackable items (consumables, loot)

    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);
```

### 4.3 combat_sessions

```sql
CREATE TABLE IF NOT EXISTS combat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE,  -- One active combat per player

    -- Enemy state
    enemies TEXT NOT NULL,              -- JSON array: [{type, level, hp, max_hp, buffs, debuffs}]

    -- Combat state
    turn_number INTEGER NOT NULL DEFAULT 1,
    current_turn TEXT NOT NULL DEFAULT 'player',  -- 'player' or 'enemy_0', 'enemy_1', etc.

    -- Player combat state
    player_buffs TEXT NOT NULL DEFAULT '[]',      -- JSON: [{name, remaining_turns, effect}]
    player_debuffs TEXT NOT NULL DEFAULT '[]',    -- JSON: [{name, remaining_turns, effect}]

    -- Enemy combat state
    enemy_buffs TEXT NOT NULL DEFAULT '[]',
    enemy_debuffs TEXT NOT NULL DEFAULT '[]',

    -- Turn action tracking (reset each turn)
    attacks_used INTEGER NOT NULL DEFAULT 0,
    buffs_used INTEGER NOT NULL DEFAULT 0,
    items_used INTEGER NOT NULL DEFAULT 0,

    -- Flags
    extra_turn INTEGER NOT NULL DEFAULT 0,
    damage_taken INTEGER NOT NULL DEFAULT 0,  -- Tracks if player took damage (for Perfect Encounter)

    -- Combat log
    combat_log TEXT NOT NULL DEFAULT '[]',     -- JSON array of log entries

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);
```

### 4.4 dungeon_sessions

```sql
CREATE TABLE IF NOT EXISTS dungeon_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE,
    floor INTEGER NOT NULL DEFAULT 1,
    position_x INTEGER NOT NULL DEFAULT 0,
    position_y INTEGER NOT NULL DEFAULT 0,
    visited_tiles TEXT NOT NULL DEFAULT '[]',    -- JSON array: [[x,y], [x,y], ...]
    active_effects TEXT NOT NULL DEFAULT '[]',   -- JSON: [{type, remaining_combats, effect}]

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);
```

---

## 5. Static Data: skills.json

Every class has exactly 10 skills. Players pick 1 skill every 5 levels (levels 5, 10, 15, 20). Resource types: SP (physical classes) or Mana (caster classes). Main stat mapping used for duration: Warrior=Strength, Rogue=Dexterity, Mage=Intelligence, Ranger=Dexterity, Bard=Charisma, Cleric=Wisdom.

"(Based on Main Stat)" duration formula: `floor(main_stat / 10)` turns, minimum 1 turn.

```json
[
  {
    "id": "warrior_whirlwind_attack",
    "class": "warrior",
    "name": "Whirlwind Attack",
    "type": "slash",
    "cost": 3,
    "resource": "sp",
    "target": "enemies_3",
    "effect": "Deals moderate damage to three nearby enemies.",
    "damage_multiplier": 0.8,
    "max_targets": 3,
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "warrior_armor_up",
    "class": "warrior",
    "name": "Armor Up",
    "type": "buff",
    "cost": 2,
    "resource": "sp",
    "target": "self",
    "effect": "Increases Defense by 25% for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "defense_up", "value": 25, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "warrior_counterattack",
    "class": "warrior",
    "name": "Counterattack",
    "type": "parry",
    "cost": 3,
    "resource": "sp",
    "target": "self",
    "effect": "Reflects 50% of damage taken back to the attacker.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "reflect", "value": 50, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "warrior_mighty_roar",
    "class": "warrior",
    "name": "Mighty Roar",
    "type": "debuff",
    "cost": 2,
    "resource": "sp",
    "target": "all_enemies",
    "effect": "Reduces enemies' strength by 15% for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": null,
    "status_effects": [{"type": "strength_down", "value": 15, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "warrior_ground_slam",
    "class": "warrior",
    "name": "Ground Slam",
    "type": "blunt",
    "cost": 3,
    "resource": "sp",
    "target": "enemies_3",
    "effect": "Deals damage in a cone to three enemies.",
    "damage_multiplier": 0.9,
    "max_targets": 3,
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "warrior_shield_bash",
    "class": "warrior",
    "name": "Shield Bash",
    "type": "blunt",
    "cost": 3,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "Deals damage based on endurance with a 25% chance to stun for 1 turn.",
    "damage_multiplier": 1.0,
    "max_targets": 1,
    "status_effects": [{"type": "stun", "chance": 25, "duration": 1}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "warrior_battle_cry",
    "class": "warrior",
    "name": "Battle Cry",
    "type": "buff",
    "cost": 2,
    "resource": "sp",
    "target": "self",
    "effect": "Increases strength by 20% for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "strength_up", "value": 20, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "warrior_defensive_stance",
    "class": "warrior",
    "name": "Defensive Stance",
    "type": "buff",
    "cost": 3,
    "resource": "sp",
    "target": "self",
    "effect": "Reduces damage taken by 30% for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "damage_reduction", "value": 30, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "warrior_rampage",
    "class": "warrior",
    "name": "Rampage",
    "type": "slash",
    "cost": 4,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "Deals 3 slashes, each dealing +20% damage.",
    "damage_multiplier": 1.2,
    "hit_count": 3,
    "max_targets": 1,
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "warrior_tactical_retreat",
    "class": "warrior",
    "name": "Tactical Retreat",
    "type": "buff",
    "cost": 3,
    "resource": "sp",
    "target": "self",
    "effect": "50% chance to avoid damage for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "evasion", "chance": 50}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "rogue_shadow_step",
    "class": "rogue",
    "name": "Shadow Step",
    "type": "weapon_based",
    "cost": 3,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "Instantly teleport behind the enemy, striking them twice. Gain 20% dodge chance at the end of your turn.",
    "damage_multiplier": 1.0,
    "hit_count": 2,
    "max_targets": 1,
    "status_effects": [{"type": "dodge_up", "value": 20, "unit": "percent", "duration": 1}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "rogue_dagger_throw",
    "class": "rogue",
    "name": "Dagger Throw",
    "type": "stab",
    "cost": 2,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "25% chance to apply bleed, causing damage for 2 turns.",
    "damage_multiplier": 0.8,
    "max_targets": 1,
    "status_effects": [{"type": "bleed", "chance": 25, "duration": 2}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "rogue_silent_kill",
    "class": "rogue",
    "name": "Silent Kill",
    "type": "weapon_based",
    "cost": 4,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "Deals 200% damage to enemies below 5% HP.",
    "damage_multiplier": 2.0,
    "max_targets": 1,
    "condition": "target_below_5_percent_hp",
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "rogue_disarm_target",
    "class": "rogue",
    "name": "Disarm Target",
    "type": "ability",
    "cost": 2,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "The rogue disarms the target, preventing them from using weapon-based attacks for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "disarm"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "rogue_vanish",
    "class": "rogue",
    "name": "Vanish",
    "type": "skill_buff",
    "cost": 3,
    "resource": "sp",
    "target": "self",
    "effect": "Become untargetable for 1 turn. +50% attack damage on player's next turn for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "untargetable", "duration": 1}, {"type": "damage_up", "value": 50, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "rogue_backstab",
    "class": "rogue",
    "name": "Backstab",
    "type": "stab",
    "cost": 4,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "Deals 150% damage to targets affected by bleed.",
    "damage_multiplier": 1.5,
    "max_targets": 1,
    "condition": "target_has_bleed",
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "rogue_cloaked_in_shadows",
    "class": "rogue",
    "name": "Cloaked in Shadows",
    "type": "skill_buff",
    "cost": 2,
    "resource": "sp",
    "target": "self",
    "effect": "+40% dodge chance for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "dodge_up", "value": 40, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "rogue_smoke_bomb",
    "class": "rogue",
    "name": "Smoke Bomb",
    "type": "skill",
    "cost": 3,
    "resource": "sp",
    "target": "all",
    "effect": "Blinds both you and enemies, skipping two turns.",
    "damage_multiplier": null,
    "max_targets": null,
    "status_effects": [{"type": "blind", "duration": 2, "affects": "all"}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "rogue_quick_escape",
    "class": "rogue",
    "name": "Quick Escape",
    "type": "skill",
    "cost": 5,
    "resource": "sp",
    "target": "self",
    "effect": "30% chance to escape from battle.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "flee", "chance": 30}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "rogue_grappling_hook",
    "class": "rogue",
    "name": "Grappling Hook",
    "type": "skill",
    "cost": 3,
    "resource": "sp",
    "target": "self",
    "effect": "Move to elevated positions, avoiding melee attacks for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "melee_immune"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "mage_frost_nova",
    "class": "mage",
    "name": "Frost Nova",
    "type": "ice_spell",
    "cost": 6,
    "resource": "mana",
    "target": "all_enemies",
    "effect": "Deals damage and slows nearby enemies for (Based on Main Stat) turns.",
    "damage_multiplier": 0.8,
    "max_targets": null,
    "status_effects": [{"type": "slow"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "mage_fire_wall",
    "class": "mage",
    "name": "Fire Wall",
    "type": "fire_spell",
    "cost": 8,
    "resource": "mana",
    "target": "all_enemies",
    "effect": "Burn damage to enemies in melee range for (Based on Main Stat) turns.",
    "damage_multiplier": 0.6,
    "max_targets": null,
    "status_effects": [{"type": "burn"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "mage_mana_shield",
    "class": "mage",
    "name": "Mana Shield",
    "type": "buff",
    "cost": 5,
    "resource": "mana",
    "target": "self",
    "effect": "Absorbs damage for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "absorb"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "mage_illusion",
    "class": "mage",
    "name": "Illusion",
    "type": "spell",
    "cost": 4,
    "resource": "mana",
    "target": "self",
    "effect": "Diverts attacks to an illusion for (Based on Main Stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "illusion"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "mage_arcane_burst",
    "class": "mage",
    "name": "Arcane Burst",
    "type": "spell",
    "cost": 7,
    "resource": "mana",
    "target": "enemies_3",
    "effect": "Deals moderate damage to three enemies.",
    "damage_multiplier": 0.9,
    "max_targets": 3,
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "mage_fireball",
    "class": "mage",
    "name": "Fireball",
    "type": "fire_spell",
    "cost": 6,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Deals high damage, and has a 30% chance to burn the target for (Based on Main Stat) turns.",
    "damage_multiplier": 1.3,
    "max_targets": 1,
    "status_effects": [{"type": "burn", "chance": 30}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "mage_ice_spike",
    "class": "mage",
    "name": "Ice Spike",
    "type": "ice_spell",
    "cost": 5,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "20% chance to freeze the target for (Based on Main Stat) turns.",
    "damage_multiplier": 1.0,
    "max_targets": 1,
    "status_effects": [{"type": "freeze", "chance": 20}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "mage_magic_missile",
    "class": "mage",
    "name": "Magic Missile",
    "type": "spell",
    "cost": 3,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Low damage but cannot miss.",
    "damage_multiplier": 0.5,
    "max_targets": 1,
    "auto_hit": true,
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "mage_teleportation",
    "class": "mage",
    "name": "Teleportation",
    "type": "skill_buff",
    "cost": 4,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Skips 1 enemy turn.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "skip_turn", "duration": 1}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "mage_elemental_burst",
    "class": "mage",
    "name": "Elemental Burst",
    "type": "spell",
    "cost": 9,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Random elemental effect. Guaranteed to cause the element's effect. (fire=burn, ice=slow, lightning=stun).",
    "damage_multiplier": 1.1,
    "max_targets": 1,
    "random_element": true,
    "status_effects": [{"type": "random_element", "chance": 100}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "ranger_concentrated_shot",
    "class": "ranger",
    "name": "Concentrated Shot",
    "type": "skill",
    "cost": 4,
    "resource": "sp",
    "target": "self",
    "effect": "Deals double damage on the next shot.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "next_attack_bonus", "value": 100, "unit": "percent"}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "ranger_trap_setting",
    "class": "ranger",
    "name": "Trap Setting",
    "type": "skill",
    "cost": 3,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "Set a trap with a 50% chance to deal low damage and immobilize an enemy, skipping that enemy's turn.",
    "damage_multiplier": 0.4,
    "max_targets": 1,
    "status_effects": [{"type": "immobilize", "chance": 50}, {"type": "skip_turn", "chance": 50, "duration": 1}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "ranger_natures_grasp",
    "class": "ranger",
    "name": "Nature's Grasp",
    "type": "skill",
    "cost": 3,
    "resource": "sp",
    "target": "all_enemies",
    "effect": "Summons vines to slow all enemies present.",
    "damage_multiplier": null,
    "max_targets": null,
    "status_effects": [{"type": "slow"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "ranger_multi_shot",
    "class": "ranger",
    "name": "Multi-Shot",
    "type": "skill",
    "cost": 3,
    "resource": "sp",
    "target": "single_enemy",
    "effect": "Fires two arrows at one target, each dealing moderate damage.",
    "damage_multiplier": 0.8,
    "hit_count": 2,
    "max_targets": 1,
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "ranger_beast_companion",
    "class": "ranger",
    "name": "Beast Companion",
    "type": "skill",
    "cost": 4,
    "resource": "sp",
    "target": "summon",
    "effect": "Summon a temporary animal companion to attack. Animal damage (Based on Main Stat). Animal lasts for (Based on Main Stat) turns. Cannot be attacked.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "summon_companion", "untargetable": true}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "ranger_natures_karma",
    "class": "ranger",
    "name": "Nature's Karma",
    "type": "skill_buff",
    "cost": 4,
    "resource": "sp",
    "target": "self",
    "effect": "Deal 150% damage when attacking enemies affected by slow. Lasts for (Based on Main Stat) turns.",
    "damage_multiplier": 1.5,
    "max_targets": 1,
    "condition": "target_has_slow",
    "status_effects": [{"type": "conditional_damage_up", "value": 150, "condition": "slow"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "ranger_hawkeye",
    "class": "ranger",
    "name": "Hawkeye",
    "type": "skill_buff",
    "cost": 2,
    "resource": "sp",
    "target": "self",
    "effect": "Increases critical hit chance by 20% for your next attack.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "crit_up", "value": 20, "unit": "percent", "duration": 1}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "ranger_eagle_eye",
    "class": "ranger",
    "name": "Eagle Eye",
    "type": "skill",
    "cost": 2,
    "resource": "sp",
    "target": "self",
    "effect": "The next attack deals 50% bonus damage and ignores enemy armor.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "next_attack_bonus", "value": 50, "unit": "percent"}, {"type": "armor_pierce", "duration": 1}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "ranger_natures_shield",
    "class": "ranger",
    "name": "Nature's Shield",
    "type": "skill",
    "cost": 3,
    "resource": "sp",
    "target": "self",
    "effect": "Gain +20% damage resistance for 2 turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "damage_reduction", "value": 20, "unit": "percent", "duration": 2}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "ranger_long_shot",
    "class": "ranger",
    "name": "Long Shot",
    "type": "skill",
    "cost": 4,
    "resource": "sp",
    "target": "furthest_enemy",
    "effect": "Deals 200% damage to the furthest target.",
    "damage_multiplier": 2.0,
    "max_targets": 1,
    "status_effects": [],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "bard_heroic_anthem",
    "class": "bard",
    "name": "Heroic Anthem",
    "type": "skill",
    "cost": 5,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Deal moderate damage to one enemy. Stuns for (based on main stat) turns.",
    "damage_multiplier": 0.9,
    "max_targets": 1,
    "status_effects": [{"type": "stun"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "bard_dissonant_chord",
    "class": "bard",
    "name": "Dissonant Chord",
    "type": "skill",
    "cost": 4,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Reduces an enemy's accuracy by 50% for (based on main stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "accuracy_down", "value": 50, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "bard_rallying_cry",
    "class": "bard",
    "name": "Rallying Cry",
    "type": "buff",
    "cost": 3,
    "resource": "mana",
    "target": "self",
    "effect": "Increases the damage of your next attack by 40%.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "next_attack_bonus", "value": 40, "unit": "percent"}],
    "duration_rule": null,
    "unlock_level": 5
  },
  {
    "id": "bard_fascinating_tune",
    "class": "bard",
    "name": "Fascinating Tune",
    "type": "skill",
    "cost": 4,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Enchants a target, causing them to take moderate damage and reducing their attack power by 15% for (based on main stat) turns.",
    "damage_multiplier": 0.7,
    "max_targets": 1,
    "status_effects": [{"type": "attack_down", "value": 15, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "bard_ballad_of_resilience",
    "class": "bard",
    "name": "Ballad of Resilience",
    "type": "buff",
    "cost": 6,
    "resource": "mana",
    "target": "self",
    "effect": "Increases your defense by 15% for (based on main stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "defense_up", "value": 15, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "bard_inspiring_tune",
    "class": "bard",
    "name": "Inspiring Tune",
    "type": "skill",
    "cost": 5,
    "resource": "mana",
    "target": "self",
    "effect": "Restores 15% of your max health immediately.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "heal", "value": 15, "unit": "percent_max_hp"}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "bard_charming_song",
    "class": "bard",
    "name": "Charming Song",
    "type": "skill",
    "cost": 7,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Charms one enemy for (based on main stat) turns, making them attack their allies instead of you.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "charm"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "bard_echoing_song",
    "class": "bard",
    "name": "Echoing Song",
    "type": "skill",
    "cost": 5,
    "resource": "mana",
    "target": "all_enemies",
    "effect": "Deals moderate damage to all enemies, and lowers all enemies armor 25% for (based on main stat) turns.",
    "damage_multiplier": 0.7,
    "max_targets": null,
    "status_effects": [{"type": "armor_down", "value": 25, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "bard_song_shield",
    "class": "bard",
    "name": "Song Shield",
    "type": "skill",
    "cost": 8,
    "resource": "mana",
    "target": "self",
    "effect": "Absorbs damage for (based on main stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "absorb"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "cleric_blessed_strike",
    "class": "cleric",
    "name": "Blessed Strike",
    "type": "skill",
    "cost": 4,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Deals moderate damage and heals yourself for 10% of the damage dealt.",
    "damage_multiplier": 0.9,
    "max_targets": 1,
    "status_effects": [{"type": "lifesteal", "value": 10, "unit": "percent"}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "cleric_sanctuary",
    "class": "cleric",
    "name": "Sanctuary",
    "type": "skill",
    "cost": 6,
    "resource": "mana",
    "target": "self",
    "effect": "Restores 10% HP per turn for 2 turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "heal_over_time", "value": 10, "unit": "percent_max_hp", "duration": 2}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "cleric_divine_smite",
    "class": "cleric",
    "name": "Divine Smite",
    "type": "skill",
    "cost": 5,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Deals moderate damage with a chance to stun the target for (based on main stat) turns.",
    "damage_multiplier": 1.0,
    "max_targets": 1,
    "status_effects": [{"type": "stun"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "cleric_healing_wave",
    "class": "cleric",
    "name": "Healing Wave",
    "type": "skill",
    "cost": 8,
    "resource": "mana",
    "target": "self",
    "effect": "Restores 25% of your max HP immediately.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "heal", "value": 25, "unit": "percent_max_hp"}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "cleric_aura_of_protection",
    "class": "cleric",
    "name": "Aura of Protection",
    "type": "skill",
    "cost": 5,
    "resource": "mana",
    "target": "self",
    "effect": "Reduces damage taken by 50% for (based on main stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "damage_reduction", "value": 50, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "cleric_holy_light",
    "class": "cleric",
    "name": "Holy Light",
    "type": "skill",
    "cost": 7,
    "resource": "mana",
    "target": "single_enemy",
    "effect": "Deals low damage to an enemy and restores 15% HP to yourself.",
    "damage_multiplier": 0.5,
    "max_targets": 1,
    "status_effects": [{"type": "heal", "value": 15, "unit": "percent_max_hp"}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "cleric_divine_shield",
    "class": "cleric",
    "name": "Divine Shield",
    "type": "skill",
    "cost": 6,
    "resource": "mana",
    "target": "self",
    "effect": "Absorb damage for (based on main stat) turns.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "absorb"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "cleric_purge",
    "class": "cleric",
    "name": "Purge",
    "type": "skill",
    "cost": 3,
    "resource": "mana",
    "target": "self",
    "effect": "Cleanses 1 debuff (burn, poison, slow, stun) from yourself.",
    "damage_multiplier": null,
    "max_targets": 1,
    "status_effects": [{"type": "cleanse", "count": 1}],
    "duration_rule": null,
    "unlock_level": null
  },
  {
    "id": "cleric_guiding_light",
    "class": "cleric",
    "name": "Guiding Light",
    "type": "skill",
    "cost": 4,
    "resource": "mana",
    "target": "all_enemies",
    "effect": "Lowers all enemies hit chance by 50% for (based on main stat) turns.",
    "damage_multiplier": null,
    "max_targets": null,
    "status_effects": [{"type": "accuracy_down", "value": 50, "unit": "percent"}],
    "duration_rule": "main_stat",
    "unlock_level": null
  },
  {
    "id": "cleric_consecrate_ground",
    "class": "cleric",
    "name": "Consecrate Ground",
    "type": "skill",
    "cost": 7,
    "resource": "mana",
    "target": "self",
    "effect": "Restores 10% HP per turn for 4 turns. Single use per combat scenario.",
    "damage_multiplier": null,
    "max_targets": 1,
    "once_per_combat": true,
    "status_effects": [{"type": "heal_over_time", "value": 10, "unit": "percent_max_hp", "duration": 4}],
    "duration_rule": null,
    "unlock_level": null
  }
]
```

---

## 6. Static Data: talents.json

5 passive talents per class. Players pick 1 talent every 10 levels (levels 10, 20).

```json
[
  {
    "id": "warrior_iron_will",
    "class": "warrior",
    "name": "Iron Will",
    "effect": "Resistance to stuns and slows increased by 25%.",
    "passive_modifiers": [{"type": "status_resistance", "effects": ["stun", "slow"], "value": 25, "unit": "percent"}]
  },
  {
    "id": "warrior_toughened_skin",
    "class": "warrior",
    "name": "Toughened Skin",
    "effect": "Reduces physical damage taken by 10%.",
    "passive_modifiers": [{"type": "physical_damage_reduction", "value": 10, "unit": "percent"}]
  },
  {
    "id": "warrior_berserker_fury",
    "class": "warrior",
    "name": "Berserker Fury",
    "effect": "Gain 5% damage for every 10% HP lost.",
    "passive_modifiers": [{"type": "low_hp_damage_bonus", "value": 5, "per": 10, "unit": "percent"}]
  },
  {
    "id": "warrior_armor_proficiency",
    "class": "warrior",
    "name": "Armor Proficiency",
    "effect": "+10% defense in heavy armor.",
    "passive_modifiers": [{"type": "armor_bonus", "condition": "heavy_armor", "value": 10, "unit": "percent"}]
  },
  {
    "id": "warrior_battle_hardened",
    "class": "warrior",
    "name": "Battle Hardened",
    "effect": "5 health regeneration during combat (5 per turn).",
    "passive_modifiers": [{"type": "combat_regen", "resource": "hp", "value": 5, "per": "turn"}]
  },
  {
    "id": "rogue_evasion",
    "class": "rogue",
    "name": "Evasion",
    "effect": "+15% dodge chance.",
    "passive_modifiers": [{"type": "dodge_bonus", "value": 15, "unit": "percent"}]
  },
  {
    "id": "rogue_cunning_defense",
    "class": "rogue",
    "name": "Cunning Defense",
    "effect": "+10% chance to avoid critical hits.",
    "passive_modifiers": [{"type": "crit_avoidance", "value": 10, "unit": "percent"}]
  },
  {
    "id": "rogue_silent_steps",
    "class": "rogue",
    "name": "Silent Steps",
    "effect": "Lowers encounter/ambush rate.",
    "passive_modifiers": [{"type": "encounter_rate_reduction", "value": 15, "unit": "percent"}]
  },
  {
    "id": "rogue_thrust_mastery",
    "class": "rogue",
    "name": "Thrust Mastery",
    "effect": "+25% thrust (Thrust Weapon) damage.",
    "passive_modifiers": [{"type": "damage_bonus", "damage_type": "stab", "value": 25, "unit": "percent"}]
  },
  {
    "id": "rogue_quick_reflexes",
    "class": "rogue",
    "name": "Quick Reflexes",
    "effect": "+10% dodge chance after landing a hit.",
    "passive_modifiers": [{"type": "conditional_dodge", "trigger": "after_hit", "value": 10, "unit": "percent"}]
  },
  {
    "id": "mage_mana_efficiency",
    "class": "mage",
    "name": "Mana Efficiency",
    "effect": "Reduces spell mana cost by 10%.",
    "passive_modifiers": [{"type": "resource_cost_reduction", "resource": "mana", "value": 10, "unit": "percent"}]
  },
  {
    "id": "mage_arcane_knowledge",
    "class": "mage",
    "name": "Arcane Knowledge",
    "effect": "+5% spell damage for every 10 Intelligence.",
    "passive_modifiers": [{"type": "stat_scaling_damage", "stat": "intelligence", "value": 5, "per": 10, "unit": "percent"}]
  },
  {
    "id": "mage_elemental_resistance",
    "class": "mage",
    "name": "Elemental Resistance",
    "effect": "+10% resistance to chosen element.",
    "passive_modifiers": [{"type": "elemental_resistance", "value": 10, "unit": "percent", "choice_required": true}]
  },
  {
    "id": "mage_spell_reflect",
    "class": "mage",
    "name": "Spell Reflect",
    "effect": "5% chance to reflect damage.",
    "passive_modifiers": [{"type": "reflect_chance", "value": 5, "unit": "percent"}]
  },
  {
    "id": "mage_intelligent_casting",
    "class": "mage",
    "name": "Intelligent Casting",
    "effect": "+10% critical spell hit chance.",
    "passive_modifiers": [{"type": "spell_crit_bonus", "value": 10, "unit": "percent"}]
  },
  {
    "id": "ranger_keen_reflexes",
    "class": "ranger",
    "name": "Keen Reflexes",
    "effect": "+10% dodge chance.",
    "passive_modifiers": [{"type": "dodge_bonus", "value": 10, "unit": "percent"}]
  },
  {
    "id": "ranger_natures_companion",
    "class": "ranger",
    "name": "Nature's Companion",
    "effect": "Summon an Animal companion to aid you in battle. (Damage based on main stat). Only attacks one enemy per turn.",
    "passive_modifiers": [{"type": "passive_summon", "damage_scaling": "main_stat", "attacks_per_turn": 1}]
  },
  {
    "id": "ranger_marksmanship",
    "class": "ranger",
    "name": "Marksmanship",
    "effect": "Increases ranged attack damage by 25%.",
    "passive_modifiers": [{"type": "damage_bonus", "damage_type": "ranged", "value": 25, "unit": "percent"}]
  },
  {
    "id": "ranger_quick_reload",
    "class": "ranger",
    "name": "Quick Reload",
    "effect": "Allows the ranger to shoot an extra basic attack at the end of the turn.",
    "passive_modifiers": [{"type": "extra_attack", "timing": "end_of_turn", "attack_type": "basic"}]
  },
  {
    "id": "ranger_stealthy_hunter",
    "class": "ranger",
    "name": "Stealthy Hunter",
    "effect": "Increases damage dealt by the ranger's first attack against an enemy by 15%.",
    "passive_modifiers": [{"type": "first_strike_bonus", "value": 15, "unit": "percent"}]
  },
  {
    "id": "bard_inspiring_presence",
    "class": "bard",
    "name": "Inspiring Presence",
    "effect": "Increases the effectiveness of all buffs the bard applies by 50%.",
    "passive_modifiers": [{"type": "buff_effectiveness", "value": 50, "unit": "percent"}]
  },
  {
    "id": "bard_melodic_health",
    "class": "bard",
    "name": "Melodic Health",
    "effect": "Gain 5 HP for every buff cast in a turn.",
    "passive_modifiers": [{"type": "hp_on_buff_cast", "value": 5}]
  },
  {
    "id": "bard_charming_aura",
    "class": "bard",
    "name": "Charming Aura",
    "effect": "10% chance to charm one enemy at the start of a combat scenario for (based on main stat) turns.",
    "passive_modifiers": [{"type": "combat_start_charm", "chance": 10, "duration_rule": "main_stat"}]
  },
  {
    "id": "bard_quick_notes",
    "class": "bard",
    "name": "Quick Notes",
    "effect": "Gives the bard one additional action per turn. (extra attack, buff, skill for that turn)",
    "passive_modifiers": [{"type": "extra_action", "value": 1}]
  },
  {
    "id": "bard_fascinating_tunes",
    "class": "bard",
    "name": "Fascinating Tunes",
    "effect": "Increase the duration of any song effects by 1 turn.",
    "passive_modifiers": [{"type": "song_duration_bonus", "value": 1, "unit": "turns"}]
  },
  {
    "id": "cleric_divine_protection",
    "class": "cleric",
    "name": "Divine Protection",
    "effect": "Increases the effectiveness of healing spells by 25%.",
    "passive_modifiers": [{"type": "healing_bonus", "value": 25, "unit": "percent"}]
  },
  {
    "id": "cleric_sacred_resilience",
    "class": "cleric",
    "name": "Sacred Resilience",
    "effect": "Gain 20% damage resistance against enemies.",
    "passive_modifiers": [{"type": "damage_reduction", "value": 20, "unit": "percent"}]
  },
  {
    "id": "cleric_faithful_recovery",
    "class": "cleric",
    "name": "Faithful Recovery",
    "effect": "Automatically restores a small percentage of health (20%) at the start of each encounter.",
    "passive_modifiers": [{"type": "encounter_start_heal", "value": 20, "unit": "percent_max_hp"}]
  },
  {
    "id": "cleric_blessed_aura",
    "class": "cleric",
    "name": "Blessed Aura",
    "effect": "Naturally gives the cleric +3 strength. Increases +1 per 10 levels.",
    "passive_modifiers": [{"type": "flat_stat_bonus", "stat": "strength", "base_value": 3, "per_10_levels": 1}]
  },
  {
    "id": "cleric_holy_guidance",
    "class": "cleric",
    "name": "Holy Guidance",
    "effect": "Increases the cleric's blunt weapon damage by 10%.",
    "passive_modifiers": [{"type": "damage_bonus", "damage_type": "blunt", "value": 10, "unit": "percent"}]
  }
]
```

---

## 7. Static Data: weapons.json

All weapons from Section 6.3 of the design doc. Weapons are NOT class-restricted (class is a theme only). Rarity and damage are assigned at drop time, not in this table.

```json
[
  {"id": "long_sword", "name": "Long Sword", "class_theme": "warrior", "hand_type": "two_hand", "casting": false, "damage_type": "slash"},
  {"id": "battle_axe", "name": "Battle Axe", "class_theme": "warrior", "hand_type": "two_hand", "casting": false, "damage_type": "slash"},
  {"id": "shield", "name": "Shield", "class_theme": "warrior", "hand_type": "off_hand", "casting": false, "damage_type": "blunt"},
  {"id": "great_sword", "name": "Great Sword", "class_theme": "warrior", "hand_type": "two_hand", "casting": false, "damage_type": "slash"},
  {"id": "warrior_spear", "name": "Spear", "class_theme": "warrior", "hand_type": "two_hand", "casting": false, "damage_type": "stab"},
  {"id": "war_hammer", "name": "War Hammer", "class_theme": "warrior", "hand_type": "two_hand", "casting": false, "damage_type": "blunt"},
  {"id": "broadsword", "name": "Broadsword", "class_theme": "warrior", "hand_type": "one_hand", "casting": false, "damage_type": "slash"},
  {"id": "warrior_mace", "name": "Mace", "class_theme": "warrior", "hand_type": "one_hand", "casting": false, "damage_type": "blunt"},
  {"id": "glaive", "name": "Glaive", "class_theme": "warrior", "hand_type": "two_hand", "casting": false, "damage_type": "slash"},
  {"id": "halberd", "name": "Halberd", "class_theme": "warrior", "hand_type": "two_hand", "casting": false, "damage_type": "slash"},
  {"id": "spell_book", "name": "Spell Book", "class_theme": "mage", "hand_type": "off_hand", "casting": true, "damage_type": "spell"},
  {"id": "staff", "name": "Staff", "class_theme": "mage", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "wand", "name": "Wand", "class_theme": "mage", "hand_type": "off_hand", "casting": true, "damage_type": "spell"},
  {"id": "grimoire", "name": "Grimoire", "class_theme": "mage", "hand_type": "off_hand", "casting": true, "damage_type": "spell"},
  {"id": "crystal_orb", "name": "Crystal Orb", "class_theme": "mage", "hand_type": "off_hand", "casting": true, "damage_type": "spell"},
  {"id": "scepter", "name": "Scepter", "class_theme": "mage", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "spell_tome", "name": "Spell Tome", "class_theme": "mage", "hand_type": "off_hand", "casting": true, "damage_type": "spell"},
  {"id": "focus_rod", "name": "Focus Rod", "class_theme": "mage", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "arcane_blade", "name": "Arcane Blade", "class_theme": "mage", "hand_type": "one_hand", "casting": false, "damage_type": "slash"},
  {"id": "ritual_dagger", "name": "Ritual Dagger", "class_theme": "mage", "hand_type": "one_hand", "casting": false, "damage_type": "stab"},
  {"id": "longbow", "name": "Longbow", "class_theme": "ranger", "hand_type": "two_hand", "casting": false, "damage_type": "ranged"},
  {"id": "crossbow", "name": "Crossbow", "class_theme": "ranger", "hand_type": "two_hand", "casting": false, "damage_type": "ranged"},
  {"id": "ranger_short_sword", "name": "Short Sword", "class_theme": "ranger", "hand_type": "one_hand", "casting": false, "damage_type": "slash"},
  {"id": "hunting_knife", "name": "Hunting Knife", "class_theme": "ranger", "hand_type": "one_hand", "casting": false, "damage_type": "stab"},
  {"id": "compound_bow", "name": "Compound Bow", "class_theme": "ranger", "hand_type": "two_hand", "casting": false, "damage_type": "ranged"},
  {"id": "ranger_spear", "name": "Spear", "class_theme": "ranger", "hand_type": "two_hand", "casting": false, "damage_type": "stab"},
  {"id": "ranger_cestus", "name": "Cestus", "class_theme": "ranger", "hand_type": "one_hand", "casting": false, "damage_type": "blunt"},
  {"id": "handaxe", "name": "Handaxe", "class_theme": "ranger", "hand_type": "one_hand", "casting": false, "damage_type": "slash"},
  {"id": "recurve_bow", "name": "Recurve Bow", "class_theme": "ranger", "hand_type": "two_hand", "casting": false, "damage_type": "ranged"},
  {"id": "sling", "name": "Sling", "class_theme": "ranger", "hand_type": "one_hand", "casting": false, "damage_type": "blunt"},
  {"id": "dagger", "name": "Dagger", "class_theme": "rogue", "hand_type": "one_hand", "casting": false, "damage_type": "stab"},
  {"id": "rogue_short_sword", "name": "Short Sword", "class_theme": "rogue", "hand_type": "one_hand", "casting": false, "damage_type": "slash"},
  {"id": "rogue_cestus", "name": "Cestus", "class_theme": "rogue", "hand_type": "one_hand", "casting": false, "damage_type": "blunt"},
  {"id": "hand_crossbow", "name": "Hand Crossbow", "class_theme": "rogue", "hand_type": "one_hand", "casting": false, "damage_type": "ranged"},
  {"id": "stiletto", "name": "Stiletto", "class_theme": "rogue", "hand_type": "one_hand", "casting": false, "damage_type": "stab"},
  {"id": "dual_daggers", "name": "Dual Daggers", "class_theme": "rogue", "hand_type": "two_hand", "casting": false, "damage_type": "stab"},
  {"id": "spiked_knuckles", "name": "Spiked Knuckles", "class_theme": "rogue", "hand_type": "two_hand", "casting": false, "damage_type": "blunt"},
  {"id": "letter_opener", "name": "Letter Opener", "class_theme": "rogue", "hand_type": "one_hand", "casting": false, "damage_type": "stab"},
  {"id": "whip", "name": "Whip", "class_theme": "rogue", "hand_type": "one_hand", "casting": false, "damage_type": "slash"},
  {"id": "lute", "name": "Lute", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "flute", "name": "Flute", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "rapier", "name": "Rapier", "class_theme": "bard", "hand_type": "one_hand", "casting": false, "damage_type": "stab"},
  {"id": "hand_drum", "name": "Hand Drum", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "mandolin", "name": "Mandolin", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "violin", "name": "Violin", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "pan_flute", "name": "Pan Flute", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "horn", "name": "Horn", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "castanets", "name": "Castanets", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "tambourine", "name": "Tambourine", "class_theme": "bard", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "cleric_mace", "name": "Mace", "class_theme": "cleric", "hand_type": "one_hand", "casting": false, "damage_type": "blunt"},
  {"id": "holy_symbol", "name": "Holy Symbol", "class_theme": "cleric", "hand_type": "off_hand", "casting": true, "damage_type": "spell"},
  {"id": "warhammer", "name": "Warhammer", "class_theme": "cleric", "hand_type": "two_hand", "casting": false, "damage_type": "blunt"},
  {"id": "staff_of_healing", "name": "Staff of Healing", "class_theme": "cleric", "hand_type": "two_hand", "casting": true, "damage_type": "spell"},
  {"id": "blessed_dagger", "name": "Blessed Dagger", "class_theme": "cleric", "hand_type": "off_hand", "casting": true, "damage_type": "spell"},
  {"id": "censer", "name": "Censer", "class_theme": "cleric", "hand_type": "off_hand", "casting": true, "damage_type": "spell"},
  {"id": "cleric_shield", "name": "Shield", "class_theme": "cleric", "hand_type": "off_hand", "casting": false, "damage_type": "blunt"},
  {"id": "spiked_club", "name": "Spiked Club", "class_theme": "cleric", "hand_type": "one_hand", "casting": false, "damage_type": "blunt"},
  {"id": "battle_staff", "name": "Battle Staff", "class_theme": "cleric", "hand_type": "two_hand", "casting": false, "damage_type": "blunt"},
  {"id": "rod_of_faith", "name": "Rod of Faith", "class_theme": "cleric", "hand_type": "two_hand", "casting": true, "damage_type": "spell"}
]
```

### Weapon Rarity Damage Ranges (used at generation time)

| Rarity | Damage Min | Damage Max |
|---|---|---|
| poor | 3 | 11 |
| common | 9 | 16 |
| uncommon | 13 | 21 |
| rare | 18 | 26 |
| epic | 23 | 31 |
| legendary | 28 | 36 |

### Weapon Drop Chances

| Rarity | Chance |
|---|---|
| poor | 50.9% |
| common | 30% |
| uncommon | 10% |
| rare | 5% |
| epic | 4% |
| legendary | 0.1% |

### Weapon Stat Affix Rules (applied at generation time)

| Rarity | Number of Stats | Multipliers |
|---|---|---|
| poor | 0 | -- |
| common | 0 | -- |
| uncommon | 1 | +1 base |
| rare | 2 | 2x main, 1x secondary |
| epic | 3 | 3x main, 2x secondary, 1x third |
| legendary | 3 | 3x main, 3x secondary, 2x third |

Floor scaling: base increases by +1 every 5 floors (floors 1-5: +1, floors 6-10: +2, etc.)

---

## 8. Static Data: armor.json

Full armor catalog from Sections 7.1-7.4 of the design doc. Every single armor item is listed below.

### Armor Rarity Multipliers (applied to AR at generation time)

| Rarity | Multiplier Min | Multiplier Max |
|---|---|---|
| common | 1.1 | 1.5 |
| uncommon | 1.5 | 2.0 |
| rare | 2.0 | 2.5 |
| epic | 2.5 | 3.0 |
| legendary | 3.0 | 5.0 |

### Max Armor Rating by Slot

| Slot | Max AR |
|---|---|
| head | 100 |
| shoulders | 90 |
| chest | 110 |
| gloves | 80 |
| legs | 90 |
| feet | 80 |

### Armor Damage Reduction Formula

```
damage_reduction_percent = (total_AR / (total_AR + 500)) * 100
```

### Armor Stat Affix Rules (same as weapons)

Same affix table as weapons (Section 7).

### Complete Armor List

```json
[
  {"id": "enchanted_hood", "name": "Enchanted Hood", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard", "cleric"]},
  {"id": "mystic_circlet", "name": "Mystic Circlet", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard", "cleric"]},
  {"id": "arcane_cap", "name": "Arcane Cap", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard"]},
  {"id": "sorcerers_hat", "name": "Sorcerer's Hat", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard"]},
  {"id": "spellweavers_tiara", "name": "Spellweaver's Tiara", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard"]},
  {"id": "holy_circlet", "name": "Holy Circlet", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "sacred_hood", "name": "Sacred Hood", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "divine_cap", "name": "Divine Cap", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "priests_veil", "name": "Priest's Veil", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "blessed_headpiece", "name": "Blessed Headpiece", "armor_type": "cloth", "slot": "head", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric", "mage"]},
  {"id": "mystic_shoulders", "name": "Mystic Shoulders", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard"]},
  {"id": "robes_of_the_arcane", "name": "Robes of the Arcane", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage"]},
  {"id": "spellcasters_mantle", "name": "Spellcaster's Mantle", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard"]},
  {"id": "arcane_cloak", "name": "Arcane Cloak", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard"]},
  {"id": "elders_shawl", "name": "Elder's Shawl", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["mage", "bard"]},
  {"id": "blessed_mantle", "name": "Blessed Mantle", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "sacred_shawl", "name": "Sacred Shawl", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "divine_shoulders", "name": "Divine Shoulders", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "holy_cloak", "name": "Holy Cloak", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "priests_epaulets", "name": "Priest's Epaulets", "armor_type": "cloth", "slot": "shoulders", "ar_min": 1, "ar_max": 6, "allowed_classes": ["cleric"]},
  {"id": "robe_of_the_arcane", "name": "Robe of the Arcane", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["mage"]},
  {"id": "elemental_robe", "name": "Elemental Robe", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["mage"]},
  {"id": "enchanted_tunic", "name": "Enchanted Tunic", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["mage", "bard"]},
  {"id": "sorcerers_garb", "name": "Sorcerer's Garb", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["mage"]},
  {"id": "arcane_vestments", "name": "Arcane Vestments", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["mage", "bard"]},
  {"id": "divine_robe", "name": "Divine Robe", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["cleric"]},
  {"id": "priests_tunic", "name": "Priest's Tunic", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["cleric"]},
  {"id": "sacred_garb", "name": "Sacred Garb", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["cleric"]},
  {"id": "holy_vestments", "name": "Holy Vestments", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["cleric"]},
  {"id": "blessed_armor_cloth", "name": "Blessed Armor", "armor_type": "cloth", "slot": "chest", "ar_min": 1, "ar_max": 8, "allowed_classes": ["cleric"]},
  {"id": "spellweavers_gloves", "name": "Spellweaver's Gloves", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage", "bard"]},
  {"id": "arcane_handwraps", "name": "Arcane Handwraps", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage"]},
  {"id": "enchanted_gloves", "name": "Enchanted Gloves", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage", "bard"]},
  {"id": "mystic_grips", "name": "Mystic Grips", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage", "bard"]},
  {"id": "wizards_mitts", "name": "Wizard's Mitts", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage"]},
  {"id": "healing_gloves", "name": "Healing Gloves", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric"]},
  {"id": "sacred_handwraps", "name": "Sacred Handwraps", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric", "mage"]},
  {"id": "priests_mitts", "name": "Priest's Mitts", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric"]},
  {"id": "divine_grips", "name": "Divine Grips", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric"]},
  {"id": "holy_gauntlets_cloth", "name": "Holy Gauntlets", "armor_type": "cloth", "slot": "gloves", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric"]},
  {"id": "cloth_trousers", "name": "Cloth Trousers", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["mage", "warrior"]},
  {"id": "arcane_leggings", "name": "Arcane Leggings", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["mage"]},
  {"id": "slacks_of_casting", "name": "Slacks of Casting", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["mage"]},
  {"id": "enchanted_skirt", "name": "Enchanted Skirt", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["mage", "bard"]},
  {"id": "sorcerers_pants", "name": "Sorcerer's Pants", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["mage"]},
  {"id": "prayer_skirt", "name": "Prayer Skirt", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["cleric"]},
  {"id": "holy_trousers", "name": "Holy Trousers", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["cleric"]},
  {"id": "divine_leggings", "name": "Divine Leggings", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["cleric"]},
  {"id": "blessed_slacks", "name": "Blessed Slacks", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["cleric", "mage"]},
  {"id": "sacred_pants", "name": "Sacred Pants", "armor_type": "cloth", "slot": "legs", "ar_min": 1, "ar_max": 7, "allowed_classes": ["cleric"]},
  {"id": "soft_slippers", "name": "Soft Slippers", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage", "bard"]},
  {"id": "enchanted_footwraps", "name": "Enchanted Footwraps", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage", "bard"]},
  {"id": "mystic_boots", "name": "Mystic Boots", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage", "bard"]},
  {"id": "spellcasters_shoes", "name": "Spellcaster's Shoes", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage", "bard"]},
  {"id": "wizards_sandals", "name": "Wizard's Sandals", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["mage"]},
  {"id": "sturdy_sandals", "name": "Sturdy Sandals", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric", "mage"]},
  {"id": "priest_shoes", "name": "Priest Shoes", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric"]},
  {"id": "divine_footwear", "name": "Divine Footwear", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric"]},
  {"id": "holy_boots", "name": "Holy Boots", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric"]},
  {"id": "blessed_slippers", "name": "Blessed Slippers", "armor_type": "cloth", "slot": "feet", "ar_min": 1, "ar_max": 5, "allowed_classes": ["cleric", "mage"]},
  {"id": "shadow_hood", "name": "Shadow Hood", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue", "ranger"]},
  {"id": "leather_cap", "name": "Leather Cap", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue", "ranger", "bard", "warrior"]},
  {"id": "thiefs_mask", "name": "Thief's Mask", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue"]},
  {"id": "dark_cowl", "name": "Dark Cowl", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue"]},
  {"id": "assassins_veil", "name": "Assassin's Veil", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue"]},
  {"id": "camouflage_cap", "name": "Camouflage Cap", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger", "rogue"]},
  {"id": "hunters_hood", "name": "Hunter's Hood", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger"]},
  {"id": "leather_headband", "name": "Leather Headband", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger", "bard", "warrior"]},
  {"id": "beaver_hat", "name": "Beaver Hat", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger", "rogue", "warrior"]},
  {"id": "woodland_crown", "name": "Woodland Crown", "armor_type": "leather", "slot": "head", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger"]},
  {"id": "leather_epaulettes", "name": "Leather Epaulettes", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue", "ranger", "bard", "warrior"]},
  {"id": "shadow_cloak", "name": "Shadow Cloak", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue"]},
  {"id": "midnight_mantle", "name": "Midnight Mantle", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue"]},
  {"id": "light_shoulder_armor", "name": "Light Shoulder Armor", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue", "ranger", "warrior"]},
  {"id": "daggerwing_shoulders", "name": "Daggerwing Shoulders", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["rogue"]},
  {"id": "hunters_shoulders", "name": "Hunter's Shoulders", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger"]},
  {"id": "leather_shoulder_armor", "name": "Leather Shoulder Armor", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger", "bard", "warrior"]},
  {"id": "eagle_cloak", "name": "Eagle Cloak", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger", "rogue", "warrior"]},
  {"id": "woodland_epaulets", "name": "Woodland Epaulets", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger"]},
  {"id": "natures_mantle", "name": "Nature's Mantle", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["ranger"]},
  {"id": "capes_of_melody", "name": "Capes of Melody", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["bard"]},
  {"id": "poetic_epaulets", "name": "Poetic Epaulets", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["bard"]},
  {"id": "harmonious_shawl", "name": "Harmonious Shawl", "armor_type": "leather", "slot": "shoulders", "ar_min": 7, "ar_max": 13, "allowed_classes": ["bard", "cleric"]},
  {"id": "leather_tunic", "name": "Leather Tunic", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["rogue", "ranger", "bard", "warrior"]},
  {"id": "stealth_vest", "name": "Stealth Vest", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["rogue", "ranger"]},
  {"id": "shadow_armor", "name": "Shadow Armor", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["rogue"]},
  {"id": "weightless_garb", "name": "Weightless Garb", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["rogue"]},
  {"id": "black_leather_shirt", "name": "Black Leather Shirt", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["rogue", "ranger"]},
  {"id": "quick_leather_vest", "name": "Quick Leather Vest", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["ranger", "rogue", "warrior"]},
  {"id": "bear_tunic", "name": "Bear Tunic", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["ranger", "rogue", "warrior"]},
  {"id": "leather_armor", "name": "Leather Armor", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["ranger", "bard", "rogue"]},
  {"id": "woodland_jacket", "name": "Woodland Jacket", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["ranger"]},
  {"id": "hunters_garb", "name": "Hunter's Garb", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["ranger"]},
  {"id": "harmonious_tunic", "name": "Harmonious Tunic", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["bard"]},
  {"id": "lyrical_robe", "name": "Lyrical Robe", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["bard"]},
  {"id": "enchanted_blouse", "name": "Enchanted Blouse", "armor_type": "leather", "slot": "chest", "ar_min": 9, "ar_max": 16, "allowed_classes": ["bard", "mage"]},
  {"id": "silent_handwraps", "name": "Silent Handwraps", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue", "ranger"]},
  {"id": "leather_gloves", "name": "Leather Gloves", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue", "ranger", "bard"]},
  {"id": "thiefs_grips", "name": "Thief's Grips", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue"]},
  {"id": "shadowy_gauntlets", "name": "Shadowy Gauntlets", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue"]},
  {"id": "dexterity_gloves", "name": "Dexterity Gloves", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue", "ranger"]},
  {"id": "hunters_gloves", "name": "Hunter's Gloves", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger"]},
  {"id": "leather_grips", "name": "Leather Grips", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger", "rogue"]},
  {"id": "archery_gloves", "name": "Archery Gloves", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger"]},
  {"id": "dexterity_gauntlets", "name": "Dexterity Gauntlets", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger", "rogue"]},
  {"id": "musicians_gloves", "name": "Musicians' Gloves", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["bard"]},
  {"id": "melodic_mitts", "name": "Melodic Mitts", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["bard"]},
  {"id": "lyrical_grips", "name": "Lyrical Grips", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["bard"]},
  {"id": "performers_gloves", "name": "Performer's Gloves", "armor_type": "leather", "slot": "gloves", "ar_min": 6, "ar_max": 10, "allowed_classes": ["bard"]},
  {"id": "agile_pants", "name": "Agile Pants", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["ranger"]},
  {"id": "shadow_trousers", "name": "Shadow Trousers", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["rogue"]},
  {"id": "leather_leggings", "name": "Leather Leggings", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["rogue", "ranger", "bard"]},
  {"id": "dark_pants", "name": "Dark Pants", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["rogue", "ranger"]},
  {"id": "stealthy_slacks", "name": "Stealthy Slacks", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["rogue", "ranger"]},
  {"id": "sturdy_trousers", "name": "Sturdy Trousers", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["ranger", "bard", "warrior"]},
  {"id": "wolf_leggings", "name": "Wolf Leggings", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["ranger", "rogue"]},
  {"id": "leather_pants", "name": "Leather Pants", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["ranger", "bard"]},
  {"id": "elegant_trousers", "name": "Elegant Trousers", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["bard"]},
  {"id": "lyrical_pants", "name": "Lyrical Pants", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["bard"]},
  {"id": "musical_slacks", "name": "Musical Slacks", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["bard"]},
  {"id": "harmonious_skirt", "name": "Harmonious Skirt", "armor_type": "leather", "slot": "legs", "ar_min": 8, "ar_max": 13, "allowed_classes": ["bard"]},
  {"id": "softfoot_boots", "name": "Softfoot Boots", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue", "ranger", "mage"]},
  {"id": "leather_shoes", "name": "Leather Shoes", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue", "ranger", "bard", "mage"]},
  {"id": "shadowy_footwraps", "name": "Shadowy Footwraps", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue"]},
  {"id": "silent_treads", "name": "Silent Treads", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue", "ranger"]},
  {"id": "assassins_footwear", "name": "Assassin's Footwear", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["rogue"]},
  {"id": "travel_boots", "name": "Travel Boots", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger", "rogue", "mage", "warrior"]},
  {"id": "sturdy_leather_boots", "name": "Sturdy Leather Boots", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger", "rogue"]},
  {"id": "bandit_footwear", "name": "Bandit Footwear", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger", "rogue"]},
  {"id": "camouflage_shoes", "name": "Camouflage Shoes", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger"]},
  {"id": "woodland_sandals", "name": "Woodland Sandals", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["ranger"]},
  {"id": "dance_shoes", "name": "Dance Shoes", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["bard"]},
  {"id": "harmony_sandals", "name": "Harmony Sandals", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["bard"]},
  {"id": "graceful_slippers", "name": "Graceful Slippers", "armor_type": "leather", "slot": "feet", "ar_min": 6, "ar_max": 10, "allowed_classes": ["bard", "mage"]},
  {"id": "iron_helm", "name": "Iron Helm", "armor_type": "heavy", "slot": "head", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior", "cleric", "ranger"]},
  {"id": "steel_battle_helm", "name": "Steel Battle Helm", "armor_type": "heavy", "slot": "head", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior", "cleric", "ranger"]},
  {"id": "horned_helmet", "name": "Horned Helmet", "armor_type": "heavy", "slot": "head", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior", "ranger"]},
  {"id": "spiked_helm", "name": "Spiked Helm", "armor_type": "heavy", "slot": "head", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior", "rogue", "ranger"]},
  {"id": "crest_of_valor", "name": "Crest of Valor", "armor_type": "heavy", "slot": "head", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior", "cleric"]},
  {"id": "steel_pauldrons", "name": "Steel Pauldrons", "armor_type": "heavy", "slot": "shoulders", "ar_min": 14, "ar_max": 18, "allowed_classes": ["warrior", "cleric"]},
  {"id": "spiked_shoulder_guards", "name": "Spiked Shoulder Guards", "armor_type": "heavy", "slot": "shoulders", "ar_min": 14, "ar_max": 18, "allowed_classes": ["warrior", "rogue", "ranger"]},
  {"id": "heavy_shoulder_plates", "name": "Heavy Shoulder Plates", "armor_type": "heavy", "slot": "shoulders", "ar_min": 14, "ar_max": 18, "allowed_classes": ["warrior", "cleric"]},
  {"id": "iron_epaulets", "name": "Iron Epaulets", "armor_type": "heavy", "slot": "shoulders", "ar_min": 14, "ar_max": 18, "allowed_classes": ["warrior", "cleric"]},
  {"id": "guardian_mantle", "name": "Guardian Mantle", "armor_type": "heavy", "slot": "shoulders", "ar_min": 14, "ar_max": 18, "allowed_classes": ["warrior", "cleric"]},
  {"id": "plate_mail", "name": "Plate Mail", "armor_type": "heavy", "slot": "chest", "ar_min": 17, "ar_max": 25, "allowed_classes": ["warrior", "cleric"]},
  {"id": "iron_breastplate", "name": "Iron Breastplate", "armor_type": "heavy", "slot": "chest", "ar_min": 17, "ar_max": 25, "allowed_classes": ["warrior", "cleric"]},
  {"id": "steel_chestplate", "name": "Steel Chestplate", "armor_type": "heavy", "slot": "chest", "ar_min": 17, "ar_max": 25, "allowed_classes": ["warrior", "cleric"]},
  {"id": "worn_cuirass", "name": "Worn Cuirass", "armor_type": "heavy", "slot": "chest", "ar_min": 17, "ar_max": 25, "allowed_classes": ["warrior", "cleric"]},
  {"id": "battle_harness", "name": "Battle Harness", "armor_type": "heavy", "slot": "chest", "ar_min": 17, "ar_max": 25, "allowed_classes": ["warrior"]},
  {"id": "reinforced_gauntlets", "name": "Reinforced Gauntlets", "armor_type": "heavy", "slot": "gloves", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior", "cleric"]},
  {"id": "iron_fist_wraps", "name": "Iron Fist Wraps", "armor_type": "heavy", "slot": "gloves", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior"]},
  {"id": "heavy_leather_gloves", "name": "Heavy Leather Gloves", "armor_type": "heavy", "slot": "gloves", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior"]},
  {"id": "steel_gauntlets", "name": "Steel Gauntlets", "armor_type": "heavy", "slot": "gloves", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior", "cleric"]},
  {"id": "sturdy_iron_grips", "name": "Sturdy Iron Grips", "armor_type": "heavy", "slot": "gloves", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior"]},
  {"id": "steel_leggings", "name": "Steel Leggings", "armor_type": "heavy", "slot": "legs", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior"]},
  {"id": "iron_greaves", "name": "Iron Greaves", "armor_type": "heavy", "slot": "legs", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior", "cleric"]},
  {"id": "heavy_trousers", "name": "Heavy Trousers", "armor_type": "heavy", "slot": "legs", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior"]},
  {"id": "battle_leggings", "name": "Battle Leggings", "armor_type": "heavy", "slot": "legs", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior"]},
  {"id": "worn_plate_legs", "name": "Worn Plate Legs", "armor_type": "heavy", "slot": "legs", "ar_min": 14, "ar_max": 20, "allowed_classes": ["warrior"]},
  {"id": "heavy_boots", "name": "Heavy Boots", "armor_type": "heavy", "slot": "feet", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior"]},
  {"id": "iron_footguards", "name": "Iron Footguards", "armor_type": "heavy", "slot": "feet", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior"]},
  {"id": "steel_sabatons", "name": "Steel Sabatons", "armor_type": "heavy", "slot": "feet", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior"]},
  {"id": "sturdy_battle_boots", "name": "Sturdy Battle Boots", "armor_type": "heavy", "slot": "feet", "ar_min": 11, "ar_max": 15, "allowed_classes": ["warrior"]}
]
```

**Total armor count: 147 items** (60 Cloth + 56 Leather + 31 Heavy)

---

## 9. Static Data: consumables.json

```json
[
  {"id": "minor_healing_potion", "name": "Minor Healing Potion", "category": "healing", "effect": "Restores 10 HP.", "resource": "hp", "value": 10, "status_effect": null, "duration": null, "encounter_limit": null},
  {"id": "herbal_remedy", "name": "Herbal Remedy", "category": "healing", "effect": "Restores 15 HP and removes minor ailments (like poison).", "resource": "hp", "value": 15, "status_effect": {"type": "cleanse", "removes": ["poison"]}, "duration": null, "encounter_limit": null},
  {"id": "elixir_of_vitality", "name": "Elixir of Vitality", "category": "healing", "effect": "Restores 25 HP and increases maximum HP temporarily by 5 for the duration of a battle.", "resource": "hp", "value": 25, "status_effect": {"type": "max_hp_up", "value": 5}, "duration": "combat", "encounter_limit": null},
  {"id": "revitalizing_salve", "name": "Revitalizing Salve", "category": "healing", "effect": "Restores 20 HP and heals for an additional 5 HP over 3 turns.", "resource": "hp", "value": 20, "status_effect": {"type": "heal_over_time", "value": 5, "duration": 3}, "duration": null, "encounter_limit": null},
  {"id": "healing_fruit", "name": "Healing Fruit", "category": "healing", "effect": "Restores 12 HP. Can be eaten once per encounter. Lasts 3 encounters.", "resource": "hp", "value": 12, "status_effect": null, "duration": null, "encounter_limit": {"per_encounter": 1, "total_encounters": 3}},
  {"id": "mana_potion", "name": "Mana Potion", "category": "mana", "effect": "Restores 10 Mana.", "resource": "mana", "value": 10, "status_effect": null, "duration": null, "encounter_limit": null},
  {"id": "arcane_elixir", "name": "Arcane Elixir", "category": "mana", "effect": "Restores 20 Mana and enhances spell damage by 10% for the next spell cast.", "resource": "mana", "value": 20, "status_effect": {"type": "spell_damage_up", "value": 10, "unit": "percent", "uses": 1}, "duration": null, "encounter_limit": null},
  {"id": "essence_of_magic", "name": "Essence of Magic", "category": "mana", "effect": "Restores 15 Mana and grants a 5% chance to regain 5 Mana on spell cast for the next turn.", "resource": "mana", "value": 15, "status_effect": {"type": "mana_on_cast", "chance": 5, "value": 5, "duration": 1}, "duration": null, "encounter_limit": null},
  {"id": "crystalline_focus", "name": "Crystalline Focus", "category": "mana", "effect": "Restores 25 Mana but causes a temporary reduction of 5% to spellcasting speed for the next turn.", "resource": "mana", "value": 25, "status_effect": {"type": "cast_speed_down", "value": 5, "unit": "percent", "duration": 1}, "duration": null, "encounter_limit": null},
  {"id": "sorcerers_snack", "name": "Sorcerer's Snack", "category": "mana", "effect": "Restores 10 Mana and provides a one-time boost to spell effectiveness by 5% for the next spell.", "resource": "mana", "value": 10, "status_effect": {"type": "spell_effectiveness_up", "value": 5, "unit": "percent", "uses": 1}, "duration": null, "encounter_limit": null},
  {"id": "stamina_tonic", "name": "Stamina Tonic", "category": "sp", "effect": "Restores 10 SP.", "resource": "sp", "value": 10, "status_effect": null, "duration": null, "encounter_limit": null},
  {"id": "energizing_elixir", "name": "Energizing Elixir", "category": "sp", "effect": "Restores 15 SP and provides a 10% chance to regain an additional 5 SP after a successful action.", "resource": "sp", "value": 15, "status_effect": {"type": "sp_on_action", "chance": 10, "value": 5, "duration": 1}, "duration": null, "encounter_limit": null},
  {"id": "rejuvenating_tea", "name": "Rejuvenating Tea", "category": "sp", "effect": "Restores 20 SP and grants a temporary 5 SP increase to maximum SP for the next encounter.", "resource": "sp", "value": 20, "status_effect": {"type": "max_sp_up", "value": 5}, "duration": "next_encounter", "encounter_limit": null},
  {"id": "warriors_ration", "name": "Warrior's Ration", "category": "sp", "effect": "Restores 12 SP and boosts attack power by 5% for the next turn.", "resource": "sp", "value": 12, "status_effect": {"type": "attack_up", "value": 5, "unit": "percent", "duration": 1}, "duration": null, "encounter_limit": null},
  {"id": "filling_meal", "name": "Filling Meal", "category": "sp", "effect": "Restores 25 SP but skips turn.", "resource": "sp", "value": 25, "status_effect": {"type": "skip_turn"}, "duration": null, "encounter_limit": null}
]
```

---

## 10. Static Data: enemies.json

Levels 1-20 scaling for both enemy types.

```json
[
  {"type": "goblin", "level": 1, "damage_min": 12, "damage_max": 16, "hp": 30, "xp_reward": 30},
  {"type": "goblin", "level": 2, "damage_min": 14, "damage_max": 18, "hp": 35, "xp_reward": 35},
  {"type": "goblin", "level": 3, "damage_min": 16, "damage_max": 20, "hp": 40, "xp_reward": 40},
  {"type": "goblin", "level": 4, "damage_min": 18, "damage_max": 22, "hp": 45, "xp_reward": 50},
  {"type": "goblin", "level": 5, "damage_min": 20, "damage_max": 24, "hp": 50, "xp_reward": 60},
  {"type": "goblin", "level": 6, "damage_min": 22, "damage_max": 26, "hp": 60, "xp_reward": 70},
  {"type": "goblin", "level": 7, "damage_min": 24, "damage_max": 28, "hp": 70, "xp_reward": 80},
  {"type": "goblin", "level": 8, "damage_min": 26, "damage_max": 30, "hp": 80, "xp_reward": 90},
  {"type": "goblin", "level": 9, "damage_min": 28, "damage_max": 32, "hp": 90, "xp_reward": 100},
  {"type": "goblin", "level": 10, "damage_min": 30, "damage_max": 34, "hp": 100, "xp_reward": 110},
  {"type": "goblin", "level": 11, "damage_min": 32, "damage_max": 36, "hp": 110, "xp_reward": 130},
  {"type": "goblin", "level": 12, "damage_min": 34, "damage_max": 38, "hp": 120, "xp_reward": 140},
  {"type": "goblin", "level": 13, "damage_min": 36, "damage_max": 40, "hp": 130, "xp_reward": 150},
  {"type": "goblin", "level": 14, "damage_min": 38, "damage_max": 42, "hp": 140, "xp_reward": 160},
  {"type": "goblin", "level": 15, "damage_min": 40, "damage_max": 44, "hp": 150, "xp_reward": 170},
  {"type": "goblin", "level": 16, "damage_min": 42, "damage_max": 46, "hp": 160, "xp_reward": 180},
  {"type": "goblin", "level": 17, "damage_min": 44, "damage_max": 48, "hp": 175, "xp_reward": 190},
  {"type": "goblin", "level": 18, "damage_min": 46, "damage_max": 50, "hp": 190, "xp_reward": 200},
  {"type": "goblin", "level": 19, "damage_min": 48, "damage_max": 52, "hp": 205, "xp_reward": 210},
  {"type": "goblin", "level": 20, "damage_min": 50, "damage_max": 54, "hp": 220, "xp_reward": 250},
  {"type": "feral_rat", "level": 1, "damage_min": 0, "damage_max": 2, "hp": 30, "xp_reward": 20},
  {"type": "feral_rat", "level": 2, "damage_min": 2, "damage_max": 4, "hp": 32, "xp_reward": 25},
  {"type": "feral_rat", "level": 3, "damage_min": 4, "damage_max": 6, "hp": 35, "xp_reward": 30},
  {"type": "feral_rat", "level": 4, "damage_min": 6, "damage_max": 8, "hp": 37, "xp_reward": 40},
  {"type": "feral_rat", "level": 5, "damage_min": 8, "damage_max": 10, "hp": 40, "xp_reward": 50},
  {"type": "feral_rat", "level": 6, "damage_min": 10, "damage_max": 12, "hp": 45, "xp_reward": 60},
  {"type": "feral_rat", "level": 7, "damage_min": 12, "damage_max": 14, "hp": 50, "xp_reward": 70},
  {"type": "feral_rat", "level": 8, "damage_min": 14, "damage_max": 16, "hp": 55, "xp_reward": 80},
  {"type": "feral_rat", "level": 9, "damage_min": 16, "damage_max": 18, "hp": 60, "xp_reward": 90},
  {"type": "feral_rat", "level": 10, "damage_min": 18, "damage_max": 20, "hp": 65, "xp_reward": 100},
  {"type": "feral_rat", "level": 11, "damage_min": 20, "damage_max": 22, "hp": 70, "xp_reward": 120},
  {"type": "feral_rat", "level": 12, "damage_min": 22, "damage_max": 24, "hp": 75, "xp_reward": 130},
  {"type": "feral_rat", "level": 13, "damage_min": 24, "damage_max": 26, "hp": 80, "xp_reward": 140},
  {"type": "feral_rat", "level": 14, "damage_min": 26, "damage_max": 28, "hp": 85, "xp_reward": 150},
  {"type": "feral_rat", "level": 15, "damage_min": 28, "damage_max": 30, "hp": 90, "xp_reward": 160},
  {"type": "feral_rat", "level": 16, "damage_min": 30, "damage_max": 32, "hp": 95, "xp_reward": 170},
  {"type": "feral_rat", "level": 17, "damage_min": 32, "damage_max": 35, "hp": 100, "xp_reward": 180},
  {"type": "feral_rat", "level": 18, "damage_min": 35, "damage_max": 38, "hp": 105, "xp_reward": 190},
  {"type": "feral_rat", "level": 19, "damage_min": 38, "damage_max": 41, "hp": 110, "xp_reward": 200},
  {"type": "feral_rat", "level": 20, "damage_min": 41, "damage_max": 44, "hp": 110, "xp_reward": 250}
]
```

---

## 11. Static Data: loot_tables.json

Enemy-specific drops from Section 5.2 of the design doc.

```json
{
  "goblin": [
    {"id": "small_pouch_of_coins", "name": "Small Pouch of Coins", "type": "valuable", "gold_min": 10, "gold_max": 25, "description": "A little leather pouch filled with a handful of coins."},
    {"id": "goblin_crafted_trinket", "name": "Goblin-Crafted Trinket", "type": "valuable", "gold_min": 5, "gold_max": 10, "description": "A crude necklace or ring made of bone or metal scraps."},
    {"id": "rotten_meat_rations", "name": "Rotten Meat Rations", "type": "usable", "effect": "Restores 5 HP; 20% chance to cause illness, reducing stats by -1 for 2 turns.", "resource": "hp", "value": 5, "risk": {"type": "illness", "chance": 20, "stat_penalty": -1, "duration": 2}, "description": "Goblins aren't picky about their food, but their rations are barely edible."},
    {"id": "shiny_pebble", "name": "Shiny Pebble", "type": "valuable", "gold_min": 1, "gold_max": 1, "description": "Goblins love shiny things. It has no real value but can be traded for a few coins."},
    {"id": "cracked_health_potion", "name": "Cracked Health Potion", "type": "usable", "effect": "Restores 10 HP.", "resource": "hp", "value": 10, "description": "A poorly maintained health potion in a cracked glass bottle."}
  ],
  "feral_rat": [
    {"id": "rat_pelts", "name": "Rat Pelts", "type": "valuable", "gold_min": 2, "gold_max": 5, "description": "A small, tattered pelt from a feral rat."},
    {"id": "sharp_rat_teeth", "name": "Sharp Rat Teeth", "type": "crafting", "effect": "Can be crafted into crude jewelry or used as ingredients in some basic potions.", "description": "Broken-off teeth from a feral rat, sharp enough to be repurposed."},
    {"id": "disease_infested_tail", "name": "Disease-Infested Tail", "type": "crafting", "gold_min": 3, "gold_max": 7, "effect": "Ingredient for poisons or curses. Can be sold for 3-7 Gold.", "description": "A foul, diseased rat tail. Too dangerous to eat, but some potion makers may have a use for it."}
  ]
}
```

---

## 12. Static Data: xp_thresholds.json

```json
[
  {"level": 1, "total_xp_needed": 100},
  {"level": 2, "total_xp_needed": 250},
  {"level": 3, "total_xp_needed": 500},
  {"level": 4, "total_xp_needed": 1000},
  {"level": 5, "total_xp_needed": 1500},
  {"level": 6, "total_xp_needed": 2000},
  {"level": 7, "total_xp_needed": 2500},
  {"level": 8, "total_xp_needed": 3500},
  {"level": 9, "total_xp_needed": 4500},
  {"level": 10, "total_xp_needed": 5500},
  {"level": 11, "total_xp_needed": 7000},
  {"level": 12, "total_xp_needed": 8500},
  {"level": 13, "total_xp_needed": 10000},
  {"level": 14, "total_xp_needed": 12000},
  {"level": 15, "total_xp_needed": 14000},
  {"level": 16, "total_xp_needed": 16500},
  {"level": 17, "total_xp_needed": 19000},
  {"level": 18, "total_xp_needed": 22000},
  {"level": 19, "total_xp_needed": 25000},
  {"level": 20, "total_xp_needed": 28000}
]
```

---

## 13. Static Data: classes.json

Starting stats, main stat mapping, base resources, and class identity.

```json
[
  {
    "id": "warrior",
    "name": "Warrior",
    "description": "A powerful melee fighter who excels in close combat with heavy weapons and armor.",
    "main_stat": "strength",
    "resource": "sp",
    "starting_stats": {
      "strength": 8, "dexterity": 4, "intelligence": 3, "agility": 5,
      "wisdom": 3, "endurance": 8, "charisma": 4
    },
    "base_hp": 100, "base_mana": 50, "base_sp": 30
  },
  {
    "id": "rogue",
    "name": "Rogue",
    "description": "A stealthy fighter who uses speed and cunning to deal devastating damage from the shadows.",
    "main_stat": "dexterity",
    "resource": "sp",
    "starting_stats": {
      "strength": 4, "dexterity": 8, "intelligence": 3, "agility": 7,
      "wisdom": 3, "endurance": 4, "charisma": 6
    },
    "base_hp": 100, "base_mana": 50, "base_sp": 30
  },
  {
    "id": "mage",
    "name": "Mage",
    "description": "A master of arcane magic who wields devastating elemental spells from range.",
    "main_stat": "intelligence",
    "resource": "mana",
    "starting_stats": {
      "strength": 3, "dexterity": 3, "intelligence": 8, "agility": 4,
      "wisdom": 6, "endurance": 5, "charisma": 6
    },
    "base_hp": 100, "base_mana": 50, "base_sp": 30
  },
  {
    "id": "ranger",
    "name": "Ranger",
    "description": "A versatile wilderness fighter skilled in ranged combat and nature magic.",
    "main_stat": "dexterity",
    "resource": "sp",
    "starting_stats": {
      "strength": 5, "dexterity": 7, "intelligence": 4, "agility": 6,
      "wisdom": 4, "endurance": 5, "charisma": 4
    },
    "base_hp": 100, "base_mana": 50, "base_sp": 30
  },
  {
    "id": "bard",
    "name": "Bard",
    "description": "A charismatic performer who uses songs and music to buff allies and debilitate foes.",
    "main_stat": "charisma",
    "resource": "mana",
    "starting_stats": {
      "strength": 4, "dexterity": 5, "intelligence": 5, "agility": 5,
      "wisdom": 5, "endurance": 4, "charisma": 7
    },
    "base_hp": 100, "base_mana": 50, "base_sp": 30
  },
  {
    "id": "cleric",
    "name": "Cleric",
    "description": "A holy warrior who channels divine power to heal, protect, and smite the unholy.",
    "main_stat": "wisdom",
    "resource": "mana",
    "starting_stats": {
      "strength": 6, "dexterity": 3, "intelligence": 6, "agility": 3,
      "wisdom": 8, "endurance": 6, "charisma": 3
    },
    "base_hp": 100, "base_mana": 50, "base_sp": 30
  }
]
```

---

## 14. Static Data: maps.json

Floor 1 tile grid. Based on the design doc map references, the start tile is top-left. SR = Scenario Room. Red = guaranteed combat. This is a placeholder grid derived from the described structure -- the exact layout should be refined from the map images.

```json
{
  "floors": [
    {
      "floor": 1,
      "name": "Floor 1",
      "width": 7,
      "height": 7,
      "start": [0, 0],
      "exit": [6, 6],
      "tiles": [
        ["start",  "path",    "path",    "sr",      "path",    "combat",  "path"],
        ["path",   "wall",    "wall",    "path",    "wall",    "path",    "wall"],
        ["sr",     "path",    "combat",  "path",    "sr",      "path",    "path"],
        ["path",   "wall",    "path",    "wall",    "path",    "wall",    "sr"],
        ["path",   "path",    "sr",      "path",    "combat",  "path",    "path"],
        ["wall",   "wall",    "path",    "wall",    "path",    "wall",    "path"],
        ["combat", "path",    "sr",      "path",    "path",    "sr",      "exit"]
      ]
    }
  ]
}
```

Tile types:
- `start` -- player spawn point
- `exit` -- advances to next floor
- `path` -- walkable tile, may trigger random encounter
- `wall` -- impassable
- `sr` -- Scenario Room (guaranteed scenario event)
- `combat` -- Red room (guaranteed combat encounter)

---

## 15. Game Constants

All numeric constants from the design doc, centralized in `src/game/constants.py`.

```python
# --- Resource Regeneration (per tile move) ---
REGEN_SP_PER_TILE = 5
REGEN_MANA_PER_TILE = 10
REGEN_HP_PER_TILE = 10

# --- Base Resources ---
BASE_HP = 100
BASE_MANA = 50
BASE_SP = 30

# --- Stat Multipliers ---
STRENGTH_MULTIPLIER = 0.2        # Physical damage bonus
DEXTERITY_MULTIPLIER = 0.4       # Double-strike chance (percent)
INTELLIGENCE_DMG_MULTIPLIER = 0.2  # Spell damage bonus
INTELLIGENCE_EFFECT_MULTIPLIER = 0.4  # Spell effect activation chance
AGILITY_MULTIPLIER = 0.2         # Dodge chance (percent)
WISDOM_MULTIPLIER = 0.4          # Healing bonus & buff extension chance
ENDURANCE_HP_PER_POINT = 10      # Bonus HP per endurance
ENDURANCE_MANA_PER_POINT = 5     # Bonus mana per endurance
ENDURANCE_SP_PER_POINT = 5       # Bonus SP per endurance
CHARISMA_SONG_MULTIPLIER = 0.2   # Spell song damage bonus
CHARISMA_BUFF_MULTIPLIER = 0.4   # Buff duration extension chance

# --- Leveling ---
STAT_POINTS_PER_LEVEL = 5
SKILL_UNLOCK_INTERVAL = 5        # Learn a skill every 5 levels
TALENT_UNLOCK_INTERVAL = 10      # Learn a talent every 10 levels
PERFECT_ENCOUNTER_XP_BONUS = 0.10  # +10% XP for taking no damage

# --- Combat Turn Rules ---
MAX_ATTACKS_PER_TURN = 1
MAX_BUFFS_PER_TURN = 1
MAX_ITEMS_PER_TURN = 1

# --- Armor ---
ARMOR_REDUCTION_CONSTANT = 500   # AR / (AR + 500) * 100 = DR%
MAX_AR_BY_SLOT = {
    "head": 100, "shoulders": 90, "chest": 110,
    "gloves": 80, "legs": 90, "feet": 80
}

# --- Weapon/Armor Rarity ---
RARITY_TIERS = ["poor", "common", "uncommon", "rare", "epic", "legendary"]

WEAPON_DAMAGE_RANGES = {
    "poor": (3, 11), "common": (9, 16), "uncommon": (13, 21),
    "rare": (18, 26), "epic": (23, 31), "legendary": (28, 36)
}

WEAPON_DROP_CHANCES = {
    "poor": 50.9, "common": 30.0, "uncommon": 10.0,
    "rare": 5.0, "epic": 4.0, "legendary": 0.1
}

ARMOR_RARITY_MULTIPLIERS = {
    "common": (1.1, 1.5), "uncommon": (1.5, 2.0), "rare": (2.0, 2.5),
    "epic": (2.5, 3.0), "legendary": (3.0, 5.0)
}

# --- Stat Affix Rules ---
STAT_AFFIX_RULES = {
    "poor": {"count": 0, "multipliers": []},
    "common": {"count": 0, "multipliers": []},
    "uncommon": {"count": 1, "multipliers": [1]},
    "rare": {"count": 2, "multipliers": [2, 1]},
    "epic": {"count": 3, "multipliers": [3, 2, 1]},
    "legendary": {"count": 3, "multipliers": [3, 3, 2]}
}

# Floor scaling: base affix increases by +1 every 5 floors
AFFIX_BASE_PER_FLOOR_GROUP = 1   # floors 1-5 = +1 base, 6-10 = +2, etc.

# --- Scenario Chances ---
SCENARIO_NEGATIVE_CHANCE = 33
SCENARIO_POSITIVE_CHANCE = 33
SCENARIO_NEUTRAL_CHANCE = 34
ENCOUNTER_CHANCE_PER_TILE = 60   # % chance on non-combat, non-SR tiles

# --- Flee ---
BASE_FLEE_CHANCE = 30            # percent
AGILITY_FLEE_BONUS = 1           # +1% per agility point

# --- Main Stat Duration Formula ---
# duration_turns = max(1, floor(main_stat_value / 10))

# --- Stats List ---
ALL_STATS = ["strength", "dexterity", "intelligence", "agility", "wisdom", "endurance", "charisma"]
```

---

## 16. Bot Skeleton

### 16.1 bot.py (Entry Point)

Responsibilities:
- Load `.env` (BOT_TOKEN)
- Initialize Discord bot with required intents
- Load all cogs from `src/bot/cogs/`
- Initialize database on startup
- Sync slash commands
- Run the bot

### 16.2 src/bot/cogs/general.py (Stage 1 Commands)

Two commands for Stage 1:

- `/ping` -- Responds with bot latency. Confirms the bot is online.
- `/help` -- Shows an overview embed with available commands and game description.

### 16.3 src/db/database.py

Responsibilities:
- `async def init_db()` -- Create all tables using the schema from Section 4
- `async def get_db()` -- Return an aiosqlite connection
- Handle migrations as schema evolves

### 16.4 src/utils/data_loader.py

Responsibilities:
- `load_json(filename)` -- Load a JSON data file from `data/` directory
- `get_skills(class_name=None)` -- Return skills, optionally filtered by class
- `get_talents(class_name=None)` -- Return talents, optionally filtered by class
- `get_weapons()` -- Return all weapons
- `get_armor(class_name=None, slot=None)` -- Return armor, optionally filtered
- `get_consumables()` -- Return all consumables
- `get_enemies(enemy_type=None, level=None)` -- Return enemy data
- `get_class(class_id)` -- Return class data
- `get_xp_threshold(level)` -- Return XP needed for a given level

### 16.5 src/utils/embeds.py

Reusable embed builders:
- `error_embed(message)` -- Red embed for errors
- `success_embed(title, message)` -- Green embed for success
- `info_embed(title, message)` -- Blue embed for info
- `help_embed()` -- Full help command embed

### 16.6 src/game/constants.py

All constants from Section 15 of this document.

### 16.7 src/game/formulas.py

Pure functions (no DB, no state):
- `calc_bonus_physical_damage(strength)` -- strength * 0.2
- `calc_double_strike_chance(dexterity)` -- dexterity * 0.4
- `calc_bonus_spell_damage(intelligence)` -- intelligence * 0.2
- `calc_spell_effect_chance(intelligence)` -- intelligence * 0.4
- `calc_dodge_chance(agility)` -- agility * 0.2
- `calc_healing_bonus(wisdom)` -- wisdom * 0.4
- `calc_buff_extend_chance(wisdom)` -- wisdom * 0.4
- `calc_bonus_hp(endurance)` -- endurance * 10
- `calc_bonus_mana(endurance)` -- endurance * 5
- `calc_bonus_sp(endurance)` -- endurance * 5
- `calc_song_bonus(charisma)` -- charisma * 0.2
- `calc_buff_duration_chance(charisma)` -- charisma * 0.4
- `calc_armor_reduction(total_ar)` -- (total_ar / (total_ar + 500)) * 100
- `calc_max_hp(base_hp, endurance)` -- base_hp + calc_bonus_hp(endurance)
- `calc_max_mana(base_mana, endurance)` -- base_mana + calc_bonus_mana(endurance)
- `calc_max_sp(base_sp, endurance)` -- base_sp + calc_bonus_sp(endurance)
- `calc_main_stat_duration(main_stat_value)` -- max(1, main_stat_value // 10)

---

## 17. Validation Checklist

When Stage 1 is complete, verify:

- [ ] Bot connects to Discord and responds to `/ping` with latency
- [ ] `/help` displays a formatted embed
- [ ] Database creates all 4 tables without errors
- [ ] All 10 JSON data files load without parse errors
- [ ] `skills.json` contains exactly 60 skills (10 per class x 6 classes)
- [ ] `talents.json` contains exactly 30 talents (5 per class x 6 classes)
- [ ] `weapons.json` contains exactly 59 weapons
- [ ] `armor.json` contains exactly 147 armor pieces
- [ ] `consumables.json` contains exactly 15 consumables
- [ ] `enemies.json` contains exactly 40 entries (20 levels x 2 enemy types)
- [ ] `xp_thresholds.json` contains exactly 20 entries (levels 1-20)
- [ ] `classes.json` contains exactly 6 classes with starting stats summing to 35
- [ ] `maps.json` contains at least Floor 1
- [ ] `loot_tables.json` contains drops for goblin (5 items) and feral_rat (3 items)
- [ ] `constants.py` compiles without errors
- [ ] `formulas.py` functions return correct values for sample inputs
- [ ] `data_loader.py` can load and filter all data files
- [ ] `.env.example` exists with placeholder values
- [ ] `.gitignore` excludes `.env`, `__pycache__`, `*.db`
- [ ] `requirements.txt` lists all dependencies
