import os
import sqlite3
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
import google.generativeai as genai
from telegram import (
    Update, ReplyKeyboardMarkup, InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)

# --- 0. CẤU HÌNH AI GEMINI ---
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')

# --- NẠP DỮ LIỆU TỪ FILE data.py ---
try:
    from data import INITIAL_ASSETS, INITIAL_TRANSACTIONS
except ImportError:
    INITIAL_ASSETS, INITIAL_TRANSACTIONS = [], []

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_FILE = 'portfolio.db'

# --- 1. KHỞI TẠO DATABASE (GIỮ NGUYÊN GỐC) ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (category TEXT PRIMARY KEY, current_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, type TEXT, amount REAL, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)''')
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('target_asset', 500000000)")
    c.execute("SELECT COUNT(*) FROM transactions")
    if c.fetchone()[0] == 0 and INITIAL_TRANSACTIONS:
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", INITIAL_ASSETS)
        c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", INITIAL_TRANSACTIONS)
    conn.commit()
    conn.close()

# --- 2. HÀM HỖ TRỢ (GIỮ NGUYÊN LOGIC CỦA BẠN) ---
def format_m(amount): return f"{amount / 1000000:.1f}M" if amount != 0 else "0"
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

def get_stats():
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT category, current_value FROM assets")
    assets = {row[0]: row[1] for row in c.fetchall()}
    c.execute("SELECT category, type, SUM(amount) FROM transactions GROUP BY category, type")
    txs = c.fetchall()
    c.execute("SELECT value FROM settings WHERE key='target_asset'")
    tr = c.fetchone(); target_asset = tr[0] if tr else 500000000
    conn.close()
    s = {'Crypto': {'Nạp': 0, 'Rút': 0}, 'Stock': {'Nạp': 0, 'Rút': 0}, 'Cash': {'Nạp': 0, 'Rút': 0}}
    for cat, t_type, amt in txs:
        if cat in s: s[cat][t_type] = amt
    c_hc, s_hc, cash_hc = assets.get('Crypto', 0), assets.get('Stock', 0), assets.get('Cash', 0)
    c_v, s_v, cash_v = s['Crypto']['Nạp'] - s['Crypto']['Rút'], s['Stock']['Nạp'] - s['Stock']['Rút'], s['Cash']['Nạp'] - s['Cash']['Rút']
    tong_ts = c_hc + s_hc + cash_hc
    tong_v = (s['Crypto']['Nạp'] + s['Stock']['Nạp'] + s['Cash']['Nạp']) - (s['Crypto']['Rút'] + s['Stock']['Rút'] + s['Cash']['Rút'])
    tong_l = tong_ts - tong_v
    return {
        'tong_tai_san': tong_ts, 'tong_von': tong_v, 'tong_lai': tong_l, 
        'tong_lai_pct': (tong_l / tong_v * 100) if tong_v > 0 else 0,
        'c_hien_co': c_hc, 's_hien_co': s_hc, 'cash_hien_co': cash_hc,
        'target_asset': target_asset, 'target_progress': (tong_ts / target_asset * 100) if target_asset > 0 else 0
    }

# --- 3. MENU KEYBOARD ---
def get_main_menu(): return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '🤖 Trợ lý AI'], ['⚙️ Hệ thống']], resize_keyboard=True)
def get_asset_menu(): return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_stats_menu(): return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_sys_menu(): return ReplyKeyboardMarkup([['💾 Backup DB', '♻️ Restore DB'], ['❓ Hướng dẫn', '🏠 Menu Chính']], resize_keyboard=True)

# --- 4. LỊCH SỬ CHUẨN (GIỮ NGUYÊN FORM BẠN MUỐN) ---
def get_history_menu(page=None):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    c.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY date DESC, id DESC")
    rows = c.fetchall(); conn.close()
    if not rows: return "Chưa có giao dịch.", None
    PAGE_SIZE = 10
    kb = []
    if page is None: display, bd = rows[:10], "recent"; msg = "📜 10 GIAO DỊCH GẦN NHẤT\n\nClick để Sửa/Xóa:"
    else: start = page * PAGE_SIZE; display, bd = rows[start:start+PAGE_SIZE], str(page); msg = f"📜 LỊCH SỬ (Trang {page+1})"
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    for i, r in enumerate(display):
        kb.append([InlineKeyboardButton(f"{emojis[i] if i<10 else i+1}. {r[1]} | {r[2]} {format_money(r[3])} ({r[4]})", callback_data=f"hist_{r[0]}_{bd}")])
    if page is None: kb.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_page_0")])
    else:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"view_page_{page-1}"))
        if (page+1)*PAGE_SIZE < len(rows): nav.append(InlineKeyboardButton("Sau ➡️", callback_data=f"view_page_{page+1}"))
        if nav: kb.append(nav)
        kb.append([InlineKeyboardButton("⬅️ Đóng", callback_data="back_to_recent")])
    return msg, InlineKeyboardMarkup(kb)

