import discord
from discord import app_commands
from discord.ext import commands
import io

class RoleIDListerHybrid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="list-id", description="Lists the IDs of all members with a specified role.")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(target_role="The role to list member IDs for")
    async def list_member_ids(self, ctx: commands.Context, target_role: discord.Role):     
        
        # 1. Defer the response
        await ctx.defer(ephemeral=False)

        if ctx.guild is None:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        # 2. Member ID extraction
        member_info = []
        for member in target_role.members:
            member_info.append(f"ID: {member.id} | Name: {member.display_name} ")
        member_count = len(member_info)

        # 3. File Creation and Sending
        if member_info:
            
            file_content = "\n".join(member_info)
            buffer = io.StringIO(file_content)
            
            filename = f"members_{target_role.name.replace(' ', '_')}_ids.txt"
            discord_file = discord.File(buffer, filename=filename)

            embed = discord.Embed(
                title=f"✅ Member List for Role: {target_role.name}",
                description=f"Found **{member_count}** members. The list of names and IDs is attached below.",
                color=discord.Color.green()
            )
            
            await ctx.send(embed=embed, file=discord_file)
            
        else:
            response_message = f"🤔 No members found with the role: **{target_role.name}**."
            await ctx.send(response_message)

#   ---- Cog setup ----
async def setup(bot: commands.Bot):
    await bot.add_cog(RoleIDListerHybrid(bot))