"""General commands: /ping and /help."""

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.embeds import help_embed, info_embed


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check bot latency")
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.bot.latency * 1000)
        embed = info_embed("Pong!", f"Latency: **{latency_ms}ms**")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="help", description="Show all available commands")
    async def help_command(self, interaction: discord.Interaction):
        await interaction.response.send_message(embed=help_embed())


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
