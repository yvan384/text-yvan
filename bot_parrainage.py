# bot_parrainage.py
import sqlite3
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# =========================
# Configuration directe
# =========================
BOT_TOKEN = "6555077062:AAGlIz7Lewj_5hikssB_a7UXj9xy2FOR1w4"
BOT_USERNAME = "n_y_w_bot"
CHANNEL_ID = "@nywtech3"
CHANNEL_INVITE_LINK = "https://t.me/nywtech3"
DB_PATH = "parrainage.db"


# =========================
# Base de données (SQLite)
# =========================
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TEXT,
            referrer_id INTEGER,
            UNIQUE(user_id)
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS referrals (
            referrer_id INTEGER NOT NULL,
            referred_id INTEGER NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# =========================
# Utilitaires
# =========================
def ensure_user_record(user_id: int, username: str, first_name: str):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row:
        cur.execute(
            "INSERT INTO users (user_id, username, first_name, joined_at) VALUES (?, ?, ?, ?)",
            (user_id, username, first_name, datetime.utcnow().isoformat())
        )
        conn.commit()
    conn.close()

def credit_referral_if_applicable(new_user_id: int, referrer_id: int):
    if new_user_id == referrer_id:
        return False, "Tu ne peux pas te parrainer toi-même."

    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT referrer_id FROM users WHERE user_id = ?", (new_user_id,))
    user_row = cur.fetchone()
    if user_row and user_row["referrer_id"] is not None:
        conn.close()
        return False, "Parrainage déjà attribué auparavant."

    cur.execute("SELECT referred_id FROM referrals WHERE referred_id = ?", (new_user_id,))
    existing_ref = cur.fetchone()
    if existing_ref:
        conn.close()
        return False, "Parrainage déjà enregistré."

    now = datetime.utcnow().isoformat()
    cur.execute(
        "INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?, ?, ?)",
        (referrer_id, new_user_id, now)
    )
    cur.execute(
        "UPDATE users SET referrer_id = ? WHERE user_id = ?",
        (referrer_id, new_user_id)
    )
    conn.commit()
    conn.close()
    return True, "Parrainage attribué avec succès."

def get_referral_count(user_id: int) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (user_id,))
    count = cur.fetchone()["c"]
    conn.close()
    return count

def get_referrals(user_id: int, limit: int = 50):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.username, u.first_name, r.created_at
        FROM referrals r
        LEFT JOIN users u ON u.user_id = r.referred_id
        WHERE r.referrer_id = ?
        ORDER BY r.created_at DESC
        LIMIT ?
    """, (user_id, limit))
    rows = cur.fetchall()
    conn.close()
    return rows

def get_leaderboard(limit: int = 10):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.username, u.first_name, COUNT(r.referred_id) AS score
        FROM users u
        LEFT JOIN referrals r ON r.referrer_id = u.user_id
        GROUP BY u.user_id, u.username, u.first_name
        ORDER BY score DESC, u.user_id ASC
        LIMIT ?
    """, (limit,))
    rows = cur.fetchall()
    conn.close()
    return rows


# =========================
# Handlers de commandes
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""

    ensure_user_record(user_id, username, first_name)

    msg_lines = [f"👋 Bienvenue, {first_name}!"]

    if context.args:
        try:
            referrer_id = int(context.args[0])
            ok, info = credit_referral_if_applicable(user_id, referrer_id)
            if ok:
                msg_lines.append("✅ Ton parrainage a été pris en compte.")
                # Annonce dans le canal
                await context.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=f"🎉 {first_name} (@{username}) a été parrainé par ID {referrer_id} !"
                )
            else:
                msg_lines.append(f"ℹ️ {info}")
        except ValueError:
            msg_lines.append("⚠️ L'argument de démarrage n'est pas valide.")
    else:
        msg_lines.append("Utilise ton lien de parrainage pour inviter des amis et gagner des points.")

    if CHANNEL_INVITE_LINK:
        msg_lines.append(f"\n🔗 Rejoins le canal: {CHANNEL_INVITE_LINK}")

    await update.message.reply_text("\n".join(msg_lines), parse_mode=ParseMode.HTML)

async def monlien(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    ensure_user_record(user_id, user.username or "", user.first_name or "")

    referral_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"
    count = get_referral_count(user_id)

    text = (
        f"🔗 Ton lien de parrainage:\n{referral_link}\n\n"
        f"👥 Filleuls: {count}\n"
        "Partage ce lien pour que tes amis démarrent le bot via toi."
    )
    await update.message.reply_text(text)

async def mesfilleuls(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    ensure_user_record(user_id, user.username or "", user.first_name or "")

    rows = get_referrals(user_id, limit=50)
    count = len(rows)
    if count == 0:
        await update.message.reply_text("Tu n'as pas encore de filleuls. Partage ton lien avec tes amis!")
        return

    lines = [f"👥 Tu as {count} filleul(s):"]
    for r in rows:
        handle = f"@{r['username']}" if r['username'] else f"{r['first_name'] or 'Utilisateur'}"
        lines.append(f"• {handle} (ID: {r['user_id']})")

    await update.message.reply_text("\n".join(lines))

async def classement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = get_leaderboard(limit=10)
    if not rows:
        await update.message.reply_text("Pas encore de participants au classement.")
        return

    lines = ["🏆 Top parrains:"]
    rank = 1
    for r in rows:
        handle = f"@{r['username']}" if r['username'] else f"{r['first_name'] or 'Utilisateur'}"
        lines.append(f"{rank}. {handle} — {r['score']} filleul(s)")
        rank += 1

    await update.message.reply_text("\n".join(lines))

async def invitation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if CHANNEL_INVITE_LINK:
        await update.message.reply_text(f"🔗 Lien d'invitation du canal:\n{CHANNEL_INVITE_LINK}")
    else:
        await update.message.reply_text("Aucun lien d'invitation n'est configuré.")

# =========================
# Entrée du programme
# =========================
def main():
    init_db()

    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN manquant.")

    # Crée l'application
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Ajoute les handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("monlien", monlien))
    app.add_handler(CommandHandler("mesfilleuls", mesfilleuls))
    app.add_handler(CommandHandler("classement", classement))
    app.add_handler(CommandHandler("invitation", invitation))

    print("Bot de parrainage démarré.")
    app.run_polling()
