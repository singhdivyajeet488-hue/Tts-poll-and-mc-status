import re
import io
import asyncio
import requests
import discord
from discord import app_commands
from discord.ext import commands, tasks
from mcstatus import JavaServer
from PIL import Image, ImageDraw, ImageFont

class Minecraft(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_monitors = {}
        self.live_monitor_loop.start()

    def cog_unload(self):
        self.live_monitor_loop.cancel()

    def parse_motd_components(self, description):
        """Extracts text and color codes from complex Minecraft MOTD schemas."""
        color_map = {
            '0': (0, 0, 0), '1': (0, 0, 170), '2': (0, 170, 0), '3': (0, 170, 170),
            '4': (170, 0, 0), '5': (170, 0, 170), '6': (255, 170, 0), '7': (170, 170, 170),
            '8': (85, 85, 85), '9': (85, 85, 255), 'a': (85, 255, 85), 'b': (85, 255, 255),
            'c': (255, 85, 85), 'd': (255, 85, 255), 'e': (255, 255, 85), 'f': (255, 255, 255)
        }
        
        parsed_parts = []
        default_color = (255, 255, 255)

        if isinstance(description, dict):
            extra_parts = description.get("extra", [])
            base_text = description.get("text", "")
            if base_text:
                parsed_parts.append((base_text, default_color))
            for part in extra_parts:
                if isinstance(part, dict):
                    txt = part.get("text", "")
                    color_name = part.get("color", "white")
                    # Basic fallback translation map for text fields
                    named_colors = {"red": (255, 85, 85), "gold": (255, 170, 0), "yellow": (255, 255, 85), "green": (85, 255, 85), "aqua": (85, 255, 255), "blue": (85, 85, 255), "light_purple": (255, 85, 255)}
                    col = named_colors.get(color_name.lower(), default_color)
                    if txt:
                        parsed_parts.append((txt, col))
        elif isinstance(description, str):
            tokens = re.split(r'(§[0-9a-fk-orA-FK-OR])', description)
            current_color = default_color
            for token in tokens:
                if token.startswith('§'):
                    code = token[1].lower()
                    current_color = color_map.get(code, default_color)
                elif token:
                    parsed_parts.append((token, current_color))
        return parsed_parts

    def generate_server_image(self, address: str, raw_description, status) -> io.BytesIO:
        """Draws a true 1:1 replica image layout modeled exactly after the in-game multiplayer tab."""
        img = Image.new('RGBA', (750, 110), color=(18, 18, 18, 255))
        draw = ImageDraw.Draw(img)

        # Download and apply favicon
        try:
            icon_url = f"https://api.mcsrvstat.us/icon/{address}"
            res = requests.get(icon_url, timeout=4)
            icon_img = Image.open(io.BytesIO(res.content)).convert("RGBA").resize((72, 72))
            img.paste(icon_img, (16, 19), icon_img)
        except Exception:
            draw.rectangle([16, 19, 88, 91], fill=(40, 40, 40, 255))

        # Attempt to bind your uploaded pixel fonts, fallback gracefully if not built yet
        try:
            font_title = ImageFont.truetype("Minecraftia.ttf", 18)
            font_motd = ImageFont.truetype("Minecraftia.ttf", 15)
        except Exception:
            font_title = font_motd = ImageFont.load_default()

        # Render Title / IP Address details
        draw.text((105, 16), address.upper(), fill=(255, 255, 255), font=font_title)

        # Render active Player Count stats
        players_str = f"{status.players.online}/{status.players.max}"
        draw.text((734 - draw.textlength(players_str, font=font_motd), 16), players_str, fill=(170, 170, 170), font=font_motd)

        # Process complex MOTD items line by line
        motd_components = self.parse_motd_components(raw_description)
        x_cursor, y_cursor = 105, 46
        
        for text_segment, rgb_color in motd_components:
            if '\n' in text_segment:
                sub_lines = text_segment.split('\n')
                for idx, line in enumerate(sub_lines):
                    if idx > 0:
                        x_cursor = 105
                        y_cursor += 22
                    if y_cursor > 80:
                        break
                    draw.text((x_cursor, y_cursor), line, fill=rgb_color, font=font_motd)
                    x_cursor += int(draw.textlength(line, font=font_motd))
            else:
                if y_cursor > 80:
                    break
                draw.text((x_cursor, y_cursor), text_segment, fill=rgb_color, font=font_motd)
                x_cursor += int(draw.textlength(text_segment, font=font_motd))

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer

    async def fetch_status_embed(self, address: str):
        try:
            server = await JavaServer.async_lookup(address)
            status = await server.async_status()
            embed = discord.Embed(title="🎮 Server Status", color=discord.Color.green())
            embed.add_field(name="⚙️ Server Version", value=f"`{status.version.name}`", inline=True)
            embed.add_field(name="🔗 Host Domain IP", value=f"`{address}`", inline=True)
            embed.set_footer(text="🔄 Live updating background loop active (30s intervals)")
            return embed, status.description, status
        except Exception:
            embed_err = discord.Embed(title="❌ Connection Offline", description=f"Could not connect to `{address}`.", color=discord.Color.red())
            return embed_err, None, None

    @app_commands.command(name="mcstatus", description="Query network attributes for a specific Minecraft server instance.")
    @app_commands.describe(address="The IP or domain address of the server")
    async def mcstatus(self, interaction: discord.Interaction, address: str) -> None:
        await interaction.response.defer(thinking=True)
        embed, raw_desc, status = await self.fetch_status_embed(address)
        
        if raw_desc:
            img_buffer = self.generate_server_image(address, raw_desc, status)
            file = discord.File(img_buffer, filename="server_ui.png")
            embed.set_image(url="attachment://server_ui.png")
            await interaction.followup.send(embed=embed, file=file)
        else:
            await interaction.followup.send(embed=embed)
        
        original_msg = await interaction.original_response()
        self.active_monitors[original_msg.id] = {"address": address, "channel": interaction.channel}

    @tasks.loop(seconds=30.0)
    async def live_monitor_loop(self):
        if not self.active_monitors:
            return
        for msg_id, data in list(self.active_monitors.items()):
            try:
                channel, address = data["channel"], data["address"]
                try:
                    message = await channel.fetch_message(msg_id)
                except discord.NotFound:
                    del self.active_monitors[msg_id]
                    continue
                
                embed, raw_desc, status = await self.fetch_status_embed(address)
                if raw_desc:
                    img_buffer = self.generate_server_image(address, raw_desc, status)
                    file = discord.File(img_buffer, filename="server_ui.png")
                    embed.set_image(url="attachment://server_ui.png")
                    await message.edit(embed=embed, attachments=[file])
                else:
                    await message.edit(embed=embed)
            except Exception:
                pass

    @live_monitor_loop.before_loop
    async def before_live_monitor_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Minecraft(bot))
