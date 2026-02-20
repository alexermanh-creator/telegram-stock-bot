
import os
import telebot
import matplotlib.pyplot as plt
from telebot.types import ReplyKeyboardMarkup
from openpyxl import Workbook, load_workbook
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
    markup.row("📥 Import Excel", "📤 Xuất Excel")
    return markup


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "🤖 Bot Quản Lý Tài Sản PRO MAX", reply_markup=main_menu())


# ===== REPORT =====
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


# ===== HISTORY =====
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


# ===== ADD / WITHDRAW =====
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


# ===== EDIT / DELETE =====
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


# ===== VALUE =====
@bot.message_handler(regexp=r'^value ')
def value(message):
    try:
        _, cat, val = message.text.split()
        set_value(message.from_user.id, cat, float(val))
        bot.reply_to(message, "✅ Đã cập nhật")
    except:
        bot.reply_to(message, "❌ Sai cú pháp")


# ===== CHART =====
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
        dates.append(str(date))
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


# ===== IMPORT 3 TABLES FROM YOUR EXCEL =====
@bot.message_handler(func=lambda m: m.text == "📥 Import Excel")
def import_excel_info(message):
    bot.send_message(message.chat.id, "Gửi file Excel của bạn (sẽ import Crypto + Stock)")


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

        # ===== CRYPTO TABLE (cols A-D approx) =====
        for row in ws.iter_rows(min_row=6, max_col=4, values_only=True):
            date_in, amount_in, date_out, amount_out = row

            if date_in and amount_in:
                add_transaction(message.from_user.id, "crypto", "deposit", float(amount_in), str(date_in))
                count += 1

            if date_out and amount_out:
                add_transaction(message.from_user.id, "crypto", "withdraw", float(amount_out), str(date_out))
                count += 1

        # ===== STOCK TABLE (cols G-J approx) =====
        for row in ws.iter_rows(min_row=6, min_col=7, max_col=10, values_only=True):
            date_in, amount_in, date_out, amount_out = row

            if date_in and amount_in:
                add_transaction(message.from_user.id, "stock", "deposit", float(amount_in), str(date_in))
                count += 1

            if date_out and amount_out:
                add_transaction(message.from_user.id, "stock", "withdraw", float(amount_out), str(date_out))
                count += 1

        os.remove(fname)

        bot.send_message(message.chat.id, f"✅ Import thành công {count} giao dịch", reply_markup=main_menu())

    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Lỗi import: {e}")


# ===== EXPORT =====
@bot.message_handler(func=lambda m: m.text == "📤 Xuất Excel")
def export_excel(message):

    rows = get_history(message.from_user.id)

    if not rows:
        bot.send_message(message.chat.id, "Không có dữ liệu")
        return

    file_name = "export.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.append(["ID", "Category", "Type", "Amount", "Date"])

    for r in rows:
        ws.append(r)

    wb.save(file_name)

    with open(file_name, "rb") as f:
        bot.send_document(message.chat.id, f)

    os.remove(file_name)


bot.infinity_polling()
