"""Reusable Discord embed builders."""

import json

import discord

from src.game.formulas import (
    calc_bonus_physical_damage,
    calc_bonus_spell_damage,
    calc_buff_duration_chance,
    calc_dodge_chance,
    calc_double_strike_chance,
    calc_healing_bonus,
    calc_song_bonus,
)
from src.utils.data_loader import get_skill_by_id, get_talent_by_id, get_xp_for_level

RARITY_COLORS = {
    "poor": discord.Color.dark_grey(),
    "common": discord.Color.light_grey(),
    "uncommon": discord.Color.green(),
    "rare": discord.Color.blue(),
    "epic": discord.Color.purple(),
    "legendary": discord.Color.orange(),
}

EQUIPMENT_SLOTS = ["head", "shoulders", "chest", "gloves", "legs", "feet", "main_hand", "off_hand"]

CLASS_COLORS = {
    "warrior": discord.Color.red(),
    "rogue": discord.Color.dark_purple(),
    "mage": discord.Color.blue(),
    "ranger": discord.Color.green(),
    "bard": discord.Color.gold(),
    "cleric": discord.Color.light_grey(),
}


def _xp_progress_bar(current_xp: int, next_level_xp: int, bar_length: int = 10) -> str:
    """Generate a text-based XP progress bar."""
    if next_level_xp is None or next_level_xp <= 0:
        return "[##########] MAX"
    pct = min(current_xp / next_level_xp, 1.0)
    filled = round(pct * bar_length)
    empty = bar_length - filled
    return f"[{'#' * filled}{'-' * empty}] {int(pct * 100)}%"


def error_embed(message: str) -> discord.Embed:
    """Red embed for error messages."""
    return discord.Embed(description=message, color=discord.Color.red())


def success_embed(title: str, message: str) -> discord.Embed:
    """Green embed for success messages."""
    return discord.Embed(title=title, description=message, color=discord.Color.green())


def info_embed(title: str, message: str) -> discord.Embed:
    """Blue embed for informational messages."""
    return discord.Embed(title=title, description=message, color=discord.Color.blue())


def help_embed() -> discord.Embed:
    """Full help command embed."""
    embed = discord.Embed(
        title="Dungeon Crawler - Help",
        description="A dungeon crawler RPG played through Discord!",
        color=discord.Color.gold(),
    )

    embed.add_field(
        name="Getting Started",
        value=(
            "`/create <name> <class>` - Create a character\n"
            "Classes: Warrior, Rogue, Mage, Ranger, Bard, Cleric"
        ),
        inline=False,
    )

    embed.add_field(
        name="Character",
        value=(
            "`/stats` - View your character sheet\n"
            "`/inventory` - View your items\n"
            "`/inspect <item>` - View item details\n"
            "`/equip <item>` - Equip weapon or armor\n"
            "`/unequip <slot>` - Remove equipment\n"
            "`/sell <item>` - Sell an item for gold\n"
            "`/use_item <item>` - Use a consumable\n"
            "`/allocate <stat> <points>` - Spend stat points"
        ),
        inline=False,
    )

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

    embed.add_field(
        name="Combat",
        value=(
            "`/fight` - Engage in combat\n"
            "`/attack <type>` - Basic attack (slash/thrust)\n"
            "`/use <skill>` - Use a combat skill\n"
            "`/cast <spell>` - Cast a spell\n"
            "`/item <name>` - Use a consumable\n"
            "`/flee` - Attempt to flee"
        ),
        inline=False,
    )

    embed.add_field(
        name="Info",
        value=(
            "`/ping` - Check bot latency\n"
            "`/help` - Show this message"
        ),
        inline=False,
    )

    embed.set_footer(text="Dungeon Crawler Bot v0.1")
    return embed


