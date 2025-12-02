# web/dashboard.py
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ───── FORZA IL CARICAMENTO DEL .env DALLA CARTELLA GIUSTA ─────
BASE_DIR = Path(__file__).resolve().parent.parent  # sale dalla cartella /web alla root
env_path = BASE_DIR / ".env"

print(f"Cercando .env in: {env_path}")

if not env_path.exists():
    print("ERRORE: file .env NON trovato!")
    print("   → Deve stare nella cartella principale (dove c'è bot.py)")
    sys.exit(1)

load_dotenv(dotenv_path=env_path)
print("File .env caricato correttamente")

# Controllo immediato del token
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN or BOT_TOKEN.strip() == "":
    print("ERRORE: BOT_TOKEN non trovato o vuoto nel file .env")
    sys.exit(1)
print(f"BOT_TOKEN trovato ({len(BOT_TOKEN)} caratteri) → OK")

# ───── Fine caricamento .env ─────

import functools
from flask import Flask, redirect, url_for, session, render_template, request, flash
import discord
from discord.ext import commands
import asyncio
import threading
import requests

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-change-me")

# ───── OAuth2 Discord ─────
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = "http://localhost:5000/callback"
AUTH_URL = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"
TOKEN_URL = "https://discord.com/api/oauth2/token"

# ───── Variabili globali bot ─────
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
    if session.get("user"):
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/login")
def login():
    return redirect(AUTH_URL)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Errore autorizzazione", 400

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
    common_guilds = [g for g in bot.guilds if str(g.id) in user_guild_ids]
    return render_template("index.html", guilds=common_guilds, user=session["user"])

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

    # Top 10
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

    return render_template("guild.html", guild=guild, config=config, top_users=top_users)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ───── Avvio bot in background ─────
def run_bot():
    global bot

    # IMPORTANTE: aggiungiamo la cartella principale al percorso Python
    import sys
    from pathlib import Path
    root_path = Path(__file__).resolve().parent.parent
    sys.path.append(str(root_path))        # ← questa riga risolve tutto per sempre
    print(f"Percorso aggiunto a sys.path: {root_path}")

    intents = discord.Intents.all()
    bot = commands.Bot(command_prefix="/", intents=intents)

    @bot.event
    async def on_ready():
        print(f"Bot connesso come {bot.user} ({bot.user.id})")
        print("Caricamento cogs...")
        try:
            await bot.load_extension("cogs.leveling")
            print("Leveling caricato")
            await bot.load_extension("cogs.tempvoice")
            print("TempVoice caricato")
            await bot.load_extension("cogs.moderation")
            print("Moderation caricato")
            await bot.load_extension("cogs.member_id")
            print("Member ID caricato")
            await bot.tree.sync()
            print("Comandi slash sincronizzati")
        except Exception as e:
            print(f"Errore cogs: {e}")

    print("Avvio bot con token...")
    bot.run(BOT_TOKEN)

# ───── MAIN (lascia così) ─────
if __name__ == "__main__":
    print("="*60)
    print("AVVIO BOT + DASHBOARD - VERSIONE DEFINITIVA")
    print("="*60)
    threading.Thread(target=run_bot, daemon=True).start()
    print("Bot avviato → Flask su http://localhost:5000")
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)