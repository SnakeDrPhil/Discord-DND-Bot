# Dungeon Crawler Discord Bot -- Multi-Stage Implementation Plan

**Based on:** `dungeon_crawler_combined_design_reference_page7_deleted.pdf`
**Prepared:** 2026-04-23

---

## Executive Summary

This plan breaks the Dungeon Crawler Discord Bot into **7 stages**, ordered by dependency and playability milestones. Each stage produces a working, testable slice of the game. The goal is to have a playable core loop as early as Stage 3, with later stages layering in depth.

### Unresolved Design Items (Must Decide Before or During Implementation)

These items are flagged in Section 9 of the design doc as undefined. Each is assigned to the stage where it becomes blocking.

| Item | Blocking Stage | Recommended Default |
|---|---|---|
| Class Starting Stats | Stage 1 | Define balanced starter arrays per class (see Stage 1 notes) |
| Main Stat Mapping per Class | Stage 1 | Warrior=Strength, Rogue=Dexterity, Mage=Intelligence, Ranger=Dexterity, Bard=Charisma, Cleric=Wisdom |
| Knowledge vs Intelligence | Stage 1 | Treat as a single stat: Intelligence. Remove "Knowledge" references |
| Damage Type Definitions | Stage 3 | Define Slash/Stab/Blunt as physical subtypes; Poison/Burn as DoTs; AOE as a targeting tag; Parry as a reaction mechanic |
| Flee Rules | Stage 3 | Base 30% flee chance, +1% per Agility point, enemies get a free attack on flee attempt |
| Scenario Frequency | Stage 4 | 60% chance per non-combat tile to trigger a scenario |
| Death & Curse Rules | Stage 4 | Death = run ends, keep XP, lose inventory. Curse = -10% to a random stat for next 5 combats |
| Spellcasting Speed | Stage 5 | Treat as turn-priority modifier: lower speed = act later in grouped combat |
| Goblin Equipment Drops | Stage 5 | Generate from existing weapon/armor tables at Poor/Common rarity |
| Weapon Drop % Gap (0.9%) | Stage 5 | Add 0.9% to Poor rarity (50% -> 50.9%) |

---

## Stage 1: Foundation -- Data Models & Bot Skeleton

**Goal:** Establish the project structure, database schema, Discord bot framework, and all static game data. No gameplay yet, but every data structure the game needs is in place and validated.

### 1.1 Project Setup
- Initialize Node.js (or Python) project with dependency management
- Select and configure Discord library (discord.js v14+ or discord.py)
- Set up environment config (.env for bot token, DB connection)
- Establish folder structure:
  ```
  src/
    bot/           -- Discord command handlers, event listeners
    game/          -- Core game engine (combat, movement, scenarios)
    data/          -- Static JSON data files
    db/            -- Database models and migrations
    utils/         -- Shared helpers (dice rolls, formatters, embed builders)
  data/
    characters.json
    skills.json
    talents.json
    weapons.json
    armor.json
    consumables.json
    enemies.json
    maps.json
  ```
- Set up linting, formatting, and a basic test runner

### 1.2 Static Game Data Files
Transcribe all design doc tables into structured JSON:

- **skills.json** -- All 60 class skills (10 per class) with fields: `class`, `name`, `type`, `cost`, `resource` (SP/Mana), `effect`, `duration_rule`, `target_rule`, `status_effects`, `unlock_level`
- **talents.json** -- All 30 passive talents (5 per class) with fields: `class`, `name`, `effect`, `passive_modifiers`, `unlock_level`
- **weapons.json** -- All weapons from class-themed lists with fields: `name`, `class_theme`, `hand_type`, `casting_flag`, `rarity`, `damage_range`, `stat_affixes`
- **armor.json** -- Full armor catalog (~150+ items) with fields: `name`, `armor_type` (Cloth/Leather/Heavy), `slot`, `ar_range`, `allowed_classes`, `rarity`, `stat_affixes`
- **consumables.json** -- All consumable items with fields: `name`, `category` (Healing/Mana/SP), `resource_restored`, `status_effect`, `duration`, `encounter_limit`
- **enemies.json** -- Goblin and Feral Rat scaling tables (levels 1-20) with fields: `type`, `level`, `damage_range`, `hp`, `xp_reward`, `loot_table`
- **maps.json** -- At minimum, Floor 1 tile grid transcribed from the design doc map references

