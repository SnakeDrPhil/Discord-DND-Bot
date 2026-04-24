"""Dungeon Crawler Discord Bot - Entry Point."""

import asyncio
import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

from src.db.database import init_db
from src.utils.embeds import error_embed

# ── Logging ────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("dungeon_bot")

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
    "src.bot.cogs.dungeon",
    "src.bot.cogs.inventory",
    "src.bot.cogs.shop",
    "src.bot.cogs.leaderboard",
    "src.bot.cogs.admin",
]


# ── Global Error Handler ──────────────────────────────────────────

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction,
                                error: app_commands.AppCommandError):
    """Global error handler for all slash commands."""
    if isinstance(error, app_commands.CommandOnCooldown):
        embed = error_embed(f"Command on cooldown. Try again in {error.retry_after:.1f}s.")
    elif isinstance(error, app_commands.MissingPermissions):
        embed = error_embed("You don't have permission to use this command.")
    else:
        logger.exception("Unhandled command error", exc_info=error)
        embed = error_embed("Something went wrong. Please try again.")

    try:
        if interaction.response.is_done():
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception:
        pass  # Interaction expired


# ── Events ─────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    """Called when the bot is connected and ready."""
    logger.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)

    # Initialize database
    await init_db()
    logger.info("Database initialized.")

    # Sync slash commands
    synced = await bot.tree.sync()
    logger.info("Synced %d slash command(s).", len(synced))

    logger.info("Bot is ready!")


async def main():
    """Load cogs and start the bot."""
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            logger.info("Loaded cog: %s", cog)
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
