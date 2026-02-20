
import os
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup
from portfolio import get_totals, set_value, add_tx

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def fmt(x):
    if x >= 1_000_000_000: return f"{x/1_000_000_000:.2f}B"
    if x >= 1_000_000: return f"{x/1_000_000:.1f}M"
    return f"{x:,.0f}"

def menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📊 Tài sản","📜 Lịch sử")
    m.row("💰 Tài sản hiện có","💵 Tiền mặt")
    m.row("➕ Nạp thêm","➖ Rút ra")
    m.row("📈 Biểu đồ","🥧 Phân bổ")
    m.row("📦 Backup","📥 Restore")
    m.row("🛠 Hướng dẫn")
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id,"👋 Bot quản lý tài sản sẵn sàng.", reply_markup=menu())

# ---------- Assets ----------
@bot.message_handler(func=lambda m: m.text=="📊 Tài sản")
def assets(msg):
    t, dep, wd = get_totals()
    crypto = t["crypto"]["value"]
    stock = t["stock"]["value"]
    total = crypto + stock

    text = f"""💰 TỔNG TÀI SẢN
{fmt(total)}

📥 Tổng nạp: {fmt(dep)}
📤 Tổng rút: {fmt(wd)}

🪙 Crypto: {fmt(crypto)}
📈 Stock: {fmt(stock)}"""
    bot.send_message(msg.chat.id,text,reply_markup=menu())

# ---------- Current Assets ----------
@bot.message_handler(func=lambda m: m.text=="💰 Tài sản hiện có")
def cur_assets(msg):
    bot.send_message(msg.chat.id,"Chọn danh mục:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row("🪙 Crypto","📈 Stock"))

@bot.message_handler(func=lambda m: m.text in ["🪙 Crypto","📈 Stock"])
def set_asset(msg):
    cat = "crypto" if "Crypto" in msg.text else "stock"
    bot.send_message(msg.chat.id,f"Nhập giá trị {cat}:")
    bot.register_next_step_handler(msg, lambda m: save_asset(m,cat))

def save_asset(msg,cat):
    try:
        val = float(msg.text)
        set_value(cat,val)
        bot.send_message(msg.chat.id,"✅ Đã cập nhật", reply_markup=menu())
    except:
        bot.send_message(msg.chat.id,"❌ Sai dữ liệu", reply_markup=menu())

# ---------- Deposit ----------
@bot.message_handler(func=lambda m: m.text=="➕ Nạp thêm")
def dep(msg):
    bot.send_message(msg.chat.id,"Chọn danh mục:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row("🪙 Crypto","📈 Stock"))
    bot.register_next_step_handler(msg, dep_cat)

def dep_cat(msg):
    cat = "crypto" if "Crypto" in msg.text else "stock"
    bot.send_message(msg.chat.id,"Nhập số tiền nạp:")
    bot.register_next_step_handler(msg, lambda m: save_dep(m,cat))

def save_dep(msg,cat):
    try:
        amt = float(msg.text)
        add_tx(cat,"deposit",amt,str(datetime.now().date()))
        bot.send_message(msg.chat.id,"✅ Đã thêm nạp", reply_markup=menu())
    except:
        bot.send_message(msg.chat.id,"❌ Sai dữ liệu", reply_markup=menu())

# ---------- Withdraw ----------
@bot.message_handler(func=lambda m: m.text=="➖ Rút ra")
def wd(msg):
    bot.send_message(msg.chat.id,"Chọn danh mục:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row("🪙 Crypto","📈 Stock"))
    bot.register_next_step_handler(msg, wd_cat)

def wd_cat(msg):
    cat = "crypto" if "Crypto" in msg.text else "stock"
    bot.send_message(msg.chat.id,"Nhập số tiền rút:")
    bot.register_next_step_handler(msg, lambda m: save_wd(m,cat))

def save_wd(msg,cat):
    try:
        amt = float(msg.text)
        add_tx(cat,"withdraw",amt,str(datetime.now().date()))
        bot.send_message(msg.chat.id,"✅ Đã thêm rút", reply_markup=menu())
    except:
        bot.send_message(msg.chat.id,"❌ Sai dữ liệu", reply_markup=menu())

# ---------- Help ----------
@bot.message_handler(func=lambda m: m.text=="🛠 Hướng dẫn")
def help(msg):
    bot.send_message(msg.chat.id,"Dùng menu để quản lý tài sản.", reply_markup=menu())

# ---------- Backup ----------
@bot.message_handler(func=lambda m: m.text=="📦 Backup")
def backup(msg):
    filename = f"portfolio_{datetime.now().strftime('%Y-%m-%d')}.db"
    with open("portfolio.db","rb") as f:
        bot.send_document(msg.chat.id,f,visible_file_name=filename)

# ---------- Restore ----------
@bot.message_handler(content_types=['document'])
def restore(msg):
    file_info = bot.get_file(msg.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    with open("portfolio.db","wb") as f:
        f.write(downloaded)
    bot.send_message(msg.chat.id,"✅ Restore xong", reply_markup=menu())

bot.infinity_polling()
