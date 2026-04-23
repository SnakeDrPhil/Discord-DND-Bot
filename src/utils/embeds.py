"""Reusable Discord embed builders."""

import discord


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