### 1.3 Database Schema
Design persistent storage for player state:

- **players** -- `discord_id`, `character_name`, `class`, `level`, `xp`, `hp`, `max_hp`, `mana`, `max_mana`, `sp`, `max_sp`, `stats` (JSON: str/dex/int/agi/wis/end/cha), `unspent_stat_points`, `position`, `floor`, `created_at`
- **inventories** -- `player_id`, `item_type` (weapon/armor/consumable), `item_data` (JSON), `equipped` (bool), `slot`
- **combat_sessions** -- `player_id`, `enemy_data` (JSON), `turn_number`, `player_buffs`, `enemy_debuffs`, `state`
- **dungeon_sessions** -- `player_id`, `floor`, `tile_position`, `visited_tiles`, `active_effects`

### 1.4 Resolve Starting Stats
Define starting stat arrays for each class. Recommended baseline (total 35 points each):

| Stat | Warrior | Rogue | Mage | Ranger | Bard | Cleric |
|---|---|---|---|---|---|---|
| Strength | 8 | 4 | 3 | 5 | 4 | 6 |
| Dexterity | 4 | 8 | 3 | 7 | 5 | 3 |
| Intelligence | 3 | 3 | 8 | 4 | 5 | 6 |
| Agility | 5 | 7 | 4 | 6 | 5 | 3 |
| Wisdom | 3 | 3 | 6 | 4 | 5 | 8 |
| Endurance | 8 | 4 | 5 | 5 | 4 | 6 |
| Charisma | 4 | 6 | 6 | 4 | 7 | 3 |

### 1.5 Bot Skeleton
- Register the bot with Discord, set up intents (guilds, messages, interactions)
- Implement slash command registration framework
- Create basic embed builder utility for consistent message formatting
- Implement `/ping` and `/help` as connectivity tests

### Deliverables
- Runnable bot that connects to Discord and responds to `/ping`
- All static data files populated and schema-validated
- Database migrations ready to run
- No gameplay yet -- this is pure infrastructure

---

## Stage 2: Character Creation & Stat System

**Goal:** Players can create characters, choose a class, view their stats, and level up. The stat formulas from the design doc are fully implemented.

### 2.1 Character Creation Flow
- `/create <name> <class>` -- Creates a new character
  - Validate class choice (Warrior, Rogue, Mage, Ranger, Bard, Cleric)
  - Assign starting stats from Stage 1.4 table
  - Set starting resources: HP=100, Mana=50, SP=30 (adjust per class/endurance)
  - Save to database
  - Display character sheet embed

### 2.2 Character Sheet & Stats Display
- `/stats` or `/character` -- Rich embed showing:
  - Class, Level, XP progress bar
  - All 7 stats with their computed effects
  - Current HP/Mana/SP
  - Equipped items (empty at this stage)

### 2.3 Stat Formula Engine
Implement all stat multipliers and derived values from Section 3 of the design doc:

- **Strength** (0.2x) -- `bonus_physical_damage = strength * 0.2`
- **Dexterity** (0.4x) -- `double_strike_chance = dexterity * 0.4` (percent)
- **Intelligence** (0.2x dmg, 0.4x effect) -- `bonus_spell_damage = intelligence * 0.2`, `spell_effect_chance = intelligence * 0.4`
- **Agility** (0.2x) -- `dodge_chance = agility * 0.2`
- **Wisdom** (0.4x) -- `healing_bonus = wisdom * 0.4`, `buff_extend_chance = wisdom * 0.4`
- **Endurance** -- `bonus_hp = endurance * 10`, `bonus_mana = endurance * 5`, `bonus_sp = endurance * 5`
- **Charisma** (0.2x song, 0.4x buff) -- `song_bonus = charisma * 0.2`, `buff_duration_chance = charisma * 0.4`

