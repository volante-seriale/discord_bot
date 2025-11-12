import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

#1. Load the token
load_dotenv()
Token = os.getenv('BOT_TOKEN')

if Token is None:
    print("ERRORE FATALE: Token non trovato. Controlla il file .env.")
    exit()
#2. Configure Intents
intents = discord.Intents.all()

#3. Create Bot Instance
bot = commands.Bot(command_prefix='/', intents=intents)

#4. Event listener
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'Bot is logged in as {bot.user.name}')
    print("slash command synced globally")
    print("--------------")

#5. Slash command: /ping
@bot.tree.command(name="ping", description="Tests the bot's responsiveness,")
async def ping_command(interaction: discord.Interaction):
    latency_ms = round(bot.latency)
    await interaction.response.send_message(f'**Pong** | Current latency: **{latency_ms}**')

#6. Slash command: /serverinfo
@bot.tree.command(name="serverinfo", description="Displays basic information about the server.")
async def server_info_command(interaction: discord.Interaction):
    guild = interaction.guild
    if not guild:
        await interaction.response.send_message("This command must be run inside a Discord server.")
        return
    embed = discord.Embed(
        title=f"Infos about {guild.name}",
        color=discord.Color.blue()
    )
    #1. owner/members count
    embed.add_field(name="Owner", value=guild.owner.mention, inline=True)
    embed.add_field(name="Member count", value=guild.member_count, inline=True)
    
    #2. server id and creation date
    embed.add_field(name="Server ID", value=guild.id, inline=False)
    embed.add_field(name="Created on", value=f"<t:{int(guild.created_at.timestamp())}>", inline=False)

    #3. Send embed
    await interaction.response.send_message(embed=embed)
#7. Run
bot.run(Token)