def character_sheet_embed(player: dict, class_data: dict) -> discord.Embed:
    """Rich character sheet embed with stats and computed effects."""
    color = CLASS_COLORS.get(player["class"], discord.Color.greyple())
    embed = discord.Embed(
        title=f"{player['character_name']} - Level {player['level']} {class_data['name']}",
        description=class_data["description"],
        color=color,
    )

    # Resources
    embed.add_field(
        name="Resources",
        value=(
            f"HP: {player['hp']}/{player['max_hp']}\n"
            f"Mana: {player['mana']}/{player['max_mana']}\n"
            f"SP: {player['sp']}/{player['max_sp']}"
        ),
        inline=True,
    )

    # Stats with computed effects
    str_bonus = calc_bonus_physical_damage(player["strength"])
    dex_bonus = calc_double_strike_chance(player["dexterity"])
    int_bonus = calc_bonus_spell_damage(player["intelligence"])
    agi_bonus = calc_dodge_chance(player["agility"])
    wis_bonus = calc_healing_bonus(player["wisdom"])
    cha_bonus = calc_song_bonus(player["charisma"])

    embed.add_field(
        name="Stats",
        value=(
            f"STR: {player['strength']}  (+{str_bonus:.1f} dmg)\n"
            f"DEX: {player['dexterity']}  ({dex_bonus:.1f}% double strike)\n"
            f"INT: {player['intelligence']}  (+{int_bonus:.1f} spell dmg)\n"
            f"AGI: {player['agility']}  ({agi_bonus:.1f}% dodge)\n"
            f"WIS: {player['wisdom']}  (+{wis_bonus:.1f}% healing)\n"
            f"END: {player['endurance']}\n"
            f"CHA: {player['charisma']}  (+{cha_bonus:.1f} song pwr)"
        ),
        inline=True,
    )

    # Progression
    next_xp = get_xp_for_level(player["level"] + 1)
    bar = _xp_progress_bar(player["xp"], next_xp)
    xp_display = f"{player['xp']}/{next_xp}" if next_xp else f"{player['xp']} (MAX)"
    embed.add_field(
        name="Progression",
        value=(
            f"XP: {xp_display}\n"
            f"{bar}\n"
            f"Unspent stat points: {player['unspent_stat_points']}"
        ),
        inline=False,
    )

    # Learned skills
    learned_ids = json.loads(player["learned_skills"])
    if learned_ids:
        skill_lines = []
        for sid in learned_ids:
            skill = get_skill_by_id(sid)
            if skill:
                skill_lines.append(f"- {skill['name']} ({skill['cost']} {skill['resource']})")
        if skill_lines:
            embed.add_field(name="Skills", value="\n".join(skill_lines), inline=False)

    # Selected talents
    selected_ids = json.loads(player["selected_talents"])
    if selected_ids:
        talent_lines = []
        for tid in selected_ids:
            talent = get_talent_by_id(tid)
            if talent:
                talent_lines.append(f"- {talent['name']}")
        if talent_lines:
            embed.add_field(name="Talents", value="\n".join(talent_lines), inline=False)

    embed.set_footer(
        text=f"Main stat: {class_data['main_stat'].capitalize()} | Gold: {player['gold']}"
    )
    return embed


def level_up_embed(character_name: str, events: list) -> discord.Embed:
    """Gold embed for level-up notification."""
    final_level = events[-1]["new_level"]
    total_stat_points = sum(e["stat_points_awarded"] for e in events)
    total_levels = len(events)

    if total_levels > 1:
        title = "Level Up!"
        desc = f"{character_name} reached Level {final_level}! (+{total_levels} levels)"
    else:
        title = "Level Up!"
        desc = f"{character_name} reached Level {final_level}!"

    embed = discord.Embed(title=title, description=desc, color=discord.Color.gold())

    rewards = f"+{total_stat_points} stat points"
    skill_unlocked = any(e["skill_unlocked"] for e in events)
    talent_unlocked = any(e["talent_unlocked"] for e in events)
    if skill_unlocked:
        rewards += "\nNew skill slot available! Use `/skills` to learn one."
    if talent_unlocked:
        rewards += "\nNew talent slot available! Use `/talents` to choose one."

    embed.add_field(name="Rewards", value=rewards, inline=False)
    return embed


