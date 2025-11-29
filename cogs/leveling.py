import discord
from discord.ext import commands
import json
from typing import Dict, Any, Optional
import os

Xp_Message = 1
LEVEL_THRESHOLDS: Dict[int, int] = {
    1:15,   #level 1 at 15xp (15 messages)
    2:100,  #level 2 at 100xp (100 messages) etc
    3:300,
    4:500,
    5:1500, #MAX level
}

ROLE_ASSIGNMENTS: Dict[int,int] = {
    1:1439044854477750272,
    2:1439044982836039852,
    3:1439045020761063646,
    4:1439044973642256384,
    5:1439045087848829080
} # will be overwritten

MAX_LEVEL = max(LEVEL_THRESHOLDS.keys())
MAX_XP_TOTAL = LEVEL_THRESHOLDS[MAX_LEVEL]
LEVEL_UP_CHANNEL_ID = 1439200176408363059 # will be overwritten

def get_level_info(total_xp: int) -> tuple[int,int]:
    actual_level = 0
    xp_needed = 0
    for level, threshold_xp in LEVEL_THRESHOLDS.items():
        if total_xp >= threshold_xp:
            actual_level = level
        else: 
            xp_needed = threshold_xp
            return actual_level, xp_needed
    
    #If the user xp is equal or greater than max xp
    return MAX_LEVEL, 0

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not os.path.exists('data'):
            os.makedirs('data')
        self.level_data: Dict[str, Dict[str, Any]] = self._load_level_data()
        self.config_data: Dict[str, Any] = self._load_config_data()
    
    
