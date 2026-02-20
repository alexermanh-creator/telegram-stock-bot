
import os
import telebot
import matplotlib.pyplot as plt
from telebot.types import ReplyKeyboardMarkup
from portfolio import *

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

init_db()


def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 Tài sản", "📜 Lịch sử")
    markup.row("➕ Nạp thêm", "➖ Rút ra")
    markup.row("✏️ Sửa giao dịch", "❌ Xóa giao dịch")
    markup.row("💰 Cập nhật giá trị", "📈 Biểu đồ")
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🤖 Bot Quản Lý Tài Sản PRO", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "📊 Tài sản")
def report(message):

    data, total_value, total_profit, total_percent = get_report(message.from_user.id)

    text = "📊 TÀI SẢN\n\n"

    for cat, d in data.items():
        name = "Crypto" if cat == "crypto" else "Chứng khoán"
        text += f"{name}\n"
        text += f"Nạp: {d['deposit']:,.0f}\n"
        text += f"Rút: {d['withdraw']:,.0f}\n"
        text += f"Giá trị: {d['value']:,.0f}\n"
        text += f"Lãi/Lỗ: {d['profit']:,.0f} ({d['percent']:.2f}%)\n\n"

    text += f"💰 Tổng tài sản: {total_value:,.0f}\n"
    text += f"📈 Tổng lãi/lỗ: {total_profit:,.0f} ({total_percent:.2f}%)"

    bot.send_message(message.chat.id, text, reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "📜 Lịch sử")
def history(message):

    rows = get_history(message.from_user.id)

    if not rows:
        bot.send_message(message.chat.id, "Chưa có dữ liệu")
        return

    text = "📜 Lịch sử\n\n"

    for tx_id, cat, ttype, amount, date in rows[-20:]:
        icon = "📥" if ttype == "deposit" else "📤"
        text += f"ID:{tx_id} {icon} {cat} {amount:,.0f} | {date}\n"

    bot.send_message(message.chat.id, text, reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "➕ Nạp thêm")
def nap_menu(message):
    bot.send_message(message.chat.id, "Nhập: nap crypto 5000000 2024-03-01")


@bot.message_handler(func=lambda m: m.text == "➖ Rút ra")
def rut_menu(message):
    bot.send_message(message.chat.id, "Nhập: rut crypto 2000000 2024-03-01")


@bot.message_handler(regexp=r'^nap ')
def nap(message):
    try:
        _, cat, amount, date = message.text.split()
        add_transaction(message.from_user.id, cat, "deposit", float(amount), date)
        bot.reply_to(message, "✅ Đã thêm")
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


@bot.message_handler(regexp=r'^rut ')
def rut(message):
    try:
        _, cat, amount, date = message.text.split()
        add_transaction(message.from_user.id, cat, "withdraw", float(amount), date)
        bot.reply_to(message, "✅ Đã thêm")
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


@bot.message_handler(func=lambda m: m.text == "✏️ Sửa giao dịch")
def edit_info(message):
    bot.send_message(message.chat.id, "Nhập: edit ID 5000000 2024-03-01")


@bot.message_handler(regexp=r'^edit ')
def edit_tx(message):
    try:
        _, tx_id, amount, date = message.text.split()
        update_transaction(message.from_user.id, int(tx_id), float(amount), date)
        bot.reply_to(message, "✅ Đã sửa")
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


@bot.message_handler(func=lambda m: m.text == "❌ Xóa giao dịch")
def del_info(message):
    bot.send_message(message.chat.id, "Nhập: del ID")


@bot.message_handler(regexp=r'^del ')
def delete_tx(message):
    try:
        _, tx_id = message.text.split()
        delete_transaction(message.from_user.id, int(tx_id))
        bot.reply_to(message, "✅ Đã xóa")
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


@bot.message_handler(regexp=r'^value ')
def value(message):
    try:
        _, cat, val = message.text.split()
        set_value(message.from_user.id, cat, float(val))
        bot.reply_to(message, "✅ Đã cập nhật")
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


@bot.message_handler(func=lambda m: m.text == "📈 Biểu đồ")
def chart(message):

    rows = get_history(message.from_user.id)

    if not rows:
        bot.send_message(message.chat.id, "Chưa có dữ liệu")
        return

    dates = []
    totals = []

    total = 0
    for _, _, ttype, amount, date in rows:
        if ttype == "deposit":
            total += amount
        else:
            total -= amount
        dates.append(date)
        totals.append(total)

    plt.figure()
    plt.plot(dates, totals)
    plt.xticks(rotation=45)
    plt.tight_layout()

    file_name = "chart.png"
    plt.savefig(file_name)
    plt.close()

    with open(file_name, "rb") as f:
        bot.send_photo(message.chat.id, f)

    os.remove(file_name)


bot.infinity_polling()
