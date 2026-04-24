"""Shop commands: /shop, /buy, /sell_all."""

import json
import logging

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("dungeon_bot.shop")

from src.db.models import (
    add_inventory_item,
    count_inventory,
    get_inventory,
    get_player,
    remove_inventory_item,
    update_player,
)
from src.game.constants import INVENTORY_CAPACITY, SHOP_PRICES
from src.game.items import get_sell_price
from src.utils.data_loader import get_consumables
from src.utils.embeds import error_embed, shop_embed, success_embed


class Shop(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Browse the shop")
    async def shop(self, interaction: discord.Interaction):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found. Use `/create` first."),
                ephemeral=True)

        if player.get("in_dungeon"):
            return await interaction.response.send_message(
                embed=error_embed("You can't shop while in the dungeon. Use `/retreat` first."),
                ephemeral=True)

        consumables = get_consumables()
        items = []
        for c in consumables:
            price = SHOP_PRICES.get(c["id"])
            if price is None:
                continue
            items.append({
                "id": c["id"],
                "name": c["name"],
                "effect": c.get("effect", ""),
                "price": price,
            })
        items.sort(key=lambda x: x["price"])
        embed = shop_embed(items, player["gold"])
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="buy", description="Buy an item from the shop")
    @app_commands.describe(item_name="Item to buy", quantity="How many to buy")
    async def buy(self, interaction: discord.Interaction, item_name: str,
                  quantity: int = 1):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        if player.get("in_dungeon"):
            return await interaction.response.send_message(
                embed=error_embed("You can't shop while in the dungeon."),
                ephemeral=True)

        if quantity < 1:
            return await interaction.response.send_message(
                embed=error_embed("Quantity must be at least 1."), ephemeral=True)

        # Find the consumable
        consumables = get_consumables()
        item = None
        for c in consumables:
            if c["name"].lower() == item_name.lower() or c["id"] == item_name.lower():
                item = c
                break
        if not item:
            return await interaction.response.send_message(
                embed=error_embed(f"Item '{item_name}' not found in the shop."),
                ephemeral=True)

        price = SHOP_PRICES.get(item["id"])
        if price is None:
            return await interaction.response.send_message(
                embed=error_embed("That item is not for sale."), ephemeral=True)

        total_cost = price * quantity
        if player["gold"] < total_cost:
            return await interaction.response.send_message(
                embed=error_embed(
                    f"Not enough gold! Need {total_cost}g, have {player['gold']}g."),
                ephemeral=True)

        inv_count = await count_inventory(player["id"])
        if inv_count + quantity > INVENTORY_CAPACITY:
            space = INVENTORY_CAPACITY - inv_count
            return await interaction.response.send_message(
                embed=error_embed(
                    f"Not enough inventory space! Have {space} slot(s) free."),
                ephemeral=True)

        # Process purchase
        for _ in range(quantity):
            await add_inventory_item(player["id"], "consumable", item["id"], item)
        new_gold = player["gold"] - total_cost
        await update_player(str(interaction.user.id), gold=new_gold)

        logger.info("Purchase: player=%s item=%s qty=%d cost=%d",
                     player["character_name"], item["name"], quantity, total_cost)
        qty_text = f" x{quantity}" if quantity > 1 else ""
        await interaction.response.send_message(
            embed=success_embed(
                "Purchase Complete",
                f"Bought **{item['name']}{qty_text}** for **{total_cost}**g.\n"
                f"Gold remaining: {new_gold}"))

    @buy.autocomplete("item_name")
    async def buy_autocomplete(self, interaction: discord.Interaction,
                               current: str):
        consumables = get_consumables()
        results = []
        for c in consumables:
            if c["id"] not in SHOP_PRICES:
                continue
            name = c["name"]
            price = SHOP_PRICES[c["id"]]
            if current.lower() in name.lower():
                results.append(app_commands.Choice(
                    name=f"{name} ({price}g)"[:100], value=name))
        return results[:25]

    @app_commands.command(name="sell_all",
                          description="Sell all unequipped items for gold")
    async def sell_all(self, interaction: discord.Interaction):
        player = await get_player(str(interaction.user.id))
        if not player:
            return await interaction.response.send_message(
                embed=error_embed("No character found."), ephemeral=True)

        items = await get_inventory(player["id"])
        total_gold = 0
        sold_count = 0
        for item in items:
            if item.get("equipped"):
                continue
            idata = json.loads(item["item_data"]) if isinstance(
                item["item_data"], str) else item["item_data"]
            total_gold += get_sell_price(idata)
            await remove_inventory_item(item["id"])
            sold_count += 1

        if sold_count == 0:
            return await interaction.response.send_message(
                embed=error_embed("No unequipped items to sell."),
                ephemeral=True)

        new_gold = player["gold"] + total_gold
        await update_player(str(interaction.user.id), gold=new_gold)
        await interaction.response.send_message(
            embed=success_embed(
                "Items Sold",
                f"Sold **{sold_count}** item(s) for **{total_gold}**g.\n"
                f"Gold: {new_gold}"))


async def setup(bot: commands.Bot):
    await bot.add_cog(Shop(bot))
