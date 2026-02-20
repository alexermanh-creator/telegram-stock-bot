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
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

# IMPORT DỮ LIỆU TỪ FILE data.py
try:
    from data import INITIAL_ASSETS, INITIAL_TRANSACTIONS
except ImportError:
    INITIAL_ASSETS = []
    INITIAL_TRANSACTIONS = []

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

DB_FILE = 'portfolio.db'

# --- 1. KHỞI TẠO DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (category TEXT PRIMARY KEY, current_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, type TEXT, amount REAL, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('target_asset', 500000000)")
    
    # Kiểm tra xem có cần bơm dữ liệu từ file data.py không
    c.execute("SELECT COUNT(*) FROM transactions")
    if c.fetchone()[0] == 0 and INITIAL_TRANSACTIONS:
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", INITIAL_ASSETS)
        c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", INITIAL_TRANSACTIONS)
        
    conn.commit()
    conn.close()

# --- 2. HÀM HỖ TRỢ HIỂN THỊ ---
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
        if cat not in stats: stats[cat] = {'Nạp': 0, 'Rút': 0}
        stats[cat][t_type] = amt

    c_hien_co = assets.get('Crypto', 0)
    s_hien_co = assets.get('Stock', 0)
    cash_hien_co = assets.get('Cash', 0)
    
    c_nap, c_rut = stats['Crypto']['Nạp'], stats['Crypto']['Rút']
    s_nap, s_rut = stats['Stock']['Nạp'], stats['Stock']['Rút']
    cash_nap, cash_rut = stats['Cash']['Nạp'], stats['Cash']['Rút']
    
    c_von = c_nap - c_rut
    s_von = s_nap - s_rut
    cash_von = cash_nap - cash_rut
    
    c_lai = c_hien_co - c_von
    s_lai = s_hien_co - s_von
    
    c_lai_pct = (c_lai / c_von * 100) if c_von > 0 else 0
    s_lai_pct = (s_lai / s_von * 100) if s_von > 0 else 0
    
    tong_tai_san = c_hien_co + s_hien_co + cash_hien_co
    tong_nap = c_nap + s_nap + cash_nap
    tong_rut = c_rut + s_rut + cash_rut
    tong_von = tong_nap - tong_rut
    tong_lai = tong_tai_san - tong_von
    tong_lai_pct = (tong_lai / tong_von * 100) if tong_von > 0 else 0
    target_progress = (tong_tai_san / target_asset * 100) if target_asset > 0 else 0

    return {
        'tong_tai_san': tong_tai_san, 'tong_von': tong_von, 'tong_lai': tong_lai, 'tong_lai_pct': tong_lai_pct,
        'tong_nap': tong_nap, 'tong_rut': tong_rut,
        'c_hien_co': c_hien_co, 'c_von': c_von, 'c_nap': c_nap, 'c_rut': c_rut, 'c_lai': c_lai, 'c_lai_pct': c_lai_pct,
        's_hien_co': s_hien_co, 's_von': s_von, 's_nap': s_nap, 's_rut': s_rut, 's_lai': s_lai, 's_lai_pct': s_lai_pct,
        'cash_hien_co': cash_hien_co, 'cash_nap': cash_nap, 'cash_rut': cash_rut,
        'target_asset': target_asset, 'target_progress': target_progress
    }

# --- 3. MENU VÀ ĐIỀU HƯỚNG ---
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

async def get_history_menu(page=None):
    async with aiosqlite.connect(DB_FILE) as conn:
        async with conn.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY date DESC, id DESC") as c:
            rows = await c.fetchall()
    if not rows: return "Chưa có giao dịch nào.", None
    PAGE_SIZE = 10
    keyboard = []
    if page is None:
        display_rows, back_data = rows[:10], "recent"
    else:
        start_idx = page * PAGE_SIZE
        display_rows, back_data = rows[start_idx : start_idx + PAGE_SIZE], str(page)
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    for i, row in enumerate(display_rows):
        keyboard.append([InlineKeyboardButton(f"{emojis[i] if i<10 else i+1}. {row[1]} | {row[2]} {format_money(row[3])} ({row[4]})", callback_data=f"hist_{row[0]}_{back_data}")])
    if page is None:
        keyboard.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_page_0")])
    else:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Trang trước", callback_data=f"view_page_{page-1}"))
        if (page + 1) * PAGE_SIZE < len(rows): nav.append(InlineKeyboardButton("Trang sau ➡️", callback_data=f"view_page_{page+1}"))
        if nav: keyboard.append(nav)
        keyboard.append([InlineKeyboardButton("⬅️ Đóng full lịch sử", callback_data="back_to_recent")])
    return "📜 DANH SÁCH GIAO DỊCH:", InlineKeyboardMarkup(keyboard)

