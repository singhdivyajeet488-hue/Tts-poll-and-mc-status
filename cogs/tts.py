import os
import shutil
import asyncio
import io
import logging
import discord
from discord import app_commands
from discord.ext import commands
import edge_tts
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

    def get_ffmpeg_executable(self) -> str:
        """Determines the absolute location of the system FFmpeg binary wrapper."""
        # Check explicit pathing layers or fall back to system lookups
        env_path = os.getenv("FFMPEG_PATH", "/usr/bin/ffmpeg")
        if os.path.exists(env_path):
            return env_path
        
        fallback = shutil.which("ffmpeg")
        if fallback:
            return fallback
            
        # Common structural paths for cloud container engines
        for common_loc in ["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/opt/homebrew/bin/ffmpeg"]:
            if os.path.exists(common_loc):
                return common_loc
        return "ffmpeg"

    async def tts_worker(self, guild_id: int, vc: discord.VoiceClient) -> None:
        state = self.guild_states.get(guild_id)
        if not state:
            return
        try:
            while vc.is_connected():
                text = await state.queue.get()
                try:
                    communicate = edge_tts.Communicate(text, "en-US-ChristopherNeural")
                    audio_data = b""
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            audio_data += chunk["data"]

                    if not audio_data:
                        state.queue.task_done()
                        continue

                    audio_stream = io.BytesIO(audio_data)
                    ffmpeg_bin = self.get_ffmpeg_executable()
                    
                    # Pass the localized path directly into the processing engine
                    source = discord.FFmpegPCMAudio(audio_stream, pipe=True, executable=ffmpeg_bin)

                    vc.play(source)
                    while vc.is_playing():
                        await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error(f"Error in raw stream loop: {e}")
                finally:
                    state.queue.task_done()
        except asyncio.CancelledError:
            pass

    @app_commands.command(name="join", description="Connect bot to your present voice channel.")
    async def join(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(thinking=True)

        if not interaction.user.voice or not interaction.user.voice.channel: # type: ignore
            await interaction.followup.send("❌ Connect to a voice channel first!")
            return

        voice_channel = interaction.user.voice.channel # type: ignore
        text_channel_id = interaction.channel_id

        try:
            if interaction.guild.voice_client: # type: ignore
                await interaction.guild.voice_client.move_to(voice_channel) # type: ignore
            else:
                await voice_channel.connect(timeout=20.0, reconnect=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to connect: {e}")
            return

        vc: discord.VoiceClient = interaction.guild.voice_client # type: ignore
        guild_id = interaction.guild_id # type: ignore

        if guild_id in self.guild_states:
            if self.guild_states[guild_id].worker_task:
                self.guild_states[guild_id].worker_task.cancel()

        state = VoiceStateTracker(text_channel_id) # type: ignore
        state.worker_task = asyncio.create_task(self.tts_worker(guild_id, vc))
        self.guild_states[guild_id] = state

        await interaction.followup.send(f"🎙️ Joined **{voice_channel.name}** and linked to this channel!")

    @app_commands.command(name="leave", description="Disconnect bot from voice.")
    async def leave(self, interaction: discord.Interaction) -> None:
        vc: Optional[discord.VoiceClient] = interaction.guild.voice_client # type: ignore
        if not vc:
            await interaction.response.send_message("❌ Not in voice.", ephemeral=True)
            return

        guild_id = interaction.guild_id # type: ignore
        if guild_id in self.guild_states:
            if self.guild_states[guild_id].worker_task:
                self.guild_states[guild_id].worker_task.cancel()
            del self.guild_states[guild_id]

        await vc.disconnect()
        await interaction.response.send_message("👋 Left the voice channel.")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot or not message.guild:
            return
        state = self.guild_states.get(message.guild.id)
        if state and message.channel.id == state.text_channel_id:
            vc: Optional[discord.VoiceClient] = message.guild.voice_client # type: ignore
            if vc and vc.is_connected():
                spoken_content = f"{message.author.display_name} says: {message.clean_content}"
                await state.queue.put(spoken_content)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TTS(bot))
