import asyncio
import logging
import discord
from discord.ext import commands
import config

# Setup clean logging layout
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("BotMain")

class CoreBot(commands.Bot):
    def __init__(self) -> None:
        # Request necessary intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        intents.voice_states = True
        
        super().__init__(command_prefix=None, intents=intents)
        
    async def setup_hook(self) -> None:
        # Extensions to load
        extensions = [
            "cogs.polls",
            "cogs.tts",
            "cogs.minecraft"
        ]
        
        for ext in extensions:
            try:
                await self.load_extension(ext)
                logger.info(f"Successfully loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load extension {ext}: {e}", exc_info=True)
                
    async def on_ready(self) -> None:
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("Syncing global slash commands...")
        try:
            synced = await self.tree.sync()
            logger.info(f"Successfully synced {len(synced)} slash commands globally.")
        except Exception as e:
            logger.error(f"Failed to sync slash commands: {e}")
            
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name="your commands")
        )

async def main() -> None:
    bot = CoreBot()
    async with bot:
        await bot.start(config.TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot shutting down gracefully via KeyboardInterrupt.")
