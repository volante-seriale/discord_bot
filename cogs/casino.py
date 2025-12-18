# cogs/casino.py
import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from typing import Dict, Optional

BUTTON_CUSTOM_ID = "casino:select_number"

class CasinoSelectModal(discord.ui.Modal, title="Choose your lucky number"):
    numero = discord.ui.TextInput(
        label="Enter the number (1-100)",
        placeholder="Example: 77",
        min_length=1,
        max_length=3,
        style=discord.TextStyle.short
    )

    def __init__(self, casino_cog: "Casino", message_id: int):
        super().__init__()
        self.casino_cog = casino_cog
        self.message_id = message_id

    async def on_submit(self, interaction: discord.Interaction):
        if self.message_id not in self.casino_cog.active_casinos:
            await interaction.response.send_message("This Casino event has been closed.", ephemeral=True)
            return

        try:
            num = int(self.numero.value.strip())
            if not (1 <= num <= 100):
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Enter a valid number between 1 and 100.", ephemeral=True)
            return

        num_str = str(num)
        casino_data = self.casino_cog.active_casinos[self.message_id]
        assignments = casino_data["assignments"]

        if num_str in assignments:
            owner = interaction.guild.get_member(int(assignments[num_str]))
            owner_name = owner.display_name if owner else "someone"
            await interaction.response.send_message(f"❌ The number **{num}** has already been chosen by {owner_name}.", ephemeral=True)
            return

        assignments[num_str] = str(interaction.user.id)

        occupied = len(assignments)
        embed = self.casino_cog._build_party_embed(casino_data, interaction.guild, occupied)

        if occupied == 100:
            for item in interaction.message.components:
                for child in item.children:
                    if child.custom_id == BUTTON_CUSTOM_ID:
                        child.disabled = True

        await interaction.response.edit_message(embed=embed)

        await interaction.followup.send(f"✅ You've taken the lucky number **{num}**!", ephemeral=True)

        self.casino_cog._save_casinos()


class CasinoButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Choose Number", style=discord.ButtonStyle.green, emoji="🎰", custom_id=BUTTON_CUSTOM_ID)
    async def select_number(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = interaction.message.id
        casino_cog = interaction.client.get_cog("Casino")

        if not casino_cog or message_id not in casino_cog.active_casinos:
            await interaction.response.send_message("This Casino event does not exist or has been closed.", ephemeral=True)
            return

        casino_data = casino_cog.active_casinos[message_id]
        if len(casino_data["assignments"]) >= 100:
            await interaction.response.send_message("❌ All numbers have already been chosen!", ephemeral=True)
            return

        modal = CasinoSelectModal(casino_cog, message_id)
        await interaction.response.send_modal(modal)


class Casino(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_casinos: Dict[int, Dict] = self._load_casinos()
        self._register_persistent_views()

    def _load_casinos(self) -> Dict[int, Dict]:
        if not os.path.exists('data'):
            os.makedirs('data')
        try:
            with open('data/casino_events.json', 'r') as f:
                return {int(k): v for k, v in json.load(f).items()}
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_casinos(self):
        with open('data/casino_events.json', 'w') as f:
            json.dump(self.active_casinos, f, indent=4)

    def _register_persistent_views(self):
        if not self.active_casinos:
            return
        for _ in self.active_casinos.keys():
            self.bot.add_view(CasinoButton())

    def _build_party_embed(self, casino_data: Dict, guild: discord.Guild, occupied: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"Casino Night - {casino_data['data_ora']}",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        embed.set_footer(text=f"Event created by {guild.get_member(casino_data['creator_id']).display_name if guild.get_member(casino_data['creator_id']) else 'Unknown'}")

        costo = casino_data.get('cost', None)  # Recupera il costo, se presente
        base_description = f"**Numbers taken: {occupied}/100**\nClick the button to choose a free number!"

        if costo:
            embed.description = f"💰 **Entry cost: {costo}**\n\n{base_description}"
        else:
            embed.description = base_description

        assignments = casino_data["assignments"]

        party_ranges = [
            (1, 30),   
            (31, 60),  
            (61, 90)  
        ]

        for party_num, (start, end) in enumerate(party_ranges, start=1):
            lines = []
            for num in range(start, end + 1):
                num_str = str(num)
                if num_str in assignments:
                    member = guild.get_member(int(assignments[num_str]))
                    name = member.mention if member else "Unknown"
                    lines.append(f"✅ {num}. {name}")
                else:
                    lines.append(f"⬜ {num}. Free")
            value = "\n".join(lines)
            embed.add_field(
                name=f"Party {party_num}",
                value=value,
                inline=True
            )
        return embed

    @commands.hybrid_command(name="casino", description="Creates an event 'Casino'")
    @commands.has_permissions(administrator=True)
    async def casino(
        self,
        ctx: commands.Context,
        dateTime: str,
        entry_cost: int = 0,
        canale: Optional[discord.TextChannel] = None
    ):
        canale = canale or ctx.channel

        embed = self._build_party_embed(
            {"data_ora": dateTime, "assignments": {}, "creator_id": ctx.author.id},
            ctx.guild,
            0
        )

        view = CasinoButton()
        msg = await canale.send(embed=embed, view=view)

        self.active_casinos[msg.id] = {
            "channel_id": canale.id,
            "guild_id": ctx.guild.id,
            "data_ora": dateTime,
            "assignments": {},
            "creator_id": ctx.author.id,
            "cost": entry_cost,
        }
        self._save_casinos()

        await ctx.send(f"'Casino' event created in {canale.mention} for **{dateTime}**!", ephemeral=True)

    @commands.hybrid_command(name="close-casino", description="Manually closes an active Casino event")
    @commands.has_permissions(administrator=True)
    async def close_casino(self, ctx: commands.Context, message_id: int):
        if message_id not in self.active_casinos:
            return await ctx.send("No active Casino event found with this message ID.", ephemeral=True)
        channel = ctx.guild.get_channel(self.active_casinos[message_id]["channel_id"])
        if not channel or not isinstance(channel, discord.TextChannel):
            return await ctx.send("Channel not found.", ephemeral=True)

        try:
            msg = await channel.fetch_message(message_id)

            disabled_view = CasinoButton()
            for item in disabled_view.children:
                if item.custom_id == BUTTON_CUSTOM_ID:
                    item.disabled = True

            embed = msg.embeds[0]
            embed.color = discord.Color.red()
            embed.title = f"❌ Casino Night - {self.active_casinos[message_id]['data_ora']} (CLOSED)"
            embed.description = "Event closed."

            await msg.edit(embed=embed, view=disabled_view)

            del self.active_casinos[message_id]
            self._save_casinos()

            await ctx.send("'Casino' event closed successfully.", ephemeral=True)
        except discord.NotFound:
            await ctx.send("Message not found.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Casino(bot))