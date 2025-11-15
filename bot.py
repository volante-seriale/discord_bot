import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

# --- Load the token ---
load_dotenv()
Token = os.getenv('BOT_TOKEN')

if Token is None:
    print("ERRORE FATALE: Token non trovato. Controlla il file .env.")
    exit()
    
# --- Configure Intents ---
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

# --- Config bot.owner_id ---
bot.owner_id = 943923205381443604

# --- Definizione del Tempo per il Kick ---
Kick_Timeout = timedelta(hours=48)
Current_Timezone = timezone.utc

# --- Funzione per caricare i Cogs (AGGIUNTA) ---
async def load_extensions():
    # Assicurati che la cartella 'data' esista per levels.json
    if not os.path.exists('data'):
        os.makedirs('data')
        
    try:
        # Carica il Cog di livellamento (cogs/leveling.py)
        await bot.load_extension("cogs.leveling")        
        print("COG: Leveling caricato con successo.")
    except Exception as e:
        print(f"ERRORE nel caricamento del COG: Leveling\n{e}")


# --- Background task ---
@tasks.loop(minutes=60)
async def check_unassigned_roles():
    time_limit = datetime.now(Current_Timezone) - Kick_Timeout
    
    for guild in bot.guilds:
        bot_member = guild.get_member(bot.user.id)
        if not bot_member or not bot_member.guild_permissions.kick_members:
            print(f"The bot can't kick from '{guild.name}'")
            continue
        
        async for member in guild.fetch_members(limit=None):
            #Ignores bot and owner in the server
            if member.bot or member == guild.owner or member == bot_member:
                continue
            #Checks if has other role than @everyone
            has_only_everyone_role = len(member.roles) <= 1
            #Checks if the 48hrs have passed
            if has_only_everyone_role and member.joined_at < time_limit:
                try:
                    #Tries kick
                    print(f"Kicking {member.name} ({member.id}) from server '{guild.name}'")
                    await member.kick(reason="Automatic: No roles after 48h")
                except discord.Forbidden:
                    print(f"Error: I can't kick {member.name} from the server '{guild.name}'")
                except Exception as e:
                    print(f"Error while kicking {member.name}: {e}")

# --- Event listener ---
@bot.event
async def on_ready():
    await load_extensions()
    print(f'Bot is logged in as {bot.user.name}')
    print("Extensions loaded")
    print("--------------")
    
    if not check_unassigned_roles.is_running():
        check_unassigned_roles.start()
    
    print("Background task started.")
    print("--------------")

    #bot log-in
    await bot.tree.sync()
    print("slash command synced globally")
    print("--------------")
       
# --- Slash command: /ping ---
@bot.tree.command(name="ping", description="Tests the bot's responsiveness,")
async def ping_command(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f'**Pong** | Current latency: **{latency_ms}ms**')

# --- Slash command: /serverinfo ---
@bot.tree.command(name="serverinfo", description="Displays basic information about the server.")
async def server_info_command(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("This command must be run inside a Discord server.")
        return
    
    #Obtains the configuration from cog/leveling.py
    leveling_cog = bot.get_cog("Leveling")
    invite_link = None
    if leveling_cog:
        guild_id = str(guild.id)
        # Accedi alla funzione di configurazione per recuperare i dati
        guild_config = leveling_cog.get_guild_config(guild_id) 
        invite_link = guild_config.get("invite_link")
        
    embed = discord.Embed(
        title=f"Infos about {guild.name}",
        color=discord.Color.blue()
    )
    #1. Owner/members count
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Member count", value=guild.member_count, inline=True)
    
    #2. Server id and creation date
    embed.add_field(name="Server ID", value=guild.id, inline=False)
    embed.add_field(name="Created on", value=f"<t:{int(guild.created_at.timestamp())}>", inline=False)
    
    #3. Invite link
    if invite_link:
        embed.add_field(name="Invite Link", value=f"({invite_link})", inline=False)

    #4. Send embed
    await interaction.response.send_message(embed=embed)

# --- NUOVO Comando Admin per forzare la Sincronizzazione Slash (CORRETTO) ---
# Usiamo il decoratore bot.hybrid_command per registrarlo correttamente
@bot.hybrid_command(name="sync", description="Forces the slash commands syncronization.")
@commands.is_owner() 
async def sync_commands(ctx: commands.Context):
    """Syncs slash commands globaly."""
    
    # Questo controllo non è strettamente necessario se usi @commands.is_owner(),
    # ma assicura che il bot sappia chi è il proprietario.
    if ctx.author.id != ctx.bot.owner_id:
        return await ctx.send("You're not the bot owner", ephemeral=True)
    
    try:
        # Usiamo ctx.bot.tree.sync() per sincronizzare tutti i comandi slash
        await ctx.bot.tree.sync() 
        await ctx.send("✅ Slash command synced successful.", ephemeral=True)
    except Exception as e:
        await ctx.send(f"❌ Error during sync: {e}", ephemeral=True)    
# --- Run ---
bot.run(Token)