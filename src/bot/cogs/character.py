"""Character commands: /create, /stats, /delete."""

import logging
import re

import discord
from discord import app_commands
from discord.ext import commands

from src.db.models import create_player, delete_player, get_equipped_items, get_player
from src.game.items import calc_equipment_stat_bonuses, get_total_armor_rating
from src.utils.data_loader import get_class
from src.utils.embeds import character_sheet_embed, error_embed, info_embed, success_embed

logger = logging.getLogger("dungeon_bot.character")

NAME_PATTERN = re.compile(r"^[a-zA-Z0-9 '\-]{2,32}$")


class DeleteConfirmView(discord.ui.View):
    """Confirmation buttons for character deletion."""

    def __init__(self, discord_id: str):
        super().__init__(timeout=30)
        self.discord_id = discord_id

    @discord.ui.button(label="Confirm Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await delete_player(self.discord_id)
        logger.info("Character deleted by discord_id=%s", self.discord_id)
        await interaction.response.edit_message(
            embed=success_embed("Character Deleted", "Your character has been permanently deleted."),
            view=None,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=info_embed("Cancelled", "Character deletion cancelled."),
            view=None,
        )
        self.stop()

    async def on_timeout(self):
        pass


class Character(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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
    async def create(
        self, interaction: discord.Interaction, name: str, player_class: app_commands.Choice[str]
    ):
        discord_id = str(interaction.user.id)

        # Check for existing character
        existing = await get_player(discord_id)
        if existing:
            return await interaction.response.send_message(
                embed=error_embed("You already have a character. Use `/delete` to remove it first."),
                ephemeral=True,
            )

        # Validate name
        if not NAME_PATTERN.match(name):
            return await interaction.response.send_message(
                embed=error_embed(
                    "Invalid name. Use 2-32 characters: letters, numbers, spaces, hyphens, apostrophes."
                ),
                ephemeral=True,
            )

        # Look up class data
        class_data = get_class(player_class.value)
        stats = class_data["starting_stats"]

        # Starting resources (no bonus from starting stats)
        hp = max_hp = class_data["base_hp"]
        mana = max_mana = class_data["base_mana"]
        sp = max_sp = class_data["base_sp"]

        # Create the player
        await create_player(
            discord_id, name, player_class.value,
            stats, hp, max_hp, mana, max_mana, sp, max_sp,
        )

        # Fetch and display
        player = await get_player(discord_id)
        logger.info("Character created: %s (%s) by %s",
                     name, player_class.value, discord_id)
        await interaction.response.send_message(
            embed=character_sheet_embed(player, class_data),
        )

    @app_commands.command(name="stats", description="View your character sheet")
    async def stats(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a character. Use `/create` to make one."),
                ephemeral=True,
            )
        class_data = get_class(player["class"])

        # Load equipment data for character sheet
        equipped = await get_equipped_items(player["id"])
        bonuses = calc_equipment_stat_bonuses(equipped)
        total_ar = get_total_armor_rating(equipped)

        await interaction.response.send_message(
            embed=character_sheet_embed(player, class_data, equipped, bonuses, total_ar)
        )

    @app_commands.command(name="delete", description="Delete your character (irreversible)")
    async def delete(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a character to delete."),
                ephemeral=True,
            )

        view = DeleteConfirmView(discord_id)
        await interaction.response.send_message(
            embed=info_embed(
                "Confirm Deletion",
                f"Are you sure you want to delete **{player['character_name']}**? This is permanent.",
            ),
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Character(bot))
