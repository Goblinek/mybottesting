import os
import json
import logging
from pathlib import Path
from datetime import timedelta

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or 0)
CONFIG_PATH = Path("config.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
log = logging.getLogger("community-bot")

DEFAULT_CONFIG = {
    "log_channel_id": None,
    "welcome_channel_id": None,
    "voice_category_id": None,
    "voice_lobby_id": None,
    "temporary_voice_ids": [],
    "game_roles": {
        "🎯 CS2": 0,
        "🦖 Rust": 0,
        "⛏️ Minecraft": 0,
        "⚔️ League of Legends": 0,
        "🎮 Other Games": 0
    },
    "ping_roles": {
        "🔔 CS2 Ping": 0,
        "🔔 Rust Ping": 0,
        "🔔 Minecraft Ping": 0,
        "🔔 LoL Ping": 0,
        "📢 Event Ping": 0
    }
}

def load_config():
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            merged = DEFAULT_CONFIG.copy()
            merged.update(data)
            return merged
        except Exception:
            log.exception("Nepodařilo se načíst config.json; používám výchozí nastavení.")
    return DEFAULT_CONFIG.copy()

config = load_config()

def save_config():
    CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

class CommunityBot(commands.Bot):
    async def setup_hook(self):
        self.add_view(RolePanelView())
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Slash příkazy synchronizovány pro server %s", GUILD_ID)
        else:
            await self.tree.sync()
            log.info("Globální slash příkazy synchronizovány.")

bot = CommunityBot(command_prefix="!", intents=intents)

def is_admin(interaction: discord.Interaction) -> bool:
    return bool(interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator)

async def send_log(guild: discord.Guild, message: str):
    channel_id = config.get("log_channel_id")
    channel = guild.get_channel(channel_id) if channel_id else None
    if channel:
        try:
            await channel.send(message)
        except discord.HTTPException:
            log.exception("Nepodařilo se odeslat log.")

class RoleButton(discord.ui.Button):
    def __init__(self, label: str, role_id: int, custom_id: str, style=discord.ButtonStyle.secondary):
        super().__init__(label=label, style=style, custom_id=custom_id)
        self.role_id = role_id

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id) if self.role_id else None
        if not role:
            await interaction.response.send_message(
                "Tato role zatím není nastavena. Požádej správce o spuštění `/setup-roles`.",
                ephemeral=True
            )
            return
        member = interaction.guild.get_member(interaction.user.id)
        if role in member.roles:
            await member.remove_roles(role, reason="Vlastní změna role přes panel")
            await interaction.response.send_message(f"Role **{role.name}** odebrána.", ephemeral=True)
        else:
            await member.add_roles(role, reason="Vlastní změna role přes panel")
            await interaction.response.send_message(f"Role **{role.name}** přidána.", ephemeral=True)

class RolePanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for label, role_id in config["game_roles"].items():
            self.add_item(RoleButton(label, role_id, f"game_role:{label}"))
        for label, role_id in config["ping_roles"].items():
            self.add_item(RoleButton(label, role_id, f"ping_role:{label}"))

@bot.event
async def on_ready():
    log.info("Přihlášen jako %s (%s)", bot.user, bot.user.id)
    await bot.change_presence(activity=discord.Activity(
        type=discord.ActivityType.watching, name="komunitu ProPlayers"
    ))

@bot.event
async def on_member_join(member: discord.Member):
    channel_id = config.get("welcome_channel_id")
    channel = member.guild.get_channel(channel_id) if channel_id else None
    if channel:
        await channel.send(f"👋 Vítej na serveru {member.mention}! Přečti si pravidla a vyber si role.")
    await send_log(member.guild, f"📥 **Přišel nový člen:** {member.mention} (`{member}`)")

@bot.event
async def on_member_remove(member: discord.Member):
    await send_log(member.guild, f"📤 **Člen opustil server:** `{member}`")

