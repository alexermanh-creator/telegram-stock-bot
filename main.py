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
            
    target_asset = target_row[0] if target_row else 500000000
    stats = {'Crypto': {'Nạp': 0, 'Rút': 0}, 'Stock': {'Nạp': 0, 'Rút': 0}, 'Cash': {'Nạp': 0, 'Rút': 0}}
    for cat, t_type, amt in txs:
        if cat in stats: stats[cat][t_type] = amt

    res = {}
    total_val, total_nap, total_rut = 0, 0, 0

    for cat in ['Crypto', 'Stock', 'Cash']:
        hien_co = assets.get(cat, 0)
        nap, rut = stats[cat]['Nạp'], stats[cat]['Rút']
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

# --- 3. MENU ---
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
    kb = []
    if page is None: display_rows, bd = rows[:10], "recent"
    else: start = page * PAGE_SIZE; display_rows, bd = rows[start : start + PAGE_SIZE], str(page)
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    for i, r in enumerate(display_rows):
        kb.append([InlineKeyboardButton(f"{emojis[i] if i<10 else i+1}. {r[1]} | {r[2]} {format_money(r[3])} ({r[4]})", callback_data=f"hist_{r[0]}_{bd}")])
    if page is None: kb.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_page_0")])
    else:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"view_page_{page-1}"))
        if (page+1)*PAGE_SIZE < len(rows): nav.append(InlineKeyboardButton("Sau ➡️", callback_data=f"view_page_{page+1}"))
        if nav: kb.append(nav)
        kb.append([InlineKeyboardButton("🏠 Đóng", callback_data="back_to_recent")])
    return "📜 LỊCH SỬ GIAO DỊCH:", InlineKeyboardMarkup(kb)

# --- 4. VẼ BIỂU ĐỒ ---
def _draw_pie(s):
    fig, ax = plt.subplots(figsize=(5,5))
    d = s['details']
    labels = [l for l in ['Crypto', 'Stock', 'Cash'] if d[l]['hien_co'] > 0]
    sizes = [d[l]['hien_co'] for l in labels]
    if not sizes: return None
    ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=['#f39c12', '#3498db', '#2ecc71'])
    buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight'); plt.close(fig); buf.seek(0)
    return buf

def _draw_line(txs, s):
    daily = {}
    for d_str, t, a in txs:
        daily[d_str] = daily.get(d_str, 0) + (a if t == 'Nạp' else -a)
    dates, caps, cur = [], [], 0
    for d in sorted(daily.keys()):
        cur += daily[d]; dates.append(datetime.datetime.strptime(d, "%Y-%m-%d")); caps.append(cur)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, caps, label="Vốn thực", color='#3498db', marker='.', lw=2)
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x/1000000:,.0f}M"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
    plt.xticks(rotation=45); ax.grid(True, alpha=0.3); ax.legend()
    buf = io.BytesIO(); plt.savefig(buf, format='png', bbox_inches='tight'); plt.close(fig); buf.seek(0)
    return buf

