"""Bot Discord dédié à l'organisation des flex LoL.

Commande /flex :
  - ping le rôle @FLEX (nom configurable)
  - affiche un embed avec 2 boutons (rejoindre / se retirer)
  - garde la liste des participants en mémoire + sur disque (data/flex_sessions.json)
  - expire automatiquement après FLEX_TTL_HOURS (par défaut 6h), ou après la
    durée passée en paramètre de la commande
"""
import logging
import os
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv

from flex import FlexView
from storage import load_sessions, save_sessions, utcnow

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("flexbot")

TOKEN = os.getenv("DISCORD_TOKEN")
ROLE_NAME = os.getenv("FLEX_ROLE_NAME", "FLEX")
DEFAULT_TTL_HOURS = float(os.getenv("FLEX_TTL_HOURS", "6"))
MAX_PLAYERS = int(os.getenv("FLEX_MAX_PLAYERS", "5"))
ALLOWED_GUILD_IDS = {
    int(g) for g in os.getenv("ALLOWED_GUILD_IDS", "").split(",") if g.strip()
}

intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # nécessaire pour bien résoudre les rôles/membres

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# message_id -> FlexView (sessions actuellement actives, en mémoire)
active_sessions: dict[int, FlexView] = {}


def persist_sessions() -> None:
    save_sessions({str(mid): view.to_dict() for mid, view in active_sessions.items()})


@bot.event
async def on_guild_join(guild: discord.Guild):
    if ALLOWED_GUILD_IDS and guild.id not in ALLOWED_GUILD_IDS:
        logger.warning("Serveur non autorisé (%s / %s), je quitte.", guild.name, guild.id)
        await guild.leave()


@bot.tree.command(name="flex", description="Lance un appel au flex à 5 et ping le rôle @FLEX")
@app_commands.describe(
    message="Message optionnel à afficher (ex: 'ce soir 21h')",
    duree_heures="Durée avant expiration de l'appel, en heures (défaut: configuré sur le bot)",
)
async def flex(interaction: discord.Interaction, message: str = "", duree_heures: Optional[float] = None):
    guild = interaction.guild
    if guild is None:
        await interaction.response.send_message("⚠️ Cette commande ne fonctionne que sur un serveur.", ephemeral=True)
        return

    role = discord.utils.get(guild.roles, name=ROLE_NAME)

    if role is None:
        await interaction.response.send_message(
            f"⚠️ Le rôle `@{ROLE_NAME}` n'existe pas sur ce serveur. Crée-le d'abord "
            f"(Paramètres du serveur → Rôles) puis réessaie.",
            ephemeral=True,
        )
        return

    ttl_hours = duree_heures if duree_heures and duree_heures > 0 else DEFAULT_TTL_HOURS

    view = FlexView(
        creator_id=interaction.user.id,
        role_id=role.id,
        user_message=message,
        max_players=MAX_PLAYERS,
        ttl_hours=ttl_hours,
        persist_callback=persist_sessions,
    )

    await interaction.response.send_message(
        content=role.mention,
        embed=view.build_embed(),
        view=view,
        allowed_mentions=discord.AllowedMentions(roles=True),
    )
    sent = await interaction.original_response()
    view.bind(message_id=sent.id, channel_id=sent.channel.id, guild_id=interaction.guild_id)

    active_sessions[sent.id] = view
    bot.add_view(view, message_id=sent.id)
    persist_sessions()


async def _finalize_expired(mid: int, view: FlexView) -> None:
    """Marque la vue comme expirée, désactive ses boutons et met à jour le
    message Discord en conséquence."""
    view.expire()
    try:
        channel = bot.get_channel(view.channel_id) or await bot.fetch_channel(view.channel_id)
        msg = await channel.fetch_message(mid)
        await msg.edit(embed=view.build_embed(), view=view)
    except discord.HTTPException as exc:
        logger.warning("Impossible de mettre à jour le message expiré %s: %s", mid, exc)


@tasks.loop(minutes=2)
async def expire_sessions():
    now = utcnow()
    expired_ids = [mid for mid, view in active_sessions.items() if not view.expired and view.is_expired(now)]

    for mid in expired_ids:
        view = active_sessions.pop(mid)
        await _finalize_expired(mid, view)

    if expired_ids:
        persist_sessions()


@bot.event
async def on_ready():
    # Recharge les sessions actives depuis le disque (redémarrage du bot)
    raw = load_sessions()
    now = utcnow()
    to_finalize: list[tuple[int, FlexView]] = []

    for mid_str, data in raw.items():
        mid = int(mid_str)
        view = FlexView.from_dict(data, persist_callback=persist_sessions)
        view.message_id = mid

        if view.is_expired(now) and not view.expired:
            # Expirée pendant que le bot était hors ligne : on met à jour le
            # message pour désactiver les boutons, sans la garder active.
            to_finalize.append((mid, view))
            continue

        active_sessions[mid] = view
        bot.add_view(view, message_id=mid)

    for mid, view in to_finalize:
        bot.add_view(view, message_id=mid)  # pour pouvoir éditer/désactiver proprement
        await _finalize_expired(mid, view)

    if to_finalize:
        persist_sessions()

    if not expire_sessions.is_running():
        expire_sessions.start()

    synced = await bot.tree.sync()
    logger.info("✅ %d commande(s) synchronisée(s) : %s", len(synced), [c.name for c in synced])
    logger.info("Connecté en tant que %s (%d session(s) active(s) rechargée(s))", bot.user, len(active_sessions))


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("DISCORD_TOKEN manquant : vérifie ton fichier .env")
    bot.run(TOKEN)