@bot.event
async def on_voice_state_update(member, before, after):
    lobby_id = config.get("voice_lobby_id")
    # Vytvoření dočasné místnosti po připojení do lobby
    if after.channel and after.channel.id == lobby_id:
        category_id = config.get("voice_category_id")
        category = member.guild.get_channel(category_id) if category_id else None
        if category:
            try:
                channel = await member.guild.create_voice_channel(
                    name=f"🔊 {member.display_name}",
                    category=category,
                    user_limit=0,
                    reason="Automatické vytvoření dočasné místnosti"
                )
                config.setdefault("temporary_voice_ids", []).append(channel.id)
                save_config()
                await member.move_to(channel)
            except discord.Forbidden:
                log.error("Bot nemá oprávnění vytvářet/přesouvat hlasové místnosti.")
            except discord.HTTPException:
                log.exception("Chyba při vytváření dočasné místnosti.")

    # Smazání prázdné dočasné místnosti
    if before.channel and before.channel.id in config.get("temporary_voice_ids", []):
        if len(before.channel.members) == 0:
            channel_id = before.channel.id
            try:
                await before.channel.delete(reason="Dočasná místnost je prázdná")
            except discord.NotFound:
                pass
            except discord.Forbidden:
                log.error("Bot nemá oprávnění mazat dočasné místnosti.")
            config["temporary_voice_ids"] = [
                x for x in config.get("temporary_voice_ids", []) if x != channel_id
            ]
            save_config()

