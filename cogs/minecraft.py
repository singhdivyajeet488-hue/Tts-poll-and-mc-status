import base64
import io
import re
import discord
from discord import app_commands
from discord.ext import commands
from mcstatus import JavaServer
import config

class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    def motd_to_ansi(self, description) -> str:
        """Converts Minecraft legacy section codes (§) to Discord ANSI color sequences."""
        if isinstance(description, str):
            text = description
        elif isinstance(description, dict):
            text = description.get("text", "")
            if "extra" in description:
                text += "".join([part.get("text", "") for part in description["extra"] if isinstance(part, dict)])
        else:
            text = str(description)

        # Mapping Minecraft section codes to ANSI escape codes
        color_map = {
            '0': '\u001b[0;30m', '1': '\u001b[0;34m', '2': '\u001b[0;32m', '3': '\u001b[0;36m',
            '4': '\u001b[0;31m', '5': '\u001b[0;35m', '6': '\u001b[0;33m', '7': '\u001b[0;37m',
            '8': '\u001b[1;30m', '9': '\u001b[1;34m', 'a': '\u001b[1;32m', 'b': '\u001b[1;36m',
            'c': '\u001b[1;31m', 'd': '\u001b[1;35m', 'e': '\u001b[1;33m', 'f': '\u001b[1;37m',
            'r': '\u001b[0m'
        }

        # Replace standard section codes with ANSI formatting
        for key, value in color_map.items():
            text = text.replace(f"§{key}", value)
            text = text.replace(f"§{key.upper()}", value)

        # Remove extra unsupported text format styles (bold, underline, italic, strikethrough, obfuscated)
        text = re.sub(r'§[k-oK-O]', '', text)
        
        # Reset color string ending
        return text.strip() + '\u001b[0m'

    @app_commands.command(name="mcstatus", description="Query network attributes for a specific Minecraft server instance.")
    @app_commands.rename(address="ip_address")
    @app_commands.describe(address="The IP or domain address of the server (e.g. play.hypixel.net)")
    async def mcstatus(self, interaction: discord.Interaction, address: str) -> None:
        await interaction.response.defer(thinking=True)

        try:
            server = await JavaServer.async_lookup(address)
            status = await server.async_status()
        except Exception:
            try:
                server = JavaServer.lookup(address)
                status = await server.async_status()
            except Exception:
                embed_err = discord.Embed(
                    title="❌ Target Connection Terminated",
                    description=f"Could not connect to `{address}`.\nVerify the IP or check if the host is down.",
                    color=config.COLOR_ERROR
                )
                await interaction.followup.send(embed=embed_err)
                return

        # Process standard color conversions
        ansi_motd = self.motd_to_ansi(status.description) or "No custom MOTD active."

        embed = discord.Embed(title=f"🎮 {address} Status", color=config.COLOR_SUCCESS)
        embed.add_field(name="📌 Host Target IP/Port", value=f"`{server.address.host}:{server.address.port}`", inline=True)
        embed.add_field(name="⚙️ Server Software Version", value=f"`{status.version.name}`", inline=True)
        embed.add_field(name="👥 Population Metrics", value=f"`{status.players.online}/{status.players.max}` players", inline=True)
        # Using ansi code blocks to bring colors alive
        embed.add_field(name="📝 Message of the Day (MOTD)", value=f"```ansi\n{ansi_motd}\n```", inline=False)

        if status.players.sample:
            player_sample = ", ".join([p.name for p in status.players.sample])
            if len(player_sample) > 1018:
                player_sample = player_sample[:1015] + "..."
            embed.add_field(name="👥 Sample Player Activity", value=f"```text\n{player_sample}\n```", inline=False)

        file = None
        # Locate Favicon icon string data inside the host status wrapper
        favicon_data = getattr(status, 'favicon', None)
        if favicon_data and isinstance(favicon_data, str) and "," in favicon_data:
            try:
                header, encoded = favicon_data.split(",", 1)
                data = base64.b64decode(encoded)
                file = discord.File(io.BytesIO(data), filename="server_icon.png")
                embed.set_thumbnail(url="attachment://server_icon.png")
            except Exception:
                pass

        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="serverstatus", description="Alternative layout mapping path alias for mcstatus.")
    async def serverstatus(self, interaction: discord.Interaction, address: str) -> None:
        await self.mcstatus(interaction, address)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Minecraft(bot))
