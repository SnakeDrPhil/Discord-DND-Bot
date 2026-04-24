"""Combat commands: /fight, /attack, /use, /item, /flee with interactive buttons."""

import json
import random

import discord
from discord import app_commands
from discord.ext import commands

from src.db.models import (
    add_inventory_item,
    create_combat_session,
    delete_combat_session,
    get_combat_session,
    get_inventory,
    get_player,
    remove_inventory_item,
    update_combat_session,
    update_player,
)
from src.game.combat import (
    calculate_rewards,
    check_combat_end,
    get_action_slot,
    get_max_actions,
    is_stunned,
    parse_state,
    process_basic_attack,
    process_enemy_turns,
    process_flee,
    process_item,
    process_skill,
    process_turn_start,
    serialize_state,
    should_auto_end_turn,
    spawn_enemies,
)
from src.game.leveling import grant_xp
from src.utils.data_loader import get_consumables, get_skill_by_id, get_skills
from src.utils.embeds import (
    combat_defeat_embed,
    combat_embed,
    combat_flee_embed,
    combat_victory_embed,
    error_embed,
)


# ── Helpers ─────────────────────────────────────────────────────────

async def _get_combat_context(discord_id: str):
    """Fetch player and combat session. Returns (player, session) or (player, None)."""
    player = await get_player(discord_id)
    if not player:
        return None, None
    session = await get_combat_session(player["id"])
    return player, session


async def _save_and_build(player, session, state, player_updates, msgs):
    """Persist state and build the updated embed + view. Returns (embed, view, result)."""
    # Save player updates
    if player_updates:
        await update_player(str(player["discord_id"]), **player_updates)
        for k, v in player_updates.items():
            player[k] = v

    # Check combat end before auto-ending turn
    result = check_combat_end(player["hp"], state["enemies"])
    if result != "ongoing":
        await _finish_combat(player, state, result)
        return None, None, result

    # Check auto end turn
    if should_auto_end_turn(player, state):
        state, eu, emsg = process_enemy_turns(player, state)
        msgs.extend(emsg)
        if eu:
            await update_player(str(player["discord_id"]), **eu)
            for k, v in eu.items():
                player[k] = v
        result = check_combat_end(player["hp"], state["enemies"])
        if result != "ongoing":
            await _finish_combat(player, state, result)
            return None, None, result
        # Start of new turn
        tu, tmsg = process_turn_start(player, state)
        msgs.extend(tmsg)
        if tu:
            await update_player(str(player["discord_id"]), **tu)
            for k, v in tu.items():
                player[k] = v
        result = check_combat_end(player["hp"], state["enemies"])
        if result != "ongoing":
            await _finish_combat(player, state, result)
            return None, None, result

    # Serialize and save combat state
    serialized = serialize_state(state)
    await update_combat_session(player["id"], **serialized)

    # Rebuild session dict for embed
    session_for_embed = dict(session)
    session_for_embed.update(serialized)

    ma, mb, mi = get_max_actions(player)
    al = max(0, ma - state["attacks_used"])
    bl = max(0, mb - state["buffs_used"])
    il = max(0, mi - state["items_used"])

    embed = combat_embed(player, session_for_embed, state["enemies"],
                         state["combat_log"], al, bl, il)
    # Append action messages to embed
    if msgs:
        action_text = "\n".join(f"- {m}" for m in msgs[-8:])
        embed.add_field(name="Last Action", value=action_text, inline=False)

    view = CombatView(str(player["discord_id"]), al > 0, bl > 0 or il > 0)
    return embed, view, "ongoing"


async def _finish_combat(player, state, result):
    """Clean up combat session on victory/defeat/flee."""
    await delete_combat_session(player["id"])


