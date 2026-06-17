import discord
from discord import app_commands
from discord.ext import commands
import discord.opus
import os

# Docker/Railway ke liye library fix
try:
    discord.opus.load_opus('/usr/lib/x86_64-linux-gnu/libopus.so.0')
except Exception as e:
    print(f"Opus load error: {e}")

class TTS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="join", description="Join your voice channel")
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            await channel.connect()
            await interaction.response.send_message(f"🎙️ Joined {channel.name}")
        else:
            await interaction.response.send_message("❌ You are not in a voice channel!")

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("👋 Left the voice channel.")
        else:
            await interaction.response.send_message("❌ I am not in a voice channel.")

async def setup(bot):
    await bot.add_cog(TTS(bot))
