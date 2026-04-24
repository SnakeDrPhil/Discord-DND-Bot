"""General commands: /ping, /help, /classinfo."""

import discord
from discord import app_commands
from discord.ext import commands

from src.utils.data_loader import get_class, get_skills, get_talents
from src.utils.embeds import classinfo_embed, help_embed, info_embed


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

    @app_commands.command(name="classinfo",
                          description="View detailed class information")
    @app_commands.describe(class_name="Class to view")
    @app_commands.choices(class_name=[
        app_commands.Choice(name="Warrior", value="warrior"),
        app_commands.Choice(name="Rogue", value="rogue"),
        app_commands.Choice(name="Mage", value="mage"),
        app_commands.Choice(name="Ranger", value="ranger"),
        app_commands.Choice(name="Bard", value="bard"),
        app_commands.Choice(name="Cleric", value="cleric"),
    ])
    async def classinfo(self, interaction: discord.Interaction,
                        class_name: app_commands.Choice[str]):
        class_data = get_class(class_name.value)
        skills = get_skills(class_name.value)
        talents = get_talents(class_name.value)
        embed = classinfo_embed(class_data, skills, talents)
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