# --- 4. XỬ LÝ SỰ KIỆN ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Chào mừng bạn!", reply_markup=get_main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == '🏠 Menu Chính': await update.message.reply_text("Menu Chính:", reply_markup=get_main_menu())
    elif text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=get_tx_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu())
    
    state = context.user_data.get('state')
    # Xử lý cập nhật số dư
    if state and str(state).startswith('awaiting_balance_'):
        cat, amt = state.split("_")[2], parse_amount(text)
        if amt is not None:
            async with aiosqlite.connect(DB_FILE) as conn:
                await conn.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amt))
                await conn.commit()
            context.user_data.clear()
            await update.message.reply_text(f"✅ Đã cập nhật {cat}: {format_money(amt)}", reply_markup=get_asset_menu())
        else: await update.message.reply_text("⚠️ Nhập số hợp lệ:")
        return

    # Xử lý nạp/rút
    elif state in ['awaiting_nap', 'awaiting_rut']:
        amt = parse_amount(text)
        if amt is not None:
            cat, tx_type = context.user_data.get('category'), ('Nạp' if state == 'awaiting_nap' else 'Rút')
            async with aiosqlite.connect(DB_FILE) as conn:
                cursor = await conn.execute("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", (cat, tx_type, amt, datetime.datetime.now().strftime("%Y-%m-%d")))
                tx_id = cursor.lastrowid
                await conn.commit()
            context.user_data.clear()
            await update.message.reply_text(f"✅ Ghi nhận {tx_type} {format_money(amt)} vào {cat}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Hoàn tác", callback_data=f"undo_{tx_id}")]]))
        else: await update.message.reply_text("⚠️ Nhập số hợp lệ:")
        return

    # Xử lý mục tiêu
    elif state == 'awaiting_target':
        s = await get_stats()
        text_lower = text.lower()
        new_target = None
        if 'hòa vốn' in text_lower or 'hoà vốn' in text_lower: new_target = s['tong_von']
        else:
            match = re.search(r'(lãi|lời|âm|lỗ)\s*([\d\.]+)\s*(%|tr|triệu|m|tỷ|k)?', text_lower)
            if match:
                sign = 1 if match.group(1) in ['lãi', 'lời'] else -1
                val, unit = float(match.group(2)), match.group(3)
                if unit == '%': new_target = s['tong_von'] + sign * (s['tong_von'] * val / 100)
                elif unit in ['tr', 'triệu', 'm']: new_target = s['tong_von'] + sign * (val * 1000000)
                elif unit in ['tỷ', 'ty']: new_target = s['tong_von'] + sign * (val * 1000000000)
                elif unit in ['k']: new_target = s['tong_von'] + sign * (val * 1000)
                else: new_target = s['tong_von'] + sign * val
            else: new_target = parse_amount(text_lower)
        if new_target:
            async with aiosqlite.connect(DB_FILE) as conn:
                await conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_asset', ?)", (new_target,))
                await conn.commit()
            context.user_data.clear()
            await update.message.reply_text(f"✅ Mục tiêu mới: {format_money(new_target)}", reply_markup=get_asset_menu())
        else: await update.message.reply_text("⚠️ Không hiểu. Thử: Hòa vốn, Lãi 10%...")
        return

    # Xem tài sản
    if text == '💰 Xem Tổng Tài sản':
        s = await get_stats()
        t = s['tong_tai_san']
        reply = (f"🏆 TỔNG TÀI SẢN: {format_m(t)}\n{'📈' if s['tong_lai']>=0 else '📉'} {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)\n"
                 f"🎯 Mục tiêu: {s['target_progress']:.1f}% ({format_m(t)}/{format_m(s['target_asset'])})\n\n"
                 f"🌕 CRYPTO: {format_m(s['c_hien_co'])} (Vốn: {format_m(s['c_von'])}) | {s['c_lai_pct']:.1f}%\n"
                 f"📈 STOCK: {format_m(s['s_hien_co'])} (Vốn: {format_m(s['s_von'])}) | {s['s_lai_pct']:.1f}%\n"
                 f"💵 TIỀN MẶT: {format_m(s['cash_hien_co'])}")
        await update.message.reply_text(reply)
    elif text == '💵 Cập nhật Số dư':
        await update.message.reply_text("Chọn loại:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"), InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]]))
    elif text == '➕ Nạp tiền' or text == '➖ Rút tiền':
        action = 'nap' if 'Nạp' in text else 'rut'
        await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{action}_Crypto"), InlineKeyboardButton("📈 Stock", callback_data=f"cat_{action}_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data=f"cat_{action}_Cash")]]))
    elif text == '📊 Xuất báo cáo Excel':
        async with aiosqlite.connect(DB_FILE) as conn:
            async with conn.execute("SELECT category, type, amount, date FROM transactions ORDER BY date DESC") as c:
                rows = await c.fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=['Danh mục', 'Loại', 'Số tiền', 'Ngày'])
            buf = io.BytesIO()
            df.to_excel(buf, index=False); buf.seek(0)
            await update.message.reply_document(document=buf, filename=f"BaoCao_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx")
    elif text == '💾 Backup DB':
        if os.path.exists(DB_FILE): await update.message.reply_document(document=open(DB_FILE, 'rb'))
    elif text == '🎯 Đặt Mục tiêu':
        context.user_data['state'] = 'awaiting_target'
        await update.message.reply_text("Nhập mục tiêu (VD: Hòa vốn, Lãi 10%, 1 tỷ):")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); data = query.data
    if data.startswith("undo_"):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.execute("DELETE FROM transactions WHERE id = ?", (data.split("_")[1],)); await conn.commit()
        await query.edit_message_text("✅ Đã hoàn tác!")
    elif data.startswith("bal_"):
        context.user_data['state'] = f"awaiting_balance_{data.split('_')[1]}"
        await query.edit_message_text(f"Nhập số dư hiện tại cho {data.split('_')[1]}:")
    elif data.startswith("cat_"):
        p = data.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]
        await query.edit_message_text(f"Nhập số tiền {p[1]} cho {p[2]}:")

def main():
    init_db()
    app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("Bot đang chạy..."); app.run_polling()

if __name__ == '__main__': main()
