import discord
from discord import app_commands
from discord.ext import commands
import edge_tts
import io
import asyncio
import discord.opus
import os

# Docker container ke liye library path fix
try:
    discord.opus.load_opus('/usr/lib/x86_64-linux-gnu/libopus.so.0')
except Exception as e:
    print(f"Opus load error: {e}")

class TTS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ffmpeg_path = "/usr/bin/ffmpeg"

    @app_commands.command(name="join", description="Bot ko voice channel mein join karayein")
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice:
            channel = interaction.user.voice.channel
            try:
                await channel.connect()
                await interaction.response.send_message("🎙️ Voice channel mein connect ho gaya!")
            except Exception as e:
                await interaction.response.send_message(f"❌ Failed to connect: {str(e)}")
        else:
            await interaction.response.send_message("Pehle kisi voice channel mein toh jao!")

    @app_commands.command(name="leave", description="Bot ko voice channel se bahar nikalen")
    async def leave(self, interaction: discord.Interaction):
        if interaction.guild.voice_client:
            await interaction.guild.voice_client.disconnect()
            await interaction.response.send_message("👋 Chalo, main nikal gaya.")
        else:
            await interaction.response.send_message("Main kisi channel mein hoon hi nahi!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or not message.guild.voice_client:
            return
        
        # TTS logic
        communicate = edge_tts.Communicate(message.content, "en-US-ChristopherNeural")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        source = discord.FFmpegPCMAudio(
            io.BytesIO(audio_data), 
            pipe=True, 
            executable=self.ffmpeg_path
        )
        
        if not message.guild.voice_client.is_playing():
            message.guild.voice_client.play(source)

async def setup(bot):
    await bot.add_cog(TTS(bot))
