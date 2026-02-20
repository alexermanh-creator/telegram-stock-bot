import os
import requests
from bs4 import BeautifulSoup
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")


def get_stock_price(symbol: str):
    try:
        url = f"https://finance.vietstock.vn/{symbol}/thong-ke-giao-dich.htm"
        headers = {"User-Agent": "Mozilla/5.0"}

        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, "lxml")

        price_tag = soup.select_one(".price")
        if price_tag:
            return price_tag.text.strip()
        else:
            return "Không lấy được giá."

    except Exception as e:
        return f"Lỗi: {e}"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📈 Bot chứng khoán đã hoạt động!\n\n"
        "Gõ:\n"
        "/stock VNM"
    )


async def stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Ví dụ: /stock VNM")
        return

    symbol = context.args[0].upper()
    price = get_stock_price(symbol)

    await update.message.reply_text(
        f"📊 Mã: {symbol}\n💰 Giá: {price}"
    )


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stock", stock))

    print("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
