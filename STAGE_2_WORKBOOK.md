# Stage 2 Workbook -- Character Creation & Stat System

**Purpose:** Comprehensive build spec for Stage 2. Players can create characters, view stats, level up, allocate stat points, and learn skills/talents.

---

## Table of Contents

1. [What Already Exists](#1-what-already-exists)
2. [Files to Create](#2-files-to-create)
3. [Files to Modify](#3-files-to-modify)
4. [Critical Design Decision: Starting Resource Rules](#4-critical-design-decision-starting-resource-rules)
5. [New Cog: character.py -- Commands](#5-new-cog-characterpy----commands)
6. [New Cog: leveling.py -- Commands](#6-new-cog-levelingpy----commands)
7. [New Module: game/leveling.py -- Level-Up Engine](#7-new-module-gamelevelingpy----level-up-engine)
8. [Embed Designs](#8-embed-designs)
9. [Modifications to Existing Files](#9-modifications-to-existing-files)
10. [Testing & Admin Commands](#10-testing--admin-commands)
11. [Validation Checklist](#11-validation-checklist)

---

## 1. What Already Exists

These Stage 1 components are ready to use:

| Component | Location | What it provides |
|---|---|---|
| Class definitions | `data/classes.json` | 6 classes with starting_stats, main_stat, base_hp/mana/sp |
| Skills data | `data/skills.json` | 59 skills with class, cost, resource, effects |
| Talents data | `data/talents.json` | 30 talents with class, passive_modifiers |
| XP thresholds | `data/xp_thresholds.json` | 20 level thresholds |
| Data loader | `src/utils/data_loader.py` | `get_class()`, `get_skills()`, `get_talents()`, `get_xp_for_level()` |
| Formulas | `src/game/formulas.py` | `calc_max_hp()`, `calc_max_mana()`, `calc_max_sp()`, all stat formulas |
| Constants | `src/game/constants.py` | `STAT_POINTS_PER_LEVEL`, `SKILL_UNLOCK_INTERVAL`, `TALENT_UNLOCK_INTERVAL`, `ALL_STATS` |
| DB models | `src/db/models.py` | `create_player()`, `get_player()`, `update_player()`, `delete_player()` |
| DB schema | `src/db/database.py` | `players` table with all stat columns, `learned_skills`, `selected_talents`, `unspent_stat_points` |
| Embeds | `src/utils/embeds.py` | `error_embed()`, `success_embed()`, `info_embed()` |
| Bot entry | `bot.py` | Cog loading, `COGS` list to extend |

---

## 2. Files to Create

| File | Purpose |
|---|---|
| `src/bot/cogs/character.py` | `/create`, `/stats`, `/delete` commands |
| `src/bot/cogs/leveling.py` | `/allocate`, `/skills`, `/learn`, `/talents`, `/chooseTalent` commands |
| `src/game/leveling.py` | Level-up engine: XP check, level-up processing, skill/talent slot calculation |

---

## 3. Files to Modify

| File | Changes |
|---|---|
| `bot.py` | Add new cogs to `COGS` list |
| `src/utils/embeds.py` | Add `character_sheet_embed()`, `level_up_embed()`, `skill_list_embed()`, `talent_list_embed()` |
| `src/game/formulas.py` | Add `calc_resource_maxes()` helper that respects starting-stat exclusion rule |
| `src/db/models.py` | No new functions needed -- existing CRUD is sufficient |

---

## 4. Critical Design Decision: Starting Resource Rules

The design doc contains these TEST notes that affect resource calculation:

> - "Starting Endurance does not change starting HP."
> - "Adds 5 mana per 1 Intelligence; starting Intelligence does not add to starting mana."
> - "Adds 1 SP per agility; beginning Agility does not add to starting SP."

### Implementation Rule

Only stat points allocated AFTER character creation contribute to resource bonuses. Starting class stats do not affect starting HP/Mana/SP.

### Resource Formulas

```python
# Look up starting stats from classes.json for the player's class
starting = get_class(player_class)["starting_stats"]

bonus_endurance = current_endurance - starting["endurance"]
bonus_intelligence = current_intelligence - starting["intelligence"]
bonus_agility = current_agility - starting["agility"]

max_hp   = base_hp   + (bonus_endurance * 10)
max_mana = base_mana + (bonus_endurance * 5) + (bonus_intelligence * 5)
max_sp   = base_sp   + (bonus_endurance * 5) + (bonus_agility * 1)
```

### At Character Creation

```
max_hp   = 100  (base, no endurance bonus)
max_mana = 50   (base, no endurance/intelligence bonus)
max_sp   = 30   (base, no endurance/agility bonus)
```

All classes start with the same resource pool. Differentiation comes from stat allocation during level-ups.

### When Allocating Stat Points

If a player puts points into Endurance, Intelligence, or Agility, recalculate max resources and increase current resources by the same amount (so the player benefits immediately).

Example: A Warrior (starting endurance=8) at level 2 with endurance=10 (allocated 2 points):
```
bonus_endurance = 10 - 8 = 2
max_hp = 100 + (2 * 10) = 120
max_mana = 50 + (2 * 5) = 60
max_sp = 30 + (2 * 5) = 40
```

---

## 5. New Cog: character.py -- Commands

### 5.1 `/create`

**Slash command signature:**
```python
@app_commands.command(name="create", description="Create a new character")
@app_commands.describe(name="Your character's name", player_class="Choose your class")
@app_commands.choices(player_class=[
    app_commands.Choice(name="Warrior", value="warrior"),
    app_commands.Choice(name="Rogue", value="rogue"),
    app_commands.Choice(name="Mage", value="mage"),
    app_commands.Choice(name="Ranger", value="ranger"),
    app_commands.Choice(name="Bard", value="bard"),
    app_commands.Choice(name="Cleric", value="cleric"),
])
async def create(self, interaction, name: str, player_class: app_commands.Choice[str]):
```

**Validation:**
1. Check if player already has a character (`get_player(discord_id)`). If yes, send error: "You already have a character. Use `/delete` to remove it first."
2. Validate name length: 2-32 characters.
3. Validate name contains only letters, numbers, spaces, hyphens, apostrophes.

**Flow:**
1. Look up class data: `class_data = get_class(player_class.value)`
2. Extract starting stats: `stats = class_data["starting_stats"]`
3. Set starting resources: `hp = max_hp = 100`, `mana = max_mana = 50`, `sp = max_sp = 30`
4. Call `create_player(discord_id, name, player_class.value, stats, hp, max_hp, mana, max_mana, sp, max_sp)`
5. Fetch the created player: `player = get_player(discord_id)`
6. Send `character_sheet_embed(player, class_data)`

### 5.2 `/stats`

**Slash command signature:**
```python
@app_commands.command(name="stats", description="View your character sheet")
async def stats(self, interaction):
```

**Validation:**
1. Check player exists. If not, send error: "You don't have a character. Use `/create` to make one."

**Flow:**
1. Fetch player: `player = get_player(discord_id)`
2. Fetch class data: `class_data = get_class(player["class"])`
3. Send `character_sheet_embed(player, class_data)`

### 5.3 `/delete`

**Slash command signature:**
```python
@app_commands.command(name="delete", description="Delete your character (irreversible)")
async def delete(self, interaction):
```

**Validation:**
1. Check player exists. If not, send error.

**Flow:**
1. Send confirmation embed with two buttons: "Confirm Delete" (red, danger) and "Cancel" (grey)
2. On "Confirm Delete": call `delete_player(discord_id)`, send success message
3. On "Cancel": send "Deletion cancelled." and remove buttons
4. Buttons time out after 30 seconds

**Button implementation:**
```python
class DeleteConfirmView(discord.ui.View):
    def __init__(self, discord_id: str):
        super().__init__(timeout=30)
        self.discord_id = discord_id
        self.value = None

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction, button):
        await delete_player(self.discord_id)
        await interaction.response.edit_message(
            embed=success_embed("Character Deleted", "Your character has been permanently deleted."),
            view=None,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction, button):
        await interaction.response.edit_message(
            embed=info_embed("Cancelled", "Character deletion cancelled."),
            view=None,
        )
        self.stop()

    async def on_timeout(self):
        # Buttons expire silently
        pass
```

---

## 6. New Cog: leveling.py -- Commands

### 6.1 `/allocate`

**Slash command signature:**
```python
@app_commands.command(name="allocate", description="Spend stat points")
@app_commands.describe(stat="The stat to increase", points="Number of points to allocate")
@app_commands.choices(stat=[
    app_commands.Choice(name="Strength", value="strength"),
    app_commands.Choice(name="Dexterity", value="dexterity"),
    app_commands.Choice(name="Intelligence", value="intelligence"),
    app_commands.Choice(name="Agility", value="agility"),
    app_commands.Choice(name="Wisdom", value="wisdom"),
    app_commands.Choice(name="Endurance", value="endurance"),
    app_commands.Choice(name="Charisma", value="charisma"),
])
async def allocate(self, interaction, stat: app_commands.Choice[str], points: int):
```

**Validation:**
1. Player exists
2. `points >= 1`
3. `points <= player["unspent_stat_points"]`

**Flow:**
1. Fetch player
2. Compute new stat value: `new_value = player[stat.value] + points`
3. Compute new unspent: `new_unspent = player["unspent_stat_points"] - points`
4. If stat is `endurance`, `intelligence`, or `agility`: recalculate max resources using the formula from Section 4. Also increase current resources by the delta.
5. Build update dict and call `update_player(discord_id, **updates)`
6. Send success embed showing: stat name, old value -> new value, remaining unspent points, and resource changes if applicable

**Resource recalculation detail:**
```python
class_data = get_class(player["class"])
starting = class_data["starting_stats"]

new_stats = {s: player[s] for s in ALL_STATS}
new_stats[stat.value] += points

new_max_hp, new_max_mana, new_max_sp = calc_resource_maxes(
    class_data, new_stats
)

# Increase current resources by the delta
hp_delta = new_max_hp - player["max_hp"]
mana_delta = new_max_mana - player["max_mana"]
sp_delta = new_max_sp - player["max_sp"]

updates = {
    stat.value: new_stats[stat.value],
    "unspent_stat_points": new_unspent,
    "max_hp": new_max_hp,
    "max_mana": new_max_mana,
    "max_sp": new_max_sp,
    "hp": min(player["hp"] + max(0, hp_delta), new_max_hp),
    "mana": min(player["mana"] + max(0, mana_delta), new_max_mana),
    "sp": min(player["sp"] + max(0, sp_delta), new_max_sp),
}
```

### 6.2 `/skills`

**Slash command signature:**
```python
@app_commands.command(name="skills", description="View available skills for your class")
async def skills(self, interaction):
```

**Flow:**
1. Fetch player
2. Get all skills for player's class: `get_skills(player["class"])`
3. Parse learned skills: `json.loads(player["learned_skills"])`
4. Calculate skill slots: `available = player["level"] // SKILL_UNLOCK_INTERVAL`
5. Calculate pending: `pending = available - len(learned)`
6. Send `skill_list_embed(class_skills, learned_ids, pending, player["level"])`

### 6.3 `/learn`

**Slash command signature:**
```python
@app_commands.command(name="learn", description="Learn a new skill")
@app_commands.describe(skill_name="Name of the skill to learn")
async def learn(self, interaction, skill_name: str):
```

Note: Use autocomplete to suggest available skills.

**Autocomplete:**
```python
@learn.autocomplete("skill_name")
async def learn_autocomplete(self, interaction, current: str):
    player = await get_player(str(interaction.user.id))
    if not player:
        return []
    class_skills = get_skills(player["class"])
    learned = json.loads(player["learned_skills"])
    available = [
        s for s in class_skills
        if s["id"] not in learned
        and (s["unlock_level"] is None or player["level"] >= s["unlock_level"])
    ]
    return [
        app_commands.Choice(name=s["name"], value=s["id"])
        for s in available
        if current.lower() in s["name"].lower()
    ][:25]
```

**Validation:**
1. Player exists
2. Skill exists and belongs to player's class
3. Skill not already learned
4. Player has pending skill slots: `player["level"] // 5 > len(learned)`
5. If skill has `unlock_level`, player meets the requirement

**Flow:**
1. Add skill ID to learned_skills JSON array
2. `update_player(discord_id, learned_skills=json.dumps(new_learned))`
3. Send success embed with skill name, effect description, cost

### 6.4 `/talents`

**Slash command signature:**
```python
@app_commands.command(name="talents", description="View available talents for your class")
async def talents(self, interaction):
```

**Flow:**
1. Same pattern as `/skills` but uses `get_talents()`, `TALENT_UNLOCK_INTERVAL`, `player["selected_talents"]`
2. Send `talent_list_embed(class_talents, selected_ids, pending)`

### 6.5 `/choose_talent`

**Slash command signature:**
```python
@app_commands.command(name="choose_talent", description="Select a passive talent")
@app_commands.describe(talent_name="Name of the talent to select")
async def choose_talent(self, interaction, talent_name: str):
```

**Autocomplete:** Same pattern as `/learn` but for talents.

**Validation:**
1. Player exists
2. Talent exists and belongs to player's class
3. Talent not already selected
4. Player has pending talent slots: `player["level"] // 10 > len(selected)`

**Flow:**
1. Add talent ID to selected_talents JSON array
2. `update_player(discord_id, selected_talents=json.dumps(new_selected))`
3. Send success embed with talent name and passive effect

---

## 7. New Module: game/leveling.py -- Level-Up Engine

This module contains pure game logic (no Discord imports).

### 7.1 `calc_resource_maxes(class_data, stats)`

```python
def calc_resource_maxes(class_data: dict, stats: dict) -> tuple[int, int, int]:
    """Calculate max HP, Mana, SP respecting starting-stat exclusion rule.

    Returns (max_hp, max_mana, max_sp).
    """
    starting = class_data["starting_stats"]
    base_hp = class_data["base_hp"]
    base_mana = class_data["base_mana"]
    base_sp = class_data["base_sp"]

    bonus_end = max(0, stats["endurance"] - starting["endurance"])
    bonus_int = max(0, stats["intelligence"] - starting["intelligence"])
    bonus_agi = max(0, stats["agility"] - starting["agility"])

    max_hp = base_hp + (bonus_end * ENDURANCE_HP_PER_POINT)
    max_mana = base_mana + (bonus_end * ENDURANCE_MANA_PER_POINT) + (bonus_int * 5)
    max_sp = base_sp + (bonus_end * ENDURANCE_SP_PER_POINT) + (bonus_agi * 1)

    return max_hp, max_mana, max_sp
```

### 7.2 `check_level_up(player)`

```python
def check_level_up(player: dict) -> list[dict]:
    """Check if a player has enough XP to level up.

    Returns a list of level-up events (may be multiple if XP
    crosses several thresholds). Each event is a dict:
    {
        "new_level": int,
        "stat_points_awarded": int,
        "skill_unlocked": bool,
        "talent_unlocked": bool,
    }

    Does NOT modify the player dict or DB. Caller is responsible
    for applying the changes.
    """
    events = []
    current_level = player["level"]
    current_xp = player["xp"]

    while current_level < 20:
        xp_needed = get_xp_for_level(current_level + 1)
        if xp_needed is None or current_xp < xp_needed:
            break

        current_level += 1
        new_event = {
            "new_level": current_level,
            "stat_points_awarded": STAT_POINTS_PER_LEVEL,
            "skill_unlocked": (current_level % SKILL_UNLOCK_INTERVAL == 0),
            "talent_unlocked": (current_level % TALENT_UNLOCK_INTERVAL == 0),
        }
        events.append(new_event)

    return events
```

### 7.3 `apply_level_ups(player, events)`

```python
def apply_level_ups(player: dict, events: list[dict]) -> dict:
    """Compute the DB update fields from level-up events.

    Returns a dict of fields to pass to update_player().
    """
    if not events:
        return {}

    final_level = events[-1]["new_level"]
    total_stat_points = sum(e["stat_points_awarded"] for e in events)

    return {
        "level": final_level,
        "unspent_stat_points": player["unspent_stat_points"] + total_stat_points,
    }
```

### 7.4 `get_skill_slots(level)` and `get_talent_slots(level)`

```python
def get_skill_slots(level: int) -> int:
    """Number of skill choices a player should have at this level."""
    return level // SKILL_UNLOCK_INTERVAL


def get_talent_slots(level: int) -> int:
    """Number of talent choices a player should have at this level."""
    return level // TALENT_UNLOCK_INTERVAL


def get_pending_skill_slots(level: int, learned_count: int) -> int:
    """Number of skill choices the player hasn't made yet."""
    return max(0, get_skill_slots(level) - learned_count)


def get_pending_talent_slots(level: int, selected_count: int) -> int:
    """Number of talent choices the player hasn't made yet."""
    return max(0, get_talent_slots(level) - selected_count)
```

### 7.5 `grant_xp(player, amount)`

```python
async def grant_xp(discord_id: str, amount: int) -> tuple[dict, list[dict]]:
    """Grant XP to a player, process any level-ups, and persist.

    Returns (updated_player, level_up_events).
    This is the single entry point for all XP gains (combat, perfect encounter, etc.).
    """
    player = await get_player(discord_id)
    new_xp = player["xp"] + amount

    # Temporarily update XP for level check
    player["xp"] = new_xp
    events = check_level_up(player)
    updates = apply_level_ups(player, events)
    updates["xp"] = new_xp

    await update_player(discord_id, **updates)

    # Return fresh player state
    updated_player = await get_player(discord_id)
    return updated_player, events
```

---

## 8. Embed Designs

### 8.1 Character Sheet Embed (`character_sheet_embed`)

Color: Class-themed (Warrior=red, Rogue=dark_purple, Mage=blue, Ranger=green, Bard=gold, Cleric=light_grey)

```
Title: "{character_name} - Level {level} {Class Name}"
Description: "{class_description}"

Field: "Resources" (inline)
  HP:   {hp}/{max_hp}
  Mana: {mana}/{max_mana}
  SP:   {sp}/{max_sp}

Field: "Stats" (inline)
  STR: {strength}  (+{bonus_phys_dmg:.1f} dmg)
  DEX: {dexterity}  ({double_strike:.1f}% double strike)
  INT: {intelligence}  (+{spell_dmg:.1f} spell dmg)
  AGI: {agility}  ({dodge:.1f}% dodge)
  WIS: {wisdom}  (+{heal_bonus:.1f}% healing)
  END: {endurance}
  CHA: {charisma}  (+{song_bonus:.1f} song pwr)

Field: "Progression" (not inline)
  XP: {xp}/{xp_for_next_level}
  [####------] {percent}%    ← text-based progress bar
  Unspent stat points: {unspent}

Field: "Skills" (not inline, if any learned)
  • Skill Name 1 (3 SP)
  • Skill Name 2 (5 Mana)

Field: "Talents" (not inline, if any selected)
  • Talent Name 1
  • Talent Name 2

Footer: "Main stat: {main_stat_name} | Gold: {gold}"
```

### 8.2 Level-Up Embed (`level_up_embed`)

Color: Gold

```
Title: "Level Up!"
Description: "{character_name} reached Level {new_level}!"

Field: "Rewards"
  +{stat_points} stat points

  (if skill_unlocked): "New skill slot available! Use `/skills` to learn one."
  (if talent_unlocked): "New talent slot available! Use `/talents` to choose one."
```

If multiple level-ups occurred at once, show them all:
```
"{character_name} reached Level {final_level}! (+{total_levels} levels)"
```

### 8.3 Skill List Embed (`skill_list_embed`)

Color: Class-themed

```
Title: "{Class Name} Skills"
Description: "{pending} skill slot(s) available" or "No skill slots available"

For each skill:
  (if learned): "**[LEARNED]** Skill Name"
  (if available): "Skill Name"
  (if locked): "~~Skill Name~~ (Unlocks at Level X)"
  "  {type} | {cost} {resource} | {effect}"
```

### 8.4 Talent List Embed (`talent_list_embed`)

Color: Class-themed

```
Title: "{Class Name} Talents"
Description: "{pending} talent slot(s) available" or "No talent slots available"

For each talent:
  (if selected): "**[SELECTED]** Talent Name"
  (if available): "Talent Name"
  "  {effect}"
```

### 8.5 Class Color Map

```python
CLASS_COLORS = {
    "warrior": discord.Color.red(),
    "rogue": discord.Color.dark_purple(),
    "mage": discord.Color.blue(),
    "ranger": discord.Color.green(),
    "bard": discord.Color.gold(),
    "cleric": discord.Color.light_grey(),
}
```

### 8.6 XP Progress Bar Helper

```python
def xp_progress_bar(current_xp: int, next_level_xp: int, bar_length: int = 10) -> str:
    """Generate a text-based XP progress bar.

    Returns something like: '[####------] 40%'
    """
    if next_level_xp <= 0:
        return "[##########] MAX"
    pct = min(current_xp / next_level_xp, 1.0)
    filled = round(pct * bar_length)
    empty = bar_length - filled
    return f"[{'#' * filled}{'-' * empty}] {int(pct * 100)}%"
```

---

## 9. Modifications to Existing Files

### 9.1 bot.py -- Add new cogs

```python
COGS = [
    "src.bot.cogs.general",
    "src.bot.cogs.character",   # NEW
    "src.bot.cogs.leveling",    # NEW
]
```

### 9.2 src/game/formulas.py -- Add resource calculation

Add this function (it depends on data_loader, so consider placing in `game/leveling.py` instead to keep formulas.py pure):

```python
def calc_resource_maxes(class_data: dict, stats: dict) -> tuple:
    """Calculate (max_hp, max_mana, max_sp) respecting starting-stat exclusion."""
    # See Section 4 for full formula
```

**Decision:** Place `calc_resource_maxes` in `src/game/leveling.py` since it depends on class data, keeping `formulas.py` dependency-free.

### 9.3 src/utils/embeds.py -- Add new embed builders

Add these functions:
- `character_sheet_embed(player: dict, class_data: dict) -> discord.Embed`
- `level_up_embed(character_name: str, events: list, total_stat_points: int) -> discord.Embed`
- `skill_list_embed(class_name: str, skills: list, learned_ids: list, pending: int, player_level: int) -> discord.Embed`
- `talent_list_embed(class_name: str, talents: list, selected_ids: list, pending: int) -> discord.Embed`

Also add:
- `CLASS_COLORS` dict
- `xp_progress_bar()` helper

---

## 10. Testing & Admin Commands

Since combat (Stage 3) doesn't exist yet, we need a way to grant XP for testing the leveling system.

### Admin XP Command (in leveling.py cog)

```python
@app_commands.command(name="admin_xp", description="[Admin] Grant XP for testing")
@app_commands.describe(amount="Amount of XP to grant")
async def admin_xp(self, interaction, amount: int):
```

**Flow:**
1. Fetch player
2. Call `grant_xp(discord_id, amount)`
3. If level-up events occurred, send level_up_embed
4. Otherwise, send simple XP gain message

**Note:** This command should be restricted to server admins or removed before production. For now, it enables end-to-end testing of the leveling pipeline.

### Manual Test Script

After building, verify these scenarios:

1. **Create a character:** `/create TestWarrior warrior` -- should show character sheet with STR=8, HP=100/100
2. **View stats:** `/stats` -- should match creation output
3. **Duplicate creation:** `/create Another warrior` -- should error "already have a character"
4. **Grant XP to level 5:** `/admin_xp 1500` -- should trigger 5 level-ups, award 25 stat points, unlock 1 skill slot
5. **Allocate stats:** `/allocate endurance 5` -- should increase max HP by 50, max Mana by 25, max SP by 25
6. **View skills:** `/skills` -- should show 10 warrior skills, 1 slot available
7. **Learn a skill:** `/learn Whirlwind Attack` -- should succeed, show in `/stats`
8. **Learn without slot:** `/learn Rampage` -- should error "no skill slots available"
9. **Grant XP to level 10:** `/admin_xp 4000` -- should unlock 1 more skill slot + 1 talent slot
10. **Choose talent:** `/choose_talent Iron Will` -- should succeed
11. **Delete character:** `/delete` -- should show confirmation buttons, confirm deletes
12. **Stats after delete:** `/stats` -- should error "no character"

---

## 11. Validation Checklist

When Stage 2 is complete, verify:

- [ ] `/create` creates a character with correct starting stats and resources (HP=100, Mana=50, SP=30)
- [ ] `/create` rejects duplicate characters with a clear error message
- [ ] `/create` validates name length (2-32 chars)
- [ ] `/create` offers all 6 classes as choices
- [ ] `/stats` displays a rich character sheet embed with all stats and computed effects
- [ ] `/stats` shows XP progress bar and unspent stat points
- [ ] `/stats` shows learned skills and selected talents
- [ ] `/delete` shows confirmation buttons before deleting
- [ ] `/delete` actually removes the player and cascaded data
- [ ] `/allocate` correctly deducts unspent points and increases the stat
- [ ] `/allocate` recalculates max HP/Mana/SP when endurance/intelligence/agility are increased
- [ ] `/allocate` increases current resources by the delta (not just max)
- [ ] `/allocate` rejects if insufficient unspent points
- [ ] `/admin_xp` grants XP and triggers level-ups with correct stat point awards
- [ ] Multi-level-up works (e.g., granting enough XP to go from level 1 to 5)
- [ ] Level 5 unlocks a skill slot, level 10 unlocks a skill + talent slot
- [ ] `/skills` shows all class skills with learned/available/locked status
- [ ] `/learn` adds skill to learned list and validates slot availability
- [ ] `/learn` respects `unlock_level` requirements (e.g., Bard's Rallying Cry at level 5)
- [ ] `/learn` autocomplete suggests only available, unlearned skills
- [ ] `/talents` shows all class talents with selected/available status
- [ ] `/choose_talent` adds talent to selected list and validates slot availability
- [ ] `/choose_talent` autocomplete suggests only available, unselected talents
- [ ] Max level is 20 -- no level-ups beyond that
- [ ] All embeds use class-themed colors
- [ ] New cogs are registered in bot.py COGS list
- [ ] All new code imports cleanly with no circular dependencies
