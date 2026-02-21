import os
import sqlite3
import logging
import datetime
import io
import re
import asyncio
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

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

DB_FILE = 'portfolio.db'
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# --- 0. CẤU HÌNH AI (Sửa lỗi 404) ---
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # Sử dụng tên model chuẩn để tránh lỗi v1beta
    ai_model = genai.GenerativeModel('gemini-1.5-flash')

# --- 1. KHỞI TẠO DATABASE (Giữ nguyên bản ổn định) ---
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
    if c.fetchone()[0] <= 4:
        c.execute("DELETE FROM assets")
        c.execute("DELETE FROM transactions")
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", 
                      [('Crypto', 20000000), ('Stock', 123000000), ('Cash', 0)])
        # ... (Dữ liệu mẫu 70 dòng của bạn giữ nguyên ở đây)
        full_data = [
            ('Crypto', 'Nạp', 2000000, '2021-04-07'), ('Crypto', 'Nạp', 5000000, '2021-04-12'),
            ('Crypto', 'Nạp', 15000000, '2021-04-15'), ('Crypto', 'Nạp', 1500000, '2021-04-26'),
            ('Crypto', 'Nạp', 5000000, '2022-02-22'), ('Crypto', 'Nạp', 5000000, '2024-03-11'),
            ('Crypto', 'Nạp', 8000000, '2024-05-21'), ('Crypto', 'Nạp', 5000000, '2024-06-12'),
            ('Crypto', 'Nạp', 10000000, '2024-06-14'), ('Crypto', 'Nạp', 5000000, '2024-09-12'),
            ('Crypto', 'Nạp', 5000000, '2024-09-13'), ('Crypto', 'Nạp', 5000000, '2024-09-28'),
            ('Crypto', 'Nạp', 5000000, '2024-10-11'), ('Crypto', 'Nạp', 5000000, '2024-11-07'),
            ('Crypto', 'Nạp', 5000000, '2024-11-10'), ('Crypto', 'Nạp', 5200000, '2024-11-10'),
            ('Crypto', 'Nạp', 20000000, '2024-11-11'), ('Crypto', 'Nạp', 20000000, '2024-11-21'),
            ('Crypto', 'Nạp', 20000000, '2024-11-22'), ('Crypto', 'Nạp', 20000000, '2024-11-23'),
            ('Crypto', 'Nạp', 40000000, '2024-11-27'), ('Crypto', 'Nạp', 40000000, '2024-12-03'),
            ('Crypto', 'Nạp', 20000000, '2024-12-19'), ('Crypto', 'Nạp', 10000000, '2025-02-02'),
            ('Crypto', 'Nạp', 8000000, '2025-02-28'), ('Crypto', 'Nạp', 10000000, '2025-03-11'),
            ('Crypto', 'Nạp', 5300000, '2025-04-04'), ('Crypto', 'Nạp', 13500000, '2025-05-19'),
            ('Crypto', 'Nạp', 10000000, '2025-08-10'), ('Crypto', 'Nạp', 20000000, '2026-02-20'),
            ('Crypto', 'Rút', 5000000, '2024-11-08'), ('Crypto', 'Rút', 24500000, '2025-06-25'),
            ('Crypto', 'Rút', 28000000, '2025-06-30'), ('Crypto', 'Rút', 30000000, '2025-07-01'),
            ('Crypto', 'Rút', 20000000, '2025-07-24'), ('Crypto', 'Rút', 20000000, '2025-07-30'),
            ('Crypto', 'Rút', 20000000, '2025-07-31'), ('Crypto', 'Rút', 20000000, '2025-08-05'),
            ('Crypto', 'Rút', 20000000, '2025-08-28'), ('Crypto', 'Rút', 20000000, '2025-09-23'),
            ('Crypto', 'Rút', 5000000, '2025-10-28'), ('Crypto', 'Rút', 10000000, '2025-11-03'),
            ('Crypto', 'Rút', 15000000, '2025-11-12'), ('Crypto', 'Rút', 13000000, '2026-01-28'),
            ('Stock', 'Nạp', 3000000, '2024-03-15'), ('Stock', 'Nạp', 7000000, '2024-03-25'),
            ('Stock', 'Nạp', 4000000, '2024-05-17'), ('Stock', 'Nạp', 4000000, '2024-05-17'),
            ('Stock', 'Nạp', 2800000, '2024-06-04'), ('Stock', 'Nạp', 4000000, '2024-06-14'),
            ('Stock', 'Nạp', 5000000, '2024-06-20'), ('Stock', 'Nạp', 2700000, '2024-08-14'),
            ('Stock', 'Nạp', 6800000, '2025-04-23'), ('Stock', 'Nạp', 15000000, '2025-05-05'),
            ('Stock', 'Nạp', 30000000, '2025-05-15'), ('Stock', 'Nạp', 20000000, '2025-07-29'),
            ('Stock', 'Nạp', 20000000, '2025-07-30'), ('Stock', 'Nạp', 20000000, '2025-08-01'),
            ('Stock', 'Nạp', 20000000, '2025-08-05'), ('Stock', 'Nạp', 20000000, '2025-08-29'),
            ('Stock', 'Nạp', 5000000, '2025-09-15'), ('Stock', 'Nạp', 5000000, '2025-09-20'),
            ('Stock', 'Nạp', 20000000, '2025-09-23'), ('Stock', 'Nạp', 10000000, '2025-10-30'),
            ('Stock', 'Nạp', 10000000, '2025-11-03'), ('Stock', 'Nạp', 5000000, '2025-11-05'),
            ('Stock', 'Nạp', 15000000, '2025-11-12'), ('Stock', 'Nạp', 13000000, '2026-01-28'),
            ('Stock', 'Rút', 7000000, '2025-02-27'), ('Stock', 'Rút', 80000000, '2025-06-27'),
            ('Stock', 'Rút', 2000000, '2025-07-23'), ('Stock', 'Rút', 3000000, '2025-08-26'),
            ('Stock', 'Rút', 10000000, '2025-08-30'), ('Stock', 'Rút', 50000000, '2025-12-24'),
            ('Stock', 'Rút', 4500000, '2025-12-29')
        ]
        c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", full_data)
    conn.commit()
    conn.close()

