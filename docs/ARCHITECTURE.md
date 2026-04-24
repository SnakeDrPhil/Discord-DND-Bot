# Architecture & Developer Guide

Technical documentation for developers working on the Dungeon Crawler Discord bot.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Directory Structure](#2-directory-structure)
3. [Module Responsibilities](#3-module-responsibilities)
4. [Data Flow](#4-data-flow)
5. [Database Schema](#5-database-schema)
6. [Adding New Content](#6-adding-new-content)
7. [Adding New Commands](#7-adding-new-commands)
8. [Key Patterns](#8-key-patterns)
9. [Configuration & Constants](#9-configuration--constants)
10. [Logging](#10-logging)
11. [Error Handling](#11-error-handling)

---

## 1. Overview

The bot is a Python async application built on:

- **discord.py 2.x** -- slash commands, buttons, select menus
- **aiosqlite** -- async SQLite for persistent state
- **Standard library** -- `logging`, `json`, `asyncio`, `random`, `math`

All game logic lives in `src/game/` with no Discord imports, making it independently testable. The Discord layer (`src/bot/cogs/`) handles user interaction and calls into game logic.

---

## 2. Directory Structure

```
bot.py                          # Entry point
├── Logging setup (basicConfig)
├── Global error handler (on_app_command_error)
├── Cog loading loop
└── Bot startup (on_ready → init_db → sync commands)

src/bot/cogs/                   # Command handlers (9 cogs)
    ├── admin.py                # Admin tools for testing
    ├── character.py            # Character CRUD
    ├── combat.py               # Combat commands + interactive UI
    ├── dungeon.py              # Dungeon exploration + interactive UI
    ├── general.py              # Utility commands (ping, help, classinfo)
    ├── inventory.py            # Item management
    ├── leaderboard.py          # Leaderboard display
    ├── leveling.py             # Stat/skill/talent allocation
    └── shop.py                 # Shop purchasing

src/game/                       # Pure game logic (no Discord)
    ├── combat.py               # Enemy spawning, attack processing, rewards
    ├── constants.py            # All tuning values
    ├── dungeon.py              # Map loading, movement, scenarios, rendering
    ├── formulas.py             # Stat calculations (pure math)
    ├── items.py                # Procedural item generation
    └── leveling.py             # XP grants, level-up, resource scaling

src/db/                         # Persistence layer
    ├── database.py             # Schema, connection factory, migrations
    └── models.py               # CRUD operations (all async)

src/utils/                      # Shared utilities
    ├── data_loader.py          # JSON file loader with in-memory cache
    └── embeds.py               # All Discord embed builders

data/                           # Static game content (JSON files)
```

---

## 3. Module Responsibilities

### `src/game/constants.py`

Single source of truth for all tuning values: damage ranges, drop rates, regen rates, stat multipliers, floor configurations, shop prices, etc. All values are plain Python constants at module scope.

### `src/game/formulas.py`

Pure functions for stat-derived calculations. No state, no DB, no side effects. Functions like `calc_bonus_physical_damage(strength)` take a stat value and return a number.

### `src/game/combat.py`

Combat engine functions:
- `spawn_enemies(player_level, floor)` -- generates enemy groups from data files
- `spawn_boss(boss_type)` -- generates a boss encounter
- `process_basic_attack(atype, player, state)` -- resolves a Slash or Thrust
- `process_skill(skill, player, state)` -- resolves a skill use
- `process_item(item, player, state)` -- resolves a consumable use
- `process_enemy_turns(player, state)` -- resolves all enemy attacks
- `process_flee(player, state)` -- resolves a flee attempt
- `calculate_rewards(enemies, damage_taken, floor, player_class)` -- computes XP, gold, loot

All functions take state dicts and return `(updated_state, player_updates, messages)`.

### `src/game/dungeon.py`

Dungeon engine:
- `load_floor(floor_num)` -- loads floor data from maps.json
- `render_map(floor_data, visited, position)` -- generates emoji map string
- `get_valid_moves(floor_data, row, col)` -- returns valid movement directions
- `resolve_scenario(player, active_effects)` -- rolls and applies a scenario event
- `apply_regen(player)` -- calculates per-tile resource regeneration

### `src/game/items.py`

Procedural item generation:
- `roll_rarity()` -- weighted random rarity selection
- `generate_weapon(base_weapon, rarity)` -- creates a weapon with stats
- `generate_armor(base_armor, rarity)` -- creates armor with stats
- `generate_stat_affixes(rarity)` -- rolls random stat bonuses
- `generate_loot(enemies, floor, player_class)` -- generates combat loot
- `generate_boss_loot(boss_type, floor, player_class)` -- guaranteed minimum-rarity boss loot

### `src/game/leveling.py`

Level progression:
- `grant_xp(discord_id, amount)` -- adds XP, triggers level-ups, returns events
- `calc_resource_maxes(class_data, stats)` -- computes max HP/Mana/SP from stats
- `get_pending_skill_slots(level, learned_count)` -- available skill slots
- `get_pending_talent_slots(level, selected_count)` -- available talent slots

### `src/db/models.py`

Async CRUD for all 4 tables. Each function opens a connection, executes, and closes via try/finally. Key functions:
- `get_player(discord_id)` / `update_player(discord_id, **fields)`
- `add_inventory_item()` / `get_inventory()` / `equip_item()` / `remove_inventory_item()`
- `create_combat_session()` / `get_combat_session()` / `update_combat_session()`
- `create_dungeon_session()` / `get_dungeon_session()` / `update_dungeon_session()`
- `increment_player_stat()` / `get_leaderboard()`

### `src/utils/data_loader.py`

Loads JSON data files from `data/` with in-memory caching. First call reads from disk; subsequent calls return cached data. `clear_cache()` is available for testing.

### `src/utils/embeds.py`

All Discord embed builders. Functions take game data and return `discord.Embed` objects. This keeps display logic separate from command logic. Key embeds:
- `character_sheet_embed()` -- full character sheet with equipment and progression
- `combat_embed()` -- combat status with HP bars, actions, and combat log
- `dungeon_enter_embed()` / `dungeon_map_embed()` / `dungeon_move_embed()`
- `classinfo_embed()` -- detailed class breakdown
- `help_embed()` -- command reference

---

## 4. Data Flow

### Command Execution Flow

```
User → Discord → bot.py (slash command routing)
  → Cog handler (e.g., combat.py /fight)
    → models.py (load player, session data)
    → game logic (combat.py, items.py, etc.)
    → models.py (save updated state)
    → embeds.py (build response embed)
  → Discord → User
```

### Combat Flow

```
/fight or dungeon combat tile
  → spawn_enemies() or spawn_boss()
  → create_combat_session()
  → combat_embed() + CombatView (buttons/selects)
  → User presses button
    → _handle_attack/_handle_skill/_handle_item/_handle_flee
      → process_*() (game logic)
      → check_combat_end()
      → If ongoing: update_combat_session() → new embed + view
      → If victory: calculate_rewards() → grant_xp() → loot → victory embed
      → If defeat: restore HP → death embed (dungeon: lose items)
```

### Equipment Injection Pattern

Before any combat action, `_inject_equipment(player)` loads equipped items and injects:
- `player["_equipped_weapon"]` -- weapon damage data
- `player["_total_ar"]` -- total armor rating
- Stat bonuses added directly to player stat fields

This avoids passing equipment through every function -- the player dict is self-contained.

---

## 5. Database Schema

### players

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Internal ID |
| discord_id | TEXT UNIQUE | Discord user ID |
| character_name | TEXT | Display name |
| class | TEXT | Class ID (warrior, rogue, etc.) |
| level | INTEGER | Current level (1-20) |
| xp | INTEGER | Current XP |
| hp, max_hp | INTEGER | Current and max hit points |
| mana, max_mana | INTEGER | Current and max mana |
| sp, max_sp | INTEGER | Current and max stamina points |
| strength..charisma | INTEGER | 7 stat values |
| unspent_stat_points | INTEGER | Available stat points |
| learned_skills | TEXT (JSON) | Array of skill IDs |
| selected_talents | TEXT (JSON) | Array of talent IDs |
| current_floor | INTEGER | Highest floor available to enter |
| in_dungeon | INTEGER | Whether currently in dungeon |
| gold | INTEGER | Currency |
| enemies_killed | INTEGER | Lifetime kill counter |
| highest_floor | INTEGER | Deepest floor reached |
| bosses_killed | INTEGER | Boss kill counter |

### inventories

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Internal ID |
| player_id | INTEGER FK | Owner player |
| item_type | TEXT | "weapon", "armor", "consumable" |
| item_id | TEXT | Base item ID from data files |
| item_data | TEXT (JSON) | Full item data with generated stats |
| equipped | INTEGER | 0 or 1 |
| slot | TEXT | Equipment slot when equipped |
| quantity | INTEGER | Stack count (used for consumables) |

### combat_sessions

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Internal ID |
| player_id | INTEGER FK UNIQUE | One session per player |
| enemies | TEXT (JSON) | Array of enemy state objects |
| turn_number | INTEGER | Current turn |
| attacks_used..items_used | INTEGER | Action counters per turn |
| player_buffs..enemy_debuffs | TEXT (JSON) | Active status effects |
| damage_taken | INTEGER | Total damage for perfect bonus |
| combat_log | TEXT (JSON) | Recent action messages |

### dungeon_sessions

| Column | Type | Description |
|---|---|---|
| id | INTEGER PK | Internal ID |
| player_id | INTEGER FK UNIQUE | One session per player |
| floor | INTEGER | Current floor number |
| position_x, position_y | INTEGER | Current grid position |
| visited_tiles | TEXT (JSON) | Array of [row, col] pairs |
| active_effects | TEXT (JSON) | Curses and blessings |

---

## 6. Adding New Content

### Adding a New Enemy

1. Add an entry to `data/enemies.json`:
   ```json
   {"type": "skeleton", "level": 5, "damage_min": 15, "damage_max": 25, "hp": 120, "xp_reward": 80, "name": "Skeleton"}
   ```
2. Add a loot table entry in `data/loot_tables.json` (optional):
   ```json
   {"skeleton": [{"name": "Bone Fragment", "type": "usable", "sell_value": 5}]}
   ```
3. Add the type to `ENEMY_TYPES` in `constants.py` if it should spawn randomly.

### Adding a New Dungeon Floor

1. Add the floor layout to `data/maps.json` under the `floors` array:
   ```json
   {"floor": 6, "start": [0, 1], "exit": [8, 7], "tiles": [...]}
   ```
2. Add floor constants in `constants.py`:
   ```python
   FLOOR_ENEMY_LEVELS[6] = (16, 20)
   FLOOR_ENEMY_COUNTS[6] = (3, 5)
   FLOOR_NAMES[6] = "The Abyssal Depths"
   ```
3. Optionally add a boss: `FLOOR_BOSSES[6] = "boss_type"` + boss entry in enemies.json.

### Adding a New Class

1. Add class definition to `data/classes.json` with id, name, description, starting_stats, base_hp/mana/sp, main_stat, resource.
2. Add class skills to `data/skills.json` (10 recommended).
3. Add class talents to `data/talents.json` (5 recommended).
4. Add class-appropriate weapons to `data/weapons.json`.
5. Add armor access: include the class in armor entries' `allowed_classes`.
6. Add the class to choice lists in `character.py` and `general.py`.
7. Add a class color to `CLASS_COLORS` in `embeds.py`.

### Adding a New Skill

1. Add to `data/skills.json`:
   ```json
   {
     "id": "warrior_execute", "class": "warrior", "name": "Execute",
     "type": "attack", "resource": "sp", "cost": 20,
     "effect": "Deal 200% damage to enemies below 20% HP",
     "unlock_level": 15
   }
   ```
2. Add processing logic in `src/game/combat.py` `process_skill()` if the skill has unique mechanics (most skills use the generic damage/heal/buff framework).

### Adding a New Consumable

1. Add to `data/consumables.json`:
   ```json
   {"id": "super_potion", "name": "Super Potion", "category": "healing", "effect": "Restore 100 HP", "heal_hp": 100}
   ```
2. To make it buyable, add to `SHOP_PRICES` in `constants.py`:
   ```python
   SHOP_PRICES["super_potion"] = 75
   ```

---

## 7. Adding New Commands

### Creating a New Cog

1. Create `src/bot/cogs/my_cog.py`:
   ```python
   import logging
   import discord
   from discord import app_commands
   from discord.ext import commands

   logger = logging.getLogger("dungeon_bot.my_cog")

   class MyCog(commands.Cog):
       def __init__(self, bot: commands.Bot):
           self.bot = bot

       @app_commands.command(name="mycommand", description="Does a thing")
       async def my_command(self, interaction: discord.Interaction):
           await interaction.response.send_message("Hello!")

   async def setup(bot: commands.Bot):
       await bot.add_cog(MyCog(bot))
   ```

2. Add to COGS in `bot.py`:
   ```python
   COGS = [
       ...
       "src.bot.cogs.my_cog",
   ]
   ```

### Adding a Command to an Existing Cog

Add a new method to the cog class with `@app_commands.command()`. Follow these conventions:
- Always fetch the player first with `get_player(str(interaction.user.id))`
- Check for character existence and valid state (not in combat, not in dungeon, etc.)
- Use `error_embed()` for validation errors with `ephemeral=True`
- Use `success_embed()` for confirmations
- Add logging for significant actions

---

## 8. Key Patterns

### Connection-Per-Operation

Every database function in `models.py` follows this pattern:
```python
async def some_operation(...):
    db = await get_db()
    try:
        # execute queries
        await db.commit()
    finally:
        await db.close()
```

This is simple and safe for SQLite. No connection pooling needed.

### State Dict Pattern

Combat and dungeon state is stored as JSON in the database. The cog layer:
1. Loads the session from DB → dict
2. Parses JSON fields into native Python objects
3. Passes the state dict to game logic functions
4. Serializes the updated state back to JSON
5. Saves to DB

### Embed Builder Pattern

All embeds are built in `embeds.py`. Cog code never directly creates `discord.Embed`. This keeps display logic centralized and consistent.

### Interactive View Pattern

`CombatView` and `MovementView` are persistent `discord.ui.View` subclasses with buttons. They store the player ID for `interaction_check()` and delegate to cog methods via `interaction.client.get_cog()`.

---

## 9. Configuration & Constants

All game balance values are in `src/game/constants.py`. Key groups:

| Group | Examples |
|---|---|
| Resources | BASE_HP=100, BASE_MANA=50, BASE_SP=30, regen rates |
| Stat multipliers | STR=0.2, DEX=0.4, INT=0.2, AGI=0.2, WIS=0.4, CHA=0.2 |
| Leveling | STAT_POINTS_PER_LEVEL=5, skill/talent unlock intervals |
| Combat | UNARMED_DAMAGE=5-10, flee chance=30%, stun chance=10% |
| Equipment | Rarity tiers, damage ranges, drop rates, affix rules |
| Dungeon | Scenario chances, encounter rate=60%, curse mechanics |
| Floor scaling | Enemy level ranges and group sizes per floor |
| Shop | Consumable prices |
| Boss | Guaranteed loot rules |

Environment variables (`.env`):
- `BOT_TOKEN` -- Discord bot token (required)
- `DATABASE_PATH` -- SQLite file path (default: `dungeon_crawler.db`)

---

## 10. Logging

Logging is configured in `bot.py` with dual handlers:
- **File:** `bot.log` (UTF-8)
- **Console:** stderr

Logger hierarchy:
```
dungeon_bot              # Root bot logger (bot.py)
dungeon_bot.character    # Character events
dungeon_bot.combat       # Combat results
dungeon_bot.dungeon      # Dungeon events
dungeon_bot.shop         # Purchases
dungeon_bot.admin        # Admin commands (WARNING level)
dungeon_bot.db           # Database operations
```

### Log Levels Used

| Level | Usage |
|---|---|
| INFO | Normal events: startup, character creation, combat results, dungeon entry |
| WARNING | Admin command usage (for auditing) |
| ERROR | Unhandled exceptions (via global error handler) |

---

## 11. Error Handling

### Global Error Handler

`bot.py` registers `on_app_command_error` on the command tree. It catches:
- `CommandOnCooldown` -- friendly cooldown message
- `MissingPermissions` -- permission denied message
- All other `AppCommandError` -- logs full traceback, shows generic error embed

The handler checks `interaction.response.is_done()` to decide between `send_message` and `followup.send`, handling cases where the interaction was already responded to.

### Per-Command Validation

Each command validates its preconditions:
- Character exists
- Not in combat (when required)
- Not in dungeon (for shop)
- Sufficient resources (gold, inventory space, stat points)
- Valid input ranges

Validation failures return `error_embed()` with `ephemeral=True` so only the user sees the error.
