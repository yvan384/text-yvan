Python 3.14.1 (tags/v3.14.1:57e0d17, Dec  2 2025, 14:05:07) [MSC v.1944 64 bit (AMD64)] on win32
Enter "help" below or click "Help" above for more information.
>>> from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
... from telegram import Update
... 
... BOT_TOKEN = "6555077062:AAGlIz7Lewj_5hikssB_a7UXj9xy2FOR1w4"
... 
... async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
...     await update.message.reply_text("Bot OK ✅")
... 
... def main():
...     app = ApplicationBuilder().token(BOT_TOKEN).build()
...     app.add_handler(CommandHandler("start", start))
...     print("Bot de test démarré.")
...     app.run_polling()
... 
... if __name__ == "__main__":