# --- 5. XỬ LÝ TEXT ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip(); state = context.user_data.get('state')

    # CHÀO MỪNG START
    if text in ['/start', '🏠 Menu Chính']:
        context.user_data.clear()
        welcome = "👋 **Chào mừng bạn đến với Portfolio AI!**\n\nTôi giúp bạn quản lý tiền bạc thông minh. Hãy chọn một mục bên dưới:"
        await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=get_main_menu()); return

    # ĐIỀU HƯỚNG MENU
    if text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True))

    # AI PHÂN TÍCH (FIX ĐÚNG DATA)
    elif text == '🤖 Trợ lý AI':
        context.user_data['state'] = 'chatting_ai'
        await update.message.reply_text("🤖 Tôi đã đọc danh mục của bạn. Bạn muốn hỏi gì nào?")
        return

    if state == 'chatting_ai':
        if not GEMINI_KEY: await update.message.reply_text("⚠️ Vui lòng cấu hình GEMINI_API_KEY."); return
        s = get_stats()
        prompt = (f"Bạn là chuyên gia tài chính. Dữ liệu người dùng: "
                  f"Tổng TS: {format_money(s['tong_tai_san'])}, Lãi: {s['tong_lai_pct']:.1f}%. "
                  f"Crypto: {format_money(s['c_hien_co'])}, Stock: {format_money(s['s_hien_co'])}. "
                  f"Câu hỏi: {text}")
        loading = await update.message.reply_text("⌛ AI đang suy nghĩ..."); res = ai_model.generate_content(prompt)
        await loading.delete(); await update.message.reply_text(res.text, parse_mode='Markdown'); return

    # TỔNG TÀI SẢN (DÙNG ĐÚNG HÀM GỐC)
    elif text == '💰 Xem Tổng Tài sản':
        s = get_stats()
        msg = (f"🏆 *TỔNG TÀI SẢN*\n`{format_money(s['tong_tai_san'])}` VNĐ\n"
               f"{'📈' if s['tong_lai']>=0 else '📉'} {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)\n"
               f"🎯 Mục tiêu: {s['target_progress']:.1f}% (`{format_m(s['target_asset'])}`)\n"
               f"----------------------------------\n\n"
               f"🟡 *CRYPTO*: {format_money(s['c_hien_co'])}\n"
               f"📈 *STOCK*: {format_money(s['s_hien_co'])}\n"
               f"💵 *TIỀN MẶT*: {format_money(s['cash_hien_co'])}")
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif text == '📈 Biểu đồ':
        conn = sqlite3.connect(DB_FILE); txs = conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC").fetchall(); conn.close()
        if txs:
            daily = {}; s = get_stats()
            for ds, t, a in txs: daily[ds] = daily.get(ds, 0) + (a if t == 'Nạp' else -a)
            dates, caps, cur = [], [], 0
            for d in sorted(daily.keys()):
                cur += daily[d]; dates.append(datetime.datetime.strptime(d, "%Y-%m-%d")); caps.append(cur)
            fig, ax = plt.subplots(figsize=(10, 5)); ax.plot(dates, caps, color='#1f77b4', linewidth=2, marker='o', markersize=3)
            ax.fill_between(dates, caps, color='#1f77b4', alpha=0.15); ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x/1000000:,.0f}M"))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y')); ax.grid(True, linestyle='--', alpha=0.4)
            buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=120); plt.close(); buf.seek(0)
            await update.message.reply_photo(photo=buf)

    elif text == '❓ Hướng dẫn':
        await update.message.reply_text("📘 **CẨM NANG:**\n- Nhập số tiền: `10tr`, `500k`.\n- Nhấn **Undo** ngay sau khi Nạp/Rút nếu nhầm.\n- Hỏi AI để phân tích lãi lỗ.")

    # Xử lý Nạp/Rút + UNDO
    elif state in ['awaiting_nap', 'awaiting_rut']:
        amt = parse_amount(text)
        if amt:
            cat = context.user_data.get('category'); t_type = 'Nạp' if state == 'awaiting_nap' else 'Rút'
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            c.execute("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", (cat, t_type, amt, datetime.datetime.now().strftime("%Y-%m-%d")))
            tx_id = c.lastrowid; conn.commit(); conn.close(); context.user_data.clear()
            kb = [[InlineKeyboardButton("↩️ Hoàn tác (Undo)", callback_data=f"undo_{tx_id}")]]
            await update.message.reply_text(f"✅ Đã ghi nhận {t_type} {format_money(amt)}.", reply_markup=InlineKeyboardMarkup(kb))
    
    elif text == '📜 Lịch sử':
        msg, mk = get_history_menu(); await update.message.reply_text(msg, reply_markup=mk)

# --- 6. CALLBACKS (GIỮ NGUYÊN FORM CHUẨN) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); d = q.data
    if d.startswith("undo_"):
        conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (d.split("_")[1],)); conn.commit(); conn.close()
        await q.edit_message_text("✅ Đã hoàn tác!")
    elif d.startswith("hist_"):
        p = d.split("_"); kb = [[InlineKeyboardButton("✏️ Sửa", callback_data=f"edit_{p[1]}_{p[2]}"), InlineKeyboardButton("❌ Xóa", callback_data=f"del_{p[1]}_{p[2]}")], [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{p[2]}")]]
        await q.edit_message_text("Thao tác:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("view_page_"):
        m, mk = get_history_menu(int(d.split("_")[2])); await q.edit_message_text(m, reply_markup=mk)
    elif d.startswith("cat_"):
        p = d.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]
        await q.edit_message_text(f"Nhập tiền {p[1]} cho {p[2]}:")

def main():
    init_db(); app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", handle_text)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback)); app.run_polling()

if __name__ == '__main__': main()
