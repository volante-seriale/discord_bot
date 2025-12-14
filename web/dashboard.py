import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent  # go up from /web to project root
env_path = BASE_DIR / ".env"

print(f"Looking for .env at: {env_path}")

if not env_path.exists():
    print("ERROR: .env file NOT found!")
    print(" → It must be in the main project folder (where bot.py is located)")
    sys.exit(1)

load_dotenv(dotenv_path=env_path)
print(".env file loaded successfully")

# Immediate token check
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN.strip() == "":
    print("ERROR: BOT_TOKEN not found or empty in .env file")
    sys.exit(1)
print(f"BOT_TOKEN found ({len(BOT_TOKEN)} characters) → OK")

import functools
from flask import Flask, redirect, url_for, session, render_template, request, flash
import discord
from discord.ext import commands
import threading
import requests

app = Flask(__name__, static_folder='static', template_folder='templates')
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-change-me")

#   ---- OAuth2 Configuration ----
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "https://oviparous-dan-overnarrow.ngrok-free.dev/callback"
AUTH_URL = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={  REDIRECT_URI  }&response_type=code&scope=identify%20guilds"
TOKEN_URL = "https://discord.com/api/oauth2/token"
bot = None

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if session.get("user") is None:
            return redirect(url_for("login"))
        return view(**kwargs)
    return wrapped_view

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/home")
def home():
    return render_template("index.html")    

@app.route("/login")
def login():
    return redirect(AUTH_URL)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Authorization error", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "scope": "identify guilds"
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post(TOKEN_URL, data=data, headers=headers)
    r.raise_for_status()
    token = r.json()

    user_info = requests.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {token['access_token']}"}).json()
    guilds = requests.get("https://discord.com/api/users/@me/guilds", headers={"Authorization": f"Bearer {token['access_token']}"}).json()

    # Keep only servers where the user is admin or owner
    user_guilds = [g for g in guilds if (g["permissions"] & 0x8 == 0x8) or g["owner"]]

    session["user"] = {
        "id": user_info["id"],
        "username": user_info["username"],
        "discriminator": user_info.get("discriminator", "0"),
        "avatar": user_info["avatar"],
        "guilds": user_guilds
    }
    return redirect(url_for("dashboard"))

@app.route("/dashboard")
@login_required
def dashboard():
    user_guild_ids = [str(g["id"]) for g in session["user"]["guilds"]]
    common_guilds = []
    for g in bot.guilds:
        if str(g.id) in user_guild_ids:
            common_guilds.append({
                "id": g.id,
                "name": g.name,
                "icon_url": str(g.icon.with_size(256)) if g.icon else None
            })            
    
    return render_template("dashboard.html", guilds=common_guilds, user=session["user"])

@app.route("/guild/<guild_id>")
@login_required
def guild_config(guild_id):
    guild = bot.get_guild(int(guild_id))
    if not guild:
        flash("Bot non presente o permessi insufficienti")
        return redirect(url_for("dashboard"))

    leveling = bot.get_cog("Leveling")
    tempvoice = bot.get_cog("TempVoice")
    moderation = bot.get_cog("Moderation")

    config = {}
    if leveling:
        config.update(leveling.get_guild_config(str(guild.id)))
    if tempvoice:
        config.update(tempvoice.get_guild_config(guild.id))
    if moderation:
        config.update(moderation.get_guild_config(guild.id))

    # NUOVO: Convertiamo gli ID in nomi reali per la dashboard web
    def resolve_channel(channel_id):
        if not channel_id:
            return "Non configurato"
        channel = guild.get_channel(int(channel_id))
        return channel.name if channel else "Canale eliminato"

    def resolve_role(role_id):
        if not role_id:
            return "Non configurato"
        role = guild.get_role(int(role_id))
        return role.name if role else "Ruolo eliminato"

    # Prepariamo i dati puliti per il template
    display_config = {
        "level_up_channel": resolve_channel(config.get("level_up_channel_id")),
        "exit_channel": resolve_channel(config.get("exit_channel_id")),
        "voice_creator": resolve_channel(config.get("creator_channel_id")),
        "invite_link": config.get("invite_link", "Non impostato"),
        "background_task": "Attivo" if config.get("backgroundT_status", True) else "Disattivo",
        "leveling_active": "Attivo" if config.get("is_active", True) else "Disattivo",
        "roles": {}
    }

    # Ruoli livello
    for i in range(1, 6):
        role_id = config.get("role_assignments", {}).get(str(i))
        display_config["roles"][f"level_{i}"] = resolve_role(role_id)

    # Top 10 (come prima)
    top_users = []
    if leveling and str(guild.id) in leveling.level_data:
        users = leveling.level_data[str(guild.id)]
        for uid, data in sorted(users.items(), key=lambda x: x[1]["total_xp"], reverse=True)[:10]:
            member = guild.get_member(int(uid))
            if member:
                top_users.append({
                    "name": member.display_name,
                    "level": data["level"],
                    "xp": data["total_xp"],
                    "avatar": member.display_avatar.url
                })

    return render_template("guild.html", guild=guild, config=display_config, top_users=top_users, user=session["user"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

#   ---- Run Bot in Separate Thread ----
def run_bot():
    global bot

    # IMPORTANT: add the project root to Python path
    import sys
    from pathlib import Path
    root_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(root_path))
    print(f"Added to sys.path: {root_path}")

    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="/", intents=intents)

    @bot.event
    async def on_ready():
        print(f"Bot logged in as {bot.user} ({bot.user.id})")
        print("Loading cogs...")
        print("------------------------------")

        try:
            await bot.load_extension("cogs.leveling")
            print("Leveling cog loaded")
            await bot.load_extension("cogs.tempvoice")
            print("TempVoice cog loaded")
            await bot.load_extension("cogs.moderation")
            print("Moderation cog loaded")
            await bot.load_extension("cogs.member_id")
            print("Member ID cog loaded")
            await bot.load_extension("cogs.utility")
            print("Utility cog loaded")
            await bot.load_extension("cogs.casino")
            print("Casino cog loaded")
            print("------------------------------")

            await bot.tree.sync()
            print("Slash commands synced globally")
        except Exception as e:
            print(f"Error loading cogs: {e}")

    print("Starting bot with token...")
    bot.run(BOT_TOKEN)

#   ---- Main Entry Point ----
if __name__ == "__main__":
    print("="*60)
    print("STARTING BOT + DASHBOARD - FINAL VERSION")
    print("="*60)
    threading.Thread(target=run_bot, daemon=True).start()
    print("Bot started → Flask running at http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)