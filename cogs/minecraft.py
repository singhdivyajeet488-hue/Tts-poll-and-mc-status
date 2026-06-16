import re
import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from mcstatus import JavaServer
import config

class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_monitors = {} # Dictionary tracking {message_id: server_address_string}
        self.live_monitor_loop.start()

    def cog_unload(self):
        self.live_monitor_loop.cancel()

    def motd_to_ansi(self, description) -> str:
        """Converts Minecraft legacy section formatting codes to Discord codeblock ANSI color spaces."""
        text = ""
        if isinstance(description, str):
            text = description
        elif isinstance(description, dict):
            text = description.get("text", "")
            if "extra" in description:
                for part in description["extra"]:
                    if isinstance(part, dict):
                        text += part.get("text", "")
                    elif isinstance(part, str):
                        text += part
        else:
            text = str(description)

        # Map Minecraft formatting flags cleanly to ANSI sequences
        color_map = {
            '0': '\u001b[0;30m', '1': '\u001b[0;34m', '2': '\u001b[0;32m', '3': '\u001b[0;36m',
            '4': '\u001b[0;31m', '5': '\u001b[0;35m', '6': '\u001b[0;33m', '7': '\u001b[0;37m',
            '8': '\u001b[1;30m', '9': '\u001b[1;34m', 'a': '\u001b[1;32m', 'b': '\u001b[1;36m',
            'c': '\u001b[1;31m', 'd': '\u001b[1;35m', 'e': '\u001b[1;33m', 'f': '\u001b[1;37m',
            'r': '\u001b[0m'
        }

        for key, value in color_map.items():
            text = text.replace(f"§{key}", value)
            text = text.replace(f"§{key.upper()}", value)

        # Clear secondary non-color layout modifiers (bold, oblique, etc)
        text = re.sub(r'§[k-oK-O]', '', text)
        return text.strip() + '\u001b[0m'

    async def fetch_status_embed(self, address: str) -> discord.Embed:
        """Helper tool to look up server details and wrap them into an embed."""
        try:
            server = await JavaServer.async_lookup(address)
            status = await server.async_status()
            
            ansi_motd = self.motd_to_ansi(status.description)
            
            embed = discord.Embed(title=f"🎮 {address} Live Status", color=config.COLOR_SUCCESS)
            embed.add_field(name="📌 Host Target IP", value=f"`{server.address.host}:{server.address.port}`", inline=True)
            embed.add_field(name="⚙️ Software Version", value=f"`{status.version.name}`", inline=True)
            embed.add_field(name="👥 Population", value=f"`{status.players.online}/{status.players.max}` players", inline=True)
            embed.add_field(name="📝 Message of the Day (MOTD)", value=f"```ansi\n{ansi_motd}\n```", inline=False)

            if status.players.sample:
                player_sample = ", ".join([p.name for p in status.players.sample])
                if len(player_sample) > 1018:
                    player_sample = player_sample[:1015] + "..."
                embed.add_field(name="👥 Active Players", value=f"```text\n{player_sample}\n```", inline=False)
            
            # Utilizing permanent icon wrapper API to maintain stable thumbnail URLs across asynchronous re-edits
            icon_url = f"https://api.mcsrvstat.us/icon/{address}"
            embed.set_thumbnail(url=icon_url)
            embed.set_footer(text="🔄 Auto-refreshes every 30 seconds live")
            return embed

        except Exception:
            embed_err = discord.Embed(
                title="❌ Target Connection Lost",
                description=f"Could not update status for `{address}`.\nThe server might be down or restarting.",
                color=config.COLOR_ERROR
            )
            return embed_err

    @app_commands.command(name="mcstatus", description="Query network attributes for a specific Minecraft server instance.")
    @app_commands.rename(address="ip_address")
    @app_commands.describe(address="The IP or domain address of the server (e.g. play.hypixel.net)")
    async def mcstatus(self, interaction: discord.Interaction, address: str) -> None:
        await interaction.response.defer(thinking=True)
        
        embed = await self.fetch_status_embed(address)
        await interaction.followup.send(embed=embed)
        
        # Capture the output response message ID to include it in our background task map loop
        original_msg = await interaction.original_response()
        self.active_monitors[original_msg.id] = {
            "address": address,
            "channel": interaction.channel
        }

    @tasks.loop(seconds=30.0)
    async def live_monitor_loop(self):
        """Background daemon looping continuously every 30 seconds to update old embeds without making new ones."""
        if not self.active_monitors:
            return

        # Create a copy of keys to avoid modification loops during iterations
        for msg_id, data in list(self.active_monitors.items()):
            try:
                channel = data["channel"]
                address = data["address"]
                
                # Fetch the message structure out from Discord's active channel caches
                try:
                    message = await channel.fetch_message(msg_id)
                except discord.NotFound:
                    # Clear target reference if the tracking post was deleted by a user
                    del self.active_monitors[msg_id]
                    continue
                
                # Render updated dataset
                new_embed = await self.fetch_status_embed(address)
                await message.edit(embed=new_embed)
                
            except Exception as e:
                print(f"Error occurring inside live monitor scheduler thread: {e}")

    @live_monitor_loop.before_loop
    async def before_live_monitor_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Minecraft(bot))
