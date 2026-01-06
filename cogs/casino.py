# cogs/casino.py
import discord
from discord.ext import commands
from discord import app_commands
import json
import os
from datetime import datetime
from typing import Dict, Optional

BUTTON_CUSTOM_ID = "casino:select_number"
APPROVE_CUSTOM_ID = "casino:approve"
REJECT_CUSTOM_ID = "casino:reject"

# ------------------- VALIDATION VIEW -------------------
class ValidationView(discord.ui.View):
    def __init__(self, user_id: int, number: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.number = number

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id=APPROVE_CUSTOM_ID)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_decision(interaction, approved=True)

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id=REJECT_CUSTOM_ID)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.handle_decision(interaction, approved=False)

    async def handle_decision(self, interaction: discord.Interaction, approved: bool):
        casino_cog = interaction.client.get_cog("Casino")
        if not casino_cog:
            return

        found = False
        for msg_id, data in list(casino_cog.pending_validations.items()):
            if (data["user_id"] == self.user_id and
                data["number"] == self.number and
                data["guild_id"] == interaction.guild.id):
                found = True
                message_id = data["message_id"]
                del casino_cog.pending_validations[msg_id]
                casino_cog._save_pending()
                break

        if not found:
            await interaction.response.send_message("This request has already been processed.", ephemeral=True)
            return

        user = interaction.guild.get_member(self.user_id)
        user_name = user.display_name if user else "Unknown user"

        if approved:
            casino_data = casino_cog.active_casinos.get(message_id)
            if casino_data:
                casino_data["assignments"][self.number] = str(self.user_id)
                casino_cog._save_casinos()

                channel = interaction.guild.get_channel(casino_data["channel_id"])
                if channel:
                    try:
                        msg = await channel.fetch_message(message_id)
                        occupied = len(casino_data["assignments"])
                        new_embed = casino_cog._build_party_embed(casino_data, interaction.guild, occupied)
                        await msg.edit(embed=new_embed)
                    except:
                        pass

            await interaction.response.send_message(f"✅ Number **{self.number}** approved for {user_name}!", ephemeral=True)
            if user:
                try:
                    await user.send(f"✅ Your number **{self.number}** for the Casino has been **approved** by the staff!")
                except:
                    pass
        else:
            await interaction.response.send_message(f"❌ Number **{self.number}** rejected for {user_name}.", ephemeral=True)
            if user:
                try:
                    await user.send(f"❌ Your number **{self.number}** for the Casino has been **rejected** by the staff. Try another one!")
                except:
                    pass

        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)


# ------------------- MODAL -------------------
class CasinoSelectModal(discord.ui.Modal, title="Choose your lucky number"):
    numero = discord.ui.TextInput(
        label="Enter the number (1-100)",
        placeholder="Example: 77",
        min_length=1,
        max_length=3,
        style=discord.TextStyle.short
    )

    def __init__(self, casino_cog: "Casino", message_id: int, casino_data: Dict):
        super().__init__()
        self.casino_cog = casino_cog
        self.message_id = message_id
        self.casino_data = casino_data

    async def on_submit(self, interaction: discord.Interaction):
        if self.message_id not in self.casino_cog.active_casinos:
            await interaction.response.send_message("This Casino event has been closed.", ephemeral=True)
            return

        try:
            num = int(self.numero.value.strip())
            if not (1 <= num <= 100):
                raise ValueError
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number between 1 and 100.", ephemeral=True)
            return

        num_str = str(num)
        assignments = self.casino_data["assignments"]

        if num_str in assignments:
            owner = interaction.guild.get_member(int(assignments[num_str]))
            owner_name = owner.display_name if owner else "someone"
            await interaction.response.send_message(f"❌ The number **{num}** has already been taken by {owner_name}.", ephemeral=True)
            return

        # --- VALIDATION LOGIC ---
        validation_channel_id = self.casino_cog.get_validation_channel(interaction.guild.id)
        if validation_channel_id:
            validation_channel = interaction.guild.get_channel(validation_channel_id)
            if validation_channel and isinstance(validation_channel, discord.TextChannel):
                await interaction.response.send_message(
                    f"⏳ Your request for number **{num}** has been sent to the staff for approval.",
                    ephemeral=True
                )

                embed = discord.Embed(
                    title="🎰 Casino Validation Request",
                    description=f"**User:** {interaction.user.mention} ({interaction.user.display_name})\n"
                                f"**Requested number:** {num}\n"
                                f"**Event:** {self.casino_data['data_ora']}",
                    color=discord.Color.orange(),
                    timestamp=datetime.now()
                )
                embed.set_thumbnail(url=interaction.user.display_avatar.url)
                embed.add_field(
                    name="Event Link",
                    value=f"[Go to event](https://discord.com/channels/{interaction.guild.id}/{self.casino_data['channel_id']}/{self.message_id})",
                    inline=False
                )

                view = ValidationView(interaction.user.id, num_str)
                val_msg = await validation_channel.send(embed=embed, view=view)

                self.casino_cog.pending_validations[val_msg.id] = {
                    "message_id": self.message_id,
                    "user_id": interaction.user.id,
                    "number": num_str,
                    "guild_id": interaction.guild.id
                }
                self.casino_cog._save_pending()
                return

        # --- DIRECT ASSIGNMENT IF NO VALIDATION ---
        assignments[num_str] = str(interaction.user.id)
        occupied = len(assignments)
        embed = self.casino_cog._build_party_embed(self.casino_data, interaction.guild, occupied)

        await interaction.response.edit_message(embed=embed)
        await interaction.followup.send(f"✅ You have taken the number **{num}**!", ephemeral=True)
        self.casino_cog._save_casinos()


