
import os
import telebot
import matplotlib.pyplot as plt
from telebot.types import ReplyKeyboardMarkup
from openpyxl import load_workbook, Workbook
from datetime import datetime
from portfolio import *

TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

init_db()

state = {}

def main_menu():
    m = ReplyKeyboardMarkup(resize_keyboard=True)
    m.row("📊 Tài sản", "📜 Lịch sử")
    m.row("➕ Nạp thêm", "➖ Rút ra")
    m.row("💵 Giá trị hiện tại", "📈 Biểu đồ")
    m.row("📥 Import Excel", "📤 Xuất Excel")
    return m

@bot.message_handler(commands=['start'])
def start(msg):
    bot.send_message(msg.chat.id, "🤖 Bot Quản Lý Tài Sản PRO MAX", reply_markup=main_menu())

# ===== REPORT =====
@bot.message_handler(func=lambda m: m.text == "📊 Tài sản")
def report(msg):
    data, total_value, total_profit, total_percent = get_report(msg.from_user.id)
    text = "📊 TÀI SẢN\n\n"
    for cat, d in data.items():
        name = "Crypto" if cat == "crypto" else "Chứng khoán"
        text += f"{name}\nNạp: {d['deposit']:,.0f}\nRút: {d['withdraw']:,.0f}\nGiá trị: {d['value']:,.0f}\nLãi/Lỗ: {d['profit']:,.0f} ({d['percent']:.2f}%)\n\n"
    text += f"💰 Tổng tài sản: {total_value:,.0f}\n📈 Tổng lãi/lỗ: {total_profit:,.0f} ({total_percent:.2f}%)"
    bot.send_message(msg.chat.id, text, reply_markup=main_menu())

# ===== HISTORY =====
@bot.message_handler(func=lambda m: m.text == "📜 Lịch sử")
def history(msg):
    rows = get_history(msg.from_user.id)
    if not rows:
        bot.send_message(msg.chat.id, "Chưa có dữ liệu", reply_markup=main_menu())
        return
    text = "📜 Lịch sử\n\n"
    for tx in rows[-30:]:
        text += f"ID:{tx[0]} {tx[1]} {tx[2]} {tx[3]:,.0f} | {tx[4]}\n"
    bot.send_message(msg.chat.id, text, reply_markup=main_menu())

# ===== IMPORT EXCEL FULL HISTORY =====

def to_float(v):
    try:
        return float(v)
    except:
        return None

def to_date(v):
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d")
    return str(v)

@bot.message_handler(func=lambda m: m.text == "📥 Import Excel")
def import_excel(msg):
    bot.send_message(msg.chat.id, "Gửi file Excel để import toàn bộ lịch sử (sẽ xóa dữ liệu cũ).")

@bot.message_handler(content_types=['document'])
def handle_doc(msg):
    try:
        user_id = msg.from_user.id

        # clear old data (Mode A)
        clear_user(user_id)

        file_info = bot.get_file(msg.document.file_id)
        downloaded = bot.download_file(file_info.file_path)
        fname = "import.xlsx"
        with open(fname, "wb") as f:
            f.write(downloaded)

        wb = load_workbook(fname, data_only=True)
        ws = wb.active

        count = 0

        # Crypto table (B-E)
        for row in ws.iter_rows(min_row=6, min_col=2, max_col=5, values_only=True):
            date_in, amount_in, date_out, amount_out = row

            a = to_float(amount_in)
            if date_in and a:
                add_transaction(user_id, "crypto", "deposit", a, to_date(date_in))
                count += 1

            a = to_float(amount_out)
            if date_out and a:
                add_transaction(user_id, "crypto", "withdraw", a, to_date(date_out))
                count += 1

        # Stock table (H-K)
        for row in ws.iter_rows(min_row=6, min_col=8, max_col=11, values_only=True):
            date_in, amount_in, date_out, amount_out = row

            a = to_float(amount_in)
            if date_in and a:
                add_transaction(user_id, "stock", "deposit", a, to_date(date_in))
                count += 1

            a = to_float(amount_out)
            if date_out and a:
                add_transaction(user_id, "stock", "withdraw", a, to_date(date_out))
                count += 1

        os.remove(fname)

        bot.send_message(msg.chat.id, f"✅ Import thành công {count} giao dịch", reply_markup=main_menu())

    except Exception as e:
        bot.send_message(msg.chat.id, f"❌ Lỗi import: {e}", reply_markup=main_menu())

# ===== VALUE INPUT =====
@bot.message_handler(func=lambda m: m.text == "💵 Giá trị hiện tại")
def value_input(msg):
    bot.send_message(msg.chat.id, "Nhập: crypto 100000000 hoặc stock 200000000")

@bot.message_handler(func=lambda m: m.text and ("crypto" in m.text.lower() or "stock" in m.text.lower()))
def set_val(msg):
    try:
        parts = msg.text.split()
        cat = parts[0].lower()
        val = float(parts[1])
        set_value(msg.from_user.id, cat, val)
        bot.send_message(msg.chat.id, "✅ Đã cập nhật giá trị", reply_markup=main_menu())
    except:
        bot.send_message(msg.chat.id, "Sai cú pháp", reply_markup=main_menu())

# ===== EXPORT =====
@bot.message_handler(func=lambda m: m.text == "📤 Xuất Excel")
def export_excel(msg):
    rows = get_history(msg.from_user.id)
    if not rows:
        bot.send_message(msg.chat.id, "Không có dữ liệu", reply_markup=main_menu())
        return

    fname = "export.xlsx"
    wb = Workbook()
    ws = wb.active

    ws.append(["ID", "Category", "Type", "Amount", "Date"])

    for r in rows:
        ws.append(r)

    wb.save(fname)

    with open(fname, "rb") as f:
        bot.send_document(msg.chat.id, f)

    os.remove(fname)


bot.infinity_polling()
