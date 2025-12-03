import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import asyncio

#   ---- Global log list ----
WEB_LOGS = []
MAX_LOGS = 200

#   ---- Configure Intents ----
intents = discord.Intents.all()
bot = commands.Bot(command_prefix='/', intents=intents)

#   ---- Load the token ----
load_dotenv()
Token = os.getenv('BOT_TOKEN')

if Token is None:
    print("Fatal Error: Token not found. Check '.env' file.")
    exit()
     
#   ---- Config bot.owner_id ----
owner_id_int = int(os.getenv('BOT_OWNER_ID'))
bot.owner_id = owner_id_int
if bot.owner_id is None:
    print("Fatal Error: BOT_OWNER_ID not found. Check '.env' file.")
    exit()

#   ---- Definition of the time for the kick ----
Kick_Timeout = timedelta(hours=48)
Current_Timezone = timezone.utc

#   ---- Fuction for loading Cogs ----
async def load_extensions():
    # Checks for levels.json in the data/ directory
    if not os.path.exists('data'):
        os.makedirs('data')
        
    try:

        await bot.load_extension("cogs.leveling")        
        print("COG: Leveling loaded successfully.")

        await bot.load_extension("cogs.tempvoice")        
        print("COG: TempVoice loaded successfully.")
        
        await bot.load_extension("cogs.moderation")     
        print("COG: Moderation loaded successfully.")
        
        await bot.load_extension("cogs.member_id")
        print("COG: Member ID Lister loaded successfully.")

        print("--------------")
    except Exception as e:
        print(f"Error while loading the cogs\n{e}")

#   ---- Event listener ----
@bot.event
async def on_ready():
    await load_extensions()
    print(f'Bot is logged in as {bot.user.name}')
    print("--------------")
    
    print("Extensions loaded")
    print("--------------")
    
    if not check_unassigned_roles.is_running():
        check_unassigned_roles.start()
    
    print("Background task started.")
    print("--------------")

    await asyncio.sleep(2)
    await bot.tree.sync()
    print("slash command synced globally")
    print("--------------")
 

#   ---- Event listener for commands errors ----
@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    # Check for missing permissions (CheckFailure)
    if isinstance(error, commands.CheckFailure):
        
        # Check for NotOwner error
        if isinstance(error, commands.NotOwner):
            # Sends message to the user
            await ctx.send(
                "❌ **Access denied!** Only the bot owner can execute **/sync**. ",
                ephemeral=True
            )
            # Logs the attempt for admin
            print(f"{ctx.author.name} ({ctx.author.id}) tried to use /sync without being the owner.")
        
        # Can add other CheckFailure errors here
        else:
             await ctx.send(f"❌  **{error}**", ephemeral=True)

        return # blocks further error handling
        
    # Every other error (es. CommandNotFound, BadArgument, ecc.)
    if hasattr(ctx.command, 'qualified_name'):
        print(f"❌ Error not handle in the command '{ctx.command.qualified_name}': {error}")
    else:
        print(f"❌ Error not handle: {error}")

#   ---- Background task ----
@tasks.loop(minutes=60)
async def check_unassigned_roles():
    time_limit = datetime.now(Current_Timezone) - Kick_Timeout
    
    # 1. Recupera il Cog Leveling (necessario per accedere alla configurazione)
    leveling_cog = bot.get_cog("Leveling")
    if not leveling_cog:
        print("Warnign: COG 'leveling' not found. Unable to read backgroundT_status.")
        return

    for guild in bot.guilds:
        guild_id = str(guild.id)
        
        # 2. Loads guild configuration
        guild_config = leveling_cog.get_guild_config(guild_id) 
        
        # 3. Check if backgroundT_status is enabled
        if not guild_config.get("backgroundT_status", True): 
            print(f"Background task (kick) for the guild **{guild.name}** is unactive from server config.")
            continue
                    
        bot_member = guild.get_member(bot.user.id)
        
        if not bot_member or not bot_member.guild_permissions.kick_members:
            print(f"Bot can't kick '{guild.name}' (missing permission to kick).")
            continue
        
        async for member in guild.fetch_members(limit=None):
            if member.bot or member == guild.owner or member == bot_member:
                continue
            
            # Checks if has other role than @everyone
            has_only_everyone_role = len(member.roles) <= 1
            
            # Checks if the 48hrs have passed
            if has_only_everyone_role and member.joined_at < time_limit:
                try:
                    # Tries kick
                    print(f"Kicking {member.name} ({member.id}) from server '{guild.name}'")
                    await member.kick(reason="Automatic: No roles after 48h (Background task)") 
                except discord.Forbidden:
                    print(f"Error: I can't kick {member.name} from the server '{guild.name}'")
                except Exception as e:
                    print(f"Error while kicking {member.name}: {e}")                    
#   ---- Run ----
bot.run(Token)
