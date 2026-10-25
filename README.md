# Flex Bot — LoL

Bot Discord mono-commande pour organiser un flex à 5 sur League of Legends.

`/flex [message] [duree_heures]` :
- ping le rôle `@FLEX`
- poste un embed avec 2 boutons : **✅ Je suis chaud** / **❌ Pas dispo**
- un clic sur ✅ ajoute ton pseudo à la liste (max 5, bouton grisé une fois complet)
- un clic sur ❌ te retire de la liste si tu y étais (sinon ne fait rien)
- la session reste active en mémoire **et** sur disque (`data/flex_sessions.json`),
  donc elle survit à un redémarrage du bot
- elle expire automatiquement après un délai configurable (6h par défaut, ou la
  valeur passée dans `duree_heures`) : les boutons se désactivent et le message
  affiche "Expiré"

## Ce qui a changé par rapport à l'ancienne version

- UI : embed propre (titre, statut, liste numérotée, compteur X/5, horodatage
  d'expiration en "il y a / dans X" via le format Discord `<t:...:R>`) au lieu
  d'un simple message texte.
- Les boutons se désactivent automatiquement (groupe complet / session expirée).
- Persistance JSON réelle : avant, après un redémarrage, toutes les anciennes
  sessions partageaient le même état générique et perdaient leur liste de
  participants. Maintenant chaque session est sauvegardée individuellement et
  restaurée telle quelle au redémarrage (`bot.add_view(view, message_id=...)`).
- Expiration automatique (nouveau, vérifiée toutes les 2 minutes).
- Config externalisée dans `.env` (nom du rôle, nombre de joueurs max, durée
  par défaut, serveurs autorisés).
- Dockerfile + docker-compose fournis pour un hébergement propre sur ton
  serveur perso, avec volume persistant pour `data/`.

Le reste (hello/kick_vocal/jokes) présent dans l'autre repo `BOT/` n'a pas été
repris ici : ce bot reste focalisé sur le flex, comme demandé. Si tu veux
fusionner les deux bots en un seul, dis-le moi.

## 1. Configuration côté Discord

### 1.1 Créer l'application / le bot (si pas déjà fait)

1. https://discord.com/developers/applications → **New Application**
2. Onglet **Bot** → **Reset Token** → copie le token (tu l'as déjà dans `.env`)
3. Toujours sur l'onglet **Bot**, active **Server Members Intent** (requis par
   `intents.members = True`). Pas besoin de l'intent "Message Content" cette
   fois, le bot ne lit plus les messages.

### 1.2 Inviter le bot sur ton serveur

Génère un lien d'invitation : onglet **OAuth2 → URL Generator**
- Scopes : `bot` + `applications.commands`
- Permissions bot : `View Channels`, `Send Messages`, `Embed Links`,
  `Read Message History`, `Mention Everyone` (nécessaire pour ping `@FLEX`
  même si le rôle n'est pas mentionnable par les membres classiques)

Ou directement avec ce lien (remplace `CLIENT_ID` par l'ID de ton application,
visible sur l'onglet **General Information**) :

```
https://discord.com/api/oauth2/authorize?client_id=CLIENT_ID&permissions=216064&scope=bot%20applications.commands
```

Ouvre-le, choisis ton serveur, valide.

### 1.3 Créer le rôle FLEX

Sur ton serveur : Paramètres → Rôles → **Créer un rôle**, nomme-le exactement
`FLEX` (ou change `FLEX_ROLE_NAME` dans `.env` si tu veux un autre nom).
Deux options pour que le ping fonctionne :
- coche **"Autoriser la mention de ce rôle par n'importe qui"** sur le rôle, OU
- laisse tel quel : comme le bot a la permission `Mention Everyone` (donnée à
  l'étape 1.2), il pourra pinger le rôle même non-mentionnable.

Chaque joueur doit ensuite s'auto-attribuer le rôle `FLEX` (ou tu les ajoutes
manuellement) pour recevoir le ping.

## 2. Configuration du bot (`.env`)

Le fichier `.env` existe déjà avec ton token. Les autres variables (déjà
présentes, à ajuster si besoin) :

| Variable | Rôle | Défaut |
|---|---|---|
| `DISCORD_TOKEN` | Token du bot | *(obligatoire)* |
| `FLEX_ROLE_NAME` | Nom exact du rôle à ping | `FLEX` |
| `FLEX_MAX_PLAYERS` | Taille max du groupe | `5` |
| `FLEX_TTL_HOURS` | Durée avant expiration auto | `6` |
| `ALLOWED_GUILD_IDS` | IDs de serveurs autorisés, séparés par virgule (vide = tous) | *(vide)* |
| `FLEX_DATA_FILE` | Chemin du fichier JSON de sauvegarde | `data/flex_sessions.json` |

`.env.example` documente la même chose si tu dois en recréer un ailleurs.
**Ne commit jamais `.env`** (déjà dans `.gitignore`).

## 3. Déploiement sur ton serveur (laptop Home Assistant / MotionEye)

Ça part du principe que le serveur tourne sous Linux avec **Docker** déjà
installé (souvent le cas si MotionEye tourne déjà en conteneur). Si ce n'est
pas le cas, voir [3.4](#34-si-docker-nest-pas-installé).

### 3.1 Copier le projet sur le serveur

Depuis PowerShell/Windows, deux options :

**Option A — via Git (recommandé, permet de faire `git pull` pour les mises à jour)**

```powershell
ssh user@IP_DU_SERVEUR
# une fois connecté, sur le serveur :
git clone https://github.com/LeoLapendery/flex-bot.git
cd flex-bot
```

Puis crée le `.env` sur le serveur (il n'est pas dans Git) :
```bash
nano .env
# colle le contenu de ton .env local (DISCORD_TOKEN=... etc.)
```

**Option B — copie directe avec `scp` depuis Windows (si tu ne veux pas passer par Git)**

```powershell
scp -r C:\Users\leopo\Sites\FlexBot\flex-bot user@IP_DU_SERVEUR:/home/user/flex-bot
```

(Ça copie aussi ton `.env` local tel quel, pratique pour un premier déploiement.)

### 3.2 Lancer le bot avec Docker Compose

Une fois connecté en SSH, dans le dossier du projet :

```bash
cd flex-bot
docker compose up -d --build
```

(Si ta version de Docker est plus ancienne, utilise `docker-compose` avec un
tiret au lieu de `docker compose`.)

Vérifier que ça tourne :
```bash
docker compose logs -f flex-bot
```

Tu dois voir `Connecté en tant que <nom du bot>` et la liste des commandes
synchronisées. `Ctrl+C` pour sortir des logs (le bot continue de tourner).

### 3.3 Mettre à jour le bot plus tard

```bash
cd flex-bot
git pull            # si tu as utilisé l'option A
docker compose up -d --build
```

Le fichier `data/flex_sessions.json` est monté en volume (`./data:/app/data`),
donc les sessions actives survivent aux mises à jour et redémarrages du
conteneur.

### 3.4 Si Docker n'est pas installé

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# déconnecte-toi / reconnecte-toi en SSH pour que le groupe prenne effet
```
Puis reprends à l'étape 3.2.

### 3.5 Alternative sans Docker (venv + systemd)

Si tu préfères ne pas utiliser Docker sur cette machine :

```bash
cd flex-bot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Crée un service systemd pour qu'il tourne en continu et redémarre tout seul :

```bash
sudo tee /etc/systemd/system/flex-bot.service > /dev/null << 'EOF'
[Unit]
Description=Flex Bot Discord
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/user/flex-bot
ExecStart=/home/user/flex-bot/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now flex-bot
sudo systemctl status flex-bot
journalctl -u flex-bot -f   # pour suivre les logs
```

(Adapte `/home/user/flex-bot` au chemin réel sur ton serveur.)

## 4. Vérification finale

Sur Discord, tape `/flex` dans un salon où le bot a accès. Si la commande
n'apparaît pas tout de suite, attends ~1 minute (la synchronisation globale
des commandes slash peut prendre un peu de temps la première fois) ou relance
Discord (Ctrl+R).
