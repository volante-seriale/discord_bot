import os
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
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
        # Loads Cogs (cogs/leveling.py)
        await bot.load_extension("cogs.leveling")        
        print("COG: Leveling loaded successfully.")
        # Loads Cogs (cogs/tempvoice.py)
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

    #bot log-in
    await bot.tree.sync()
    print("slash command synced globally")
    print("--------------")
 
#   ---- Slash command: /ping ----
@bot.tree.command(name="ping", description="Tests the bot's responsiveness,")
async def ping_command(interaction: discord.Interaction):
    latency_ms = round(bot.latency * 1000)
    await interaction.response.send_message(f'**Pong** | Current latency: **{latency_ms}ms**')

#   ---- Slash command: /serverinfo ----
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
    await interaction.response.send_message(embed=embed, ephemeral=False)

#   ---- Admin command to globaly sync ----
@bot.hybrid_command(name="sync", description="Forces the slash commands syncronization.")
@commands.is_owner() 
async def sync_commands(ctx: commands.Context):
    """Syncs slash commands globaly."""
    
    # Check di Ownership
    if ctx.author.id != ctx.bot.owner_id:
        return await ctx.send("You're not the bot owner", ephemeral=True) 

    try:
        initial_message = await ctx.send("⏳ Trying to globaly sync slash commands...", ephemeral=True) 
    except Exception as e:
        print(f"Error in the first answer: {e}")
        return
        
    try:
        synced = await ctx.bot.tree.sync() 
        await initial_message.edit(content=f"✅ Slash command synced successful. **{len(synced)}** comandi trovati.")
        
    except Exception as e:
        await initial_message.edit(content=f"❌ Error during sync: {e}")
        print(f"Errore di sincronizzazione: {e}")

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
        print(f"Errore non gestito nel comando '{ctx.command.qualified_name}': {error}")
    else:
        print(f"Errore non gestito: {error}")

#   ---- Background task ----
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
                    
#   ---- Run ----
bot.run(Token)