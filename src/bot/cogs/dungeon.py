"""Dungeon commands: /enter, /move, /map, /retreat with interactive buttons."""

import json
import random

import discord
from discord import app_commands
from discord.ext import commands

from src.db.models import (
    add_inventory_item,
    clear_non_equipped_inventory,
    create_combat_session,
    create_dungeon_session,
    delete_dungeon_session,
    get_combat_session,
    get_dungeon_session,
    get_inventory,
    get_non_equipped_inventory,
    get_player,
    remove_inventory_item,
    update_dungeon_session,
    update_player,
)
from src.game.combat import spawn_enemies
from src.game.dungeon import (
    MAP_LEGEND,
    apply_dungeon_effects_to_player,
    apply_regen,
    get_encounter_level,
    get_tile,
    get_valid_moves,
    load_floor,
    regen_message,
    render_map,
    resolve_scenario,
    roll_path_encounter,
    tick_dungeon_effects,
)
from src.game.leveling import grant_xp
from src.utils.data_loader import get_consumables
from src.utils.embeds import (
    dungeon_death_embed,
    dungeon_enter_embed,
    dungeon_map_embed,
    dungeon_move_embed,
    dungeon_retreat_embed,
    error_embed,
    floor_complete_embed,
    scenario_embed,
    success_embed,
)


# ── Helpers ────────────────────────────────────────────────────────

def _count_passable(floor_data: dict) -> int:
    """Count total passable tiles on a floor."""
    count = 0
    for row in floor_data["tiles"]:
        for tile in row:
            if tile != "wall":
                count += 1
    return count


async def _handle_death(player: dict):
    """Process player death: clear inventory, restore resources, end session."""
    items_lost = await clear_non_equipped_inventory(player["id"])
    await update_player(
        str(player["discord_id"]),
        hp=player["max_hp"],
        mana=player["max_mana"],
        sp=player["max_sp"],
        in_dungeon=0,
    )
    await delete_dungeon_session(player["id"])
    return items_lost


async def _start_dungeon_combat(player, session, floor_data, interaction,
                                is_button=False, hp_penalty=0):
    """Spawn enemies and start combat from a dungeon tile."""
    level = get_encounter_level(session["floor"])
    enemies = spawn_enemies(level)
    enemies_json = json.dumps(enemies)
    await create_combat_session(player["id"], enemies_json)

    # Build combat embed using the combat cog's infrastructure
    combat_cog = interaction.client.get_cog("Combat")
    if combat_cog:
        # Re-fetch fresh session
        from src.db.models import get_combat_session as _gcs
        csess = await _gcs(player["id"])
        from src.game.combat import parse_state, get_max_actions
        state = parse_state(csess)
        ma, mb, mi = get_max_actions(player)

        from src.utils.embeds import combat_embed
        embed = combat_embed(player, csess, enemies, [], ma, mb, mi)
        names = ", ".join(f"{e['name']} (Lv.{e['level']})" for e in enemies)
        if hp_penalty:
            embed.description = f"Ambush! You took {hp_penalty} damage!\nYou encounter {names}!"
        else:
            embed.description = f"You encounter {names}!"

        view = await combat_cog._build_view(player, state)
        if is_button:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)
    else:
        # Fallback if combat cog isn't loaded
        msg = "Combat triggered! Use `/fight` to begin."
        if is_button:
            await interaction.response.edit_message(content=msg, embed=None, view=None)
        else:
            await interaction.response.send_message(msg)


# ── Movement View ──────────────────────────────────────────────────

