"""Admin commands: /admin_set_floor, /admin_set_gold, /admin_set_level, /admin_heal, /admin_clear_effects, /admin_boss."""

import json
import logging

import discord
from discord import app_commands
from discord.ext import commands

from src.db.models import (
    get_dungeon_session,
    get_player,
    update_dungeon_session,
    update_player,
)
from src.game.combat import spawn_boss
from src.game.constants import FLOOR_BOSSES
from src.utils.data_loader import get_class, get_xp_for_level
from src.utils.embeds import error_embed, success_embed

logger = logging.getLogger("dungeon_bot.admin")


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="admin_set_floor",
                          description="[Admin] Set your current floor")
    @app_commands.describe(floor="Floor number (1-5)")
    async def admin_set_floor(self, interaction: discord.Interaction, floor: int):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        floor = max(1, min(floor, 5))
        highest = max(floor, player.get("highest_floor", 1) or 1)
        await update_player(str(interaction.user.id),
                            current_floor=floor, highest_floor=highest)
        logger.warning("admin_set_floor used by %s: floor=%d",
                        interaction.user.id, floor)
        await interaction.response.send_message(
            embed=success_embed("Floor Set",
                                f"Current floor set to **{floor}**.\n"
                                f"Highest floor: {highest}"))

    @app_commands.command(name="admin_set_gold",
                          description="[Admin] Set your gold amount")
    @app_commands.describe(amount="Gold amount")
    async def admin_set_gold(self, interaction: discord.Interaction, amount: int):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        amount = max(0, amount)
        await update_player(str(interaction.user.id), gold=amount)
        logger.warning("admin_set_gold used by %s: amount=%d",
                        interaction.user.id, amount)
        await interaction.response.send_message(
            embed=success_embed("Gold Set", f"Gold set to **{amount}**."))

    @app_commands.command(name="admin_set_level",
                          description="[Admin] Set your character level")
    @app_commands.describe(level="Target level (1-20)")
    async def admin_set_level(self, interaction: discord.Interaction, level: int):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        level = max(1, min(level, 20))
        # Set XP to the threshold for this level
        xp_needed = get_xp_for_level(level)
        xp = xp_needed if xp_needed else 0

        # Recalculate stat points: (level - 1) * 5 total earned, minus spent
        from src.game.constants import STAT_POINTS_PER_LEVEL, ALL_STATS
        class_data = get_class(player["class"])
        starting_stats = class_data["starting_stats"]
        spent = sum(player[s] - starting_stats[s] for s in ALL_STATS)
        total_earned = (level - 1) * STAT_POINTS_PER_LEVEL
        unspent = max(0, total_earned - spent)

        await update_player(str(interaction.user.id),
                            level=level, xp=xp, unspent_stat_points=unspent)
        logger.warning("admin_set_level used by %s: level=%d",
                        interaction.user.id, level)
        await interaction.response.send_message(
            embed=success_embed("Level Set",
                                f"Level set to **{level}**.\n"
                                f"XP: {xp}\n"
                                f"Unspent stat points: {unspent}"))

    @app_commands.command(name="admin_heal",
                          description="[Admin] Fully restore HP, Mana, and SP")
    async def admin_heal(self, interaction: discord.Interaction):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        await update_player(str(interaction.user.id),
                            hp=player["max_hp"],
                            mana=player["max_mana"],
                            sp=player["max_sp"])
        logger.warning("admin_heal used by %s", interaction.user.id)
        await interaction.response.send_message(
            embed=success_embed("Fully Healed",
                                f"HP: {player['max_hp']}/{player['max_hp']}\n"
                                f"Mana: {player['max_mana']}/{player['max_mana']}\n"
                                f"SP: {player['max_sp']}/{player['max_sp']}"))

    @app_commands.command(name="admin_clear_effects",
                          description="[Admin] Clear all dungeon effects")
    async def admin_clear_effects(self, interaction: discord.Interaction):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        dsess = await get_dungeon_session(player["id"])
        if not dsess:
            return await interaction.response.send_message(
                embed=error_embed("Not in a dungeon."), ephemeral=True)

        await update_dungeon_session(player["id"], active_effects=json.dumps([]))
        logger.warning("admin_clear_effects used by %s", interaction.user.id)
        await interaction.response.send_message(
            embed=success_embed("Effects Cleared",
                                "All dungeon effects have been removed."))

    @app_commands.command(name="admin_boss",
                          description="[Admin] Force a boss encounter")
    @app_commands.describe(boss_type="Boss type (e.g. goblin_king)")
    async def admin_boss(self, interaction: discord.Interaction,
                         boss_type: str = "goblin_king"):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        from src.db.models import get_combat_session, create_combat_session
        csess = await get_combat_session(player["id"])
        if csess:
            return await interaction.response.send_message(
                embed=error_embed("Already in combat!"), ephemeral=True)

        enemies = spawn_boss(boss_type)
        if not enemies:
            return await interaction.response.send_message(
                embed=error_embed(f"Unknown boss type: {boss_type}"),
                ephemeral=True)

        await create_combat_session(player["id"], json.dumps(enemies))
        logger.warning("admin_boss used by %s: boss=%s",
                        interaction.user.id, boss_type)

        # Build combat embed
        combat_cog = interaction.client.get_cog("Combat")
        if combat_cog:
            from src.db.models import get_combat_session as _gcs
            from src.game.combat import parse_state, get_max_actions
            from src.utils.embeds import combat_embed

            # Inject equipment
            from src.bot.cogs.combat import _inject_equipment
            await _inject_equipment(player)

            csess = await _gcs(player["id"])
            state = parse_state(csess)
            ma, mb, mi = get_max_actions(player)
            embed = combat_embed(player, csess, enemies, [], ma, mb, mi)
            names = ", ".join(f"{e['name']} (Lv.{e['level']})" for e in enemies)
            embed.description = f"Boss fight: {names}!"
            view = await combat_cog._build_view(player, state)
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(
                embed=success_embed("Boss Spawned",
                                    "Boss combat started! Use `/fight` to view."))

    @admin_boss.autocomplete("boss_type")
    async def boss_autocomplete(self, interaction: discord.Interaction,
                                 current: str):
        bosses = list(set(FLOOR_BOSSES.values()))
        return [
            app_commands.Choice(
                name=b.replace("_", " ").title(), value=b)
            for b in bosses if current.lower() in b.lower()
        ][:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