def skill_list_embed(
    class_name: str, skills: list, learned_ids: list, pending: int, player_level: int
) -> discord.Embed:
    """Embed listing all class skills with learned/available/locked status."""
    color = CLASS_COLORS.get(class_name.lower(), discord.Color.greyple())
    desc = (
        f"{pending} skill slot(s) available" if pending > 0 else "No skill slots available"
    )
    embed = discord.Embed(title=f"{class_name.capitalize()} Skills", description=desc, color=color)

    lines = []
    for s in skills:
        unlock = s.get("unlock_level")
        if s["id"] in learned_ids:
            header = f"**[LEARNED]** {s['name']}"
        elif unlock and player_level < unlock:
            header = f"~~{s['name']}~~ (Unlocks at Level {unlock})"
        else:
            header = s["name"]
        detail = f"  {s['type']} | {s['cost']} {s['resource']} | {s['effect']}"
        lines.append(f"{header}\n{detail}")

    embed.add_field(name="\u200b", value="\n".join(lines) if lines else "No skills.", inline=False)
    return embed


def talent_list_embed(
    class_name: str, talents: list, selected_ids: list, pending: int
) -> discord.Embed:
    """Embed listing all class talents with selected/available status."""
    color = CLASS_COLORS.get(class_name.lower(), discord.Color.greyple())
    desc = (
        f"{pending} talent slot(s) available" if pending > 0 else "No talent slots available"
    )
    embed = discord.Embed(
        title=f"{class_name.capitalize()} Talents", description=desc, color=color
    )

    lines = []
    for t in talents:
        if t["id"] in selected_ids:
            header = f"**[SELECTED]** {t['name']}"
        else:
            header = t["name"]
        lines.append(f"{header}\n  {t['effect']}")

    embed.add_field(name="\u200b", value="\n".join(lines) if lines else "No talents.", inline=False)
    return embed


# ── Combat Embeds ───────────────────────────────────────────────────

def _resource_bar(current: int, maximum: int, length: int = 10) -> str:
    if maximum <= 0:
        return "\u2591" * length
    ratio = min(max(current, 0) / maximum, 1.0)
    filled = round(ratio * length)
    return "\u2588" * filled + "\u2591" * (length - filled)


def combat_embed(
    player: dict, session: dict, enemies: list, log_entries: list,
    attacks_left: int, buffs_left: int, items_left: int,
) -> discord.Embed:
    """Build the combat status embed."""
    color = CLASS_COLORS.get(player["class"], discord.Color.greyple())
    embed = discord.Embed(
        title=f"Combat - Turn {session['turn_number']}",
        color=color,
    )

    # Player status
    pstatus = (
        f"HP: {_resource_bar(player['hp'], player['max_hp'])} {player['hp']}/{player['max_hp']}\n"
        f"Mana: {_resource_bar(player['mana'], player['max_mana'])} {player['mana']}/{player['max_mana']}\n"
        f"SP: {_resource_bar(player['sp'], player['max_sp'])} {player['sp']}/{player['max_sp']}"
    )
    buffs = json.loads(session["player_buffs"]) if isinstance(session["player_buffs"], str) else session["player_buffs"]
    if buffs:
        pstatus += "\nBuffs: " + ", ".join(f"{b['type']}({b['remaining_turns']}t)" for b in buffs)
    debuffs = json.loads(session["player_debuffs"]) if isinstance(session["player_debuffs"], str) else session["player_debuffs"]
    if debuffs:
        pstatus += "\nDebuffs: " + ", ".join(f"{d['type']}({d['remaining_turns']}t)" for d in debuffs)
    embed.add_field(name=player["character_name"], value=pstatus, inline=True)

    # Enemy status
    enemy_debuffs = json.loads(session["enemy_debuffs"]) if isinstance(session["enemy_debuffs"], str) else session["enemy_debuffs"]
    estatus = ""
    for e in enemies:
        if not e["is_alive"]:
            estatus += f"~~{e['name']} (Lv.{e['level']})~~ DEAD\n"
            continue
        estatus += f"{e['name']} (Lv.{e['level']}): {_resource_bar(e['hp'], e['max_hp'])} {e['hp']}/{e['max_hp']}\n"
        edbs = [d for d in enemy_debuffs if d.get("enemy_id") == e["id"]]
        if edbs:
            estatus += f"  [{', '.join(d['type'] for d in edbs)}]\n"
    embed.add_field(name="Enemies", value=estatus.strip() or "None", inline=True)

    # Actions
    a = "avail" if attacks_left > 0 else "used"
    b = "avail" if buffs_left > 0 else "used"
    it = "avail" if items_left > 0 else "used"
    embed.add_field(name="Actions", value=f"Attack: {a} | Buff: {b} | Item: {it}", inline=False)

    # Combat log
    if log_entries:
        log_text = "\n".join(f"> {e['message']}" for e in log_entries[-5:])
        embed.add_field(name="Combat Log", value=log_text, inline=False)

    return embed


