# Dungeon Crawler Discord Bot

A fully-featured dungeon crawler RPG played through Discord slash commands. Create a character, explore procedurally-generated dungeons, fight enemies in tactical turn-based combat, collect loot, and climb the leaderboard.

## Features

- **6 Playable Classes** -- Warrior, Rogue, Mage, Ranger, Bard, Cleric, each with unique skills, talents, and playstyles
- **Turn-Based Combat** -- Tactical combat with attacks, skills, items, buffs/debuffs, and flee mechanics
- **Dungeon Exploration** -- 5 dungeon floors with tile-based movement, scenario rooms, traps, treasures, and a boss encounter
- **Equipment System** -- Procedurally-generated weapons and armor across 6 rarity tiers (Poor to Legendary) with stat affixes
- **Skill & Talent Trees** -- 10 skills and 5 talents per class, unlocked through leveling
- **Shop System** -- Buy consumables between dungeon runs
- **Leaderboards** -- Compete for highest level, deepest floor, and most kills
- **Interactive UI** -- Button-based movement and combat, select menus for skills and items

## Quick Start

### Prerequisites

- Python 3.9+
- A [Discord bot token](https://discord.com/developers/applications)

### Installation

```bash
git clone https://github.com/SnakeDrPhil/Discord-DND-Bot.git
cd Discord-DND-Bot
pip install -r requirements.txt
```

### Configuration

Copy the environment file and add your bot token:

```bash
cp .env.example .env
```

Edit `.env`:

```
BOT_TOKEN=your_discord_bot_token_here
DATABASE_PATH=dungeon_crawler.db
```

### Running

```bash
python bot.py
```

The bot will:
1. Initialize the SQLite database
2. Load all cog modules
3. Sync slash commands with Discord
4. Begin logging to `bot.log` and console

### Inviting the Bot

When creating your bot in the Discord Developer Portal, enable the following:
- **Bot permissions:** Send Messages, Embed Links, Use Slash Commands
- **Privileged intents:** Message Content

Use the OAuth2 URL generator with the `bot` and `applications.commands` scopes.

## Commands

### Getting Started

| Command | Description |
|---|---|
| `/create <name> <class>` | Create a new character |
| `/classinfo <class>` | View detailed class information |
| `/help` | Show all available commands |

### Character

| Command | Description |
|---|---|
| `/stats` | View your full character sheet (equipment, stats, progression) |
| `/inventory` | View your items |
| `/inspect <item>` | View detailed item stats |
| `/equip <item>` | Equip a weapon or armor piece |
| `/unequip <slot>` | Remove equipment from a slot |
| `/sell <item>` | Sell an item for gold |
| `/use_item <item>` | Use a consumable outside combat |
| `/allocate <stat> <points>` | Spend unspent stat points |

### Progression

| Command | Description |
|---|---|
| `/skills` | View available class skills |
| `/learn <skill>` | Learn a new skill (requires skill slot) |
| `/talents` | View available passive talents |
| `/choose_talent <talent>` | Select a passive talent (requires talent slot) |

### Dungeon

| Command | Description |
|---|---|
| `/enter [floor]` | Enter the dungeon (defaults to highest unlocked floor) |
| `/move <direction>` | Move north/south/east/west (or use buttons) |
| `/map` | View the dungeon map with exploration progress |
| `/retreat` | Leave the dungeon safely, keeping all items |

### Combat

| Command | Description |
|---|---|
| `/fight` | Start a random combat encounter |
| `/attack <type>` | Basic attack (Slash or Thrust) |
| `/use <skill>` | Use a learned combat skill |
| `/item <name>` | Use a consumable item in combat |
| `/flee` | Attempt to escape combat |

### Shop & Leaderboard

| Command | Description |
|---|---|
| `/shop` | Browse the consumable shop |
| `/buy <item> [quantity]` | Buy items from the shop |
| `/sell_all` | Sell all unequipped items for gold |
| `/leaderboard [category]` | View rankings (Level, Highest Floor, Enemies Killed) |

### Admin / Testing

| Command | Description |
|---|---|
| `/admin_fight <type> <level> [count]` | Spawn specific enemies for testing |
| `/admin_item <item_id>` | Give yourself a consumable |
| `/admin_give_weapon <id> <rarity>` | Give a weapon at a specific rarity |
| `/admin_give_armor <id> <rarity>` | Give armor at a specific rarity |
| `/admin_xp <amount>` | Grant XP |
| `/admin_teleport <row> <col>` | Teleport to a dungeon tile |
| `/admin_scenario <type>` | Force a scenario event |
| `/admin_set_floor <floor>` | Set your current floor |
| `/admin_set_gold <amount>` | Set your gold amount |
| `/admin_set_level <level>` | Set your level |
| `/admin_heal` | Fully restore HP, Mana, and SP |
| `/admin_clear_effects` | Clear all dungeon curses/blessings |
| `/admin_boss [boss_type]` | Force a boss encounter |

## Game Guide

### Classes

| Class | Main Stat | Resource | Playstyle |
|---|---|---|---|
| Warrior | Strength | SP | Heavy melee damage, high durability, heavy armor |
| Rogue | Dexterity | SP | Fast strikes, DoTs (bleed/poison), dodge-focused |
| Mage | Intelligence | Mana | Elemental spells, AoE damage, crowd control |
| Ranger | Dexterity | SP | Ranged attacks, traps, nature-based abilities |
| Bard | Charisma | Mana | Buffs, debuffs, songs that affect all combatants |
| Cleric | Wisdom | Mana | Healing, shields, holy damage, party support |

### Stats

| Stat | Effect |
|---|---|
| **Strength (STR)** | +0.2 physical damage per point |
| **Dexterity (DEX)** | +0.4% double strike chance per point |
| **Intelligence (INT)** | +0.2 spell damage per point |
| **Agility (AGI)** | +0.2% dodge chance per point |
| **Wisdom (WIS)** | +0.4% healing bonus per point |
| **Endurance (END)** | +10 HP, +5 Mana, +5 SP per point |
| **Charisma (CHA)** | +0.2 song power per point |

You receive **5 stat points per level** to allocate freely.

### Leveling

- Gain XP from combat victories. Perfect encounters (no damage taken) grant +10% bonus XP.
- Every **5 levels**, a new skill slot unlocks.
- Every **10 levels**, a new talent slot unlocks.

### Equipment

Items drop from combat encounters with one of 6 rarity tiers:

| Rarity | Drop Rate | Stat Affixes |
|---|---|---|
| Poor | 50.9% | 0 |
| Common | 30.0% | 0 |
| Uncommon | 10.0% | 1 |
| Rare | 5.0% | 2 |
| Epic | 4.0% | 3 |
| Legendary | 0.1% | 3 (higher values) |

**Equipment slots:** Head, Shoulders, Chest, Gloves, Legs, Feet, Main Hand, Off Hand

**Armor Rating** reduces incoming damage: `AR / (AR + 500) * 100`%. For example, 100 AR = 16.7% reduction.

### Dungeon Floors

| Floor | Name | Enemies | Boss |
|---|---|---|---|
| 1 | The Goblin Warrens | Lv. 1-3 | -- |
| 2 | The Winding Tunnels | Lv. 3-5 | -- |
| 3 | The Rat King's Domain | Lv. 5-8 | -- |
| 4 | The Deep Halls | Lv. 8-12 | -- |
| 5 | The Goblin King's Throne | Lv. 12-16 | Goblin King |

Each floor has tile types: paths, combat rooms, scenario rooms, and the exit. Scenario rooms can be positive (treasure, healing), negative (traps, curses), or neutral (lore, merchants).

**Death penalty:** Dying in a dungeon loses all unequipped inventory items. XP, level, gold, and equipped items are kept.

### Combat System

Each turn you get:
- **1 Attack action** -- basic attack or offensive skill
- **1 Buff action** -- defensive/buff skill
- **1 Item action** -- use a consumable

Turns auto-end when all actions are used. Enemies attack after your turn ends.

**Status effects:** Burn (5/turn), Bleed (3/turn), Poison (4/turn), Stun, Charm, and various buffs.

### Inventory

- **Capacity:** 20 slots
- **Overflow:** When inventory is full, new loot is auto-sold for gold
- `/sell_all` sells all unequipped items at once

## Project Structure

```
Discord-DND-Bot/
├── bot.py                      # Entry point, logging, error handler
├── requirements.txt            # Python dependencies
├── .env.example                # Environment template
│
├── src/
│   ├── bot/cogs/               # Discord command modules
│   │   ├── admin.py            # Admin/testing commands
│   │   ├── character.py        # /create, /stats, /delete
│   │   ├── combat.py           # /fight, /attack, /use, /item, /flee
│   │   ├── dungeon.py          # /enter, /move, /map, /retreat
│   │   ├── general.py          # /ping, /help, /classinfo
│   │   ├── inventory.py        # /inventory, /equip, /inspect, etc.
│   │   ├── leaderboard.py      # /leaderboard
│   │   ├── leveling.py         # /allocate, /skills, /learn, /talents
│   │   └── shop.py             # /shop, /buy, /sell_all
│   │
│   ├── db/                     # Database layer
│   │   ├── database.py         # Schema, connection, migrations
│   │   └── models.py           # CRUD operations
│   │
│   ├── game/                   # Core game logic (no Discord dependencies)
│   │   ├── combat.py           # Combat engine, spawning, rewards
│   │   ├── constants.py        # All game constants and tuning values
│   │   ├── dungeon.py          # Dungeon engine, map rendering, scenarios
│   │   ├── formulas.py         # Stat formulas and calculations
│   │   ├── items.py            # Procedural item generation, loot
│   │   └── leveling.py         # XP, level-up, resource scaling
│   │
│   └── utils/                  # Shared utilities
│       ├── data_loader.py      # JSON data file loader with caching
│       └── embeds.py           # All Discord embed builders
│
└── data/                       # Static game data (JSON)
    ├── armor.json              # 163 armor pieces
    ├── classes.json             # 6 class definitions
    ├── consumables.json         # 15 consumable items
    ├── enemies.json             # 41 enemy types + bosses
    ├── loot_tables.json         # Enemy-specific loot tables
    ├── maps.json                # 5 dungeon floor layouts
    ├── scenarios.json           # Dungeon scenario events
    ├── skills.json              # 59 class skills
    ├── talents.json             # 30 class talents
    ├── weapons.json             # 59 weapon types
    └── xp_thresholds.json       # XP requirements per level
```

## Architecture

### Technology Stack

- **Python 3.9+** with asyncio
- **discord.py 2.x** -- slash commands, buttons, select menus, embeds
- **aiosqlite** -- async SQLite database access
- **python-dotenv** -- environment variable management

### Design Patterns

- **Cog architecture** -- each command group is a self-contained cog module loaded by `bot.py`
- **Game logic separation** -- `src/game/` contains pure game logic with no Discord dependencies, making it testable independently
- **Static data files** -- all game content (classes, skills, enemies, maps) lives in `data/*.json`, loaded and cached by `data_loader.py`
- **Embed builders** -- all Discord embeds are built in `embeds.py`, keeping display logic separate from command logic
- **Connection-per-operation** -- each database function opens, operates, and closes its own connection via try/finally

### Database

SQLite with 4 tables:
- **players** -- character data, stats, progression tracking
- **inventories** -- items with equipment state and slot tracking
- **combat_sessions** -- active combat state (enemies, buffs, turn tracking)
- **dungeon_sessions** -- active dungeon state (floor, position, visited tiles, effects)

### Logging

All events are logged to `bot.log` and console using Python's `logging` module:
- **INFO** -- bot startup, character creation, combat results, dungeon events, purchases
- **WARNING** -- admin command usage
- **ERROR** -- unhandled exceptions with full tracebacks

### Error Handling

A global error handler (`on_app_command_error`) catches all unhandled slash command errors and returns a user-friendly embed instead of a raw Discord error. Expired interactions are handled gracefully.

## Game Content Summary

| Content Type | Count |
|---|---|
| Classes | 6 |
| Skills | 59 |
| Talents | 30 |
| Weapons | 59 |
| Armor Pieces | 163 |
| Consumables | 15 |
| Enemy Types | 41 |
| Dungeon Floors | 5 |
| Rarity Tiers | 6 |
| Slash Commands | 35+ |

## License

This project is for personal/educational use.
