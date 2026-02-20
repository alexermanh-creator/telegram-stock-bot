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

# Import dữ liệu từ data.py
try:
    from data import INITIAL_ASSETS, INITIAL_TRANSACTIONS
except ImportError:
    INITIAL_ASSETS, INITIAL_TRANSACTIONS = [], []

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_FILE = 'portfolio.db'

# --- 1. KHỞI TẠO DATABASE ---
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

# --- 2. HÀM HỖ TRỢ ---
def format_m(amount): return f"{amount / 1000000:.1f}M"
def format_money(amount): return f"{int(amount):,}"
def parse_amount(text):
    text_lower = text.lower().strip().replace(',', '').replace(' ', '')
    match = re.search(r'^([\d\.]+)(tr|triệu|trieu|m|tỷ|ty|k|nghìn)?$', text_lower)
    if match:
        val, unit = float(match.group(1)), match.group(2)
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
            tr = await c.fetchone()
    
    target_asset = tr[0] if tr else 500000000
    s = {'Crypto': {'Nạp': 0, 'Rút': 0}, 'Stock': {'Nạp': 0, 'Rút': 0}, 'Cash': {'Nạp': 0, 'Rút': 0}}
    for cat, t_type, amt in txs:
        if cat in s: s[cat][t_type] = amt

    res, tv, tn, trut = {}, 0, 0, 0
    for cat in ['Crypto', 'Stock', 'Cash']:
        hc = assets.get(cat, 0)
        nap, rut = s[cat].get('Nạp', 0), s[cat].get('Rút', 0)
        von = nap - rut
        lai = hc - von
        pct = (lai / von * 100) if von != 0 else 0
        res[cat] = {'hien_co': hc, 'nap': nap, 'rut': rut, 'von': von, 'lai': lai, 'pct': pct}
        tv += hc; tn += nap; trut += rut

    tvon = tn - trut
    tlai = tv - tvon
    tlai_pct = (tlai / tvon * 100) if tvon != 0 else 0
    prog = (tv / target_asset * 100) if target_asset > 0 else 0
    return {'total_val': tv, 'total_von': tvon, 'total_lai': tlai, 'total_lai_pct': tlai_pct, 'total_nap': tn, 'total_rut': trut, 'target_asset': target_asset, 'progress': prog, 'details': res}

# --- 3. GIAO DIỆN MENU ---
def get_main_menu(): return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '⚙️ Hệ thống']], resize_keyboard=True)
def get_asset_menu(): return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_tx_menu(): return ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_stats_menu(): return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['📊 Xuất báo cáo Excel'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_sys_menu(): return ReplyKeyboardMarkup([['💾 Backup DB', '♻️ Restore DB'], ['❓ Hướng dẫn', '🏠 Menu Chính']], resize_keyboard=True)

# --- 4. VẼ BIỂU ĐỒ ---
def _draw_pie(s):
    plt.figure(figsize=(6, 6))
    d = s['details']
    labels = [l for l in ['Crypto', 'Stock', 'Cash'] if d[l]['hien_co'] > 0]
    sizes = [d[l]['hien_co'] for l in labels]
    if not sizes: return None
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#f39c12', '#3498db', '#2ecc71'])
    plt.title("PHÂN BỔ TÀI SẢN")
    buf = io.BytesIO(); plt.savefig(buf, format='png'); plt.close(); buf.seek(0)
    return buf

def _draw_line(txs, s):
    plt.figure(figsize=(10, 5))
    daily = {}
    for d_str, t, a in txs:
        daily[d_str] = daily.get(d_str, 0) + (a if t == 'Nạp' else -a)
    dates, caps, cur = [], [], 0
    for d in sorted(daily.keys()):
        cur += daily[d]; dates.append(datetime.datetime.strptime(d, "%Y-%m-%d")); caps.append(cur)
    plt.plot(dates, caps, label="Vốn thực (Nạp - Rút)", marker='.', color='tab:blue', linewidth=2)
    plt.gca().yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x/1000000:,.0f}M"))
    plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
    plt.title("BIỂU ĐỒ BIẾN ĐỘNG TÀI SẢN")
    plt.legend(); plt.grid(True, linestyle=':', alpha=0.6); plt.xticks(rotation=45)
    buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight'); plt.close(); buf.seek(0)
    return buf