# --- 2. HÀM HỖ TRỢ ---
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
    assets = {row[0]: row[1] for row in c.execute("SELECT category, current_value FROM assets").fetchall()}
    txs = c.execute("SELECT category, type, SUM(amount) FROM transactions GROUP BY category, type").fetchall()
    tr = c.execute("SELECT value FROM settings WHERE key='target_asset'").fetchone()
    target_asset = tr[0] if tr else 0; conn.close()

    s = {'Crypto': {'Nạp': 0, 'Rút': 0}, 'Stock': {'Nạp': 0, 'Rút': 0}, 'Cash': {'Nạp': 0, 'Rút': 0}}
    for cat, t_type, amt in txs:
        if cat in s: s[cat][t_type] = amt

    c_hc, s_hc, cash_hc = assets.get('Crypto', 0), assets.get('Stock', 0), assets.get('Cash', 0)
    c_v, s_v, cash_v = s['Crypto']['Nạp'] - s['Crypto']['Rút'], s['Stock']['Nạp'] - s['Stock']['Rút'], s['Cash']['Nạp'] - s['Cash']['Rút']
    
    t_ts = c_hc + s_hc + cash_hc
    t_n = s['Crypto']['Nạp'] + s['Stock']['Nạp'] + s['Cash']['Nạp']
    t_r = s['Crypto']['Rút'] + s['Stock']['Rút'] + s['Cash']['Rút']
    t_v = t_n - t_r
    t_l = t_ts - t_v
    
    return {
        'tong_tai_san': t_ts, 'tong_von': t_v, 'tong_lai': t_l, 
        'tong_lai_pct': (t_l / t_v * 100) if t_v > 0 else 0,
        'tong_nap': t_n, 'tong_rut': t_r,
        'c_hien_co': c_hc, 'c_von': c_v, 'c_nap': s['Crypto']['Nạp'], 'c_rut': s['Crypto']['Rút'],
        's_hien_co': s_hc, 's_von': s_v, 's_nap': s['Stock']['Nạp'], 's_rut': s['Stock']['Rút'],
        'cash_hien_co': cash_hc, 'cash_nap': s['Cash']['Nạp'], 'cash_rut': s['Cash']['Rút'],
        'target_asset': target_asset, 'target_progress': (t_ts / target_asset * 100) if target_asset > 0 else 0
    }

