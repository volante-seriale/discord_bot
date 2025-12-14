import discord
from discord.ext import commands
from typing import Dict, Any, Optional
import json
import os

XP_PER_MESSAGE = 1

LEVEL_THRESHOLDS = {
    1: 15,
    2: 100,
    3: 300,
    4: 500,
    5: 1500
}

MAX_LEVEL = max(LEVEL_THRESHOLDS.keys())


def get_level_info(total_xp: int):
    for level, threshold in LEVEL_THRESHOLDS.items():
        if total_xp < threshold:
            return level - 1, threshold - total_xp
    return MAX_LEVEL, 0


class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        os.makedirs("data", exist_ok=True)
        self.level_data = self._load_level_data()
        self.config_data = self._load_config_data()

    def _load_level_data(self):
        try:
            with open("data/levels.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_level_data(self):
        with open("data/levels.json", "w", encoding="utf-8") as f:
            json.dump(self.level_data, f, indent=4)

    def _load_config_data(self):
        try:
            with open("data/config.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_config_data(self):
        with open("data/config.json", "w", encoding="utf-8") as f:
            json.dump(self.config_data, f, indent=4)

    def get_guild_config(self, guild_id: str):
        if guild_id not in self.config_data:
            self.config_data[guild_id] = {
                "level_up_channel_id": None,
                "level_up_channel_name": None,
                "invite_link": None,
                "role_assignments": {"1": None, "2": None, "3": None, "4": None, "5": None},
                "is_active": True,
                "backgroundT_status": True
            }
            self._save_config_data()
        return self.config_data[guild_id]

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        gid = str(guild.id)
        changed = False
        if gid in self.level_data:
            del self.level_data[gid]
            changed = True
        if gid in self.config_data:
            del self.config_data[gid]
            changed = True
        if changed:
            self._save_level_data()
            self._save_config_data()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        gid = str(message.guild.id)
        uid = str(message.author.id)
        config = self.get_guild_config(gid)

        if not config.get("is_active", True):
            return

        self.level_data.setdefault(gid, {}).setdefault(uid, {"total_xp": 0, "level": 0})
        user = self.level_data[gid][uid]

        old_level = user["level"]
        if old_level < MAX_LEVEL:
            user["total_xp"] += XP_PER_MESSAGE

        new_level, _ = get_level_info(user["total_xp"])
        if new_level > old_level:
            user["level"] = new_level
            self._save_level_data()

            channel = message.guild.get_channel(config["level_up_channel_id"]) or message.channel
            msg = f"**Congratulazioni {message.author.mention}!** Hai raggiunto il **Livello {new_level}**!"

            role_id = config["role_assignments"].get(str(new_level))
            if role_id:
                role = message.guild.get_role(int(role_id))
                if role:
                    try:
                        await message.author.add_roles(role, reason="Level up")
                        msg += f" e hai ottenuto **{role.name}**!"
                    except discord.Forbidden:
                        pass

            try:
                await channel.send(msg)
            except:
                pass
        else:
            self._save_level_data()

    @commands.hybrid_command(name="level", description="Mostra il tuo livello e XP")
    async def level(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        gid = str(ctx.guild.id)
        uid = str(target.id)

        data = self.level_data.get(gid, {}).get(uid, {"total_xp": 0, "level": 0})
        level = data["level"]
        xp = data["total_xp"]

        # Calcoliamo livello attuale e XP necessari
        current_level, xp_to_next = get_level_info(xp)

        # Barra di progresso
        if level >= MAX_LEVEL:
            progress_bar = "█" * 10
            progress_percent = 100.0
            status = "MAX LEVEL RAGGIUNTO!"
        else:
            # XP nel livello corrente
            prev_threshold = LEVEL_THRESHOLDS.get(current_level, 0)
            next_threshold = LEVEL_THRESHOLDS[current_level + 1]
            xp_in_current = xp - prev_threshold
            needed_in_current = next_threshold - prev_threshold

            progress = (xp_in_current / needed_in_current) * 100
            filled = int(progress // 10)
            progress_bar = "🟦" * filled + "⬛" * (10 - filled)
            progress_percent = progress
            status = f"{xp_to_next} XP al Livello {current_level + 1}"

        embed = discord.Embed(
            title=f"Livello di {target.display_name}",
            color=discord.Color.gold() if level >= MAX_LEVEL else discord.Color.blue()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="Livello", value=f"**{level}** / {MAX_LEVEL}", inline=True)
        embed.add_field(name="XP Totali", value=f"**{xp}**", inline=True)
        embed.add_field(name="Prossimo livello", value=status, inline=False)

        embed.add_field(
            name="Progresso",
            value=f"{progress_bar} **{progress_percent:.1f}%**",
            inline=False
        )

        embed.set_footer(text=f"ID Utente: {target.id}")
        await ctx.send(embed=embed)
        
    @commands.hybrid_command(name="config-show", description="Mostra la configurazione attuale del server")
    @commands.has_permissions(administrator=True)
    async def show_config(self, ctx: commands.Context):
        config = self.get_guild_config(str(ctx.guild.id))

        moderation = self.bot.get_cog("Moderation")
        tempvoice = self.bot.get_cog("TempVoice")

        # Level-up channel
        lvl_text = "Non configurato"
        if config.get("level_up_channel_id"):
            ch = ctx.guild.get_channel(config["level_up_channel_id"])
            lvl_text = ch.mention if ch else config.get("level_up_channel_name", "Canale eliminato")

        # Exit channel
        exit_text = "Non configurato"
        if moderation:
            mod_cfg = moderation.get_guild_config(ctx.guild.id)
            if mod_cfg.get("exit_channel_id"):
                ch = ctx.guild.get_channel(mod_cfg["exit_channel_id"])
                exit_text = ch.mention if ch else mod_cfg.get("exit_channel_name", "Canale eliminato")

        # Voice creator
        voice_text = "Non configurato"
        if tempvoice:
            vc_cfg = tempvoice.get_guild_config(ctx.guild.id)
            if vc_cfg.get("creator_channel_id"):
                ch = ctx.guild.get_channel(vc_cfg["creator_channel_id"])
                voice_text = ch.mention if ch else vc_cfg.get("creator_channel_name", "Canale eliminato")

        # Roles
        roles_lines = []
        for lvl in range(1, 6):
            role_id = config["role_assignments"].get(str(lvl))
            if role_id:
                role = ctx.guild.get_role(int(role_id))
                roles_lines.append(f"Livello **{lvl}** → {role.mention if role else 'Ruolo eliminato'}")
            else:
                roles_lines.append(f"Livello **{lvl}** → Non configurato")

        embed = discord.Embed(title="Configurazione Server", color=discord.Color.gold())
        embed.add_field(name="Link Invito", value=f"`{config.get('invite_link', 'Non impostato')}`", inline=False)
        embed.add_field(name="Canale Level-up", value=lvl_text, inline=True)
        embed.add_field(name="Canale Uscite", value=exit_text, inline=True)
        embed.add_field(name="Canale Crea Voce", value=voice_text, inline=True)
        embed.add_field(name="Ruoli per Livello", value="\n".join(roles_lines), inline=False)
        embed.add_field(name="Sistema Livelli", value="Attivo" if config.get("is_active") else "Disattivato", inline=True)
        embed.add_field(name="Task Background (48h)", value="Attivo" if config.get("backgroundT_status") else "Disattivato", inline=True)
        await ctx.send(embed=embed, ephemeral=False)

    @commands.hybrid_command(name="config", description="Configura canali, ruoli e impostazioni")
    @commands.has_permissions(administrator=True)
    async def configure_all(
        self, ctx: commands.Context,
        level_up_channel: Optional[discord.TextChannel] = None,
        invite_link: Optional[str] = None,
        role_level_1: Optional[discord.Role] = None,
        role_level_2: Optional[discord.Role] = None,
        role_level_3: Optional[discord.Role] = None,
        role_level_4: Optional[discord.Role] = None,
        role_level_5: Optional[discord.Role] = None,
        exit_channel: Optional[discord.TextChannel] = None,
        voice_creator_channel: Optional[discord.VoiceChannel] = None
    ):
        config = self.get_guild_config(str(ctx.guild.id))
        updated = []

        if level_up_channel:
            config["level_up_channel_id"] = level_up_channel.id
            config["level_up_channel_name"] = level_up_channel.name
            updated.append(f"Livello-up → {level_up_channel.mention}")

        if invite_link:
            if not invite_link.startswith(("http", "discord.gg")):
                return await ctx.send("Link non valido.", ephemeral=True)
            config["invite_link"] = invite_link
            updated.append(f"Invito → `{invite_link}`")

        roles_map = {1: role_level_1, 2: role_level_2, 3: role_level_3, 4: role_level_4, 5: role_level_5}
        for lvl, role in roles_map.items():
            if role:
                if role.is_default():
                    return await ctx.send("Non puoi assegnare @everyone.", ephemeral=True)
                config["role_assignments"][str(lvl)] = role.id
                updated.append(f"Livello {lvl} → {role.mention}")

        if exit_channel and self.bot.get_cog("Moderation"):
            mod = self.bot.get_cog("Moderation")
            mod_cfg = mod.get_guild_config(ctx.guild.id)
            mod_cfg["exit_channel_id"] = exit_channel.id
            mod_cfg["exit_channel_name"] = exit_channel.name
            mod._save_config_data()
            updated.append(f"Uscite → {exit_channel.mention}")

        if voice_creator_channel and self.bot.get_cog("TempVoice"):
            vc = self.bot.get_cog("TempVoice")
            vc_cfg = vc.get_guild_config(ctx.guild.id)
            vc_cfg["creator_channel_id"] = voice_creator_channel.id
            vc_cfg["creator_channel_name"] = voice_creator_channel.name
            vc._save_config_data()
            updated.append(f"Crea Voce → {voice_creator_channel.mention}")

        if updated:
            self._save_config_data()
            await ctx.send("Configurazione aggiornata:\n" + "\n".join(updated), ephemeral=True)
        else:
            await ctx.send("Nessuna modifica applicata.", ephemeral=True)

    @commands.hybrid_command(name="leveling-toggle", description="Attiva/disattiva il sistema livelli")
    @commands.has_permissions(administrator=True)
    async def leveling_toggle(self, ctx: commands.Context, stato: bool):
        config = self.get_guild_config(str(ctx.guild.id))
        config["is_active"] = stato
        self._save_config_data()
        await ctx.send(f"Sistema livelli {'attivato' if stato else 'disattivato'}.", ephemeral=False)

    @commands.hybrid_command(name="bg-task-toggle", description="Attiva/disattiva il task background (kick 48h)")
    @commands.has_permissions(administrator=True)
    async def bg_task_toggle(self, ctx: commands.Context, stato: bool):
        config = self.get_guild_config(str(ctx.guild.id))
        config["backgroundT_status"] = stato
        self._save_config_data()
        embed = discord.Embed(
            title="Task Background",
            description=f"Task 48h {'attivato' if stato else 'disattivato'}.",
            color=discord.Color.green() if stato else discord.Color.red()
        )
        await ctx.send(embed=embed, ephemeral=False)


async def setup(bot):
    await bot.add_cog(Leveling(bot))