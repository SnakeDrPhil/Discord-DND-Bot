"""Inventory & equipment commands: /inventory, /inspect, /equip, /unequip, /sell, /use_item."""

import json

import discord
from discord import app_commands
from discord.ext import commands

from src.db.models import (
    add_inventory_item,
    count_inventory,
    equip_item,
    get_equipped_in_slot,
    get_equipped_items,
    get_inventory,
    get_player,
    remove_inventory_item,
    unequip_item,
    update_player,
)
from src.game.constants import INVENTORY_CAPACITY
from src.game.items import (
    generate_armor,
    generate_weapon,
    get_sell_price,
)
from src.utils.data_loader import get_armor_by_id, get_weapon_by_id
from src.utils.embeds import (
    equip_embed,
    error_embed,
    inventory_embed,
    item_inspect_embed,
    success_embed,
)


# ── Helpers ─────────────────────────────────────────────────────────

def _parse_item_data(row: dict) -> dict:
    """Parse item_data from a DB row."""
    d = row["item_data"]
    return json.loads(d) if isinstance(d, str) else d


def _find_inventory_item(items: list, name: str):
    """Find an inventory row by item name (case-insensitive)."""
    for item in items:
        idata = _parse_item_data(item)
        if idata.get("name", "").lower() == name.lower():
            return item, idata
    return None, None


# ── Cog ─────────────────────────────────────────────────────────────