### 2.4 Leveling System
- Implement XP thresholds table (levels 1-20) from Section 2
- `/levelup` or auto-trigger on XP gain:
  - Award 5 stat points per level
  - Flag skill unlock at levels 5, 10, 15, 20
  - Flag talent unlock at levels 10, 20
  - Show level-up embed with new rewards
- `/allocate <stat> <points>` -- Spend unspent stat points

### 2.5 Skill & Talent Selection
- `/skills` -- Show available skills for the player's class and level
- `/learn <skill_name>` -- Learn a skill at eligible levels (every 5 levels)
- `/talents` -- Show available talents
- `/chooseTalent <talent_name>` -- Select a talent at eligible levels (every 10 levels)
- Validate unlock level requirements

### Deliverables
- Players can create characters and see stat sheets
- Stat formulas compute correctly with test coverage
- Level-up flow works end-to-end (XP will be granted by combat in Stage 3)
- Skill/talent selection stores choices in DB

---

## Stage 3: Combat Engine (Core Loop)

**Goal:** Players can fight enemies in turn-based combat. This is the most critical stage -- it implements the heart of the game.

### 3.1 Combat State Machine
Design a state machine for combat flow:

```
IDLE -> ENCOUNTER -> PLAYER_TURN -> ENEMY_TURN -> [RESOLVE] -> PLAYER_TURN / VICTORY / DEFEAT
```

- Track per-combat state: turn number, active buffs/debuffs with remaining durations, extra-turn flags, skip-turn flags
- Support grouped enemies (Player > Enemy1 > Enemy2 > Enemy3 > Player)
- Support extra turns from skills/buffs (Player > Player > Enemy)

### 3.2 Basic Attack System
- `/attack slash` -- Basic Slash: damage scales with Strength and weapon slash damage
- `/attack thrust` -- Basic Thrust: low damage, chance to Stun
- Each attack consumes the player's attack action for the turn
- Implement armor damage reduction formula: `reduction = (AR / (AR + 500)) * 100`

### 3.3 Skill Usage in Combat
- `/use <skill_name>` -- Use a learned combat skill
  - Deduct SP or Mana cost
  - Apply skill effect (damage, buff, debuff)
  - Apply status effects with duration tracking
  - Respect "1 attack, 1 buff, 1 item per turn" rule

### 3.4 Spell Casting
- `/cast <spell_name>` -- For Mage, Bard, Cleric spell-style skills
  - Route through same skill engine but with Mana costs
  - Apply spell effect chance scaling from Intelligence

### 3.5 Item Usage in Combat
- `/item <item_name>` -- Use a consumable
  - Deduct from inventory
  - Apply healing, mana restore, SP restore, or temporary buff
  - Respect 1 item per turn limit

### 3.6 Enemy AI
- Enemies attack on their turn with damage randomly selected from their level-scaled range
- Implement basic enemy behavior (always attacks, no special abilities for Goblins/Feral Rats at this stage)

### 3.7 Status Effect System
Implement all referenced status effects:

| Effect | Behavior |
|---|---|
| Burn | Damage over time each turn |
| Poison | Damage over time each turn |
| Slow | Reduces dodge chance or delays turn |
| Stun | Skip next turn |
| Bleed | Damage over time, enables Backstab bonus |
| Freeze | Skip next turn (ice variant) |
| Blind | Reduces accuracy |
| Charm | Enemy attacks allies instead |

- Effects have duration in turns, tracked per-combat
- Wisdom-based buff extension chance applies

