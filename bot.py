# bot.py — Karuna Discord Bot v0.1.0

import discord
import asyncio
import logging
from discord import app_commands
from config import LOG_PATH
from db import get_setting

logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

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

    # รัน pipeline ใน thread pool โดยไม่บล็อก event loop
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_pipeline)

    await interaction.followup.send("📡 Done — check the news channel!")

def _run_pipeline():
    from crawler import fetch_articles
    from summariser import summarise_batch
    from notifier import send_to_discord
    limit = int(get_setting("news_per_run") or 10)
    articles = fetch_articles(limit=limit)
    summaries = summarise_batch(articles)
    send_to_discord(summaries)

if __name__ == "__main__":
    token = get_bot_token()
    if not token:
        print("❌ No bot token configured")
    else:
        client.run(token)
