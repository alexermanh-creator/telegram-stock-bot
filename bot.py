
import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from portfolio import *
from openpyxl import Workbook

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

init_db()


def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row(KeyboardButton("📊 Tài sản"), KeyboardButton("📥 Nạp tiền"))
    markup.row(KeyboardButton("📤 Rút tiền"), KeyboardButton("💰 Cập nhật giá trị"))
    markup.row(KeyboardButton("📜 Lịch sử Crypto"), KeyboardButton("📜 Lịch sử Stock"))
    markup.row(KeyboardButton("📤 Xuất Excel"))
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🤖 Bot quản lý tài sản VIP",
        reply_markup=main_menu()
    )


def show_report(message):
    data = get_report(message.from_user.id)
    text = "📊 TÀI SẢN CỦA BẠN\n\n"

    total_value = 0
    total_profit = 0

    for cat, d in data.items():
        name = "Crypto" if cat == "crypto" else "Chứng khoán"

        text += f"📁 {name}\n"
        text += f"Nạp: {d['deposit']:,.0f}\n"
        text += f"Rút: {d['withdraw']:,.0f}\n"
        text += f"Giá trị: {d['value']:,.0f}\n"
        text += f"Lãi/Lỗ: {d['profit']:,.0f}\n\n"

        total_value += d['value']
        total_profit += d['profit']

    text += f"💰 Tổng tài sản: {total_value:,.0f}\n"
    text += f"📊 Tổng lãi/lỗ: {total_profit:,.0f}"

    bot.send_message(message.chat.id, text, reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "📊 Tài sản")
def taisan_btn(message):
    show_report(message)


@bot.message_handler(func=lambda m: m.text == "📥 Nạp tiền")
def nap_menu(message):
    bot.send_message(message.chat.id, "Nhập: nap crypto 5000000 2024-03-01")


@bot.message_handler(func=lambda m: m.text == "📤 Rút tiền")
def rut_menu(message):
    bot.send_message(message.chat.id, "Nhập: rut crypto 2000000 2024-03-01")


@bot.message_handler(func=lambda m: m.text == "💰 Cập nhật giá trị")
def value_menu(message):
    bot.send_message(message.chat.id, "Nhập: value crypto 91000000")


@bot.message_handler(regexp=r'^nap ')
def nap(message):
    try:
        _, cat, amount, date = message.text.split()
        add_transaction(message.from_user.id, cat, "deposit", float(amount), date)
        bot.reply_to(message, "✅ Đã lưu", reply_markup=main_menu())
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


@bot.message_handler(regexp=r'^rut ')
def rut(message):
    try:
        _, cat, amount, date = message.text.split()
        add_transaction(message.from_user.id, cat, "withdraw", float(amount), date)
        bot.reply_to(message, "✅ Đã lưu", reply_markup=main_menu())
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


@bot.message_handler(regexp=r'^value ')
def value(message):
    try:
        _, cat, val = message.text.split()
        set_value(message.from_user.id, cat, float(val))
        bot.reply_to(message, "✅ Đã cập nhật", reply_markup=main_menu())
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


def show_history(message, category):
    rows = get_history(message.from_user.id, category)
    if not rows:
        bot.send_message(message.chat.id, "Chưa có dữ liệu")
        return

    text = f"📜 Lịch sử {category.upper()}\n\n"

    for tx_id, ttype, amount, date in rows[:20]:
        icon = "📥" if ttype == "deposit" else "📤"
        text += f"ID:{tx_id} {icon} {amount:,.0f} | {date}\n"

    bot.send_message(message.chat.id, text, reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "📜 Lịch sử Crypto")
def history_crypto(message):
    show_history(message, "crypto")


@bot.message_handler(func=lambda m: m.text == "📜 Lịch sử Stock")
def history_stock(message):
    show_history(message, "stock")


@bot.message_handler(func=lambda m: m.text == "📤 Xuất Excel")
def export_excel(message):
    rows = get_all_transactions(message.from_user.id)
    if not rows:
        bot.send_message(message.chat.id, "Không có dữ liệu")
        return

    file_name = f"portfolio_{message.from_user.id}.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Category", "Type", "Amount", "Date"])

    for row in rows:
        ws.append(row)

    wb.save(file_name)

    with open(file_name, "rb") as f:
        bot.send_document(message.chat.id, f)

    os.remove(file_name)


bot.infinity_polling()
