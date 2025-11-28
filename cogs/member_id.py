import discord
from discord.ext import commands

class RoleIDListerHybrid(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="list-id", description="Lists the IDs of all members with a specified role.")
    @commands.has_permissions(administrator=True)
    async def list_member_ids(self, ctx: commands.Context, target_role: discord.Role):     
        
        # 1. Defer the response
        await ctx.defer(ephemeral=False)

        if ctx.guild is None:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        # 2. Member ID extraction
        member_ids = []
        for member in target_role.members:
            member_ids.append(str(member.id))
        
        # 3. Response message
        if member_ids:
            id_list_text = "\n".join(member_ids)
            response_message = (
                f"✅ Found **{len(member_ids)}** members with the role: **{target_role.name}**:\n"
                f"```\n{id_list_text}\n```"
            )
        else:
            response_message = f"🤔 No members found with the role: **{target_role.name}**."

        # Sends the response
        await ctx.send(response_message)

#   ---- Cog setup ----
async def setup(bot: commands.Bot):
    await bot.add_cog(RoleIDListerHybrid(bot))
