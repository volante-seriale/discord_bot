import discord
from discord import app_commands
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
        guild_id = str(guild_id)
        guild = self.bot.get_guild(int(guild_id))
        if guild_id not in self.config_data:
            guild_name = guild.name if guild else "Unknown",
            self.config_data[guild_id] = {
                "guild_name": guild_name,
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
            msg = f"**Congratulations {message.author.mention}!** You've reached **Level {new_level}**!"

            role_id = config["role_assignments"].get(str(new_level))
            if role_id:
                role = message.guild.get_role(int(role_id))
                if role:
                    try:
                        await message.author.add_roles(role, reason="Level up")
                        msg += f" and you got **{role.name}**!"
                    except discord.Forbidden:
                        pass

            try:
                await channel.send(msg)
            except:
                pass
        else:
            self._save_level_data()

    @commands.hybrid_command(name="level", description="Show current level and XP")
    @app_commands.describe(member="Member of which to show the level (default: yourself)")
    async def level(self, ctx: commands.Context, member: Optional[discord.Member] = None):
        target = member or ctx.author
        gid = str(ctx.guild.id)
        uid = str(target.id)

        data = self.level_data.get(gid, {}).get(uid, {"total_xp": 0, "level": 0})
        level = data["level"]
        xp = data["total_xp"]
        current_level, xp_to_next = get_level_info(xp)

        if level >= MAX_LEVEL:
            progress_bar = "█" * 10
            progress_percent = 100.0
            status = "MAX LEVEL REACHED!"
        else:
            prev_threshold = LEVEL_THRESHOLDS.get(current_level, 0)
            next_threshold = LEVEL_THRESHOLDS[current_level + 1]
            xp_in_current = xp - prev_threshold
            needed_in_current = next_threshold - prev_threshold

            progress = (xp_in_current / needed_in_current) * 100
            filled = int(progress // 10)
            progress_bar = "🟦" * filled + "⬛" * (10 - filled)
            progress_percent = progress
            status = f"{xp_to_next} XP to Level {current_level + 1}"

        embed = discord.Embed(
            title=f"Level of {target.display_name}",
            color=discord.Color.gold() if level >= MAX_LEVEL else discord.Color.blue()
        )
        embed.set_thumbnail(url=target.display_avatar.url)

        embed.add_field(name="Level", value=f"**{level}** / {MAX_LEVEL}", inline=True)
        embed.add_field(name="Total XP", value=f"**{xp}**", inline=True)
        embed.add_field(name="Next Level", value=status, inline=False)

        embed.add_field(
            name="Progress",
            value=f"{progress_bar} **{progress_percent:.1f}%**",
            inline=False
        )

        embed.set_footer(text=f"User ID: {target.id}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="config-show", description="Show current server configuration")
    @commands.has_permissions(administrator=True)
    async def show_config(self, ctx: commands.Context):
        config = self.get_guild_config(str(ctx.guild.id))

        moderation = self.bot.get_cog("Moderation")
        tempvoice = self.bot.get_cog("TempVoice")

        # Level-up channel
        lvl_text = "Not set"
        if config.get("level_up_channel_id"):
            ch = ctx.guild.get_channel(config["level_up_channel_id"])
            lvl_text = ch.mention if ch else config.get("level_up_channel_name", "Canale eliminato")

        # Exit channel
        exit_text = "Not set"
        if moderation:
            mod_cfg = moderation.get_guild_config(ctx.guild.id)
            if mod_cfg.get("exit_channel_id"):
                ch = ctx.guild.get_channel(mod_cfg["exit_channel_id"])
                exit_text = ch.mention if ch else mod_cfg.get("exit_channel_name", "Deleted Channel")

        # Voice creator
        voice_text = "Not set"
        if tempvoice:
            vc_cfg = tempvoice.get_guild_config(ctx.guild.id)
            if vc_cfg.get("creator_channel_id"):
                ch = ctx.guild.get_channel(vc_cfg["creator_channel_id"])
                voice_text = ch.mention if ch else vc_cfg.get("creator_channel_name", "Deleted Channel")

        # Roles
        roles_lines = []
        for lvl in range(1, 6):
            role_id = config["role_assignments"].get(str(lvl))
            if role_id:
                role = ctx.guild.get_role(int(role_id))
                roles_lines.append(f"Level **{lvl}** → {role.mention if role else 'Role deleted'}")
            else:
                roles_lines.append(f"Level **{lvl}** → Not set")

        embed = discord.Embed(title="Server Configuration", color=discord.Color.gold())
        embed.add_field(name="Invite Link", value=f"`{config.get('invite_link', 'Not set')}`", inline=False)
        embed.add_field(name="Level-up Channel", value=lvl_text, inline=True)
        embed.add_field(name="Exit Channel", value=exit_text, inline=True)
        embed.add_field(name="Voice Creator Channel", value=voice_text, inline=True)
        embed.add_field(name="Roles by Level", value="\n".join(roles_lines), inline=False)
        embed.add_field(name="Leveling System", value="Active" if config.get("is_active") else "Inactive", inline=True)
        embed.add_field(name="Task Background (48h)", value="Active" if config.get("backgroundT_status") else "Inactive", inline=True)
        await ctx.send(embed=embed, ephemeral=False)

    @commands.hybrid_command(name="config", description="Used to configure the leveling/tempvoice/moderation settings")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(
        level_up_channel="Channel for level-up messages",
        invite_link="Server invite link",
        role_level_1="Role for level 1",
        role_level_2="Role for level 2",    
        role_level_3="Role for level 3",
        role_level_4="Role for level 4",
        role_level_5="Role for level 5",
        exit_channel="Channel for user exit messages (requires Moderation cog)",
        voice_creator_channel="Channel to create temporary voice channels (requires TempVoice cog)"
    )
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
            updated.append(f"Level-up → {level_up_channel.mention}")

        if invite_link:
            if not invite_link.startswith(("http", "discord.gg")):
                return await ctx.send("Invalid link.", ephemeral=True)
            config["invite_link"] = invite_link
            updated.append(f"Invite → `{invite_link}`")

        roles_map = {1: role_level_1, 2: role_level_2, 3: role_level_3, 4: role_level_4, 5: role_level_5}
        for lvl, role in roles_map.items():
            if role:
                if role.is_default():
                    return await ctx.send("Can't assign @everyone.", ephemeral=True)
                config["role_assignments"][str(lvl)] = role.id
                updated.append(f"Level {lvl} → {role.mention}")

        if exit_channel and self.bot.get_cog("Moderation"):
            mod = self.bot.get_cog("Moderation")
            mod_cfg = mod.get_guild_config(ctx.guild.id)
            mod_cfg["exit_channel_id"] = exit_channel.id
            mod_cfg["exit_channel_name"] = exit_channel.name
            mod._save_config_data()
            updated.append(f"Exit → {exit_channel.mention}")

        if voice_creator_channel and self.bot.get_cog("TempVoice"):
            vc = self.bot.get_cog("TempVoice")
            vc_cfg = vc.get_guild_config(ctx.guild.id)
            vc_cfg["creator_channel_id"] = voice_creator_channel.id
            vc_cfg["creator_channel_name"] = voice_creator_channel.name
            vc._save_config_data()
            updated.append(f"Create VC channel → {voice_creator_channel.mention}")

        if updated:
            self._save_config_data()
            await ctx.send("Configuration updated:\n" + "\n".join(updated), ephemeral=True)
        else:
            await ctx.send("No changes applied.", ephemeral=True)

    @commands.hybrid_command(name="leveling-toggle", description="On/off the leveling system")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(stato="True to activate, False to deactivate")
    async def leveling_toggle(self, ctx: commands.Context, stato: bool):
        config = self.get_guild_config(str(ctx.guild.id))
        config["is_active"] = stato
        self._save_config_data()
        await ctx.send(f"Leveling system {'enabled' if stato else 'disabled'}.", ephemeral=False)

    @commands.hybrid_command(name="bg-task-toggle", description="On/off the background task (kick 48h)")
    @commands.has_permissions(administrator=True)
    @app_commands.describe(stato="True to activate, False to deactivate")
    async def bg_task_toggle(self, ctx: commands.Context, stato: bool):
        config = self.get_guild_config(str(ctx.guild.id))
        config["backgroundT_status"] = stato
        self._save_config_data()
        embed = discord.Embed(
            title="Task Background",
            description=f"Task 48h {'enabled' if stato else 'disabled'}.",
            color=discord.Color.green() if stato else discord.Color.red()
        )
        await ctx.send(embed=embed, ephemeral=False)

async def setup(bot):
    await bot.add_cog(Leveling(bot))