async def _send_result(interaction, player, state, result, flee_damage=0, is_button=False):
    """Send the combat result embed."""
    if result == "victory":
        rewards = calculate_rewards(state["enemies"], state["damage_taken"])
        updated_player, events = await grant_xp(str(player["discord_id"]), rewards["xp"])
        if rewards["gold"] > 0:
            await update_player(str(player["discord_id"]),
                                gold=player["gold"] + rewards["gold"])
        # Add usable loot to inventory
        for item in rewards["loot"]:
            if item.get("type") == "usable":
                await add_inventory_item(player["id"], "consumable", item["id"], item)
        embed = combat_victory_embed(
            player["character_name"], rewards["xp"], rewards["perfect"],
            rewards["gold"], rewards["loot"], events,
        )
    elif result == "defeat":
        await update_player(str(player["discord_id"]),
                            hp=player["max_hp"], mana=player["max_mana"],
                            sp=player["max_sp"])
        embed = combat_defeat_embed()
    else:  # fled
        embed = combat_flee_embed(flee_damage > 0, flee_damage)

    if is_button:
        await interaction.response.edit_message(embed=embed, view=None)
    else:
        await interaction.response.send_message(embed=embed)


# ── Combat View ─────────────────────────────────────────────────────

class SkillSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Use a skill...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Combat")
        if cog:
            await cog._handle_skill(interaction, self.values[0], is_button=True)


class ItemSelect(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="Use an item...", options=options, row=3)

    async def callback(self, interaction: discord.Interaction):
        cog = interaction.client.get_cog("Combat")
        if cog:
            await cog._handle_item(interaction, self.values[0], is_button=True)


class CombatView(discord.ui.View):
    def __init__(self, player_id: str, attacks_available: bool, skills_available: bool):
        super().__init__(timeout=300)
        self.player_id = player_id
        self.slash_btn.disabled = not attacks_available
        self.thrust_btn.disabled = not attacks_available

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != self.player_id:
            await interaction.response.send_message(
                "This isn't your combat!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Slash", style=discord.ButtonStyle.danger, row=0)
    async def slash_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Combat")
        if cog:
            await cog._handle_attack(interaction, "slash", is_button=True)

    @discord.ui.button(label="Thrust", style=discord.ButtonStyle.danger, row=0)
    async def thrust_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Combat")
        if cog:
            await cog._handle_attack(interaction, "thrust", is_button=True)

    @discord.ui.button(label="End Turn", style=discord.ButtonStyle.secondary, row=0)
    async def end_turn_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Combat")
        if cog:
            await cog._handle_end_turn(interaction, is_button=True)

    @discord.ui.button(label="Flee", style=discord.ButtonStyle.secondary, row=2)
    async def flee_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("Combat")
        if cog:
            await cog._handle_flee(interaction, is_button=True)


# ── Cog ─────────────────────────────────────────────────────────────

