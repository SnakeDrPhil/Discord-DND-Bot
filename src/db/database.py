"""Database connection and initialization."""

import logging
import os

import aiosqlite

logger = logging.getLogger("dungeon_bot.db")

DATABASE_PATH = os.getenv("DATABASE_PATH", "dungeon_crawler.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    discord_id TEXT UNIQUE NOT NULL,
    character_name TEXT NOT NULL,
    class TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 1,
    xp INTEGER NOT NULL DEFAULT 0,
    hp INTEGER NOT NULL,
    max_hp INTEGER NOT NULL,
    mana INTEGER NOT NULL,
    max_mana INTEGER NOT NULL,
    sp INTEGER NOT NULL,
    max_sp INTEGER NOT NULL,
    strength INTEGER NOT NULL,
    dexterity INTEGER NOT NULL,
    intelligence INTEGER NOT NULL,
    agility INTEGER NOT NULL,
    wisdom INTEGER NOT NULL,
    endurance INTEGER NOT NULL,
    charisma INTEGER NOT NULL,
    unspent_stat_points INTEGER NOT NULL DEFAULT 0,
    learned_skills TEXT NOT NULL DEFAULT '[]',
    selected_talents TEXT NOT NULL DEFAULT '[]',
    current_floor INTEGER NOT NULL DEFAULT 1,
    position_x INTEGER NOT NULL DEFAULT 0,
    position_y INTEGER NOT NULL DEFAULT 0,
    in_dungeon INTEGER NOT NULL DEFAULT 0,
    gold INTEGER NOT NULL DEFAULT 0,
    enemies_killed INTEGER NOT NULL DEFAULT 0,
    highest_floor INTEGER NOT NULL DEFAULT 1,
    bosses_killed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS inventories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    item_id TEXT NOT NULL,
    item_data TEXT NOT NULL,
    equipped INTEGER NOT NULL DEFAULT 0,
    slot TEXT,
    quantity INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS combat_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE,
    enemies TEXT NOT NULL,
    turn_number INTEGER NOT NULL DEFAULT 1,
    current_turn TEXT NOT NULL DEFAULT 'player',
    player_buffs TEXT NOT NULL DEFAULT '[]',
    player_debuffs TEXT NOT NULL DEFAULT '[]',
    enemy_buffs TEXT NOT NULL DEFAULT '[]',
    enemy_debuffs TEXT NOT NULL DEFAULT '[]',
    attacks_used INTEGER NOT NULL DEFAULT 0,
    buffs_used INTEGER NOT NULL DEFAULT 0,
    items_used INTEGER NOT NULL DEFAULT 0,
    extra_turn INTEGER NOT NULL DEFAULT 0,
    damage_taken INTEGER NOT NULL DEFAULT 0,
    combat_log TEXT NOT NULL DEFAULT '[]',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS dungeon_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE,
    floor INTEGER NOT NULL DEFAULT 1,
    position_x INTEGER NOT NULL DEFAULT 0,
    position_y INTEGER NOT NULL DEFAULT 0,
    visited_tiles TEXT NOT NULL DEFAULT '[]',
    active_effects TEXT NOT NULL DEFAULT '[]',
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
);
"""


async def get_db() -> aiosqlite.Connection:
    """Get a database connection with foreign keys enabled."""
    db = await aiosqlite.connect(DATABASE_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON")
    return db


_MIGRATIONS = [
    "ALTER TABLE players ADD COLUMN enemies_killed INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE players ADD COLUMN highest_floor INTEGER NOT NULL DEFAULT 1",
    "ALTER TABLE players ADD COLUMN bosses_killed INTEGER NOT NULL DEFAULT 0",
]


async def init_db():
    """Create all tables if they don't exist."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.executescript(_SCHEMA)
        await db.commit()
        # Run migrations for existing databases
        for migration in _MIGRATIONS:
            try:
                await db.execute(migration)
                await db.commit()
                logger.info("Migration applied: %s", migration[:60])
            except Exception:
                pass  # Column already exists
        logger.info("Database initialized at %s", DATABASE_PATH)
