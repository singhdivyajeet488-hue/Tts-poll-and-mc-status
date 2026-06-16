import asyncio
import io
import logging
import os
import discord
from discord import app_commands
from discord.ext import commands
import edge_tts
import config
from typing import Dict, Optional

logger = logging.getLogger("BotTTS")

class VoiceStateTracker:
    def __init__(self, text_channel_id: int) -> None:
        self.text_channel_id: int = text_channel_id
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.worker_task: Optional[asyncio.Task] = None

class TTS(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.guild_states: Dict[int, VoiceStateTracker] = {}

    async def tts_worker(self, guild_id: int, vc: discord.VoiceClient) -> None:
        state = self.guild_states.get(guild_id)
        if not state:
            return
        try:
            while vc.is_connected():
                text = await state.queue.get()
                try:
                    communicate = edge_tts.Communicate(text, config.TTS_VOICE)
                    audio_data = b""
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_data += chunk["data"]

                    if not audio_data:
                        state.queue.task_done()
                        continue

                    audio_stream = io.BytesIO(audio_data)
                    source = discord.FFmpegPCMAudio(audio_stream, pipe=True, options="-loglevel quiet")

                    vc.play(source)
                    while vc.is_playing():
                        await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error in raw stream loop inside guild {guild_id}: {e}")
                finally:
                    state.queue.task_done()
        except asyncio.CancelledError:
            logger.info(f"Worker task canceled for guild {guild_id}")

    @app_commands.command(name="join", description="Connect bot to your present voice channel.")
    async def join(self, interaction: discord.Interaction) -> None:
        if not interaction.user.voice or not interaction.user.voice.channel: # type: ignore
            await interaction.response.send_message("❌ Connect to a voice channel first!", ephemeral=True)
            return

        voice_channel = interaction.user.voice.channel # type: ignore
        text_channel_id = interaction.channel_id

        if interaction.guild.voice_client: # type: ignore
            await interaction.guild.voice_client.move_to(voice_channel) # type: ignore
        else:
            # Explicitly disable DAVE protocol support flags during handshake initialization
            await voice_channel.connect(timeout=20.0, reconnect=True, self_deaf=True)

        vc: discord.VoiceClient = interaction.guild.voice_client # type: ignore
        guild_id = interaction.guild_id # type: ignore

        if guild_id in self.guild_states:
            if self.guild_states[guild_id].worker_task:
                self.guild_states[guild_id].worker_task.cancel()

        state = VoiceStateTracker(text_channel_id) # type: ignore
        state.worker_task = asyncio.create_task(self.tts_worker(guild_id, vc))
        self.guild_states[guild_id] = state

        embed = discord.Embed(
            description=f"🎙️ Joined **{voice_channel.name}**\n📝 Bound tracking context to text-channel <#{text_channel_id}>",
            color=config.COLOR_SUCCESS
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leave", description="Disconnect bot from current Voice server instance.")
    async def leave(self, interaction: discord.Interaction) -> None:
        vc: Optional[discord.VoiceClient] = interaction.guild.voice_client # type: ignore
        if not vc or not vc.is_connected():
            await interaction.response.send_message("❌ Active voice link instances do not exist.", ephemeral=True)
            return

        guild_id = interaction.guild_id # type: ignore
        if guild_id in self.guild_states:
            if self.guild_states[guild_id].worker_task:
                self.guild_states[guild_id].worker_task.cancel()
            del self.guild_states[guild_id]

        await vc.disconnect()
        await interaction.response.send_message("👋 Safely disconnected from voice streams.")

    @app_commands.command(name="stoptts", description="Immediately halt ongoing audio synthesis execution.")
    async def stoptts(self, interaction: discord.Interaction) -> None:
        vc: Optional[discord.VoiceClient] = interaction.guild.voice_client # type: ignore
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("🛑 Clear audio buffers. Current track terminated.")
        else:
            await interaction.response.send_message("❌ No audio streams are currently playing.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        guild_id = message.guild.id
        state = self.guild_states.get(guild_id)
        if state and message.channel.id == state.text_channel_id:
            vc: Optional[discord.VoiceClient] = message.guild.voice_client # type: ignore
            if vc and vc.is_connected():
                spoken_content = f"{message.author.display_name} says: {message.clean_content}"
                await state.queue.put(spoken_content)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if member.id == self.bot.user.id:
            return
        vc: Optional[discord.VoiceClient] = member.guild.voice_client # type: ignore
        if vc and len(vc.channel.members) == 1:
            guild_id = member.guild.id
            if guild_id in self.guild_states:
                if self.guild_states[guild_id].worker_task:
                    self.guild_states[guild_id].worker_task.cancel()
                del self.guild_states[guild_id]
            await vc.disconnect()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TTS(bot))
