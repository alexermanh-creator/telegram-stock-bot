import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Bot chứng khoán đã hoạt động!")


async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("Nhập mã cổ phiếu. Ví dụ: /price FPT")
        return

    symbol = context.args[0].upper()

    url = f"https://finance.vietstock.vn/data/stockdata/{symbol}"

    try:
        r = requests.get(url)
        data = r.json()

        price = data.get("LastPrice", "N/A")

        await update.message.reply_text(f"📈 {symbol}: {price}")

    except Exception:
        await update.message.reply_text("Không lấy được dữ liệu.")


app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("price", price))

print("Bot started...")
app.run_polling()
