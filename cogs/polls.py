import discord
from discord import app_commands
from discord.ext import commands
import config
from typing import Dict, List, Set

class PollVoteButton(discord.ui.Button):
    def __init__(self, label: str, custom_id: str) -> None:
        super().__init__(style=discord.ButtonStyle.secondary, label=label, custom_id=custom_id)

    async def callback(self, interaction: discord.Interaction) -> None:
        view: 'PollView' = self.view  # type: ignore
        user_id = interaction.user.id
        option_selected = self.custom_id

        if user_id in view.voters:
            previous_vote = view.voters[user_id]
            if previous_vote == option_selected:
                view.votes[option_selected].remove(user_id)
                del view.voters[user_id]
                await interaction.response.send_message("Your vote has been removed.", ephemeral=True)
            else:
                view.votes[previous_vote].remove(user_id)
                view.votes[option_selected].add(user_id)
                view.voters[user_id] = option_selected
                await interaction.response.send_message(f"Vote changed to: **{option_selected}**", ephemeral=True)
        else:
            view.votes[option_selected].add(user_id)
            view.voters[user_id] = option_selected
            await interaction.response.send_message(f"Voted for: **{option_selected}**", ephemeral=True)

        await view.update_embed(interaction.message)

class PollView(discord.ui.View):
    def __init__(self, question: str, options: List[str]) -> None:
        super().__init__(timeout=None)
        self.question: str = question
        self.votes: Dict[str, Set[int]] = {opt: set() for opt in options}
        self.voters: Dict[int, str] = {}

        # Track loaded button IDs to prevent duplicates
        seen_ids = set()
        for opt in options:
            btn_id = opt.lower().strip()
            if btn_id in seen_ids:
                continue
            seen_ids.add(btn_id)
            self.add_item(PollVoteButton(label=opt, custom_id=opt))

    def generate_embed(self) -> discord.Embed:
        total_votes = len(self.voters)
        embed = discord.Embed(title=f"📊 {self.question}", color=config.COLOR_INFO)
        
        for opt, users in self.votes.items():
            count = len(users)
            pct = (count / total_votes * 100) if total_votes > 0 else 0
            bar_length = int(pct // 10)
            progress_bar = "🟩" * bar_length + "⬛" * (10 - bar_length)
            embed.add_field(name=opt, value=f"{progress_bar} **{count}** votes ({pct:.1f}%)", inline=False)
            
        embed.set_footer(text=f"Total unique votes: {total_votes}")
        return embed

    async def update_embed(self, message: discord.Message) -> None:
        await message.edit(embed=self.generate_embed(), view=self)

class Polls(commands.GroupCog, name="poll"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.active_polls: Dict[int, PollView] = {}

    @app_commands.command(name="create", description="Generate a new interactive multi-option poll.")
    @app_commands.describe(question="The topic or question for the poll", options="Comma-separated options (e.g. Yes, No)")
    async def poll_create(self, interaction: discord.Interaction, question: str, options: str) -> None:
        # Deduplicate and trim list items cleanly
        raw_options = [opt.strip() for opt in options.split(",") if opt.strip()]
        parsed_options = []
        seen = set()
        
        for opt in raw_options:
            if opt.lower() not in seen:
                seen.add(opt.lower())
                parsed_options.append(opt)

        if len(parsed_options) < 2 or len(parsed_options) > 10:
            await interaction.response.send_message("❌ You must provide between 2 and 10 unique options.", ephemeral=True)
            return

        view = PollView(question, parsed_options)
        embed = view.generate_embed()
        
        await interaction.response.send_message(embed=embed, view=view)
        msg = await interaction.original_response()
        self.active_polls[msg.id] = view

    @app_commands.command(name="end", description="Conclude an ongoing poll and lock inputs.")
    @app_commands.describe(message_id="The Message ID of the poll you wish to close")
    async def poll_end(self, interaction: discord.Interaction, message_id: str) -> None:
        try:
            target_id = int(message_id)
        except ValueError:
            await interaction.response.send_message("❌ Invalid Message ID structure provided.", ephemeral=True)
            return

        if target_id not in self.active_polls:
            await interaction.response.send_message("❌ Poll not found or already terminated.", ephemeral=True)
            return

        view = self.active_polls[target_id]
        for item in view.children:
            if isinstance(item, discord.ui.Button):
                item.disabled = True
                
        try:
            msg = await interaction.channel.fetch_message(target_id)
            final_embed = view.generate_embed()
            final_embed.title = f"🔒 [CLOSED] {view.question}"
            final_embed.color = config.COLOR_ERROR
            await msg.edit(embed=final_embed, view=view)
            
            del self.active_polls[target_id]
            await interaction.response.send_message("✅ Poll closed successfully.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to terminate poll sequence: {e}", ephemeral=True)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Polls(bot))
