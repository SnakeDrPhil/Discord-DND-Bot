# Stage 3 Workbook -- Combat Engine (Core Loop)

**Purpose:** Comprehensive build spec for Stage 3. Players can fight enemies in turn-based combat using basic attacks, learned skills, and consumable items. This is the heart of the game.

---

## Table of Contents

1. [What Already Exists](#1-what-already-exists)
2. [Files to Create](#2-files-to-create)
3. [Files to Modify](#3-files-to-modify)
4. [Design Decisions](#4-design-decisions)
5. [Combat State Machine](#5-combat-state-machine)
6. [Combat Session Data Model](#6-combat-session-data-model)
7. [Damage Calculation Pipeline](#7-damage-calculation-pipeline)
8. [Basic Attacks](#8-basic-attacks)
9. [Skill & Spell Usage](#9-skill--spell-usage)
10. [Status Effect System](#10-status-effect-system)
11. [Talent Passive System](#11-talent-passive-system)
12. [Enemy AI](#12-enemy-ai)
13. [Flee Mechanics](#13-flee-mechanics)
14. [Double Strike (Dexterity)](#14-double-strike-dexterity)
15. [Consumable Item Usage](#15-consumable-item-usage)
16. [Combat Resolution](#16-combat-resolution)
17. [Combat UI -- Embeds & Buttons](#17-combat-ui----embeds--buttons)
18. [New Cog: combat.py -- Commands](#18-new-cog-combatpy----commands)
19. [Modifications to Existing Files](#19-modifications-to-existing-files)
20. [Testing & Admin Commands](#20-testing--admin-commands)
21. [Validation Checklist](#21-validation-checklist)

---

## 1. What Already Exists

These Stage 1 & 2 components are ready to use:

| Component | Location | What it provides |
|---|---|---|
| Skills data (59 skills) | `data/skills.json` | All skill definitions with damage_multiplier, status_effects, cost, resource, target, duration_rule |
| Talents data (30 talents) | `data/talents.json` | All passive talent definitions with passive_modifiers |
| Enemies data (40 entries) | `data/enemies.json` | Goblin + Feral Rat, levels 1-20 with damage_min/max, hp, xp_reward |
| Consumables (15 items) | `data/consumables.json` | Healing/Mana/SP consumables with effects and status_effects |
| Loot tables | `data/loot_tables.json` | 5 goblin drops, 3 feral rat drops with gold ranges |
| Weapons (59 weapons) | `data/weapons.json` | All weapons with hand_type, casting, damage_type |
| Data loader | `src/utils/data_loader.py` | `get_enemies()`, `get_skill_by_id()`, `get_consumables()`, `get_loot_table()` |
| Formulas | `src/game/formulas.py` | `calc_bonus_physical_damage()`, `calc_bonus_spell_damage()`, `calc_dodge_chance()`, `calc_double_strike_chance()`, `calc_armor_reduction()`, `calc_main_stat_duration()`, all stat formula functions |
| Constants | `src/game/constants.py` | `BASE_FLEE_CHANCE`, `AGILITY_FLEE_BONUS`, `PERFECT_ENCOUNTER_XP_BONUS`, `MAX_ATTACKS_PER_TURN`, `MAX_BUFFS_PER_TURN`, `MAX_ITEMS_PER_TURN` |
| Leveling engine | `src/game/leveling.py` | `grant_xp()`, `check_level_up()` -- used to award XP on victory |
| DB schema | `src/db/database.py` | `combat_sessions` table already defined with all needed columns |
| DB models | `src/db/models.py` | `get_player()`, `update_player()`, `get_inventory()`, `add_inventory_item()`, `remove_inventory_item()` |
| Embeds | `src/utils/embeds.py` | `error_embed()`, `success_embed()`, `level_up_embed()`, `CLASS_COLORS` |
| Bot entry | `bot.py` | COGS list to extend |

---

## 2. Files to Create

| File | Purpose |
|---|---|
| `src/game/combat.py` | Combat engine: state machine, damage calc, turn processing, status effects, skill execution |
| `src/bot/cogs/combat.py` | Combat commands and interactive button UI |

---

## 3. Files to Modify

| File | Changes |
|---|---|
| `bot.py` | Add `"src.bot.cogs.combat"` to COGS list |
| `src/utils/embeds.py` | Add `combat_embed()`, `combat_result_embed()`, `loot_embed()` |
| `src/db/models.py` | Add combat session CRUD: `create_combat_session()`, `get_combat_session()`, `update_combat_session()`, `delete_combat_session()` |
| `src/game/constants.py` | Add `UNARMED_DAMAGE_MIN/MAX`, `THRUST_STUN_CHANCE`, `THRUST_DAMAGE_MULTIPLIER`, enemy spawn weights |

---

## 4. Design Decisions

### 4.1 Equipment Not Yet Available

Stage 5 implements the full item/equipment system. For Stage 3, players fight **unarmed** with a default base damage range. This keeps combat functional without equipment.

```python
UNARMED_DAMAGE_MIN = 5
UNARMED_DAMAGE_MAX = 10
UNARMED_DAMAGE_TYPE = "blunt"
```

When Stage 5 is built, the damage pipeline will check for equipped weapons and use their damage range instead.

### 4.2 Action Slot Classification

The design doc states: *"A normal combat turn allows 1 attack, 1 buff, and 1 item usage in a single turn."*

Skills are classified into action slots based on their `type` field:

| Action Slot | Skill Types | Examples |
|---|---|---|
| **Attack** | `slash`, `blunt`, `stab`, `weapon_based`, `ice_spell`, `fire_spell`, `spell`, `skill` (with damage_multiplier), `debuff` | Whirlwind Attack, Fireball, Dagger Throw, Mighty Roar |
| **Buff** | `buff`, `skill_buff`, `parry` | Armor Up, Counterattack, Vanish, Cloaked in Shadows |
| **Neither** (special) | `skill` (no damage, self-target flee/skip) | Quick Escape, Smoke Bomb |

**Rule:** If a skill has `damage_multiplier is not None` or its `target` is an enemy target, it uses the **Attack** slot. Otherwise it uses the **Buff** slot. Special skills like Quick Escape (flee) and Smoke Bomb (skip turns) end the turn immediately.

### 4.3 Main Stat Duration Formula

Already implemented in `formulas.py`:
```python
calc_main_stat_duration(main_stat_value) = max(1, floor(main_stat / 10))
```

Main stat mapping (from `classes.json`):
| Class | Main Stat |
|---|---|
| Warrior | strength |
| Rogue | dexterity |
| Mage | intelligence |
| Ranger | dexterity |
| Bard | charisma |
| Cleric | wisdom |

### 4.4 Enemy Spawning (Standalone)

Since dungeons (Stage 4) don't exist yet, `/fight` spawns enemies directly:
- Enemy count: 1-3 (weighted: 60% chance of 1, 30% chance of 2, 10% chance of 3)
- Enemy type: random from goblin/feral_rat
- Enemy level: matches player level (capped at 20)

### 4.5 Basic Thrust Stun Chance

The design doc says thrust "can Stun" but doesn't give a percentage. Default:
```python
THRUST_STUN_CHANCE = 10   # 10% chance to stun for 1 turn
THRUST_DAMAGE_MULTIPLIER = 0.7  # Lower damage than slash
```

### 4.6 Absorb Shields

Skills with `"type": "absorb"` (Mana Shield, Song Shield, Divine Shield) negate all incoming damage while active. The buff lasts for its duration in turns. This makes them powerful but balanced by high mana costs and limited duration.

---

## 5. Combat State Machine

```
IDLE ──[/fight]──> PLAYER_TURN ──[actions]──> PLAYER_TURN (until turn ends)
                       │                           │
                       │                    [all slots used or /endturn]
                       │                           │
                       │                           v
                       │                     ENEMY_TURN ──> process each enemy
                       │                           │
                       │         ┌─────────────────┤
                       │         v                  v
                       │    PLAYER_TURN       COMBAT_OVER
                       │    (new turn)        (victory/defeat/flee)
                       │         │                  │
                       └─────────┘                  v
                                                  IDLE
```

### Turn Flow Detail

**Player Turn Start:**
1. Reset action counters: `attacks_used=0`, `buffs_used=0`, `items_used=0`
2. Process start-of-turn effects:
   - Talent: Cleric's Faithful Recovery (+20% max HP at start of each encounter, FIRST TURN ONLY)
   - Talent: Bard's Charming Aura (10% charm chance at combat start, FIRST TURN ONLY)
   - Talent: Warrior's Battle Hardened (+5 HP regen per turn)
   - Process player DoT debuffs (burn, poison, bleed damage)
   - Tick down buff/debuff durations, remove expired ones
3. Check if player is stunned/frozen → if so, skip to enemy turn
4. Send updated combat embed with available actions

**Player Action Processing:**
1. Validate action is allowed (correct slot available, enough resources)
2. Execute action (damage calc, apply effects)
3. Check for double-strike trigger (Dexterity)
4. Mark action slot as used
5. Check if turn should auto-end (all slots used, or special skill like Smoke Bomb)
6. If turn not ended, update embed (player can take more actions)

**Player Turn End → Enemy Turn:**
1. Process end-of-turn player effects (Ranger's Quick Reload extra attack)
2. Process each living enemy sequentially:
   a. Check if enemy is stunned/frozen/charmed → skip if so
   b. If charmed: enemy attacks another enemy instead
   c. Roll enemy damage (damage_min to damage_max)
   d. Check player dodge (agility * 0.2 %)
   e. Apply player damage reduction buffs
   f. Apply damage to player
   g. Track damage_taken for perfect encounter check
3. Process companion attacks (Ranger's Beast Companion)
4. Check defeat: player HP <= 0 → combat over
5. Increment turn number

---

## 6. Combat Session Data Model

The `combat_sessions` table already exists in the schema:

```sql
combat_sessions (
    id, player_id (UNIQUE), enemies (JSON), turn_number,
    current_turn ('player'/'enemy'),
    player_buffs (JSON), player_debuffs (JSON),
    enemy_buffs (JSON), enemy_debuffs (JSON),
    attacks_used, buffs_used, items_used,
    extra_turn, damage_taken, combat_log (JSON),
    started_at
)
```

### 6.1 Enemies JSON Structure

```json
[
  {
    "id": 0,
    "type": "goblin",
    "name": "Goblin",
    "level": 3,
    "hp": 40,
    "max_hp": 40,
    "damage_min": 16,
    "damage_max": 20,
    "xp_reward": 40,
    "is_alive": true
  },
  {
    "id": 1,
    "type": "feral_rat",
    "name": "Feral Rat",
    "level": 3,
    "hp": 35,
    "max_hp": 35,
    "damage_min": 4,
    "damage_max": 6,
    "xp_reward": 30,
    "is_alive": true
  }
]
```

Each enemy gets a unique `id` (index) for targeting purposes.

### 6.2 Buff/Debuff JSON Structure

```json
// player_buffs example
[
  {
    "type": "defense_up",
    "value": 25,
    "unit": "percent",
    "remaining_turns": 2,
    "source": "warrior_armor_up"
  },
  {
    "type": "absorb",
    "remaining_turns": 1,
    "source": "mage_mana_shield"
  }
]

// player_debuffs example
[
  {
    "type": "burn",
    "damage_per_turn": 5,
    "remaining_turns": 2,
    "source": "enemy"
  }
]

// enemy_debuffs example (keyed by enemy id)
[
  {
    "enemy_id": 0,
    "type": "slow",
    "remaining_turns": 1,
    "source": "mage_frost_nova"
  },
  {
    "enemy_id": 0,
    "type": "stun",
    "remaining_turns": 1,
    "source": "warrior_shield_bash"
  }
]
```

### 6.3 Combat Log Structure

```json
[
  {"turn": 1, "actor": "player", "action": "slash", "target": "Goblin", "damage": 15, "message": "You slashed the Goblin for 15 damage!"},
  {"turn": 1, "actor": "Goblin", "action": "attack", "target": "player", "damage": 14, "message": "Goblin attacked you for 14 damage!"},
  {"turn": 1, "actor": "player", "action": "dodge", "target": null, "damage": 0, "message": "You dodged the Feral Rat's attack!"}
]
```

Only keep the last 10 log entries to prevent embed overflow.

---

## 7. Damage Calculation Pipeline

### 7.1 Player Physical Attack Damage

```python
def calc_player_attack_damage(player, skill=None, target_enemy=None):
    """Calculate damage for a player's physical attack."""
    # 1. Base weapon damage (unarmed for Stage 3)
    base_min = UNARMED_DAMAGE_MIN  # 5
    base_max = UNARMED_DAMAGE_MAX  # 10
    # TODO Stage 5: check equipped weapon, use its damage range

    base_damage = random.randint(base_min, base_max)

    # 2. Apply skill multiplier (if using a skill)
    if skill and skill.get("damage_multiplier"):
        base_damage = int(base_damage * skill["damage_multiplier"])

    # 3. Add stat bonus
    stat_bonus = calc_bonus_physical_damage(player["strength"])  # str * 0.2
    damage = base_damage + stat_bonus

    # 4. Apply player damage buffs
    for buff in player_buffs:
        if buff["type"] == "strength_up":
            damage *= (1 + buff["value"] / 100)
        if buff["type"] == "next_attack_bonus":
            damage *= (1 + buff["value"] / 100)
            # Remove one-shot buff after use
        if buff["type"] == "damage_up":
            damage *= (1 + buff["value"] / 100)

    # 5. Apply talent bonuses
    #    - Berserker Fury: +5% per 10% HP lost
    #    - Thrust Mastery: +25% for stab attacks
    #    - Stealthy Hunter: +15% on first attack
    #    - Marksmanship: +25% ranged damage
    #    - Holy Guidance: +10% blunt damage

    # 6. Apply conditional bonuses
    #    - Backstab: 150% if target has bleed
    #    - Nature's Karma: 150% if target has slow
    #    - Silent Kill: 200% if target below 5% HP

    # 7. Floor to int, minimum 1
    return max(1, int(damage))
```

### 7.2 Player Spell Damage

```python
def calc_player_spell_damage(player, skill, target_enemy=None):
    """Calculate damage for a player's spell attack."""
    base_min = UNARMED_DAMAGE_MIN
    base_max = UNARMED_DAMAGE_MAX
    # TODO Stage 5: use casting weapon damage

    base_damage = random.randint(base_min, base_max)

    if skill.get("damage_multiplier"):
        base_damage = int(base_damage * skill["damage_multiplier"])

    # Spell damage uses intelligence OR charisma (for bard songs)
    if player["class"] == "bard":
        stat_bonus = calc_song_bonus(player["charisma"])  # cha * 0.2
    else:
        stat_bonus = calc_bonus_spell_damage(player["intelligence"])  # int * 0.2

    damage = base_damage + stat_bonus

    # Apply spell damage buffs and talents
    # - Arcane Knowledge: +5% per 10 INT
    # - Inspiring Presence: +50% buff effectiveness (indirect)

    return max(1, int(damage))
```

### 7.3 Enemy Damage to Player

```python
def calc_enemy_damage(enemy, player, player_buffs):
    """Calculate damage an enemy deals to the player."""
    # 1. Roll raw damage
    raw_damage = random.randint(enemy["damage_min"], enemy["damage_max"])

    # 2. Check absorb shield -- if active, damage = 0
    for buff in player_buffs:
        if buff["type"] == "absorb":
            return 0, "absorbed"

    # 3. Check dodge
    dodge_chance = calc_dodge_chance(player["agility"])  # agi * 0.2
    # Add dodge bonuses from buffs/talents
    for buff in player_buffs:
        if buff["type"] == "dodge_up":
            dodge_chance += buff["value"]
        if buff["type"] == "evasion":
            dodge_chance += buff.get("chance", 0)
    # Talent: Evasion +15%, Keen Reflexes +10%, Quick Reflexes +10% after hit

    if random.random() * 100 < dodge_chance:
        return 0, "dodged"

    # 4. Apply damage reduction buffs
    damage = raw_damage
    for buff in player_buffs:
        if buff["type"] == "damage_reduction":
            damage *= (1 - buff["value"] / 100)
        if buff["type"] == "defense_up":
            damage *= (1 - buff["value"] / 100)

    # Talent: Toughened Skin -10% physical damage
    # Talent: Sacred Resilience -20% damage

    # 5. Apply armor reduction (Stage 5 -- currently 0 AR)
    # ar_reduction = calc_armor_reduction(total_ar)
    # damage *= (1 - ar_reduction / 100)

    # 6. Counterattack check: if player has reflect buff
    # Apply reflect damage to enemy

    return max(1, int(damage)), "hit"
```

---

## 8. Basic Attacks

### 8.1 Basic Slash (`/attack slash`)

- Available to all classes
- Uses the **Attack** action slot
- Damage: `random(base_min, base_max) + strength * 0.2`
- Damage type: uses weapon's damage_type, or `"slash"` if unarmed
- No special effects

### 8.2 Basic Thrust (`/attack thrust`)

- Available to all classes
- Uses the **Attack** action slot
- Damage: `random(base_min, base_max) * 0.7 + strength * 0.2` (lower base damage)
- Damage type: `"stab"`
- **10% chance to stun** the target for 1 turn (target skips their next turn)

### 8.3 Target Selection

- If 1 enemy: auto-target
- If multiple enemies: player selects target via select menu or parameter
- Default: target the first living enemy if not specified

---

## 9. Skill & Spell Usage

### 9.1 Using a Skill

Command: `/use <skill_name>` or click the Skills select menu

**Validation:**
1. Player is in combat and it's their turn
2. Player has learned the skill
3. Player has enough resources (SP or Mana) to pay the cost
4. The correct action slot is available (attack or buff slot)
5. If skill has `condition`, validate it:
   - `target_has_bleed`: target must have bleed debuff
   - `target_has_slow`: target must have slow debuff
   - `target_below_5_percent_hp`: target HP < 5% of max
6. If skill has `once_per_combat` flag, check it hasn't been used

**Execution:**
1. Deduct resource cost (apply Mana Efficiency talent: -10% mana cost for mages)
2. Calculate damage (if applicable) via damage pipeline
3. Apply damage to target(s):
   - `single_enemy`: damage one target
   - `enemies_3`: damage up to 3 enemies (distribute evenly)
   - `all_enemies`: damage all living enemies
   - `self`: apply buff/heal to player
   - `summon`: create companion
4. Apply status effects (see Section 10)
5. Handle special effects:
   - `hit_count`: repeat the attack N times (Rampage x3, Shadow Step x2, Multi-Shot x2)
   - `auto_hit`: skip dodge check (Magic Missile)
   - `random_element`: roll fire/ice/lightning, apply corresponding effect
   - `heal` effects: restore HP immediately
   - `lifesteal`: heal for X% of damage dealt
6. Log the action to combat_log

### 9.2 Skill Action Slot Mapping

```python
ATTACK_SLOT_TYPES = {
    "slash", "blunt", "stab", "weapon_based",
    "ice_spell", "fire_spell", "spell",
    "debuff",
}
BUFF_SLOT_TYPES = {"buff", "skill_buff", "parry"}
SPECIAL_TYPES = {"skill", "ability"}  # Determined by context

def get_action_slot(skill):
    """Determine which action slot a skill uses."""
    if skill["type"] in ATTACK_SLOT_TYPES:
        return "attack"
    if skill["type"] in BUFF_SLOT_TYPES:
        return "buff"
    # For "skill" and "ability" types, check context:
    if skill.get("damage_multiplier") is not None and skill["target"] != "self":
        return "attack"
    # Self-target skills with no damage use buff slot
    if skill["target"] == "self":
        return "buff"
    # Enemy-target debuffs use attack slot
    return "attack"
```

### 9.3 Skill Target Types Reference

| Target Value | Meaning | How to handle |
|---|---|---|
| `single_enemy` | One enemy | Player selects target |
| `enemies_3` | Up to 3 enemies | Hits first 3 living enemies |
| `all_enemies` | All enemies | Hits all living enemies |
| `all` | Both player and enemies | Smoke Bomb: affects everyone |
| `self` | Player only | Buff/heal on self |
| `summon` | Creates companion | Special handling |
| `furthest_enemy` | Farthest target | Hits last living enemy in list |

---

## 10. Status Effect System

### 10.1 Effect Application

When a skill's `status_effects` contains an effect:

```python
def apply_status_effect(effect_def, source_skill, player, combat_session):
    """Apply a status effect from a skill."""
    # Check if the effect has a chance roll
    chance = effect_def.get("chance", 100)
    if random.randint(1, 100) > chance:
        return False  # Effect didn't proc

    # Determine duration
    duration = effect_def.get("duration")
    if duration is None and source_skill["duration_rule"] == "main_stat":
        class_data = get_class(player["class"])
        main_stat = class_data["main_stat"]
        duration = calc_main_stat_duration(player[main_stat])
    elif duration is None:
        duration = 1  # Default 1 turn if unspecified

    # Create the buff/debuff entry
    entry = {
        "type": effect_def["type"],
        "remaining_turns": duration,
        "source": source_skill["id"],
    }
    if "value" in effect_def:
        entry["value"] = effect_def["value"]
    if "unit" in effect_def:
        entry["unit"] = effect_def["unit"]

    return entry
```

### 10.2 Status Effect Reference

**Debuffs on Enemies:**

| Effect | Behavior | Source Examples |
|---|---|---|
| `stun` | Enemy skips their turn | Shield Bash (25% x 1 turn), Divine Smite, Heroic Anthem |
| `slow` | Reduces enemy dodge (flavor: reduce turn priority) | Frost Nova, Nature's Grasp, Ice Bolt |
| `burn` | Damage per turn = 5% of original skill damage | Fireball (30%), Fire Wall, Elemental Burst |
| `bleed` | Damage per turn = 3 per turn | Dagger Throw (25% x 2 turns) |
| `freeze` | Enemy skips turn (ice variant of stun) | Ice Spike (20%) |
| `charm` | Enemy attacks other enemies instead of player | Charming Song, Charming Aura talent |
| `disarm` | Enemy deals 50% reduced damage (can't use weapon) | Disarm Target |
| `accuracy_down` | Enemy has X% miss chance | Dissonant Chord (-50%), Guiding Light (-50%) |
| `strength_down` | Enemy damage reduced by X% | Mighty Roar (-15%) |
| `attack_down` | Enemy damage reduced by X% | Fascinating Tune (-15%) |
| `armor_down` | Enemy takes X% more damage | Echoing Song (-25%) |
| `skip_turn` | Enemy skips N turns | Teleportation, Trap Setting |
| `immobilize` | Enemy can't act | Trap Setting (50%) |

**Buffs on Player:**

| Effect | Behavior | Source Examples |
|---|---|---|
| `defense_up` | Reduce incoming damage by X% | Armor Up (+25%), Ballad of Resilience (+15%) |
| `damage_reduction` | Reduce incoming damage by X% | Defensive Stance (-30%), Aura of Protection (-50%), Nature's Shield (-20%) |
| `strength_up` | Increase outgoing damage by X% | Battle Cry (+20%) |
| `damage_up` | Increase outgoing damage by X% | Vanish (+50%) |
| `dodge_up` | Increase dodge chance by X% | Shadow Step (+20%), Cloaked in Shadows (+40%) |
| `evasion` | X% chance to avoid damage entirely | Tactical Retreat (50%) |
| `absorb` | Negate all incoming damage | Mana Shield, Song Shield, Divine Shield |
| `reflect` | Reflect X% of damage back to attacker | Counterattack (50%) |
| `untargetable` | Cannot be targeted for N turns | Vanish (1 turn) |
| `melee_immune` | Immune to melee attacks | Grappling Hook |
| `illusion` | Attacks diverted to illusion | Illusion |
| `next_attack_bonus` | Next attack deals +X% damage (consumed on use) | Concentrated Shot (+100%), Rallying Cry (+40%), Eagle Eye (+50%) |
| `crit_up` | +X% critical hit chance for next attack | Hawkeye (+20%) |
| `armor_pierce` | Next attack ignores armor | Eagle Eye |
| `heal_over_time` | Heal X% max HP per turn | Sanctuary (10% x 2), Consecrate Ground (10% x 4) |
| `conditional_damage_up` | +X% damage vs targets with condition | Nature's Karma (+150% vs slowed) |

**Self-Effects (Immediate):**

| Effect | Behavior | Source Examples |
|---|---|---|
| `heal` | Restore X% of max HP immediately | Inspiring Tune (15%), Healing Wave (25%), Holy Light (15%) |
| `lifesteal` | Heal for X% of damage dealt | Blessed Strike (10%) |
| `cleanse` | Remove N debuffs | Purge (1 debuff) |
| `flee` | X% chance to escape combat | Quick Escape (30%) |

### 10.3 Turn-Based Processing

At the **start of each turn** (before the actor acts):

```python
def process_turn_start(actor_buffs, actor_debuffs, actor_hp, actor_max_hp):
    """Process start-of-turn effects. Returns (new_hp, log_messages, expired_effects)."""
    messages = []

    # Process DoTs (burn, bleed, poison)
    for debuff in actor_debuffs:
        if debuff["type"] in ("burn", "bleed", "poison"):
            dot_damage = debuff.get("damage_per_turn", 3)
            actor_hp -= dot_damage
            messages.append(f"Took {dot_damage} {debuff['type']} damage!")

    # Process HoTs (heal_over_time)
    for buff in actor_buffs:
        if buff["type"] == "heal_over_time":
            heal_amount = int(actor_max_hp * buff["value"] / 100)
            actor_hp = min(actor_hp + heal_amount, actor_max_hp)
            messages.append(f"Healed for {heal_amount} HP!")

    # Tick down durations
    for effect in actor_buffs + actor_debuffs:
        effect["remaining_turns"] -= 1

    # Remove expired effects
    actor_buffs = [b for b in actor_buffs if b["remaining_turns"] > 0]
    actor_debuffs = [d for d in actor_debuffs if d["remaining_turns"] > 0]

    return actor_hp, messages, actor_buffs, actor_debuffs
```

### 10.4 Stun/Freeze Check

```python
def is_stunned(debuffs):
    """Check if actor is stunned or frozen (must skip turn)."""
    return any(d["type"] in ("stun", "freeze", "blind") for d in debuffs)
```

If the player is stunned at the start of their turn, skip directly to enemy turn. If an enemy is stunned, skip that enemy's attack.

---

## 11. Talent Passive System

Talents are passive effects that are always active in combat. Check for selected talents when relevant.

### 11.1 Talent Processing by Timing

**At Combat Start (once):**
| Talent | Effect | Implementation |
|---|---|---|
| Cleric: Faithful Recovery | Restore 20% max HP | `hp = min(hp + int(max_hp * 0.2), max_hp)` |
| Bard: Charming Aura | 10% chance to charm one enemy | Roll 10%, apply charm to random enemy |

**Each Player Turn Start:**
| Talent | Effect | Implementation |
|---|---|---|
| Warrior: Battle Hardened | +5 HP per turn | `hp = min(hp + 5, max_hp)` |

**On Player Attack:**
| Talent | Effect | Implementation |
|---|---|---|
| Warrior: Berserker Fury | +5% damage per 10% HP lost | `bonus = 5 * ((max_hp - hp) // (max_hp // 10))` |
| Rogue: Thrust Mastery | +25% stab damage | If attack type == "stab": `damage *= 1.25` |
| Rogue: Stealthy Hunter | +15% on first attack | If first attack of combat: `damage *= 1.15` |
| Ranger: Marksmanship | +25% ranged damage | If weapon damage_type == "ranged": `damage *= 1.25` |
| Cleric: Holy Guidance | +10% blunt damage | If attack type == "blunt": `damage *= 1.10` |
| Mage: Arcane Knowledge | +5% spell damage per 10 INT | `bonus = 5 * (intelligence // 10)` |

**On Incoming Damage:**
| Talent | Effect | Implementation |
|---|---|---|
| Warrior: Toughened Skin | -10% physical damage | `damage *= 0.90` |
| Warrior: Iron Will | +25% resist stun/slow | 25% chance to negate stun/slow application |
| Rogue: Cunning Defense | +10% avoid crits | (No crit system yet -- reserve for Stage 7) |
| Cleric: Sacred Resilience | -20% damage | `damage *= 0.80` |

**On Dodge Check:**
| Talent | Effect | Implementation |
|---|---|---|
| Rogue: Evasion | +15% dodge | Add to dodge chance |
| Ranger: Keen Reflexes | +10% dodge | Add to dodge chance |
| Rogue: Quick Reflexes | +10% dodge after landing hit | Track if player hit last turn |

**End of Player Turn:**
| Talent | Effect | Implementation |
|---|---|---|
| Ranger: Quick Reload | Extra basic attack | Auto-perform one additional basic slash |

**On Buff Cast:**
| Talent | Effect | Implementation |
|---|---|---|
| Bard: Inspiring Presence | +50% buff effectiveness | Multiply buff values by 1.5 |
| Bard: Melodic Health | +5 HP per buff cast | `hp = min(hp + 5, max_hp)` |
| Bard: Fascinating Tunes | +1 turn on song effects | Add 1 to duration of bard buffs |

**Action Slot Modifier:**
| Talent | Effect | Implementation |
|---|---|---|
| Bard: Quick Notes | +1 action per turn | `max_attacks += 1`, `max_buffs += 1` |

**Spell Modifiers:**
| Talent | Effect | Implementation |
|---|---|---|
| Mage: Mana Efficiency | -10% mana cost | `cost = int(cost * 0.9)` (minimum 1) |
| Mage: Spell Reflect | 5% chance to reflect damage | On incoming spell damage: 5% chance to reflect |
| Mage: Intelligent Casting | +10% spell crit chance | (Reserve for Stage 7 crit system) |
| Mage: Elemental Resistance | +10% elemental resist | Reduce elemental damage by 10% |

**Encounter Rate (out-of-combat, Stage 4):**
| Talent | Effect | Implementation |
|---|---|---|
| Rogue: Silent Steps | Lower encounter rate | Reduce encounter_chance_per_tile by 15% |

**Companion (persistent per combat):**
| Talent | Effect | Implementation |
|---|---|---|
| Ranger: Nature's Companion | Summon companion | Attacks one enemy per turn for main_stat-based damage |

---

## 12. Enemy AI

Enemies use simple AI: each living enemy attacks the player on their turn.

```python
def process_enemy_turn(enemy, player, player_buffs, enemy_debuffs):
    """Process a single enemy's turn. Returns (damage, result, log_message)."""
    # Check if stunned/frozen/immobilized
    my_debuffs = [d for d in enemy_debuffs if d["enemy_id"] == enemy["id"]]
    if any(d["type"] in ("stun", "freeze", "skip_turn", "immobilize") for d in my_debuffs):
        return 0, "stunned", f"{enemy['name']} is stunned and cannot act!"

    # Check if charmed -- attack another enemy instead
    if any(d["type"] == "charm" for d in my_debuffs):
        # Find another living enemy to attack
        # Deal damage to that enemy
        return 0, "charmed", f"{enemy['name']} is charmed and attacks its allies!"

    # Check if disarmed -- reduced damage
    disarmed = any(d["type"] == "disarm" for d in my_debuffs)

    # Roll damage
    damage = random.randint(enemy["damage_min"], enemy["damage_max"])
    if disarmed:
        damage = int(damage * 0.5)

    # Apply enemy strength/attack debuffs
    for d in my_debuffs:
        if d["type"] in ("strength_down", "attack_down"):
            damage = int(damage * (1 - d["value"] / 100))

    # Check player dodge
    # Check player absorb/untargetable/melee_immune
    # Apply player damage reduction
    # Calculate final damage

    return final_damage, "hit", f"{enemy['name']} attacked you for {final_damage} damage!"
```

---

## 13. Flee Mechanics

### 13.1 `/flee` Command

```python
flee_chance = BASE_FLEE_CHANCE + (player["agility"] * AGILITY_FLEE_BONUS)
# BASE_FLEE_CHANCE = 30, AGILITY_FLEE_BONUS = 1
# Example: 30 + (5 * 1) = 35% flee chance
```

**On flee attempt:**
1. Roll flee chance
2. If **success**: end combat, no XP awarded, no loot
3. If **fail**: all living enemies get a free attack on the player, then player's turn ends
4. Flee always uses the player's entire turn (all remaining action slots)

### 13.2 Rogue's Quick Escape

- Separate from `/flee`, used via `/use Quick Escape`
- Costs 5 SP
- 30% chance to escape (independent of agility)
- Uses the buff action slot
- On failure: no free enemy attacks (unlike /flee)
- On success: combat ends immediately

---

## 14. Double Strike (Dexterity)

After any player **attack** action (basic attack or offensive skill), check for double strike:

```python
double_strike_chance = calc_double_strike_chance(player["dexterity"])
# dexterity * 0.4, e.g., 8 dex = 3.2%

if random.random() * 100 < double_strike_chance:
    # Perform one additional basic slash attack (free, doesn't use action slot)
    bonus_damage = calc_player_attack_damage(player, skill=None, target=target)
    # Apply damage
    # Log: "Double Strike! You struck again for {damage} damage!"
```

Double strike:
- Only triggers after attack-slot actions, not buffs or items
- Performs a basic slash (not the original skill)
- Does NOT consume an action slot
- Can only trigger once per action (no double-double-strike)

---

## 15. Consumable Item Usage

### 15.1 `/item` Command

- Uses the **Item** action slot (1 per turn)
- Player selects a consumable from their inventory via select menu or parameter
- Validates the item is in their inventory and is a consumable

### 15.2 Consumable Effects Processing

```python
def use_consumable(player, item_data, combat_session):
    """Process consumable use in combat. Returns (updates, log_message)."""
    # 1. Apply immediate resource restoration
    resource = item_data["resource"]  # "hp", "mana", or "sp"
    value = item_data["value"]

    updates = {}
    if resource == "hp":
        new_hp = min(player["hp"] + value, player["max_hp"])
        updates["hp"] = new_hp
        msg = f"Restored {value} HP!"
    elif resource == "mana":
        new_mana = min(player["mana"] + value, player["max_mana"])
        updates["mana"] = new_mana
        msg = f"Restored {value} Mana!"
    elif resource == "sp":
        new_sp = min(player["sp"] + value, player["max_sp"])
        updates["sp"] = new_sp
        msg = f"Restored {value} SP!"

    # 2. Apply status effects from the consumable
    if item_data.get("status_effect"):
        se = item_data["status_effect"]
        if se["type"] == "heal_over_time":
            # Add HoT buff to player
            pass
        elif se["type"] == "cleanse":
            # Remove debuffs
            pass
        elif se["type"] == "skip_turn":
            # Filling Meal: skip turn
            pass
        # ... etc

    # 3. Remove item from inventory (or decrement quantity)
    # remove_inventory_item(item_id)

    return updates, msg
```

### 15.3 Encounter-Limited Items

Some items have `encounter_limit`:
```json
{"per_encounter": 1, "total_encounters": 3}
```

- `per_encounter`: max uses in one combat
- `total_encounters`: total combats the item lasts across

Track uses in the combat session. For Stage 3, implement `per_encounter` only; `total_encounters` deferred to Stage 5 (persistent inventory tracking).

---

## 16. Combat Resolution

### 16.1 Victory

All enemies are dead (`hp <= 0` and `is_alive = false`).

**On Victory:**
1. Calculate total XP: sum of all enemies' `xp_reward`
2. Check perfect encounter: if `damage_taken == 0`, apply +10% XP bonus
3. Grant XP via `grant_xp(discord_id, total_xp)` -- handles level-ups automatically
4. Roll loot for each enemy killed (see 16.3)
5. Delete combat session from DB
6. Update player HP/Mana/SP in DB (persist combat state)
7. Send victory embed with XP gained, level-up info, and loot

### 16.2 Defeat

Player HP reaches 0.

**On Defeat:**
1. Delete combat session
2. Reset player HP to max_hp, Mana to max_mana, SP to max_sp (full heal on death)
3. Player keeps XP and level (no XP loss)
4. Player loses non-equipped inventory items (Stage 5 -- for now, no inventory impact)
5. Send defeat embed

### 16.3 Loot Rolling

```python
import random

def roll_loot(enemy_type):
    """Roll for loot drops from an enemy. Returns list of items."""
    loot_table = get_loot_table(enemy_type)
    if not loot_table:
        return []

    drops = []
    for entry in loot_table:
        # Each item in the table has a chance to drop
        # For simplicity: 50% chance per table entry to drop one item
        if random.random() < 0.5:
            drop = dict(entry)
            if "gold_min" in drop and "gold_max" in drop:
                drop["gold_value"] = random.randint(drop["gold_min"], drop["gold_max"])
            drops.append(drop)
            break  # One drop per enemy for now

    return drops
```

For Stage 3, loot is simplified:
- Roll one item from the enemy's loot table per enemy killed
- Valuable items add gold to the player
- Usable items (Rotten Meat Rations, Cracked Health Potion) are added to inventory
- Weapon/armor drops are deferred to Stage 5

---

## 17. Combat UI -- Embeds & Buttons

### 17.1 Combat Status Embed

```python
def combat_embed(player, combat_session, enemies, log_entries):
    """Build the combat status embed."""
    color = CLASS_COLORS.get(player["class"], discord.Color.greyple())

    embed = discord.Embed(
        title=f"Combat - Turn {combat_session['turn_number']}",
        color=color,
    )

    # Player Status
    hp_bar = _resource_bar(player["hp"], player["max_hp"])
    mana_bar = _resource_bar(player["mana"], player["max_mana"])
    sp_bar = _resource_bar(player["sp"], player["max_sp"])

    player_status = f"HP: {hp_bar} {player['hp']}/{player['max_hp']}\n"
    player_status += f"Mana: {mana_bar} {player['mana']}/{player['max_mana']}\n"
    player_status += f"SP: {sp_bar} {player['sp']}/{player['max_sp']}"

    # Add active buffs
    buffs = json.loads(combat_session["player_buffs"])
    if buffs:
        buff_str = ", ".join(f"{b['type']} ({b['remaining_turns']}t)" for b in buffs)
        player_status += f"\nBuffs: {buff_str}"

    # Add active debuffs
    debuffs = json.loads(combat_session["player_debuffs"])
    if debuffs:
        debuff_str = ", ".join(f"{d['type']} ({d['remaining_turns']}t)" for d in debuffs)
        player_status += f"\nDebuffs: {debuff_str}"

    embed.add_field(name=f"{player['character_name']}", value=player_status, inline=True)

    # Enemy Status
    enemy_status = ""
    for e in enemies:
        if not e["is_alive"]:
            enemy_status += f"~~{e['name']} (Lv.{e['level']})~~ DEAD\n"
            continue
        hp_bar = _resource_bar(e["hp"], e["max_hp"])
        enemy_status += f"{e['name']} (Lv.{e['level']}): {hp_bar} {e['hp']}/{e['max_hp']}\n"
        # Enemy debuffs
        e_debuffs = [d for d in json.loads(combat_session["enemy_debuffs"]) if d["enemy_id"] == e["id"]]
        if e_debuffs:
            enemy_status += f"  [{', '.join(d['type'] for d in e_debuffs)}]\n"

    embed.add_field(name="Enemies", value=enemy_status.strip(), inline=True)

    # Actions Available
    attacks_left = MAX_ATTACKS_PER_TURN - combat_session["attacks_used"]
    buffs_left = MAX_BUFFS_PER_TURN - combat_session["buffs_used"]
    items_left = MAX_ITEMS_PER_TURN - combat_session["items_used"]
    actions = f"Attack: {'available' if attacks_left > 0 else 'used'} | "
    actions += f"Buff: {'available' if buffs_left > 0 else 'used'} | "
    actions += f"Item: {'available' if items_left > 0 else 'used'}"
    embed.add_field(name="Actions", value=actions, inline=False)

    # Combat Log (last 5 entries)
    if log_entries:
        log_text = "\n".join(f"> {entry['message']}" for entry in log_entries[-5:])
        embed.add_field(name="Combat Log", value=log_text, inline=False)

    return embed
```

### 17.2 Resource Bar Helper

```python
def _resource_bar(current: int, maximum: int, length: int = 10) -> str:
    """Generate a text resource bar like '████████░░'."""
    if maximum <= 0:
        return "░" * length
    ratio = min(current / maximum, 1.0)
    filled = round(ratio * length)
    empty = length - filled
    return "█" * filled + "░" * empty
```

### 17.3 Combat Result Embeds

**Victory:**
```
Title: "Victory!"
Color: Green
Description: "You defeated {enemy_count} enemies!"

Field: "Rewards"
  XP: +{xp} (+{bonus}% perfect encounter bonus)
  Gold: +{gold}
  Loot: {item_name} (if any)

Field: "Level Up!" (if level-up occurred)
  (same as level_up_embed content)
```

**Defeat:**
```
Title: "Defeated!"
Color: Red
Description: "You were slain in combat. Your wounds have been healed."
```

**Flee:**
```
Title: "Escaped!"
Color: Orange
Description: "You fled from combat. No XP or loot gained."
(if took damage fleeing): "You took {damage} damage while fleeing!"
```

### 17.4 Combat Action View (Buttons + Select Menus)

```python
class CombatView(discord.ui.View):
    """Interactive combat action buttons."""

    def __init__(self, player_id: str, combat_session_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.player_id = player_id
        # Buttons are added dynamically based on available actions

    @discord.ui.button(label="Slash", style=discord.ButtonStyle.danger, emoji="⚔️", row=0)
    async def slash_button(self, interaction, button):
        # Process basic slash attack

    @discord.ui.button(label="Thrust", style=discord.ButtonStyle.danger, emoji="🗡️", row=0)
    async def thrust_button(self, interaction, button):
        # Process basic thrust attack

    @discord.ui.button(label="End Turn", style=discord.ButtonStyle.secondary, emoji="⏭️", row=0)
    async def end_turn_button(self, interaction, button):
        # End player turn, process enemy turn

    @discord.ui.button(label="Flee", style=discord.ButtonStyle.secondary, emoji="🏃", row=2)
    async def flee_button(self, interaction, button):
        # Attempt to flee

    # Skills select menu (row 1) -- populated dynamically
    # Items select menu (row 2) -- populated dynamically
```

**Button Disabling:**
- Slash/Thrust disabled when attack slot is used
- Skills select disabled when relevant slot is used (or no learned skills)
- Items select disabled when item slot is used (or no consumables)
- All buttons disabled when it's not the player's turn
- All buttons disabled when combat is over

**Ownership Check:** Every button callback must verify `interaction.user.id == player_id` to prevent other players from clicking buttons.

---

## 18. New Cog: combat.py -- Commands

### 18.1 `/fight`

```python
@app_commands.command(name="fight", description="Start a combat encounter")
async def fight(self, interaction):
```

**Validation:**
1. Player exists
2. Player is NOT already in combat (no existing combat_session)
3. Player HP > 0

**Flow:**
1. Roll enemy count and types (see Section 4.4)
2. Fetch enemy data from `enemies.json` at player level
3. Build enemies JSON list
4. Create combat session in DB
5. Process combat-start talents (Faithful Recovery, Charming Aura)
6. Send combat embed with CombatView buttons

### 18.2 `/attack`

```python
@app_commands.command(name="attack", description="Basic attack")
@app_commands.describe(attack_type="Type of attack")
@app_commands.choices(attack_type=[
    app_commands.Choice(name="Slash", value="slash"),
    app_commands.Choice(name="Thrust", value="thrust"),
])
async def attack(self, interaction, attack_type: app_commands.Choice[str]):
```

**Validation:**
1. Player is in combat
2. It's the player's turn
3. Attack slot available
4. Player is not stunned

**Flow:**
1. Calculate damage (see Section 7.1)
2. Select target (first living enemy, or specified)
3. Apply damage to target
4. Check for status effects (thrust stun)
5. Check for double strike (dexterity)
6. Mark attack slot as used
7. Check turn end / auto-end
8. Update combat embed

### 18.3 `/use`

```python
@app_commands.command(name="use", description="Use a combat skill")
@app_commands.describe(skill_name="Name of the skill to use")
async def use_skill(self, interaction, skill_name: str):
```

With autocomplete for learned skills (same pattern as `/learn` autocomplete).

### 18.4 `/item`

```python
@app_commands.command(name="item", description="Use a consumable item")
@app_commands.describe(item_name="Name of the item to use")
async def use_item(self, interaction, item_name: str):
```

With autocomplete for inventory consumables.

### 18.5 `/flee`

```python
@app_commands.command(name="flee", description="Attempt to flee from combat")
async def flee(self, interaction):
```

### 18.6 Combat State Resume

If a player has an active combat session and tries to use `/stats` or other non-combat commands, show a warning: "You are in combat! Use combat actions or `/flee` to escape."

If a player uses `/fight` with an existing session, resume: send the current combat embed.

---

## 19. Modifications to Existing Files

### 19.1 bot.py

```python
COGS = [
    "src.bot.cogs.general",
    "src.bot.cogs.character",
    "src.bot.cogs.leveling",
    "src.bot.cogs.combat",    # NEW
]
```

### 19.2 src/game/constants.py -- New Constants

```python
# --- Combat ---
UNARMED_DAMAGE_MIN = 5
UNARMED_DAMAGE_MAX = 10
UNARMED_DAMAGE_TYPE = "blunt"
THRUST_STUN_CHANCE = 10
THRUST_DAMAGE_MULTIPLIER = 0.7

# --- Enemy Spawning ---
ENEMY_TYPES = ["goblin", "feral_rat"]
ENEMY_COUNT_WEIGHTS = [(1, 60), (2, 30), (3, 10)]  # (count, weight_percent)

# --- Loot ---
LOOT_DROP_CHANCE = 0.5  # 50% chance per enemy to drop from loot table

# --- Combat Turn Limits ---
# Already exists: MAX_ATTACKS_PER_TURN = 1, MAX_BUFFS_PER_TURN = 1, MAX_ITEMS_PER_TURN = 1

# --- Status Effect Defaults ---
BURN_DAMAGE_PER_TURN = 5
BLEED_DAMAGE_PER_TURN = 3
POISON_DAMAGE_PER_TURN = 4
```

### 19.3 src/db/models.py -- Combat Session CRUD

```python
# --- Combat Sessions ---

async def create_combat_session(
    player_id: int, enemies: str,
) -> int:
    """Create a combat session. enemies is a JSON string."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO combat_sessions (player_id, enemies)
            VALUES (?, ?)""",
            (player_id, enemies),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_combat_session(player_id: int) -> Optional[dict]:
    """Fetch active combat session by player_id."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM combat_sessions WHERE player_id = ?", (player_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_combat_session(player_id: int, **fields) -> None:
    """Update combat session fields."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [player_id]
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE combat_sessions SET {set_clause} WHERE player_id = ?", values
        )
        await db.commit()
    finally:
        await db.close()


async def delete_combat_session(player_id: int) -> None:
    """Delete a combat session (on victory/defeat/flee)."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM combat_sessions WHERE player_id = ?", (player_id,)
        )
        await db.commit()
    finally:
        await db.close()
```

### 19.4 src/utils/embeds.py -- New Embeds

Add these functions (see Section 17 for full design):
- `combat_embed(player, combat_session, enemies, log_entries) -> discord.Embed`
- `combat_victory_embed(player_name, xp_gained, xp_bonus, gold_gained, loot, level_events) -> discord.Embed`
- `combat_defeat_embed() -> discord.Embed`
- `combat_flee_embed(damage_taken) -> discord.Embed`
- `_resource_bar(current, maximum, length=10) -> str`

---

## 20. Testing & Admin Commands

### 20.1 Admin Commands (in combat.py cog)

```python
@app_commands.command(name="admin_fight", description="[Admin] Fight a specific enemy")
@app_commands.describe(
    enemy_type="Enemy type",
    level="Enemy level",
    count="Number of enemies",
)
async def admin_fight(self, interaction, enemy_type: str, level: int, count: int = 1):
```

```python
@app_commands.command(name="admin_item", description="[Admin] Give yourself a consumable")
@app_commands.describe(item_id="Consumable item ID")
async def admin_item(self, interaction, item_id: str):
```

### 20.2 Manual Test Script

After building, verify these scenarios:

1. **Start combat:** `/fight` -- spawns 1-3 enemies at player level, shows combat embed with buttons
2. **Basic slash:** Click [Slash] or `/attack slash` -- deals damage, shows updated enemy HP
3. **Basic thrust:** `/attack thrust` -- deals less damage, check for stun proc
4. **Action limits:** Try second attack in same turn -- should be rejected
5. **End turn:** Click [End Turn] -- enemies attack, shows damage taken
6. **Multi-enemy:** Each enemy attacks sequentially, all damage shown in log
7. **Defeat:** Let enemies kill you -- shows defeat embed, HP reset to max
8. **Victory:** Kill all enemies -- shows victory embed with XP and loot
9. **Level-up from combat XP:** Kill enemies until XP triggers a level-up
10. **Perfect encounter:** Win without taking damage -- verify +10% XP bonus
11. **Flee success:** `/flee` with high agility -- verify escape
12. **Flee failure:** `/flee` -- verify enemies get free attacks
13. **Use skill in combat:** Level to 5, learn a skill, use it in combat
14. **Buff skill:** Use a buff skill -- verify it uses buff slot, not attack slot
15. **Status effect - stun:** Apply stun to enemy -- verify enemy skips turn
16. **Status effect - burn:** Apply burn -- verify damage each turn and expiry
17. **Double strike:** Set dexterity high (via admin_xp + allocate) -- verify proc
18. **Skill resource cost:** Use a skill -- verify SP/Mana is deducted
19. **Insufficient resources:** Try skill with not enough SP/Mana -- rejected
20. **Consumable in combat:** `/admin_item minor_healing_potion`, then `/item Minor Healing Potion` -- verify HP restore
21. **Existing session resume:** `/fight` while already in combat -- shows current combat
22. **Multi-hit skill:** Use Rampage (3 hits) or Shadow Step (2 hits) -- verify all hits
23. **AOE skill:** Use Whirlwind Attack against 3 enemies -- all take damage
24. **Dodge:** Set high agility, let enemy attack -- verify dodge procs occasionally
25. **Talent effects:** Select Battle Hardened, verify +5 HP per turn in combat

---

## 21. Validation Checklist

When Stage 3 is complete, verify:

**Core Combat:**
- [ ] `/fight` creates a combat encounter with 1-3 enemies at player level
- [ ] Combat embed shows player status, enemy status, action slots, and combat log
- [ ] Buttons (Slash, Thrust, End Turn, Flee) are functional and respond to clicks
- [ ] Only the combat owner can click buttons (ownership check)
- [ ] Basic Slash deals `weapon_damage + strength * 0.2` damage
- [ ] Basic Thrust deals reduced damage with 10% stun chance
- [ ] Action slot limits enforced: 1 attack, 1 buff, 1 item per turn
- [ ] Turn auto-ends when all action slots are used
- [ ] End Turn button skips remaining actions

**Enemy Turn:**
- [ ] All living enemies attack after player turn ends
- [ ] Enemy damage is random within their level-scaled range
- [ ] Stunned/frozen enemies skip their turn
- [ ] Charmed enemies attack other enemies (or skip if solo)
- [ ] Disarmed enemies deal 50% damage
- [ ] Debuffs reduce enemy damage appropriately

**Skills:**
- [ ] `/use` works for learned skills with autocomplete
- [ ] Skill costs (SP/Mana) are deducted correctly
- [ ] Skills with `damage_multiplier` deal the correct modified damage
- [ ] Multi-hit skills (hit_count) apply all hits
- [ ] AOE skills (enemies_3, all_enemies) hit multiple targets
- [ ] Buff skills use the buff action slot
- [ ] Attack skills use the attack action slot
- [ ] Skills with conditions (target_has_bleed, etc.) validate correctly
- [ ] once_per_combat skills can only be used once

**Status Effects:**
- [ ] Stun/freeze cause turn skip
- [ ] Burn/bleed/poison deal damage at turn start
- [ ] Buff durations count down and expire
- [ ] Main-stat-based durations calculate correctly
- [ ] Status effects with chance rolls only apply when the roll succeeds
- [ ] Cleanse (Purge) removes debuffs

**Talents:**
- [ ] Selected talents are active in combat
- [ ] Battle Hardened: +5 HP per turn
- [ ] Berserker Fury: damage scales with HP lost
- [ ] Evasion/Keen Reflexes: dodge bonus applied
- [ ] Mana Efficiency: reduced mana costs
- [ ] Inspiring Presence: buff values increased
- [ ] Quick Notes: extra action slot
- [ ] Quick Reload: extra basic attack at turn end

**Resolution:**
- [ ] Victory awards XP (sum of enemy rewards)
- [ ] Perfect encounter (+10% XP) triggers when damage_taken == 0
- [ ] XP grant triggers level-ups via existing leveling engine
- [ ] Loot drops from killed enemies
- [ ] Gold from valuable drops adds to player gold
- [ ] Usable drops added to inventory
- [ ] Defeat resets HP to max, no XP loss
- [ ] Flee calculates chance correctly (30% + agi * 1%)
- [ ] Failed flee: enemies get free attacks
- [ ] Combat session is deleted on victory/defeat/flee

**Dexterity Double Strike:**
- [ ] Triggers after attack actions with dex * 0.4 % chance
- [ ] Performs one free basic slash
- [ ] Does not consume an action slot
- [ ] Cannot double-trigger

**Consumables:**
- [ ] `/item` works with inventory consumables
- [ ] Resource restoration applies correctly (HP/Mana/SP)
- [ ] Consumable status effects apply (HoT, cleanse, etc.)
- [ ] Item is removed from inventory after use
- [ ] Item slot enforced (1 per turn)

**Integration:**
- [ ] Combat cog registered in bot.py
- [ ] No circular imports between combat.py, leveling.py, formulas.py
- [ ] Combat session persists across bot restarts (DB-backed)
- [ ] `/fight` while in combat resumes existing session
- [ ] All new code imports cleanly
