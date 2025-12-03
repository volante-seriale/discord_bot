import discord
from discord.ext import commands
from discord import app_commands

class GlobalCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Tests the bot's responsiveness")
    async def ping(self, interaction: discord.Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(f"**Pong!** | Latency: **{latency}ms**")

    @app_commands.command(name="serverinfo", description="Displays basic information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("This command must be used in a server.")

        leveling_cog = self.bot.get_cog("Leveling")
        invite_link = "Not set"
        if leveling_cog:
            config = leveling_cog.get_guild_config(str(guild.id))
            if config.get("invite_link"):
                invite_link = config["invite_link"]

        embed = discord.Embed(title=f"Info about {guild.name}", color=discord.Color.blue())
        embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Server ID", value=guild.id, inline=False)
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:D>", inline=False)
        embed.add_field(name="Invite Link", value=invite_link, inline=False)

        await interaction.response.send_message(embed=embed)

    @commands.hybrid_command(name="sync", description="Force sync slash commands (owner only)")
    @commands.is_owner()
    async def sync(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"Synced {len(synced)} commands globally.", ephemeral=True)
        except Exception as e:
            await ctx.send(f"Sync failed: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(GlobalCommands(bot))