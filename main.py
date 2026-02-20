import os
import sqlite3
import logging
import datetime
import io
import re
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

# --- NẠP DỮ LIỆU TỪ FILE data.py ---
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
    
    c.execute("SELECT COUNT(*) FROM transactions")
    tx_count = c.fetchone()[0]
    
    # Nạp dữ liệu từ data.py nếu DB trống
    if tx_count == 0 and INITIAL_TRANSACTIONS:
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", INITIAL_ASSETS)
        c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", INITIAL_TRANSACTIONS)
        
    conn.commit()
    conn.close()

# --- 2. HÀM HỖ TRỢ ---
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

def get_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT category, current_value FROM assets")
    assets = {row[0]: row[1] for row in c.fetchall()}
    c.execute("SELECT category, type, SUM(amount) FROM transactions GROUP BY category, type")
    txs = c.fetchall()
    
    c.execute("SELECT value FROM settings WHERE key='target_asset'")
    target_row = c.fetchone()
    target_asset = target_row[0] if target_row else 0
    conn.close()

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

# --- CÁC MENU KEYBOARD ---
def get_main_menu():
    return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '⚙️ Hệ thống']], resize_keyboard=True)

def get_asset_menu():
    return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)

def get_tx_menu():
    return ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True)

def get_stats_menu():
    return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['🏠 Menu Chính']], resize_keyboard=True)

def get_sys_menu():
    return ReplyKeyboardMarkup([['💾 Backup DB', '♻️ Restore DB'], ['❓ Hướng dẫn', '🏠 Menu Chính']], resize_keyboard=True)