# --- 3. MENU ---
def get_main_menu():
    return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '🤖 Trợ lý AI'], ['⚙️ Hệ thống']], resize_keyboard=True)

def get_asset_menu():
    return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)

def get_stats_menu():
    return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['🏠 Menu Chính']], resize_keyboard=True)

def get_history_menu(page=None):
    conn = sqlite3.connect(DB_FILE); c = conn.cursor()
    rows = c.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY date DESC, id DESC").fetchall(); conn.close()
    if not rows: return "Chưa có giao dịch.", None
    PAGE_SIZE = 10; kb = []
    if page is None: display, bd = rows[:10], "recent"; msg = "📜 10 GIAO DỊCH GẦN NHẤT\n\nClick để Sửa/Xóa:"
    else: start = page * PAGE_SIZE; display, bd = rows[start:start+PAGE_SIZE], str(page); msg = f"📜 LỊCH SỬ (Trang {page+1})"
    
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    for i, row in enumerate(display):
        kb.append([InlineKeyboardButton(f"{emojis[i] if i<10 else i+1}. {row[1]} | {row[2]} {format_money(row[3])} ({row[4]})", callback_data=f"hist_{row[0]}_{bd}")])
    
    if page is None: kb.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_page_0")])
    else:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"view_page_{page-1}"))
        if (page + 1) * PAGE_SIZE < len(rows): nav.append(InlineKeyboardButton("Sau ➡️", callback_data=f"view_page_{page+1}"))
        if nav: kb.append(nav)
        kb.append([InlineKeyboardButton("⬅️ Đóng", callback_data="back_to_recent")])
    return msg, InlineKeyboardMarkup(kb)

