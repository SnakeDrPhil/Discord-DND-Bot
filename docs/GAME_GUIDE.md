# Dungeon Crawler -- Complete Game Guide

This guide covers everything you need to know to play the Dungeon Crawler Discord bot, from creating your first character to defeating the Goblin King.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [Classes](#2-classes)
3. [Stats & Attributes](#3-stats--attributes)
4. [Leveling & Progression](#4-leveling--progression)
5. [Skills](#5-skills)
6. [Talents](#6-talents)
7. [Combat](#7-combat)
8. [Dungeon Exploration](#8-dungeon-exploration)
9. [Equipment](#9-equipment)
10. [Inventory & Shop](#10-inventory--shop)
11. [Tips & Strategy](#11-tips--strategy)

---

## 1. Getting Started

### Creating a Character

Use `/create <name> <class>` to create your character. Names can be 2-32 characters long and contain letters, numbers, spaces, hyphens, and apostrophes.

Use `/classinfo <class>` before creating to see a class's starting stats, skills, and talents.

You can only have one character at a time. Use `/delete` to permanently remove your character if you want to start over.

### Your First Steps

1. **Create** your character with `/create`
2. **Check** your stats with `/stats`
3. **Fight** a random encounter with `/fight` to gain XP and gold
4. **Enter** the dungeon with `/enter` for more structured exploration
5. **Spend** stat points with `/allocate` when you level up
6. **Learn** skills with `/learn` when skill slots unlock (every 5 levels)

---

## 2. Classes

### Warrior

- **Main Stat:** Strength | **Resource:** SP
- **Playstyle:** Frontline melee fighter with heavy armor access. High base HP makes Warriors durable. Skills focus on raw damage and weapon-based attacks.
- **Best for:** Players who want straightforward, high-damage combat.

### Rogue

- **Main Stat:** Dexterity | **Resource:** SP
- **Playstyle:** Fast attacker with damage-over-time effects (bleed, poison). High dodge chance through Agility. Skills exploit enemy weaknesses.
- **Best for:** Players who enjoy status effects and evasion.

### Mage

- **Main Stat:** Intelligence | **Resource:** Mana
- **Playstyle:** Ranged elemental damage dealer. Can hit multiple enemies with AoE spells. Lower HP but devastating damage output.
- **Best for:** Players who want powerful spells and elemental variety.

### Ranger

- **Main Stat:** Dexterity | **Resource:** SP
- **Playstyle:** Versatile ranged fighter with nature abilities and trap-setting. Good balance of damage and utility.
- **Best for:** Players who want ranged combat with tactical options.

### Bard

- **Main Stat:** Charisma | **Resource:** Mana
- **Playstyle:** Support-focused with songs that buff allies and debuff enemies. Can charm enemies to skip their turns.
- **Best for:** Players who enjoy buffing/debuffing and creative combat.

### Cleric

- **Main Stat:** Wisdom | **Resource:** Mana
- **Playstyle:** Holy healer and protector. Can restore HP, create shields, and deal holy damage. Very durable with healing.
- **Best for:** Players who want self-sustain and survivability.

---

## 3. Stats & Attributes

Every character has 7 stats. Each class starts with different values. You gain 5 stat points per level to distribute freely.

| Stat | Abbreviation | Effect per Point |
|---|---|---|
| Strength | STR | +0.2 physical damage |
| Dexterity | DEX | +0.4% double strike chance |
| Intelligence | INT | +0.2 spell damage |
| Agility | AGI | +0.2% dodge chance |
| Wisdom | WIS | +0.4% healing bonus |
| Endurance | END | +10 max HP, +5 max Mana, +5 max SP |
| Charisma | CHA | +0.2 song power |

### Derived Stats

- **Max HP** = Class base HP + (Endurance x 10)
- **Max Mana** = Class base Mana + (Endurance x 5)
- **Max SP** = Class base SP + (Endurance x 5)
- **Dodge Chance** = Agility x 0.2%
- **Double Strike** = Dexterity x 0.4%

### Stat Allocation Tips

- **Endurance** is universally useful -- more HP, Mana, and SP
- Invest in your class's **main stat** for maximum skill effectiveness
- **Agility** provides passive defense through dodge chance
- Don't neglect your resource stat (END for SP users, END+INT for Mana users)

---

## 4. Leveling & Progression

### XP and Leveling

- XP is gained from combat victories
- **Perfect encounter bonus:** Take 0 damage in a fight for +10% bonus XP
- XP thresholds increase with each level
- Level cap: 20

### Stat Points

- **5 stat points per level** (starting at level 2)
- Allocate with `/allocate <stat> <points>`
- Endurance increases also raise your current HP/Mana/SP

### Skill Slots

- First skill slot available at level 1
- New slot every **5 levels** (levels 5, 10, 15, 20)
- View and learn with `/skills` and `/learn`
- Some skills have minimum level requirements

### Talent Slots

- First talent slot available at level 10
- New slot every **10 levels** (levels 10, 20)
- View and select with `/talents` and `/choose_talent`
- Talents are passive bonuses (always active)

---

## 5. Skills

Each class has **10 skills** (9 for Bard). Skills cost SP or Mana to use and fall into categories:

| Type | Action Slot | Description |
|---|---|---|
| Attack | Attack action | Offensive skills that deal damage |
| Buff | Buff action | Self-buffs that enhance your stats |
| Heal | Buff action | Restore HP or provide shields |
| Debuff | Attack action | Weaken enemies |
| Utility | Varies | Special effects (flee, multi-hit, etc.) |

### Using Skills

- In combat, use the **skill dropdown** or `/use <skill>`
- Skills consume their resource (SP or Mana) on use
- Each turn you get 1 attack action and 1 buff action
- Attack-type skills use your attack action; buff-type skills use your buff action

---

## 6. Talents

Each class has **5 passive talents**. Talents are always active once selected and provide permanent bonuses.

Examples:
- **Warrior: Berserker Rage** -- +20% damage when below 30% HP
- **Rogue: Shadow Step** -- +15% dodge chance
- **Mage: Arcane Mastery** -- +25% spell damage
- **Cleric: Faithful Recovery** -- +20% HP at the start of each encounter

View your class talents with `/talents` or `/classinfo <class>`.

---

## 7. Combat

### Starting Combat

- `/fight` starts a random encounter based on your current floor
- Dungeon tiles marked as combat rooms trigger encounters automatically
- Boss tiles trigger the floor boss

### Turn Structure

Each turn, you have 3 action slots:

1. **Attack** (1 per turn) -- Slash, Thrust, or attack skill
2. **Buff** (1 per turn) -- Buff/heal skill
3. **Item** (1 per turn) -- Use a consumable

Your turn ends automatically when all slots are used, or manually with the **End Turn** button.

### Attack Types

| Attack | Effect |
|---|---|
| **Slash** | Full damage, standard attack |
| **Thrust** | 70% damage, 10% chance to stun |

### Damage Calculation

- **Unarmed damage:** 5-10 (random)
- **Weapon damage:** Based on weapon's damage range + rarity
- **Strength bonus:** +0.2 damage per STR point
- **Armor reduction:** `AR / (AR + 500) * 100`%
- **Double strike:** DEX x 0.4% chance to hit twice

### Status Effects

| Effect | Damage/Turn | Source |
|---|---|---|
| Burn | 5 | Fire spells |
| Bleed | 3 | Slashing attacks |
| Poison | 4 | Poison abilities |
| Stun | Skip turn | Thrust, stun skills |
| Charm | Enemy skips | Bard abilities |

### Fleeing

- Base flee chance: 30% + (Agility x 1% bonus)
- Failed flee: enemies get free attacks
- Successful flee: no XP or loot gained, but you survive

### Victory Rewards

- **XP** based on enemy levels and count
- **Gold** drops
- **Loot** -- equipment and consumables based on loot tables
- **Perfect bonus** -- +10% XP if you took no damage

### Defeat

- **Outside dungeon:** HP/Mana/SP restored, no penalty
- **Inside dungeon:** All unequipped inventory items lost, dungeon session ends, HP/Mana/SP restored

---

## 8. Dungeon Exploration

### Entering the Dungeon

- `/enter` enters your highest unlocked floor
- `/enter <floor>` enters a specific previously-cleared floor
- New characters start at Floor 1

### Movement

Use the direction buttons or `/move <direction>` to navigate. The map shows:
- Your position (player marker)
- Visited tiles
- Fog of war for unvisited areas
- Special tile icons (combat, scenario rooms, exit, boss)

### Tile Types

| Tile | Description |
|---|---|
| **Path** | Safe passage (60% chance of random encounter) |
| **Combat** | Guaranteed enemy encounter |
| **Scenario Room (SR)** | Random event (positive, negative, or neutral) |
| **Exit** | Completes the floor, advances to the next |
| **Boss** | Boss encounter (Floor 5 only currently) |

### Scenario Events

Scenario rooms trigger one of three categories:

- **Positive (33%):** Find treasure, healing fountains, bonus XP
- **Negative (33%):** Traps, curses, ambushes, item theft
- **Neutral (34%):** Lore, merchant encounters, stat checks

### Curses & Blessings

- **Curses** reduce a stat by 10% for 5 combats
- Maximum 3 active curses at once
- Curses tick down after each combat (victory or flee)
- `/admin_clear_effects` removes all effects (testing)

### Resource Regeneration

Moving between tiles regenerates resources:
- **HP:** +10 per tile
- **Mana:** +10 per tile
- **SP:** +5 per tile

### Floor Progression

- Reaching the exit unlocks the next floor permanently
- Your **highest floor** is tracked on the leaderboard
- You can replay earlier floors at any time with `/enter <floor>`

### Retreating

- `/retreat` or the Retreat button exits the dungeon safely
- All items and progress are kept
- You must finish any active combat before retreating

---

## 9. Equipment

### Equipment Slots

| Slot | Types |
|---|---|
| Head | Helmets, hoods, circlets |
| Shoulders | Pauldrons, mantles |
| Chest | Breastplates, robes, vests |
| Gloves | Gauntlets, gloves, wraps |
| Legs | Leggings, greaves, pants |
| Feet | Boots, shoes, sandals |
| Main Hand | All weapon types |
| Off Hand | One-hand weapons, shields |

### Weapon Types

- **Two-hand weapons** occupy both Main Hand and Off Hand
- **One-hand weapons** can go in Main Hand or Off Hand
- Weapon damage replaces unarmed damage (5-10)

### Armor Types & Class Restrictions

| Armor Type | Available To |
|---|---|
| Heavy | Warrior |
| Medium | Rogue, Ranger |
| Light | Mage, Bard, Cleric |
| Cloth | All classes |

### Rarity System

| Rarity | Color | Drop Rate | Stat Affixes | Affix Power |
|---|---|---|---|---|
| Poor | Grey | 50.9% | 0 | -- |
| Common | White | 30.0% | 0 | -- |
| Uncommon | Green | 10.0% | 1 | x1 |
| Rare | Blue | 5.0% | 2 | x2, x1 |
| Epic | Purple | 4.0% | 3 | x3, x2, x1 |
| Legendary | Orange | 0.1% | 3 | x3, x3, x2 |

### Stat Affixes

Higher-rarity items can roll random stat bonuses (e.g., +3 Strength, +2 Dexterity). These bonuses are shown on `/inspect` and reflected in your `/stats` character sheet.

### Selling

| Method | Description |
|---|---|
| `/sell <item>` | Sell a specific item |
| `/sell_all` | Sell all unequipped items at once |
| Auto-sell | Items auto-sell when inventory is full (20 slots) |

Sell values scale with rarity: Poor (1g), Common (3g), Uncommon (8g), Rare (20g), Epic (50g), Legendary (150g).

---

## 10. Inventory & Shop

### Inventory

- **Capacity:** 20 slots
- View with `/inventory`
- Equipped items are marked with their slot
- Items are grouped by type (Equipped, Weapons, Armor, Consumables)

### Shop

The shop sells 15 consumable items, available when you're not in a dungeon:

**Healing:**
- Minor Healing Potion (15g), Herbal Remedy (25g), Healing Fruit (50g), etc.

**Mana:**
- Mana Potion (15g), Essence of Magic (25g), Arcane Elixir (35g), etc.

**Stamina:**
- Stamina Tonic (15g), Energizing Elixir (25g), Rejuvenating Tea (35g), etc.

Use `/shop` to browse, `/buy <item> [quantity]` to purchase.

---

## 11. Tips & Strategy

### General Tips

- **Allocate stat points immediately** -- they make a significant difference
- **Learn skills early** -- even one skill dramatically improves your combat options
- **Keep consumables** for tough fights and boss encounters
- **Equip everything** before entering the dungeon -- unequipped items are lost on death
- **Sell junk regularly** with `/sell_all` to keep inventory space open

### Combat Tips

- **Thrust** is weaker but can stun -- useful against single tough enemies
- Use **buff skills** every turn if available -- the buff action is otherwise wasted
- **Flee** is risky due to free enemy attacks -- consider it a last resort
- **Perfect encounters** (0 damage taken) give +10% XP -- dodge chance and killing fast help

### Dungeon Tips

- **Explore everything** -- scenario rooms can give free items, XP, and gold
- **Watch your HP** -- the regeneration between tiles is modest (10 HP per move)
- **Retreat if low** -- dying loses all unequipped items
- **Buy healing potions** before entering -- they're cheap and can save a run
- **Floor 5 has the Goblin King** -- make sure you're well-equipped before attempting it

### Class-Specific Tips

- **Warriors:** Stack Strength and Endurance. Heavy armor gives the best AR.
- **Rogues:** Balance Dexterity and Agility for damage and dodge. Bleed/poison stack.
- **Mages:** Intelligence is king. Mana management matters -- bring Mana Potions.
- **Rangers:** Dexterity for damage, some Agility for dodge. Versatile skill set.
- **Bards:** Charisma boosts songs. The Charming Aura talent can charm enemies at combat start.
- **Clerics:** Wisdom for healing. Faithful Recovery talent provides free HP each fight.
