from discord.ext import tasks, commands

import discord
from discord import app_commands
import requests
import urllib.parse
import os
import json

from dotenv import load_dotenv
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CLASH_TOKEN = os.getenv("CLASH_TOKEN")
BASE_URL = "https://api.clashroyale.com/v1"
headers = {"Authorization": f"Bearer {CLASH_TOKEN}"}

# JSON-bestand voor opslag
DATA_FILE = "users.json"

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

users = load_data()

def get_player(tag: str):
    tag_enc = urllib.parse.quote(tag.strip().upper())
    url = f"{BASE_URL}/players/%23{tag_enc}"
    r = requests.get(url, headers=headers)
    print(url)
    print(r)
    if r.status_code == 200:
        return r.json()
    else:
        return None

def get_clan(tag: str):
    tag_enc = urllib.parse.quote(tag.strip().upper())
    url = f"{BASE_URL}/clans/{tag_enc}"
    print(url)
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()
    else:
        return None

class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

client = MyClient()

@client.event
async def on_ready():
    print(f"✅ Ingelogd als {client.user}")
    check_users.start()

# --- Commando om je tag te linken ---
@client.tree.command(name="link", description="Koppel jouw Clash Royale speler-tag")
async def link(interaction: discord.Interaction, tag: str):
    users[str(interaction.user.id)]['tag'] = tag.upper().replace("#", "")
    users[str(interaction.user.id)]['checkTag'] = tag.upper().replace("#", "")
    users[str(interaction.user.id)]['alert'] = "False"
    save_data(users)
    await interaction.response.send_message(f"🔗 Jouw account is gekoppeld aan tag `{tag.upper()}`", ephemeral=True)

@tasks.loop(minutes=1)
async def check_users():
    print("⏰ Running hourly check...")
    data = load_data()
    for user_id, pref in data.items():
        tag = pref.get("tag")
        check_tag = pref.get("checkTag")
        alert_value = str(pref.get("alert", "False")).lower() == "true"  # cast naar bool

        # alleen verder als alerts aanstaan
        if not alert_value:
            continue

        # haal speler-data op
        player_data = get_player(tag)
        check_data = get_player(check_tag)

        if not player_data or not check_data:
            print(f"❌ kon data niet ophalen voor {user_id}")
            continue

        # trophies vergelijken
        if check_data.get("trophies", 0) > player_data.get("trophies", 0):
            print("ingehaalt")
            member = await client.fetch_user(int(user_id))
            print(member)
            if member:
                try:
                    await member.send("🔔 Je bent ingehaald!")
                    print(f"Pinged {member}")
                except Exception as e:
                    print(f"Kon {member} niet pingen: {e}")

# --- Commando: /player (zonder dat je tag hoeft te geven) ---
@client.tree.command(name="player", description="Bekijk info over jouw (gelinkte) of iemand anders zijn Clash Royale account")
async def player(interaction: discord.Interaction, tag: str = None):
    await interaction.response.defer()  # laat Discord weten dat de bot bezig is

    user_id = str(interaction.user.id)

    if tag:
        tag_to_use = tag.upper()
    else:
        if user_id not in users:
            await interaction.followup.send(
                "❌ Je hebt geen tag gegeven en ook geen gelinkte tag. Gebruik `/link <tag>`.",
                ephemeral=True
            )
            return
        tag_to_use = users[user_id]['tag']

    data = get_player(tag_to_use)
    if not data:
        await interaction.followup.send("❌ Fout bij ophalen spelerdata.", ephemeral=True)
        return


    name = data.get("name")
    level = data.get("expLevel")
    trophies = data.get("trophies")
    clan_name = data.get("clan", {}).get("name", "Geen clan")
    wins = data.get("wins")
    clan_tag = data.get("clan", {}).get("tag", "Geen clan")

    await interaction.followup.send(
        f"Speler: {name} (Level {level}) 👑\n"
        f"Trofeeën: {trophies} 🏆\n"
        f"Clannaam: {clan_name}, Clantag: {clan_tag} ⛵ (meer details met /clan)\n"
        f"Wins: {wins} 🎉"
    )

@client.tree.command(name="zetchecktag", description="zet de tag van degene die je wilt checken")
async def player(interaction: discord.Interaction, tag: str = None):
    await interaction.response.defer()  # laat Discord weten dat de bot bezig is
    user_id = str(interaction.user.id)
    users[str(interaction.user.id)]['checkTag'] = tag.upper().replace("#", "")
    save_data(users)
    await interaction.followup.send("check tag succesvol gelinkt")


@client.tree.command(name="clan", description="Bekijk info over jouw of iemand anders zijn clan")
async def player(interaction: discord.Interaction, tag: str = None):
    await interaction.response.defer()  # laat Discord weten dat de bot bezig is

    user_id = str(interaction.user.id)

    if tag:
        tag_to_use = tag.upper()
    else:
        if user_id not in users:
            await interaction.followup.send(
                "❌ Je hebt geen tag gegeven en ook geen gelinkte tag. Gebruik `/link <tag>`.",
                ephemeral=True
            )
            return
        tag_to_use = users[user_id]['tag']

    data = get_player(tag_to_use)
    print(data)
    if not data:
        await interaction.followup.send("❌ Fout bij ophalen spelerdata.", ephemeral=True)
        return

    print(data.get("clan", {}).get("tag"))
    clandata = get_clan(data.get("clan", {}).get("tag"))
    name = clandata.get("name")
    tag = clandata.get("tag")
    description = clandata.get("description")
    typeOpen = clandata.get("type")
    requiredTrophies = clandata.get("requiredTrophies")
    members = clandata.get("members")
    memberList = clandata.get("memberList")
    for mem in memberList:
        if mem.get("role") == "leader":
            leader = mem.get("name")
            break
        else:
            leader = "onb"
    await interaction.followup.send(
        f"Clan: {name} 👑\n"
        f"Tag: {name} 🧨\n"
        f"Beschrijving: {description} ✨\n"
        f"Joinbaar: {typeOpen}, Minimumtrofeeën: {requiredTrophies} 🎁\n"
        f"Aantal spelers: {members} 🙋\n"
        f"leider: {leader} 🤴\n"
    )

client.run(DISCORD_TOKEN)
