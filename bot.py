
import os, sqlite3
from telebot import TeleBot, types

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(BASE_DIR, "portfolio.db")

TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TOKEN_HERE")
bot = TeleBot(TOKEN)

def conn():
    return sqlite3.connect(DB)

def fmt(x):
    if x >= 1_000_000_000:
        return f"{x/1_000_000_000:.2f}B"
    if x >= 1_000_000:
        return f"{x/1_000_000:.1f}M"
    return f"{x:,.0f}"

def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Tài sản","Lịch sử")
    kb.row("Tài sản hiện có","Tiền mặt")
    kb.row("Nạp thêm","Rút ra")
    kb.row("Biểu đồ","Phân bổ")
    kb.row("Backup","Restore")
    kb.row("Cài đặt","Hướng dẫn")
    return kb

def get_portfolio():
    c = conn()
    cur = c.cursor()
    data = {}
    total_dep = total_wd = 0
    for cat in ["crypto","stock"]:
        cur.execute("SELECT type, SUM(amount) FROM transactions WHERE category=? GROUP BY type",(cat,))
        dep = wd = 0
        for t,v in cur.fetchall():
            if t=="deposit": dep = v or 0
            if t=="withdraw": wd = v or 0
        cur.execute("SELECT value FROM values_now WHERE category=?",(cat,))
        row = cur.fetchone()
        val = row[0] if row else 0
        capital = dep - wd
        profit = val - capital
        percent = (profit/capital*100) if capital else 0
        total_dep += dep
        total_wd += wd
        data[cat] = dict(deposit=dep, withdraw=wd, value=val, capital=capital, profit=profit, percent=percent)
    cur.execute("SELECT amount FROM cash WHERE id=1")
    cash = cur.fetchone()[0]
    c.close()
    return data, total_dep, total_wd, cash

@bot.message_handler(commands=["start"])
def start(msg):
    data, _, _, _ = get_portfolio()
    total = data["crypto"]["value"] + data["stock"]["value"]
    profit = data["crypto"]["profit"] + data["stock"]["profit"]
    percent = (profit/(data["crypto"]["capital"]+data["stock"]["capital"])*100) if (data["crypto"]["capital"]+data["stock"]["capital"]) else 0
    text = f"Bot READY\nTotal: {fmt(total)}\nProfit: {fmt(profit)} ({percent:.1f}%)"
    bot.send_message(msg.chat.id, text, reply_markup=menu())

@bot.message_handler(func=lambda m: m.text and "Tài sản" in m.text and "hiện" not in m.text)
def assets(msg):
    data, dep, wd, cash = get_portfolio()
    crypto = data["crypto"]
    stock = data["stock"]
    total = crypto["value"] + stock["value"] + cash
    total_profit = crypto["profit"] + stock["profit"]
    total_percent = (total_profit/(crypto["capital"]+stock["capital"])*100) if (crypto["capital"]+stock["capital"]) else 0
    text=f"TOTAL: {fmt(total)}\nPROFIT: {fmt(total_profit)} ({total_percent:.1f}%)"
    bot.send_message(msg.chat.id, text, reply_markup=menu())

@bot.message_handler(func=lambda m: True)
def other(msg):
    bot.send_message(msg.chat.id,"OK", reply_markup=menu())

bot.infinity_polling()
