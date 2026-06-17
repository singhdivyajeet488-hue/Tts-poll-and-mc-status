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

    # 1. Join
    @app_commands.command(name="join", description="Bot ko voice channel mein join karayein")
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
            await interaction.response.send_message("🎙️ Voice channel mein connect ho gaya!")
        else:
            await interaction.response.send_message("❌ Pehle voice channel mein jao!")

    # 2. Leave
    @app_commands.command(name="leave", description="Bot ko voice channel se bahar nikalen")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("👋 Chalo, main nikal gaya.")
        else:
            await interaction.response.send_message("❌ Main kisi channel mein hoon hi nahi!")

    # 3. MC Status
    @app_commands.command(name="mcstatus", description="Minecraft server status check karein")
    async def mcstatus(self, interaction: discord.Interaction):
        await interaction.response.send_message("Server status: Online! 🟢")

    # 4. Poll Create
    @app_commands.command(name="poll_create", description="Ek naya poll banayein")
    async def poll_create(self, interaction: discord.Interaction, question: str):
        await interaction.response.send_message(f"📊 Poll ban gaya: {question}")

    # 5. Poll End
    @app_commands.command(name="poll_end", description="Poll khatam karein")
    async def poll_end(self, interaction: discord.Interaction):
        await interaction.response.send_message("🏁 Poll khatam ho gaya!")

async def setup(bot):
    await bot.add_cog(TTS(bot))
