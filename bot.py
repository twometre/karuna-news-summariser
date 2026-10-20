# bot.py — Karuna Discord Bot v0.3.0

import discord
import asyncio
import logging
from discord import app_commands
from db import get_setting
from pipeline import run_pipeline, setup_logging

setup_logging()

def get_bot_token():
    return get_setting("discord_bot_token")

def get_guild_id():
    val = get_setting("discord_guild_id")
    return int(val) if val else None

class KarunaBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        guild_id = get_guild_id()
        if guild_id:
            guild = discord.Object(id=guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logging.info(f"Slash commands synced to guild {guild_id}")
        else:
            logging.error("No guild ID configured")

    async def on_ready(self):
        logging.info(f"Karuna Bot ready — logged in as {self.user}")
        print(f"✅ Karuna Bot ready — {self.user}")

client = KarunaBot()

@client.tree.command(name="newnews", description="Fetch and summarise latest news now")
async def newnews(interaction: discord.Interaction):
    await interaction.response.defer(thinking=True)
    logging.info(f"/newnews triggered by {interaction.user}")

    # pipeline.py holds a cross-container flock — a concurrent scheduled run
    # makes this a no-op instead of a duplicate digest.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, run_pipeline)

    await interaction.followup.send("📡 Done — check the news channel!")

if __name__ == "__main__":
    token = get_bot_token()
    if not token:
        print("❌ No bot token configured")
    else:
        client.run(token)
