import discord
from discord.ext import commands
import edge_tts
import io
import asyncio
import discord.opus
import os

# Library path fix for Railway/Docker
try:
    discord.opus.load_opus('/usr/lib/x86_64-linux-gnu/libopus.so.0')
except Exception as e:
    print(f"Opus load error: {e}")

class TTS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # FFMPEG path for Docker
        self.ffmpeg_path = "/usr/bin/ffmpeg"

    @commands.command(name="join")
    async def join(self, ctx):
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            try:
                await channel.connect()
                await ctx.send("Connected!")
            except Exception as e:
                await ctx.send(f"Error: {e}")
        else:
            await ctx.send("Pehle voice channel mein jao!")

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
        
        # Path explicitly pass karna zaroori hai
        source = discord.FFmpegPCMAudio(
            io.BytesIO(audio_data), 
            pipe=True, 
            executable=self.ffmpeg_path
        )
        
        if not message.guild.voice_client.is_playing():
            message.guild.voice_client.play(source)

async def setup(bot):
    await bot.add_cog(TTS(bot))
