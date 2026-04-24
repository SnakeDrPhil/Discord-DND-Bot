# Stage 7 Workbook -- Polish, Balance & Quality of Life

**Purpose:** Comprehensive build spec for Stage 7. Add error handling, logging, onboarding, class info, character sheet enhancements, admin tools, help completeness, and production hardening. This is the final stage before the bot is production-ready.

---

## Table of Contents

1. [What Already Exists](#1-what-already-exists)
2. [Files to Create](#2-files-to-create)
3. [Files to Modify](#3-files-to-modify)
4. [Design Decisions](#4-design-decisions)
5. [Global Error Handling](#5-global-error-handling)
6. [Logging System](#6-logging-system)
7. [Character Sheet Enhancement](#7-character-sheet-enhancement)
8. [Class Info Command](#8-class-info-command)
9. [Help Command Completeness](#9-help-command-completeness)
10. [Admin Tools Expansion](#10-admin-tools-expansion)
11. [Database Hardening](#11-database-hardening)
12. [Combat Balance Visibility](#12-combat-balance-visibility)
13. [Quality of Life Improvements](#13-quality-of-life-improvements)
14. [Testing & Validation](#14-testing--validation)
15. [Validation Checklist](#15-validation-checklist)

---

## 1. What Already Exists

### 1.1 Admin Commands (7 total)

| Command | Cog | What it does |
|---|---|---|
| `/admin_fight <type> <level> [count]` | combat.py | Spawn specific enemies |
| `/admin_item <item_id>` | combat.py | Give a consumable |
| `/admin_give_weapon <id> <rarity>` | inventory.py | Give a weapon at rarity |
| `/admin_give_armor <id> <rarity>` | inventory.py | Give armor at rarity |
| `/admin_teleport <row> <col>` | dungeon.py | Teleport to a tile |
| `/admin_scenario <type>` | dungeon.py | Force a scenario type |
| `/admin_xp <amount>` | leveling.py | Grant XP |

### 1.2 Error Handling (Current State)

- **Per-command checks:** Each command validates player exists, not in combat, etc. Uses `error_embed()` for user-facing messages.
- **No global error handler:** Unhandled exceptions surface as raw Discord errors.
- **No logging:** Zero `import logging` in the entire codebase.
- **No try/except around DB operations** in cog code (models.py uses try/finally for connection cleanup but no error recovery).

### 1.3 Character Sheet (Current State)

Shows: Name, level, class, HP/Mana/SP, 7 stats with computed effects, XP progress bar, learned skills, selected talents, gold.

**Missing:** Equipment slots, stat bonuses from equipment, total armor rating, highest floor, enemies killed, bosses killed.

### 1.4 Help Command (Current State)

Lists most commands but **missing**: `/skills`, `/learn`, `/talents`, `/choose_talent`.

### 1.5 Data Caching

`src/utils/data_loader.py` uses an in-memory `_cache` dict. First load reads from disk; subsequent calls use cache. `clear_cache()` available. This is adequate.

### 1.6 Database Pattern

Every function in `models.py` opens a new connection, executes, and closes in try/finally. No connection pooling, no transaction grouping, no explicit rollback.

---

## 2. Files to Create

| File | Purpose |
|---|---|
| `src/bot/cogs/admin.py` | Consolidated admin cog with new commands: `/admin_reset`, `/admin_set_floor`, `/admin_set_gold`, `/admin_set_level`, `/admin_boss` |

---

## 3. Files to Modify

| File | Change |
|---|---|
| `bot.py` | Add global error handler, add admin cog, add logging setup |
| `src/utils/embeds.py` | Enhance `character_sheet_embed()` with equipment/progression, add `classinfo_embed()` |
| `src/bot/cogs/general.py` | Add `/classinfo` command |
| `src/bot/cogs/character.py` | Enhance `/stats` to load and pass equipment data |
| `src/bot/cogs/combat.py` | Move admin commands to admin cog (optional), add error wrapping |
| `src/bot/cogs/dungeon.py` | Add floor name to enter/map embeds |
| `src/game/constants.py` | Add admin permission constant |
| `src/db/models.py` | Add `reset_player()`, connection error wrapping |

---

## 4. Design Decisions

| Decision | Resolution | Rationale |
|---|---|---|
| Global error handler | `on_app_command_error` in bot.py | Catches all unhandled slash command errors cleanly |
| Logging framework | Python `logging` module, file + console | Standard, lightweight, built-in |
| Admin permissions | No Discord permission check (any user can use admin commands) | Design doc doesn't specify; keep it simple for now. Can add checks later |
| Connection pooling | Not adding | SQLite doesn't benefit from pooling; aiosqlite is adequate |
| Tutorial system | Not implementing a guided tutorial | Would require significant UX design; `/help` and `/classinfo` are sufficient for now |
| Combat balance tuning | No number changes | The existing values are from the design doc; changes would need playtesting data |
| Move admin commands | Keep in original cogs, add new ones to admin.py | Avoids breaking existing commands; new admin cog supplements |

---

## 5. Global Error Handling

### 5.1 Error Handler in bot.py

Add a global error handler that catches unhandled exceptions and returns a friendly embed:

```python
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    """Global error handler for all slash commands."""
    if isinstance(error, app_commands.CommandOnCooldown):
        embed = error_embed(f"Command on cooldown. Try again in {error.retry_after:.1f}s.")
    elif isinstance(error, app_commands.MissingPermissions):
        embed = error_embed("You don't have permission to use this command.")
    else:
        logger.exception("Unhandled command error", exc_info=error)
        embed = error_embed("Something went wrong. Please try again.")

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception:
        pass  # Interaction expired
```

### 5.2 Cog-Level Error Handling

Add a `cog_app_command_error` handler to each cog as a fallback. Not strictly necessary with the global handler, but provides cog-specific logging context.

---

## 6. Logging System

### 6.1 Logger Setup in bot.py

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("dungeon_bot")
```

### 6.2 What to Log

| Event | Level | Location |
|---|---|---|
| Bot startup/ready | INFO | bot.py `on_ready` |
| Cog loaded | INFO | bot.py `main()` |
| Character created | INFO | character.py `/create` |
| Character deleted | INFO | character.py `/delete` |
| Combat started | DEBUG | combat.py `/fight` |
| Combat result (victory/defeat/flee) | INFO | combat.py `_send_result` |
| Level up | INFO | leveling.py `grant_xp` |
| Item equipped/unequipped | DEBUG | inventory.py |
| Shop purchase | INFO | shop.py `/buy` |
| Dungeon entered/exited | INFO | dungeon.py |
| Boss defeated | INFO | combat.py |
| Admin command used | WARNING | admin commands |
| Unhandled errors | ERROR | global error handler |
| DB errors | ERROR | models.py |

### 6.3 Log Format

```
2026-04-23 14:30:15 [INFO] dungeon_bot.combat: Victory: player=Hero enemies=3 xp=120 loot=2
2026-04-23 14:30:16 [WARNING] dungeon_bot.admin: admin_xp used by discord_id=123456 amount=1000
2026-04-23 14:30:17 [ERROR] dungeon_bot: Unhandled error in /fight: ...
```

---

## 7. Character Sheet Enhancement

### 7.1 Updated `character_sheet_embed`

The `/stats` command should show equipment and progression stats. The cog layer loads equipment data and passes it to the embed builder.

**New signature:**

```python
def character_sheet_embed(player: dict, class_data: dict,
                          equipped_items: list = None,
                          equipment_bonuses: dict = None,
                          total_ar: int = 0) -> discord.Embed:
```

### 7.2 New Sections to Add

**Equipment Section:**
```
Head: Iron Helm (Rare, 45 AR)
Shoulders: (empty)
Chest: Leather Vest (Common, 12 AR)
Gloves: (empty)
Legs: (empty)
Feet: (empty)
Main Hand: Long Sword (Uncommon, 13-21 dmg)
Off Hand: (empty)

Total AR: 57 (10.2% reduction)
```

**Stats with Equipment Bonuses:**
```
STR: 12 (+3) (+2.4 dmg)     ← +3 from equipment affixes
DEX: 8 (3.2% double strike)
...
```

Format: Show base stat, then equipment bonus in parentheses if any, then computed effect.

**Progression Section Enhancement:**
```
Progression
XP: 1500/2000
[########--] 75%
Unspent stat points: 5
Highest Floor: 3
Enemies Killed: 47
Bosses Killed: 1
```

### 7.3 Changes to character.py `/stats`

```python
@app_commands.command(name="stats", description="View your character sheet")
async def stats(self, interaction):
    player = await get_player(str(interaction.user.id))
    ...
    # Load equipment data for character sheet
    equipped = await get_equipped_items(player["id"])
    from src.game.items import calc_equipment_stat_bonuses, get_total_armor_rating
    bonuses = calc_equipment_stat_bonuses(equipped)
    total_ar = get_total_armor_rating(equipped)

    embed = character_sheet_embed(player, class_data, equipped, bonuses, total_ar)
```

---

## 8. Class Info Command

### 8.1 `/classinfo` Command

Add to `general.py`:

```python
@app_commands.command(name="classinfo", description="View detailed class information")
@app_commands.describe(class_name="Class to view")
@app_commands.choices(class_name=[
    Choice(name="Warrior", value="warrior"),
    Choice(name="Rogue", value="rogue"),
    Choice(name="Mage", value="mage"),
    Choice(name="Ranger", value="ranger"),
    Choice(name="Bard", value="bard"),
    Choice(name="Cleric", value="cleric"),
])
async def classinfo(self, interaction, class_name: Choice[str]):
    class_data = get_class(class_name.value)
    skills = get_skills(class_name.value)
    talents = get_talents(class_name.value)
    embed = classinfo_embed(class_data, skills, talents)
    await interaction.response.send_message(embed=embed)
```

### 8.2 `classinfo_embed` in embeds.py

```python
def classinfo_embed(class_data: dict, skills: list, talents: list) -> discord.Embed:
    """Detailed class breakdown with stats, skills, and talents."""
    color = CLASS_COLORS.get(class_data["id"], discord.Color.greyple())
    embed = discord.Embed(
        title=class_data["name"],
        description=class_data["description"],
        color=color,
    )

    # Starting stats
    stats = class_data["starting_stats"]
    stat_text = "\n".join(f"{k.upper()[:3]}: {v}" for k, v in stats.items())
    embed.add_field(name="Starting Stats", value=stat_text, inline=True)

    # Class info
    embed.add_field(name="Details", value=(
        f"Main Stat: {class_data['main_stat'].capitalize()}\n"
        f"Resource: {class_data['resource'].upper()}\n"
        f"Base HP: {class_data['base_hp']}\n"
        f"Base Mana: {class_data['base_mana']}\n"
        f"Base SP: {class_data['base_sp']}"
    ), inline=True)

    # Skills
    skill_lines = []
    for s in skills:
        unlock = f" (Lv.{s['unlock_level']})" if s.get("unlock_level") else ""
        skill_lines.append(f"**{s['name']}**{unlock} - {s['cost']} {s['resource'].upper()}")
    if skill_lines:
        embed.add_field(name=f"Skills ({len(skills)})",
                       value="\n".join(skill_lines), inline=False)

    # Talents
    talent_lines = [f"**{t['name']}** - {t['effect']}" for t in talents]
    if talent_lines:
        embed.add_field(name=f"Talents ({len(talents)})",
                       value="\n".join(talent_lines), inline=False)

    return embed
```

---

## 9. Help Command Completeness

### 9.1 Missing Commands

Add to the help embed:

**Progression section (new):**
```
`/skills` - View available class skills
`/learn <skill>` - Learn a new skill
`/talents` - View available talents
`/choose_talent <talent>` - Select a talent
`/classinfo <class>` - View class details
```

### 9.2 Updated Help Embed Structure

```
Getting Started
  /create, /classinfo

Character
  /stats, /inventory, /inspect, /equip, /unequip, /sell, /use_item, /allocate

Progression
  /skills, /learn, /talents, /choose_talent

Dungeon
  /enter, /move, /map, /retreat

Combat
  /fight, /attack, /use, /item, /flee

Shop & Leaderboard
  /shop, /buy, /sell_all, /leaderboard

Info
  /ping, /help
```

---

## 10. Admin Tools Expansion

### 10.1 New Admin Cog (`src/bot/cogs/admin.py`)

Consolidates new admin commands. Existing admin commands remain in their cogs to avoid disruption.

### 10.2 New Admin Commands

| Command | Parameters | Purpose |
|---|---|---|
| `/admin_reset <player_mention>` | player: User | Reset a player's character (delete and recreate prompt) |
| `/admin_set_floor <floor>` | floor: int | Set player's current_floor and highest_floor |
| `/admin_set_gold <amount>` | amount: int | Set player's gold to exact amount |
| `/admin_set_level <level>` | level: int | Set player level and XP to match |
| `/admin_boss <boss_type>` | boss_type: str | Force a boss encounter |
| `/admin_heal` | None | Fully restore HP/Mana/SP |
| `/admin_clear_effects` | None | Clear all dungeon effects (curses/blessings) |

### 10.3 Implementation

```python
class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="admin_set_floor", description="[Admin] Set your floor")
    @app_commands.describe(floor="Floor number")
    async def admin_set_floor(self, interaction, floor: int):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character."), ephemeral=True)
        floor = max(1, min(floor, 5))
        await update_player(str(interaction.user.id),
                          current_floor=floor, highest_floor=max(floor, player.get("highest_floor", 1)))
        await interaction.response.send_message(
            embed=success_embed("Floor Set", f"Floor set to {floor}."))

    @app_commands.command(name="admin_set_gold", description="[Admin] Set your gold")
    @app_commands.describe(amount="Gold amount")
    async def admin_set_gold(self, interaction, amount: int):
        ...

    @app_commands.command(name="admin_set_level", description="[Admin] Set your level")
    @app_commands.describe(level="Target level")
    async def admin_set_level(self, interaction, level: int):
        ...

    @app_commands.command(name="admin_heal", description="[Admin] Fully restore resources")
    async def admin_heal(self, interaction):
        ...

    @app_commands.command(name="admin_clear_effects", description="[Admin] Clear dungeon effects")
    async def admin_clear_effects(self, interaction):
        ...

    @app_commands.command(name="admin_boss", description="[Admin] Force a boss fight")
    @app_commands.describe(boss_type="Boss type (e.g. goblin_king)")
    async def admin_boss(self, interaction, boss_type: str):
        ...
```

---

## 11. Database Hardening

### 11.1 Error Wrapping in models.py

Add a decorator for consistent error handling:

```python
import logging

logger = logging.getLogger("dungeon_bot.db")

# Wrap DB functions to log errors instead of crashing
# The existing try/finally pattern is adequate for connection cleanup
# Add logging to the finally blocks when errors occur
```

Since every function already uses try/finally for connection cleanup, the main improvement is adding logging when exceptions propagate. The global error handler in bot.py will catch these at the command level.

### 11.2 Migration Safety

Improve the migration runner to log results:

```python
async def init_db():
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()
        for migration in _MIGRATIONS:
            try:
                await db.execute(migration)
                await db.commit()
                logger.info(f"Migration applied: {migration[:60]}...")
            except Exception:
                pass  # Column already exists
```

---

## 12. Combat Balance Visibility

### 12.1 Combat Summary on Victory

Enhance the victory embed to show a brief combat summary:

```python
def combat_victory_embed(player_name, xp, perfect, gold, loot, level_events,
                         turns=0, damage_dealt=0, damage_taken=0):
    ...
    if turns > 0:
        summary = f"Turns: {turns}"
        if damage_dealt > 0:
            summary += f" | Damage dealt: {damage_dealt}"
        if damage_taken > 0:
            summary += f" | Damage taken: {damage_taken}"
        embed.set_footer(text=summary)
```

### 12.2 Armor Rating Display

Show armor reduction percentage in the character sheet:

```python
from src.game.formulas import calc_armor_reduction
if total_ar > 0:
    reduction = calc_armor_reduction(total_ar)
    ar_text = f"Total AR: {total_ar} ({reduction:.1f}% reduction)"
```

---

## 13. Quality of Life Improvements

### 13.1 Floor Name in Dungeon Embeds

Use `FLOOR_NAMES` from constants in dungeon enter/map embeds:

```python
from src.game.constants import FLOOR_NAMES

floor_name = FLOOR_NAMES.get(floor_num, f"Floor {floor_num}")
# Use in embed title: f"{floor_name} (Floor {floor_num})"
```

### 13.2 Dungeon Enter Floor Name

Update `dungeon_enter_embed` to show floor name:

```python
def dungeon_enter_embed(player_name, floor, map_str, legend, floor_name=None):
    title = floor_name or f"Floor {floor}"
    embed = discord.Embed(
        title=title,
        description=f"**{player_name}** enters the dungeon.\n\n{map_str}",
        ...
    )
```

### 13.3 Death Embed Enhancement

Show which floor the player died on:

```python
def dungeon_death_embed(items_lost, floor=0):
    ...
    if floor > 0:
        embed.add_field(name="Floor", value=f"Died on Floor {floor}", inline=True)
```

### 13.4 Version Footer

Add a version string to the bot:

```python
BOT_VERSION = "0.7.0"
# Use in help embed footer
embed.set_footer(text=f"Dungeon Crawler Bot v{BOT_VERSION}")
```

---

## 14. Testing & Validation

### 14.1 Manual Test Script

1. **Global error handler:** Trigger an edge case (e.g., interact with expired session) -- should show friendly error, not crash
2. **Logging:** Start bot, perform actions, check `bot.log` has entries
3. **Character sheet equipment:** Equip items, `/stats` shows equipment section with AR and bonuses
4. **Character sheet progression:** `/stats` shows highest_floor, enemies_killed, bosses_killed
5. **Stat bonuses display:** Equip item with affixes, `/stats` shows `STR: 12 (+3)` format
6. **Total AR display:** Equip armor, `/stats` shows total AR with reduction percentage
7. **`/classinfo warrior`:** Shows warrior description, starting stats, all 10 skills, all 5 talents
8. **`/classinfo` all 6 classes:** Each class renders correctly
9. **Help completeness:** `/help` lists all commands including /skills, /learn, /talents, /choose_talent, /classinfo
10. **`/admin_set_floor 3`:** Sets floor, can `/enter` floor 3
11. **`/admin_set_gold 500`:** Gold is exactly 500
12. **`/admin_set_level 10`:** Level is 10 with matching XP
13. **`/admin_heal`:** HP/Mana/SP fully restored
14. **`/admin_clear_effects`:** Dungeon curses removed
15. **`/admin_boss goblin_king`:** Boss combat starts
16. **Floor name in embeds:** `/enter` shows "The Goblin Warrens" not just "Floor 1"
17. **Floor name in map:** `/map` title shows floor name
18. **Admin logging:** Use admin commands, verify WARNING entries in log
19. **Combat victory logging:** Win a fight, verify INFO entry in log
20. **Unhandled error logging:** Force an error, verify ERROR entry with traceback in log

---

## 15. Validation Checklist

### Error Handling
- [ ] Global error handler catches unhandled exceptions
- [ ] Friendly error embed shown instead of Discord error
- [ ] Expired interactions handled gracefully
- [ ] Error logged with traceback

### Logging
- [ ] `bot.log` file created on startup
- [ ] Bot ready event logged
- [ ] Cog loading logged
- [ ] Combat results logged
- [ ] Admin commands logged with user info
- [ ] Errors logged with tracebacks

### Character Sheet
- [ ] Equipment slots shown (with item or "empty")
- [ ] Stat bonuses from equipment displayed as `STR: 12 (+3)`
- [ ] Total armor rating with reduction percentage shown
- [ ] Highest floor displayed
- [ ] Enemies killed displayed
- [ ] Bosses killed displayed

### Class Info
- [ ] `/classinfo` works for all 6 classes
- [ ] Shows description, starting stats, main stat, resource
- [ ] Lists all skills with unlock levels
- [ ] Lists all talents with effects

### Help Completeness
- [ ] All slash commands listed in `/help`
- [ ] Progression section added (/skills, /learn, /talents, /choose_talent)
- [ ] /classinfo listed
- [ ] Version number in footer

### Admin Tools
- [ ] `/admin_set_floor` works
- [ ] `/admin_set_gold` works
- [ ] `/admin_set_level` sets level and XP correctly
- [ ] `/admin_heal` restores all resources
- [ ] `/admin_clear_effects` clears dungeon effects
- [ ] `/admin_boss` triggers boss combat

### Quality of Life
- [ ] Floor names shown in dungeon enter/map embeds
- [ ] Death embed shows floor number
- [ ] All embeds render without errors
- [ ] Autocomplete works on all commands that have it

### Edge Cases
- [ ] Using commands with no character gives helpful error
- [ ] Using dungeon commands while not in dungeon gives error
- [ ] Using combat commands while not in combat gives error
- [ ] Using shop while in dungeon gives error
- [ ] Bot handles concurrent players without data corruption
- [ ] Bot restarts cleanly with existing data
