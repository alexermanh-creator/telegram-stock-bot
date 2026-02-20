import os
import sqlite3
import aiosqlite
import asyncio
import logging
import datetime
import io
import re
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# IMPORT DỮ LIỆU TỪ FILE data.py
try:
    from data import INITIAL_ASSETS, INITIAL_TRANSACTIONS
except ImportError:
    INITIAL_ASSETS = []
    INITIAL_TRANSACTIONS = []

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_FILE = 'portfolio.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets (category TEXT PRIMARY KEY, current_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, type TEXT, amount REAL, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('target_asset', 500000000)")
    c.execute("SELECT COUNT(*) FROM transactions")
    if c.fetchone()[0] == 0 and INITIAL_TRANSACTIONS:
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", INITIAL_ASSETS)
        c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", INITIAL_TRANSACTIONS)
    conn.commit()
    conn.close()

def format_m(amount):
    return f"{amount / 1000000:.1f}M" if amount != 0 else "0"

def format_money(amount):
    return f"{int(amount):,}"

def parse_amount(text):
    text_lower = text.lower().strip().replace(',', '').replace(' ', '')
    match = re.search(r'^([\d\.]+)(tr|triệu|trieu|m|tỷ|ty|k|nghìn)?$', text_lower)
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        if unit in ['tr', 'triệu', 'trieu', 'm']: return val * 1000000
        elif unit in ['tỷ', 'ty']: return val * 1000000000
        elif unit in ['k', 'nghìn']: return val * 1000
        else: return val 
    return None

async def get_stats():
    async with aiosqlite.connect(DB_FILE) as conn:
        async with conn.execute("SELECT category, current_value FROM assets") as c:
            assets = {row[0]: row[1] for row in await c.fetchall()}
        async with conn.execute("SELECT category, type, SUM(amount) FROM transactions GROUP BY category, type") as c:
            txs = await c.fetchall()
        async with conn.execute("SELECT value FROM settings WHERE key='target_asset'") as c:
            target_row = await c.fetchone()
            
    target_asset = target_row[0] if target_row else 0
    stats = {'Crypto': {'Nạp': 0, 'Rút': 0}, 'Stock': {'Nạp': 0, 'Rút': 0}, 'Cash': {'Nạp': 0, 'Rút': 0}}
    for cat, t_type, amt in txs:
        if cat in stats: stats[cat][t_type] = amt

    res = {}
    total_val = 0
    total_nap = 0
    total_rut = 0

    for cat in ['Crypto', 'Stock', 'Cash']:
        hien_co = assets.get(cat, 0)
        nap = stats[cat]['Nạp']
        rut = stats[cat]['Rút']
        von = nap - rut
        lai = hien_co - von
        pct = (lai / von * 100) if von != 0 else 0
        
        res[cat] = {'hien_co': hien_co, 'nap': nap, 'rut': rut, 'von': von, 'lai': lai, 'pct': pct}
        total_val += hien_co
        total_nap += nap
        total_rut += rut

    total_von = total_nap - total_rut
    total_lai = total_val - total_von
    total_lai_pct = (total_lai / total_von * 100) if total_von != 0 else 0
    progress = (total_val / target_asset * 100) if target_asset > 0 else 0

    return {
        'total_val': total_val, 'total_von': total_von, 'total_lai': total_lai, 'total_lai_pct': total_lai_pct,
        'total_nap': total_nap, 'total_rut': total_rut, 'target_asset': target_asset, 'progress': progress, 'details': res
    }

def get_main_menu():
    return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '⚙️ Hệ thống']], resize_keyboard=True)

def get_asset_menu():
    return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)

def get_tx_menu():
    return ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True)

def get_stats_menu():
    return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['📊 Xuất báo cáo Excel'], ['🏠 Menu Chính']], resize_keyboard=True)

def get_sys_menu():
    return ReplyKeyboardMarkup([['💾 Backup DB', '♻️ Restore DB'], ['❓ Hướng dẫn', '🏠 Menu Chính']], resize_keyboard=True)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Chào mừng bạn!", reply_markup=get_main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == '🏠 Menu Chính': await update.message.reply_text("Menu Chính:", reply_markup=get_main_menu())
    elif text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=get_tx_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu())
    
    # Xử lý xem tài sản chi tiết 
    elif text == '💰 Xem Tổng Tài sản':
        s = await get_stats()
        d = s['details']
        msg = (f"🏆 TỔNG TÀI SẢN: {format_m(s['total_val'])}\n"
               f"{'📈' if s['total_lai']>=0 else '📉'} {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"🎯 Mục tiêu: {s['progress']:.1f}% ({format_m(s['total_val'])}/{format_m(s['target_asset'])})\n\n"
               f"🌕 CRYPTO: {format_m(d['Crypto']['hien_co'])} (Vốn: {format_m(d['Crypto']['von'])}) | {d['Crypto']['pct']:.1f}%\n"
               f"📈 STOCK: {format_m(d['Stock']['hien_co'])} (Vốn: {format_m(d['Stock']['von'])}) | {d['Stock']['pct']:.1f}%\n"
               f"💵 TIỀN MẶT: {format_m(d['Cash']['hien_co'])}")
        await update.message.reply_text(msg)
    
    # (Các phần xử lý nhập liệu giữ nguyên logic cũ nhưng sửa lỗi đóng ngoặc)
    state = context.user_data.get('state')
    if state and str(state).startswith('awaiting_balance_'):
        cat, amt = state.split("_")[2], parse_amount(text)
        if amt is not None:
            async with aiosqlite.connect(DB_FILE) as conn:
                await conn.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amt))
                await conn.commit()
            context.user_data.clear()
            await update.message.reply_text(f"✅ Đã cập nhật {cat}: {format_money(amt)}", reply_markup=get_asset_menu())
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); data = query.data
    if data.startswith("bal_"):
        context.user_data['state'] = f"awaiting_balance_{data.split('_')[1]}"
        await query.edit_message_text(f"Nhập số dư hiện tại cho {data.split('_')[1]}:")

def main():
    init_db()
    app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == '__main__': main()
