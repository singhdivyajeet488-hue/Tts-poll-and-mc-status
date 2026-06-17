import discord
from discord.ext import commands
import asyncio
import os
import config

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.voice_states = True

bot_prefix = "!"
if hasattr(config, "PREFIX") and config.PREFIX:
    bot_prefix = str(config.PREFIX)

bot = commands.Bot(command_prefix=bot_prefix, intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f"[INFO] BotMain: Logged in as {bot.user} (ID: {bot.user.id})")
    try:
        # Extensions load karein
        await load_extensions()
        
        # Commands sync karein
        bot.tree.clear_commands(guild=None)
        synced = await bot.tree.sync()
        print(f"[INFO] BotMain: Successfully synced {len(synced)} slash commands globally.")
    except Exception as e:
        print(f"[ERROR] BotMain: Failed to sync slash commands: {e}")

async def load_extensions():
    initial_extensions = ["cogs.minecraft", "cogs.polls", "cogs.tts"]
    for ext in initial_extensions:
        try:
            await bot.load_extension(ext)
            print(f"[INFO] BotMain: Successfully loaded extension: {ext}")
        except Exception as e:
            print(f"[ERROR] BotMain: Failed to load extension {ext}: {e}")

async def main():
    async with bot:
        token = os.getenv("DISCORD_TOKEN") or getattr(config, "TOKEN", None)
        if not token:
            raise ValueError("No discord token found in Environment or config.py!")
        await bot.start(token)

if __name__ == "__main__":
    asyncio.run(main())
