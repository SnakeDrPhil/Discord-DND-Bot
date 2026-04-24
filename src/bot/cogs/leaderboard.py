"""Leaderboard commands: /leaderboard."""

import discord
from discord import app_commands
from discord.ext import commands

from src.db.models import get_leaderboard
from src.utils.embeds import leaderboard_embed


class Leaderboard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="leaderboard", description="View the leaderboard")
    @app_commands.describe(category="Leaderboard category")
    @app_commands.choices(category=[
        app_commands.Choice(name="Level", value="level"),
        app_commands.Choice(name="Highest Floor", value="floor"),
        app_commands.Choice(name="Enemies Killed", value="kills"),
    ])
    async def leaderboard(self, interaction: discord.Interaction,
                          category: app_commands.Choice[str] = None):
        cat = category.value if category else "level"
        entries = await get_leaderboard(cat, limit=10)
        embed = leaderboard_embed(cat, entries)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Leaderboard(bot))
