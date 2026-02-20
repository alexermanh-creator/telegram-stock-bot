import os
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

BOT_TOKEN = os.getenv("BOT_TOKEN")

def start(update: Update, context: CallbackContext):
    update.message.reply_text("✅ Bot đang hoạt động! Gửi /ping để kiểm tra.")

def ping(update: Update, context: CallbackContext):
    update.message.reply_text("🏓 Pong! Bot online OK.")

def main():
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN chưa được set trong Environment Variables")

    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("ping", ping))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()