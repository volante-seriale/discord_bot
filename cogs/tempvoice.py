import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Dict, Any, Optional
import json
import os

#   ---- TempVoice Cog ----
class TempVoice(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_channels: Dict[int, int] = {}
        self.config_data: Dict[str, Any] = self._load_config_data()
        
    #   ---- Database (JSON) ----
    def _load_config_data(self) -> Dict[str, Optional[int]]:
        if not os.path.exists('data'):
            os.makedirs('data')
        try:
            with open('data/tempvoice_config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}
        except json.JSONDecodeError:
            print("Error: tempvoice_config.json corrupted, loaded in void.")
            return {}
    
    def _save_config_data(self):
        with open('data/tempvoice_config.json', 'w') as f:
            json.dump(self.config_data, f, indent=4)
    
    def get_guild_config(self, guild_id: int) -> Dict[str, Any]:
        default_config = {
            "creator_channel_id": None,
        }
        guild_id_str = str(guild_id)
        
        if guild_id_str not in self.config_data:
            self.config_data[guild_id_str] = default_config
            self._save_config_data()
        return self.config_data[guild_id_str]
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        guild_id_str = str(guild.id)
        if guild_id_str in self.config_data:
            del self.config_data[guild_id_str]
            self._save_config_data()
            print(f"TempVoice: Removed config for guild {guild.id} on bot removal.")
            
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.guild is None:
            return
        
        guild_id = str(member.guild.id)
        guild_config = self.get_guild_config(guild_id)
        creator_channel_id = guild_config["creator_channel_id"]
        
        # 1. Try to create a temp channel
        if after.channel and after.channel.id == creator_channel_id:
            if member.bot or creator_channel_id is None:
                return
            await self._create_temporary_channel(member, after.channel)
        
        # 2. Try to delete a temp channel
        if before.channel and before.channel.id in self.active_channels:
            await self._check_and_delete_channel(before.channel)
    
    async def _create_temporary_channel(self, member: discord.Member, source_channel: discord.VoiceChannel):
        guild = member.guild
        
        #defnine the new channel name/category
        new_channel_name = f"{member.display_name}'s Channel"
        category = source_channel.category
        try:    
            #create the new voice channel
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
                member: discord.PermissionOverwrite(manage_channels=True, connect=True, view_channel=True)
            }

            new_channel = await guild.create_voice_channel(
                name=new_channel_name,
                category=category,
                overwrites=overwrites,
                reason="Temporary voice channel creation.",
            )

            #move the member to the new channel
            await member.move_to(new_channel)

            #store the new channel in active channels
            self.active_channels[new_channel.id] = member.id
            print(f"TempVoice: Created temp channel {new_channel.id} for member {member.id} in guild {guild.id}.")

        except discord.Forbidden:
            print(f"TempVoice Error: Missing permissions to create channel in guild {guild.id}.")
            if member.voice and member.voice.channel == source_channel:
                await member.move_to(None)
        except Exception as e:
            print(f"TempVoice Error: {e} while creating temp channel in guild {guild.id}.")
    
    async def _check_and_delete_channel(self, channel: discord.VoiceChannel):
        if len(channel.members) == 0:
            try:
                await channel.delete(reason="Temporary voice channel deletion.")
                del self.active_channels[channel.id]
                print(f"TempVoice: Deleted temp channel {channel.id}.")
                
            except discord.Forbidden:
                print(f"TempVoice Error: Missing permissions to delete channel {channel.id}.")
            except Exception as e:
                print(f"TempVoice Error: {e} while deleting channel {channel.id}.")
            
            
#   ---- Setup function ----
async def setup(bot: commands.Bot):
    await bot.add_cog(TempVoice(bot))