# --- 4. XỬ LÝ TEXT ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip(); state = context.user_data.get('state')
    
    if text in ['/start', '🏠 Menu Chính']:
        context.user_data.clear()
        await update.message.reply_text("👋 Chào mừng bạn! Tôi là Portfolio Manager Pro.\nHãy chọn tính năng bên dưới:", reply_markup=get_main_menu()); return

    # Điều hướng Menu
    if text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu()); return
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True)); return
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu()); return
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=ReplyKeyboardMarkup([['💾 Backup DB', '♻️ Restore DB'], ['❓ Hướng dẫn', '🏠 Menu Chính']], resize_keyboard=True)); return

    # Trợ lý AI (CHỐNG TREO)
    elif text == '🤖 Trợ lý AI':
        context.user_data['state'] = 'chatting_ai'
        await update.message.reply_text("🤖 AI đã sẵn sàng! Hãy hỏi tôi về danh mục hoặc nhờ tôi phân tích tài chính giúp bạn:"); return

    if state == 'chatting_ai':
        if not GEMINI_KEY: await update.message.reply_text("⚠️ Chưa cấu hình GEMINI_API_KEY."); return
        s = get_stats()
        prompt = (f"Bạn là chuyên gia tài chính. Dữ liệu: Tổng TS {format_money(s['tong_tai_san'])}, "
                  f"Lãi {s['tong_lai_pct']:.1f}%. Crypto {format_money(s['c_hien_co'])}, Stock {format_money(s['s_hien_co'])}. "
                  f"Trả lời ngắn gọn câu hỏi: {text}")
        loading = await update.message.reply_text("⌛ AI đang suy nghĩ...")
        try:
            # Chạy AI không đồng bộ để tránh treo Bot
            response = await asyncio.to_thread(ai_model.generate_content, prompt)
            await loading.delete(); await update.message.reply_text(response.text, parse_mode='Markdown')
        except Exception as e:
            await loading.delete(); await update.message.reply_text(f"❌ Lỗi AI: {str(e)}")
        return

    # Xử lý nhập số dư/nạp/rút
    if state and (state.startswith('awaiting_balance_') or state in ['awaiting_nap', 'awaiting_rut']):
        amount = parse_amount(text)
        if amount is not None:
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            if state.startswith('awaiting_balance_'):
                cat = state.split("_")[2]
                c.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amount))
                msg = f"✅ Cập nhật số dư {cat}: {format_money(amount)}"
            else:
                cat, t_type = context.user_data.get('category'), ('Nạp' if state == 'awaiting_nap' else 'Rút')
                c.execute("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", (cat, t_type, amount, datetime.datetime.now().strftime("%Y-%m-%d")))
                tx_id = c.lastrowid
                msg = f"✅ Đã ghi nhận {t_type} {format_money(amount)} vào {cat}."
                context.user_data['last_tx'] = tx_id
            conn.commit(); conn.close(); context.user_data.clear()
            kb = [[InlineKeyboardButton("↩️ Hoàn tác", callback_data=f"undo_{tx_id}")]] if 'tx_id' in locals() else None
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb) if kb else None)
        else: await update.message.reply_text("⚠️ Vui lòng nhập số hợp lệ (VD: 10tr, 50M).")
        return

    # Mục tiêu
    elif state == 'awaiting_target':
        s = get_stats(); nt = None; text_l = text.lower()
        if 'hòa vốn' in text_l or 'hoà vốn' in text_l: nt = s['tong_von']
        else:
            m = re.search(r'(lãi|lời|âm|lỗ)\s*([\d\.]+)\s*(%|tr|triệu|m|tỷ|ty|k)?', text_l)
            if m:
                d = 1 if m.group(1) in ['lãi', 'lời'] else -1; v, u = float(m.group(2)), m.group(3)
                if u == '%': nt = s['tong_von'] + d * (s['tong_von'] * v / 100)
                else: nt = s['tong_von'] + d * (parse_amount(f"{v}{u or ''}") or 0)
            else: nt = parse_amount(text)
        if nt:
            conn = sqlite3.connect(DB_FILE); conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_asset', ?)", (nt,)); conn.commit(); conn.close()
            context.user_data.clear(); await update.message.reply_text(f"✅ Đã đặt mục tiêu: {format_money(nt)}")
        return

    # Xem tổng tài sản (Định dạng chi tiết của bạn)
    if text == '💰 Xem Tổng Tài sản':
        s = get_stats(); t_ts = s['tong_tai_san']
        c_p = (s['c_hien_co']/t_ts*100) if t_ts>0 else 0; s_p = (s['s_hien_co']/t_ts*100) if t_ts>0 else 0; cash_p = (s['cash_hien_co']/t_ts*100) if t_ts>0 else 0
        reply = (f"🏆 TỔNG TÀI SẢN\n{format_m(t_ts)}\n{'📈' if s['tong_lai']>=0 else '📉'} {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)\n"
                 f"🎯 Mục tiêu: {s['target_progress']:.1f}% ({format_m(t_ts)} / {format_m(s['target_asset'])})\n\n"
                 f"📥 Tổng nạp: {format_m(s['tong_nap'])}\n📤 Tổng rút: {format_m(s['tong_rut'])}\n\n"
                 f"━━━━━━━━━━━━━━\n\n🟡 CRYPTO ({c_p:.0f}%)\n💰 Hiện có: {format_m(s['c_hien_co'])}\n🏦 Vốn thực: {format_m(s['c_von'])}\n"
                 f"📥 Nạp: {format_m(s['c_nap'])}\n📤 Rút: {format_m(s['c_rut'])}\n{'📈' if s['c_lai']>=0 else '📉'} Lãi/Lỗ: {format_money(s['c_lai'])}\n\n"
                 f"━━━━━━━━━━━━━━\n\n📈 STOCK ({s_p:.0f}%)\n💰 Hiện có: {format_m(s['s_hien_co'])}\n🏦 Vốn thực: {format_m(s['s_von'])}\n"
                 f"📥 Nạp: {format_m(s['s_nap'])}\n📤 Rút: {format_m(s['s_rut'])}\n{'📈' if s['s_lai']>=0 else '📉'} Lãi/Lỗ: {format_m(s['s_lai'])}")
        await update.message.reply_text(reply); return

    elif text == '📈 Biểu đồ':
        conn = sqlite3.connect(DB_FILE); txs = conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC").fetchall(); conn.close()
        if not txs: await update.message.reply_text("Chưa có dữ liệu."); return
        daily = {}
        for ds, t, a in txs: daily[ds] = daily.get(ds, 0) + (a if t == 'Nạp' else -a)
        dates, caps, cur = [], [], 0
        for d in sorted(daily.keys()):
            cur += daily[d]; dates.append(datetime.datetime.strptime(d, "%Y-%m-%d")); caps.append(cur)
        s = get_stats(); fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, caps, label="Vốn thực (Nạp - Rút)", color='#3498db', marker='.', linewidth=2)
        color_t = '#2ecc71' if s['tong_tai_san'] >= caps[-1] else '#e74c3c'
        ax.plot([dates[-1], datetime.datetime.now()], [caps[-1], s['tong_tai_san']], label=f"Hiện tại ({format_m(s['tong_tai_san'])})", color=color_t, marker='o', linestyle='--', linewidth=2)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{x/1000000:,.0f}M"))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        ax.set_title(f"BIẾN ĐỘNG TÀI SẢN\nLãi: {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)", fontweight='bold')
        ax.legend(); ax.grid(True, linestyle='--', alpha=0.6)
        buf = io.BytesIO(); plt.savefig(buf, format='png'); buf.seek(0); plt.close(fig)
        await update.message.reply_photo(photo=buf, caption="📈 Biểu đồ vốn và tài sản thực tế."); return

    elif text == '📜 Lịch sử': msg, mk = get_history_menu(); await update.message.reply_text(msg, reply_markup=mk); return
    elif text == '🎯 Đặt Mục tiêu': context.user_data['state'] = 'awaiting_target'; await update.message.reply_text("Nhập mục tiêu (VD: Hòa vốn, Lãi 10%):"); return
    elif text == '💵 Cập nhật Số dư': await update.message.reply_text("Chọn mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"), InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]])); return
    elif text == '💾 Backup DB': 
        if os.path.exists(DB_FILE): await update.message.reply_document(document=open(DB_FILE, 'rb'))
        return

