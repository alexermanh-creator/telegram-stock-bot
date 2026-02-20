
import os
import telebot
import matplotlib.pyplot as plt
from telebot.types import ReplyKeyboardMarkup
from portfolio import *

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

def menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📊 Tài sản", "💰 Giá trị")
    m.row("📈 Biểu đồ tăng trưởng", "🥧 Phân bổ tài sản")
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, "🚀 BOT VIP QUẢN LÝ TÀI SẢN", reply_markup=menu())

@bot.message_handler(func=lambda m: m.text == "📊 Tài sản")
def report(msg):
    data, total_value, total_profit, total_percent = get_report()

    text = "📊 TÀI SẢN\n\n"

    for cat, d in data.items():
        name = "Crypto" if cat == "crypto" else "Stock"
        text += f"{name}\n"
        text += f"Nạp: {d['deposit']:,.0f}\n"
        text += f"Rút: {d['withdraw']:,.0f}\n"
        text += f"Giá trị: {d['value']:,.0f}\n"
        text += f"Lãi/Lỗ: {d['profit']:,.0f} ({d['percent']:.2f}%)\n\n"

    text += f"💰 Tổng: {total_value:,.0f}"
    bot.send_message(msg.chat.id, text, reply_markup=menu())

@bot.message_handler(func=lambda m: m.text == "💰 Giá trị")
def set_val(msg):
    bot.send_message(msg.chat.id, "Nhập: crypto 100000000")

@bot.message_handler(func=lambda m: m.text and ("crypto" in m.text.lower() or "stock" in m.text.lower()))
def save_val(msg):
    try:
        cat, val = msg.text.split()
        set_value(cat.lower(), float(val))
        bot.send_message(msg.chat.id, "✅ Đã cập nhật", reply_markup=menu())
    except:
        bot.send_message(msg.chat.id, "❌ Sai cú pháp")

@bot.message_handler(func=lambda m: m.text == "📈 Biểu đồ tăng trưởng")
def growth(msg):
    data, total_value, _, _ = get_report()
    values = [d["value"] for d in data.values()]
    labels = ["Crypto", "Stock"]

    plt.figure()
    plt.plot(labels, values, marker="o")
    plt.title("Tăng trưởng tài sản")
    plt.savefig("growth.png")
    plt.close()

    bot.send_photo(msg.chat.id, open("growth.png", "rb"), reply_markup=menu())

@bot.message_handler(func=lambda m: m.text == "🥧 Phân bổ tài sản")
def pie(msg):
    data, _, _, _ = get_report()
    values = [d["value"] for d in data.values()]
    labels = ["Crypto", "Stock"]

    plt.figure()
    plt.pie(values, labels=labels, autopct="%1.1f%%")
    plt.title("Phân bổ tài sản")
    plt.savefig("pie.png")
    plt.close()

    bot.send_photo(msg.chat.id, open("pie.png", "rb"), reply_markup=menu())

bot.infinity_polling()
