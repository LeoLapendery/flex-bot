import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

active_flex_sessions = []

FLEX_DURATION_HOURS = 6  # Durée normale
EMPTY_TIMEOUT_MINUTES = 10  # Durée avant fermeture d'une flex vide


class FlexView(discord.ui.View):
    def __init__(self, author, role_mention):
        super().__init__(timeout=None)
        self.participants = [author]
        self.active = True
        self.role_mention = role_mention
        self.creation_time = datetime.utcnow()
        self.empty_task = None  # Task pour la fermeture si vide

    async def update_message(self):
        if hasattr(self, "message"):
            content = f"**GROSSE {self.role_mention} ??** ({len(self.participants)}/5 flexeurs) :\n" + \
                      "\n".join([f"- {p.mention}" for p in self.participants])
            await self.message.edit(content=content, view=self)

    async def schedule_empty_check(self):
        if self.empty_task:
            self.empty_task.cancel()
        if len(self.participants) == 0:
            self.empty_task = asyncio.create_task(self.expire_empty())

    async def expire_empty(self):
        await asyncio.sleep(EMPTY_TIMEOUT_MINUTES * 60)
        await expire_session(self)

    @discord.ui.button(label="OUI JE FLEX", style=discord.ButtonStyle.green)
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("C'est fini... connard", ephemeral=True)
            return

        for session in active_flex_sessions:
            if session is not self and interaction.user in session.participants:
                session.participants.remove(interaction.user)
                await session.update_message()
                await session.schedule_empty_check()

        if interaction.user in self.participants:
            await interaction.response.send_message("T'es déjà dedans, connard", ephemeral=True)
            return

        if len(self.participants) >= 5:
            await interaction.response.send_message("ILS SONT DEJA 5, CONNARD", ephemeral=True)
            return

        self.participants.append(interaction.user)
        await interaction.response.defer()
        await self.update_message()

        # Annule la fermeture si elle était prévue
        if self.empty_task:
            self.empty_task.cancel()
            self.empty_task = None

    @discord.ui.button(label="C'EST MORT", style=discord.ButtonStyle.red)
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.active:
            await interaction.response.send_message("C'est fini... connard", ephemeral=True)
            return

        if interaction.user not in self.participants:
            await interaction.response.send_message("Pourquoi tu cliques là enculé ? VIENS FLEX", ephemeral=True)
            return

        self.participants.remove(interaction.user)
        await interaction.response.defer()
        await self.update_message()
        await self.schedule_empty_check()


async def expire_session(view: FlexView):
    view.active = False
    if hasattr(view, "message"):
        content = f"**La {view.role_mention} est terminée...** ({len(view.participants)}/5 flexeurs)\n" + \
                  "\n".join([f"- {p.mention}" for p in view.participants])
        try:
            await view.message.edit(content=content, view=None)
        except Exception:
            pass

    if view in active_flex_sessions:
        active_flex_sessions.remove(view)

@bot.tree.command(name="flex", description="Créer un groupe pour FLEX à 5")
async def flex(interaction: discord.Interaction):
    guild = interaction.guild
    role = discord.utils.get(guild.roles, name="FLEX")
    if not role:
        await interaction.response.send_message("⚠️ Le rôle `@FLEX` n'existe pas sur ce serveur.", ephemeral=True)
        return

    view = FlexView(interaction.user, role.mention)
    content = f"**GROSSE {role.mention} ??** (1/5 flexeurs)\n- {interaction.user.mention}"
    await interaction.response.send_message(content=content, view=view, allowed_mentions=discord.AllowedMentions(roles=True))

    view.message = await interaction.original_response()
    active_flex_sessions.append(view)

    # Expiration normale après 6h
    bot.loop.create_task(expire_session_timer(view))


async def expire_session_timer(view: FlexView):
    await asyncio.sleep(FLEX_DURATION_HOURS * 3600)
    await expire_session(view)


@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Connecté en tant que {bot.user}")

bot.run("DISCORD_TOKEN")