class MovementView(discord.ui.View):
    """Direction buttons for dungeon navigation."""

    def __init__(self, player_id: str, valid_moves: dict):
        super().__init__(timeout=300)
        self.player_id = player_id
        self.north_btn.disabled = "north" not in valid_moves
        self.west_btn.disabled = "west" not in valid_moves
        self.east_btn.disabled = "east" not in valid_moves
        self.south_btn.disabled = "south" not in valid_moves

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message(
                "This isn't your dungeon!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="\u2b06 North", style=discord.ButtonStyle.primary, row=0)
    async def north_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Dungeon")
        if cog:
            await cog._handle_move(interaction, "north", is_button=True)

    @discord.ui.button(label="\u2b05 West", style=discord.ButtonStyle.primary, row=1)
    async def west_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Dungeon")
        if cog:
            await cog._handle_move(interaction, "west", is_button=True)

    @discord.ui.button(label="East \u27a1", style=discord.ButtonStyle.primary, row=1)
    async def east_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Dungeon")
        if cog:
            await cog._handle_move(interaction, "east", is_button=True)

    @discord.ui.button(label="\u2b07 South", style=discord.ButtonStyle.primary, row=2)
    async def south_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Dungeon")
        if cog:
            await cog._handle_move(interaction, "south", is_button=True)

    @discord.ui.button(label="Retreat", style=discord.ButtonStyle.secondary, row=2)
    async def retreat_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Dungeon")
        if cog:
            await cog._handle_retreat(interaction, is_button=True)


# ── Cog ────────────────────────────────────────────────────────────

class Dungeon(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Core handlers ────────────────────────────────────────

    async def _handle_move(self, interaction, direction, is_button=False):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            msg = "No character found. Use `/create` first."
            if is_button:
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=error_embed(msg), ephemeral=True)
            return

        dsess = await get_dungeon_session(player["id"])
        if not dsess:
            msg = "You're not in a dungeon. Use `/enter` first."
            if is_button:
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=error_embed(msg), ephemeral=True)
            return

        # Block movement during combat
        csess = await get_combat_session(player["id"])
        if csess:
            msg = "Finish your combat first!"
            if is_button:
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=error_embed(msg), ephemeral=True)
            return

        floor_data = load_floor(dsess["floor"])
        if not floor_data:
            await interaction.response.send_message(
                embed=error_embed("Floor data not found!"), ephemeral=True)
            return

        cur_row, cur_col = dsess["position_x"], dsess["position_y"]
        valid = get_valid_moves(floor_data, cur_row, cur_col)

        if direction not in valid:
            msg = "You can't go that way!"
            if is_button:
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.response.send_message(
                    embed=error_embed(msg), ephemeral=True)
            return

        new_row, new_col = valid[direction]
        tile_type = get_tile(floor_data, new_row, new_col)

        # Apply resource regen
        regen_updates = apply_regen(player)
        if regen_updates:
            await update_player(discord_id, **regen_updates)
            for k, v in regen_updates.items():
                player[k] = v
        regen_msg = regen_message(regen_updates)

        # Update position
        visited = json.loads(dsess["visited_tiles"])
        first_visit = [new_row, new_col] not in visited
        if first_visit:
            visited.append([new_row, new_col])

        active_effects = json.loads(dsess["active_effects"])

        await update_dungeon_session(
            player["id"],
            position_x=new_row,
            position_y=new_col,
            visited_tiles=json.dumps(visited),
        )

        # --- Resolve tile events on first visit ---
        if not first_visit:
            # Already visited -- just show map
            map_str = render_map(floor_data, visited, (new_row, new_col))
            embed = dungeon_move_embed(
                player, dsess["floor"], map_str,
                f"Moved {direction}. (Already explored)", regen_msg,
            )
            new_valid = get_valid_moves(floor_data, new_row, new_col)
            view = MovementView(discord_id, new_valid)
            if is_button:
                await interaction.response.edit_message(embed=embed, view=view)
            else:
                await interaction.response.send_message(embed=embed, view=view)
            return

        # --- Exit tile ---
        if tile_type == "exit":
            new_floor = dsess["floor"] + 1
            await update_player(discord_id, current_floor=new_floor, in_dungeon=0)
            await delete_dungeon_session(player["id"])
            embed = floor_complete_embed(
                player["character_name"], dsess["floor"], len(visited))
            if is_button:
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.response.send_message(embed=embed)
            return

        # --- Combat tile ---
        if tile_type == "combat":
            await _start_dungeon_combat(
                player, dsess, floor_data, interaction, is_button=is_button)
            return

        # --- Scenario room ---
        if tile_type == "sr":
            result = resolve_scenario(player, active_effects)
            event = result["event"]
            category = result["category"]

            # Apply player updates
            if result["player_updates"]:
                await update_player(discord_id, **result["player_updates"])
                for k, v in result["player_updates"].items():
                    player[k] = v

            # Apply effect updates (curses/blessings)
            if result["effect_updates"] is not None:
                active_effects = result["effect_updates"]
                await update_dungeon_session(
                    player["id"],
                    active_effects=json.dumps(active_effects),
                )

            # Handle item gains
            for item_id in result["items_gained"]:
                consumables = get_consumables()
                item = next((c for c in consumables if c["id"] == item_id), None)
                if item:
                    await add_inventory_item(
                        player["id"], "consumable", item["id"], item)
                    result["messages"].append(f"Received: {item['name']}")

            # Handle item loss
            if result["items_lost_count"] > 0:
                inv = await get_inventory(player["id"], item_type="consumable")
                if inv:
                    victim = random.choice(inv)
                    idata = json.loads(victim["item_data"])
                    await remove_inventory_item(victim["id"])
                    result["messages"].append(f"Lost: {idata.get('name', 'an item')}")
                else:
                    result["messages"].append("But you had nothing to steal!")

            # Handle XP gain
            if result["xp"] > 0:
                await grant_xp(discord_id, result["xp"])

            # Handle death
            if result["death"]:
                items_lost = await _handle_death(player)
                s_embed = scenario_embed(event, category, result["messages"])
                d_embed = dungeon_death_embed(items_lost)
                if is_button:
                    await interaction.response.edit_message(embed=s_embed, view=None)
                    await interaction.followup.send(embed=d_embed)
                else:
                    await interaction.response.send_message(embeds=[s_embed, d_embed])
                return

            # Handle combat from scenario (ambush)
            if result["combat"]:
                # Send scenario embed first, then start combat
                s_embed = scenario_embed(event, category, result["messages"])
                if is_button:
                    await interaction.response.edit_message(embed=s_embed, view=None)
                    # Start combat as followup
                    await _start_dungeon_combat_followup(
                        player, dsess, floor_data, interaction,
                        hp_penalty=result["combat_hp_penalty"])
                else:
                    await interaction.response.send_message(embed=s_embed)
                    await _start_dungeon_combat_followup(
                        player, dsess, floor_data, interaction,
                        hp_penalty=result["combat_hp_penalty"])
                return

            # Normal scenario -- show result + map
            s_embed = scenario_embed(event, category, result["messages"])
            map_str = render_map(floor_data, visited, (new_row, new_col))
            m_embed = dungeon_move_embed(
                player, dsess["floor"], map_str, f"Moved {direction}.", regen_msg)
            new_valid = get_valid_moves(floor_data, new_row, new_col)
            view = MovementView(discord_id, new_valid)
            if is_button:
                await interaction.response.edit_message(embed=s_embed, view=view)
            else:
                await interaction.response.send_message(embeds=[s_embed, m_embed], view=view)
            return

        # --- Path tile ---
        if tile_type in ("path", "start"):
            triggered = tile_type == "path" and roll_path_encounter(player)
            if triggered:
                await _start_dungeon_combat(
                    player, dsess, floor_data, interaction, is_button=is_button)
                return

        # --- Safe passage ---
        map_str = render_map(floor_data, visited, (new_row, new_col))
        embed = dungeon_move_embed(
            player, dsess["floor"], map_str,
            f"Moved {direction}.", regen_msg,
        )
        new_valid = get_valid_moves(floor_data, new_row, new_col)
        view = MovementView(discord_id, new_valid)
        if is_button:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    async def _handle_retreat(self, interaction, is_button=False):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)
            return

        dsess = await get_dungeon_session(player["id"])
        if not dsess:
            await interaction.response.send_message(
                embed=error_embed("You're not in a dungeon."), ephemeral=True)
            return

        csess = await get_combat_session(player["id"])
        if csess:
            await interaction.response.send_message(
                embed=error_embed("Finish your combat first!"), ephemeral=True)
            return

        await update_player(discord_id, in_dungeon=0)
        await delete_dungeon_session(player["id"])
        embed = dungeon_retreat_embed(player["character_name"])
        if is_button:
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            await interaction.response.send_message(embed=embed)

    # ── Slash Commands ───────────────────────────────────────

    @app_commands.command(name="enter", description="Enter the dungeon")
    async def enter(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found. Use `/create` first."),
                ephemeral=True)

        # Block if in combat
        csess = await get_combat_session(player["id"])
        if csess:
            return await interaction.response.send_message(
                embed=error_embed("Finish your combat first!"), ephemeral=True)

        dsess = await get_dungeon_session(player["id"])
        floor_num = player["current_floor"] or 1

        if dsess:
            # Resume existing session
            floor_data = load_floor(dsess["floor"])
            if not floor_data:
                return await interaction.response.send_message(
                    embed=error_embed("Floor data not found!"), ephemeral=True)

            visited = json.loads(dsess["visited_tiles"])
            pos = (dsess["position_x"], dsess["position_y"])
            map_str = render_map(floor_data, visited, pos)
            embed = dungeon_enter_embed(
                player["character_name"], dsess["floor"], map_str, MAP_LEGEND)
            embed.add_field(
                name="Resources",
                value=(
                    f"HP: {player['hp']}/{player['max_hp']} | "
                    f"Mana: {player['mana']}/{player['max_mana']} | "
                    f"SP: {player['sp']}/{player['max_sp']}"
                ),
                inline=False,
            )
            valid = get_valid_moves(floor_data, pos[0], pos[1])
            view = MovementView(discord_id, valid)
            return await interaction.response.send_message(embed=embed, view=view)

        # New session
        floor_data = load_floor(floor_num)
        if not floor_data:
            return await interaction.response.send_message(
                embed=error_embed(
                    f"Floor {floor_num} is not yet available. "
                    "More floors coming soon!"),
                ephemeral=True)

        start = floor_data["start"]
        await create_dungeon_session(player["id"], floor_num, start[0], start[1])
        await update_player(discord_id, in_dungeon=1)

        visited = [start]
        pos = (start[0], start[1])
        map_str = render_map(floor_data, visited, pos)
        embed = dungeon_enter_embed(
            player["character_name"], floor_num, map_str, MAP_LEGEND)
        embed.add_field(
            name="Resources",
            value=(
                f"HP: {player['hp']}/{player['max_hp']} | "
                f"Mana: {player['mana']}/{player['max_mana']} | "
                f"SP: {player['sp']}/{player['max_sp']}"
            ),
            inline=False,
        )
        valid = get_valid_moves(floor_data, pos[0], pos[1])
        view = MovementView(discord_id, valid)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="move", description="Move in a direction")
    @app_commands.describe(direction="Direction to move")
    @app_commands.choices(direction=[
        app_commands.Choice(name="North", value="north"),
        app_commands.Choice(name="South", value="south"),
        app_commands.Choice(name="East", value="east"),
        app_commands.Choice(name="West", value="west"),
    ])
    async def move(self, interaction: discord.Interaction,
                   direction: app_commands.Choice[str]):
        await self._handle_move(interaction, direction.value)

    @app_commands.command(name="map", description="View the dungeon map")
    async def show_map(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        dsess = await get_dungeon_session(player["id"])
        if not dsess:
            return await interaction.response.send_message(
                embed=error_embed("You're not in a dungeon. Use `/enter`."),
                ephemeral=True)

        floor_data = load_floor(dsess["floor"])
        if not floor_data:
            return await interaction.response.send_message(
                embed=error_embed("Floor data not found!"), ephemeral=True)

        visited = json.loads(dsess["visited_tiles"])
        pos = (dsess["position_x"], dsess["position_y"])
        map_str = render_map(floor_data, visited, pos)
        total = _count_passable(floor_data)
        embed = dungeon_map_embed(
            player, dsess["floor"], map_str, MAP_LEGEND, len(visited), total)
        valid = get_valid_moves(floor_data, pos[0], pos[1])
        view = MovementView(discord_id, valid)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="retreat", description="Leave the dungeon")
    async def retreat(self, interaction: discord.Interaction):
        await self._handle_retreat(interaction)

    # ── Admin Commands ───────────────────────────────────────

    @app_commands.command(name="admin_teleport",
                          description="[Admin] Teleport to a tile")
    @app_commands.describe(row="Row (0-indexed)", col="Column (0-indexed)")
    async def admin_teleport(self, interaction: discord.Interaction,
                             row: int, col: int):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character."), ephemeral=True)

        dsess = await get_dungeon_session(player["id"])
        if not dsess:
            return await interaction.response.send_message(
                embed=error_embed("Not in dungeon."), ephemeral=True)

        floor_data = load_floor(dsess["floor"])
        tile = get_tile(floor_data, row, col) if floor_data else None
        if not tile or tile == "wall":
            return await interaction.response.send_message(
                embed=error_embed("Invalid tile."), ephemeral=True)

        visited = json.loads(dsess["visited_tiles"])
        if [row, col] not in visited:
            visited.append([row, col])

        await update_dungeon_session(
            player["id"],
            position_x=row, position_y=col,
            visited_tiles=json.dumps(visited),
        )
        map_str = render_map(floor_data, visited, (row, col))
        embed = dungeon_move_embed(
            player, dsess["floor"], map_str,
            f"Teleported to ({row}, {col}) [{tile}]", "")
        valid = get_valid_moves(floor_data, row, col)
        view = MovementView(discord_id, valid)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="admin_scenario",
                          description="[Admin] Force a scenario type")
    @app_commands.describe(scenario_type="Scenario category")
    @app_commands.choices(scenario_type=[
        app_commands.Choice(name="Negative", value="negative"),
        app_commands.Choice(name="Positive", value="positive"),
        app_commands.Choice(name="Neutral", value="neutral"),
    ])
    async def admin_scenario(self, interaction: discord.Interaction,
                             scenario_type: app_commands.Choice[str]):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character."), ephemeral=True)

        dsess = await get_dungeon_session(player["id"])
        if not dsess:
            return await interaction.response.send_message(
                embed=error_embed("Not in dungeon."), ephemeral=True)

        active_effects = json.loads(dsess["active_effects"])

        from src.game.dungeon import pick_scenario, apply_scenario_effect
        category = scenario_type.value
        event = pick_scenario(category)
        result = apply_scenario_effect(event, category, player, active_effects)

        if result["player_updates"]:
            await update_player(discord_id, **result["player_updates"])
        if result["effect_updates"] is not None:
            await update_dungeon_session(
                player["id"],
                active_effects=json.dumps(result["effect_updates"]))
        if result["xp"] > 0:
            await grant_xp(discord_id, result["xp"])

        embed = scenario_embed(event, category, result["messages"])
        await interaction.response.send_message(embed=embed)


async def _start_dungeon_combat_followup(player, session, floor_data,
                                         interaction, hp_penalty=0):
    """Start combat as a followup message (after scenario embed)."""
    level = get_encounter_level(session["floor"])
    enemies = spawn_enemies(level)
    enemies_json = json.dumps(enemies)
    await create_combat_session(player["id"], enemies_json)

    combat_cog = interaction.client.get_cog("Combat")
    if combat_cog:
        from src.db.models import get_combat_session as _gcs
        csess = await _gcs(player["id"])
        from src.game.combat import parse_state, get_max_actions
        from src.utils.embeds import combat_embed
        state = parse_state(csess)
        ma, mb, mi = get_max_actions(player)
        embed = combat_embed(player, csess, enemies, [], ma, mb, mi)
        names = ", ".join(f"{e['name']} (Lv.{e['level']})" for e in enemies)
        if hp_penalty:
            embed.description = f"Ambush! You took {hp_penalty} damage!\nYou encounter {names}!"
        else:
            embed.description = f"You encounter {names}!"
        view = await combat_cog._build_view(player, state)
        await interaction.followup.send(embed=embed, view=view)
    else:
        await interaction.followup.send("Combat triggered! Use `/fight` to begin.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Dungeon(bot))
