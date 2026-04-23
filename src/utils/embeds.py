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
