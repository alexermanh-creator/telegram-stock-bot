
import os
from datetime import datetime
import telebot
from telebot.types import ReplyKeyboardMarkup
from portfolio import *

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

DB_FILE = "portfolio.db"

def fmt(num):
    if num >= 1000000000:
        return f"{num/1000000000:.2f}B"
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    return f"{num:,.0f}"

def menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📊 Tài sản","📜 Lịch sử")
    m.row("💰 Giá trị đầu tư","💵 Tiền mặt")
    m.row("➕ Nạp thêm","➖ Rút ra")
    m.row("📈 Biểu đồ","🥧 Phân bổ")
    m.row("📦 Backup","📥 Restore")
    m.row("🛠 Hướng dẫn")
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    r,total,profit,percent,dep,wd,invest,cash = get_report()
    text = "Chao ban\n\n"
    text += f"Tong tai san: {fmt(total)}\n"
    text += f"Lai/Lo: {fmt(profit)} ({percent:.1f}%)\n\n"
    text += "Ban chon chuc nang ben duoi"
    bot.send_message(msg.chat.id, text, reply_markup=menu())

@bot.message_handler(func=lambda m: m.text=="📊 Tài sản")
def dashboard(msg):
    r,total,profit,percent,dep,wd,invest,cash = get_report()
    text = f"TONG TAI SAN\n{fmt(total)}\n"
    text += f"Lai/Lo {fmt(profit)} ({percent:.1f}%)\n\n"
    text += f"Gia tri dau tu: {fmt(invest)}\n\n"
    text += f"Tong nap: {fmt(dep)}\n"
    text += f"Tong rut: {fmt(wd)}\n\n"
    text += f"Crypto: {fmt(r['crypto']['value'])}\n"
    text += f"Stock: {fmt(r['stock']['value'])}\n"
    text += f"Tien mat: {fmt(cash)}"
    bot.send_message(msg.chat.id, text, reply_markup=menu())

@bot.message_handler(func=lambda m: m.text=="💵 Tiền mặt")
def cash(msg):
    bot.send_message(msg.chat.id,"Nhap so tien mat:")

@bot.message_handler(func=lambda m: m.text and m.text.isdigit())
def setcash(msg):
    set_cash(float(msg.text))
    bot.send_message(msg.chat.id,"Da cap nhat tien mat", reply_markup=menu())

@bot.message_handler(func=lambda m: m.text=="📦 Backup")
def backup(msg):
    filename = f"portfolio_{datetime.now().strftime('%Y-%m-%d')}.db"
    with open(DB_FILE, "rb") as f:
        bot.send_document(msg.chat.id, f, visible_file_name=filename)

@bot.message_handler(content_types=['document'])
def restore_file(msg):
    file_info = bot.get_file(msg.document.file_id)
    downloaded = bot.download_file(file_info.file_path)
    with open(DB_FILE, "wb") as new_file:
        new_file.write(downloaded)
    bot.send_message(msg.chat.id, "Khoi phuc du lieu thanh cong.", reply_markup=menu())

bot.infinity_polling()
