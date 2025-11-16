import discord
from discord.ext import commands
from flex import FlexView
import os
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
active_flex_sessions = []

@bot.tree.command(name="flex", description="Créer un groupe pour FLEX à 5")
async def flex(interaction: discord.Interaction, message: str = ""):
    guild = interaction.guild
    role = discord.utils.get(guild.roles, name="FLEX")

    if role is None:
        await interaction.response.send_message("⚠️ Le rôle `@FLEX` n'existe pas sur ce serveur.", ephemeral=True)
        return

    view = FlexView(creator=interaction.user, role_mention=role.mention, user_message=message)

    msg = await interaction.channel.send(
        content=view.get_content(),
        view=view,
        allowed_mentions=discord.AllowedMentions(roles=True),
    )

    view.message = msg
    active_flex_sessions.append(view)
    bot.add_view(view)

@bot.event
async def on_ready():
    bot.add_view(FlexView.persistent())
    await bot.tree.sync()
    print(f"✅ Connecté en tant que {bot.user}")

bot.run(os.getenv("DISCORD_TOKEN"))