#   ---- Database(JSON) ----
    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        guild_id = str(guild.id)

        # Rimuove i dati di livellamento per quella gilda
        if guild_id in self.level_data:
            del self.level_data[guild_id]
            self._save_level_data()
            print(f"Mod: Removed config for guild {guild.name} ({guild.id}) on leave.")

        # Rimuove i dati di configurazione per quella gilda
        if guild_id in self.config_data:
            del self.config_data[guild_id]
            self._save_config_data()
            print(f"Mod: Removed config for guild {guild.name} ({guild.id}) on leave.")
    #Xp load
    def _load_level_data(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open('data/levels.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return{}
        except json.JSONDecodeError:
            print("Error: JSON decode error in levels.json. Using empty config.")
            return{}
        
    def _save_level_data(self):
        with open ('data/levels.json', 'w') as f:
            json.dump(self.level_data, f, indent=4)

    #Config load
    def _load_config_data(self) -> Dict[str, Any]:
        try:
            with open('data/config.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return{}
        except json.JSONDecodeError:
            print("Error: JSON decode error in config.json. Using empty config.")
            return{}
        
    def _save_config_data(self):
        with open('data/config.json', 'w') as f:
            json.dump(self.config_data, f, indent=4)
    
    def get_guild_config(self, guild_id:str) -> Dict[str,Any]:
        default_config = {
            "level_up_channel_id": None,
            "invite_link": None,
            "role_assignments": {str(lvl): None for lvl in LEVEL_THRESHOLDS.keys()},
            "is_active": True,
            "backgroundT_status": True,
        }
        if guild_id not in self.config_data:
            self.config_data[guild_id] = default_config
            self._save_config_data()
        return self.config_data[guild_id]
    
#   ---- Event listener: Xp assign ----
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or message.content.startswith(self.bot.command_prefix):
            return
        
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        #Loads specifc guild config
        guild_config = self.get_guild_config(guild_id)
        
        if not guild_config.get("is_active", True):
            return
        
        role_assignments = {int(lvl): int(role_id) for lvl, role_id in guild_config["role_assignments"].items() if role_id is not None}
        level_up_channel_id = guild_config["level_up_channel_id"]
        
        #1. Inizialize (saving total and needed xp)
        if guild_id not in self.level_data:
            self.level_data[guild_id] = {}
        if user_id not in self.level_data[guild_id]:
            self.level_data[guild_id][user_id] = {"total_xp": 0, "level": 0}
            
        user_data = self.level_data[guild_id][user_id]
        
        #2. Add xp (if not max_level)
        if user_data["level"] < MAX_LEVEL:
            user_data["total_xp"] += Xp_Message
        
        #3.Level check
        new_level, _ = get_level_info(user_data["total_xp"])
        actual_level = user_data["level"]
        
        if new_level > actual_level:
            user_data["level"] = new_level
            self._save_level_data() #Instantly saves after level-up
            
            if level_up_channel_id is None:
                print(f"Warning: Level-up channel not configured for {message.guild.name}")
                target_channel = message.channel
            else:
                level_up_channel = message.guild.get_channel(level_up_channel_id)
                target_channel = level_up_channel if level_up_channel else message.channel
            
            congrats_message = f"**Congrats, {message.author.mention}!** \nYou reached the **Level {new_level}** "
            
            if new_level in ROLE_ASSIGNMENTS:
                role_id = ROLE_ASSIGNMENTS[new_level]
                role = message.guild.get_role(role_id)
        
                if role:
                    try:
                        # 1. Assing new role
                        await message.author.add_roles(role, reason="Automatic Level Up")

                        # 2. Remove previous role
                        prev_role_id = ROLE_ASSIGNMENTS.get(actual_level)
                        if prev_role_id and prev_role_id != role_id:
                            prev_role = message.guild.get_role(prev_role_id)
                            if prev_role and prev_role in message.author.roles:
                                await message.author.remove_roles(prev_role, reason="Removed previous level-role")

                        congrats_message +=f"and earned the role **{role.name}**"
                        
                    except discord.Forbidden:
                        print(f"Error: Missing permission to add {role.name} on the server {message.guild.name}.")
                    except Exception as e:
                        print(f"Error assigning role to {message.author}: {e}")
                else:
                    print(f"Warning: Role with ID {role_id} is missing on the server {message.guild.name}.")
    
        # If level increases but no there's no level-role, sends defaul message
            try:
                await target_channel.send(congrats_message)
            except discord.Forbidden:
                pass
             
        # If there's no level-up, just saves data
        else:
            self._save_level_data()
            
            
#   ---- Slash Commands: /level ----
    @commands.hybrid_command(name="level", description="show your actual level and xp")
    async def level_command(self, ctx: commands.Context, member: discord.Member = None):
        if ctx.guild is None:
            await ctx.send ("This command must be sent in a server.")
            return
        
        target = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(target.id)
        
        if guild_id not in self.level_data or user_id not in self.level_data[guild_id]:
            await ctx.send(f"**{target.mention}** hasn't ernead xp in this server")
            return
        
        user_data = self.level_data[guild_id][user_id]
        level = user_data["level"]
        total_xp = user_data["total_xp"]
        
        #Use new function to define status
        current_level, xp_needed = get_level_info(total_xp)
        
        #Calculates xp in actual_level
        xp_prev_level = 0
        if current_level > 1 and (current_level-1) in LEVEL_THRESHOLDS:
            # To avoid KeyError 
            xp_prev_level = LEVEL_THRESHOLDS[current_level-1] # Use previous level 
            
        #Recalculates progression
        if current_level == MAX_LEVEL:
            xp_needed = 0
        else:
            xp_needed = LEVEL_THRESHOLDS[current_level+1]
        
        xp_to_next_level = xp_needed - total_xp if xp_needed > 0 else 0
                
        xp_in_actual_level = total_xp - xp_prev_level
        xp_needed_total_in_level = xp_needed - xp_prev_level if xp_needed > 0 else 1
        
        #Calculates the advancement percentage
        progress = (xp_in_actual_level / xp_needed_total_in_level) * 100 if xp_needed_total_in_level > 0 else 100
        progress_bar_length = 10
        filled_block = int(progress * progress_bar_length // 100)
        progress_bar = "🟦" * filled_block + "⬛" * (progress_bar_length - filled_block)
        
        embed = discord.Embed(
            title=f"Level and Xp {target.display_name}",
            color=discord.Color.blue() if level < MAX_LEVEL else discord.Color.purple()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Actual level", value=f"**{level}** (Max: {MAX_LEVEL})", inline=True)
        embed.add_field(name="Total Xp", value=f"**{total_xp}**", inline=True)
        
        if level < MAX_LEVEL:
            embed.add_field(name="Xp to next level", value=f"**{xp_to_next_level}**", inline=True)
            embed.add_field(name="Progression", value=f"[{progress_bar}] ({progress:.2f}%)", inline=False)
        else:
            embed.add_field(name="State", value=f"🎉 **Max level reached**", inline=True)
            embed.add_field(name="Progress", value="`[🟦🟦🟦🟦🟦🟦🟦🟦🟦🟦]` (100.00%)", inline=False) 
        
        embed.set_footer(text=f"User Id: {target.id}")
        await ctx.send(embed=embed)
        
#   ---- Slash Commands: /config-show ----
    @commands.hybrid_command(name="config-show", description="Displays current configuration")
    @commands.has_permissions(administrator=True)
    async def show_config(self, ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send("This command must be sent in a server")
            return

        guild_id = str(ctx.guild.id)
        config = self.get_guild_config(guild_id)

        moderation_cog = self.bot.get_cog("Moderation")
        
        TempVoice_cog = self.bot.get_cog("TempVoice")
        
        if moderation_cog:
            mod_config = moderation_cog.get_guild_config(ctx.guild.id)
            exit_channel_id = mod_config.get("exit_channel_id")
            exit_channel_mention = f"<#{exit_channel_id}>" if exit_channel_id else "Not configured"
        else:
            exit_channel_mention = "Moderation cog not loaded"
            
        if TempVoice_cog:
            voice_config = TempVoice_cog.get_guild_config(ctx.guild.id)
            creator_channel_id = voice_config.get("creator_channel_id")
            creator_channel_mention = f"<#{creator_channel_id}>" if creator_channel_id else "Not configured"
        else:
            creator_channel_mention = "❌ TempVoice cog not loaded"

        embed = discord.Embed(
            title="Leveling Configuration",
            color=discord.Color.gold()
        )

        #Invite link
        invite_link = config.get("invite_link","N/A")
        embed.add_field(name="Server Invite Link", value=f"```\n{invite_link}\n```", inline=False)

        #Level-up Channel
        channel_id = config.get("level_up_channel_id")
        channel_mention = f"<#{channel_id}>" if channel_id else "Not configured"
        embed.add_field(name="Level-up Channel", value=channel_mention, inline=True)
        
        #Level-roles
        role_info = []
        for level, role_id in config["role_assignments"].items():
            role_mention = f"<@&{role_id}>" if role_id else "Not configured"
            role_info.append(f"Level **{level}**: {role_mention}")
        embed.add_field(name="Level Roles", value="\n".join(role_info), inline=False)
        
        #Voice Creator Channel
        embed.add_field(name="Voice Creator Channel", value=creator_channel_mention, inline=True)
        
        #Exit Channel
        embed.add_field(name="Member Leave Channel", value=exit_channel_mention, inline=True)
        
        #Send embed
        await ctx.send(embed=embed, ephemeral=False)

#   ---- Slash Commands: /config ----
    @commands.hybrid_command(name="config", description="Configure every needed settings (channel, invite, level roles etc.).")
    @commands.has_permissions(administrator=True)
    async def configure_all(
        self, 
        ctx: commands.Context, 
        level_up_channel: Optional[discord.TextChannel] = None, 
        invite_link: Optional[str] = None, 
        role_level_1: Optional[discord.Role] = None,  # Role per level 1
        role_level_2: Optional[discord.Role] = None,  # Role per level 2
        role_level_3: Optional[discord.Role] = None,  # Role per level 3
        role_level_4: Optional[discord.Role] = None,  # Role per level 4
        role_level_5: Optional[discord.Role] = None,  # Role per level 5 (MAX)
        exit_channel: Optional[discord.TextChannel] = None, # Exit channel
        voice_creator_channel: Optional[discord.VoiceChannel] = None # Voice creator channel
    ):
        if ctx.guild is None:
            return await ctx.send("This command must be used in a server", ephemeral=True)
        
        guild_id = str(ctx.guild.id)
        config = self.get_guild_config(guild_id)
        updated_settings = []
        
        moderation_cog = self.bot.get_cog("Moderation")
        
        voice_temp_cog = self.bot.get_cog("TempVoice")
        
        # Map role value to levels
        role_params = {
            1: role_level_1, 
            2: role_level_2, 
            3: role_level_3, 
            4: role_level_4, 
            5: role_level_5
        }
        
        # 1. Config level-up channel
        if level_up_channel is not None:
            config["level_up_channel_id"] = level_up_channel.id
            updated_settings.append(f"Channel level-up set to: **{level_up_channel.mention}**")
        
        # 2. Config invite link
        if invite_link is not None:
            if not invite_link.startswith("http") and not invite_link.startswith("discord.gg/"):
                 return await ctx.send("❌ Invalid link. Must start with 'http' or 'discord.gg/'.", ephemeral=True)
                 
            config["invite_link"] = invite_link
            updated_settings.append(f"Invite link set to: `{invite_link}`")
            
        # 3. Config level-role
        for level, role in role_params.items():
            if role is not None:
                # Check on @everyone
                if role.id == ctx.guild.id:
                    return await ctx.send(f"❌ Can't assign the **@everyone** role at level {level}.", ephemeral=True)

                level_key = str(level)
                config["role_assignments"][level_key] = role.id
                updated_settings.append(f"Role for the **{level}** set: **{role.mention}**")
            
        # 4. Config exit channel
        if exit_channel is not None:
            if moderation_cog is None:
                updated_settings.append("❌ Moderation cog is not loaded. Cannot set exit channel.")
            else:
                mod_config = moderation_cog.get_guild_config(ctx.guild.id)
                mod_config["exit_channel_id"] = exit_channel.id
                moderation_cog._save_config_data()
                updated_settings.append(f"Exit channel set to: **{exit_channel.mention}**")
        
        # 5. Config voice creator channel
        if voice_creator_channel is not None:
            if voice_temp_cog is None:
                updated_settings.append("❌ VoiceTemp cog is not loaded. Cannot set voice creator channel.")
            else:
                voice_config = voice_temp_cog.get_guild_config(guild_id)
                voice_config["creator_channel_id"] = voice_creator_channel.id
                voice_temp_cog._save_config_data()
                updated_settings.append(f"Voice creator channel set to: **{voice_creator_channel.mention}**")
                
        # END. Save patched config
        if updated_settings:
            self._save_config_data()
            response_message = (
                "✅ Config realoded:\n" + 
                "\n".join(updated_settings) +
                "\n\nUse **/config-show** to see the actual config."
            )
        else:
            response_message = "⚠️ No value for the patch."
            
        await ctx.send(response_message, ephemeral=True)

#   ---- Slash Commands: /leveling-toggle ----
    @commands.hybrid_command(name="leveling-toggle", description="Activate/Deactivate the leveling system for the server.")
    @commands.has_permissions(administrator=True)
    async def leveling_toggle(self, ctx: commands.Context, enabled: bool):
            if ctx.guild is None:
                return await ctx.send("This command must be used in a server.", ephemeral=True)

            guild_id = str(ctx.guild.id)
            config = self.get_guild_config(guild_id)

            # Imposta il nuovo valore
            config["is_active"] = enabled
            self._save_config_data()

            status = "activated" if enabled else "deactivated"
            await ctx.send(f"✅ Leveling system **{status}** for **{ctx.guild.name}**.", ephemeral=False)

#   ---- Slash Commands: /backgroundT-toggle ----
    @commands.hybrid_command(name="bg-task-toggle", description="Activate/Deactivate the background role-check task for the server.")
    @commands.has_permissions(administrator=True)
    async def backgroundT_toggle(self, ctx: commands.Context, enabled: bool):
                
        # 1. Check guild context
        if ctx.guild is None:
            return await ctx.send("This command must be used in a server", ephemeral=True)

        # 2. Load guild config
        guild_id = str(ctx.guild.id)
        config: Dict[str, Any] = self.get_guild_config(guild_id)

        # 3. Set new value and save
        config["backgroundT_status"] = enabled
        self._save_config_data()

        # 4. Feedback to utente
        status = "activated" if enabled else "deactivated"
        
        embed = discord.Embed(
            title="⚙️ Background Task",
            description=f"The background task was **{status}** for **{ctx.guild.name}**.",
            color=discord.Color.green() if enabled else discord.Color.red()
        )
        embed.set_footer(text="Status will update at the next cicle (every 60 minuts).")
        await ctx.send(embed=embed, ephemeral=False)

#   ---- Setup to load Cog ----
async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))