# ------------------- BUTTON VIEW -------------------
class CasinoButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Choose Number", style=discord.ButtonStyle.green, emoji="🎰", custom_id=BUTTON_CUSTOM_ID)
    async def select_number(self, interaction: discord.Interaction, button: discord.ui.Button):
        message_id = interaction.message.id
        casino_cog = interaction.client.get_cog("Casino")
        if not casino_cog or message_id not in casino_cog.active_casinos:
            await interaction.response.send_message("Event does not exist or has been closed.", ephemeral=True)
            return

        casino_data = casino_cog.active_casinos[message_id]
        if len(casino_data["assignments"]) >= 100 and casino_cog.get_validation_channel(interaction.guild.id) is None:
            await interaction.response.send_message("❌ All numbers have already been taken!", ephemeral=True)
            return

        modal = CasinoSelectModal(casino_cog, message_id, casino_data)
        await interaction.response.send_modal(modal)


# ------------------- COG -------------------
class Casino(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_casinos: Dict[int, Dict] = self._load_casinos()
        self.pending_validations: Dict[int, Dict] = self._load_pending()
        self.validation_channels: Dict[str, int] = self._load_validation_channels()
        self._register_persistent_views()

    # --- FILE MANAGEMENT ---
    def _load_casinos(self) -> Dict[int, Dict]:
        path = 'data/casino_events.json'
        if os.path.exists(path):
            with open(path, 'r') as f:
                return {int(k): v for k, v in json.load(f).items()}
        return {}

    def _save_casinos(self):
        with open('data/casino_events.json', 'w') as f:
            json.dump(self.active_casinos, f, indent=4)

    def _load_pending(self) -> Dict[int, Dict]:
        path = 'data/casino_pending.json'
        if os.path.exists(path):
            with open(path, 'r') as f:
                return {int(k): v for k, v in json.load(f).items()}
        return {}

    def _save_pending(self):
        with open('data/casino_pending.json', 'w') as f:
            json.dump(self.pending_validations, f, indent=4)

    def _load_validation_channels(self) -> Dict[str, int]:
        path = 'data/casino_validation_channels.json'
        if os.path.exists(path):
            with open(path, 'r') as f:
                return json.load(f)
        return {}

    def _save_validation_channels(self):
        with open('data/casino_validation_channels.json', 'w') as f:
            json.dump(self.validation_channels, f, indent=4)

    def get_validation_channel(self, guild_id: int) -> Optional[int]:
        return self.validation_channels.get(str(guild_id))

    # --- PERSISTENT VIEWS ---
    def _register_persistent_views(self):
        self.bot.add_view(CasinoButton())
        self.bot.add_view(ValidationView(user_id=0, number="0"))  # dummy instance

    # --- EMBED ---
    def _build_party_embed(self, casino_data: Dict, guild: discord.Guild, occupied: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"🎰 Casino Night - {casino_data['data_ora']}",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        creator = guild.get_member(casino_data['creator_id'])
        embed.set_footer(text=f"Created by {creator.display_name if creator else 'Unknown'}")

        cost = casino_data.get("cost", 0)
        base = f"**Numbers taken: {occupied}/100**\nClick the button below to choose your number!"

        if cost > 0:
            embed.description = f"💰 **Entry cost: {cost}€**\n\n{base}"
        else:
            embed.description = f"🎟️ **Free entry**\n\n{base}"

        assignments = casino_data["assignments"]
        for party_num, (start, end) in enumerate([(1,34), (35,67), (68,100)], 1):
            lines = []
            for n in range(start, end+1):
                ns = str(n)
                if ns in assignments:
                    member = guild.get_member(int(assignments[ns]))
                    lines.append(f"✅ {n}. {member.mention if member else 'Unknown'}")
                else:
                    lines.append(f"⬜ {n}. Free")
            embed.add_field(name=f"Party {party_num}", value="\n".join(lines), inline=True)
        return embed

    # --- COMMANDS ---
    @commands.hybrid_command(name="casino", description="Create a Casino Night event")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        date_time="Date and time of the event DD/MM/YY 20:00)",
        entry_cost="Entry cost (default: 0 for free)",
        channel="Channel to post the event (default: current channel)"
    )
    async def casino(self, ctx: commands.Context, date_time: str, entry_cost: int = 0, channel: Optional[discord.TextChannel] = None):
        channel = channel or ctx.channel
        embed = self._build_party_embed({"data_ora": date_time, "assignments": {}, "creator_id": ctx.author.id}, ctx.guild, 0)
        view = CasinoButton()
        msg = await channel.send(embed=embed, view=view)

        self.active_casinos[msg.id] = {
            "channel_id": channel.id,
            "guild_id": ctx.guild.id,
            "data_ora": date_time,
            "assignments": {},
            "creator_id": ctx.author.id,
            "cost": entry_cost,
        }
        self._save_casinos()
        await ctx.send(f"Casino event created in {channel.mention}!", ephemeral=True)

    @commands.hybrid_command(name="casino-set-validation-channel", description="Set/remove the channel for Casino validations")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(channel="Text channel for validations (leave empty to remove)")
    async def set_validation_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        gid = str(ctx.guild.id)
        if channel is None:
            if gid in self.validation_channels:
                del self.validation_channels[gid]
                self._save_validation_channels()
                await ctx.send("Validation channel removed.", ephemeral=True)
            else:
                await ctx.send("No validation channel configured.", ephemeral=True)
        else: 
            self.validation_channels[gid] = channel.id
            self._save_validation_channels()
            await ctx.send(f"Validation channel set to {channel.mention}", ephemeral=True)

    @commands.hybrid_command(name="close-casino", description="Manually close a Casino event")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(message_id="Message ID of the Casino event to close")
    async def close_casino(self, ctx: commands.Context, message_id: str):
        message_id = int(message_id)
        if message_id not in self.active_casinos:
            await ctx.send("No active event found with that message ID.", ephemeral=True)
            return
        data = self.active_casinos[message_id]
        channel = ctx.guild.get_channel(data["channel_id"])
        if not channel:
            await ctx.send("Channel not found.", ephemeral=True)
            return
        try:
            msg = await channel.fetch_message(message_id)
            embed = msg.embeds[0]
            embed.color = discord.Color.red()
            embed.title = f"❌ Casino Night - {data['data_ora']} (CLOSED)"
            view = CasinoButton()
            for child in view.children:
                child.disabled = True
            await msg.edit(embed=embed, view=view)
            del self.active_casinos[message_id]
            self._save_casinos()
            await ctx.send("Event closed successfully.", ephemeral=True)
        except:
            await ctx.send("Message not found.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Casino(bot))