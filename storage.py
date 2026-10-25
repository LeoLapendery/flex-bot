"""Persistance JSON des sessions de flex actives.

Le fichier est réécrit entièrement à chaque sauvegarde (écriture atomique via
un fichier temporaire + rename) pour éviter de corrompre les données si le
bot est tué en plein milieu d'une écriture.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

DATA_FILE = Path(os.getenv("FLEX_DATA_FILE", "data/flex_sessions.json"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def load_sessions() -> dict:
    """Charge les sessions sauvegardées. Renvoie {} si le fichier est absent
    ou illisible (on ne plante jamais le démarrage du bot pour ça)."""
    if not DATA_FILE.exists():
        return {}
    try:
        with DATA_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def save_sessions(sessions: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2, ensure_ascii=False)
    tmp.replace(DATA_FILE)