# --- 5. XỬ LÝ LỆNH ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Chào mừng bạn!", reply_markup=get_main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == '🏠 Menu Chính': await update.message.reply_text("Menu Chính:", reply_markup=get_main_menu())
    elif text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=get_tx_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu())
    
    elif text == '💰 Xem Tổng Tài sản':
        s = await get_stats()
        d = s['details']
        msg = (f"🏆 TỔNG TÀI SẢN\n{format_money(s['total_val'])}\n"
               f"{'📈' if s['total_lai']>=0 else '📉'} {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"🎯 Tiến độ mục tiêu: {s['progress']:.1f}% ({format_money(s['total_val'])} / {format_m(s['target_asset'])})\n\n"
               f"📤 Tổng nạp: {format_money(s['total_nap'])}\n📥 Tổng rút: {format_money(s['total_rut'])}\n"
               f"----------------------------------\n\n"
               f"🟡 CRYPTO ({ (d['Crypto']['hien_co']/s['total_val']*100) if s['total_val']>0 else 0 :.0f}%)\n"
               f"💰 Tài sản hiện có: {format_money(d['Crypto']['hien_co'])}\n🏦 Vốn thực: {format_money(d['Crypto']['von'])}\n\n"
               f"📤 Nạp: {format_money(d['Crypto']['nap'])}\n📥 Rút: {format_money(d['Crypto']['rut'])}\n\n"
               f"{'📈' if d['Crypto']['lai']>=0 else '📉'} Lãi/Lỗ: {format_money(d['Crypto']['lai'])} ({d['Crypto']['pct']:.1f}%)\n"
               f"----------------------------------\n\n"
               f"📈 STOCK ({ (d['Stock']['hien_co']/s['total_val']*100) if s['total_val']>0 else 0 :.0f}%)\n"
               f"💰 Tài sản hiện có: {format_money(d['Stock']['hien_co'])}\n🏦 Vốn thực: {format_money(d['Stock']['von'])}\n\n"
               f"📤 Nạp: {format_money(d['Stock']['nap'])}\n📥 Rút: {format_money(d['Stock']['rut'])}\n\n"
               f"{'📈' if d['Stock']['lai']>=0 else '📉'} Lãi/Lỗ: {format_money(d['Stock']['lai'])} ({d['Stock']['pct']:.1f}%)\n"
               f"----------------------------------\n\n"
               f"💵 TIỀN MẶT ({ (d['Cash']['hien_co']/s['total_val']*100) if s['total_val']>0 else 0 :.0f}%)\n"
               f"💰 Số dư: {format_money(d['Cash']['hien_co'])}\n📤 Nạp: {format_money(d['Cash']['nap'])}\n📥 Rút: {format_money(d['Cash']['rut'])}")
        await update.message.reply_text(msg)

    elif text == '📜 Lịch sử':
        m, mk = await get_history_menu(); await update.message.reply_text(m, reply_markup=mk)
    elif text == '🥧 Phân bổ':
        s = await get_stats(); buf = await asyncio.to_thread(_draw_pie, s)
        if buf: await update.message.reply_photo(photo=buf)
        else: await update.message.reply_text("Tài sản đang trống.")
    elif text == '📈 Biểu đồ':
        async with aiosqlite.connect(DB_FILE) as conn:
            async with conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC") as c: txs = await c.fetchall()
        if txs:
            s = await get_stats(); buf = await asyncio.to_thread(_draw_line, txs, s)
            await update.message.reply_photo(photo=buf)
        else: await update.message.reply_text("Chưa có đủ dữ liệu để vẽ.")
    elif text == '📊 Xuất báo cáo Excel':
        async with aiosqlite.connect(DB_FILE) as conn:
            async with conn.execute("SELECT category, type, amount, date FROM transactions ORDER BY date DESC") as cursor: rows = await cursor.fetchall()
        if rows:
            df = pd.DataFrame(rows, columns=['Danh mục', 'Loại', 'Số tiền', 'Ngày'])
            buf = io.BytesIO(); df.to_excel(buf, index=False); buf.seek(0)
            await update.message.reply_document(document=buf, filename=f"BaoCao_{datetime.datetime.now().strftime('%Y%m%d')}.xlsx")
        else: await update.message.reply_text("Chưa có giao dịch.")
    elif text == '💵 Cập nhật Số dư':
        await update.message.reply_text("Chọn tài sản:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"), InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]]))
    elif text in ['➕ Nạp tiền', '➖ Rút tiền']:
        a = 'nap' if 'Nạp' in text else 'rut'
        await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{a}_Crypto"), InlineKeyboardButton("📈 Stock", callback_data=f"cat_{a}_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data=f"cat_{a}_Cash")]]))
    elif text == '🎯 Đặt Mục tiêu':
        context.user_data['state'] = 'awaiting_target'
        await update.message.reply_text("Nhập mục tiêu (VD: Hòa vốn, Lãi 10%, 1 tỷ):")
    elif text == '💾 Backup DB':
        if os.path.exists(DB_FILE): await update.message.reply_document(document=open(DB_FILE, 'rb'))

    state = context.user_data.get('state')
    if state and str(state).startswith('awaiting_balance_'):
        cat, amt = state.split("_")[2], parse_amount(text)
        if amt is not None:
            async with aiosqlite.connect(DB_FILE) as conn:
                await conn.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amt))
                await conn.commit()
            context.user_data.clear(); await update.message.reply_text(f"✅ Đã cập nhật {cat}: {format_money(amt)}", reply_markup=get_asset_menu())
        return

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); d = q.data
    if d.startswith("undo_"):
        async with aiosqlite.connect(DB_FILE) as conn:
            await conn.execute("DELETE FROM transactions WHERE id = ?", (d.split("_")[1],)); await conn.commit()
        await q.edit_message_text("✅ Đã hoàn tác!")
    elif d.startswith("bal_"):
        context.user_data['state'] = f"awaiting_balance_{d.split('_')[1]}"
        await q.edit_message_text(f"Nhập số dư hiện tại cho {d.split('_')[1]}:")
    elif d.startswith("cat_"):
        p = d.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]
        await q.edit_message_text(f"Nhập số tiền {p[1]} cho {p[2]}:")
    elif d.startswith("view_page_"):
        m, mk = await get_history_menu(int(d.split("_")[2])); await q.edit_message_text(m, reply_markup=mk)
    elif d == "back_to_recent":
        m, mk = await get_history_menu(); await q.edit_message_text(m, reply_markup=mk)

def main():
    init_db()
    app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("Bot đang khởi động..."); app.run_polling()

if __name__ == '__main__': main()