# --- 5. XỬ LÝ CHÍNH ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    state = context.user_data.get('state')

    if text == '/start' or text == '🏠 Menu Chính':
        await update.message.reply_text("🏠 Menu Chính:", reply_markup=get_main_menu())
        return

    # Nhóm Menu
    elif text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=get_tx_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu())

    # Xem tài sản chi tiết
    elif text == '💰 Xem Tổng Tài sản':
        s = await get_stats(); d = s['details']
        msg = (f"🏆 TỔNG TÀI SẢN\n{format_money(s['total_val'])}\n"
               f"{'📈' if s['total_lai']>=0 else '📉'} {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"🎯 Tiến độ mục tiêu: {s['progress']:.1f}% ({format_money(s['total_val'])} / {format_money(s['target_asset'])})\n\n"
               f"📤 Tổng nạp: {format_money(s['total_nap'])}\n📥 Tổng rút: {format_money(s['total_rut'])}\n"
               f"----------------------------------\n\n"
               f"🟡 CRYPTO\n💰 Hiện có: {format_money(d['Crypto']['hien_co'])}\n🏦 Vốn thực: {format_money(d['Crypto']['von'])}\n"
               f"📤 Nạp: {format_money(d['Crypto']['nap'])} | 📥 Rút: {format_money(d['Crypto']['rut'])}\n"
               f"{'📈' if d['Crypto']['lai']>=0 else '📉'} Lãi/Lỗ: {format_money(d['Crypto']['lai'])} ({d['Crypto']['pct']:.1f}%)\n\n"
               f"📈 STOCK\n💰 Hiện có: {format_money(d['Stock']['hien_co'])}\n🏦 Vốn thực: {format_money(d['Stock']['von'])}\n"
               f"📤 Nạp: {format_money(d['Stock']['nap'])} | 📥 Rút: {format_money(d['Stock']['rut'])}\n"
               f"{'📈' if d['Stock']['lai']>=0 else '📉'} Lãi/Lỗ: {format_money(d['Stock']['lai'])} ({d['Stock']['pct']:.1f}%)\n\n"
               f"💵 TIỀN MẶT: {format_money(d['Cash']['hien_co'])}")
        await update.message.reply_text(msg)

    # Thống kê & Biểu đồ
    elif text == '🥧 Phân bổ':
        s = await get_stats(); buf = await asyncio.to_thread(_draw_pie, s)
        if buf: await update.message.reply_photo(photo=buf)
    elif text == '📈 Biểu đồ':
        async with aiosqlite.connect(DB_FILE) as conn:
            async with conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC") as c: txs = await c.fetchall()
        if txs:
            s = await get_stats(); buf = await asyncio.to_thread(_draw_line, txs, s)
            await update.message.reply_photo(photo=buf)
    
    # Mục tiêu & Giao dịch
    elif text == '🎯 Đặt Mục tiêu':
        context.user_data['state'] = 'awaiting_target'
        await update.message.reply_text("Nhập mục tiêu (VD: Hòa vốn, Lãi 10%, 1 tỷ):")
    
    elif text == '💵 Cập nhật Số dư':
        await update.message.reply_text("Chọn tài sản:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"), InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]]))

    elif text in ['➕ Nạp tiền', '➖ Rút tiền']:
        a = 'nap' if 'Nạp' in text else 'rut'
        await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{a}_Crypto"), InlineKeyboardButton("📈 Stock", callback_data=f"cat_{a}_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data=f"cat_{a}_Cash")]]))

    # Xử lý nhập liệu từ trạng thái (State)
    if state == 'awaiting_target':
        s = await get_stats(); text_l = text.lower(); nt = None
        if 'hòa vốn' in text_l or 'hoà vốn' in text_l: nt = s['total_von']
        else:
            m = re.search(r'(lãi|lời|âm|lỗ)\s*([\d\.]+)\s*(%|tr|triệu|m|tỷ|ty|k)?', text_l)
            if m:
                d = 1 if m.group(1) in ['lãi', 'lời'] else -1
                v, u = float(m.group(2)), m.group(3)
                if u == '%': nt = s['total_von'] + (s['total_von'] * (d * v / 100))
                else: nt = s['total_von'] + (d * (parse_amount(f"{v}{u or ''}") or 0))
            else: nt = parse_amount(text)
        if nt:
            async with aiosqlite.connect(DB_FILE) as conn:
                await conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_asset', ?)", (nt,)); await conn.commit()
            context.user_data.clear(); await update.message.reply_text(f"✅ Đã đặt mục tiêu: {format_money(nt)}", reply_markup=get_asset_menu())
        return

    if state and str(state).startswith('awaiting_balance_'):
        cat, amt = state.split("_")[2], parse_amount(text)
        if amt is not None:
            async with aiosqlite.connect(DB_FILE) as conn:
                await conn.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amt)); await conn.commit()
            context.user_data.clear(); await update.message.reply_text(f"✅ Đã cập nhật {cat}.", reply_markup=get_asset_menu())
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); d = q.data
    if d.startswith("bal_"):
        context.user_data['state'] = f"awaiting_balance_{d.split('_')[1]}"
        await q.edit_message_text(f"Nhập số dư mới cho {d.split('_')[1]}:")
    elif d.startswith("cat_"):
        p = d.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]
        await q.edit_message_text(f"Nhập tiền {p[1]} cho {p[2]}:")

def main():
    init_db()
    app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == '__main__': main()
