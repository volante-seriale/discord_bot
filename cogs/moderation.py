import discord
import os
import json
from discord.ext import commands
from typing import Dict, Any, Optional

class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not os.path.exists('data'):
            os.makedirs('data')
        self.config_data: Dict[str, Any] = self._load_config_data()

#   ---- Database (JSON) ----
    def _load_config_data(self) -> Dict[str, Optional[int]]:
        try:
            with open('data/moderation_config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            print("Error: JSON decode error in moderation_config.json. Using empty config.")
            return {}
    
    def _save_config_data(self):
        with open('data/moderation_config.json', 'w') as f:
            json.dump(self.config_data, f, indent=4)
            
    def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        default_config = {
            "exit_channel_id": None
        }
        guild_id_str = str(guild_id)
        
        if guild_id_str not in self.config_data:
            self.config_data[guild_id_str] = default_config
            self._save_config_data()
        return self.config_data[guild_id_str]
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        guild_id_str = str(guild.id)
        if guild_id_str in self.config_data:
            del self.config_data[guild_id_str]
            self._save_config_data()
            print(f"Mod: Removed config for guild {guild.name} ({guild.id}) on leave.")
            
    #   ---- Event listener: Member Leave ----
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.guild is None or member.bot:
            return
        
        guild_id = member.guild.id
        guild_config = self.get_guild_config(guild_id)
        exit_channel_id = guild_config.get("exit_channel_id")
        
        if exit_channel_id is not None:
            exit_channel = member.guild.get_channel(exit_channel_id)
            if isinstance(exit_channel, discord.TextChannel):
                try:
                    await exit_channel.send(f"👋 {member.mention} has left the server.")
                except discord.Forbidden:
                    print(f"Mod: Missing permissions to send messages in channel for guild {member.guild.name} ({guild_id}).")
                except Exception as e:
                    print(f"Mod: Error sending leave message in guild {member.guild.name} ({guild_id}): {e}")
            else:
                print(f"Mod: Exit channel ID {exit_channel_id} is not a text channel in guild {member.guild.name} ({guild_id}).")

    #   ---- Slash Commad: /config-exit-channel ----
    @commands.hybrid_command(name="config-exit-channel", description="Sets the channel for member leave messages.")
    @commands.has_permissions(administrator=True)
    async def config_exit_channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        if ctx.guild is None:
            return await ctx.send("This command must be used in a server.", ephemeral=True)
        
        guild_id = ctx.guild.id
        config = self.get_guild_config(guild_id)
        
        if channel is None:
            current_id = config.get("exit_channel_id")
            channel_mention = f"<#{current_id}>" if current_id else "**not set**"
            
            embed = discord.Embed(
                title="Exit Message Configuration",
                description="Channel where the bot announces when a member leaves the server.",
                color=discord.Color.dark_red()
            )
            embed.add_field(name="Current Exit Channel", value=channel_mention, inline=False)
            return await ctx.send(embed=embed, ephemeral=True)
        
        else:
            config["exit_channel_id"] = channel.id
            self._save_config_data()
            await ctx.send(f"✅ Exit message channel set to **{channel.mention}**.", ephemeral=True)

#   ---- Setup function ----
async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))