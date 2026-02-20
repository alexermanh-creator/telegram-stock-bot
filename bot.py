import json
import os
import requests
import matplotlib.pyplot as plt

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = "8411805699:AAEmN8Thtuezey_amr83UZNnUILvHoYb9ME"

DATA_FILE = "data.json"


# ================= DATA =================

def load():
    if not os.path.exists(DATA_FILE):

        data = {
            "cash": 0,
            "portfolio": {
                "PDR": {"qty": 60, "avg": 21490},
                "VPB": {"qty": 4000, "avg": 30510}
            },
            "nav_history": []
        }

        save(data)
        return data

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ================= REALTIME PRICE =================

from bs4 import BeautifulSoup


import requests

def get_price(symbol, fallback=0):
    """
    Lấy giá realtime cổ phiếu Việt Nam
    Nguồn: TCBS API (ổn định, không bị chặn)
    """

    try:
        symbol = symbol.upper().strip()

        url = f"https://price.tpbs.com.vn/api/StockBoardApi/getStockQuote?stock={symbol}"

        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        r = requests.get(url, headers=headers, timeout=5)

        if r.status_code != 200:
            return fallback

        data = r.json()

        # Giá khớp lệnh
        price = data.get("matchPrice")

        if price is None:
            return fallback

        price = float(price) * 1000   # TCBS trả về đơn vị nghìn

        if price <= 0:
            return fallback

        return price

    except Exception as e:
        print("PRICE ERROR:", e)
        return fallback



# ================= MENU =================

def menu():

    kb = [
        ["📊 Danh mục", "💰 Tiền"],
        ["➕ Mua", "➖ Bán"],
        ["🤖 AI cổ phiếu", "🌍 AI thị trường"],
        ["🚨 Cảnh báo lỗ", "📈 NAV"],
        ["📊 Phân bổ", "❓ Hướng dẫn"]
    ]

    return ReplyKeyboardMarkup(kb, resize_keyboard=True)


# ================= START =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text(
        "📈 BOT QUẢN LÝ TÀI SẢN PRO",
        reply_markup=menu()
    )


# ================= GUIDE =================

async def guide(update: Update, context: ContextTypes.DEFAULT_TYPE):

    text = """
📘 HƯỚNG DẪN BOT ĐẦY ĐỦ

📊 Danh mục → xem cổ phiếu
💰 Tiền → xem tiền mặt

➕ Mua
Nhập:
MUA MÃ GIÁ SL
VD:
MUA FPT 90000 100

➖ Bán
Nhập:
BÁN MÃ GIÁ SL
VD:
BÁN FPT 95000 50

🤖 AI cổ phiếu
Phân tích từng mã

🌍 AI thị trường
Đánh giá xu hướng VNINDEX

🚨 Cảnh báo lỗ
Báo khi lỗ >10%

📈 NAV
Biểu đồ tài sản

📊 Phân bổ
Tỷ trọng danh mục
"""

    await update.message.reply_text(text)


# ================= PORTFOLIO =================

async def portfolio(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = load()

    msg = "💼 DANH MỤC\n\n"

    total_value = 0
    total_cost = 0

    for sym, p in data["portfolio"].items():

        price = get_price(sym, p["avg"])

        value = price * p["qty"]
        cost = p["avg"] * p["qty"]

        pnl = value - cost
        pct = pnl / cost * 100 if cost else 0

        total_value += value
        total_cost += cost

        msg += f"""
{sym}
SL: {p['qty']}
Giá vốn: {p['avg']:,.0f}
Giá hiện tại: {price:,.0f}
Lãi: {pnl:,.0f} ({pct:.2f}%)

"""

    nav = total_value + data["cash"]

    msg += f"""
--------------
Tổng vốn: {total_cost:,.0f}
Tài sản: {nav:,.0f}
"""

    data["nav_history"].append(nav)
    save(data)

    await update.message.reply_text(msg)


# ================= BUY =================

async def buy(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("Nhập: MUA MÃ GIÁ SL")


# ================= SELL =================

async def sell(update: Update, context: ContextTypes.DEFAULT_TYPE):

    await update.message.reply_text("Nhập: BÁN MÃ GIÁ SL")


# ================= AI STOCK =================

async def ai_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = load()

    msg = "🤖 AI CỔ PHIẾU\n\n"

    for sym, p in data["portfolio"].items():

        price = get_price(sym, p["avg"])

        diff = (price - p["avg"]) / p["avg"] * 100

        if diff > 10:
            status = "🔥 Mạnh"
        elif diff > 0:
            status = "📈 Tích cực"
        elif diff > -10:
            status = "⚖️ Sideway"
        else:
            status = "⚠️ Yếu"

        msg += f"{sym}: {status} ({diff:.2f}%)\n"

    await update.message.reply_text(msg)


# ================= AI MARKET =================

async def ai_market(update: Update, context: ContextTypes.DEFAULT_TYPE):

    price = get_price("VNINDEX", 0)

    if price == 0:
        text = "Không lấy được dữ liệu VNINDEX"
    else:

        if price > 1200:
            trend = "📈 Uptrend"
        else:
            trend = "⚠️ Sideway"

        text = f"""
🌍 AI THỊ TRƯỜNG

VNINDEX: {price:,.0f}
Xu hướng: {trend}
"""

    await update.message.reply_text(text)


# ================= LOSS ALERT =================

async def alert(update: Update, context: ContextTypes.DEFAULT_TYPE):

    data = load()

    msg = "🚨 CẢNH BÁO\n\n"

    for sym, p in data["portfolio"].items():

        price = get_price(sym, p["avg"])
        pct = (price - p["avg"]) / p["avg"] * 100

        if pct <= -10:
            msg += f"{sym} lỗ {pct:.2f}%\n"

    if msg == "🚨 CẢNH BÁO\n\n":
        msg = "Không có cổ phiếu lỗ sâu"

    await update.message.reply_text(msg)


# ================= HANDLE =================

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):

    t = update.message.text.upper()

    if t == "📊 DANH MỤC":
        await portfolio(update, context)

    elif t == "➕ MUA":
        await buy(update, context)

    elif t == "➖ BÁN":
        await sell(update, context)

    elif t == "🤖 AI CỔ PHIẾU":
        await ai_stock(update, context)

    elif t == "🌍 AI THỊ TRƯỜNG":
        await ai_market(update, context)

    elif t == "🚨 CẢNH BÁO LỖ":
        await alert(update, context)

    elif t == "❓ HƯỚNG DẪN":
        await guide(update, context)


# ================= MAIN =================

def main():

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

    print("BOT RUNNING...")
    app.run_polling()


if __name__ == "__main__":
    main()
