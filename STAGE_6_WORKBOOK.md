# Stage 6 Workbook -- Multi-Floor Progression & Content Expansion

**Purpose:** Comprehensive build spec for Stage 6. Expand the dungeon from a single floor to 5 progressively harder floors, scale enemy encounters by floor, add a shop system, implement a leaderboard, and introduce a boss encounter framework.

---

## Table of Contents

1. [What Already Exists](#1-what-already-exists)
2. [Files to Create](#2-files-to-create)
3. [Files to Modify](#3-files-to-modify)
4. [Design Decisions](#4-design-decisions)
5. [Multi-Floor Map Design](#5-multi-floor-map-design)
6. [Enemy Scaling by Floor](#6-enemy-scaling-by-floor)
7. [Boss Encounter System](#7-boss-encounter-system)
8. [Shop System](#8-shop-system)
9. [Leaderboard System](#9-leaderboard-system)
10. [Floor Progression Flow](#10-floor-progression-flow)
11. [New Embeds](#11-new-embeds)
12. [Modifications to Existing Files](#12-modifications-to-existing-files)
13. [Testing & Admin Commands](#13-testing--admin-commands)
14. [Validation Checklist](#14-validation-checklist)

---

## 1. What Already Exists

| Component | Location | What it provides |
|---|---|---|
| Floor 1 map (7x7 grid) | `data/maps.json` | Single floor with start, exit, path, wall, sr, combat tiles |
| Dungeon engine | `src/game/dungeon.py` | `load_floor()`, `get_tile()`, movement, regen, scenario resolution, fog of war rendering |
| Dungeon cog | `src/bot/cogs/dungeon.py` | `/enter`, `/move`, `/map`, `/retreat`, movement buttons, combat/scenario triggers |
| Enemy data (40 entries) | `data/enemies.json` | Goblin (levels 1-20) and Feral Rat (levels 1-20) with damage/hp/xp scaling |
| Loot tables | `data/loot_tables.json` | Goblin (5 drops), Feral Rat (3 drops) |
| Combat spawner | `src/game/combat.py` | `spawn_enemies()` picks random type/count, `ENEMY_TYPES = ["goblin", "feral_rat"]` |
| Encounter level calc | `src/game/dungeon.py` | `get_encounter_level(floor)` returns `min(floor, 20)` |
| Floor progression | `src/bot/cogs/dungeon.py` | Exit tile increments `current_floor`, deletes dungeon session |
| Item floor scaling | `src/game/items.py` | Affix base value scales by floor (`1 + (floor-1)//5`) |
| Player schema | `src/db/database.py` | `current_floor`, `gold`, `level`, `xp` fields |
| XP thresholds | `data/xp_thresholds.json` | Levels 1-20 with XP requirements |
| Scenarios | `data/scenarios.json` | 28 events (10 neg, 10 pos, 8 neutral) |
| Inventory/equipment | Stage 5 | Full item/equip/sell system, 20-slot inventory |

---

## 2. Files to Create

| File | Purpose |
|---|---|
| `src/bot/cogs/shop.py` | Shop cog: `/shop`, `/buy`, `/sell_all` commands |
| `src/bot/cogs/leaderboard.py` | Leaderboard cog: `/leaderboard` command |

---

## 3. Files to Modify

| File | Change |
|---|---|
| `data/maps.json` | Add Floors 2-5 tile grids |
| `data/enemies.json` | Add boss enemy entries |
| `data/loot_tables.json` | Add boss loot tables |
| `data/scenarios.json` | Add floor-themed scenario variants |
| `src/game/combat.py` | Add boss spawn support, floor-aware enemy selection |
| `src/game/dungeon.py` | Add boss tile handling, floor-specific encounter tables |
| `src/game/constants.py` | Add floor/shop/boss constants |
| `src/bot/cogs/dungeon.py` | Handle boss tiles, floor-specific embeds |
| `src/db/models.py` | Add leaderboard queries, player stats tracking |
| `src/db/database.py` | Add `player_stats` tracking columns |
| `src/utils/embeds.py` | Add shop, leaderboard, boss embeds |
| `src/utils/data_loader.py` | Add `get_boss()` helper |
| `bot.py` | Add `"src.bot.cogs.shop"`, `"src.bot.cogs.leaderboard"` to COGS |

---

## 4. Design Decisions

### 4.1 Resolved from Implementation Plan

| Decision | Resolution |
|---|---|
| Floor count | 5 floors for initial release (expandable) |
| Boss rooms | Floor 5 has a boss room; framework supports adding bosses to other floors later |
| Shop location | Accessible outside the dungeon only (between runs) |
| Leaderboard scope | Per-bot (all players across all servers the bot runs on) |

### 4.2 New Decisions for Stage 6

| Decision | Resolution | Rationale |
|---|---|---|
| Floor grid sizes | F1: 7x7, F2: 7x7, F3: 9x9, F4: 9x9, F5: 9x9 | Gradual complexity increase without overwhelming |
| Enemy level per floor | F1: Lv1-3, F2: Lv3-5, F3: Lv5-8, F4: Lv8-12, F5: Lv12-16 | Spreads the existing Lv1-20 enemy data across floors |
| Enemy group size by floor | F1: 1-2, F2: 1-3, F3: 2-3, F4: 2-4, F5: 2-4 + boss | Higher floors get harder packs |
| Boss mechanics | Bosses are stronger single enemies with higher stats, XP, and guaranteed loot | Keeps it simple, no special AI yet |
| Shop stock | Consumables only; restocks each time you visit | Selling is already in Stage 5; shop is a buy-only interface |
| Shop pricing | 2x sell value for buy price | Standard RPG markup |
| Gold from enemy drops | Already handled by loot tables | No change needed |
| Leaderboard categories | Level, Floor Reached, Enemies Killed | Three meaningful rankings |
| Floor-themed scenarios | Same pool for all floors (no floor-specific themes yet) | Keeps it simple; can be expanded in Stage 7 |
| Repeated floor runs | Players can re-enter completed floors at will | Allows grinding; progression is tracked by highest floor |

---

## 5. Multi-Floor Map Design

### 5.1 Floor Design Philosophy

- **Floor 1 (7x7):** Tutorial floor. Few enemies, forgiving layout, teaches mechanics.
- **Floor 2 (7x7):** More combat rooms, tighter corridors, first real challenge.
- **Floor 3 (9x9):** Larger map, more branching paths, heavier on scenarios.
- **Floor 4 (9x9):** Dense combat, few safe paths, high risk.
- **Floor 5 (9x9):** Boss floor. Mix of everything, ends with a boss room.

### 5.2 Tile Type: Boss Room

New tile type `"boss"` -- works like `"combat"` but spawns a boss enemy instead of random enemies.

- Rendered with a special emoji: `TILE_EMOJIS["boss"] = "\U0001f480"` (skull)
- Only one boss tile per floor (placed near the exit)
- Player must defeat the boss to proceed (boss tile blocks exit until cleared)

Actually, for simplicity: the boss tile triggers boss combat. After winning, the tile becomes passable like a regular combat tile (already-visited logic handles this). The exit tile remains separate and is always accessible.

### 5.3 Floor 1 (Existing -- No Change)

```
7x7 grid, already implemented
start  path   path   sr     path   combat path
path   wall   wall   path   wall   path   wall
sr     path   combat path   sr     path   path
path   wall   path   wall   path   wall   sr
path   path   sr     path   combat path   path
wall   wall   path   wall   path   wall   path
combat path   sr     path   path   sr     exit
```

### 5.4 Floor 2 (7x7)

More combat rooms, fewer scenarios. Tighter corridors.

```
start  path   combat path   path   wall   path
wall   wall   path   wall   combat path   wall
path   combat path   sr     path   path   path
path   wall   wall   wall   path   wall   combat
sr     path   path   combat path   path   path
wall   wall   path   wall   wall   wall   path
path   path   combat path   sr     path   exit
```

- 5 combat rooms (up from 4)
- 3 scenario rooms (down from 6)
- More walls creating choke points

### 5.5 Floor 3 (9x9)

Larger map with branching paths. Heavier on scenarios.

```
start  path   wall   sr     path   path   wall   path   path
path   wall   path   path   wall   combat path   wall   path
path   path   combat path   sr     path   path   path   wall
wall   path   wall   wall   path   wall   sr     path   path
sr     path   path   combat path   path   wall   wall   combat
path   wall   path   wall   wall   path   path   path   path
path   path   sr     path   combat path   wall   sr     path
wall   wall   path   wall   path   wall   path   wall   path
path   combat path   sr     path   path   path   combat exit
```

- 7 combat rooms
- 7 scenario rooms
- More route options

### 5.6 Floor 4 (9x9)

Dense combat, few safe paths. High risk/reward.

```
start  combat path   wall   path   sr     path   wall   path
path   wall   path   combat path   wall   path   combat path
sr     path   combat path   wall   path   combat path   wall
path   wall   path   wall   path   wall   path   wall   path
combat path   sr     path   combat path   sr     path   combat
wall   path   wall   path   wall   path   wall   path   wall
path   combat path   wall   path   combat path   sr     path
path   wall   sr     path   wall   path   wall   path   path
path   path   combat path   sr     path   combat path   exit
```

- 12 combat rooms
- 6 scenario rooms
- Very dense -- almost every path leads through combat

### 5.7 Floor 5 (9x9) -- Boss Floor

Mix of everything. Boss room near the exit.

```
start  path   sr     path   wall   combat path   wall   path
path   wall   path   combat path   wall   path   path   wall
combat path   path   wall   sr     path   combat path   path
path   wall   combat path   path   wall   path   wall   sr
sr     path   wall   path   combat path   path   combat path
wall   path   path   wall   path   wall   sr     wall   path
path   combat sr     path   wall   path   path   path   combat
path   wall   path   wall   path   wall   path   wall   path
combat path   path   sr     path   combat boss   path   exit
```

- 10 combat rooms + 1 boss room
- 6 scenario rooms
- Boss room at (8, 6), exit at (8, 8)

---

## 6. Enemy Scaling by Floor

### 6.1 Floor-to-Enemy-Level Mapping

Instead of enemies always matching `min(floor, 20)`, use a level range per floor with random variance:

```python
FLOOR_ENEMY_LEVELS = {
    1: (1, 3),
    2: (3, 5),
    3: (5, 8),
    4: (8, 12),
    5: (12, 16),
}
```

The spawner picks a random level within the floor's range. This provides variety within each floor.

### 6.2 Floor-to-Enemy-Count Mapping

Scale group sizes with floor difficulty:

```python
FLOOR_ENEMY_COUNTS = {
    1: (1, 2),    # 1-2 enemies
    2: (1, 3),    # 1-3 enemies
    3: (2, 3),    # 2-3 enemies
    4: (2, 4),    # 2-4 enemies
    5: (2, 4),    # 2-4 enemies (boss is separate)
}
```

### 6.3 Updated `spawn_enemies` Signature

```python
def spawn_enemies(player_level: int, floor: int = 1) -> list:
    """Spawn enemies based on floor level range and group size."""
    level_min, level_max = FLOOR_ENEMY_LEVELS.get(floor, (1, 3))
    count_min, count_max = FLOOR_ENEMY_COUNTS.get(floor, (1, 2))
    count = random.randint(count_min, count_max)
    enemies = []
    for i in range(count):
        level = random.randint(level_min, level_max)
        level = min(level, 20)
        etype = random.choice(ENEMY_TYPES)
        ...
```

### 6.4 Call Site Updates

All places that call `spawn_enemies(level)` need to pass `floor`:
- `src/bot/cogs/dungeon.py`: `_start_dungeon_combat()` and `_start_dungeon_combat_followup()` -- pass `session["floor"]`
- `src/bot/cogs/combat.py`: `/fight` command -- pass `player.get("current_floor", 1)`

---

## 7. Boss Encounter System

### 7.1 Boss Data Model

Bosses are stored in `data/enemies.json` alongside regular enemies, with `"type": "boss_<name>"` and higher stats.

```json
{
  "type": "goblin_king",
  "level": 16,
  "damage_min": 45,
  "damage_max": 60,
  "hp": 500,
  "xp_reward": 800,
  "is_boss": true,
  "name": "Goblin King"
}
```

### 7.2 Boss Entries

One boss for Floor 5 (others can be added later for more floors):

| Boss | Floor | Level | HP | Damage | XP |
|---|---|---|---|---|---|
| Goblin King | 5 | 16 | 500 | 45-60 | 800 |

### 7.3 Boss Loot

Boss gets a guaranteed loot drop (100% chance) with higher rarity floor:

```python
BOSS_LOOT_RULES = {
    "goblin_king": {
        "guaranteed_rarity_min": "rare",  # minimum rarity is rare
        "drop_count": 2,                   # guaranteed 2 item drops
        "bonus_gold": (100, 250),          # extra gold range
    },
}
```

Boss loot generation:
1. Roll 2 equipment items with minimum rarity of Rare
2. Add bonus gold (100-250)
3. Add enemy-specific drops (from loot table, 100% chance instead of 50%)

### 7.4 Boss Loot Table

```json
"goblin_king": [
  {"id": "kings_treasury", "name": "King's Treasury", "type": "valuable", "gold_min": 50, "gold_max": 150, "description": "A chest filled with the Goblin King's hoard."},
  {"id": "royal_goblin_crown", "name": "Royal Goblin Crown", "type": "valuable", "gold_min": 75, "gold_max": 200, "description": "A crude but surprisingly valuable crown made of stolen gold."}
]
```

### 7.5 Boss Spawn Function

```python
def spawn_boss(boss_type: str) -> list:
    """Spawn a boss enemy. Returns a list with one boss enemy dict."""
    from src.utils.data_loader import get_boss
    boss_data = get_boss(boss_type)
    if not boss_data:
        return spawn_enemies(16, floor=5)  # fallback
    return [{
        "id": 0,
        "type": boss_data["type"],
        "name": boss_data.get("name", boss_data["type"].replace("_", " ").title()),
        "level": boss_data["level"],
        "hp": boss_data["hp"],
        "max_hp": boss_data["hp"],
        "damage_min": boss_data["damage_min"],
        "damage_max": boss_data["damage_max"],
        "xp_reward": boss_data["xp_reward"],
        "is_alive": True,
        "is_boss": True,
    }]
```

### 7.6 Boss Tile in Dungeon Cog

When the player moves onto a `"boss"` tile:
1. Check if boss has already been defeated this session (track in dungeon session)
2. If not defeated, spawn boss and start combat
3. On victory, mark boss as defeated in dungeon session
4. Already-visited logic allows passing through after defeat

Add `boss_defeated` field to dungeon session updates (stored in `active_effects` JSON or as a separate field).

### 7.7 Boss Floor Mapping

```python
FLOOR_BOSSES = {
    5: "goblin_king",
}
```

---

## 8. Shop System

### 8.1 Shop Design

The shop is an NPC vendor accessible **outside the dungeon** (no active dungeon session). It sells consumables at a fixed markup over sell value.

### 8.2 Shop Stock

The shop sells all consumables from `data/consumables.json`. Prices are calculated as:

```python
SHOP_PRICE_MULTIPLIER = 2  # buy price = sell price * 2

def get_shop_price(consumable: dict) -> int:
    """Calculate shop buy price for a consumable."""
    base = consumable.get("shop_price", 10)
    return base
```

Since consumables don't have sell values defined, we define shop prices directly:

| Consumable | Shop Price |
|---|---|
| Minor Healing Potion | 15 |
| Healing Potion | 30 |
| Greater Healing Potion | 60 |
| Minor Mana Potion | 15 |
| Mana Potion | 30 |
| Greater Mana Potion | 60 |
| Stamina Tonic | 20 |
| Greater Stamina Tonic | 40 |
| Antidote | 25 |
| Smoke Bomb | 35 |
| Fire Bomb | 40 |
| Frost Bomb | 40 |
| Healing Fruit | 50 |
| Elixir of Fortitude | 75 |
| Scroll of Teleportation | 100 |

### 8.3 Shop Constants

```python
SHOP_PRICES = {
    "minor_healing_potion": 15,
    "healing_potion": 30,
    "greater_healing_potion": 60,
    "minor_mana_potion": 15,
    "mana_potion": 30,
    "greater_mana_potion": 60,
    "stamina_tonic": 20,
    "greater_stamina_tonic": 40,
    "antidote": 25,
    "smoke_bomb": 35,
    "fire_bomb": 40,
    "frost_bomb": 40,
    "healing_fruit": 50,
    "elixir_of_fortitude": 75,
    "scroll_of_teleportation": 100,
}
```

### 8.4 Shop Commands

| Command | Description |
|---|---|
| `/shop` | Display shop with available items and prices |
| `/buy <item> [quantity]` | Buy a consumable from the shop |
| `/sell_all` | Sell all non-equipped items in inventory |

### 8.5 `/shop` Command

Shows a paginated embed with all consumables, their effects, and prices. Uses Discord select menu for purchasing.

```python
@app_commands.command(name="shop", description="Browse the shop")
async def shop(self, interaction):
    player = await get_player(str(interaction.user.id))
    # Check not in dungeon
    # Build shop embed with all items and prices
    # Add select menu for buying
```

### 8.6 `/buy` Command

```python
@app_commands.command(name="buy", description="Buy an item from the shop")
@app_commands.describe(item_name="Item to buy", quantity="How many to buy")
async def buy(self, interaction, item_name: str, quantity: int = 1):
    # Validate player exists, not in dungeon
    # Find consumable by name
    # Check gold >= price * quantity
    # Check inventory capacity
    # Deduct gold, add items
    # Show confirmation
```

### 8.7 `/sell_all` Command

Sells all non-equipped inventory items. Shows total gold earned and item count.

```python
@app_commands.command(name="sell_all", description="Sell all unequipped items")
async def sell_all(self, interaction):
    # Get all non-equipped items
    # Calculate total sell value
    # Remove items, add gold
    # Show summary
```

---

## 9. Leaderboard System

### 9.1 Tracked Stats

Add tracking columns to the players table:

```sql
ALTER TABLE players ADD COLUMN enemies_killed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE players ADD COLUMN highest_floor INTEGER NOT NULL DEFAULT 1;
ALTER TABLE players ADD COLUMN bosses_killed INTEGER NOT NULL DEFAULT 0;
```

Since we use `CREATE TABLE IF NOT EXISTS`, we'll add the columns to the schema. For existing databases, we'll use a migration helper.

### 9.2 Stat Tracking Points

- **enemies_killed**: Incremented in `_send_result()` on victory (count of dead enemies)
- **highest_floor**: Updated in dungeon exit tile handler (if new floor > current highest)
- **bosses_killed**: Incremented on boss victory

### 9.3 Leaderboard Queries

```python
async def get_leaderboard(category: str, limit: int = 10) -> list:
    """Fetch top players for a leaderboard category."""
    columns = {
        "level": "level DESC, xp DESC",
        "floor": "highest_floor DESC, level DESC",
        "kills": "enemies_killed DESC, level DESC",
    }
    order = columns.get(category, "level DESC")
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT character_name, class, level, highest_floor, enemies_killed "
            f"FROM players ORDER BY {order} LIMIT ?", (limit,))
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()
```

### 9.4 `/leaderboard` Command

```python
@app_commands.command(name="leaderboard", description="View the leaderboard")
@app_commands.describe(category="Leaderboard category")
@app_commands.choices(category=[
    Choice(name="Level", value="level"),
    Choice(name="Highest Floor", value="floor"),
    Choice(name="Enemies Killed", value="kills"),
])
async def leaderboard(self, interaction, category: Choice[str] = None):
    # Default to "level" if no category
    # Fetch top 10
    # Build leaderboard embed with rankings
```

### 9.5 Leaderboard Embed

```
Leaderboard - Highest Level
━━━━━━━━━━━━━━━━━━━━━━━━━━
1. 🥇 PlayerName (Warrior) - Level 15
2. 🥈 AnotherOne (Mage) - Level 12
3. 🥉 ThirdGuy (Rogue) - Level 10
4. FourthPlayer (Bard) - Level 8
...
```

---

## 10. Floor Progression Flow

### 10.1 Current Flow (No Change Needed)

```
Player at Floor N
    |
    v
/enter -> loads floor N map from maps.json
    |
    v
Explore, fight, loot
    |
    v
Reach exit tile -> current_floor = N+1, session deleted
    |
    v
/enter -> loads floor N+1
```

This already works. The only change needed is ensuring `maps.json` has floors 2-5 defined.

### 10.2 Floor Unavailable Handling

Already handled in dungeon cog:
```python
if not floor_data:
    return await interaction.response.send_message(
        embed=error_embed(f"Floor {floor_num} is not yet available. More floors coming soon!"),
        ephemeral=True)
```

### 10.3 Re-entering Completed Floors

Players should be able to re-enter lower floors for grinding. The `/enter` command uses `player["current_floor"]` which always points to the highest unlocked floor. We need to add an optional floor parameter:

```python
@app_commands.command(name="enter", description="Enter the dungeon")
@app_commands.describe(floor="Floor number (defaults to highest unlocked)")
async def enter(self, interaction, floor: int = None):
    # If floor specified, validate it's <= current_floor
    # Otherwise use current_floor
```

### 10.4 Highest Floor Tracking

Update `highest_floor` when completing a floor:

```python
# In exit tile handler:
new_floor = dsess["floor"] + 1
updates = {"current_floor": new_floor, "in_dungeon": 0}
if new_floor > player.get("highest_floor", 1):
    updates["highest_floor"] = new_floor
await update_player(discord_id, **updates)
```

---

## 11. New Embeds

### 11.1 Shop Embed

```python
def shop_embed(items: list, player_gold: int) -> discord.Embed:
    """Display shop inventory with prices."""
    embed = discord.Embed(title="Shop", color=discord.Color.gold())
    lines = []
    for item in items:
        price = item["price"]
        affordable = "✓" if player_gold >= price else "✗"
        lines.append(f"{affordable} **{item['name']}** — {price}g\n  {item.get('effect', '')}")
    embed.description = "\n".join(lines)
    embed.set_footer(text=f"Your gold: {player_gold}")
    return embed
```

### 11.2 Leaderboard Embed

```python
def leaderboard_embed(category: str, entries: list) -> discord.Embed:
    """Display leaderboard rankings."""
    titles = {"level": "Highest Level", "floor": "Deepest Floor", "kills": "Most Kills"}
    embed = discord.Embed(
        title=f"Leaderboard - {titles.get(category, category)}",
        color=discord.Color.gold())
    # Format entries with medal emojis for top 3
    return embed
```

### 11.3 Boss Encounter Embed

```python
def boss_encounter_embed(boss_name: str) -> discord.Embed:
    """Special embed shown before boss combat."""
    return discord.Embed(
        title="Boss Encounter!",
        description=f"**{boss_name}** blocks your path!",
        color=discord.Color.dark_red())
```

### 11.4 Floor Enter Embed Enhancement

Update dungeon enter embed to show floor name/theme:

```python
FLOOR_NAMES = {
    1: "The Goblin Warrens",
    2: "The Winding Tunnels",
    3: "The Rat King's Domain",
    4: "The Deep Halls",
    5: "The Goblin King's Throne",
}
```

---

## 12. Modifications to Existing Files

### 12.1 `data/maps.json`

Add 4 new floor definitions (Floors 2-5) with their tile grids as specified in Section 5.

### 12.2 `data/enemies.json`

Add boss entry:
```json
{"type": "goblin_king", "level": 16, "damage_min": 45, "damage_max": 60, "hp": 500, "xp_reward": 800, "is_boss": true, "name": "Goblin King"}
```

### 12.3 `data/loot_tables.json`

Add boss loot table:
```json
"goblin_king": [
  {"id": "kings_treasury", "name": "King's Treasury", "type": "valuable", "gold_min": 50, "gold_max": 150},
  {"id": "royal_goblin_crown", "name": "Royal Goblin Crown", "type": "valuable", "gold_min": 75, "gold_max": 200}
]
```

### 12.4 `src/game/constants.py`

Add:
```python
# --- Floor Scaling ---
FLOOR_ENEMY_LEVELS = {
    1: (1, 3), 2: (3, 5), 3: (5, 8), 4: (8, 12), 5: (12, 16),
}
FLOOR_ENEMY_COUNTS = {
    1: (1, 2), 2: (1, 3), 3: (2, 3), 4: (2, 4), 5: (2, 4),
}
FLOOR_BOSSES = {
    5: "goblin_king",
}
FLOOR_NAMES = {
    1: "The Goblin Warrens",
    2: "The Winding Tunnels",
    3: "The Rat King's Domain",
    4: "The Deep Halls",
    5: "The Goblin King's Throne",
}

# --- Shop ---
SHOP_PRICES = {
    "minor_healing_potion": 15,
    "healing_potion": 30,
    "greater_healing_potion": 60,
    "minor_mana_potion": 15,
    "mana_potion": 30,
    "greater_mana_potion": 60,
    "stamina_tonic": 20,
    "greater_stamina_tonic": 40,
    "antidote": 25,
    "smoke_bomb": 35,
    "fire_bomb": 40,
    "frost_bomb": 40,
    "healing_fruit": 50,
    "elixir_of_fortitude": 75,
    "scroll_of_teleportation": 100,
}

# --- Boss Loot ---
BOSS_LOOT_RULES = {
    "goblin_king": {
        "guaranteed_rarity_min": "rare",
        "drop_count": 2,
        "bonus_gold": (100, 250),
    },
}
```

### 12.5 `src/game/combat.py`

- **`spawn_enemies()`**: Add `floor` parameter. Use `FLOOR_ENEMY_LEVELS` and `FLOOR_ENEMY_COUNTS` for floor-aware spawning.
- **Add `spawn_boss()`**: New function to spawn boss enemies from enemy data.
- **`calculate_rewards()`**: Check if any enemy is a boss; if so, apply boss loot rules (guaranteed drops, higher rarity floor, bonus gold).

### 12.6 `src/game/dungeon.py`

- **Add `"boss"` to `is_passable()`**: Boss tiles are passable.
- **Add `TILE_EMOJIS["boss"]`**: Skull emoji for boss rooms.
- **Update `MAP_LEGEND`**: Add boss icon to legend.
- **`get_encounter_level()`**: Replace with floor-range-based level selection (or deprecate in favor of `spawn_enemies` handling it).

### 12.7 `src/bot/cogs/dungeon.py`

- **Boss tile handling** in `_handle_move()`: When entering a `"boss"` tile, check `boss_defeated` flag; if not defeated, spawn boss via `spawn_boss()`. After boss victory, set flag.
- **`/enter` command**: Add optional `floor` parameter for re-entering lower floors.
- **Exit tile**: Update `highest_floor` if new floor is higher.
- **Floor name in embeds**: Use `FLOOR_NAMES` for richer enter/map embeds.

### 12.8 `src/bot/cogs/combat.py`

- **`_send_result()` victory**: Increment `enemies_killed` count. If boss defeated, increment `bosses_killed`.
- **`/fight` command**: Pass floor to `spawn_enemies()`.
- **Boss victory embed**: Show special boss defeat message.

### 12.9 `src/db/database.py`

Add columns to players table:
```sql
enemies_killed INTEGER NOT NULL DEFAULT 0,
highest_floor INTEGER NOT NULL DEFAULT 1,
bosses_killed INTEGER NOT NULL DEFAULT 0,
```

### 12.10 `src/db/models.py`

Add:
```python
async def get_leaderboard(category: str, limit: int = 10) -> list:
    """Fetch top players for a leaderboard category."""

async def increment_player_stat(discord_id: str, stat: str, amount: int = 1) -> None:
    """Increment a player tracking stat (enemies_killed, bosses_killed)."""
```

### 12.11 `src/utils/data_loader.py`

Add:
```python
def get_boss(boss_type: str) -> Optional[dict]:
    """Return boss enemy data by type."""
    for e in _load("enemies.json"):
        if e["type"] == boss_type and e.get("is_boss"):
            return e
    return None
```

### 12.12 `src/utils/embeds.py`

Add: `shop_embed()`, `leaderboard_embed()`, `boss_encounter_embed()`
Update: `dungeon_enter_embed()` and `dungeon_map_embed()` to show floor names.

### 12.13 `bot.py`

```python
COGS = [
    ...
    "src.bot.cogs.shop",
    "src.bot.cogs.leaderboard",
]
```

---

## 13. Testing & Admin Commands

### 13.1 Existing Admin Commands (Usable for Testing)

| Command | Purpose |
|---|---|
| `/admin_fight <type> <level> <count>` | Fight specific enemies |
| `/admin_teleport <row> <col>` | Teleport to a tile |
| `/admin_give_weapon <id> <rarity>` | Give a weapon |
| `/admin_give_armor <id> <rarity>` | Give armor |
| `/admin_item <id>` | Give a consumable |

### 13.2 New Admin Commands

| Command | Purpose |
|---|---|
| `/admin_set_floor <floor>` | Set player's current floor |
| `/admin_set_gold <amount>` | Set player's gold amount |
| `/admin_boss <boss_type>` | Force a boss encounter |

### 13.3 Manual Test Script

1. **Floor 2 entry:** Complete Floor 1, `/enter` loads Floor 2 (7x7 grid)
2. **Floor 2 enemies:** Enemies are level 3-5 (not level 2)
3. **Floor 2 group size:** 1-3 enemies per encounter
4. **Floor 3 entry:** Complete Floor 2, `/enter` loads Floor 3 (9x9 grid)
5. **Floor 3 map:** Map renders correctly at 9x9 with fog of war
6. **Floor 4 combat density:** High encounter rate on Floor 4
7. **Floor 5 boss:** Moving onto boss tile triggers boss combat
8. **Boss stats:** Goblin King has 500 HP, 45-60 damage, awards 800 XP
9. **Boss loot:** Guaranteed 2 items at Rare+ rarity, bonus gold 100-250
10. **Boss re-entry:** After defeating boss, tile is passable (no re-fight)
11. **Shop browse:** `/shop` shows all consumables with prices
12. **Shop buy:** `/buy Minor Healing Potion` deducts 15 gold, adds item
13. **Shop insufficient gold:** Try buying with not enough gold -- error
14. **Shop not in dungeon:** Can only shop outside dungeon
15. **Sell all:** `/sell_all` sells all non-equipped items, shows total gold
16. **Leaderboard level:** `/leaderboard level` shows top 10 by level
17. **Leaderboard floor:** `/leaderboard floor` shows highest floor reached
18. **Leaderboard kills:** `/leaderboard kills` shows most enemies killed
19. **Enemy kill tracking:** Kill enemies, verify `enemies_killed` increments
20. **Highest floor tracking:** Complete floor, verify `highest_floor` updates
21. **Re-enter lower floor:** `/enter 1` re-enters Floor 1 (not highest floor)
22. **Floor names:** Enter/map embeds show floor name (e.g., "The Goblin Warrens")
23. **Item scaling on floor 3+:** Items dropped on Floor 3 have affix base 1 (floors 5-8), Floor 6+ would have base 2
24. **Boss killed tracking:** Defeat boss, verify `bosses_killed` increments

---

## 14. Validation Checklist

### Multi-Floor Maps
- [ ] Floors 2-5 load correctly from `maps.json`
- [ ] All floors have valid start and exit tiles
- [ ] No unreachable passable tiles (all paths connected)
- [ ] Map rendering works for both 7x7 and 9x9 grids
- [ ] Boss tile renders with skull emoji
- [ ] Fog of war works on all floors

### Enemy Scaling
- [ ] Floor 1 enemies are level 1-3
- [ ] Floor 3 enemies are level 5-8
- [ ] Floor 5 enemies are level 12-16
- [ ] Group sizes increase with floor
- [ ] Enemy data exists for all levels in all floor ranges

### Boss System
- [ ] Boss tile triggers boss encounter
- [ ] Boss has correct HP/damage/XP
- [ ] Boss defeat gives guaranteed Rare+ loot
- [ ] Boss tile becomes passable after defeat
- [ ] Boss cannot be re-fought in same session
- [ ] Boss victory tracked in player stats

### Shop
- [ ] `/shop` displays all consumables with prices
- [ ] `/buy` deducts gold and adds item
- [ ] Cannot buy with insufficient gold
- [ ] Cannot buy when inventory is full
- [ ] Cannot shop while in dungeon
- [ ] `/sell_all` removes all unequipped items and adds gold

### Leaderboard
- [ ] `/leaderboard` shows top 10 players
- [ ] Level, floor, and kills categories work
- [ ] Enemies killed increments on combat victory
- [ ] Highest floor updates on floor completion
- [ ] Bosses killed increments on boss defeat

### Floor Progression
- [ ] Completing floor N unlocks floor N+1
- [ ] `/enter` defaults to highest unlocked floor
- [ ] `/enter <floor>` allows re-entering lower floors
- [ ] Floor names display in embeds
- [ ] `current_floor` and `highest_floor` tracked correctly

### Edge Cases
- [ ] Floor 5 completion doesn't break (no Floor 6 yet)
- [ ] Boss tile on revisit (already defeated) doesn't trigger combat
- [ ] Shop works with 0 gold
- [ ] Leaderboard with 0 players doesn't crash
- [ ] New columns default correctly for existing players
