# bot.py — Version finale avec onglets personnalisables
import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
import json
import asyncio

# -------------------------------
# Charger la config
# -------------------------------
with open("config.json") as f:
    config = json.load(f)

TOKEN = config["token"]
GUILD_ID = config["guild_id"]
STAFF_ROLE = config.get("staff_role", "Staff")
DATABASE = config.get("database", "profiles.db")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# -------------------------------
# Progression / paramètres
# -------------------------------
LEVEL_THRESHOLDS = {1:0, 2:10, 3:18, 4:25, 5:35, 6:50}
LEVEL_UP_POINTS = {(1,2):4, (2,3):4, (3,4):5, (4,5):5, (5,6):6}
UNLOCK_LEVELS = {"technique_1":2, "technique_2":4, "ultimate":6}

def prp_to_level(prp: int) -> int:
    lvl = 1
    for level, thresh in sorted(LEVEL_THRESHOLDS.items()):
        if prp >= thresh:
            lvl = level
    return lvl

async def award_level_up_rewards(user_id: int, old_level: int, new_level: int):
    total_points = 0
    unlocked = []
    for lvl in range(old_level, new_level):
        pts = LEVEL_UP_POINTS.get((lvl, lvl+1), 0)
        total_points += pts
    async with aiosqlite.connect(DATABASE) as db:
        if total_points > 0:
            await db.execute("UPDATE profiles SET niveau = ?, stat_points = stat_points + ? WHERE user_id = ?",
                             (new_level, total_points, user_id))
        else:
            await db.execute("UPDATE profiles SET niveau = ? WHERE user_id = ?", (new_level, user_id))
        if new_level >= UNLOCK_LEVELS["technique_1"]:
            await db.execute("UPDATE profiles SET technique_1_unlock = 1 WHERE user_id = ?", (user_id,))
            unlocked.append("Technique 1")
        if new_level >= UNLOCK_LEVELS["technique_2"]:
            await db.execute("UPDATE profiles SET technique_2_unlock = 1 WHERE user_id = ?", (user_id,))
            unlocked.append("Technique 2")
        if new_level >= UNLOCK_LEVELS["ultimate"]:
            await db.execute("UPDATE profiles SET ultimate_unlock = 1 WHERE user_id = ?", (user_id,))
            unlocked.append("Ultime")
        await db.commit()
    return total_points, unlocked