@bot.tree.command(name="setup-roles", description="Vytvoří herní a oznamovací role a panel pro jejich výběr.")
@app_commands.check(is_admin)
async def setup_roles(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    colours = {
        "CS2": discord.Colour.orange(),
        "Rust": discord.Colour.dark_orange(),
        "Minecraft": discord.Colour.green(),
        "League of Legends": discord.Colour.gold(),
        "Other Games": discord.Colour.blurple()
    }
    for group in ("game_roles", "ping_roles"):
        for label, role_id in list(config[group].items()):
            role = guild.get_role(role_id) if role_id else None
            if role is None:
                colour = discord.Colour.blurple()
                for key, value in colours.items():
                    if key.lower() in label.lower():
                        colour = value
                role = await guild.create_role(name=label, colour=colour, mentionable=(group == "ping_roles"),
                                               reason="Nastavení komunitního bota")
                config[group][label] = role.id
    save_config()

    view = RolePanelView()
    embed = discord.Embed(
        title="🎮 Vyber si své role",
        description=(
            "**Herní role** – označ hry, které hraješ.\n"
            "**Oznamovací role** – zapni si upozornění, která chceš dostávat.\n\n"
            "Kliknutím na tlačítko roli přidáš nebo odebereš."
        ),
        colour=discord.Colour.blurple()
    )
    await interaction.channel.send(embed=embed, view=view)
    await interaction.followup.send("Role jsou připravené a panel byl odeslán do tohoto kanálu.", ephemeral=True)

@bot.tree.command(name="setup-voice", description="Vytvoří lobby pro automatické dočasné hlasové místnosti.")
@app_commands.check(is_admin)
async def setup_voice(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    category = discord.utils.get(guild.categories, name="🔊 DOČASNÉ MÍSTNOSTI")
    if category is None:
        category = await guild.create_category("🔊 DOČASNÉ MÍSTNOSTI")
    lobby = discord.utils.get(category.voice_channels, name="➕ Vytvořit místnost")
    if lobby is None:
        lobby = await guild.create_voice_channel("➕ Vytvořit místnost", category=category)
    config["voice_category_id"] = category.id
    config["voice_lobby_id"] = lobby.id
    save_config()
    await interaction.followup.send(
        f"Hotovo. Připojení do {lobby.mention} vytvoří hráči vlastní místnost.", ephemeral=True
    )

@bot.tree.command(name="setup-logs", description="Nastaví kanál pro systémové a moderátorské logy.")
@app_commands.check(is_admin)
async def setup_logs(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    channel = discord.utils.get(interaction.guild.text_channels, name="bot-logs")
    if channel is None:
        channel = await interaction.guild.create_text_channel("bot-logs")
    config["log_channel_id"] = channel.id
    save_config()
    await interaction.followup.send(f"Logy se budou posílat do {channel.mention}.", ephemeral=True)

@bot.tree.command(name="setup-welcome", description="Nastaví aktuální kanál jako uvítací kanál.")
@app_commands.check(is_admin)
async def setup_welcome(interaction: discord.Interaction):
    config["welcome_channel_id"] = interaction.channel_id
    save_config()
    await interaction.response.send_message("Tento kanál je nyní nastavený pro uvítání nových členů.", ephemeral=True)

@bot.tree.command(name="clear", description="Smaže určený počet posledních zpráv (1–100).")
@app_commands.describe(pocet="Počet zpráv, které se mají smazat")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, pocet: app_commands.Range[int, 1, 100]):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=pocet)
    await interaction.followup.send(f"Smazáno {len(deleted)} zpráv.", ephemeral=True)
    await send_log(interaction.guild, f"🧹 {interaction.user.mention} smazal/a {len(deleted)} zpráv v {interaction.channel.mention}.")

@bot.tree.command(name="timeout", description="Dočasně umlčí člena.")
@app_commands.describe(clen="Člen serveru", minuty="Délka timeoutu v minutách", duvod="Důvod zásahu")
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout_member(interaction: discord.Interaction, clen: discord.Member,
                         minuty: app_commands.Range[int, 1, 40320], duvod: str = "Bez uvedeného důvodu"):
    await clen.timeout(timedelta(minutes=minuty), reason=duvod)
    await interaction.response.send_message(f"{clen.mention} dostal timeout na {minuty} minut.", ephemeral=True)
    await send_log(interaction.guild, f"⏳ {interaction.user.mention} dal timeout {clen.mention} na {minuty} min. Důvod: {duvod}")

@bot.tree.command(name="kick", description="Vyhodí člena ze serveru.")
@app_commands.checks.has_permissions(kick_members=True)
async def kick_member(interaction: discord.Interaction, clen: discord.Member, duvod: str = "Bez uvedeného důvodu"):
    await clen.kick(reason=duvod)
    await interaction.response.send_message(f"Člen {clen} byl vyhozen.", ephemeral=True)
    await send_log(interaction.guild, f"👢 {interaction.user.mention} vyhodil {clen} z důvodu: {duvod}")

@bot.tree.command(name="ban", description="Zablokuje člena na serveru.")
@app_commands.checks.has_permissions(ban_members=True)
async def ban_member(interaction: discord.Interaction, clen: discord.Member, duvod: str = "Bez uvedeného důvodu"):
    await clen.ban(reason=duvod)
    await interaction.response.send_message(f"Člen {clen} byl zabanován.", ephemeral=True)
    await send_log(interaction.guild, f"🔨 {interaction.user.mention} zabanoval {clen}. Důvod: {duvod}")

@bot.tree.command(name="bot-info", description="Zobrazí stav a základní informace o botovi.")
async def bot_info(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 Community Bot", colour=discord.Colour.blurple())
    embed.add_field(name="Stav", value="Online", inline=True)
    embed.add_field(name="Ping", value=f"{round(bot.latency * 1000)} ms", inline=True)
    embed.add_field(name="Server", value=interaction.guild.name, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        message = "Na tento příkaz nemáš potřebná oprávnění."
    else:
        log.exception("Chyba slash příkazu", exc_info=error)
        message = "Příkaz se nepodařilo provést. Zkontroluj oprávnění bota a jeho hierarchii rolí."
    try:
        if interaction.response.is_done():
            await interaction.followup.send(message, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)
    except discord.HTTPException:
        pass

if not TOKEN:
    raise RuntimeError("Chybí DISCORD_TOKEN v souboru .env")
bot.run(TOKEN)
