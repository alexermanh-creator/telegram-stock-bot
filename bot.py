
import os
import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from openpyxl import load_workbook, Workbook
from portfolio import *

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

init_db()


def main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📊 Tài sản", "📥 Import Excel")
    markup.row("💰 Cập nhật giá trị", "📤 Xuất Excel")
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🤖 Bot Quản Lý Tài Sản FULL", reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "📊 Tài sản")
def report(message):
    data = get_report(message.from_user.id)

    text = "📊 TÀI SẢN\n\n"

    total_value = 0
    total_profit = 0

    for cat, d in data.items():
        name = "Crypto" if cat == "crypto" else "Chứng khoán"

        text += f"{name}\n"
        text += f"Nạp: {d['deposit']:,.0f}\n"
        text += f"Rút: {d['withdraw']:,.0f}\n"
        text += f"Giá trị: {d['value']:,.0f}\n"
        text += f"Lãi/Lỗ: {d['profit']:,.0f}\n\n"

        total_value += d['value']
        total_profit += d['profit']

    text += f"Tổng tài sản: {total_value:,.0f}\n"
    text += f"Tổng lãi/lỗ: {total_profit:,.0f}"

    bot.send_message(message.chat.id, text, reply_markup=main_menu())


@bot.message_handler(func=lambda m: m.text == "💰 Cập nhật giá trị")
def value_info(message):
    bot.send_message(message.chat.id, "Nhập: value crypto 91000000")


@bot.message_handler(regexp=r'^value ')
def set_val(message):
    try:
        _, cat, val = message.text.split()
        set_value(message.from_user.id, cat, float(val))
        bot.reply_to(message, "✅ Đã cập nhật", reply_markup=main_menu())
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


@bot.message_handler(func=lambda m: m.text == "📥 Import Excel")
def import_excel(message):
    bot.send_message(message.chat.id, "Gửi file Excel FINAL INVERSTOR.xlsx")


@bot.message_handler(content_types=['document'])
def handle_doc(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded = bot.download_file(file_info.file_path)

        file_name = "import.xlsx"
        with open(file_name, "wb") as f:
            f.write(downloaded)

        wb = load_workbook(file_name, data_only=True)
        ws = wb["FINAL"]

        count = 0

        for row in ws.iter_rows(min_row=6, values_only=True):

            # Crypto
            if row[7] and row[8]:
                add_transaction(message.from_user.id, "crypto", "deposit", float(row[8]), str(row[7]))
                count += 1

            if row[9] and row[10]:
                add_transaction(message.from_user.id, "crypto", "withdraw", float(row[10]), str(row[9]))
                count += 1

            # Stock
            if row[14] and row[15]:
                add_transaction(message.from_user.id, "stock", "deposit", float(row[15]), str(row[14]))
                count += 1

            if row[16] and row[17]:
                add_transaction(message.from_user.id, "stock", "withdraw", float(row[17]), str(row[16]))
                count += 1

        os.remove(file_name)

        bot.send_message(message.chat.id, f"✅ Import thành công {count} giao dịch", reply_markup=main_menu())

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Lỗi: {e}")


@bot.message_handler(func=lambda m: m.text == "📤 Xuất Excel")
def export_excel(message):
    data = get_report(message.from_user.id)

    file_name = "report.xlsx"
    wb = Workbook()
    ws = wb.active

    ws.append(["Category", "Deposit", "Withdraw", "Value", "Profit"])

    for cat, d in data.items():
        ws.append([cat, d["deposit"], d["withdraw"], d["value"], d["profit"]])

    wb.save(file_name)

    with open(file_name, "rb") as f:
        bot.send_document(message.chat.id, f)

    os.remove(file_name)


bot.infinity_polling()
