# Stage 5 Workbook -- Items, Equipment & Loot

**Purpose:** Comprehensive build spec for Stage 5. Full item system with weapons, armor, consumables, rarity tiers, procedural stat affixes, loot drops from enemies, and equip/unequip/inventory management. Equipped weapons replace unarmed damage, equipped armor provides damage reduction, and stat affixes grant bonus stats.

---

## Table of Contents

1. [What Already Exists](#1-what-already-exists)
2. [Files to Create](#2-files-to-create)
3. [Files to Modify](#3-files-to-modify)
4. [Design Decisions](#4-design-decisions)
5. [Item Data Model](#5-item-data-model)
6. [Procedural Item Generation](#6-procedural-item-generation)
7. [Weapon System](#7-weapon-system)
8. [Armor System](#8-armor-system)
9. [Stat Affix System](#9-stat-affix-system)
10. [Equipment System](#10-equipment-system)
11. [Inventory System](#11-inventory-system)
12. [Loot Drop System](#12-loot-drop-system)
13. [Combat Integration](#13-combat-integration)
14. [Consumable Enhancements](#14-consumable-enhancements)
15. [Equipment UI -- Embeds](#15-equipment-ui----embeds)
16. [New Cog: inventory.py -- Commands](#16-new-cog-inventorypy----commands)
17. [Modifications to Existing Files](#17-modifications-to-existing-files)
18. [Testing & Admin Commands](#18-testing--admin-commands)
19. [Validation Checklist](#19-validation-checklist)

---

## 1. What Already Exists

| Component | Location | What it provides |
|---|---|---|
| Weapons data (59 weapons) | `data/weapons.json` | id, name, class_theme, hand_type (one_hand/two_hand/off_hand), casting flag, damage_type |
| Armor data (163 items) | `data/armor.json` | id, name, armor_type (cloth/leather/heavy), slot, ar_min, ar_max, allowed_classes |
| Consumables (15 items) | `data/consumables.json` | Full consumable definitions with effects |
| Loot tables | `data/loot_tables.json` | Goblin (5 drops) and Feral Rat (3 drops) with gold ranges |
| Data loader | `src/utils/data_loader.py` | `get_weapons()`, `get_armor()`, `get_consumables()`, `get_loot_table()` |
| Constants | `src/game/constants.py` | `WEAPON_DAMAGE_RANGES`, `WEAPON_DROP_CHANCES`, `ARMOR_RARITY_MULTIPLIERS`, `STAT_AFFIX_RULES`, `AFFIX_BASE_PER_FLOOR_GROUP`, `ARMOR_REDUCTION_CONSTANT`, `MAX_AR_BY_SLOT`, `RARITY_TIERS` |
| Formulas | `src/game/formulas.py` | `calc_armor_reduction()` already implemented |
| DB schema | `src/db/database.py` | `inventories` table with item_type, item_id, item_data (JSON), equipped, slot, quantity |
| DB models | `src/db/models.py` | `add_inventory_item()`, `get_inventory()`, `equip_item()`, `unequip_item()`, `remove_inventory_item()` |
| Combat engine | `src/game/combat.py` | `_player_damage()` uses `UNARMED_DAMAGE_MIN/MAX` -- needs weapon integration |
| Combat cog | `src/bot/cogs/combat.py` | `_send_result()` handles loot -- needs enhanced loot generation |
| Embeds | `src/utils/embeds.py` | `error_embed()`, `success_embed()`, `CLASS_COLORS`, `character_sheet_embed()` |

---

## 2. Files to Create

| File | Purpose |
|---|---|
| `src/game/items.py` | Item generation engine: procedural weapon/armor generation, stat affix rolling, rarity selection, loot rolling |
| `src/bot/cogs/inventory.py` | Inventory/equipment cog: `/inventory`, `/inspect`, `/equip`, `/unequip`, `/sell` commands |

---

## 3. Files to Modify

| File | Change |
|---|---|
| `bot.py` | Add `"src.bot.cogs.inventory"` to COGS list |
| `src/game/combat.py` | Modify `_player_damage()` to use equipped weapon damage instead of unarmed; modify `_enemy_damage()` to apply armor reduction |
| `src/bot/cogs/combat.py` | Modify `_send_result()` to use enhanced loot generation; add stat affix application from equipment |
| `src/db/models.py` | Add `get_equipped_items()`, `get_equipped_in_slot()`, `count_inventory()` |
| `src/utils/embeds.py` | Add `inventory_embed()`, `item_inspect_embed()`, `equip_embed()`, `loot_drop_embed()` |
| `src/utils/data_loader.py` | Add `get_weapon_by_id()`, `get_armor_by_id()` |
| `src/game/constants.py` | Add inventory capacity constant |

---

## 4. Design Decisions

### 4.1 Resolved from Implementation Plan

| Decision | Resolution |
|---|---|
| Goblin Equipment Drops | Generate from weapon/armor tables at Poor/Common rarity |
| Weapon Drop % Gap (0.9%) | Added to Poor rarity (50% -> 50.9%) -- already in constants |
| Inventory Capacity | 20 slots (as recommended in plan) |

### 4.2 New Decisions for Stage 5

| Decision | Resolution | Rationale |
|---|---|---|
| Weapons class-restricted? | No. Any class can equip any weapon (per PDF: "weapons are not class specific") | Follows design doc explicitly |
| Armor class-restricted? | Yes. Armor has `allowed_classes` field in data | Design doc shows specific class restrictions per armor piece |
| Two-hand vs one-hand+off-hand | Two-hand blocks off-hand slot. One-hand allows off-hand. No damage bonus for two-hand | PDF lists hand types but defines no mechanical bonus for two-hand |
| Equipped weapon damage | Replace unarmed range with weapon rarity damage range. If no weapon, fall back to unarmed (5-10) | Natural progression from Stage 3 |
| Sell items | `/sell <item>` sells for gold. Valuables sell at their gold range. Equipment sells at a fraction based on rarity | Need gold sink and item management |
| Item generation on loot | Generate complete item_data with rarity, damage/AR, and stat affixes at drop time, store in item_data JSON | Avoids re-rolling stats; item is permanent once created |
| Stat affixes from equipment | Sum all stat bonuses from equipped items, apply as temporary bonuses during combat | Simplest approach; stats on character sheet show base + equipment |
| Loot drop flow | Auto-add to inventory after combat victory (no separate `/loot` command) | Smoother UX, one less command |
| Consumables outside combat | `/use_item <name>` outside combat for healing potions etc. | Consumables should work anytime per design doc |

---

## 5. Item Data Model

### 5.1 Generated Item Structure (stored in `item_data` JSON)

**Weapon:**
```json
{
  "type": "weapon",
  "base_id": "long_sword",
  "name": "Rare Long Sword",
  "class_theme": "warrior",
  "hand_type": "two_hand",
  "casting": false,
  "damage_type": "slash",
  "rarity": "rare",
  "damage_min": 18,
  "damage_max": 26,
  "stat_affixes": [
    {"stat": "strength", "value": 4},
    {"stat": "dexterity", "value": 2}
  ],
  "floor_found": 3,
  "sell_value": 15
}
```

**Armor:**
```json
{
  "type": "armor",
  "base_id": "iron_helm",
  "name": "Epic Iron Helm",
  "armor_type": "heavy",
  "slot": "head",
  "allowed_classes": ["warrior", "cleric", "ranger"],
  "rarity": "epic",
  "armor_rating": 48,
  "stat_affixes": [
    {"stat": "endurance", "value": 6},
    {"stat": "strength", "value": 4},
    {"stat": "agility", "value": 2}
  ],
  "floor_found": 3,
  "sell_value": 25
}
```

**Consumable (existing format, unchanged):**
```json
{
  "type": "consumable",
  "id": "minor_healing_potion",
  "name": "Minor Healing Potion",
  "category": "healing",
  "effect": "Restores 10 HP.",
  "resource": "hp",
  "value": 10
}
```

### 5.2 Inventory Row Mapping

| Column | Weapon | Armor | Consumable |
|---|---|---|---|
| `item_type` | `"weapon"` | `"armor"` | `"consumable"` |
| `item_id` | base weapon id (e.g. `"long_sword"`) | base armor id (e.g. `"iron_helm"`) | consumable id |
| `item_data` | Full generated JSON | Full generated JSON | Consumable definition JSON |
| `equipped` | 0 or 1 | 0 or 1 | 0 |
| `slot` | `"main_hand"` or `"off_hand"` | armor slot name | NULL |

---

## 6. Procedural Item Generation

### 6.1 Rarity Selection

Roll against `WEAPON_DROP_CHANCES` (same distribution for armor):

| Rarity | Chance |
|---|---|
| Poor | 50.9% |
| Common | 30.0% |
| Uncommon | 10.0% |
| Rare | 5.0% |
| Epic | 4.0% |
| Legendary | 0.1% |

```python
def roll_rarity() -> str:
    """Roll a rarity tier using weighted distribution."""
    roll = random.uniform(0, 100)
    cumulative = 0
    for rarity, chance in WEAPON_DROP_CHANCES.items():
        cumulative += chance
        if roll <= cumulative:
            return rarity
    return "poor"
```

### 6.2 Weapon Generation

```python
def generate_weapon(base_weapon: dict, rarity: str, floor: int) -> dict:
    """
    Generate a complete weapon item.
    - base_weapon: entry from weapons.json
    - rarity: rolled rarity tier
    - floor: dungeon floor (for affix scaling)
    Returns full item_data dict.
    """
    dmg_min, dmg_max = WEAPON_DAMAGE_RANGES[rarity]
    affixes = generate_stat_affixes(rarity, floor)
    sell = calculate_sell_value("weapon", rarity)
    rarity_label = rarity.capitalize()
    name = f"{rarity_label} {base_weapon['name']}" if rarity != "common" else base_weapon["name"]
    return {
        "type": "weapon",
        "base_id": base_weapon["id"],
        "name": name,
        "class_theme": base_weapon["class_theme"],
        "hand_type": base_weapon["hand_type"],
        "casting": base_weapon["casting"],
        "damage_type": base_weapon["damage_type"],
        "rarity": rarity,
        "damage_min": dmg_min,
        "damage_max": dmg_max,
        "stat_affixes": affixes,
        "floor_found": floor,
        "sell_value": sell,
    }
```

### 6.3 Armor Generation

```python
def generate_armor(base_armor: dict, rarity: str, floor: int) -> dict:
    """
    Generate a complete armor item.
    - base_armor: entry from armor.json
    - rarity: rolled rarity tier
    - floor: dungeon floor (for affix scaling)
    Returns full item_data dict.
    """
    base_ar = random.randint(base_armor["ar_min"], base_armor["ar_max"])
    if rarity in ARMOR_RARITY_MULTIPLIERS:
        mult_min, mult_max = ARMOR_RARITY_MULTIPLIERS[rarity]
        mult = random.uniform(mult_min, mult_max)
        ar = int(base_ar * mult)
    else:
        ar = base_ar  # Poor rarity = 1x
    max_ar = MAX_AR_BY_SLOT.get(base_armor["slot"], 100)
    ar = min(ar, max_ar)

    affixes = generate_stat_affixes(rarity, floor)
    sell = calculate_sell_value("armor", rarity)
    rarity_label = rarity.capitalize()
    name = f"{rarity_label} {base_armor['name']}" if rarity != "common" else base_armor["name"]
    return {
        "type": "armor",
        "base_id": base_armor["id"],
        "name": name,
        "armor_type": base_armor["armor_type"],
        "slot": base_armor["slot"],
        "allowed_classes": base_armor["allowed_classes"],
        "rarity": rarity,
        "armor_rating": ar,
        "stat_affixes": affixes,
        "floor_found": floor,
        "sell_value": sell,
    }
```

### 6.4 Sell Value Calculation

```python
SELL_VALUES = {
    "poor": 1, "common": 3, "uncommon": 8,
    "rare": 20, "epic": 50, "legendary": 150,
}

def calculate_sell_value(item_type: str, rarity: str) -> int:
    base = SELL_VALUES.get(rarity, 1)
    if item_type == "weapon":
        return base * 2
    return base
```

---

## 7. Weapon System

### 7.1 Weapon Damage Ranges by Rarity

From constants (already defined):

| Rarity | Damage Range |
|---|---|
| Poor | 3-11 |
| Common | 9-16 |
| Uncommon | 13-21 |
| Rare | 18-26 |
| Epic | 23-31 |
| Legendary | 28-36 |

### 7.2 Weapon Hand Types

| Hand Type | Slot Used | Off-hand? |
|---|---|---|
| `one_hand` | `main_hand` | Off-hand slot available |
| `two_hand` | `main_hand` | Off-hand slot BLOCKED |
| `off_hand` | `off_hand` | Requires one-hand in main_hand |

### 7.3 Weapon Damage in Combat

Replace the current unarmed base damage in `_player_damage()`:

```python
# Current (Stage 3):
base = random.randint(UNARMED_DAMAGE_MIN, UNARMED_DAMAGE_MAX)

# New (Stage 5):
weapon = get_equipped_weapon(player)
if weapon:
    base = random.randint(weapon["damage_min"], weapon["damage_max"])
else:
    base = random.randint(UNARMED_DAMAGE_MIN, UNARMED_DAMAGE_MAX)
```

### 7.4 Casting Weapons

Weapons with `casting: true` provide their base damage for spell attacks instead of physical attacks. The existing spell damage formula already uses Intelligence/Charisma bonuses on top of base damage; the weapon just provides a higher base.

### 7.5 Weapon Data (59 weapons, all in `data/weapons.json`)

Classes and counts:
- Warrior: 10 (mostly two_hand, 2 one_hand, 1 off_hand)
- Mage: 10 (mostly off_hand casting, 2 one_hand physical, 3 two_hand casting)
- Ranger: 10 (mix of two_hand ranged and one_hand melee)
- Rogue: 9 (mostly one_hand, 2 two_hand)
- Bard: 10 (mostly two_hand instruments, 1 one_hand)
- Cleric: 10 (mix of one_hand, two_hand, off_hand with casting)

---

## 8. Armor System

### 8.1 Armor Rating Formula

Already implemented in `calc_armor_reduction()`:
```
damage_reduction_pct = (total_AR / (total_AR + 500)) * 100
```

Examples:
- 50 AR = 9.1% reduction
- 100 AR = 16.7% reduction
- 200 AR = 28.6% reduction
- 500 AR = 50% reduction

### 8.2 Armor Types and Base AR Ranges

| Type | Slot | Base AR |
|---|---|---|
| Cloth | Head | 1-6 |
| Cloth | Shoulders | 1-6 |
| Cloth | Chest | 1-8 |
| Cloth | Gloves | 1-5 |
| Cloth | Legs | 1-7 |
| Cloth | Feet | 1-5 |
| Leather | Head | 7-13 |
| Leather | Shoulders | 7-13 |
| Leather | Chest | 9-16 |
| Leather | Gloves | 6-10 |
| Leather | Legs | 8-13 |
| Leather | Feet | 6-10 |
| Heavy | Head | 14-20 |
| Heavy | Shoulders | 14-18 |
| Heavy | Chest | 17-25 |
| Heavy | Gloves | 11-15 |
| Heavy | Legs | 14-20 |
| Heavy | Feet | 11-15 |

### 8.3 Rarity Multipliers on AR

From constants (already defined):

| Rarity | Multiplier Range |
|---|---|
| Poor | 1.0x (implicit) |
| Common | 1.1x - 1.5x |
| Uncommon | 1.5x - 2.0x |
| Rare | 2.0x - 2.5x |
| Epic | 2.5x - 3.0x |
| Legendary | 3.0x - 5.0x |

### 8.4 Max AR Per Slot (cap)

From constants (already defined):

| Slot | Max AR |
|---|---|
| Head | 100 |
| Shoulders | 90 |
| Chest | 110 |
| Gloves | 80 |
| Legs | 90 |
| Feet | 80 |

### 8.5 Equipment Slots

Six armor slots + two weapon slots:
```python
ARMOR_SLOTS = ["head", "shoulders", "chest", "gloves", "legs", "feet"]
WEAPON_SLOTS = ["main_hand", "off_hand"]
ALL_EQUIPMENT_SLOTS = ARMOR_SLOTS + WEAPON_SLOTS
```

### 8.6 Class Restrictions

Armor has `allowed_classes` list. Validation on equip:
```python
if player["class"] not in armor_item["allowed_classes"]:
    return "Your class cannot wear this armor."
```

Weapons have NO class restriction (per design doc).

### 8.7 Armor Damage Reduction in Combat

Modify `_enemy_damage()` in combat.py to apply armor reduction:
```python
total_ar = sum(item["armor_rating"] for item in equipped_armor)
reduction_pct = calc_armor_reduction(total_ar)
raw_damage = ... # existing calculation
final_damage = max(1, int(raw_damage * (1 - reduction_pct / 100)))
```

---

## 9. Stat Affix System

### 9.1 Affix Rules by Rarity

From constants (already defined in `STAT_AFFIX_RULES`):

| Rarity | # Affixes | Multipliers |
|---|---|---|
| Poor | 0 | -- |
| Common | 0 | -- |
| Uncommon | 1 | [1x] |
| Rare | 2 | [2x, 1x] |
| Epic | 3 | [3x, 2x, 1x] |
| Legendary | 3 | [3x, 3x, 2x] |

### 9.2 Floor Scaling

From constants (`AFFIX_BASE_PER_FLOOR_GROUP = 1`):

| Floor Range | Base Value |
|---|---|
| 1-5 | 1 |
| 6-10 | 2 |
| 11-15 | 3 |
| 16-20 | 4 |

```python
def get_affix_base(floor: int) -> int:
    """Base affix value increases by 1 every 5 floors."""
    return 1 + (floor - 1) // 5
```

### 9.3 Affix Generation

```python
def generate_stat_affixes(rarity: str, floor: int) -> list:
    """Generate random stat affixes for an item."""
    rules = STAT_AFFIX_RULES[rarity]
    if rules["count"] == 0:
        return []

    base = get_affix_base(floor)
    stats = random.sample(ALL_STATS, rules["count"])
    affixes = []
    for i, stat in enumerate(stats):
        value = base * rules["multipliers"][i]
        affixes.append({"stat": stat, "value": value})
    return affixes
```

### 9.4 Affix Application

Sum stat bonuses from all equipped items with affixes:
```python
def calc_equipment_stat_bonuses(equipped_items: list) -> dict:
    """Sum all stat affixes from equipped items."""
    bonuses = {}
    for item in equipped_items:
        idata = json.loads(item["item_data"])
        for affix in idata.get("stat_affixes", []):
            stat = affix["stat"]
            bonuses[stat] = bonuses.get(stat, 0) + affix["value"]
    return bonuses
```

These bonuses are added to the player's base stats when calculating combat values and displaying the character sheet.

---

## 10. Equipment System

### 10.1 Equip Flow

```
Player issues /equip <item_name>
    |
    v
Find item in inventory by name match
    |
    v
Validate: is it weapon or armor? (not consumable)
    |
    v
For armor: check allowed_classes includes player class
    |
    v
Determine target slot:
  - Armor: use item's slot field
  - One-hand weapon: main_hand
  - Two-hand weapon: main_hand (also clears off_hand)
  - Off-hand weapon: off_hand (requires one_hand in main_hand)
    |
    v
Unequip existing item in target slot (if any)
    |
    v
Mark new item as equipped in target slot
    |
    v
Show equip confirmation embed
```

### 10.2 Unequip Flow

```
Player issues /unequip <slot>
    |
    v
Find equipped item in slot
    |
    v
Mark item as unequipped (equipped=0, slot=NULL)
    |
    v
Show unequip confirmation
```

### 10.3 Two-Hand / Off-Hand Rules

- Equipping a **two-hand** weapon: auto-unequips anything in off_hand
- Equipping an **off-hand** weapon: requires a one_hand weapon in main_hand. If main_hand is two_hand, reject
- Equipping a **one-hand** weapon in main_hand: off_hand stays as-is

### 10.4 Equipment Helper Functions

```python
async def get_equipped_items(player_id: int) -> list:
    """Get all equipped items for a player."""

async def get_equipped_in_slot(player_id: int, slot: str) -> Optional[dict]:
    """Get the item equipped in a specific slot."""

async def get_equipped_weapon(player_id: int) -> Optional[dict]:
    """Get the equipped main_hand weapon item_data."""

async def get_total_armor_rating(player_id: int) -> int:
    """Sum AR from all equipped armor pieces."""
```

---

## 11. Inventory System

### 11.1 Inventory Capacity

```python
INVENTORY_CAPACITY = 20
```

Check on item add:
```python
async def can_add_to_inventory(player_id: int) -> bool:
    count = await count_inventory(player_id)
    return count < INVENTORY_CAPACITY
```

### 11.2 Inventory Display

Group items by type in the embed:
- Equipped weapons (with slot label)
- Equipped armor (with slot label)
- Unequipped weapons
- Unequipped armor
- Consumables (with quantity if stacking)

### 11.3 Sell System

```python
def get_sell_price(item_data: dict) -> int:
    """Calculate sell price for an item."""
    if item_data.get("type") in ("weapon", "armor"):
        return item_data.get("sell_value", 1)
    # Valuables from loot tables
    if item_data.get("type") == "valuable":
        return random.randint(
            item_data.get("gold_min", 1),
            item_data.get("gold_max", 1))
    # Consumables sell for 1 gold
    return 1
```

---

## 12. Loot Drop System

### 12.1 Drop Flow (on enemy kill)

```
Enemy killed
    |
    v
Roll for enemy-specific drop (from loot_tables.json): 50% chance
    |
    v
Roll for equipment drop: separate 50% chance
    |
    v
If equipment drop:
  - Roll rarity (50.9% Poor ... 0.1% Legendary)
  - Roll type: 50% weapon, 50% armor
  - Pick random base item from data files
  - Generate full item with rarity, affixes, etc.
    |
    v
Add all drops to rewards list
```

### 12.2 Loot Generation Function

```python
def generate_loot(enemy_type: str, floor: int, player_class: str) -> list:
    """
    Generate loot drops from a killed enemy.
    Returns list of item dicts ready for inventory insertion.
    """
    drops = []

    # Enemy-specific drops (50% chance)
    if random.random() < LOOT_DROP_CHANCE:
        loot_table = get_loot_table(enemy_type)
        if loot_table:
            drop = random.choice(loot_table)
            drops.append(drop)

    # Equipment drop (50% chance)
    if random.random() < LOOT_DROP_CHANCE:
        rarity = roll_rarity()
        if random.random() < 0.5:
            # Weapon
            weapons = get_weapons()
            base = random.choice(weapons)
            item = generate_weapon(base, rarity, floor)
        else:
            # Armor (prefer items the player can wear)
            armor_list = get_armor(class_name=player_class)
            if not armor_list:
                armor_list = get_armor()
            base = random.choice(armor_list)
            item = generate_armor(base, rarity, floor)
        drops.append(item)

    return drops
```

### 12.3 Integration with Combat Victory

Replace the current loot handling in `calculate_rewards()` and `_send_result()`:

```python
# In _send_result for victory:
loot = generate_loot(enemy_type, floor, player_class)
for item in loot:
    if await can_add_to_inventory(player_id):
        item_type = item.get("type", "consumable")
        item_id = item.get("base_id", item.get("id", "unknown"))
        await add_inventory_item(player_id, item_type, item_id, item)
    else:
        # Inventory full -- auto-sell
        gold += get_sell_price(item)
```

---

## 13. Combat Integration

### 13.1 Weapon Damage (modify `_player_damage`)

```python
def _get_equipped_weapon_data(player: dict) -> Optional[dict]:
    """Extract weapon data from player's equipment info.
    This will be passed in from the cog layer which has DB access."""
    return player.get("_equipped_weapon")

def _player_damage(player, state, skill=None, attack_type="slash", tgt=None):
    weapon = _get_equipped_weapon_data(player)
    if weapon:
        base = random.randint(weapon["damage_min"], weapon["damage_max"])
        is_casting = weapon.get("casting", False)
    else:
        base = random.randint(UNARMED_DAMAGE_MIN, UNARMED_DAMAGE_MAX)
        is_casting = False

    # For spells, use weapon base only if it's a casting weapon
    is_spell = skill and skill.get("type") in ("ice_spell", "fire_spell", "spell")
    if is_spell and not is_casting and weapon:
        # Non-casting weapon: use unarmed base for spells
        base = random.randint(UNARMED_DAMAGE_MIN, UNARMED_DAMAGE_MAX)

    # ... rest of damage calc unchanged
```

### 13.2 Armor Damage Reduction (modify `_enemy_damage`)

```python
def _enemy_damage(enemy, player, state):
    # ... existing absorb/untargetable checks ...

    raw = random.randint(enemy["damage_min"], enemy["damage_max"])

    # ... existing debuff modifiers ...

    # Apply armor reduction
    total_ar = player.get("_total_ar", 0)
    if total_ar > 0:
        reduction = calc_armor_reduction(total_ar)
        raw = max(1, int(raw * (1 - reduction / 100)))

    # ... rest of calculation ...
```

### 13.3 Stat Affix Bonuses in Combat

Before starting combat, the cog layer loads equipment bonuses and injects them into the player dict:

```python
# In combat cog, before processing actions:
equipped = await get_equipped_items(player["id"])
bonuses = calc_equipment_stat_bonuses(equipped)
for stat, bonus in bonuses.items():
    player[stat] = player[stat] + bonus

weapon = await get_equipped_weapon(player["id"])
if weapon:
    player["_equipped_weapon"] = json.loads(weapon["item_data"])

total_ar = await get_total_armor_rating(player["id"])
player["_total_ar"] = total_ar
```

### 13.4 Warrior Armor Proficiency Talent

The talent `warrior_armor_proficiency` gives +10% defense in heavy armor. Check if player has any heavy armor equipped:

```python
if "warrior_armor_proficiency" in tids:
    has_heavy = any(
        json.loads(e["item_data"]).get("armor_type") == "heavy"
        for e in equipped if json.loads(e["item_data"]).get("type") == "armor"
    )
    if has_heavy:
        total_ar = int(total_ar * 1.10)
```

---

## 14. Consumable Enhancements

### 14.1 Use Outside Combat

Add `/use_item <name>` command that works outside combat for healing/mana/SP consumables. Already partially handled by the combat cog's `/item` command, but needs a non-combat path.

### 14.2 Sell Consumables

Consumables can be sold via `/sell` for 1 gold each.

---

## 15. Equipment UI -- Embeds

### 15.1 Inventory Embed

```python
def inventory_embed(player: dict, items: list, equipped: list) -> discord.Embed:
    """Show full inventory grouped by type with equipped markers."""
    # Section: Equipment (show each slot with item or "empty")
    # Section: Weapons (unequipped)
    # Section: Armor (unequipped)
    # Section: Consumables
    # Footer: X/20 slots used
```

### 15.2 Item Inspect Embed

```python
def item_inspect_embed(item_data: dict) -> discord.Embed:
    """Detailed item view with stats, rarity color, affixes."""
    # Title: item name
    # Color: rarity-based (grey/white/green/blue/purple/orange)
    # Fields: Type, Rarity, Damage/AR, Stat Affixes, Sell Value
```

### 15.3 Rarity Colors

```python
RARITY_COLORS = {
    "poor": discord.Color.dark_grey(),
    "common": discord.Color.light_grey(),
    "uncommon": discord.Color.green(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.orange(),
}
```

### 15.4 Equip Embed

```python
def equip_embed(item_name: str, slot: str, unequipped_name: str = None) -> discord.Embed:
    """Show equip confirmation with what was replaced."""
```

### 15.5 Loot Drop Embed Enhancement

Modify `combat_victory_embed()` to show detailed loot with rarity colors and stats.

### 15.6 Character Sheet Enhancement

Update `character_sheet_embed()` to show:
- Equipment section listing all slots
- Stats with equipment bonuses shown as `STR: 15 (+3)` where +3 is from affixes
- Total armor rating

---

## 16. New Cog: inventory.py -- Commands

### 16.1 Slash Commands

| Command | Description | Parameters |
|---|---|---|
| `/inventory` | Show full inventory | None |
| `/inspect <item>` | Show item details | `item`: name or position |
| `/equip <item>` | Equip a weapon or armor | `item`: item name (autocomplete) |
| `/unequip <slot>` | Remove equipment from slot | `slot`: equipment slot (choices) |
| `/sell <item>` | Sell an item for gold | `item`: item name (autocomplete) |
| `/use_item <item>` | Use a consumable outside combat | `item`: item name (autocomplete) |

### 16.2 Admin Commands

| Command | Description |
|---|---|
| `/admin_give_weapon <weapon_id> <rarity>` | Give a specific weapon at a rarity |
| `/admin_give_armor <armor_id> <rarity>` | Give a specific armor at a rarity |

### 16.3 Command Implementations

```python
class Inventory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction):
        """Display all items grouped by type."""

    @app_commands.command(name="inspect", description="Inspect an item")
    @app_commands.describe(item_name="Item to inspect")
    async def inspect(self, interaction, item_name: str):
        """Show detailed item stats."""

    @app_commands.command(name="equip", description="Equip a weapon or armor")
    @app_commands.describe(item_name="Item to equip")
    async def equip(self, interaction, item_name: str):
        """Equip logic with slot validation."""

    @app_commands.command(name="unequip", description="Remove equipment")
    @app_commands.describe(slot="Equipment slot")
    @app_commands.choices(slot=[
        Choice(name="Head", value="head"),
        Choice(name="Shoulders", value="shoulders"),
        Choice(name="Chest", value="chest"),
        Choice(name="Gloves", value="gloves"),
        Choice(name="Legs", value="legs"),
        Choice(name="Feet", value="feet"),
        Choice(name="Main Hand", value="main_hand"),
        Choice(name="Off Hand", value="off_hand"),
    ])
    async def unequip(self, interaction, slot: Choice[str]):
        """Unequip from slot."""

    @app_commands.command(name="sell", description="Sell an item for gold")
    @app_commands.describe(item_name="Item to sell")
    async def sell(self, interaction, item_name: str):
        """Sell item, add gold, remove from inventory."""

    @app_commands.command(name="use_item", description="Use a consumable")
    @app_commands.describe(item_name="Consumable to use")
    async def use_item(self, interaction, item_name: str):
        """Use consumable outside combat."""
```

---

## 17. Modifications to Existing Files

### 17.1 `bot.py`

```python
COGS = [
    "src.bot.cogs.general",
    "src.bot.cogs.character",
    "src.bot.cogs.leveling",
    "src.bot.cogs.combat",
    "src.bot.cogs.dungeon",
    "src.bot.cogs.inventory",  # NEW
]
```

### 17.2 `src/game/combat.py`

- Modify `_player_damage()`: use equipped weapon damage range (passed via `player["_equipped_weapon"]`)
- Modify `_enemy_damage()`: apply armor reduction (passed via `player["_total_ar"]`)
- Modify `calculate_rewards()`: use new `generate_loot()` from items.py instead of simple loot table roll

### 17.3 `src/bot/cogs/combat.py`

- Before combat actions: load equipped items, inject weapon data and AR into player dict
- On victory: use enhanced loot generation, handle inventory capacity
- Update `_send_result()` to show detailed loot

### 17.4 `src/db/models.py`

Add:
```python
async def get_equipped_items(player_id: int) -> list:
    """Get all equipped items."""

async def get_equipped_in_slot(player_id: int, slot: str) -> Optional[dict]:
    """Get item in a specific slot."""

async def count_inventory(player_id: int) -> int:
    """Count total inventory items."""
```

### 17.5 `src/utils/embeds.py`

Add: `inventory_embed()`, `item_inspect_embed()`, `equip_embed()`, `RARITY_COLORS`

Update: `character_sheet_embed()` to show equipment and affix bonuses

### 17.6 `src/utils/data_loader.py`

Add:
```python
def get_weapon_by_id(weapon_id: str) -> Optional[dict]:
def get_armor_by_id(armor_id: str) -> Optional[dict]:
```

### 17.7 `src/game/constants.py`

Add:
```python
INVENTORY_CAPACITY = 20
EQUIPMENT_SELL_VALUES = {
    "poor": 1, "common": 3, "uncommon": 8,
    "rare": 20, "epic": 50, "legendary": 150,
}
```

---

## 18. Testing & Admin Commands

### 18.1 Admin Commands

| Command | What it does |
|---|---|
| `/admin_give_weapon <weapon_id> <rarity>` | Give a weapon at specific rarity (e.g. `long_sword rare`) |
| `/admin_give_armor <armor_id> <rarity>` | Give armor at specific rarity (e.g. `iron_helm epic`) |

### 18.2 Manual Test Script

1. **Give weapon:** `/admin_give_weapon long_sword common` -- verify item in inventory
2. **Inspect item:** `/inspect Long Sword` -- verify damage range, rarity, affixes shown
3. **Equip weapon:** `/equip Long Sword` -- verify equipped in main_hand
4. **Inventory display:** `/inventory` -- verify item shows as equipped
5. **Combat with weapon:** `/fight` and attack -- verify weapon damage range used (not 5-10 unarmed)
6. **Unequip weapon:** `/unequip main_hand` -- verify returned to inventory
7. **Give armor:** `/admin_give_armor iron_helm rare` -- verify item with AR and affixes
8. **Equip armor (valid class):** Warrior equips iron_helm -- should work
9. **Equip armor (wrong class):** Mage tries to equip iron_helm -- should fail
10. **Armor damage reduction:** Equip armor, fight, verify damage reduced
11. **Two-hand weapon:** Equip two-hand, verify off_hand cleared
12. **Off-hand weapon:** Equip one-hand + off-hand, verify both slots
13. **Off-hand with two-hand:** Try equipping off-hand while two-hand equipped -- should fail
14. **Stat affixes:** Equip uncommon+ item, verify stat bonus on character sheet
15. **Sell item:** `/sell Long Sword` -- verify gold gained, item removed
16. **Inventory capacity:** Fill to 20, try to add more -- should auto-sell overflow
17. **Loot generation:** Kill enemies, verify weapon/armor drops with correct rarity distribution
18. **Floor-scaled affixes:** Generate items on floor 6+ -- verify base affix value = 2
19. **Use consumable outside combat:** `/use_item Minor Healing Potion` -- verify HP restored
20. **Rarity distribution:** Admin-generate 100 items, verify distribution approximately matches
21. **Character sheet update:** `/stats` shows equipment section and stat bonuses
22. **Legendary weapon:** `/admin_give_weapon great_sword legendary` -- verify high damage and 3 affixes
23. **Equipment on death:** Die in dungeon with equipped items -- verify they are kept
24. **AR cap:** Generate legendary heavy chest -- verify AR doesn't exceed 110
25. **Casting weapon for spells:** Equip casting weapon, cast spell -- verify spell uses weapon base damage

---

## 19. Validation Checklist

### Item Generation
- [ ] Weapons generate with correct damage range per rarity
- [ ] Armor generates with correct AR (base * rarity multiplier, capped at max)
- [ ] Stat affixes generate with correct count and multipliers per rarity
- [ ] Floor scaling increases affix base value every 5 floors
- [ ] Rarity roll distribution matches WEAPON_DROP_CHANCES
- [ ] Items have correct names (e.g. "Rare Long Sword")
- [ ] Sell values calculate correctly per rarity

### Equipment
- [ ] `/equip` works for weapons and armor
- [ ] Class restriction enforced on armor
- [ ] Two-hand weapon clears off-hand
- [ ] Off-hand blocked when two-hand equipped
- [ ] `/unequip` returns item to inventory
- [ ] Equipped items shown in `/inventory` with slot labels
- [ ] Only one item per slot

### Combat Integration
- [ ] Equipped weapon damage replaces unarmed damage
- [ ] Casting weapon provides base damage for spells
- [ ] Non-casting weapon falls back to unarmed for spells
- [ ] Armor rating reduces incoming damage
- [ ] Armor Proficiency talent applies +10% AR for warriors with heavy armor
- [ ] Stat affixes from equipment affect combat calculations
- [ ] Equipment bonuses shown on character sheet

### Loot System
- [ ] Enemies drop loot on kill (50% chance)
- [ ] Equipment drops generated with correct rarity
- [ ] Drops auto-added to inventory
- [ ] Inventory full -> auto-sell overflow loot
- [ ] Enemy-specific drops (valuables, usables) work correctly

### Inventory Management
- [ ] `/inventory` shows all items grouped by type
- [ ] `/inspect` shows full item details
- [ ] `/sell` removes item and adds gold
- [ ] Cannot sell equipped items
- [ ] Inventory capacity enforced at 20
- [ ] `/use_item` works outside combat for consumables

### Edge Cases
- [ ] Equipping replaces existing item in slot (old item returns to inventory)
- [ ] Death keeps equipped items, loses unequipped
- [ ] Items survive bot restart (persisted in DB)
- [ ] Autocomplete works for item names
- [ ] Rarity colors display correctly in embeds
