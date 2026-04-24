"""Dungeon Crawler Discord Bot - Entry Point."""

import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from src.db.database import init_db

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN not set in .env file. Copy .env.example to .env and add your token.")

# Bot setup with required intents
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# List of cog modules to load
COGS = [
    "src.bot.cogs.general",
    "src.bot.cogs.character",
    "src.bot.cogs.leveling",
    "src.bot.cogs.combat",
]


@bot.event
async def on_ready():
    """Called when the bot is connected and ready."""
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Initialize database
    await init_db()
    print("Database initialized.")

    # Sync slash commands
    synced = await bot.tree.sync()
    print(f"Synced {len(synced)} slash command(s).")

    print("Bot is ready!")


async def main():
    """Load cogs and start the bot."""
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f"Loaded cog: {cog}")
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