class Inventory(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /inventory ──────────────────────────────────────────────

    @app_commands.command(name="inventory", description="View your inventory")
    async def inventory(self, interaction: discord.Interaction):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found. Use `/create` first."), ephemeral=True)

        items = await get_inventory(player["id"])
        embed = inventory_embed(player, items)
        await interaction.response.send_message(embed=embed)

    # ── /inspect ────────────────────────────────────────────────

    @app_commands.command(name="inspect", description="Inspect an item in detail")
    @app_commands.describe(item_name="Item to inspect")
    async def inspect(self, interaction: discord.Interaction, item_name: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        items = await get_inventory(player["id"])
        row, idata = _find_inventory_item(items, item_name)
        if not row:
            return await interaction.response.send_message(
                embed=error_embed(f"Item '{item_name}' not found in inventory."), ephemeral=True)

        embed = item_inspect_embed(idata)
        if row.get("equipped"):
            embed.set_author(name=f"Equipped in {row['slot'].replace('_', ' ').title()}")
        await interaction.response.send_message(embed=embed)

    @inspect.autocomplete("item_name")
    async def inspect_autocomplete(self, interaction: discord.Interaction, current: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return []
        items = await get_inventory(player["id"])
        results = []
        for item in items:
            idata = _parse_item_data(item)
            name = idata.get("name", item["item_id"])
            if current.lower() in name.lower():
                results.append(app_commands.Choice(name=name[:100], value=name[:100]))
        return results[:25]

    # ── /equip ──────────────────────────────────────────────────

    @app_commands.command(name="equip", description="Equip a weapon or armor")
    @app_commands.describe(item_name="Item to equip")
    async def equip(self, interaction: discord.Interaction, item_name: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        items = await get_inventory(player["id"])
        row, idata = _find_inventory_item(items, item_name)
        if not row:
            return await interaction.response.send_message(
                embed=error_embed(f"Item '{item_name}' not found."), ephemeral=True)

        if row.get("equipped"):
            return await interaction.response.send_message(
                embed=error_embed("That item is already equipped."), ephemeral=True)

        itype = idata.get("type")
        if itype not in ("weapon", "armor"):
            return await interaction.response.send_message(
                embed=error_embed("Only weapons and armor can be equipped."), ephemeral=True)

        # Armor class restriction
        if itype == "armor":
            allowed = idata.get("allowed_classes", [])
            if allowed and player["class"] not in allowed:
                return await interaction.response.send_message(
                    embed=error_embed(f"Your class cannot wear this armor. Allowed: {', '.join(c.capitalize() for c in allowed)}"),
                    ephemeral=True)

        # Determine target slot
        unequipped_name = None
        if itype == "armor":
            slot = idata.get("slot")
            if not slot:
                return await interaction.response.send_message(
                    embed=error_embed("This armor has no slot defined."), ephemeral=True)
        else:  # weapon
            hand = idata.get("hand_type", "one_hand")
            if hand == "off_hand":
                # Check main_hand has a one-hand weapon
                main = await get_equipped_in_slot(player["id"], "main_hand")
                if main:
                    mdata = _parse_item_data(main)
                    if mdata.get("hand_type") == "two_hand":
                        return await interaction.response.send_message(
                            embed=error_embed("Cannot equip off-hand with a two-hand weapon."), ephemeral=True)
                slot = "off_hand"
            else:
                slot = "main_hand"

        # Unequip existing item in target slot
        existing = await get_equipped_in_slot(player["id"], slot)
        if existing:
            edata = _parse_item_data(existing)
            unequipped_name = edata.get("name", "Unknown")
            await unequip_item(existing["id"])

        # Two-hand: also clear off_hand
        if itype == "weapon" and idata.get("hand_type") == "two_hand":
            off = await get_equipped_in_slot(player["id"], "off_hand")
            if off:
                odata = _parse_item_data(off)
                if unequipped_name:
                    unequipped_name += f" and {odata.get('name', 'Unknown')}"
                else:
                    unequipped_name = odata.get("name", "Unknown")
                await unequip_item(off["id"])

        await equip_item(row["id"], slot)
        embed = equip_embed(idata.get("name", "Unknown"), slot, unequipped_name)
        await interaction.response.send_message(embed=embed)

    @equip.autocomplete("item_name")
    async def equip_autocomplete(self, interaction: discord.Interaction, current: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return []
        items = await get_inventory(player["id"])
        results = []
        for item in items:
            if item.get("equipped"):
                continue
            idata = _parse_item_data(item)
            if idata.get("type") not in ("weapon", "armor"):
                continue
            name = idata.get("name", item["item_id"])
            if current.lower() in name.lower():
                results.append(app_commands.Choice(name=name[:100], value=name[:100]))
        return results[:25]

    # ── /unequip ────────────────────────────────────────────────

    @app_commands.command(name="unequip", description="Remove equipment from a slot")
    @app_commands.describe(slot="Equipment slot to unequip")
    @app_commands.choices(slot=[
        app_commands.Choice(name="Head", value="head"),
        app_commands.Choice(name="Shoulders", value="shoulders"),
        app_commands.Choice(name="Chest", value="chest"),
        app_commands.Choice(name="Gloves", value="gloves"),
        app_commands.Choice(name="Legs", value="legs"),
        app_commands.Choice(name="Feet", value="feet"),
        app_commands.Choice(name="Main Hand", value="main_hand"),
        app_commands.Choice(name="Off Hand", value="off_hand"),
    ])
    async def unequip(self, interaction: discord.Interaction, slot: app_commands.Choice[str]):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        existing = await get_equipped_in_slot(player["id"], slot.value)
        if not existing:
            return await interaction.response.send_message(
                embed=error_embed(f"Nothing equipped in {slot.name}."), ephemeral=True)

        edata = _parse_item_data(existing)
        await unequip_item(existing["id"])
        await interaction.response.send_message(
            embed=success_embed("Unequipped", f"Removed **{edata.get('name', 'Unknown')}** from {slot.name}."))

    # ── /sell ───────────────────────────────────────────────────

    @app_commands.command(name="sell", description="Sell an item for gold")
    @app_commands.describe(item_name="Item to sell")
    async def sell(self, interaction: discord.Interaction, item_name: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        items = await get_inventory(player["id"])
        row, idata = _find_inventory_item(items, item_name)
        if not row:
            return await interaction.response.send_message(
                embed=error_embed(f"Item '{item_name}' not found."), ephemeral=True)

        if row.get("equipped"):
            return await interaction.response.send_message(
                embed=error_embed("Unequip the item before selling it."), ephemeral=True)

        price = get_sell_price(idata)
        await remove_inventory_item(row["id"])
        new_gold = player["gold"] + price
        await update_player(str(interaction.user.id), gold=new_gold)

        await interaction.response.send_message(
            embed=success_embed("Item Sold", f"Sold **{idata.get('name', 'Unknown')}** for **{price}** gold.\nGold: {new_gold}"))

    @sell.autocomplete("item_name")
    async def sell_autocomplete(self, interaction: discord.Interaction, current: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return []
        items = await get_inventory(player["id"])
        results = []
        for item in items:
            if item.get("equipped"):
                continue
            idata = _parse_item_data(item)
            name = idata.get("name", item["item_id"])
            if current.lower() in name.lower():
                results.append(app_commands.Choice(name=name[:100], value=name[:100]))
        return results[:25]

    # ── /use_item (outside combat) ──────────────────────────────

    @app_commands.command(name="use_item", description="Use a consumable item")
    @app_commands.describe(item_name="Consumable to use")
    async def use_item(self, interaction: discord.Interaction, item_name: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        # Check not in combat
        from src.db.models import get_combat_session
        session = await get_combat_session(player["id"])
        if session:
            return await interaction.response.send_message(
                embed=error_embed("Use `/item` during combat instead."), ephemeral=True)

        items = await get_inventory(player["id"])
        row, idata = _find_inventory_item(items, item_name)
        if not row:
            return await interaction.response.send_message(
                embed=error_embed(f"Item '{item_name}' not found."), ephemeral=True)

        if row.get("item_type") != "consumable" and not idata.get("category"):
            return await interaction.response.send_message(
                embed=error_embed("Only consumables can be used."), ephemeral=True)

        # Apply consumable effect
        updates = {}
        messages = []
        effect = idata.get("effect_type", idata.get("category", ""))
        value = idata.get("value", 0)

        if effect in ("heal", "healing"):
            healed = min(value, player["max_hp"] - player["hp"])
            if healed > 0:
                updates["hp"] = player["hp"] + healed
                messages.append(f"Restored **{healed}** HP.")
            else:
                messages.append("HP is already full.")
        elif effect in ("mana", "mana_restore"):
            restored = min(value, player["max_mana"] - player["mana"])
            if restored > 0:
                updates["mana"] = player["mana"] + restored
                messages.append(f"Restored **{restored}** Mana.")
            else:
                messages.append("Mana is already full.")
        elif effect in ("sp", "sp_restore", "stamina"):
            restored = min(value, player["max_sp"] - player["sp"])
            if restored > 0:
                updates["sp"] = player["sp"] + restored
                messages.append(f"Restored **{restored}** SP.")
            else:
                messages.append("SP is already full.")
        else:
            messages.append(f"Used **{idata.get('name', 'Unknown')}**.")

        # Remove consumed item
        await remove_inventory_item(row["id"])
        if updates:
            await update_player(str(interaction.user.id), **updates)

        await interaction.response.send_message(
            embed=success_embed(f"Used {idata.get('name', 'Item')}", "\n".join(messages)))

    @use_item.autocomplete("item_name")
    async def use_item_autocomplete(self, interaction: discord.Interaction, current: str):
        player = await get_player(str(interaction.user.id))
        if not player:
            return []
        items = await get_inventory(player["id"])
        results = []
        for item in items:
            if item.get("item_type") != "consumable":
                idata = _parse_item_data(item)
                if not idata.get("category"):
                    continue
            idata = _parse_item_data(item)
            name = idata.get("name", item["item_id"])
            if current.lower() in name.lower():
                results.append(app_commands.Choice(name=name[:100], value=name[:100]))
        return results[:25]

    # ── Admin Commands ──────────────────────────────────────────

    @app_commands.command(name="admin_give_weapon", description="[Admin] Give a weapon at a specific rarity")
    @app_commands.describe(weapon_id="Base weapon ID", rarity="Rarity tier")
    @app_commands.choices(rarity=[
        app_commands.Choice(name=r.capitalize(), value=r)
        for r in ["poor", "common", "uncommon", "rare", "epic", "legendary"]
    ])
    async def admin_give_weapon(self, interaction: discord.Interaction,
                                weapon_id: str, rarity: app_commands.Choice[str]):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        base = get_weapon_by_id(weapon_id)
        if not base:
            return await interaction.response.send_message(
                embed=error_embed(f"Unknown weapon ID: {weapon_id}"), ephemeral=True)

        cnt = await count_inventory(player["id"])
        if cnt >= INVENTORY_CAPACITY:
            return await interaction.response.send_message(
                embed=error_embed("Inventory full!"), ephemeral=True)

        floor = player.get("current_floor", 1) or 1
        item = generate_weapon(base, rarity.value, floor)
        await add_inventory_item(player["id"], "weapon", base["id"], item)
        embed = item_inspect_embed(item)
        embed.set_author(name="Weapon Added")
        await interaction.response.send_message(embed=embed)

    @admin_give_weapon.autocomplete("weapon_id")
    async def weapon_id_autocomplete(self, interaction: discord.Interaction, current: str):
        from src.utils.data_loader import get_weapons
        weapons = get_weapons()
        results = []
        for w in weapons:
            if current.lower() in w["id"].lower() or current.lower() in w["name"].lower():
                results.append(app_commands.Choice(name=f"{w['name']} ({w['id']})"[:100], value=w["id"]))
        return results[:25]

    @app_commands.command(name="admin_give_armor", description="[Admin] Give armor at a specific rarity")
    @app_commands.describe(armor_id="Base armor ID", rarity="Rarity tier")
    @app_commands.choices(rarity=[
        app_commands.Choice(name=r.capitalize(), value=r)
        for r in ["poor", "common", "uncommon", "rare", "epic", "legendary"]
    ])
    async def admin_give_armor(self, interaction: discord.Interaction,
                               armor_id: str, rarity: app_commands.Choice[str]):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        base = get_armor_by_id(armor_id)
        if not base:
            return await interaction.response.send_message(
                embed=error_embed(f"Unknown armor ID: {armor_id}"), ephemeral=True)

        cnt = await count_inventory(player["id"])
        if cnt >= INVENTORY_CAPACITY:
            return await interaction.response.send_message(
                embed=error_embed("Inventory full!"), ephemeral=True)

        floor = player.get("current_floor", 1) or 1
        item = generate_armor(base, rarity.value, floor)
        await add_inventory_item(player["id"], "armor", base["id"], item)
        embed = item_inspect_embed(item)
        embed.set_author(name="Armor Added")
        await interaction.response.send_message(embed=embed)

    @admin_give_armor.autocomplete("armor_id")
    async def armor_id_autocomplete(self, interaction: discord.Interaction, current: str):
        from src.utils.data_loader import get_armor
        armor_list = get_armor()
        results = []
        for a in armor_list:
            if current.lower() in a["id"].lower() or current.lower() in a["name"].lower():
                results.append(app_commands.Choice(name=f"{a['name']} ({a['id']})"[:100], value=a["id"]))
        return results[:25]


async def setup(bot: commands.Bot):
    await bot.add_cog(Inventory(bot))
