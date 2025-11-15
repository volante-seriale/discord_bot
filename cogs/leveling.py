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
    """
    Calculates the actual level and needed xp to level-up
    Returns: (actual_level, xp_needed)
    """
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
    
    
#   ---- Gestione Database(JSON) ----

    #Xp load
    def _load_level_data(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open('data/levels.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return{}
        except json.JSONDecodeError:
            print("Error: levels.json corrupted, reload in void.")
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
            print("Error: config.json corrupted, reload in void.")
            return{}
        
    def _save_config_data(self):
        with open('data/config.json', 'w') as f:
            json.dump(self.config_data, f, indent=4)
    
    def get_guild_config(self, guild_id:str) -> Dict[str,Any]:
        default_config = {
            "level_up_channel_id": None,
            "invite_link": None,
            "role_assignments": {str(lvl): None for lvl in LEVEL_THRESHOLDS.keys()}
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
            
            congrats_message = f"**Congrats, {message.author.mention}!** You reached the **Level {new_level}**!"
            
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

                        congrats_message +=f"and earned the role {role.name}"
                        
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
            await ctx.send(f"**{target.display_name}** hasn't ernead xp in this server")
            return
        
        user_data = self.level_data[guild_id][user_id]
        level = user_data["level"]
        total_xp = user_data["total_xp"]
        
        #Use new function to define status
        current_level, xp_needed = get_level_info(total_xp)
        
        #Calculates xp in actual_level
        xp_prev_level = 0
        if current_level > 1 and (current_level-1) in LEVEL_THRESHOLDS:
            # Per evitare KeyError nel caso improbabile in cui level non sia ancora nella soglia
            xp_prev_level = LEVEL_THRESHOLDS[current_level-1] # Usa livello precedente
            
        #Recalculates progression
        if current_level == MAX_LEVEL:
            xp_needed = 0
        else:
            xp_needed = LEVEL_THRESHOLDS[current_level+1]
        
        xp_to_next_level = xp_needed - total_xp if xp_needed > 0 else 0
                
        xp_in_actual_level = total_xp - xp_prev_level
        xp_needed_total_in_level = xp_needed - xp_prev_level if xp_needed > 0 else 1
        
        #Calculates the advancement percentage
        # Uso xp_needed_total_in_level for right progression in the actual level
        progress = (xp_in_actual_level / xp_needed_total_in_level) * 100 if xp_needed_total_in_level > 0 else 100
        progress_bar_length = 10
        filled_block = int(progress * progress_bar_length // 100)
        progress_bar = ":blue_square:" * filled_block + ":black_large_square:" * (progress_bar_length - filled_block)
        
        embed = discord.Embed(
            title=f"Level and Xp {target.display_name}",
            color=discord.Color.blue() if level < MAX_LEVEL else discord.Color.purple()
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Actual level", value=f"**{level}** (Max: {MAX_LEVEL})", inline=True)
        embed.add_field(name="Total Xp", value=f"**{total_xp}**", inline=True)
        
        if level < MAX_LEVEL:
            embed.add_field(name="Xp to next level", value=f"**{xp_to_next_level}**", inline=True)
            embed.add_field(name="Progression", value=f"`[{progress_bar}]` ({progress:.2f}%)", inline=False)
        else:
            embed.add_field(name="State", value=f"🎉 **Max level reached**", inline=True)
            embed.add_field(name="Progress", value="`[██████████]` (100.00%)", inline=False) 
        
        embed.set_footer(text=f"User Id: {target.id}")
        await ctx.send(embed=embed)
        

#   ---- New Slash Command: /configure

    @commands.hybrid_group(name="configure", description="Configure the leveling system and the server invete link.", fallback="show_config")
    @commands.has_permissions(administrator=True) #Only admin can use this command
    async def configure(self, ctx : commands.Context):
        pass #If user just types /configure

    @configure.command(name="show", description="Displays current leveling configuration")
    async def show_config(self, ctx: commands.Context):
        if ctx.guild is None:
            await ctx.send("This command must be sent in a server")
            return

        guild_id = str(ctx.guild.id)
        config = self.get_guild_config(guild_id)

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
            role_mention = f"<@{role_id}>" if channel_id else "Not configured"
            role_info.append(f"Level **{level}**: {role_mention}")
        embed.add_field(name="Level Roles", value="/n".join(role_info), inline=False)
        await ctx.send(embed=embed, ephemeral=True)
        
    @configure.command(name="channel", description="Sets the channel for level-up notifications.")
    @commands.has_permissions(administrator=True)
    async def configure_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        guild_id = str(ctx.guild.id)
        config = self.get_guild_config(guild_id)
        
        config["level_up_channel_id"] = channel.id
        self._save_config_data()
        
        await ctx.send(f"✅ Level-up notifications channel set to **{channel.mention}**.", ephemeral=True)


    @configure.command(name="role", description="Assigns a role to a specific level.")
    @commands.has_permissions(administrator=True)
    async def configure_role(self, ctx: commands.Context, level: int, role: discord.Role):
        guild_id = str(ctx.guild.id)
        config = self.get_guild_config(guild_id)
        
        if level < 1 or level > MAX_LEVEL:
            return await ctx.send(f"❌ Livello non valido. Deve essere compreso tra **1** e **{MAX_LEVEL}**.", ephemeral=True)
        
        level_key = str(level)
        
        # Controlla se il ruolo è @everyone (che non dovrebbe essere assegnato/rimosso)
        if role.id == ctx.guild.id: # L'ID della @everyone è uguale all'ID della Gilda
            return await ctx.send("❌ Non puoi assegnare il ruolo **@everyone**.", ephemeral=True)
        
        config["role_assignments"][level_key] = role.id
        self._save_config_data()
        
        await ctx.send(f"✅ Ruolo per il **Livello {level}** impostato su **{role.mention}**.", ephemeral=True)
        
    @configure.command(name="invite", description="Sets the server's permanent invite link for /serverinfo.")
    @commands.has_permissions(administrator=True)
    async def configure_invite(self, ctx: commands.Context, link: str):
        guild_id = str(ctx.guild.id)
        config = self.get_guild_config(guild_id)
        
        # Semplice validazione del link (potrebbe essere più robusta, ma è un buon inizio)
        if not link.startswith("http") and not link.startswith("discord.gg/"):
            return await ctx.send("❌ Link non valido. Assicurati che sia un link completo (es. `https://discord.gg/abc`)", ephemeral=True)
        
        config["invite_link"] = link
        self._save_config_data()
        
        await ctx.send(f"✅ Server invite link impostato: ```\n{link}\n```", ephemeral=True)
            
#Setup to load Cog
async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))