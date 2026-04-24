# Stage 4 Workbook -- Dungeon Movement & Scenario System

**Purpose:** Comprehensive build spec for Stage 4. Players explore a tile-based dungeon map, trigger scenarios (positive/negative/neutral), encounter random and guaranteed combat, regenerate resources between tiles, and progress through floors. The full game loop is connected: explore -> encounter -> fight -> loot -> explore.

---

## Table of Contents

1. [What Already Exists](#1-what-already-exists)
2. [Files to Create](#2-files-to-create)
3. [Files to Modify](#3-files-to-modify)
4. [Design Decisions](#4-design-decisions)
5. [Map Engine](#5-map-engine)
6. [Dungeon Session Data Model](#6-dungeon-session-data-model)
7. [Movement System](#7-movement-system)
8. [Resource Regeneration](#8-resource-regeneration)
9. [Scenario System](#9-scenario-system)
10. [Scenario Event Tables](#10-scenario-event-tables)
11. [Combat Encounter Triggers](#11-combat-encounter-triggers)
12. [Fog of War & Map Display](#12-fog-of-war--map-display)
13. [Floor Progression](#13-floor-progression)
14. [Death & Curse Mechanics](#14-death--curse-mechanics)
15. [Talent Interactions](#15-talent-interactions)
16. [Dungeon UI -- Embeds](#16-dungeon-ui----embeds)
17. [New Cog: dungeon.py -- Commands](#17-new-cog-dungeonpy----commands)
18. [Modifications to Existing Files](#18-modifications-to-existing-files)
19. [Testing & Admin Commands](#19-testing--admin-commands)
20. [Validation Checklist](#20-validation-checklist)

---

## 1. What Already Exists

These Stage 1-3 components are ready to use:

| Component | Location | What it provides |
|---|---|---|
| Map data (Floor 1) | `data/maps.json` | 7x7 tile grid with tile types: start, path, wall, sr, combat, exit |
| Data loader | `src/utils/data_loader.py` | `get_floor(floor_number)` already implemented |
| Constants | `src/game/constants.py` | `REGEN_HP_PER_TILE=10`, `REGEN_MANA_PER_TILE=10`, `REGEN_SP_PER_TILE=5`, `SCENARIO_NEGATIVE_CHANCE=33`, `SCENARIO_POSITIVE_CHANCE=33`, `SCENARIO_NEUTRAL_CHANCE=34`, `ENCOUNTER_CHANCE_PER_TILE=60` |
| DB schema | `src/db/database.py` | `dungeon_sessions` table already defined with columns: `player_id`, `floor`, `position_x`, `position_y`, `visited_tiles` (JSON), `active_effects` (JSON) |
| Player fields | `src/db/database.py` | Players table has `current_floor`, `position_x`, `position_y`, `in_dungeon`, `gold` columns |
| DB models | `src/db/models.py` | `get_player()`, `update_player()`, `get_inventory()`, `add_inventory_item()`, `remove_inventory_item()` |
| Combat engine | `src/game/combat.py` | `spawn_enemies()` to generate encounters on combat tiles |
| Combat cog | `src/bot/cogs/combat.py` | `/fight` command to start combat -- will chain from dungeon encounters |
| Embeds | `src/utils/embeds.py` | `error_embed()`, `success_embed()`, `info_embed()`, `CLASS_COLORS` |
| Enemies data | `data/enemies.json` | Goblin + Feral Rat, levels 1-20 |
| Consumables | `data/consumables.json` | 15 consumables for scenario rewards |
| Loot tables | `data/loot_tables.json` | Goblin + Feral Rat drop tables |
| Bot entry | `bot.py` | COGS list to extend |

---

## 2. Files to Create

| File | Purpose |
|---|---|
| `src/game/dungeon.py` | Dungeon engine: map loading, movement validation, scenario resolution, encounter triggers, fog of war |
| `src/bot/cogs/dungeon.py` | Dungeon cog: `/enter`, `/move`, `/map`, `/retreat` commands with interactive buttons |
| `data/scenarios.json` | Scenario event tables: positive, negative, neutral outcomes with specific effects |

---

## 3. Files to Modify

| File | Change |
|---|---|
| `bot.py` | Add `"src.bot.cogs.dungeon"` to COGS list |
| `src/db/models.py` | Add dungeon session CRUD: `create_dungeon_session()`, `get_dungeon_session()`, `update_dungeon_session()`, `delete_dungeon_session()` |
| `src/game/constants.py` | Add curse and death constants |
| `src/utils/embeds.py` | Add dungeon embeds: `dungeon_map_embed()`, `scenario_embed()`, `dungeon_enter_embed()`, `dungeon_retreat_embed()` |
| `src/utils/data_loader.py` | Add `get_scenarios()` loader |
| `src/bot/cogs/combat.py` | Modify `/fight` to support dungeon-triggered combat (auto-start from tile entry) |

---

## 4. Design Decisions

### 4.1 Resolved from Implementation Plan

| Decision | Resolution |
|---|---|
| Scenario Frequency | 60% chance per non-combat, non-SR path tile (constant already set) |
| Death Rules | Death = run ends, keep XP/level, lose all non-equipped inventory items, return to floor start |
| Curse Rules | -10% to a random stat for the next 5 combat encounters, stack up to 3 curses |
| Fog of War | Tiles are hidden until visited; visited tiles remain revealed for the session |

### 4.2 New Decisions for Stage 4

| Decision | Resolution | Rationale |
|---|---|---|
| SR tiles: re-triggerable? | No. Scenario rooms trigger once per dungeon session. Revisiting shows "already explored" | Prevents farming scenario rooms for buffs/items |
| Combat tiles: re-triggerable? | No. Guaranteed combat rooms trigger once per session. Revisiting is safe | Same reasoning, prevents XP farming via repeated room entry |
| Path tile encounters: re-triggerable? | No. Each path tile rolls for encounter once on first visit only | Consistent with SR/combat rooms |
| Encounter level scaling | Enemies spawn at `floor * 1` level (Floor 1 = Level 1 enemies) | Simple scaling, matches enemy data range 1-20 |
| Dungeon session persistence | Active dungeon session persists across bot restarts via `dungeon_sessions` table | Player can continue where they left off |
| Movement UI | Direction buttons (N/S/E/W) displayed with the map embed | Faster than typing `/move north` each time |
| Curse tracking | Store curses in `active_effects` JSON on dungeon session, decrement on combat completion | Curses persist across encounters within the dungeon run |
| Scenario room revisit display | Show "This room has already been explored" with no effect | Clear feedback to player |
| Exit without full clear | Players can reach the exit without clearing all rooms | Not forced to explore every tile |

---

## 5. Map Engine

### 5.1 Floor Data Structure

From `data/maps.json`:
```json
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
```

### 5.2 Tile Types

| Type | Symbol | Behavior |
|---|---|---|
| `start` | `S` | Player spawn point. Safe tile, no encounters |
| `path` | `.` | Normal walkable tile. 60% chance to trigger random encounter on first visit |
| `wall` | `#` | Impassable. Movement blocked |
| `sr` | `?` | Scenario Room. Triggers a scenario event on first visit |
| `combat` | `!` | Combat Room. Guaranteed combat encounter on first visit |
| `exit` | `E` | Floor exit. Advances to next floor when entered |

### 5.3 Coordinate System

- Grid coordinates: `(row, col)` where `(0,0)` is top-left
- Row increases downward (south), Column increases rightward (east)
- Direction mapping:
  - North: `(row - 1, col)`
  - South: `(row + 1, col)`
  - East: `(row, col + 1)`
  - West: `(row, col - 1)`

### 5.4 Map Engine Functions

```python
def load_floor(floor_number: int) -> dict:
    """Load floor data from maps.json. Returns None if floor doesn't exist."""

def get_tile(floor_data: dict, row: int, col: int) -> str | None:
    """Get tile type at (row, col). Returns None if out of bounds."""

def is_passable(tile_type: str) -> bool:
    """Returns True if the tile can be walked on (not wall, not None)."""

def get_valid_moves(floor_data: dict, row: int, col: int) -> dict[str, tuple[int, int]]:
    """Return dict of valid directions -> (new_row, new_col) from current position."""

def get_adjacent_tiles(floor_data: dict, row: int, col: int) -> dict:
    """Return dict of direction -> tile_type for all 4 directions (including walls/OOB)."""
```

---

## 6. Dungeon Session Data Model

### 6.1 Existing Schema (`dungeon_sessions` table)

```sql
CREATE TABLE IF NOT EXISTS dungeon_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE,
    floor INTEGER NOT NULL DEFAULT 1,
    position_x INTEGER NOT NULL DEFAULT 0,  -- row
    position_y INTEGER NOT NULL DEFAULT 0,  -- col
    visited_tiles TEXT NOT NULL DEFAULT '[]',
    active_effects TEXT NOT NULL DEFAULT '[]',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);
```

### 6.2 `visited_tiles` JSON Format

Array of `[row, col]` pairs representing tiles the player has entered:
```json
[[0,0], [0,1], [0,2], [1,0]]
```

### 6.3 `active_effects` JSON Format

Array of active effects from scenarios and curses:
```json
[
  {"type": "curse", "stat": "strength", "value": -10, "unit": "percent", "combats_remaining": 5},
  {"type": "blessing", "stat": "dexterity", "value": 5, "unit": "percent", "combats_remaining": 1},
  {"type": "buff", "stat": "max_hp", "value": 10, "combats_remaining": 3}
]
```

### 6.4 DB Model Functions to Add

```python
async def create_dungeon_session(player_id: int, floor: int = 1,
                                  start_x: int = 0, start_y: int = 0) -> int:
    """Create a dungeon session. Returns session ID."""

async def get_dungeon_session(player_id: int) -> Optional[dict]:
    """Fetch active dungeon session by player_id. Returns None if not in dungeon."""

async def update_dungeon_session(player_id: int, **fields) -> None:
    """Update dungeon session fields (position, visited_tiles, active_effects)."""

async def delete_dungeon_session(player_id: int) -> None:
    """Delete dungeon session (on retreat, death, or floor exit)."""
```

### 6.5 Player Table Fields Used

| Field | Usage |
|---|---|
| `current_floor` | Tracks highest floor reached (persistent across sessions) |
| `in_dungeon` | 1 if player has active dungeon session, 0 otherwise |
| `gold` | Modified by scenarios (gold gain/loss) |

---

## 7. Movement System

### 7.1 Movement Flow

```
Player issues /move <direction> (or clicks direction button)
    |
    v
Validate: player in dungeon? -> No -> error
    |
    v
Validate: player in combat? -> Yes -> error "Finish combat first"
    |
    v
Calculate target tile (row, col) from direction
    |
    v
Validate: target in bounds and passable? -> No -> "You can't go that way!"
    |
    v
Apply resource regeneration (HP/Mana/SP)
    |
    v
Update position in dungeon_session
    |
    v
Check if tile already visited -> Yes -> Show map, no event
    |
    v
Add tile to visited_tiles
    |
    v
Resolve tile type:
  - path:   Roll encounter chance (60%) -> combat or safe
  - sr:     Trigger scenario event
  - combat: Trigger guaranteed combat
  - exit:   Floor progression
  - start:  Safe (no event)
    |
    v
Display result embed + updated map + movement buttons
```

### 7.2 Direction Validation

```python
DIRECTION_DELTAS = {
    "north": (-1, 0),
    "south": (1, 0),
    "east": (0, 1),
    "west": (0, -1),
}

def validate_move(floor_data: dict, current_row: int, current_col: int,
                  direction: str) -> tuple[bool, int, int, str]:
    """
    Returns (valid, new_row, new_col, tile_type).
    valid=False if out of bounds or wall.
    """
```

### 7.3 Movement Processing

```python
def process_move(floor_data: dict, session: dict, direction: str,
                 player: dict) -> dict:
    """
    Process a movement action. Returns:
    {
        "success": bool,
        "new_row": int, "new_col": int,
        "tile_type": str,
        "first_visit": bool,
        "regen": {"hp": int, "mana": int, "sp": int},
        "message": str,
    }
    """
```

---

## 8. Resource Regeneration

### 8.1 Per-Tile Regeneration

Every successful tile movement restores resources (capped at max):

| Resource | Amount | Constant |
|---|---|---|
| HP | +10 | `REGEN_HP_PER_TILE` |
| Mana | +10 | `REGEN_MANA_PER_TILE` |
| SP | +5 | `REGEN_SP_PER_TILE` |

### 8.2 Regeneration Function

```python
def apply_regen(player: dict) -> dict:
    """
    Calculate resource regeneration. Returns dict of player field updates.
    Does NOT exceed max values.
    """
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
```

---

## 9. Scenario System

### 9.1 Scenario Trigger Rules

| Tile Type | Trigger | Chance |
|---|---|---|
| `sr` (Scenario Room) | Always triggers scenario on first visit | 100% |
| `path` | Rolls for random encounter on first visit | 60% (`ENCOUNTER_CHANCE_PER_TILE`) |
| `combat` | Always triggers combat on first visit | 100% |
| `start`, `exit` | No scenario | 0% |

### 9.2 Scenario Roll (for SR tiles)

```
Roll 1-100:
  1-33:   Negative scenario
  34-66:  Positive scenario
  67-100: Neutral scenario
```

### 9.3 Path Tile Encounter Roll

```
Roll 1-100:
  1-60:   Combat encounter triggered (spawn enemies)
  61-100: Safe passage (no encounter)
```

The 60% chance is reduced by the Rogue talent **Silent Steps** (`encounter_rate_reduction: 15%`):
- With Silent Steps: `60% * 0.85 = 51%` effective encounter chance

### 9.4 Scenario Resolution Flow

```
Scenario triggered on SR tile
    |
    v
Roll scenario type (negative/positive/neutral)
    |
    v
Select random event from scenario type pool
    |
    v
Apply event effects:
  - Modify player stats/resources
  - Add/remove inventory items
  - Apply curses/blessings (add to active_effects)
  - Instant death (end dungeon run)
    |
    v
Display scenario narrative embed with outcome
```

### 9.5 Scenario Resolution Function

```python
def resolve_scenario(player: dict, session: dict) -> dict:
    """
    Roll and resolve a scenario event. Returns:
    {
        "category": "negative" | "positive" | "neutral",
        "event": dict,  # the selected scenario event
        "player_updates": dict,  # fields to update on player
        "session_updates": dict,  # fields to update on dungeon session
        "items_gained": list,  # items to add to inventory
        "items_lost": list,  # inventory item IDs to remove
        "messages": list[str],  # narrative text
        "death": bool,  # True if player died
        "combat": bool,  # True if scenario triggers combat
    }
    """
```

---

## 10. Scenario Event Tables

### 10.1 Data File: `data/scenarios.json`

```json
{
  "negative": [
    {
      "id": "trap_pit",
      "name": "Pit Trap",
      "description": "The floor gives way beneath you!",
      "effect": {"type": "hp_loss", "value": 15},
      "message": "You fall into a pit trap and take 15 damage!"
    },
    {
      "id": "trap_poison_dart",
      "name": "Poison Dart Trap",
      "description": "A dart flies from the wall!",
      "effect": {"type": "hp_loss", "value": 10, "status": {"type": "poison", "duration": 3, "damage": 4}},
      "message": "A poison dart hits you! -10 HP and poisoned for 3 combats."
    },
    {
      "id": "cursed_shrine",
      "name": "Cursed Shrine",
      "description": "You touch a dark altar and feel a chill...",
      "effect": {"type": "curse"},
      "message": "A curse falls upon you! One of your stats is reduced for the next 5 combats."
    },
    {
      "id": "ambush",
      "name": "Ambush!",
      "description": "Enemies leap from the shadows!",
      "effect": {"type": "combat", "hp_penalty": 10},
      "message": "You're ambushed! -10 HP before combat begins!"
    },
    {
      "id": "item_thief",
      "name": "Goblin Thief",
      "description": "A sneaky goblin snatches something from your pack!",
      "effect": {"type": "item_loss"},
      "message": "A goblin thief stole an item from your inventory!"
    },
    {
      "id": "mana_drain",
      "name": "Mana Drain",
      "description": "An arcane ward siphons your magical energy.",
      "effect": {"type": "mana_loss", "value": 20},
      "message": "An arcane ward drains 20 Mana!"
    },
    {
      "id": "sp_drain",
      "name": "Exhausting Hallway",
      "description": "The air in this corridor is thick and stifling.",
      "effect": {"type": "sp_loss", "value": 15},
      "message": "The stifling air saps your stamina! -15 SP."
    },
    {
      "id": "deadly_trap",
      "name": "Deadly Trap",
      "description": "A blade swings from the ceiling!",
      "effect": {"type": "death", "chance": 15},
      "message": "A deadly blade trap activates! (15% instant death chance)"
    },
    {
      "id": "stat_debuff",
      "name": "Weakening Fog",
      "description": "A strange fog fills the room, sapping your strength.",
      "effect": {"type": "stat_debuff", "stats": ["strength", "dexterity"], "value": -2, "combats": 3},
      "message": "A weakening fog reduces your Strength and Dexterity by 2 for the next 3 combats!"
    },
    {
      "id": "gold_loss",
      "name": "Crumbling Floor",
      "description": "The floor collapses and some of your gold falls into the abyss.",
      "effect": {"type": "gold_loss", "percent": 10},
      "message": "Some of your gold falls into a chasm! Lost 10% of your gold."
    }
  ],
  "positive": [
    {
      "id": "healing_spring",
      "name": "Healing Spring",
      "description": "You discover a glowing spring of clear water.",
      "effect": {"type": "hp_gain", "percent": 30},
      "message": "You drink from the healing spring! Restored 30% of your max HP."
    },
    {
      "id": "mana_well",
      "name": "Mana Well",
      "description": "An ancient well pulses with arcane energy.",
      "effect": {"type": "mana_gain", "percent": 40},
      "message": "You draw power from the mana well! Restored 40% of your max Mana."
    },
    {
      "id": "stamina_shrine",
      "name": "Stamina Shrine",
      "description": "A warrior's shrine invigorates your body.",
      "effect": {"type": "sp_gain", "percent": 50},
      "message": "The shrine restores your stamina! Restored 50% of your max SP."
    },
    {
      "id": "treasure_chest",
      "name": "Treasure Chest",
      "description": "You find an unlocked treasure chest!",
      "effect": {"type": "gold_gain", "min": 15, "max": 40},
      "message": "You found gold in a treasure chest!"
    },
    {
      "id": "potion_cache",
      "name": "Potion Cache",
      "description": "A shelf of potions sits untouched in the corner.",
      "effect": {"type": "item_gain", "item_pool": ["minor_healing_potion", "mana_potion", "stamina_tonic"]},
      "message": "You found a potion!"
    },
    {
      "id": "blessing_strength",
      "name": "Warrior's Blessing",
      "description": "A spectral warrior salutes you and grants you strength.",
      "effect": {"type": "blessing", "stat": "strength", "value": 5, "unit": "percent", "combats": 3},
      "message": "Warrior's Blessing! +5% Strength for the next 3 combats."
    },
    {
      "id": "blessing_dexterity",
      "name": "Thief's Blessing",
      "description": "A shadow whispers secrets of agility to you.",
      "effect": {"type": "blessing", "stat": "dexterity", "value": 5, "unit": "percent", "combats": 3},
      "message": "Thief's Blessing! +5% Dexterity for the next 3 combats."
    },
    {
      "id": "full_restore",
      "name": "Sacred Fountain",
      "description": "A radiant fountain fully restores your body and mind.",
      "effect": {"type": "full_restore"},
      "message": "The sacred fountain fully restores your HP, Mana, and SP!"
    },
    {
      "id": "xp_bonus",
      "name": "Ancient Tome",
      "description": "You read an ancient tome of knowledge.",
      "effect": {"type": "xp_gain", "min": 20, "max": 50},
      "message": "You gained knowledge from the ancient tome!"
    },
    {
      "id": "rare_item",
      "name": "Hidden Stash",
      "description": "Behind a loose stone, you find a hidden stash!",
      "effect": {"type": "item_gain", "item_pool": ["herbal_remedy", "arcane_elixir", "energizing_elixir"]},
      "message": "You found a rare item in a hidden stash!"
    }
  ],
  "neutral": [
    {
      "id": "empty_room",
      "name": "Empty Room",
      "description": "The room is dusty and abandoned. Nothing of note here.",
      "effect": {"type": "none"},
      "message": "You find an empty room. Nothing happens."
    },
    {
      "id": "old_bones",
      "name": "Old Bones",
      "description": "Scattered bones of a previous adventurer lie on the ground.",
      "effect": {"type": "none"},
      "message": "You find the remains of a fallen adventurer. A sobering sight."
    },
    {
      "id": "strange_writing",
      "name": "Strange Writing",
      "description": "Ancient runes are carved into the walls. You can't read them.",
      "effect": {"type": "none"},
      "message": "Strange runes cover the walls. Their meaning is lost to time."
    },
    {
      "id": "echoing_chamber",
      "name": "Echoing Chamber",
      "description": "Your footsteps echo loudly through this vast chamber.",
      "effect": {"type": "none"},
      "message": "Your footsteps echo through a vast, empty chamber."
    },
    {
      "id": "dripping_water",
      "name": "Dripping Water",
      "description": "Water drips steadily from the ceiling into a stagnant pool.",
      "effect": {"type": "none"},
      "message": "Water drips from the ceiling. The sound is oddly calming."
    },
    {
      "id": "faded_mural",
      "name": "Faded Mural",
      "description": "A once-beautiful mural decorates the wall, now barely visible.",
      "effect": {"type": "none"},
      "message": "A faded mural depicts an ancient battle. The details are lost."
    },
    {
      "id": "cold_breeze",
      "name": "Cold Breeze",
      "description": "A cold breeze blows through a crack in the wall.",
      "effect": {"type": "none"},
      "message": "A cold breeze blows through. You shiver but press on."
    },
    {
      "id": "minor_gold",
      "name": "Loose Coins",
      "description": "A few coins glint on the floor.",
      "effect": {"type": "gold_gain", "min": 1, "max": 5},
      "message": "You pick up a few loose coins from the floor."
    }
  ]
}
```

### 10.2 Scenario Effect Types

| Effect Type | Description | Fields |
|---|---|---|
| `hp_loss` | Player loses HP | `value` (flat amount) |
| `mana_loss` | Player loses Mana | `value` (flat amount) |
| `sp_loss` | Player loses SP | `value` (flat amount) |
| `hp_gain` | Player gains HP | `percent` (% of max HP) |
| `mana_gain` | Player gains Mana | `percent` (% of max Mana) |
| `sp_gain` | Player gains SP | `percent` (% of max SP) |
| `full_restore` | Fully restore HP, Mana, SP | (no extra fields) |
| `gold_gain` | Player gains gold | `min`, `max` (random range) |
| `gold_loss` | Player loses gold | `percent` (% of current gold) |
| `xp_gain` | Player gains XP | `min`, `max` (random range) |
| `item_gain` | Player receives item | `item_pool` (list of consumable IDs, pick one randomly) |
| `item_loss` | Player loses random consumable | (picks random non-equipped inventory item) |
| `curse` | Apply curse debuff | Selects random stat, -10% for 5 combats |
| `blessing` | Apply stat blessing | `stat`, `value`, `unit`, `combats` |
| `stat_debuff` | Temporary stat reduction | `stats` (list), `value`, `combats` |
| `combat` | Trigger combat encounter | `hp_penalty` (optional damage before combat) |
| `death` | Chance of instant death | `chance` (percent, e.g. 15) |
| `none` | No effect | (flavor text only) |

### 10.3 Scenario Resolution Function

```python
def apply_scenario_effect(effect: dict, player: dict, session: dict) -> dict:
    """
    Apply a single scenario effect. Returns:
    {
        "player_updates": dict,    # changes to player table
        "session_updates": dict,   # changes to dungeon_session active_effects
        "items_gained": list,      # consumable items to add to inventory
        "items_lost": list,        # inventory item IDs to remove
        "death": bool,             # True if death occurred
        "combat": bool,            # True if combat triggered
        "xp": int,                 # XP gained (if any)
        "messages": list[str],     # output messages
    }
    """
```

---

## 11. Combat Encounter Triggers

### 11.1 Combat from Tiles

| Source | Behavior |
|---|---|
| `combat` tile (first visit) | 100% guaranteed combat. Spawn enemies at floor level |
| `path` tile (first visit) | 60% chance. Reduced by Silent Steps talent (15% reduction) |
| `sr` tile (ambush scenario) | Scenario can trigger combat as a negative event |

### 11.2 Enemy Level by Floor

```python
def get_encounter_level(floor: int) -> int:
    """Enemy level = floor number, capped at 20."""
    return min(floor, 20)
```

### 11.3 Combat Integration

When a tile triggers combat, the dungeon cog should:

1. Create a combat session using `create_combat_session()` from Stage 3
2. Spawn enemies with `spawn_enemies(encounter_level)`
3. Display the combat embed and view from the combat cog
4. After combat resolves, the player returns to dungeon exploration

The combat cog's `/fight` command already handles the full combat flow. For dungeon-triggered combat, we reuse the same combat engine but auto-trigger it from tile entry rather than requiring `/fight`.

### 11.4 Post-Combat Dungeon Flow

After combat ends (victory/defeat/flee):
- **Victory:** Player remains on the tile, continues exploring
- **Defeat:** Dungeon run ends (see Section 14 -- Death)
- **Flee:** Player remains on the tile, but the encounter is cleared (won't re-trigger)

### 11.5 Curse Application in Combat

Before each combat encounter, check `active_effects` for curses/blessings:
- Apply stat modifiers from active effects
- After combat, decrement `combats_remaining` for all effects
- Remove effects with `combats_remaining <= 0`

```python
def apply_dungeon_effects(player: dict, effects: list) -> tuple[dict, list]:
    """
    Apply active dungeon effects (curses/blessings) to player stats before combat.
    Returns (modified_player, remaining_effects after decrement).
    """

def tick_dungeon_effects(effects: list) -> list:
    """Decrement combats_remaining for all effects. Remove expired ones."""
```

---

## 12. Fog of War & Map Display

### 12.1 Fog Rules

- **Unvisited tiles:** Hidden, shown as dark/fog emoji
- **Visited tiles:** Revealed, shown with their tile type emoji
- **Current position:** Highlighted with player emoji
- **Adjacent to current:** Optionally show tile type (for navigation hints)

### 12.2 Map Emoji Legend

| Tile | Visited | Unvisited | Current |
|---|---|---|---|
| `start` | `S` or green square | fog | player marker |
| `path` | white/light square | fog | player marker |
| `wall` | dark block | dark block (walls always visible) |  |
| `sr` | `?` or purple diamond | fog | player marker |
| `combat` | `!` or red circle | fog | player marker |
| `exit` | `E` or door emoji | fog | player marker |

Using Unicode block characters for a clean look:

```python
TILE_EMOJIS = {
    "start":   "🟢",  # green circle
    "path":    "⬜",  # white square
    "wall":    "⬛",  # black square (always visible)
    "sr":      "🟣",  # purple circle (scenario room)
    "combat":  "🔴",  # red circle (combat room)
    "exit":    "🚪",  # door
}
FOG_EMOJI = "🌫️"     # or "⬛" for simpler look
PLAYER_EMOJI = "🧙"   # player position
CLEARED_SR = "🟪"     # visited scenario room
CLEARED_COMBAT = "🟥" # visited combat room
```

### 12.3 Map Render Function

```python
def render_map(floor_data: dict, visited: list, position: tuple,
               cleared_rooms: list = None) -> str:
    """
    Render the dungeon map as a string of emoji.
    - visited: list of [row, col] that have been visited
    - position: (row, col) of player
    - cleared_rooms: optional list of [row, col] for rooms already resolved
    Returns a multi-line string for embed display.
    """
    lines = []
    for r, row in enumerate(floor_data["tiles"]):
        line = ""
        for c, tile in enumerate(row):
            if (r, c) == tuple(position):
                line += PLAYER_EMOJI
            elif tile == "wall":
                line += TILE_EMOJIS["wall"]
            elif [r, c] in visited:
                line += TILE_EMOJIS.get(tile, "⬜")
            else:
                line += FOG_EMOJI
        lines.append(line)
    return "\n".join(lines)
```

### 12.4 Map Legend

Display below the map grid:
```
🧙 = You | ⬜ = Path | ⬛ = Wall | 🟣 = Scenario Room
🔴 = Combat Room | 🚪 = Exit | 🌫️ = Unexplored
```

---

## 13. Floor Progression

### 13.1 Exit Tile Behavior

When a player steps on the `exit` tile:

1. Display "Floor Complete!" embed with stats (tiles explored, combats fought)
2. Advance `current_floor` on player record
3. Delete current dungeon session
4. Player can enter the next floor with `/enter`

### 13.2 Floor Progression Function

```python
async def process_floor_exit(player: dict, session: dict) -> dict:
    """
    Handle floor exit. Returns:
    {
        "new_floor": int,
        "tiles_explored": int,
        "message": str,
    }
    """
```

### 13.3 Multi-Floor Support

Currently only Floor 1 exists in `maps.json`. The system should:
- Check if the next floor exists in `maps.json`
- If not, display "You've reached the deepest explored floor. More floors coming soon!"
- Player's `current_floor` is still incremented for tracking purposes

---

## 14. Death & Curse Mechanics

### 14.1 Death (Combat or Scenario)

When a player dies (HP reaches 0 in combat, or instant death scenario):

1. **Keep:** XP, level, stats, learned skills, selected talents, equipped items
2. **Lose:** All non-equipped inventory items (consumables, valuables, crafting materials)
3. **Restore:** HP, Mana, SP to full
4. **End:** Delete dungeon session
5. **Reset:** Player is no longer in dungeon (`in_dungeon = 0`)

```python
async def process_death(player: dict) -> dict:
    """
    Handle player death. Clears non-equipped inventory, restores resources.
    Returns summary of items lost.
    """
```

### 14.2 Death from Scenario

The "Deadly Trap" scenario has a 15% chance of instant death:
```python
if effect["type"] == "death":
    if random.randint(1, 100) <= effect["chance"]:
        # Player dies
        return {"death": True, "message": "The trap was lethal! You have been slain."}
    else:
        # Survived
        return {"death": False, "message": "You narrowly avoid a deadly trap!"}
```

### 14.3 Curse Mechanic

**Application:**
- Random stat selected from ALL_STATS
- -10% to that stat (multiplicative) for the next 5 combat encounters
- Maximum 3 curses can stack

**Storage:** Added to `active_effects` in dungeon session:
```json
{"type": "curse", "stat": "agility", "value": -10, "unit": "percent", "combats_remaining": 5}
```

**Combat Integration:**
- Before combat starts, apply all active curses to a temporary copy of player stats
- The temporary modified stats are used for combat calculations
- After combat ends, decrement `combats_remaining` for all active effects
- Remove expired effects

**Constants to add:**
```python
CURSE_STAT_PENALTY = -10  # percent
CURSE_DURATION = 5        # combats
MAX_CURSES = 3
DEATH_TRAP_ITEMS_KEPT = ["equipped"]  # only equipped items survive death
```

---

## 15. Talent Interactions

### 15.1 Rogue -- Silent Steps

| Talent | ID | Dungeon Effect |
|---|---|---|
| Silent Steps | `rogue_silent_steps` | Reduces encounter chance on path tiles by 15% (60% -> 51%) |

```python
def get_encounter_chance(player: dict) -> int:
    """Return effective encounter chance, accounting for talents."""
    base = ENCOUNTER_CHANCE_PER_TILE  # 60
    talents = json.loads(player["selected_talents"])
    if "rogue_silent_steps" in talents:
        base = int(base * 0.85)  # 15% reduction -> 51
    return base
```

### 15.2 Cleric -- Faithful Recovery

Already implemented in Stage 3 combat cog (triggers at combat start). No dungeon-specific changes needed.

### 15.3 Future Talent Hooks

The dungeon engine should be extensible for future talents that affect exploration (e.g., trap detection, better scenario outcomes). Use a hook pattern:

```python
def apply_exploration_talents(player: dict, event_type: str, event_data: dict) -> dict:
    """Apply any talent modifiers to dungeon events. Returns modified event_data."""
```

---

## 16. Dungeon UI -- Embeds

### 16.1 Dungeon Enter Embed

```python
def dungeon_enter_embed(player_name: str, floor: int) -> discord.Embed:
    """Embed shown when player enters the dungeon."""
    # Title: "Entering the Dungeon"
    # Description: "{player_name} descends to Floor {floor}..."
    # Color: dark theme
    # Fields: Current resources, floor info
```

### 16.2 Map Embed

```python
def dungeon_map_embed(player: dict, floor_data: dict, visited: list,
                      position: tuple) -> discord.Embed:
    """Full map embed with emoji grid, legend, and player status."""
    # Title: "Floor {n} - Map"
    # Description: rendered map grid (emoji)
    # Fields: Position, tiles explored, legend
```

### 16.3 Movement Result Embed

```python
def dungeon_move_embed(player: dict, floor_data: dict, visited: list,
                       position: tuple, message: str, regen: dict) -> discord.Embed:
    """Embed shown after movement, includes map + what happened."""
    # Title: "Floor {n}"
    # Description: map grid
    # Fields: Movement result, regen info, resources
```

### 16.4 Scenario Embed

```python
def scenario_embed(scenario: dict, category: str, outcome_msg: str) -> discord.Embed:
    """Embed for scenario room results."""
    # Color: red for negative, green for positive, grey for neutral
    # Title: scenario["name"]
    # Description: scenario["description"]
    # Fields: Outcome details
```

### 16.5 Floor Complete Embed

```python
def floor_complete_embed(player_name: str, floor: int,
                         tiles_explored: int) -> discord.Embed:
    """Embed shown when reaching the exit tile."""
```

### 16.6 Dungeon Death Embed

```python
def dungeon_death_embed(items_lost: list) -> discord.Embed:
    """Embed shown when player dies in the dungeon."""
    # Title: "You Have Fallen!"
    # Description: "Your dungeon run has ended. You keep your XP and level."
    # Fields: Items lost
```

### 16.7 Retreat Embed

```python
def dungeon_retreat_embed(player_name: str) -> discord.Embed:
    """Embed shown when player retreats from dungeon."""
```

---

## 17. New Cog: dungeon.py -- Commands

### 17.1 Interactive Movement View

```python
class MovementView(discord.ui.View):
    """View with N/S/E/W direction buttons for dungeon navigation."""

    def __init__(self, player_id: str, valid_moves: dict):
        super().__init__(timeout=300)
        self.player_id = player_id
        # Disable buttons for invalid directions
        self.north_btn.disabled = "north" not in valid_moves
        self.south_btn.disabled = "south" not in valid_moves
        self.east_btn.disabled = "east" not in valid_moves
        self.west_btn.disabled = "west" not in valid_moves

    async def interaction_check(self, interaction):
        return str(interaction.user.id) == self.player_id

    @discord.ui.button(label="North", style=ButtonStyle.primary, row=0)
    async def north_btn(self, interaction, button):
        cog = interaction.client.get_cog("Dungeon")
        if cog:
            await cog._handle_move(interaction, "north", is_button=True)

    @discord.ui.button(label="West", style=ButtonStyle.primary, row=1)
    async def west_btn(self, interaction, button):
        ...

    @discord.ui.button(label="East", style=ButtonStyle.primary, row=1)
    async def east_btn(self, interaction, button):
        ...

    @discord.ui.button(label="South", style=ButtonStyle.primary, row=2)
    async def south_btn(self, interaction, button):
        ...

    @discord.ui.button(label="Retreat", style=ButtonStyle.secondary, row=2)
    async def retreat_btn(self, interaction, button):
        cog = interaction.client.get_cog("Dungeon")
        if cog:
            await cog._handle_retreat(interaction, is_button=True)
```

### 17.2 Slash Commands

| Command | Description | Parameters |
|---|---|---|
| `/enter` | Enter the dungeon (start new session or resume) | None |
| `/move <direction>` | Move in a direction | `direction`: north/south/east/west |
| `/map` | View the current dungeon map | None |
| `/retreat` | Leave the dungeon voluntarily | None |

### 17.3 Admin Commands

| Command | Description | Parameters |
|---|---|---|
| `/admin_teleport <row> <col>` | Teleport to tile | `row`, `col` |
| `/admin_scenario <type>` | Force a scenario type | `type`: negative/positive/neutral |
| `/admin_floor <floor>` | Set current floor | `floor`: int |

### 17.4 Command Implementations

```python
class Dungeon(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- Core Movement Handler ---
    async def _handle_move(self, interaction, direction, is_button=False):
        """
        Process a movement action:
        1. Validate player state (has character, in dungeon, not in combat)
        2. Validate move (direction valid, target passable)
        3. Apply resource regen
        4. Update position + visited_tiles
        5. Resolve tile event (scenario/combat/exit/nothing)
        6. Send result embed with updated map + movement buttons
        """

    async def _handle_retreat(self, interaction, is_button=False):
        """End dungeon session voluntarily. Player keeps everything."""

    # --- Slash Commands ---
    @app_commands.command(name="enter", description="Enter the dungeon")
    async def enter(self, interaction):
        """
        1. Check player exists, not already in combat
        2. If dungeon session exists, resume it
        3. If no session, create one at current_floor start position
        4. Show map + intro embed + movement buttons
        """

    @app_commands.command(name="move", description="Move in a direction")
    @app_commands.describe(direction="Direction to move")
    @app_commands.choices(direction=[
        Choice(name="North", value="north"),
        Choice(name="South", value="south"),
        Choice(name="East", value="east"),
        Choice(name="West", value="west"),
    ])
    async def move(self, interaction, direction: Choice[str]):
        await self._handle_move(interaction, direction.value)

    @app_commands.command(name="map", description="View the dungeon map")
    async def show_map(self, interaction):
        """Display the current map with fog of war."""

    @app_commands.command(name="retreat", description="Leave the dungeon")
    async def retreat(self, interaction):
        await self._handle_retreat(interaction)
```

### 17.5 Combat Integration in Dungeon Cog

When a tile triggers combat, the dungeon cog should:

```python
async def _trigger_combat(self, interaction, player, session, floor_data, is_button=False):
    """
    Spawn enemies and start combat from dungeon tile.
    Uses the combat engine from Stage 3.
    """
    from src.game.combat import spawn_enemies
    from src.db.models import create_combat_session, get_combat_session

    level = get_encounter_level(session["floor"])
    enemies = spawn_enemies(level)
    enemies_json = json.dumps(enemies)
    await create_combat_session(player["id"], enemies_json)

    # Apply dungeon effects (curses/blessings) before combat
    # ... modify player stats temporarily ...

    # Build combat embed and view
    combat_session = await get_combat_session(player["id"])
    # Reuse combat cog's _build_view and combat_embed
    ...
```

---

## 18. Modifications to Existing Files

### 18.1 `bot.py`

Add to COGS list:
```python
COGS = [
    "src.bot.cogs.general",
    "src.bot.cogs.character",
    "src.bot.cogs.leveling",
    "src.bot.cogs.combat",
    "src.bot.cogs.dungeon",  # NEW
]
```

### 18.2 `src/db/models.py`

Add dungeon session CRUD functions (see Section 6.4).

### 18.3 `src/game/constants.py`

Add:
```python
# --- Dungeon ---
CURSE_STAT_PENALTY = 10      # percent reduction per curse
CURSE_DURATION = 5           # combats
MAX_CURSES = 3
DEATH_CHANCE_CAP = 15        # max instant death chance from scenarios
```

### 18.4 `src/utils/data_loader.py`

Add:
```python
def get_scenarios(category: Optional[str] = None) -> list:
    """Return scenario events, optionally filtered by category."""
    data = _load("scenarios.json")
    if category:
        return data.get(category, [])
    return data
```

### 18.5 `src/utils/embeds.py`

Add dungeon embed functions (see Section 16).

### 18.6 `src/bot/cogs/combat.py`

Modify combat resolution to integrate with dungeon:
- After combat defeat in dungeon: trigger death handling (item loss, session end)
- After combat victory/flee in dungeon: decrement curse/blessing counters
- Add helper to check if player is in dungeon during combat resolution

### 18.7 `src/utils/embeds.py` -- Help Embed

Update the help embed to include dungeon commands:
```python
embed.add_field(
    name="Dungeon",
    value=(
        "`/enter` - Enter the dungeon\n"
        "`/move <direction>` - Move (north/south/east/west)\n"
        "`/map` - View the dungeon map\n"
        "`/retreat` - Leave the dungeon"
    ),
    inline=False,
)
```
This field already exists in the help embed, so no changes needed.

---

## 19. Testing & Admin Commands

### 19.1 Admin Commands

| Command | What it does |
|---|---|
| `/admin_teleport <row> <col>` | Teleport player to specific tile in dungeon |
| `/admin_scenario <type>` | Force a specific scenario type (negative/positive/neutral) |
| `/admin_floor <floor>` | Set player's current floor |

### 19.2 Manual Test Script

1. **Enter dungeon:** `/enter` -- should show map with player at start, movement buttons
2. **Move to path tile:** Click North or East -- should regenerate resources, check encounter
3. **View map:** `/map` -- should show visited tiles revealed, fog on unvisited
4. **Move to scenario room:** Navigate to an SR tile -- should trigger scenario event
5. **Positive scenario:** Verify HP/Mana/SP/gold/item gain works
6. **Negative scenario:** Verify HP loss, curse application, item theft
7. **Neutral scenario:** Verify flavor text only
8. **Combat room:** Navigate to combat tile -- should auto-start combat
9. **Win combat:** Complete combat, verify return to dungeon exploration
10. **Encounter on path:** Move to fresh path tiles until random encounter triggers
11. **Silent Steps:** Test with rogue who has Silent Steps -- encounter rate should be lower
12. **Curse effect:** Get cursed, enter combat, verify stat reduction applied
13. **Multiple curses:** Stack curses, verify max 3
14. **Death scenario:** Trigger deadly trap, verify death handling (item loss, session end)
15. **Retreat:** `/retreat` -- should end session, keep everything
16. **Resume:** `/enter` after retreat -- should start fresh session
17. **Exit tile:** Navigate to exit -- should advance floor
18. **Wall collision:** Try to move into a wall -- should fail with error
19. **Re-visit tile:** Move back to already-visited tile -- should not re-trigger events
20. **In-combat movement:** Try to `/move` during combat -- should fail with error
21. **Death from combat:** Die in combat while in dungeon -- verify proper cleanup
22. **Resource regen capping:** Move when at full HP/Mana/SP -- should stay at max
23. **Gold loss scenario:** Verify gold_loss percentage calculates correctly
24. **Admin teleport:** `/admin_teleport 3 3` -- should move player to tile (3,3)
25. **Admin scenario:** `/admin_scenario positive` -- should force positive scenario

---

## 20. Validation Checklist

### Core Systems
- [ ] Player can enter dungeon with `/enter`
- [ ] Player can resume existing dungeon session
- [ ] Player cannot enter dungeon if already in combat
- [ ] Movement works in all 4 directions
- [ ] Movement blocked by walls and map boundaries
- [ ] Resource regeneration applies on each tile move
- [ ] Resources capped at max values
- [ ] Map displays with fog of war
- [ ] Visited tiles remain revealed
- [ ] Player position shown correctly on map

### Scenarios
- [ ] SR tiles trigger scenarios on first visit only
- [ ] Negative scenarios apply correct effects (HP loss, curses, item loss, etc.)
- [ ] Positive scenarios apply correct effects (healing, gold, items, blessings)
- [ ] Neutral scenarios show flavor text only
- [ ] Curse mechanics work (stat reduction, 5-combat duration, max 3 stacks)
- [ ] Death scenario triggers properly (15% chance, item loss, session end)
- [ ] Blessings apply to subsequent combats

### Combat Integration
- [ ] Combat tiles trigger guaranteed combat on first visit
- [ ] Path tiles trigger random encounters at 60% (51% with Silent Steps)
- [ ] Ambush scenario triggers combat with HP penalty
- [ ] Victory in dungeon combat returns to exploration
- [ ] Defeat in dungeon combat triggers death handling
- [ ] Curses/blessings apply during combat and decrement after
- [ ] Flee in dungeon combat returns to exploration

### Floor Progression
- [ ] Exit tile advances to next floor
- [ ] `current_floor` updates on player record
- [ ] Missing floor shows "coming soon" message

### Edge Cases
- [ ] Cannot move while in combat
- [ ] Cannot `/fight` manually while in dungeon (or properly integrates)
- [ ] Retreat keeps all items and XP
- [ ] Re-entering dungeon starts fresh session
- [ ] Bot restart preserves dungeon session
- [ ] Direction buttons disable for invalid moves
- [ ] Only the owning player can use movement buttons