# -------------------------------
# DB init + utilitaires
# -------------------------------
async def init_db():
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                user_id INTEGER PRIMARY KEY,
                nom TEXT, prenom TEXT, surnom TEXT, age TEXT, affiliation TEXT,
                profil_image TEXT, stats_image TEXT, alter_nom TEXT, alter_description TEXT, alter_image TEXT,
                technique_1 TEXT, technique_1_unlock INTEGER DEFAULT 0,
                technique_2 TEXT, technique_2_unlock INTEGER DEFAULT 0,
                ultimate TEXT, ultimate_unlock INTEGER DEFAULT 0,
                prp INTEGER DEFAULT 0, niveau INTEGER DEFAULT 1, stat_points INTEGER DEFAULT 8,
                force INTEGER DEFAULT 0, vitesse INTEGER DEFAULT 0, endurance INTEGER DEFAULT 0,
                controle INTEGER DEFAULT 0, puissance INTEGER DEFAULT 0, reactivite INTEGER DEFAULT 0
            )
        """)
        await db.commit()

async def get_profile(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        cur = await db.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cur.description]
        return dict(zip(cols, row))

async def delete_profile(user_id: int):
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
        await db.commit()

def is_staff(member: discord.Member) -> bool:
    return STAFF_ROLE in [r.name for r in member.roles]

# -------------------------------
# On ready (sync guild commands)
# -------------------------------
@bot.event
async def on_ready():
    await init_db()
    guild = discord.Object(id=GUILD_ID)
    await tree.sync(guild=guild)
    print(f"Bot connecté en tant {bot.user} — commandes synchronisées sur le serveur {GUILD_ID}")

# -------------------------------
# Profile View avec onglets et icônes
# -------------------------------
class ProfileView(discord.ui.View):
    def __init__(self, profile: dict, config: dict):
        super().__init__(timeout=None)
        self.profile = profile
        self.config = config

    # -----------------------
    # ------- PROFIL --------
    # -----------------------
    @discord.ui.button(label="Profil", style=discord.ButtonStyle.primary)
    async def profil_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.profile
        embed = discord.Embed(
            title=f"{p.get('nom','Non défini')} {p.get('prenom','')}".strip(),
            description=(
                f"⭐ **Surnom :** {p.get('surnom','Non défini')}\n"
                f"🎂 **Âge :** {p.get('age','Non défini')}\n"
                f"🏫 **Affiliation :** {p.get('affiliation','Non défini')}"
            ),
            color=discord.Color.blue()
        )

        # Thumbnail fixe
        embed.set_thumbnail(url="https://i.pinimg.com/736x/fe/dc/37/fedc370c66c4ca7114d03dd9a299bc4a.jpg")

        # Image personnalisée
        if p.get("profil_image"):
            embed.set_image(url=p["profil_image"])

        # Icone onglet
        if self.config.get("profil_icon_url"):
            embed.set_author(name="📘 Profil", icon_url=self.config["profil_icon_url"])

        # Champs supplémentaires
        embed.add_field(name="📊 Niveau", value=str(p.get("niveau",1)), inline=True)
        embed.add_field(name="💠 PRP", value=str(p.get("prp",0)), inline=True)
        embed.add_field(name="📌 Points à répartir", value=str(p.get("stat_points",0)), inline=True)

        await interaction.response.edit_message(embed=embed, view=self)

    # -----------------------
    # -------- STATS --------
    # -----------------------
    @discord.ui.button(label="Statistiques", style=discord.ButtonStyle.secondary)
    async def stats_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.profile
        embed = discord.Embed(title="📊 Statistiques", color=discord.Color.green())

        embed.add_field(name="💪 Force", value=p.get("force",0), inline=True)
        embed.add_field(name="⚡ Vitesse", value=p.get("vitesse",0), inline=True)
        embed.add_field(name="🛡 Endurance", value=p.get("endurance",0), inline=True)
        embed.add_field(name="🎯 Contrôle", value=p.get("controle",0), inline=True)
        embed.add_field(name="🔥 Puissance", value=p.get("puissance",0), inline=True)
        embed.add_field(name="✨ Réactivité", value=p.get("reactivite",0), inline=True)

        embed.add_field(name="🔮 PRP", value=str(p.get("prp",0)), inline=False)

        # PAS DE thumbnail (comme demandé)

        # Image personnalisée
        if p.get("stats_image"):
            embed.set_image(url=p["stats_image"])

        await interaction.response.edit_message(embed=embed, view=self)

    # -----------------------
    # -------- ALTER --------
    # -----------------------
    @discord.ui.button(label="Alter", style=discord.ButtonStyle.success)
    async def alter_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        p = self.profile
        embed = discord.Embed(
            title=f"🌀 {p.get('alter_nom','Alter non défini')}",
            description=p.get("alter_description","Aucune description fournie."),
            color=discord.Color.orange()
        )

        embed.add_field(
            name="💥 Technique 1",
            value=f"{p.get('technique_1','Non définie')} — {'✅' if p.get('technique_1_unlock') else '❌'}",
            inline=False
        )
        embed.add_field(
            name="⚡ Technique 2",
            value=f"{p.get('technique_2','Non définie')} — {'✅' if p.get('technique_2_unlock') else '❌'}",
            inline=False
        )
        embed.add_field(
            name="🌋 Technique Ultime",
            value=f"{p.get('ultimate','Non définie')} — {'✅' if p.get('ultimate_unlock') else '❌'}",
            inline=False
        )

        # Thumbnail fixe
        embed.set_thumbnail(url="https://i.pinimg.com/736x/fe/dc/37/fedc370c66c4ca7114d03dd9a299bc4a.jpg")

        # Image personnalisée
        if p.get("alter_image"):
            embed.set_image(url=p["alter_image"])

        # Icone onglet
        if self.config.get("alter_icon_url"):
            embed.set_author(name="🌀 Alter", icon_url=self.config["alter_icon_url"])

        await interaction.response.edit_message(embed=embed, view=self)

# -------------------------------
# COMMANDES
# -------------------------------

# /creer_profil (Staff)
@tree.command(name="creer_profil", description="Créer le profil d'un membre (Staff uniquement)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Membre", nom="Nom", prenom="Prénom", surnom="Surnom", age="Âge", affiliation="Affiliation",
                       profil_image="Image Profil", stats_image="Image Stats", alter_nom="Nom Alter", alter_description="Description Alter", alter_image="Image Alter")
async def creer_profil(interaction: discord.Interaction, member: discord.Member, nom: str, prenom: str, surnom: str, age: str, affiliation: str,
                       profil_image: str = None, stats_image: str = None, alter_nom: str = None, alter_description: str = None, alter_image: str = None):
    if not is_staff(interaction.user):
        await interaction.response.send_message("Vous n'avez pas la permission.", ephemeral=True)
        return
    existing = await get_profile(member.id)
    if existing:
        await interaction.response.send_message("Ce membre a déjà un profil.", ephemeral=True)
        return
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            INSERT INTO profiles(user_id, nom, prenom, surnom, age, affiliation, profil_image, stats_image, alter_nom, alter_description, alter_image)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (member.id, nom, prenom, surnom, age, affiliation, profil_image, stats_image, alter_nom, alter_description, alter_image))
        await db.commit()
    await interaction.response.send_message(f"Profil créé pour {member.display_name} ✅", ephemeral=True)

# /profil
@tree.command(name="profil", description="Voir le profil d'un membre", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Membre cible")
async def profil(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    profile = await get_profile(member.id)
    if not profile:
        await interaction.response.send_message("Aucun profil trouvé.", ephemeral=True)
        return
    view = ProfileView(profile, config)
    await interaction.response.send_message("Profil chargé :", view=view)

# /modifier_profil
@tree.command(name="modifier_profil", description="Modifier son profil", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(nom="Nom", prenom="Prénom", surnom="Surnom", age="Âge", affiliation="Affiliation", profil_image="Image Profil", stats_image="Image Stats", alter_image="Image Alter", alter_description="Description Alter")
async def modifier_profil(interaction: discord.Interaction, nom: str = None, prenom: str = None, surnom: str = None, age: str = None,
                          affiliation: str = None, profil_image: str = None, stats_image: str = None, alter_image: str = None, alter_description: str = None):
    profile = await get_profile(interaction.user.id)
    if not profile:
        await interaction.response.send_message("Vous n'avez pas de profil.", ephemeral=True)
        return
    async with aiosqlite.connect(DATABASE) as db:
        if nom: await db.execute("UPDATE profiles SET nom=? WHERE user_id=?", (nom, interaction.user.id))
        if prenom: await db.execute("UPDATE profiles SET prenom=? WHERE user_id=?", (prenom, interaction.user.id))
        if surnom: await db.execute("UPDATE profiles SET surnom=? WHERE user_id=?", (surnom, interaction.user.id))
        if age: await db.execute("UPDATE profiles SET age=? WHERE user_id=?", (age, interaction.user.id))
        if affiliation: await db.execute("UPDATE profiles SET affiliation=? WHERE user_id=?", (affiliation, interaction.user.id))
        if profil_image: await db.execute("UPDATE profiles SET profil_image=? WHERE user_id=?", (profil_image, interaction.user.id))
        if stats_image: await db.execute("UPDATE profiles SET stats_image=? WHERE user_id=?", (stats_image, interaction.user.id))
        if alter_image: await db.execute("UPDATE profiles SET alter_image=? WHERE user_id=?", (alter_image, interaction.user.id))
        if alter_description: await db.execute("UPDATE profiles SET alter_description=? WHERE user_id=?", (alter_description, interaction.user.id))
        await db.commit()
    await interaction.response.send_message("Profil mis à jour ✅", ephemeral=True)

# /staff_add_prp
@tree.command(name="staff_add_prp", description="Ajouter PRP à un membre (Staff)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Membre", points="Points PRP à ajouter")
async def staff_add_prp(interaction: discord.Interaction, member: discord.Member, points: int):
    if not is_staff(interaction.user):
        await interaction.response.send_message("Vous n'avez pas la permission.", ephemeral=True)
        return
    profile = await get_profile(member.id)
    if not profile:
        await interaction.response.send_message("Le membre n'a pas de profil.", ephemeral=True)
        return
    old_prp = profile.get("prp",0)
    new_prp = old_prp + points
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("UPDATE profiles SET prp=? WHERE user_id=?", (new_prp, member.id))
        await db.commit()
    old_level = profile.get("niveau",1)
    new_level = prp_to_level(new_prp)
    if new_level > old_level:
        pts_awarded, unlocked = await award_level_up_rewards(member.id, old_level, new_level)
        msg = f"{points} PRP ajoutés. Niveau : {old_level} → {new_level}. +{pts_awarded} points à répartir."
        if unlocked:
            msg += " Déblocages : " + ", ".join(unlocked)
    else:
        msg = f"{points} PRP ajoutés à {member.display_name}."
    await interaction.response.send_message(msg)

# /attribuer_stats
@tree.command(name="attribuer_stats", description="Répartir vos points", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(force="Force", vitesse="Vitesse", endurance="Endurance", controle="Contrôle", puissance="Puissance", reactivite="Réactivité")
async def attribuer_stats(interaction: discord.Interaction, force: int = 0, vitesse: int = 0, endurance: int = 0, controle: int = 0, puissance: int = 0, reactivite: int = 0):
    profile = await get_profile(interaction.user.id)
    if not profile:
        await interaction.response.send_message("Vous n'avez pas de profil.", ephemeral=True)
        return
    total = sum(max(0,x) for x in (force,vitesse,endurance,controle,puissance,reactivite))
    available = profile.get("stat_points",0)
    if total > available:
        await interaction.response.send_message(f"Vous n'avez que {available} point(s).", ephemeral=True)
        return
    async with aiosqlite.connect(DATABASE) as db:
        await db.execute("""
            UPDATE profiles SET
                force=force+?,
                vitesse=vitesse+?,
                endurance=endurance+?,
                controle=controle+?,
                puissance=puissance+?,
                reactivite=reactivite+?,
                stat_points=stat_points-?
            WHERE user_id=?
        """,(force,vitesse,endurance,controle,puissance,reactivite,total,interaction.user.id))
        await db.commit()
    await interaction.response.send_message(f"{total} point(s) répartis ✅", ephemeral=True)

# /reset_profil
@tree.command(name="reset_profil", description="Supprimer le profil d'un membre (Staff)", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Membre cible")
async def reset_profil(interaction: discord.Interaction, member: discord.Member):
    if not is_staff(interaction.user):
        await interaction.response.send_message("Vous n'avez pas la permission.", ephemeral=True)
        return
    profile = await get_profile(member.id)
    if not profile:
        await interaction.response.send_message("Pas de profil à supprimer.", ephemeral=True)
        return
    await delete_profile(member.id)
    await interaction.response.send_message(f"Profil de {member.display_name} supprimé ✅", ephemeral=True)

# -------------------------------
# Lancer le bot
# -------------------------------
bot.run(TOKEN)















