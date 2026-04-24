"""CRUD operations for game entities."""

import json
import logging
from typing import Optional

from src.db.database import get_db

logger = logging.getLogger("dungeon_bot.db")


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


# --- Combat Sessions ---

async def create_combat_session(player_id: int, enemies: str) -> int:
    """Create a combat session. enemies is a JSON string."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "INSERT INTO combat_sessions (player_id, enemies) VALUES (?, ?)",
            (player_id, enemies),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_combat_session(player_id: int) -> Optional[dict]:
    """Fetch active combat session by player_id."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM combat_sessions WHERE player_id = ?", (player_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_combat_session(player_id: int, **fields) -> None:
    """Update combat session fields."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [player_id]
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE combat_sessions SET {set_clause} WHERE player_id = ?", values
        )
        await db.commit()
    finally:
        await db.close()


async def delete_combat_session(player_id: int) -> None:
    """Delete a combat session (on victory/defeat/flee)."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM combat_sessions WHERE player_id = ?", (player_id,)
        )
        await db.commit()
    finally:
        await db.close()


# --- Dungeon Sessions ---

async def create_dungeon_session(
    player_id: int, floor: int = 1, start_x: int = 0, start_y: int = 0,
) -> int:
    """Create a dungeon session. Returns session ID."""
    db = await get_db()
    try:
        visited = json.dumps([[start_x, start_y]])
        cursor = await db.execute(
            """INSERT INTO dungeon_sessions (player_id, floor, position_x, position_y, visited_tiles)
            VALUES (?, ?, ?, ?, ?)""",
            (player_id, floor, start_x, start_y, visited),
        )
        await db.commit()
        return cursor.lastrowid
    finally:
        await db.close()


async def get_dungeon_session(player_id: int) -> Optional[dict]:
    """Fetch active dungeon session by player_id."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM dungeon_sessions WHERE player_id = ?", (player_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def update_dungeon_session(player_id: int, **fields) -> None:
    """Update dungeon session fields."""
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [player_id]
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE dungeon_sessions SET {set_clause} WHERE player_id = ?", values
        )
        await db.commit()
    finally:
        await db.close()


async def delete_dungeon_session(player_id: int) -> None:
    """Delete a dungeon session (on retreat, death, or floor exit)."""
    db = await get_db()
    try:
        await db.execute(
            "DELETE FROM dungeon_sessions WHERE player_id = ?", (player_id,)
        )
        await db.commit()
    finally:
        await db.close()


async def get_non_equipped_inventory(player_id: int) -> list:
    """Get all non-equipped inventory items for death penalty."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM inventories WHERE player_id = ? AND equipped = 0",
            (player_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def clear_non_equipped_inventory(player_id: int) -> int:
    """Remove all non-equipped items. Returns count deleted."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "DELETE FROM inventories WHERE player_id = ? AND equipped = 0",
            (player_id,),
        )
        await db.commit()
        return cursor.rowcount
    finally:
        await db.close()


# --- Equipment Helpers ---

async def get_equipped_items(player_id: int) -> list:
    """Get all equipped items for a player."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM inventories WHERE player_id = ? AND equipped = 1",
            (player_id,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_equipped_in_slot(player_id: int, slot: str) -> Optional[dict]:
    """Get the item equipped in a specific slot."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM inventories WHERE player_id = ? AND equipped = 1 AND slot = ?",
            (player_id, slot),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def increment_player_stat(discord_id: str, stat: str, amount: int = 1) -> None:
    """Increment a player tracking stat (enemies_killed, bosses_killed)."""
    db = await get_db()
    try:
        await db.execute(
            f"UPDATE players SET {stat} = {stat} + ? WHERE discord_id = ?",
            (amount, discord_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_leaderboard(category: str, limit: int = 10) -> list:
    """Fetch top players for a leaderboard category."""
    order_map = {
        "level": "level DESC, xp DESC",
        "floor": "highest_floor DESC, level DESC",
        "kills": "enemies_killed DESC, level DESC",
    }
    order = order_map.get(category, "level DESC, xp DESC")
    db = await get_db()
    try:
        cursor = await db.execute(
            f"SELECT character_name, class, level, highest_floor, enemies_killed "
            f"FROM players ORDER BY {order} LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def count_inventory(player_id: int) -> int:
    """Count total inventory items for a player."""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT COUNT(*) as cnt FROM inventories WHERE player_id = ?",
            (player_id,),
        )
        row = await cursor.fetchone()
        return row["cnt"]
    finally:
        await db.close()


async def reset_player(discord_id: str) -> None:
    """Delete a player and all related data (inventories, sessions)."""
    db = await get_db()
    try:
        await db.execute("DELETE FROM players WHERE discord_id = ?", (discord_id,))
        await db.commit()
        logger.info("Player reset: discord_id=%s", discord_id)
    finally:
        await db.close()