def combat_victory_embed(
    player_name: str, xp: int, perfect: bool, gold: int,
    loot: list, level_events: list,
) -> discord.Embed:
    embed = discord.Embed(title="Victory!", color=discord.Color.green())
    desc = f"**{player_name}** won the battle!"
    if perfect:
        desc += " (Perfect encounter!)"
    embed.description = desc

    rewards = f"XP: +{xp}"
    if perfect:
        rewards += " (includes +10% bonus)"
    if gold > 0:
        rewards += f"\nGold: +{gold}"
    if loot:
        for item in loot:
            rewards += f"\nLoot: {item['name']}"
    embed.add_field(name="Rewards", value=rewards, inline=False)

    if level_events:
        final = level_events[-1]["new_level"]
        pts = sum(e["stat_points_awarded"] for e in level_events)
        lvl_text = f"Reached Level {final}! +{pts} stat points"
        if any(e["skill_unlocked"] for e in level_events):
            lvl_text += "\nNew skill slot! Use `/skills`"
        if any(e["talent_unlocked"] for e in level_events):
            lvl_text += "\nNew talent slot! Use `/talents`"
        embed.add_field(name="Level Up!", value=lvl_text, inline=False)

    return embed


def combat_defeat_embed() -> discord.Embed:
    return discord.Embed(
        title="Defeated!",
        description="You were slain in combat. Your wounds have been healed.",
        color=discord.Color.red(),
    )


def combat_flee_embed(took_damage: bool, damage: int = 0) -> discord.Embed:
    desc = "You fled from combat. No XP or loot gained."
    if took_damage:
        desc += f"\nYou took {damage} damage while fleeing!"
    return discord.Embed(
        title="Escaped!",
        description=desc,
        color=discord.Color.orange(),
    )


# ── Dungeon Embeds ─────────────────────────────────────────────────

def dungeon_enter_embed(player_name: str, floor: int, map_str: str,
                        legend: str) -> discord.Embed:
    """Embed shown when entering the dungeon."""
    embed = discord.Embed(
        title=f"Floor {floor}",
        description=f"**{player_name}** enters the dungeon.\n\n{map_str}",
        color=discord.Color.dark_grey(),
    )
    embed.add_field(name="Legend", value=legend, inline=False)
    return embed


def dungeon_map_embed(player: dict, floor: int, map_str: str, legend: str,
                      tiles_explored: int, total_passable: int) -> discord.Embed:
    """Map display embed with player status."""
    embed = discord.Embed(
        title=f"Floor {floor} - Map",
        description=map_str,
        color=discord.Color.dark_grey(),
    )
    embed.add_field(
        name="Status",
        value=(
            f"HP: {player['hp']}/{player['max_hp']} | "
            f"Mana: {player['mana']}/{player['max_mana']} | "
            f"SP: {player['sp']}/{player['max_sp']}"
        ),
        inline=False,
    )
    embed.add_field(
        name="Explored",
        value=f"{tiles_explored}/{total_passable} tiles",
        inline=True,
    )
    embed.add_field(name="Legend", value=legend, inline=False)
    return embed


