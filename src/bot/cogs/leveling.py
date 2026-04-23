"""Leveling commands: /allocate, /skills, /learn, /talents, /choose_talent, /admin_xp."""

import json

import discord
from discord import app_commands
from discord.ext import commands

from src.db.models import get_player, update_player
from src.game.constants import ALL_STATS
from src.game.leveling import (
    calc_resource_maxes,
    get_pending_skill_slots,
    get_pending_talent_slots,
    grant_xp,
)
from src.utils.data_loader import get_class, get_skills, get_talent_by_id, get_talents
from src.utils.embeds import (
    error_embed,
    level_up_embed,
    skill_list_embed,
    success_embed,
    talent_list_embed,
)


class Leveling(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- /allocate ---

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
    async def allocate(
        self, interaction: discord.Interaction,
        stat: app_commands.Choice[str], points: int,
    ):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a character. Use `/create` to make one."),
                ephemeral=True,
            )
        if points < 1:
            return await interaction.response.send_message(
                embed=error_embed("You must allocate at least 1 point."), ephemeral=True,
            )
        if points > player["unspent_stat_points"]:
            return await interaction.response.send_message(
                embed=error_embed(
                    f"You only have {player['unspent_stat_points']} unspent stat point(s)."
                ),
                ephemeral=True,
            )

        old_value = player[stat.value]
        new_value = old_value + points
        new_unspent = player["unspent_stat_points"] - points

        # Build new stats dict for resource recalculation
        new_stats = {s: player[s] for s in ALL_STATS}
        new_stats[stat.value] = new_value

        class_data = get_class(player["class"])
        new_max_hp, new_max_mana, new_max_sp = calc_resource_maxes(class_data, new_stats)

        hp_delta = new_max_hp - player["max_hp"]
        mana_delta = new_max_mana - player["max_mana"]
        sp_delta = new_max_sp - player["max_sp"]

        updates = {
            stat.value: new_value,
            "unspent_stat_points": new_unspent,
            "max_hp": new_max_hp,
            "max_mana": new_max_mana,
            "max_sp": new_max_sp,
            "hp": min(player["hp"] + max(0, hp_delta), new_max_hp),
            "mana": min(player["mana"] + max(0, mana_delta), new_max_mana),
            "sp": min(player["sp"] + max(0, sp_delta), new_max_sp),
        }

        await update_player(discord_id, **updates)

        # Build response
        msg = f"**{stat.name}** {old_value} -> {new_value}\nRemaining stat points: {new_unspent}"
        if hp_delta > 0 or mana_delta > 0 or sp_delta > 0:
            resource_changes = []
            if hp_delta > 0:
                resource_changes.append(f"HP +{hp_delta}")
            if mana_delta > 0:
                resource_changes.append(f"Mana +{mana_delta}")
            if sp_delta > 0:
                resource_changes.append(f"SP +{sp_delta}")
            msg += f"\nResources: {', '.join(resource_changes)}"

        await interaction.response.send_message(
            embed=success_embed("Stat Allocated", msg),
        )

    # --- /skills ---

    @app_commands.command(name="skills", description="View available skills for your class")
    async def skills(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a character. Use `/create` to make one."),
                ephemeral=True,
            )

        class_skills = get_skills(player["class"])
        learned_ids = json.loads(player["learned_skills"])
        pending = get_pending_skill_slots(player["level"], len(learned_ids))

        await interaction.response.send_message(
            embed=skill_list_embed(
                player["class"], class_skills, learned_ids, pending, player["level"]
            ),
        )

    # --- /learn ---

    @app_commands.command(name="learn", description="Learn a new skill")
    @app_commands.describe(skill_name="Name of the skill to learn")
    async def learn(self, interaction: discord.Interaction, skill_name: str):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a character. Use `/create` to make one."),
                ephemeral=True,
            )

        class_skills = get_skills(player["class"])
        learned_ids = json.loads(player["learned_skills"])

        # Find the skill (match by id from autocomplete, or by name)
        skill = None
        for s in class_skills:
            if s["id"] == skill_name or s["name"].lower() == skill_name.lower():
                skill = s
                break

        if not skill:
            return await interaction.response.send_message(
                embed=error_embed("Skill not found or doesn't belong to your class."),
                ephemeral=True,
            )

        if skill["id"] in learned_ids:
            return await interaction.response.send_message(
                embed=error_embed("You've already learned that skill."), ephemeral=True,
            )

        # Check slots
        pending = get_pending_skill_slots(player["level"], len(learned_ids))
        if pending <= 0:
            return await interaction.response.send_message(
                embed=error_embed("No skill slots available. Level up to unlock more."),
                ephemeral=True,
            )

        # Check unlock level
        unlock = skill.get("unlock_level")
        if unlock and player["level"] < unlock:
            return await interaction.response.send_message(
                embed=error_embed(f"This skill unlocks at level {unlock}. You are level {player['level']}."),
                ephemeral=True,
            )

        # Learn the skill
        learned_ids.append(skill["id"])
        await update_player(discord_id, learned_skills=json.dumps(learned_ids))

        await interaction.response.send_message(
            embed=success_embed(
                f"Learned: {skill['name']}",
                f"{skill['effect']}\nCost: {skill['cost']} {skill['resource']}",
            ),
        )

    @learn.autocomplete("skill_name")
    async def learn_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list:
        player = await get_player(str(interaction.user.id))
        if not player:
            return []
        class_skills = get_skills(player["class"])
        learned = json.loads(player["learned_skills"])
        available = [
            s for s in class_skills
            if s["id"] not in learned
            and (s.get("unlock_level") is None or player["level"] >= s["unlock_level"])
        ]
        return [
            app_commands.Choice(name=s["name"], value=s["id"])
            for s in available
            if current.lower() in s["name"].lower()
        ][:25]

    # --- /talents ---

    @app_commands.command(name="talents", description="View available talents for your class")
    async def talents(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a character. Use `/create` to make one."),
                ephemeral=True,
            )

        class_talents = get_talents(player["class"])
        selected_ids = json.loads(player["selected_talents"])
        pending = get_pending_talent_slots(player["level"], len(selected_ids))

        await interaction.response.send_message(
            embed=talent_list_embed(
                player["class"], class_talents, selected_ids, pending
            ),
        )

    # --- /choose_talent ---

    @app_commands.command(name="choose_talent", description="Select a passive talent")
    @app_commands.describe(talent_name="Name of the talent to select")
    async def choose_talent(self, interaction: discord.Interaction, talent_name: str):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a character. Use `/create` to make one."),
                ephemeral=True,
            )

        class_talents = get_talents(player["class"])
        selected_ids = json.loads(player["selected_talents"])

        # Find the talent (by id or name)
        talent = None
        for t in class_talents:
            if t["id"] == talent_name or t["name"].lower() == talent_name.lower():
                talent = t
                break

        if not talent:
            return await interaction.response.send_message(
                embed=error_embed("Talent not found or doesn't belong to your class."),
                ephemeral=True,
            )

        if talent["id"] in selected_ids:
            return await interaction.response.send_message(
                embed=error_embed("You've already selected that talent."), ephemeral=True,
            )

        # Check slots
        pending = get_pending_talent_slots(player["level"], len(selected_ids))
        if pending <= 0:
            return await interaction.response.send_message(
                embed=error_embed("No talent slots available. Level up to unlock more."),
                ephemeral=True,
            )

        # Select the talent
        selected_ids.append(talent["id"])
        await update_player(discord_id, selected_talents=json.dumps(selected_ids))

        await interaction.response.send_message(
            embed=success_embed(
                f"Selected: {talent['name']}",
                talent["effect"],
            ),
        )

    @choose_talent.autocomplete("talent_name")
    async def choose_talent_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list:
        player = await get_player(str(interaction.user.id))
        if not player:
            return []
        class_talents = get_talents(player["class"])
        selected = json.loads(player["selected_talents"])
        available = [t for t in class_talents if t["id"] not in selected]
        return [
            app_commands.Choice(name=t["name"], value=t["id"])
            for t in available
            if current.lower() in t["name"].lower()
        ][:25]

    # --- /admin_xp ---

    @app_commands.command(name="admin_xp", description="[Admin] Grant XP for testing")
    @app_commands.describe(amount="Amount of XP to grant")
    async def admin_xp(self, interaction: discord.Interaction, amount: int):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("You don't have a character. Use `/create` to make one."),
                ephemeral=True,
            )

        if amount < 1:
            return await interaction.response.send_message(
                embed=error_embed("Amount must be positive."), ephemeral=True,
            )

        old_level = player["level"]
        updated_player, events = await grant_xp(discord_id, amount)

        if events:
            await interaction.response.send_message(
                embed=level_up_embed(updated_player["character_name"], events),
            )
        else:
            await interaction.response.send_message(
                embed=success_embed(
                    "XP Granted",
                    f"+{amount} XP (Total: {updated_player['xp']})",
                ),
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))
