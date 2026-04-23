"""CRUD operations for game entities."""

import json
from typing import Optional

from src.db.database import get_db


# --- Players ---

async def create_player(
    discord_id: str, character_name: str, player_class: str,
    stats: dict, hp: int, max_hp: int, mana: int, max_mana: int,
    sp: int, max_sp: int,
) -> int:
    """Create a new player and return the player id."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO players
            (discord_id, character_name, class,
             strength, dexterity, intelligence, agility, wisdom, endurance, charisma,
             hp, max_hp, mana, max_mana, sp, max_sp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                discord_id, character_name, player_class,
                stats["strength"], stats["dexterity"], stats["intelligence"],
                stats["agility"], stats["wisdom"], stats["endurance"], stats["charisma"],
                hp, max_hp, mana, max_mana, sp, max_sp,
            ),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_player(discord_id: str) -> Optional[dict]:
    """Fetch a player by Discord ID. Returns None if not found."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM players WHERE discord_id = ?", (discord_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)
    finally:
        await db.close()


async def update_player(discord_id: str, **fields) -> None:
    """Update one or more fields on a player row."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [discord_id]
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE players SET {set_clause} WHERE discord_id = ?", values
        )
        await db.commit()
    finally:
        await db.close()


async def delete_player(discord_id: str) -> None:
    """Delete a player and all related data (cascades)."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM players WHERE discord_id = ?", (discord_id,))
        await db.commit()
    finally:
        await db.close()


# --- Inventory ---

async def add_inventory_item(
    player_id: int, item_type: str, item_id: str,
    item_data: dict, quantity: int = 1,
) -> int:
    """Add an item to a player's inventory."""
    db = await get_db()
    try:
        cursor = await db.execute(
            """INSERT INTO inventories (player_id, item_type, item_id, item_data, quantity)
            VALUES (?, ?, ?, ?, ?)""",
            (player_id, item_type, item_id, json.dumps(item_data), quantity),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_inventory(player_id: int, item_type: str = None) -> list:
    """Get all inventory items for a player, optionally filtered by type."""
    db = await get_db()
    try:
        if item_type:
            cursor = await db.execute(
                "SELECT * FROM inventories WHERE player_id = ? AND item_type = ?",
                (player_id, item_type),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM inventories WHERE player_id = ?", (player_id,)
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def equip_item(inventory_id: int, slot: str) -> None:
    """Mark an inventory item as equipped in a slot."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE inventories SET equipped = 1, slot = ? WHERE id = ?",
            (slot, inventory_id),
        )
        await db.commit()
    finally:
        await db.close()


async def unequip_item(inventory_id: int) -> None:
    """Unequip an inventory item."""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE inventories SET equipped = 0, slot = NULL WHERE id = ?",
            (inventory_id,),
        )
        await db.commit()
    finally:
        await db.close()


async def remove_inventory_item(inventory_id: int) -> None:
    """Remove an item from inventory."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM inventories WHERE id = ?", (inventory_id,))
        await db.commit()
    finally:
        await db.close()