# --- 5. CALLBACKS ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); data = q.data
    if data.startswith("undo_"):
        conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (data.split("_")[1],)); conn.commit(); conn.close()
        await q.edit_message_text("✅ Đã hoàn tác!")
    elif data.startswith("bal_"):
        context.user_data['state'] = f"awaiting_balance_{data.split('_')[1]}"
        await q.edit_message_text(f"Nhập số dư {data.split('_')[1]}:")
    elif data.startswith("cat_"):
        p = data.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]
        await q.edit_message_text(f"Nhập tiền {p[1]} cho {p[2]}:")
    elif data.startswith("hist_"):
        p = data.split("_"); kb = [[InlineKeyboardButton("✏️ Sửa", callback_data=f"edit_{p[1]}_{p[2]}"), InlineKeyboardButton("❌ Xóa", callback_data=f"del_{p[1]}_{p[2]}")], [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{p[2]}")]]
        await q.edit_message_text("Thao tác:", reply_markup=InlineKeyboardMarkup(kb))
    elif data.startswith("view_page_"):
        m, mk = get_history_menu(int(data.split("_")[2])); await q.edit_message_text(m, reply_markup=mk)
    elif data.startswith("back_view_") or data == "back_to_recent":
        m, mk = get_history_menu(); await q.edit_message_text(m, reply_markup=mk)

def main():
    init_db(); token = os.environ.get("BOT_TOKEN")
    if not token: return
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == '__main__': main()
