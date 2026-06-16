import re
import io
import asyncio
import requests
import discord
from discord import app_commands
from discord.ext import commands, tasks
from mcstatus import JavaServer
from PIL import Image, ImageDraw, ImageFont
import config

class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_monitors = {} # Dictionary tracking {message_id: {"address": str, "channel": obj}}
        self.live_monitor_loop.start()

    def cog_unload(self):
        self.live_monitor_loop.cancel()

    def strip_color_codes(self, text: str) -> str:
        """Removes Minecraft's section sign formatting characters for image drawing."""
        return re.sub(r'§[0-9a-fk-orA-FK-OR]', '', text)

    def generate_server_image(self, address: str, raw_description) -> io.BytesIO:
        """Generates a high-quality server display image similar to the in-game server list."""
        lines = []
        if isinstance(raw_description, dict):
            text = raw_description.get("text", "")
            if "extra" in raw_description:
                text += "".join([part.get("text", "") for part in raw_description["extra"] if isinstance(part, dict)])
            lines = text.split('\n')
        elif isinstance(raw_description, str):
            lines = raw_description.split('\n')
        else:
            lines = [str(raw_description)]

        # Clean formatting tags and isolate the top 2 lines of the MOTD
        lines = [self.strip_color_codes(line).strip() for line in lines if line.strip()][:2]
        while len(lines) < 2:
            lines.append("")

        # Create the canvas simulating the dark Minecraft menu background
        img = Image.new('RGBA', (650, 100), color=(20, 20, 20, 255))
        draw = ImageDraw.Draw(img)

        # Grab and overlay the server favicon
        try:
            icon_url = f"https://api.mcsrvstat.us/icon/{address}"
            response = requests.get(icon_url, timeout=5)
            icon_img = Image.open(io.BytesIO(response.content)).convert("RGBA")
            icon_img = icon_img.resize((64, 64))
            img.paste(icon_img, (18, 18), icon_img)
        except Exception:
            # Fallback dark placeholder if server provides no favicon asset
            draw.rectangle([18, 18, 82, 82], fill=(45, 45, 45, 255))

        # Render the Text strings
        draw.text((100, 15), address.upper(), fill=(255, 255, 255))
        draw.text((100, 42), lines[0], fill=(180, 180, 180))
        draw.text((100, 65), lines[1], fill=(180, 180, 180))

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    async def fetch_status_embed(self, address: str):
        """Queries connection strings to collect metadata metrics."""
        try:
            server = await JavaServer.async_lookup(address)
            status = await server.async_status()
            
            embed = discord.Embed(title="🎮 Minecraft Server Status Monitor", color=config.COLOR_SUCCESS)
            embed.add_field(name="📌 Server IP", value=f"`{address}`", inline=True)
            embed.add_field(name="⚙️ Server Version", value=f"`{status.version.name}`", inline=True)
            embed.add_field(name="👥 Population", value=f"`{status.players.online}/{status.players.max}` players", inline=True)
            
            embed.set_footer(text="🔄 Auto-refreshes seamlessly every 30 seconds live")
            return embed, status.description
        except Exception:
            embed_err = discord.Embed(
                title="❌ Target Connection Terminated",
                description=f"Could not connect to `{address}`.\nVerify host data or check if server is starting up.",
                color=config.COLOR_ERROR
            )
            return embed_err, None

    @app_commands.command(name="mcstatus", description="Query network attributes for a specific Minecraft server instance.")
    @app_commands.rename(address="ip_address")
    @app_commands.describe(address="The IP or domain address of the server (e.g. play.hypixel.net)")
    async def mcstatus(self, interaction: discord.Interaction, address: str) -> None:
        await interaction.response.defer(thinking=True)
        
        embed, raw_desc = await self.fetch_status_embed(address)
        
        if raw_desc:
            img_buffer = self.generate_server_image(address, raw_desc)
            file = discord.File(img_buffer, filename="server_ui.png")
            embed.set_image(url="attachment://server_ui.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)
        
        original_msg = await interaction.original_response()
        self.active_monitors[original_msg.id] = {
            "address": address,
            "channel": interaction.channel
        }

    @tasks.loop(seconds=30.0)
    async def live_monitor_loop(self):
        """Background schedule loops modifying old data panels in place."""
        if not self.active_monitors:
            return

        for msg_id, data in list(self.active_monitors.items()):
            try:
                channel = data["channel"]
                address = data["address"]
                
                try:
                    message = await channel.fetch_message(msg_id)
                except discord.NotFound:
                    del self.active_monitors[msg_id]
                    continue
                
                embed, raw_desc = await self.fetch_status_embed(address)
                
                if raw_desc:
                    img_buffer = self.generate_server_image(address, raw_desc)
                    file = discord.File(img_buffer, filename="server_ui.png")
                    embed.set_image(url="attachment://server_ui.png")
                    await message.edit(embed=embed, attachments=[file])
                else:
                    await message.edit(embed=embed)
                    
            except Exception as e:
                print(f"Error occurring inside background update routine loop: {e}")

    @live_monitor_loop.before_loop
    async def before_live_monitor_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Minecraft(bot))
