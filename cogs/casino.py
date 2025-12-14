import discord
from discord.ext import commands
from typing import Dict, Any, Optional
import random

class Casino(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    
    @commands.hybrid_command(name="lucky-number", description="Generates a random number between 2 given numbers")
    @commands.has_permissions(administrator=True)
    async def generate_number(self, ctx: commands.Context, min_num: int, max_num: int):
        random_number = random.randint(min_num, max_num)
        await ctx.defer(ephemeral=False)

        if ctx.guild is None:
            await ctx.send("This command must be used in a server.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="🎲 Your Lucky Number 🎲",
            color=discord.Color.orange()
        )
        embed.add_field(name="Minimum", value=f"{min_num}", inline=True)
        embed.add_field(name="Maximum", value=f"{max_num}", inline=True)
        embed.add_field(name="Generated number", value=f"**{random_number}**", inline=True)
        
        await ctx.send(f"Requested by: {ctx.author.mention}",embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(Casino(bot))