def dungeon_move_embed(player: dict, floor: int, map_str: str,
                       move_msg: str, regen_msg: str) -> discord.Embed:
    """Embed after movement with map and result."""
    embed = discord.Embed(
        title=f"Floor {floor}",
        description=map_str,
        color=discord.Color.dark_grey(),
    )
    embed.add_field(name="Movement", value=move_msg, inline=False)
    if regen_msg:
        embed.add_field(name="Regeneration", value=regen_msg, inline=True)
    embed.add_field(
        name="Resources",
        value=(
            f"HP: {player['hp']}/{player['max_hp']} | "
            f"Mana: {player['mana']}/{player['max_mana']} | "
            f"SP: {player['sp']}/{player['max_sp']}"
        ),
        inline=False,
    )
    return embed


def scenario_embed(event: dict, category: str, messages: list) -> discord.Embed:
    """Scenario result embed."""
    colors = {
        "negative": discord.Color.red(),
        "positive": discord.Color.green(),
        "neutral": discord.Color.light_grey(),
    }
    embed = discord.Embed(
        title=event["name"],
        description=event["description"],
        color=colors.get(category, discord.Color.greyple()),
    )
    if messages:
        embed.add_field(name="Outcome", value="\n".join(messages), inline=False)
    return embed


def floor_complete_embed(player_name: str, floor: int,
                         tiles_explored: int) -> discord.Embed:
    """Embed for reaching the exit tile."""
    return discord.Embed(
        title="Floor Complete!",
        description=(
            f"**{player_name}** cleared Floor {floor}!\n"
            f"Tiles explored: {tiles_explored}\n\n"
            f"Use `/enter` to descend to Floor {floor + 1}."
        ),
        color=discord.Color.gold(),
    )


def dungeon_death_embed(items_lost: int) -> discord.Embed:
    """Embed for dying in the dungeon."""
    embed = discord.Embed(
        title="You Have Fallen!",
        description=(
            "Your dungeon run has ended.\n"
            "You keep your XP, level, and equipped items.\n"
            "Your wounds have been healed."
        ),
        color=discord.Color.dark_red(),
    )
    if items_lost > 0:
        embed.add_field(
            name="Items Lost",
            value=f"{items_lost} unequipped item(s) lost.",
            inline=False,
        )
    return embed


def dungeon_retreat_embed(player_name: str) -> discord.Embed:
    """Embed for voluntary retreat."""
    return discord.Embed(
        title="Retreated",
        description=f"**{player_name}** left the dungeon safely. All items and XP kept.",
        color=discord.Color.orange(),
    )


# ── Inventory / Equipment Embeds ──────────────────────────────────

def _format_item_line(item_data: dict, equipped: bool = False, slot: str = None) -> str:
    """Format a single item for inventory display."""
    name = item_data.get("name", "Unknown")
    rarity = item_data.get("rarity", "")
    itype = item_data.get("type", "")
    parts = []
    if equipped and slot:
        parts.append(f"[{slot.replace('_', ' ').title()}]")
    if rarity and rarity not in ("poor", "common"):
        parts.append(f"({rarity.capitalize()})")
    if itype == "weapon":
        parts.append(f"{item_data.get('damage_min', '?')}-{item_data.get('damage_max', '?')} dmg")
    elif itype == "armor":
        parts.append(f"{item_data.get('armor_rating', '?')} AR")
    prefix = " ".join(parts)
    return f"**{name}** {prefix}".strip()


