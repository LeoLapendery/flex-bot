import discord

class FlexView(discord.ui.View):
    def __init__(self, creator=None, role_mention=None, user_message=""):
        super().__init__(timeout=None)
        self.users = [creator] if creator else []
        self.role_mention = role_mention or ""
        self.user_message = (user_message + "\n") if user_message else ""
        self.message = None

    @discord.ui.button(label="Rejoindre", style=discord.ButtonStyle.green, custom_id="join_flex")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user not in self.users:
            self.users.append(interaction.user)
            await self.update_message()

        await interaction.response.defer()

    @discord.ui.button(label="Quitter", style=discord.ButtonStyle.red, custom_id="quit_flex")
    async def quit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user in self.users:
            self.users.remove(interaction.user)
            await self.update_message()

        await interaction.response.defer()

    def get_content(self):
        return (
            f"**GROSSE {self.role_mention}** ({len(self.users)}/5):\n"
            f"{self.user_message}"
            + "\n".join(f"- {u.mention}" for u in self.users)
        )

    async def update_message(self, message=None):
        if message:
            self.message = message

        if self.message:
            await self.message.edit(content=self.get_content(), view=self)

    @classmethod
    def persistent(cls):
        return cls()