class Combat(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _build_view(self, player, state):
        """Build a CombatView with skill/item selects populated."""
        ma, mb, mi = get_max_actions(player)
        al = max(0, ma - state["attacks_used"])
        bl = max(0, mb - state["buffs_used"])
        il = max(0, mi - state["items_used"])

        view = CombatView(str(player["discord_id"]), al > 0, bl > 0 or il > 0)

        # Add skill select
        learned = json.loads(player["learned_skills"])
        if learned:
            options = []
            for sid in learned:
                sk = get_skill_by_id(sid)
                if sk:
                    slot = get_action_slot(sk)
                    avail = (slot == "attack" and al > 0) or (slot == "buff" and bl > 0)
                    label = f"{sk['name']} ({sk['cost']} {sk['resource'].upper()})"
                    if not avail:
                        label += " [used]"
                    options.append(discord.SelectOption(
                        label=label[:100], value=sk["id"],
                        description=sk["effect"][:100] if sk.get("effect") else None,
                    ))
            if options:
                view.add_item(SkillSelect(options[:25]))

        # Add item select
        inv = await get_inventory(player["id"], item_type="consumable")
        if inv and il > 0:
            options = []
            for item in inv:
                idata = json.loads(item["item_data"])
                options.append(discord.SelectOption(
                    label=idata.get("name", item["item_id"])[:100],
                    value=str(item["id"]),
                    description=idata.get("effect", "")[:100] if idata.get("effect") else None,
                ))
            if options:
                view.add_item(ItemSelect(options[:25]))

        return view

    # ── Core action handlers ────────────────────────────────────

    async def _handle_attack(self, interaction, atype, is_button=False):
        player, session = await _get_combat_context(str(interaction.user.id))
        if not player or not session:
            msg = "You're not in combat!" if player else "No character found."
            if is_button:
                await interaction.response.edit_message(content=msg, embed=None, view=None)
            else:
                await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
            return

        state = parse_state(session)
        if is_stunned(state["player_debuffs"]):
            msg = "You are stunned and cannot act!"
            if is_button:
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
            return

        ma, _, _ = get_max_actions(player)
        if state["attacks_used"] >= ma:
            msg = "No attack actions remaining this turn."
            if is_button:
                await interaction.response.send_message(msg, ephemeral=True)
            else:
                await interaction.response.send_message(embed=error_embed(msg), ephemeral=True)
            return

        state, updates, msgs = process_basic_attack(atype, player, state)
        embed, view, result = await _save_and_build(player, session, state, updates, msgs)

        if result != "ongoing":
            flee_dmg = sum(m.count("damage") for m in msgs)  # rough
            await _send_result(interaction, player, state, result, is_button=is_button)
            return

        # Rebuild view with updated state
        view = await self._build_view(player, state)
        if is_button:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    async def _handle_skill(self, interaction, skill_id, is_button=False):
        player, session = await _get_combat_context(str(interaction.user.id))
        if not player or not session:
            await interaction.response.send_message("Not in combat!", ephemeral=True)
            return

        state = parse_state(session)
        if is_stunned(state["player_debuffs"]):
            await interaction.response.send_message("You are stunned!", ephemeral=True)
            return

        skill = get_skill_by_id(skill_id)
        if not skill:
            await interaction.response.send_message("Skill not found!", ephemeral=True)
            return

        learned = json.loads(player["learned_skills"])
        if skill_id not in learned:
            await interaction.response.send_message("You haven't learned that skill!", ephemeral=True)
            return

        slot = get_action_slot(skill)
        ma, mb, _ = get_max_actions(player)
        if slot == "attack" and state["attacks_used"] >= ma:
            await interaction.response.send_message("No attack actions remaining!", ephemeral=True)
            return
        if slot == "buff" and state["buffs_used"] >= mb:
            await interaction.response.send_message("No buff actions remaining!", ephemeral=True)
            return

        state, updates, msgs = process_skill(skill, player, state)

        # Check if Quick Escape fled
        if state.get("_fled"):
            await delete_combat_session(player["id"])
            if updates:
                await update_player(str(player["discord_id"]), **updates)
            embed = combat_flee_embed(False)
            if is_button:
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.response.send_message(embed=embed)
            return

        # Check resource error (not enough SP/mana)
        if not updates and msgs and "Not enough" in msgs[0]:
            await interaction.response.send_message(msgs[0], ephemeral=True)
            return

        embed, view, result = await _save_and_build(player, session, state, updates, msgs)
        if result != "ongoing":
            await _send_result(interaction, player, state, result, is_button=is_button)
            return

        view = await self._build_view(player, state)
        if is_button:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    async def _handle_item(self, interaction, inv_item_id, is_button=False):
        player, session = await _get_combat_context(str(interaction.user.id))
        if not player or not session:
            await interaction.response.send_message("Not in combat!", ephemeral=True)
            return

        state = parse_state(session)
        _, _, mi = get_max_actions(player)
        if state["items_used"] >= mi:
            await interaction.response.send_message("No item actions remaining!", ephemeral=True)
            return

        # Fetch inventory item
        inv = await get_inventory(player["id"], item_type="consumable")
        item_row = None
        for it in inv:
            if str(it["id"]) == str(inv_item_id):
                item_row = it
                break
        if not item_row:
            await interaction.response.send_message("Item not found in inventory!", ephemeral=True)
            return

        item_data = json.loads(item_row["item_data"])
        state, updates, msgs = process_item(item_data, player, state)

        # Remove from inventory
        await remove_inventory_item(item_row["id"])

        embed, view, result = await _save_and_build(player, session, state, updates, msgs)
        if result != "ongoing":
            await _send_result(interaction, player, state, result, is_button=is_button)
            return

        view = await self._build_view(player, state)
        if is_button:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    async def _handle_end_turn(self, interaction, is_button=False):
        player, session = await _get_combat_context(str(interaction.user.id))
        if not player or not session:
            await interaction.response.send_message("Not in combat!", ephemeral=True)
            return

        state = parse_state(session)
        msgs = ["Turn ended."]

        # Process enemy turns
        state, eu, emsg = process_enemy_turns(player, state)
        msgs.extend(emsg)
        if eu:
            await update_player(str(player["discord_id"]), **eu)
            for k, v in eu.items():
                player[k] = v

        result = check_combat_end(player["hp"], state["enemies"])
        if result != "ongoing":
            await delete_combat_session(player["id"])
            await _send_result(interaction, player, state, result, is_button=is_button)
            return

        # Start of new turn
        tu, tmsg = process_turn_start(player, state)
        msgs.extend(tmsg)
        if tu:
            await update_player(str(player["discord_id"]), **tu)
            for k, v in tu.items():
                player[k] = v

        result = check_combat_end(player["hp"], state["enemies"])
        if result != "ongoing":
            await delete_combat_session(player["id"])
            await _send_result(interaction, player, state, result, is_button=is_button)
            return

        serialized = serialize_state(state)
        await update_combat_session(player["id"], **serialized)

        session_for_embed = dict(session)
        session_for_embed.update(serialized)
        ma, mb, mi = get_max_actions(player)
        embed = combat_embed(player, session_for_embed, state["enemies"],
                             state["combat_log"],
                             ma - state["attacks_used"],
                             mb - state["buffs_used"],
                             mi - state["items_used"])
        if msgs:
            embed.add_field(name="Last Action",
                            value="\n".join(f"- {m}" for m in msgs[-8:]), inline=False)

        view = await self._build_view(player, state)
        if is_button:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    async def _handle_flee(self, interaction, is_button=False):
        player, session = await _get_combat_context(str(interaction.user.id))
        if not player or not session:
            await interaction.response.send_message("Not in combat!", ephemeral=True)
            return

        state = parse_state(session)
        state, updates, msgs, success = process_flee(player, state)

        if updates:
            await update_player(str(player["discord_id"]), **updates)
            for k, v in updates.items():
                player[k] = v

        if success:
            await delete_combat_session(player["id"])
            embed = combat_flee_embed(False)
            if is_button:
                await interaction.response.edit_message(embed=embed, view=None)
            else:
                await interaction.response.send_message(embed=embed)
            return

        # Failed flee -- check if player died from free attacks
        result = check_combat_end(player["hp"], state["enemies"])
        if result == "defeat":
            await delete_combat_session(player["id"])
            await _send_result(interaction, player, state, "defeat", is_button=is_button)
            return

        # Process enemy turns after failed flee
        state, eu, emsg = process_enemy_turns(player, state)
        msgs.extend(emsg)
        if eu:
            await update_player(str(player["discord_id"]), **eu)
            for k, v in eu.items():
                player[k] = v

        result = check_combat_end(player["hp"], state["enemies"])
        if result != "ongoing":
            await delete_combat_session(player["id"])
            await _send_result(interaction, player, state, result, is_button=is_button)
            return

        tu, tmsg = process_turn_start(player, state)
        msgs.extend(tmsg)
        if tu:
            await update_player(str(player["discord_id"]), **tu)
            for k, v in tu.items():
                player[k] = v

        serialized = serialize_state(state)
        await update_combat_session(player["id"], **serialized)
        session_for_embed = dict(session)
        session_for_embed.update(serialized)
        ma, mb, mi = get_max_actions(player)
        embed = combat_embed(player, session_for_embed, state["enemies"],
                             state["combat_log"],
                             ma - state["attacks_used"],
                             mb - state["buffs_used"],
                             mi - state["items_used"])
        if msgs:
            embed.add_field(name="Last Action",
                            value="\n".join(f"- {m}" for m in msgs[-8:]), inline=False)

        view = await self._build_view(player, state)
        if is_button:
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed, view=view)

    # ── Slash Commands ──────────────────────────────────────────

    @app_commands.command(name="fight", description="Start a combat encounter")
    async def fight(self, interaction: discord.Interaction):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found. Use `/create` first."), ephemeral=True)

        session = await get_combat_session(player["id"])
        if session:
            # Resume existing combat
            state = parse_state(session)
            ma, mb, mi = get_max_actions(player)
            embed = combat_embed(player, session, state["enemies"],
                                 state["combat_log"],
                                 ma - state["attacks_used"],
                                 mb - state["buffs_used"],
                                 mi - state["items_used"])
            view = await self._build_view(player, state)
            return await interaction.response.send_message(embed=embed, view=view)

        # Spawn enemies
        enemies = spawn_enemies(player["level"])
        enemies_json = json.dumps(enemies)

        await create_combat_session(player["id"], enemies_json)
        session = await get_combat_session(player["id"])
        state = parse_state(session)

        # Combat-start talents
        msgs = []
        updates = {}

        # Faithful Recovery: +20% HP at encounter start
        if "cleric_faithful_recovery" in json.loads(player["selected_talents"]):
            heal = int(player["max_hp"] * 0.20)
            new_hp = min(player["hp"] + heal, player["max_hp"])
            if new_hp != player["hp"]:
                updates["hp"] = new_hp
                player["hp"] = new_hp
                msgs.append(f"Faithful Recovery: +{heal} HP!")

        # Charming Aura: 10% charm at combat start
        if "bard_charming_aura" in json.loads(player["selected_talents"]):
            if random.randint(1, 100) <= 10:
                alive = [e for e in enemies if e["is_alive"]]
                if alive:
                    target = random.choice(alive)
                    from src.game.formulas import calc_main_stat_duration
                    from src.utils.data_loader import get_class
                    cd = get_class(player["class"])
                    dur = calc_main_stat_duration(player[cd["main_stat"]])
                    state["enemy_debuffs"].append({
                        "type": "charm", "remaining_turns": dur,
                        "source": "bard_charming_aura", "enemy_id": target["id"],
                    })
                    msgs.append(f"Charming Aura! {target['name']} is charmed!")

        if updates:
            await update_player(discord_id, **updates)
        if state["enemy_debuffs"]:
            await update_combat_session(player["id"],
                                        enemy_debuffs=json.dumps(state["enemy_debuffs"]))
            session = await get_combat_session(player["id"])

        ma, mb, mi = get_max_actions(player)
        embed = combat_embed(player, session, enemies, [], ma, mb, mi)
        names = ", ".join(f"{e['name']} (Lv.{e['level']})" for e in enemies)
        embed.description = f"You encounter {names}!"
        if msgs:
            embed.add_field(name="Combat Start",
                            value="\n".join(f"- {m}" for m in msgs), inline=False)

        view = await self._build_view(player, state)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="attack", description="Basic attack")
    @app_commands.describe(attack_type="Type of attack")
    @app_commands.choices(attack_type=[
        app_commands.Choice(name="Slash", value="slash"),
        app_commands.Choice(name="Thrust", value="thrust"),
    ])
    async def attack(self, interaction: discord.Interaction,
                     attack_type: app_commands.Choice[str]):
        await self._handle_attack(interaction, attack_type.value)

    @app_commands.command(name="use", description="Use a combat skill")
    @app_commands.describe(skill_name="Skill to use")
    async def use_skill(self, interaction: discord.Interaction, skill_name: str):
        await self._handle_skill(interaction, skill_name)

    @use_skill.autocomplete("skill_name")
    async def use_autocomplete(self, interaction: discord.Interaction, current: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return []
        learned = json.loads(player["learned_skills"])
        results = []
        for sid in learned:
            sk = get_skill_by_id(sid)
            if sk and current.lower() in sk["name"].lower():
                results.append(app_commands.Choice(name=sk["name"], value=sk["id"]))
        return results[:25]

    @app_commands.command(name="item", description="Use a consumable item in combat")
    @app_commands.describe(item_name="Item to use")
    async def use_item(self, interaction: discord.Interaction, item_name: str):
        # Find inventory item by name
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character."), ephemeral=True)
        inv = await get_inventory(player["id"], item_type="consumable")
        for it in inv:
            idata = json.loads(it["item_data"])
            if idata.get("name", "").lower() == item_name.lower() or str(it["id"]) == item_name:
                await self._handle_item(interaction, str(it["id"]))
                return
        await interaction.response.send_message(
            embed=error_embed("Item not found in inventory."), ephemeral=True)

    @use_item.autocomplete("item_name")
    async def item_autocomplete(self, interaction: discord.Interaction, current: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return []
        inv = await get_inventory(player["id"], item_type="consumable")
        results = []
        for it in inv:
            idata = json.loads(it["item_data"])
            name = idata.get("name", it["item_id"])
            if current.lower() in name.lower():
                results.append(app_commands.Choice(name=name, value=str(it["id"])))
        return results[:25]

    @app_commands.command(name="flee", description="Attempt to flee from combat")
    async def flee(self, interaction: discord.Interaction):
        await self._handle_flee(interaction)

    # ── Admin Commands ──────────────────────────────────────────

    @app_commands.command(name="admin_fight", description="[Admin] Fight specific enemies")
    @app_commands.describe(enemy_type="Enemy type (goblin/feral_rat)",
                           level="Enemy level", count="Number of enemies")
    async def admin_fight(self, interaction: discord.Interaction,
                          enemy_type: str, level: int, count: int = 1):
        discord_id = str(interaction.user.id)
        player = await get_player(discord_id)
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character."), ephemeral=True)

        session = await get_combat_session(player["id"])
        if session:
            return await interaction.response.send_message(
                embed=error_embed("Already in combat!"), ephemeral=True)

        from src.utils.data_loader import get_enemies
        enemies = []
        for i in range(min(count, 5)):
            data = get_enemies(enemy_type=enemy_type, level=min(level, 20))
            if not data:
                continue
            t = data[0]
            enemies.append({
                "id": i, "type": t["type"],
                "name": t["type"].replace("_", " ").title(),
                "level": t["level"], "hp": t["hp"], "max_hp": t["hp"],
                "damage_min": t["damage_min"], "damage_max": t["damage_max"],
                "xp_reward": t["xp_reward"], "is_alive": True,
            })

        if not enemies:
            return await interaction.response.send_message(
                embed=error_embed("Invalid enemy type or level."), ephemeral=True)

        await create_combat_session(player["id"], json.dumps(enemies))
        session = await get_combat_session(player["id"])
        state = parse_state(session)
        ma, mb, mi = get_max_actions(player)
        embed = combat_embed(player, session, enemies, [], ma, mb, mi)
        names = ", ".join(f"{e['name']} (Lv.{e['level']})" for e in enemies)
        embed.description = f"Admin fight: {names}!"
        view = await self._build_view(player, state)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="admin_item", description="[Admin] Give yourself a consumable")
    @app_commands.describe(item_id="Consumable item ID (e.g. minor_healing_potion)")
    async def admin_item(self, interaction: discord.Interaction, item_id: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character."), ephemeral=True)

        consumables = get_consumables()
        item = None
        for c in consumables:
            if c["id"] == item_id or c["name"].lower() == item_id.lower():
                item = c
                break
        if not item:
            return await interaction.response.send_message(
                embed=error_embed(f"Unknown consumable: {item_id}"), ephemeral=True)

        await add_inventory_item(player["id"], "consumable", item["id"], item)
        from src.utils.embeds import success_embed
        await interaction.response.send_message(
            embed=success_embed("Item Added", f"Added **{item['name']}** to your inventory."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Combat(bot))
