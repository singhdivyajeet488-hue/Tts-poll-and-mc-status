import base64
import io
import discord
from discord import app_commands
from discord.ext import commands
from mcstatus import JavaServer  # Updated to match the latest mcstatus API
import config

class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="mcstatus", description="Query network attributes for a specific Minecraft server instance.")
    @app_commands.rename(address="ip_address")
    @app_commands.describe(address="The IP or domain address of the server (e.g. play.hypixel.net)")
    async def mcstatus(self, interaction: discord.Interaction, address: str) -> None:
        # Acknowledge interaction because DNS lookups take time
        await interaction.response.defer(thinking=True)

        try:
            # Query standard Java server signature asynchronously using updated JavaServer class
            server = await JavaServer.async_lookup(address)
            status = await server.async_status()
        except Exception:
            try:
                # Fallback to alternative parsing models for complex configurations
                server = JavaServer.lookup(address)
                status = await server.async_status()
            except Exception as e:
                embed_err = discord.Embed(
                    title="❌ Target Connection Terminated",
                    description=f"Could not connect to `{address}`.\nVerify the IP or check if the host is down.",
                    color=config.COLOR_ERROR
                )
                await interaction.followup.send(embed=embed_err)
                return

        # Process clean MOTD lines
        motd_text = status.description if isinstance(status.description, str) else status.description.get("text", "")
        if not motd_text and isinstance(status.description, dict) and "extra" in status.description:
            motd_text = "".join([part.get("text", "") for part in status.description["extra"]])

        # Clean up legacy formatting tags if present
        for char in ["§" + c for c in "0123456789abcdefklmnor"]:
            motd_text = motd_text.replace(char, "")
        motd_text = motd_text.strip() or "No custom MOTD active."

        # Setup base embedding elements
        embed = discord.Embed(
            title=f"🎮 {address} Status",
            color=config.COLOR_SUCCESS
        )
        embed.add_field(name="📌 Host Target IP/Port", value=f"`{server.address.host}:{server.address.port}`", inline=True)
        embed.add_field(name="⚙️ Server Software Version", value=f"`{status.version.name}`", inline=True)
        embed.add_field(name="👥 Population Metrics", value=f"`{status.players.online}/{status.players.max}` players", inline=True)
        embed.add_field(name="📝 Message of the Day (MOTD)", value=f"```text\n{motd_text}\n```", inline=False)

        # Attempt to parse specific interactive lists if returned by host
        if status.players.sample:
            player_sample = ", ".join([p.name for p in status.players.sample])
            if len(player_sample) > 1018:
                player_sample = player_sample[:1015] + "..."
            embed.add_field(name="👥 Sample Player Activity", value=f"```text\n{player_sample}\n```", inline=False)

        file = None
        # Handle Server Favicon extraction if existing
        if status.favicon:
            try:
                header, encoded = status.favicon.split(",", 1)
                data = base64.b64decode(encoded)
                file = discord.File(io.BytesIO(data), filename="server_icon.png")
                embed.set_thumbnail(url="attachment://server_icon.png")
            except Exception:
                pass  # Suppress errors if favicon encoding parsing fails

        if file:
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="serverstatus", description="Alternative layout mapping path alias for mcstatus.")
    async def serverstatus(self, interaction: discord.Interaction, address: str) -> None:
        await self.mcstatus(interaction, address)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Minecraft(bot))
