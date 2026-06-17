import discord
from discord.ext import commands
import edge_tts
import io
import asyncio
import discord.opus

# Library path fix
try:
    discord.opus.load_opus('/usr/lib/x86_64-linux-gnu/libopus.so.0')
except:
    pass

class TTS(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="join")
    async def join(self, ctx):
        channel = ctx.author.voice.channel
        vc = await channel.connect()
        await ctx.send("Connected!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user or not message.guild.voice_client:
            return
        
        # Simple TTS logic
        communicate = edge_tts.Communicate(message.content, "en-US-ChristopherNeural")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]
        
        source = discord.FFmpegPCMAudio(io.BytesIO(audio_data), pipe=True)
        message.guild.voice_client.play(source)

async def setup(bot):
    await bot.add_cog(TTS(bot))
