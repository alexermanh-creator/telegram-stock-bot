
import os
import telebot
from telebot.types import ReplyKeyboardMarkup
from openpyxl import load_workbook
from datetime import datetime
from portfolio import *

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

init_db()


def to_date_str(val):
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return str(val)


def to_float(val):
    try:
        return float(val)
    except:
        return None


def menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📥 Import Excel")
    return m


@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, "🤖 Import Excel FIX datetime", reply_markup=menu())


@bot.message_handler(func=lambda m: m.text == "📥 Import Excel")
def ask_file(msg):
    bot.send_message(msg.chat.id, "Gửi file Excel")


@bot.message_handler(content_types=['document'])
def handle_doc(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)

        fname = "import.xlsx"
        with open(fname, "wb") as f:
            f.write(downloaded)

        wb = load_workbook(fname, data_only=True)
        ws = wb.active

        count = 0

        # ===== CRYPTO TABLE =====
        for row in ws.iter_rows(min_row=6, max_col=4, values_only=True):
            date_in, amount_in, date_out, amount_out = row

            amt = to_float(amount_in)
            if date_in and amt:
                add_transaction(message.from_user.id, "crypto", "deposit", amt, to_date_str(date_in))
                count += 1

            amt = to_float(amount_out)
            if date_out and amt:
                add_transaction(message.from_user.id, "crypto", "withdraw", amt, to_date_str(date_out))
                count += 1

        # ===== STOCK TABLE =====
        for row in ws.iter_rows(min_row=6, min_col=7, max_col=10, values_only=True):
            date_in, amount_in, date_out, amount_out = row

            amt = to_float(amount_in)
            if date_in and amt:
                add_transaction(message.from_user.id, "stock", "deposit", amt, to_date_str(date_in))
                count += 1

            amt = to_float(amount_out)
            if date_out and amt:
                add_transaction(message.from_user.id, "stock", "withdraw", amt, to_date_str(date_out))
                count += 1

        os.remove(fname)

        bot.send_message(message.chat.id, f"✅ Import thành công {count} giao dịch")

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Lỗi import: {e}")


bot.infinity_polling()
