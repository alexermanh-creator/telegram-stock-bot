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

# Cấu hình Style cho biểu đồ "Pro"
plt.style.use('dark_background')
matplotlib.rcParams['axes.facecolor'] = '#121212'
matplotlib.rcParams['figure.facecolor'] = '#121212'
matplotlib.rcParams['grid.color'] = '#2C2C2C'

try:
    from data import INITIAL_ASSETS, INITIAL_TRANSACTIONS
except ImportError:
    INITIAL_ASSETS, INITIAL_TRANSACTIONS = [], []

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_FILE = 'portfolio.db'

# --- 1. DATABASE ---
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

    res, tv, tn, trut = {}, 0, 0, 0
    for cat in ['Crypto', 'Stock', 'Cash']:
        hc = assets.get(cat, 0)
        nap, rut = stats[cat]['Nạp'], stats[cat]['Rút']
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

# --- 3. VẼ BIỂU ĐỒ PRO ---
def _draw_pro_pie(s):
    d = s['details']
    labels = [f"{l}\n({format_m(d[l]['hien_co'])})" for l in ['Crypto', 'Stock', 'Cash'] if d[l]['hien_co'] > 0]
    sizes = [d[l]['hien_co'] for l in ['Crypto', 'Stock', 'Cash'] if d[l]['hien_co'] > 0]
    if not sizes: return None
    
    fig, ax = plt.subplots(figsize=(7, 7))
    colors = ['#00E676', '#2979FF', '#FF9100']
    
    wedges, texts, autotexts = ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, 
                                    colors=colors, pctdistance=0.85, explode=[0.05]*len(sizes))
    
    # Tạo hình tròn trắng ở giữa để biến thành Donut Chart
    centre_circle = plt.Circle((0,0), 0.70, fc='#121212')
    fig.gca().add_artist(centre_circle)
    
    plt.setp(autotexts, size=10, weight="bold", color="white")
    plt.setp(texts, size=11, color="#B0B0B0")
    ax.set_title("PHÂN BỔ TÀI SẢN", fontsize=15, color='white', pad=20, weight='bold')
    
    buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=120); plt.close(fig); buf.seek(0)
    return buf

def _draw_pro_line(txs):
    daily = {}
    for ds, t, a in txs: daily[ds] = daily.get(ds, 0) + (a if t == 'Nạp' else -a)
    dates, caps, cur = [], [], 0
    for d in sorted(daily.keys()):
        cur += daily[d]; dates.append(datetime.datetime.strptime(d, "%Y-%m-%d")); caps.append(cur)
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(dates, caps, color='#2979FF', lw=3, label='Vốn tích lũy', marker='o', markersize=4, markerfacecolor='white')
    ax.fill_between(dates, caps, color='#2979FF', alpha=0.1) # Đổ bóng vùng dưới đường kẻ
    
    ax.set_title("BIỂU ĐỒ TĂNG TRƯỞNG VỐN", fontsize=14, color='white', pad=15, weight='bold')
    ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x/1000000:,.0f}M"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%y'))
    ax.grid(True, linestyle='--', alpha=0.2)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    
    plt.xticks(rotation=30, color='#888888')
    plt.yticks(color='#888888')
    
    buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=120); plt.close(fig); buf.seek(0)
    return buf

# --- 4. XỬ LÝ TEXT & COMMAND ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    state = context.user_data.get('state')

    # Xử lý MENU CHÍNH
    if text == '🏠 Menu Chính' or text == '/start':
        await update.message.reply_text("📱 HỆ THỐNG QUẢN LÝ PORTFOLIO", reply_markup=get_main_menu())
        return

    # Xử lý ĐẶT MỤC TIÊU (SỬA LỖI)
    if state == 'awaiting_target':
        s = await get_stats()
        text_l = text.lower()
        new_target = None
        
        if 'hòa vốn' in text_l or 'hoà vốn' in text_l: 
            new_target = s['total_von']
        else:
            # Check lãi/lỗ % hoặc tiền
            match = re.search(r'(lãi|lời|âm|lỗ)\s*([\d\.]+)\s*(%|tr|triệu|m|tỷ|ty|k)?', text_l)
            if match:
                dau = 1 if match.group(1) in ['lãi', 'lời'] else -1
                val, unit = float(match.group(2)), match.group(3)
                if unit == '%': new_target = s['total_von'] + (s['total_von'] * (dau * val / 100))
                else: 
                    so_tien = parse_amount(f"{val}{unit if unit else ''}")
                    new_target = s['total_von'] + (dau * so_tien)
            else:
                new_target = parse_amount(text)
        
        if new_target is not None:
            async with aiosqlite.connect(DB_FILE) as conn:
                await conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_asset', ?)", (new_target,))
                await conn.commit()
            context.user_data.clear()
            await update.message.reply_text(f"🎯 Đã cập nhật mục tiêu mới:\n✨ **{format_money(new_target)} VNĐ**", parse_mode='Markdown', reply_markup=get_asset_menu())
        else:
            await update.message.reply_text("⚠️ Không nhận diện được mục tiêu. Hãy thử lại (VD: 1 tỷ, Lãi 20%, Hòa vốn):")
        return

    # Các chức năng khác (giữ nguyên logic hiển thị Pro đã làm ở turn trước)
    if text == '💰 Xem Tổng Tài sản':
        s = await get_stats(); d = s['details']
        msg = (f"🏆 *TỔNG TÀI SẢN*\n`{format_money(s['total_val'])}`\n"
               f"{'📈' if s['total_lai']>=0 else '📉'} {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"🎯 Mục tiêu: {s['progress']:.1f}% (`{format_m(s['target_asset'])}`)\n"
               f"───────────────────\n"
               f"📤 Nạp: {format_money(s['total_nap'])} | 📥 Rút: {format_money(s['total_rut'])}\n\n"
               f"🟡 *CRYPTO*\n💰 Hiện có: {format_money(d['Crypto']['hien_co'])}\n📈 Lãi: {format_money(d['Crypto']['lai'])} ({d['Crypto']['pct']:.1f}%)\n\n"
               f"🔵 *STOCK*\n💰 Hiện có: {format_money(d['Stock']['hien_co'])}\n📈 Lãi: {format_money(d['Stock']['lai'])} ({d['Stock']['pct']:.1f}%)\n\n"
               f"💵 *TIỀN MẶT*: {format_money(d['Cash']['hien_co'])}")
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif text == '🥧 Phân bổ':
        s = await get_stats(); buf = await asyncio.to_thread(_draw_pro_pie, s)
        if buf: await update.message.reply_photo(photo=buf)
    
    elif text == '📈 Biểu đồ':
        async with aiosqlite.connect(DB_FILE) as conn:
            async with conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC") as c: txs = await c.fetchall()
        if txs:
            buf = await asyncio.to_thread(_draw_pro_line, txs)
            await update.message.reply_photo(photo=buf)

    elif text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=get_tx_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '🎯 Đặt Mục tiêu':
        context.user_data['state'] = 'awaiting_target'
        await update.message.reply_text("🎯 Nhập mục tiêu tài sản của bạn:\n(Hỗ trợ: '1 tỷ', 'Hòa vốn', 'Lãi 15%')")

# --- 5. HÀM MENU ---
def get_main_menu(): return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '⚙️ Hệ thống']], resize_keyboard=True)
def get_asset_menu(): return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_stats_menu(): return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['📊 Xuất báo cáo Excel'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_tx_menu(): return ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True)

# (Các hàm main, handle_callback giữ nguyên như bản trước...)
def main():
    init_db()
    app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.run_polling()

if __name__ == '__main__': main()
