import os
import logging
import sqlite3
from datetime import datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# =========================
# Configuration (Environ + Valeurs par défaut)
# =========================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "6555077062:AAGlIz7Lewj_5hikssB_a7UXj9xy2FOR1w4").strip()
BOT_USERNAME = os.environ.get("BOT_USERNAME", "n_y_w_bot").strip()
CHANNEL_ID = os.environ.get("CHANNEL_ID", "@nywtech3").strip()
CHANNEL_INVITE_LINK = os.environ.get("CHANNEL_INVITE_LINK", "https://t.me/nywtech3").strip()
DB_PATH = os.environ.get("DB_PATH", "parrainage.db").strip()

# =========================
# Logging
# =========================
logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("parrainage-bot")


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
    logger.info("Base SQLite initialisée: %s", DB_PATH)


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
        logger.info("Nouvel utilisateur enregistré: id=%s, username=%s", user_id, username)
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
    logger.info("Parrainage enregistré: referrer=%s -> referred=%s", referrer_id, new_user_id)
    return True, "Parrainage attribué avec succès."

def get_referral_count(user_id: int) -> int:
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM referrals WHERE referrer_id = ?", (user_id,))
    count = int(cur.fetchone()["c"])
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
    if not user or not update.message:
        return

    user_id = user.id
    username = user.username or ""
    first_name = user.first_name or ""

    ensure_user_record(user_id, username, first_name)

    msg_lines = [f"👋 Bienvenue chez nywtech, {first_name}!"]

    args = context.args if hasattr(context, "args") else []
    if args:
        try:
            referrer_id = int(args[0])
            ok, info = credit_referral_if_applicable(user_id, referrer_id)
            if ok:
                msg_lines.append("✅ Ton parrainage a été pris en compte.")
                if CHANNEL_ID:
                    try:
                        await context.bot.send_message(
                            chat_id=CHANNEL_ID,
                            text=f"🎉 {first_name} (@{username}) a été parrainé par ID {referrer_id} !"
                        )
                    except Exception as e:
                        logger.warning("Annonce canal échouée: %s", e)
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
    if not user or not update.message:
        return
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
    if not user or not update.message:
        return
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
    if not update.message:
        return
    rows = get_leaderboard(limit=10)
    if not rows:
        await update.message.reply_text("Pas encore de participants au classement.")
        return

    lines = ["🏆 Top parrains:"]
    for idx, r in enumerate(rows, start=1):
        handle = f"@{r['username']}" if r['username'] else f"{r['first_name'] or 'Utilisateur'}"
        lines.append(f"{idx}. {handle} — {r['score']} filleul(s)")

    await update.message.reply_text("\n".join(lines))

async def invitation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if CHANNEL_INVITE_LINK:
        await update.message.reply_text(f"🔗 Lien d'invitation du canal:\n{CHANNEL_INVITE_LINK}")
    else:
        await update.message.reply_text("Aucun lien d'invitation n'est configuré.")

async def aide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    text = (
        "Commandes disponibles:\n"
        "/start - Démarrer et enregistrer le parrainage si lien\n"
        "/monlien - Obtenir ton lien de parrainage\n"
        "/mesfilleuls - Voir tes filleuls\n"
        "/classement - Top parrains\n"
        "/invitation - Lien du canal\n"
        "/aide ou /help - Aide\n"
    )
    await update.message.reply_text(text)


# =========================
# Entrée du programme
# =========================
def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN manquant (configure la variable d'environnement BOT_TOKEN).")

    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("monlien", monlien))
    app.add_handler(CommandHandler("mesfilleuls", mesfilleuls))
    app.add_handler(CommandHandler("classement", classement))
    app.add_handler(CommandHandler("invitation", invitation))
    app.add_handler(CommandHandler("help", aide))
    app.add_handler(CommandHandler("aide", aide))

    logger.info("Bot de parrainage démarré. Username=%s", BOT_USERNAME)
    app.run_polling(allowed_updates=None)


if __name__ == "__main__":
    main()