### 3.8 Combat Resolution
- **Victory:** Award XP (from enemy scaling table), trigger loot roll, heal/restore per post-combat regen
- **Defeat:** End dungeon run (specifics in Stage 4 death rules)
- **Flee:** Base 30% + Agility bonus, enemy gets free attack on attempt
- **Perfect Encounter Bonus:** +10% XP if player took no damage

### 3.9 Dexterity Double-Strike
- After each player action, check `dexterity * 0.4` percent chance
- If triggered, player gets one additional basic attack

### 3.10 Combat UI
- Rich embeds showing:
  - Player HP/Mana/SP bars
  - Enemy HP bar
  - Active buffs/debuffs with turn durations
  - Available actions (buttons or select menus)
  - Combat log of recent actions
- Use Discord buttons/select menus for action selection to streamline UX

### Deliverables
- Full turn-based combat against Goblins and Feral Rats
- All 60 class skills functional in combat
- Status effects, buff/debuff durations, extra turns all working
- XP awarded on victory, level-ups trigger naturally
- **The game is now playable in its most basic form**

---

## Stage 4: Dungeon Movement & Scenario System

**Goal:** Players explore a tile-based dungeon map, trigger scenarios, and encounter combat rooms. The full game loop is now connected.

### 4.1 Map Engine
- Load Floor 1 tile grid from `maps.json`
- Track player position and visited tiles
- `/move <direction>` (north/south/east/west) -- Move one tile
  - Validate movement against map boundaries and walls
  - Trigger per-tile resource regeneration: +5 SP, +10 Mana, +10 HP

### 4.2 Map Display
- `/map` -- Show the dungeon map as an embed
  - Render visited tiles, current position, unexplored areas as fog
  - Mark Scenario Rooms (SR) and Red (combat) rooms
  - Use emoji grid or generated image

### 4.3 Scenario Room System
- When entering a Scenario Room (SR), roll scenario type:
  - **Negative (33%):** Debuff, item loss, HP loss, Death, Curse
  - **Positive (33%):** Buff, item gain, HP gain, blessing (+5% stat for next combat)
  - **Neutral (34%):** Flavor text, nothing happens
- Implement scenario event tables with varied outcomes
- Display scenario narrative with outcome in an embed

### 4.4 Combat Room Triggers
- Red rooms guarantee a combat encounter
- Non-red tiles have a configurable chance (default 60%) to trigger a random encounter
- Enemy selection based on current floor level
- Chain into the Stage 3 combat engine

### 4.5 Dungeon Session Management
- `/enter` -- Begin a dungeon run on the current floor
- `/retreat` -- Leave dungeon, keep XP and items
- Track dungeon session state (position, visited tiles, active effects)
- Floor exit tile advances to next floor

### 4.6 Death & Curse Implementation
- **Death from combat:** Run ends. Player keeps XP and level. Lose all non-equipped inventory items. Return to floor start.
- **Death from scenario:** Same as combat death.
- **Curse:** -10% to a random stat for the next 5 combat encounters. Stack up to 3 curses.

### 4.7 Resource Regeneration
- Every tile movement restores: +5 SP, +10 Mana, +10 HP (capped at max)
- This is critical for pacing -- players heal between fights by exploring

### Deliverables
- Players explore a dungeon floor tile by tile
- Scenarios trigger with meaningful positive/negative/neutral outcomes
- Combat encounters trigger from map exploration
- Full game loop: explore -> encounter -> fight -> loot -> explore
- Death and curse mechanics functional

---

## Stage 5: Items, Equipment & Loot

**Goal:** Full item system with weapons, armor, consumables, rarity tiers, stat affixes, and loot drops from enemies.

### 5.1 Inventory System
- `/inventory` -- Show all items grouped by type (weapons, armor, consumables)
- `/inspect <item>` -- Show item details (stats, rarity, effects)
- Inventory capacity limit (recommend 20 slots to start)