# --- GIỮ FORM LỊCH SỬ CHUẨN ---
def get_history_menu(page=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY date DESC, id DESC")
    rows = c.fetchall()
    conn.close()

    if not rows: return "Chưa có giao dịch nào.", None

    PAGE_SIZE = 10
    keyboard = []
    
    if page is None:
        display_rows = rows[:10]; msg = "📜 10 GIAO DỊCH GẦN NHẤT\n\nClick để Sửa/Xóa:"; back_data = "recent"
    else:
        start_idx = page * PAGE_SIZE; display_rows = rows[start_idx : start_idx + PAGE_SIZE]
        total_pages = (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE
        msg = f"📜 FULL LỊCH SỬ (Trang {page + 1}/{total_pages})\n\nClick để Sửa/Xóa:"; back_data = str(page)

    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    for i, row in enumerate(display_rows):
        emoji = emojis[i] if i < 10 else f"{i+1}."
        btn_text = f"{emoji} {row[1]} | {row[2]} {format_money(row[3])} ({row[4]})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"hist_{row[0]}_{back_data}")])
        
    if page is None:
        keyboard.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_page_0")])
    else:
        nav_row = []
        if page > 0: nav_row.append(InlineKeyboardButton("⬅️ Trang trước", callback_data=f"view_page_{page-1}"))
        if (page + 1) * PAGE_SIZE < len(rows): nav_row.append(InlineKeyboardButton("Trang sau ➡️", callback_data=f"view_page_{page+1}"))
        if nav_row: keyboard.append(nav_row)
        keyboard.append([InlineKeyboardButton("⬅️ Đóng full lịch sử", callback_data="back_to_recent")])
    return msg, InlineKeyboardMarkup(keyboard)

# --- 3. XỬ LÝ LỆNH ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("👋 Hệ thống Quản lý Tài sản đã sẵn sàng:", reply_markup=get_main_menu())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip(); state = context.user_data.get('state')
    
    if text == '🏠 Menu Chính' or text == '/start':
        context.user_data.clear(); await update.message.reply_text("🏠 Menu Chính:", reply_markup=get_main_menu()); return
    elif text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu()); return
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=get_tx_menu()); return
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu()); return
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu()); return

    # Xử lý nhập số dư
    if state and str(state).startswith('awaiting_balance_'):
        cat = state.split("_")[2]; amount = parse_amount(text)
        if amount is not None:
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amount))
            conn.commit(); conn.close(); context.user_data.clear()
            await update.message.reply_text(f"✅ Đã cập nhật số dư {cat}.", reply_markup=get_asset_menu())
        return

    # Xử lý Nạp/Rút
    elif state in ['awaiting_nap', 'awaiting_rut']:
        amount = parse_amount(text)
        if amount is not None:
            cat = context.user_data.get('category'); tx_type = 'Nạp' if state == 'awaiting_nap' else 'Rút'
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            c.execute("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", (cat, tx_type, amount, datetime.datetime.now().strftime("%Y-%m-%d")))
            conn.commit(); conn.close(); context.user_data.clear()
            await update.message.reply_text(f"✅ Đã ghi nhận {tx_type} vào {cat}.", reply_markup=get_tx_menu())
        return

    # Sửa lịch sử
    elif state and str(state).startswith('awaiting_edit_'):
        new_amount = parse_amount(text)
        if new_amount is not None:
            parts = state.split("_"); tx_id, back_to = parts[2], parts[3]
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            c.execute("UPDATE transactions SET amount = ? WHERE id = ?", (new_amount, tx_id))
            conn.commit(); conn.close(); context.user_data.clear()
            page = None if back_to == "recent" else int(back_to); msg, markup = get_history_menu(page)
            await update.message.reply_text(f"✅ Đã sửa thành {format_money(new_amount)}.\n\n{msg}", reply_markup=markup)
        return

    # Mục tiêu
    elif state == 'awaiting_target':
        s = get_stats(); text_l = text.lower(); nt = None
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
            context.user_data.clear(); await update.message.reply_text(f"✅ Mục tiêu mới: {format_money(nt)}", reply_markup=get_asset_menu())
        return

    # Chức năng cụ thể
    if text == '💰 Xem Tổng Tài sản':
        s = get_stats()
        reply = (f"🏆 TỔNG TÀI SẢN\n{format_m(s['tong_tai_san'])}\n{'📈' if s['tong_lai']>=0 else '📉'} {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)\n"
                 f"🎯 Tiến độ: {s['target_progress']:.1f}% (`{format_m(s['tong_tai_san'])}` / `{format_m(s['target_asset'])}`)\n\n"
                 f"🌕 CRYPTO: {format_m(s['c_hien_co'])}\n📈 STOCK: {format_m(s['s_hien_co'])}\n💵 TIỀN MẶT: {format_m(s['cash_hien_co'])}")
        await update.message.reply_text(reply)

    elif text == '📜 Lịch sử':
        msg, markup = get_history_menu(); await update.message.reply_text(msg, reply_markup=markup)

    elif text == '🥧 Phân bổ':
        s = get_stats(); plt.figure(figsize=(5,5)); labels = ['Crypto', 'Stock', 'Cash']
        vals = [s['c_hien_co'], s['s_hien_co'], s['cash_hien_co']]
        if sum(vals) == 0: await update.message.reply_text("Tài sản trống."); return
        plt.pie([v for v in vals if v > 0], labels=[l for l, v in zip(labels, vals) if v > 0], autopct='%1.1f%%', startangle=90)
        buf = io.BytesIO(); plt.savefig(buf, format='png'); plt.close(); buf.seek(0)
        await update.message.reply_photo(photo=buf)

    # --- GIỮ ĐỊNH DẠNG BIỂU ĐỒ CHUẨN ---
    elif text == '📈 Biểu đồ':
        conn = sqlite3.connect(DB_FILE); txs = conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC").fetchall(); conn.close()
        if not txs: await update.message.reply_text("Chưa có đủ dữ liệu."); return
        daily = {}
        for ds, t, a in txs: daily[ds] = daily.get(ds, 0) + (a if t == 'Nạp' else -a)
        dates, caps, cur = [], [], 0
        for d in sorted(daily.keys()):
            cur += daily[d]; dates.append(datetime.datetime.strptime(d, "%Y-%m-%d")); caps.append(cur)
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(dates, caps, label="Vốn thực (Nạp - Rút)", color='#3498db', marker='.', linewidth=2)
        s = get_stats(); today = datetime.datetime.now()
        color_t = '#2ecc71' if s['tong_tai_san'] >= caps[-1] else '#e74c3c'
        ax.plot([dates[-1], today], [caps[-1], s['tong_tai_san']], label=f"Tổng tài sản hiện tại ({format_m(s['tong_tai_san'])})", color=color_t, marker='o', linestyle='--', linewidth=2, markersize=8)
        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x/1000000:,.0f}M"))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        ax.set_title(f"BIỂU ĐỒ BIẾN ĐỘNG TÀI SẢN\nLãi/Lỗ: {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)", fontweight='bold')
        ax.legend(); ax.grid(True, linestyle='--', alpha=0.6); plt.xticks(rotation=45); plt.tight_layout()
        buf = io.BytesIO(); plt.savefig(buf, format='png'); plt.close(); buf.seek(0)
        await update.message.reply_photo(photo=buf, caption="📈 Trục ngang: Thời gian | Trục dọc: Số tiền\n▫️ Đường Xanh dương: Vốn lũy kế.\n▫️ Đường Đứt nét: Sự chênh lệch (Lãi/lỗ) so với Tài sản hiện tại.")

    elif text == '💳 Quỹ Tiền mặt':
        s = get_stats(); await update.message.reply_text(f"💵 TIỀN MẶT\n💰 Số dư: {format_money(s['cash_hien_co'])}\n📥 Nạp: {format_money(s['cash_nap'])}\n📤 Rút: {format_money(s['cash_rut'])}")
    elif text == '💾 Backup DB':
        if os.path.exists(DB_FILE): await update.message.reply_document(document=open(DB_FILE, 'rb'))
    elif text == '💵 Cập nhật Số dư':
        await update.message.reply_text("Chọn tài sản:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"), InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]]))
    elif text in ['➕ Nạp tiền', '➖ Rút tiền']:
        a = 'nap' if 'Nạp' in text else 'rut'
        await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{a}_Crypto"), InlineKeyboardButton("📈 Stock", callback_data=f"cat_{a}_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data=f"cat_{a}_Cash")]]))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); d = q.data
    if d.startswith("hist_"):
        parts = d.split("_"); tx_id, bd = parts[1], parts[2]
        kb = [[InlineKeyboardButton("✏️ Sửa", callback_data=f"edit_{tx_id}_{bd}"), InlineKeyboardButton("❌ Xóa", callback_data=f"del_{tx_id}_{bd}")], [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{bd}")]]
        await q.edit_message_text("Thao tác với giao dịch này:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("edit_"):
        p = d.split("_"); context.user_data['state'] = f"awaiting_edit_{p[1]}_{p[2]}"; await q.edit_message_text("📝 Nhập số tiền mới:")
    elif d.startswith("del_"):
        p = d.split("_"); conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (p[1],)); conn.commit(); conn.close()
        pg = None if p[2] == "recent" else int(p[2]); m, mk = get_history_menu(pg); await q.edit_message_text(f"✅ Đã xóa.\n\n{m}", reply_markup=mk)
    elif d.startswith("view_page_"):
        m, mk = get_history_menu(int(d.split("_")[2])); await q.edit_message_text(m, reply_markup=mk)
    elif d == "back_to_recent":
        m, mk = get_history_menu(); await q.edit_message_text(m, reply_markup=mk)
    elif d.startswith("back_view_"):
        bt = d.split("back_view_")[1]; pg = None if bt == "recent" else int(bt); m, mk = get_history_menu(pg); await q.edit_message_text(m, reply_markup=mk)
    elif d.startswith("bal_"):
        context.user_data['state'] = f"awaiting_balance_{d.split('_')[1]}"; await q.edit_message_text(f"Nhập số dư {d.split('_')[1]}:")
    elif d.startswith("cat_"):
        p = d.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]; await q.edit_message_text(f"Nhập tiền {p[1]} cho {p[2]}:")

def main():
    init_db(); app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", start_cmd)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback)); app.run_polling()

if __name__ == '__main__': main()
