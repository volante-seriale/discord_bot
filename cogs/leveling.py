import discord
from discord.ext import commands
import json
from typing import Dict, Any
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
}

MAX_LEVEL = max(LEVEL_THRESHOLDS.keys())
MAX_XP_TOTAL = LEVEL_THRESHOLDS[MAX_LEVEL]

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
        self.data: Dict[str, Dict[str, Any]] = self._load_data()
    
#   ---- Gestione Database(JSON) ----
    def _load_data(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open('data/levels.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return{}
        except json.JSONDecodeError:
            print("Error: levels.json corrupted, reload in void.")
            return{}
        
    def _save_data(self):
        with open ('data/levels.json', 'w') as f:
            json.dump(self.data, f, indent=4)

#   ---- Event listener: Xp assign ----

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or message.content.startswith(self.bot.command_prefix):
            return
        
        user_id = str(message.author.id)
        guild_id = str(message.guild.id)
        
        #1. Inizialize (saving total and needed xp)
        if guild_id not in self.data:
            self.data[guild_id] = {}
        if user_id not in self.data[guild_id]:
            self.data[guild_id][user_id] = {"total_xp": 0, "level": 0}
            
        user_data = self.data[guild_id][user_id]
        
        #2. Add xp (if not max_level)
        if user_data["level"] < MAX_LEVEL:
            user_data["total_xp"] += Xp_Message
        
        #3.Level check
        new_level, _ = get_level_info(user_data["total_xp"])
        actual_level = user_data["level"]
        
        if new_level > actual_level:
            user_data["level"] = new_level
            self._save_data() #Instantly saves after level-up
        
            if new_level in ROLE_ASSIGNMENTS:
                role_id = ROLE_ASSIGNMENTS[new_level]
                role = message.guild.get_role(role_id)
        
                if role:
                    try:
                        # 1. Assegna il nuovo ruolo
                        await message.author.add_roles(role, reason="Level Up automatico")

                        # 2. Rimuovi il ruolo precedente (Opzionale: se i livelli sono esclusivi)
                        # Questo blocco è OPZIONALE. Se non vuoi rimuovere i ruoli precedenti, commenta o elimina le righe sottostanti.
                        prev_role_id = ROLE_ASSIGNMENTS.get(actual_level)
                        if prev_role_id and prev_role_id != role_id:
                            prev_role = message.guild.get_role(prev_role_id)
                            if prev_role and prev_role in message.author.roles:
                                await message.author.remove_roles(prev_role, reason="Rimozione ruolo precedente per Level Up")

                        # Messaggio di congratulazioni
                        await message.channel.send(
                            f"**Congrats, {message.author.mention}!** You just leveled up to **Level {new_level}** and earned the role {role.name}!"
                        )
                    except discord.Forbidden:
                        print(f"ERRORE: Permessi insufficienti per assegnare/rimuovere il ruolo {role.name} sul server {message.guild.name}.")
                    except Exception as e:
                        print(f"Errore nell'assegnazione ruolo per {message.author}: {e}")
                else:
                    print(f"ATTENZIONE: Ruolo con ID {role_id} non trovato sul server {message.guild.name}.")
    
        # Se il livello aumenta ma non ha un ruolo associato, invia il messaggio base:
        elif new_level not in ROLE_ASSIGNMENTS:
             try:
                await message.channel.send(f"**Congrats, {message.author.mention}!** You just leveled up to **Level {new_level}**")
             except discord.Forbidden:
                 pass
             
        # Se non c'è level up, salva solo i dati (come prima)
        else:
            self._save_data()
            
#   ---- Slash Commands: /level ----
    
    @commands.hybrid_command(name="level", description="show your actual level and xp")
    async def level_command(self, ctx: commands.Context, member: discord.Member = None):
        if ctx.guild is None:
            await ctx.send ("This command must be sent in a server.")
            return
        
        target = member or ctx.author
        guild_id = str(ctx.guild.id)
        user_id = str(target.id)
        
        if guild_id not in self.data or user_id not in self.data[guild_id]:
            await ctx.send(f"**{target.display_name}** hasn't ernead xp in this server")
            return
        
        user_data = self.data[guild_id][user_id]
        level = user_data["level"]
        total_xp = user_data["total_xp"]
        
        #Use new function to define status
        _, xp_needed = get_level_info(total_xp)
        
        #Calculates xp in actual_level and xp_needed
        xp_prev_level = 0
        if level > 0 and level in LEVEL_THRESHOLDS:
            # Per evitare KeyError nel caso improbabile in cui level non sia ancora nella soglia
            xp_prev_level = LEVEL_THRESHOLDS.get(level-1, 0) # Usa livello precedente
        
        # Qui potresti voler ricalcolare la xp_prev_level in modo più preciso, ma per ora teniamo la tua logica
        xp_prev_level = LEVEL_THRESHOLDS[level] if level in LEVEL_THRESHOLDS else 0
        
        xp_in_actual_level = total_xp - xp_prev_level
        xp_to_next_level = xp_needed - total_xp if xp_needed > 0 else 0
        xp_needed_total_in_level = xp_needed - xp_prev_level if xp_needed > 0 else 1
        
        #Calculates the advancement percentage
        # Uso xp_needed_total_in_level per una progressione corretta nel livello attuale
        progress = (xp_in_actual_level / xp_needed_total_in_level) * 100 if xp_needed_total_in_level > 0 else 100
        progress_bar = "█" * int(progress // 10) + "" * (10 - int(progress // 10))
        
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
        
#Setup to load Cog
async def setup(bot: commands.Bot):
    await bot.add_cog(Leveling(bot))