### 5.2 Equipment System
- `/equip <item>` -- Equip a weapon or armor piece
  - Validate class restrictions (armor `allowed_classes`)
  - Validate slot conflicts (can't equip two chest pieces)
  - Apply stat bonuses from item affixes
  - Apply armor rating to damage reduction
- `/unequip <slot>` -- Remove equipment
- Equipment slots: Head, Shoulders, Chest, Gloves, Legs, Feet, Main Hand, Off Hand

### 5.3 Weapon System
- Implement weapon damage ranges by rarity (Poor 3-11 through Legendary 28-36)
- Weapon hand types affect combat: Two-hand vs One-hand + Off-hand
- Casting weapons enable spell damage bonuses

### 5.4 Armor Rating & Damage Reduction
- Formula: `damage_reduction_pct = (total_AR / (total_AR + 500)) * 100`
- AR from all equipped armor pieces sums together
- Rarity multipliers: Common 1.1-1.5x through Legendary 3-5x applied to base AR range

### 5.5 Item Stat Affixes
Implement the rarity-based stat affix system:

| Rarity | Affixes | Multipliers |
|---|---|---|
| Poor/Common | None | -- |
| Uncommon | 1 random stat | +1 base |
| Rare | 2 random stats | 2x main, 1x secondary |
| Epic | 3 random stats | 3x main, 2x secondary, 1x third |
| Legendary | 3 random stats | 3x main, 3x secondary, 2x third |

- Floor scaling: Base affix value increases by +1 every 5 floors (Uncommon goes from +1 on floors 1-5 to +2 on floors 6-10, etc.)

### 5.6 Loot Drop System
- On enemy kill, roll for drops:
  - Rarity roll: Poor 50.9%, Common 30%, Uncommon 10%, Rare 5%, Epic 4%, Legendary 0.1%
  - Item type roll: weapon, armor, or consumable
  - Generate item with appropriate rarity, stats, and affixes
- Enemy-specific drops (Goblin coins, trinkets; Feral Rat pelts, teeth) from design doc tables
- `/loot` -- Pick up items after combat

### 5.7 Consumable Usage
- Consumables usable in and out of combat
- `/use <consumable>` -- Use a consumable from inventory
- Track per-encounter limits (e.g., Healing Fruit: once per encounter, lasts 3 encounters)
- Implement all 15 consumables from the design doc

### Deliverables
- Full inventory and equipment management
- Weapons and armor affect combat stats
- Loot drops from all enemies with rarity system
- Stat affixes generate procedurally within design doc rules
- Consumables work in and out of combat

---

## Stage 6: Multi-Floor Progression & Content Expansion

**Goal:** Expand beyond Floor 1. Add floor progression, enemy variety scaling, and the systems needed for a longer-term play experience.

### 6.1 Multi-Floor Maps
- Design and implement Floors 2-5 tile layouts
- Each floor increases in size and complexity
- Floor themes affect scenario tables and enemy encounters
- Boss rooms on certain floors (design doc mentions dungeon tower system)

### 6.2 Enemy Scaling Implementation
- Enemies scale with floor level using the Level 1-20 tables
- Higher floors introduce higher-level Goblins and Feral Rats
- Prepare enemy framework for adding new enemy types beyond Goblin/Feral Rat

### 6.3 Floor-Based Item Scaling
- Items found on higher floors have higher base affix values
- Floor 1-5: base +1 per affix
- Floor 6-10: base +2 per affix
- Pattern continues per design doc rules

### 6.4 Economy System (If Applicable)
- Gold from enemy drops and valuable items
- `/shop` -- NPC shop to buy/sell items between dungeon runs
- Gold sink to prevent runaway inflation at higher levels

### 6.5 Leaderboard & Persistence
- `/leaderboard` -- Show top players by level, floor reached, enemies killed
- Long-term player progression tracking

### Deliverables
- Multiple dungeon floors playable
- Difficulty scales appropriately with floor level
- Items improve as players go deeper
- Long-term play loop is viable

---

## Stage 7: Polish, Balance & Quality of Life

**Goal:** Refine the player experience, balance combat numbers, and add quality-of-life features.

### 7.1 Balance Pass
- Playtest all 6 classes through levels 1-20
- Verify XP curve feels right (not too grindy, not too fast)
- Ensure no class is dramatically over/underpowered
- Validate damage formulas produce reasonable combat lengths (target: 3-8 turns per fight)
- Check that armor damage reduction curve feels impactful but not broken at high AR

### 7.2 Combat UX Polish
- Add combat animations via timed embed edits
- Improve action selection with Discord button/menu components
- Add combat summary at end of each fight
- Cooldown display for multi-turn abilities

### 7.3 Help & Onboarding
- `/help` -- Comprehensive help embed with command reference
- `/tutorial` -- Guided first-combat experience for new players
- `/classinfo <class>` -- Detailed class breakdown
- Contextual hints during gameplay

### 7.4 Error Handling & Edge Cases
- Graceful handling of all error states (no character, mid-combat commands, etc.)
- Rate limiting to prevent spam
- Concurrent session handling (one dungeon run per player)
- Database transaction safety for item/stat changes

### 7.5 Admin & Debug Tools
- `/admin reset <player>` -- Reset a player's character
- `/admin grant <player> <item/xp/level>` -- Dev tools for testing
- `/admin spawn <enemy> <level>` -- Force a combat encounter
- Logging for combat outcomes, drop rates, and error tracking

### 7.6 Performance
- Optimize database queries for hot paths (combat turns, movement)
- Cache static data (skills, talents, items) in memory
- Ensure bot can handle multiple concurrent players on different servers

### Deliverables
- Polished, balanced, production-ready bot
- New player onboarding flow
- Admin tooling for ongoing maintenance
- Performance validated under load

---

## Recommended Technology Stack

| Component | Recommendation | Rationale |
|---|---|---|
| Language | Python 3.11+ | Rapid iteration, strong Discord library support |
| Discord Library | discord.py (or Pycord) | Mature slash command and component support |
| Database | SQLite (dev) / PostgreSQL (prod) | SQLite for fast local dev, Postgres for multi-server production |
| ORM | SQLAlchemy or Tortoise ORM | Async-friendly, migration support |
| Data Format | JSON for static data | Easy to edit, version-control friendly |
| Hosting | Any VPS or cloud VM | Bot needs persistent uptime |

---

## Stage Dependency Graph

```
Stage 1 (Foundation)
   |
   v
Stage 2 (Characters & Stats)
   |
   v
Stage 3 (Combat Engine)  <-- First playable milestone
   |
   v
Stage 4 (Dungeon & Scenarios)  <-- Full game loop
   |
   v
Stage 5 (Items & Loot)  <-- Full game depth
   |
   v
Stage 6 (Multi-Floor & Expansion)
   |
   v
Stage 7 (Polish & Balance)
```

Each stage builds directly on the previous one. Stages cannot be reordered, but work within a stage can be parallelized (e.g., data entry and schema design in Stage 1 can happen simultaneously).

---

## Estimated Scope Per Stage

| Stage | Complexity | Key Risk |
|---|---|---|
| 1 - Foundation | Medium | Getting data entry right for ~200+ items |
| 2 - Characters | Low-Medium | Stat formula edge cases |
| 3 - Combat | **High** | State machine complexity, 60 unique skills, status effect interactions |
| 4 - Dungeon | Medium | Map rendering, scenario variety |
| 5 - Items | Medium-High | Procedural affix generation, rarity balance |
| 6 - Expansion | Medium | Content creation, scaling validation |
| 7 - Polish | Medium | Balance tuning requires extensive playtesting |

**Stage 3 is the highest-risk stage.** It implements the most complex systems and has the most interdependencies. Recommend breaking it into 2-week sprints with frequent playtesting.
