
import os
from telebot import TeleBot, types
from database import init_db, seed_data
from portfolio import get_portfolio, set_value
from charts import create_allocation_chart

TOKEN = os.getenv("BOT_TOKEN") or "YOUR_TOKEN_HERE"
bot = TeleBot(TOKEN)

init_db()
seed_data()

def menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("📊 Tài sản","💰 Tài sản hiện có")
    kb.row("➕ Nạp thêm","➖ Rút ra")
    kb.row("📜 Lịch sử","📈 Biểu đồ")
    kb.row("🥧 Phân bổ","💾 Backup")
    kb.row("♻️ Restore","🛠 Hướng dẫn")
    return kb

def fmt(x):
    if x>=1_000_000:
        return f"{x/1_000_000:.1f}M"
    return str(x)

@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id,"👋 PROMAX ULTIMATE READY",reply_markup=menu())

@bot.message_handler(func=lambda m: "Tài sản" in m.text)
def assets(msg):
    data = get_portfolio()
    crypto = data["crypto"]
    stock = data["stock"]
    total = crypto["value"] + stock["value"]
    total_profit = crypto["profit"] + stock["profit"]
    text=f"""💰 TỔNG TÀI SẢN

{fmt(total)}
📈 {fmt(total_profit)}

🪙 Crypto: {fmt(crypto['value'])}
📈 {fmt(crypto['profit'])} ({crypto['percent']:.1f}%)

📈 Stock: {fmt(stock['value'])}
📈 {fmt(stock['profit'])} ({stock['percent']:.1f}%)
"""
    bot.send_message(msg.chat.id,text,reply_markup=menu())

@bot.message_handler(func=lambda m: "Tài sản hiện có" in m.text)
def set_asset(msg):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("Crypto","Stock")
    bot.send_message(msg.chat.id,"Chọn danh mục:",reply_markup=kb)

@bot.message_handler(func=lambda m: m.text in ["Crypto","Stock"])
def input_asset(msg):
    cat = "crypto" if m.text=="Crypto" else "stock"
    bot.send_message(msg.chat.id,"Nhập giá trị:")
    bot.register_next_step_handler(msg, lambda m: save_asset(m,cat))

def save_asset(msg,cat):
    try:
        val=float(msg.text)
        set_value(cat,val)
        bot.send_message(msg.chat.id,"✅ Đã cập nhật",reply_markup=menu())
    except:
        bot.send_message(msg.chat.id,"❌ Sai dữ liệu",reply_markup=menu())

@bot.message_handler(func=lambda m: "Phân bổ" in m.text)
def alloc(msg):
    path = create_allocation_chart()
    with open(path,"rb") as f:
        bot.send_photo(msg.chat.id,f,reply_markup=menu())

@bot.message_handler(func=lambda m: True)
def other(msg):
    bot.send_message(msg.chat.id,"Chức năng đang cập nhật...",reply_markup=menu())

bot.infinity_polling()