def inventory_embed(player: dict, items: list) -> discord.Embed:
    """Show full inventory grouped by type with equipped markers."""
    color = CLASS_COLORS.get(player["class"], discord.Color.greyple())
    embed = discord.Embed(
        title=f"{player['character_name']}'s Inventory",
        color=color,
    )

    equipped_lines = []
    weapon_lines = []
    armor_lines = []
    consumable_lines = []
    other_lines = []

    for item in items:
        idata = json.loads(item["item_data"]) if isinstance(item["item_data"], str) else item["item_data"]
        is_equipped = item.get("equipped", 0) == 1
        slot = item.get("slot")

        if is_equipped:
            equipped_lines.append(_format_item_line(idata, True, slot))
        elif idata.get("type") == "weapon":
            weapon_lines.append(_format_item_line(idata))
        elif idata.get("type") == "armor":
            armor_lines.append(_format_item_line(idata))
        elif item.get("item_type") == "consumable" or idata.get("category"):
            consumable_lines.append(f"**{idata.get('name', 'Unknown')}**")
        else:
            other_lines.append(f"**{idata.get('name', 'Unknown')}**")

    if equipped_lines:
        embed.add_field(name="Equipped", value="\n".join(equipped_lines), inline=False)
    if weapon_lines:
        embed.add_field(name="Weapons", value="\n".join(weapon_lines), inline=False)
    if armor_lines:
        embed.add_field(name="Armor", value="\n".join(armor_lines), inline=False)
    if consumable_lines:
        embed.add_field(name="Consumables", value="\n".join(consumable_lines), inline=False)
    if other_lines:
        embed.add_field(name="Other", value="\n".join(other_lines), inline=False)
    if not any([equipped_lines, weapon_lines, armor_lines, consumable_lines, other_lines]):
        embed.description = "Your inventory is empty."

    embed.set_footer(text=f"{len(items)}/20 slots used | Gold: {player.get('gold', 0)}")
    return embed


def item_inspect_embed(item_data: dict) -> discord.Embed:
    """Detailed item view with stats, rarity color, affixes."""
    rarity = item_data.get("rarity", "common")
    color = RARITY_COLORS.get(rarity, discord.Color.greyple())
    embed = discord.Embed(
        title=item_data.get("name", "Unknown Item"),
        color=color,
    )

    itype = item_data.get("type", "")
    details = [f"**Type:** {itype.capitalize()}"]
    if rarity:
        details.append(f"**Rarity:** {rarity.capitalize()}")

    if itype == "weapon":
        details.append(f"**Damage:** {item_data.get('damage_min', '?')}-{item_data.get('damage_max', '?')}")
        details.append(f"**Hand Type:** {item_data.get('hand_type', '?').replace('_', ' ').title()}")
        details.append(f"**Damage Type:** {item_data.get('damage_type', '?').capitalize()}")
        if item_data.get("casting"):
            details.append("**Casting:** Yes (provides spell base damage)")
    elif itype == "armor":
        details.append(f"**Armor Rating:** {item_data.get('armor_rating', '?')}")
        details.append(f"**Slot:** {item_data.get('slot', '?').replace('_', ' ').title()}")
        details.append(f"**Armor Type:** {item_data.get('armor_type', '?').capitalize()}")
        classes = item_data.get("allowed_classes", [])
        if classes:
            details.append(f"**Classes:** {', '.join(c.capitalize() for c in classes)}")
    elif itype == "consumable" or item_data.get("category"):
        if item_data.get("effect"):
            details.append(f"**Effect:** {item_data['effect']}")

    embed.description = "\n".join(details)

    affixes = item_data.get("stat_affixes", [])
    if affixes:
        affix_lines = [f"+{a['value']} {a['stat'].capitalize()}" for a in affixes]
        embed.add_field(name="Stat Bonuses", value="\n".join(affix_lines), inline=True)

    sell = item_data.get("sell_value")
    if sell:
        embed.set_footer(text=f"Sell value: {sell} gold")

    return embed


def equip_embed(item_name: str, slot: str, unequipped_name: str = None) -> discord.Embed:
    """Show equip confirmation with what was replaced."""
    slot_display = slot.replace("_", " ").title()
    desc = f"Equipped **{item_name}** in {slot_display}."
    if unequipped_name:
        desc += f"\nUnequipped **{unequipped_name}**."
    return discord.Embed(
        title="Equipment Changed",
        description=desc,
        color=discord.Color.green(),
    )
