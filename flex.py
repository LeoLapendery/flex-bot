"""Vue Discord (boutons) pour un appel au Flex.

Chaque session (= un message envoyé par /flex) est représentée par une
instance de FlexView. L'état (participants, horodatages...) est sérialisable
en JSON via to_dict()/from_dict() afin de survivre à un redémarrage du bot.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Optional

import discord

from storage import utcnow

JOIN_CUSTOM_ID = "flex_join"
LEAVE_CUSTOM_ID = "flex_leave"


class FlexView(discord.ui.View):
    def __init__(
        self,
        *,
        creator_id: int,
        role_id: int,
        user_message: str = "",
        max_players: int = 5,
        ttl_hours: float = 6,
        created_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        persist_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.role_id = role_id
        self.user_message = user_message or ""
        self.max_players = max_players
        self.participant_ids: list[int] = [creator_id]
        self.created_at = created_at or utcnow()
        self.expires_at = expires_at or (self.created_at + timedelta(hours=ttl_hours))
        self.expired = False
        self.persist_callback = persist_callback

        # Renseignés après l'envoi du message (voir bind())
        self.guild_id: Optional[int] = None
        self.channel_id: Optional[int] = None
        self.message_id: Optional[int] = None

        self._sync_buttons()

    # ------------------------------------------------------------------
    # Cycle de vie / persistance
    # ------------------------------------------------------------------
    def bind(self, message_id: int, channel_id: int, guild_id: Optional[int]) -> None:
        self.message_id = message_id
        self.channel_id = channel_id
        self.guild_id = guild_id

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        return (now or utcnow()) >= self.expires_at

    def expire(self) -> None:
        self.expired = True
        self._sync_buttons()

    def _save(self) -> None:
        if self.persist_callback:
            self.persist_callback()

    def to_dict(self) -> dict:
        return {
            "guild_id": self.guild_id,
            "channel_id": self.channel_id,
            "creator_id": self.creator_id,
            "role_id": self.role_id,
            "user_message": self.user_message,
            "max_players": self.max_players,
            "participants": list(self.participant_ids),
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "expired": self.expired,
        }

    @classmethod
    def from_dict(cls, data: dict, persist_callback: Optional[Callable[[], None]] = None) -> "FlexView":
        view = cls(
            creator_id=data["creator_id"],
            role_id=data["role_id"],
            user_message=data.get("user_message", ""),
            max_players=data.get("max_players", 5),
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            persist_callback=persist_callback,
        )
        # On évite les doublons tout en gardant l'ordre d'arrivée
        view.participant_ids = list(dict.fromkeys(data.get("participants", [])))
        view.guild_id = data.get("guild_id")
        view.channel_id = data.get("channel_id")
        view.expired = data.get("expired", False)
        view._sync_buttons()
        return view

    # ------------------------------------------------------------------
    # Rendu
    # ------------------------------------------------------------------
    def build_embed(self) -> discord.Embed:
        full = len(self.participant_ids) >= self.max_players

        if self.expired:
            color = discord.Color.greyple()
            status = "⏱️ Appel de la flex expiré..."
        elif full:
            color = discord.Color.green()
            status = "✅ Groupe complet"
        else:
            color = discord.Color.blurple()
            status = "🔎 En attente de joueurs…"

        participants_text = (
            "\n".join(f"{i}. <@{uid}>" for i, uid in enumerate(self.participant_ids, start=1))
            or "_Personne pour l'instant._"
        )

        embed = discord.Embed(
            title="🎮 C'est l'heure de FLEX",
            description=self.user_message or None,
            color=color,
        )
        embed.add_field(name="Organisé par", value=f"<@{self.creator_id}>", inline=True)
        embed.add_field(name="Statut", value=status, inline=True)
        embed.add_field(
            name=f"Participants ({len(self.participant_ids)}/{self.max_players})",
            value=participants_text,
            inline=False,
        )

        expires_ts = int(self.expires_at.timestamp())
        embed.add_field(
            name="Expiration",
            value="Expiré" if self.expired else f"<t:{expires_ts}:R> (<t:{expires_ts}:f>)",
            inline=False,
        )
        embed.set_footer(text="✅ pour rejoindre • ❌ pour partir")
        embed.timestamp = self.created_at
        return embed

    def _sync_buttons(self) -> None:
        full_or_expired = self.expired or len(self.participant_ids) >= self.max_players
        for item in self.children:
            if not isinstance(item, discord.ui.Button):
                continue
            if item.custom_id == JOIN_CUSTOM_ID:
                item.disabled = full_or_expired
            elif item.custom_id == LEAVE_CUSTOM_ID:
                item.disabled = self.expired

    # ------------------------------------------------------------------
    # Boutons
    # ------------------------------------------------------------------
    @discord.ui.button(label="Je suis chaud", style=discord.ButtonStyle.success, custom_id=JOIN_CUSTOM_ID, emoji="✅")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.expired:
            await interaction.response.send_message("⏱️ Cet appel à la flex est terminé.", ephemeral=True)
            return

        if interaction.user.id in self.participant_ids:
            await interaction.response.send_message("T'es déjà dans la liste !", ephemeral=True)
            return

        if len(self.participant_ids) >= self.max_players:
            await interaction.response.send_message(
                f"🚫 Le groupe est déjà complet ({self.max_players}/{self.max_players}).", ephemeral=True
            )
            return

        self.participant_ids.append(interaction.user.id)
        self._sync_buttons()
        self._save()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Pas dispo", style=discord.ButtonStyle.danger, custom_id=LEAVE_CUSTOM_ID, emoji="❌")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in self.participant_ids:
            await interaction.response.send_message("T'es pas dans la liste...", ephemeral=True)
            return

        self.participant_ids.remove(interaction.user.id)
        self._sync_buttons()
        self._save()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)
