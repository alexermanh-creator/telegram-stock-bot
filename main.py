import os
import sqlite3
import logging
import datetime
import io
import re
import asyncio
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from ai_assistant import portfolio_ai
from exporter import reporter
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_FILE = 'portfolio.db'

try:
    from data import INITIAL_ASSETS, INITIAL_TRANSACTIONS
except ImportError:
    INITIAL_ASSETS, INITIAL_TRANSACTIONS = [], []

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets (category TEXT PRIMARY KEY, current_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        category TEXT, 
        type TEXT, 
        amount REAL, 
        date TEXT,
        note TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)''')
    
    try:
        c.execute("ALTER TABLE transactions ADD COLUMN note TEXT")
    except sqlite3.OperationalError:
        pass

    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('target_asset', 500000000)")
    
    c.execute("SELECT COUNT(*) FROM transactions")
    if c.fetchone()[0] == 0 and INITIAL_TRANSACTIONS:
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", INITIAL_ASSETS)
        processed_tx = [(*t, "") for t in INITIAL_TRANSACTIONS]
        c.executemany("INSERT INTO transactions (category, type, amount, date, note) VALUES (?, ?, ?, ?, ?)", processed_tx)
    conn.commit()
    conn.close()

def format_money(amount): return f"{int(amount):,}"
def parse_amount(text):
    match = re.search(r'^([\d\.]+)(tr|triệu|trieu|m|tỷ|ty|k|nghìn)?$', text.lower().strip().replace(',', '').replace(' ', ''))
    if match:
        v, u = float(match.group(1)), match.group(2)
        if u in ['tr', 'triệu', 'trieu', 'm']: return v * 1000000
        elif u in ['tỷ', 'ty']: return v * 1000000000
        elif u in ['k', 'nghìn']: return v * 1000
        else: return v
    return None

def get_stats():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    assets = {row[0]: row[1] for row in c.execute("SELECT category, current_value FROM assets").fetchall()}
    tx_data = c.execute("SELECT category, type, SUM(amount) FROM transactions GROUP BY category, type").fetchall()
    target_asset = (c.execute("SELECT value FROM settings WHERE key='target_asset'").fetchone() or [500000000])[0]
    conn.close()
    s = {'Crypto': {'Nạp': 0, 'Rút': 0}, 'Stock': {'Nạp': 0, 'Rút': 0}, 'Cash': {'Nạp': 0, 'Rút': 0}}
    for cat, t_type, amt in tx_data:
        if cat in s: s[cat][t_type] = amt
    res, tv, tn, trut = {}, 0, 0, 0
    for cat in ['Crypto', 'Stock', 'Cash']:
        hc = assets.get(cat, 0); nap = s[cat]['Nạp']; rut = s[cat]['Rút']
        von = nap - rut; lai = hc - von
        res[cat] = {'hien_co': hc, 'nap': nap, 'rut': rut, 'von': von, 'lai': lai, 'pct': (lai/von*100) if von!=0 else 0}
        tv += hc; tn += nap; trut += rut
    tvon = tn - trut; tlai = tv - tvon; tlai_pct = (tlai/tvon*100) if tvon!=0 else 0
    return {'total_val': tv, 'total_von': tvon, 'total_lai': tlai, 'total_lai_pct': tlai_pct, 'total_nap': tn, 'total_rut': trut, 'target_asset': target_asset, 'progress': (tv/target_asset*100) if target_asset>0 else 0, 'details': res}

def get_main_menu(): return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '🤖 Trợ lý AI'], ['⚙️ Hệ thống']], resize_keyboard=True)
def get_asset_menu(): return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_stats_menu(): return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['🏠 Menu Chính']], resize_keyboard=True)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip(); state = context.user_data.get('state')

    if text in ['/start', '🏠 Menu Chính']:
        context.user_data.clear(); await update.message.reply_text("🏠 DASHBOARD CHÍNH", reply_markup=get_main_menu()); return

    elif text in ['/xoa_tri_nho', '🧹 Xóa trí nhớ AI']:
        portfolio_ai.chat_history = []
        await update.message.reply_text("🧹 Đã xóa trí nhớ AI."); return

    if text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True))
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=ReplyKeyboardMarkup([['💾 Backup DB', '♻️ Restore DB'], ['📊 Xuất Excel', '🏠 Menu Chính']], resize_keyboard=True))

    elif text == '🤖 Trợ lý AI':
        context.user_data['state'] = 'chatting_ai'
        await update.message.reply_text("🤖 Gõ câu hỏi của bạn:", reply_markup=ReplyKeyboardMarkup([['🧹 Xóa trí nhớ AI', '🏠 Menu Chính']], resize_keyboard=True))
        return

    elif state == 'chatting_ai':
        s = get_stats()
        loading = await update.message.reply_text("⌛ AI đang phân tích...")
        reply = await portfolio_ai.get_advice(text, str(s))
        await loading.delete(); await update.message.reply_text(reply); return

    elif text == '💰 Xem Tổng Tài sản':
        s = get_stats(); d = s['details']
        msg = (f"🏆 *TỔNG TÀI SẢN*\n"
               f"{format_money(s['total_val'])} VNĐ\n"
               f"{'📈' if s['total_lai']>=0 else '📉'} {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"🎯 Mục tiêu: {s['progress']:.1f}% ({format_money(s['total_val'])} / {format_money(s['target_asset'])})\n"
               f"----------------------------------\n"
               f"📤 Tổng nạp: {format_money(s['total_nap'])}\n"
               f"📥 Tổng rút: {format_money(s['total_rut'])}\n"
               f"----------------------------------\n\n"
               f"🟡 *CRYPTO*\n"
               f"💰 Hiện có: {format_money(d['Crypto']['hien_co'])}\n"
               f"🏦 Vốn thực: {format_money(d['Crypto']['von'])}\n"
               f"📤 Nạp: {format_money(d['Crypto']['nap'])} | 📥 Rút: {format_money(d['Crypto']['rut'])}\n"
               f"📈 Lãi/Lỗ: {format_money(d['Crypto']['lai'])} ({d['Crypto']['pct']:.1f}%)\n\n"
               f"📈 *STOCK*\n"
               f"💰 Hiện có: {format_money(d['Stock']['hien_co'])}\n"
               f"🏦 Vốn thực: {format_money(d['Stock']['von'])}\n"
               f"📤 Nạp: {format_money(d['Stock']['nap'])} | 📥 Rút: {format_money(d['Stock']['rut'])}\n"
               f"📈 Lãi/Lỗ: {format_money(d['Stock']['lai'])} ({d['Stock']['pct']:.1f}%)\n\n"
               f"💵 *TIỀN MẶT*: {format_money(d['Cash']['hien_co'])}")
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif text == '📊 Xuất Excel':
        excel_file = reporter.export_excel_report()
        if excel_file: await update.message.reply_document(document=excel_file, filename="Bao_Cao.xlsx")
        else: await update.message.reply_text("❌ Lỗi xuất file.")

    elif state in ['awaiting_nap', 'awaiting_rut']:
        amt = parse_amount(text)
        if amt:
            context.user_data.update({'temp_amt': amt, 'prev_state': state, 'state': 'awaiting_note'})
            await update.message.reply_text("📝 Nhập ghi chú (Gõ '.' để bỏ qua):")
        return

    elif state == 'awaiting_note':
        amt, cat, p_state = context.user_data['temp_amt'], context.user_data['category'], context.user_data['prev_state']
        t_type = 'Nạp' if p_state == 'awaiting_nap' else 'Rút'
        note = "" if text == "." else text
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute("INSERT INTO transactions (category, type, amount, date, note) VALUES (?, ?, ?, ?, ?)", 
                  (cat, t_type, amt, datetime.datetime.now().strftime("%Y-%m-%d"), note))
        conn.commit(); conn.close(); context.user_data.clear()
        await update.message.reply_text(f"✅ Đã lưu {t_type} {format_money(amt)}.\n📝 Ghi chú: {note}", reply_markup=get_main_menu())
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); d = q.data
    if d.startswith("bal_"): context.user_data['state'] = f"awaiting_balance_{d.split('_')[1]}"; await q.edit_message_text(f"Nhập số dư {d.split('_')[1]}:")
    elif d.startswith("cat_"): context.user_data.update({'state': f"awaiting_{d.split('_')[1]}", 'category': d.split('_')[2]}); await q.edit_message_text(f"Nhập số tiền {d.split('_')[1]} cho {d.split('_')[2]}:")

def main():
    init_db(); token = os.environ.get("BOT_TOKEN")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "xoa_tri_nho"], handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback)); app.run_polling()

if __name__ == '__main__': main()
