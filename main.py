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
    if c.fetchone()[0] == 0 and INITIAL_TRANSACTIONS:
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", INITIAL_ASSETS)
        c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", INITIAL_TRANSACTIONS)
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
        pct = (lai / von * 100) if von != 0 else 0
        res[cat] = {'hien_co': hc, 'nap': nap, 'rut': rut, 'von': von, 'lai': lai, 'pct': pct}
        tv += hc; tn += nap; trut += rut

    tvon = tn - trut; tlai = tv - tvon; tlai_pct = (tlai / tvon * 100) if tvon != 0 else 0
    prog = (tv / target_asset * 100) if target_asset > 0 else 0
    return {'total_val': tv, 'total_von': tvon, 'total_lai': tlai, 'total_lai_pct': tlai_pct, 'total_nap': tn, 'total_rut': trut, 'target_asset': target_asset, 'progress': prog, 'details': res}

# --- 3. MENU KEYBOARD ---
def get_main_menu(): return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '🤖 Trợ lý AI'], ['⚙️ Hệ thống']], resize_keyboard=True)
def get_asset_menu(): return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_stats_menu(): return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_sys_menu(): return ReplyKeyboardMarkup([['💾 Backup DB', '♻️ Restore DB'], ['❓ Hướng dẫn', '🏠 Menu Chính']], resize_keyboard=True)

# --- 4. FORM LỊCH SỬ CHUẨN ---
def get_history_menu(page=None):
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY date DESC, id DESC").fetchall(); conn.close()
    if not rows: return "Chưa có giao dịch.", None
    PAGE_SIZE = 10
    kb = []
    if page is None:
        display, bd = rows[:10], "recent"; msg = "📜 10 GIAO DỊCH GẦN NHẤT\n\nClick để Sửa/Xóa:"
    else:
        start = page * PAGE_SIZE; display, bd = rows[start : start + PAGE_SIZE], str(page)
        total_p = (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE
        msg = f"📜 FULL LỊCH SỬ (Trang {page + 1}/{total_p})\n\nClick để Sửa/Xóa:"
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    for i, r in enumerate(display):
        btn_txt = f"{emojis[i] if i<10 else i+1}. {r[1]} | {r[2]} {format_money(r[3])} ({r[4]})"
        kb.append([InlineKeyboardButton(btn_txt, callback_data=f"hist_{r[0]}_{bd}")])
    if page is None: kb.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_page_0")])
    else:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"view_page_{page-1}"))
        if (page + 1) * PAGE_SIZE < len(rows): nav.append(InlineKeyboardButton("Sau ➡️", callback_data=f"view_page_{page+1}"))
        if nav: kb.append(nav)
        kb.append([InlineKeyboardButton("⬅️ Đóng", callback_data="back_to_recent")])
    return msg, InlineKeyboardMarkup(kb)

# --- 5. XỬ LÝ CHÍNH ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip(); state = context.user_data.get('state')

    # THÔNG BÁO CHÀO MỪNG START
    if text in ['/start', '🏠 Menu Chính']:
        context.user_data.clear()
        welcome = (
            "👋 **Chào mừng bạn đến với Portfolio Manager AI!**\n\n"
            "Tôi là trợ lý giúp bạn quản lý tài sản Crypto, Stock và Tiền mặt.\n\n"
            "🚀 **Bạn có thể:**\n"
            "- Xem tài sản chi tiết & lãi lỗ thực tế.\n"
            "- Theo dõi biểu đồ tăng trưởng vốn.\n"
            "- Hỏi **Trợ lý AI** để phân tích danh mục cá nhân.\n\n"
            "Hãy chọn một mục bên dưới để bắt đầu!"
        )
        await update.message.reply_text(welcome, parse_mode='Markdown', reply_markup=get_main_menu()); return

    # ĐIỀU HƯỚNG MENU
    if text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True))

    # XỬ LÝ TRỢ LÝ AI
    elif text == '🤖 Trợ lý AI':
        context.user_data['state'] = 'chatting_ai'
        await update.message.reply_text("🤖 **AI đã sẵn sàng!**\nBạn hãy đặt câu hỏi về danh mục hoặc thị trường (VD: 'Danh mục của tôi có ổn không?')")
        return

    if state == 'chatting_ai':
        if not GEMINI_KEY:
            await update.message.reply_text("⚠️ Bạn chưa cấu hình `GEMINI_API_KEY` trên Railway."); return
        s = get_stats()
        prompt = (f"Bạn là chuyên gia tài chính. Đây là dữ liệu người dùng:\n"
                  f"- Tổng tài sản: {format_money(s['total_val'])} VNĐ\n"
                  f"- Lãi/lỗ: {s['total_lai_pct']:.1f}%\n"
                  f"- Crypto: {format_money(s['details']['Crypto']['hien_co'])}\n"
                  f"- Stock: {format_money(s['details']['Stock']['hien_co'])}\n"
                  f"Câu hỏi: {text}")
        loading = await update.message.reply_text("⌛ AI đang phân tích...")
        try:
            response = ai_model.generate_content(prompt); await loading.delete()
            await update.message.reply_text(response.text, parse_mode='Markdown')
        except: await update.message.reply_text("❌ AI hiện đang bận, hãy thử lại sau.")
        return

    # TỔNG TÀI SẢN CHI TIẾT
    elif text == '💰 Xem Tổng Tài sản':
        s = get_stats(); d = s['details']
        msg = (f"🏆 *TỔNG TÀI SẢN*\n`{format_money(s['total_val'])}` VNĐ\n"
               f"{'📈' if s['total_lai']>=0 else '📉'} {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"🎯 Mục tiêu: {s['progress']:.1f}% (`{format_m(s['total_val'])}` / `{format_m(s['target_asset'])}`)\n"
               f"----------------------------------\n\n"
               f"🟡 *CRYPTO*\n💰 Hiện có: {format_money(d['Crypto']['hien_co'])}\n🏦 Vốn thực: {format_money(d['Crypto']['von'])}\n"
               f"📈 Lãi: {format_money(d['Crypto']['lai'])} ({d['Crypto']['pct']:.1f}%)\n\n"
               f"📈 *STOCK*\n💰 Hiện có: {format_money(d['Stock']['hien_co'])}\n🏦 Vốn thực: {format_money(d['Stock']['von'])}\n"
               f"📈 Lãi: {format_money(d['Stock']['lai'])} ({d['Stock']['pct']:.1f}%)\n\n"
               f"💵 *TIỀN MẶT*: {format_money(d['Cash']['hien_co'])}")
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif text == '📈 Biểu đồ':
        conn = sqlite3.connect(DB_FILE); txs = conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC").fetchall(); conn.close()
        if txs:
            daily = {}; s = get_stats()
            for ds, t, a in txs: daily[ds] = daily.get(ds, 0) + (a if t == 'Nạp' else -a)
            dates, caps, cur = [], [], 0
            for d_str in sorted(daily.keys()):
                cur += daily[d_str]; dates.append(datetime.datetime.strptime(d_str, "%Y-%m-%d")); caps.append(cur)
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.plot(dates, caps, color='#1f77b4', linewidth=2, label='Vốn thực nạp', marker='o', markersize=3)
            ax.fill_between(dates, caps, color='#1f77b4', alpha=0.15)
            color_t = '#2ecc71' if s['total_val'] >= caps[-1] else '#e74c3c'
            ax.plot([dates[-1], datetime.datetime.now()], [caps[-1], s['total_val']], label=f"Tài sản hiện có ({format_m(s['total_val'])})", color=color_t, marker='o', linestyle='--', linewidth=2)
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x/1000000:,.0f}M"))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
            ax.grid(True, linestyle='--', alpha=0.4); ax.legend(); ax.set_title("BIẾN ĐỘNG VỐN & TÀI SẢN")
            plt.xticks(rotation=45); plt.tight_layout()
            buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=120); plt.close(); buf.seek(0)
            await update.message.reply_photo(photo=buf, caption="📈 Chú thích:\n▫️ Đường Xanh: Vốn nạp ròng.\n▫️ Đường Đứt nét: Lãi/Lỗ hiện tại so với vốn.")

    elif text == '🥧 Phân bổ':
        s = get_stats(); d = s['details']
        labels = [l for l in ['Crypto', 'Stock', 'Cash'] if d[l]['hien_co'] > 0]
        vals = [d[l]['hien_co'] for l in labels]
        if vals:
            plt.figure(figsize=(6,6)); plt.pie(vals, labels=labels, autopct='%1.1f%%', startangle=90)
            buf = io.BytesIO(); plt.savefig(buf, format='png'); plt.close(); buf.seek(0)
            await update.message.reply_photo(photo=buf)

    elif text == '📜 Lịch sử':
        msg, mk = get_history_menu(); await update.message.reply_text(msg, reply_markup=mk)

    # NÚT HƯỚNG DẪN CHI TIẾT
    elif text == '❓ Hướng dẫn':
        guide = (
            "📘 **CẨM NANG SỬ DỤNG BOT**\n\n"
            "1️⃣ **Nhập số tiền:** Gõ `10tr`, `50m`, `1.5ty` hoặc `500k`.\n"
            "2️⃣ **Nạp/Rút:** Sau khi nhập, sẽ có nút **Hoàn tác** để xóa nếu nhầm.\n"
            "3️⃣ **Số dư:** Dùng 'Cập nhật số dư' để nhập giá trị thực tế trên sàn.\n"
            "4️⃣ **Mục tiêu:** Gõ 'Hòa vốn' hoặc 'Lãi 20%' để bot tự tính toán đích đến.\n"
            "5️⃣ **AI:** Nhấn 'Trợ lý AI' để chat trực tiếp với chuyên gia tài chính."
        )
        await update.message.reply_text(guide, parse_mode='Markdown')

    elif text == '💳 Quỹ Tiền mặt':
        d = get_stats()['details']['Cash']; await update.message.reply_text(f"💵 TIỀN MẶT\n💰 Số dư: {format_money(d['hien_co'])}\n📥 Nạp: {format_money(d['nap'])}\n📤 Rút: {format_money(d['rut'])}")
    elif text == '💾 Backup DB':
        if os.path.exists(DB_FILE): await update.message.reply_document(document=open(DB_FILE, 'rb'))

    # Xử lý State nhập liệu (Undo, Target, Balance)
    elif text == '🎯 Đặt Mục tiêu':
        context.user_data['state'] = 'awaiting_target'; await update.message.reply_text("🎯 Nhập đích đến (VD: Hòa vốn, Lãi 10%, 2 tỷ):")

    if state == 'awaiting_target':
        s = get_stats(); nt = None; text_l = text.lower()
        if 'hòa vốn' in text_l or 'hoà vốn' in text_l: nt = s['total_von']
        else:
            m = re.search(r'(lãi|lời|âm|lỗ)\s*([\d\.]+)\s*(%|tr|triệu|m|tỷ|ty|k)?', text_l)
            if m:
                dv = 1 if m.group(1) in ['lãi', 'lời'] else -1; v, u = float(m.group(2)), m.group(3)
                if u == '%': nt = s['total_von'] + (s['total_von'] * (dv * v / 100))
                else: nt = s['total_von'] + (dv * (parse_amount(f"{v}{u or ''}") or 0))
            else: nt = parse_amount(text)
        if nt:
            conn = sqlite3.connect(DB_FILE); conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_asset', ?)", (nt,)); conn.commit(); conn.close()
            context.user_data.clear(); await update.message.reply_text(f"✅ Mục tiêu mới: {format_money(nt)}", reply_markup=get_asset_menu())

    elif state in ['awaiting_nap', 'awaiting_rut']:
        amt = parse_amount(text)
        if amt:
            cat, t_type = context.user_data.get('category'), ('Nạp' if state == 'awaiting_nap' else 'Rút')
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            c.execute("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", (cat, t_type, amt, datetime.datetime.now().strftime("%Y-%m-%d")))
            tx_id = c.lastrowid; conn.commit(); conn.close(); context.user_data.clear()
            # NÚT UNDO CHO MỖI THAO TÁC
            kb = [[InlineKeyboardButton("↩️ Hoàn tác (Undo)", callback_data=f"undo_{tx_id}")]]
            await update.message.reply_text(f"✅ Đã ghi nhận {t_type} vào {cat}.", reply_markup=InlineKeyboardMarkup(kb))

    elif state and str(state).startswith('awaiting_balance_'):
        cat, amt = state.split("_")[2], parse_amount(text)
        if amt is not None:
            conn = sqlite3.connect(DB_FILE); conn.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amt)); conn.commit(); conn.close()
            context.user_data.clear(); await update.message.reply_text(f"✅ Cập nhật {cat} xong.", reply_markup=get_asset_menu())

    elif text == '💵 Cập nhật Số dư':
        await update.message.reply_text("Chọn mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"), InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]]))
    elif text in ['➕ Nạp tiền', '➖ Rút tiền']:
        a = 'nap' if 'Nạp' in text else 'rut'; await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{a}_Crypto"), InlineKeyboardButton("📈 Stock", callback_data=f"cat_{a}_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data=f"cat_{a}_Cash")]]))

# --- 6. CALLBACKS & RESTORE ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); d = q.data
    if d.startswith("undo_"):
        tx_id = d.split("_")[1]
        conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (tx_id,)); conn.commit(); conn.close()
        await q.edit_message_text("✅ Đã hoàn tác thành công!")
    elif d.startswith("hist_"):
        p = d.split("_"); tx_id, bd = p[1], p[2]
        kb = [[InlineKeyboardButton("✏️ Sửa", callback_data=f"edit_{tx_id}_{bd}"), InlineKeyboardButton("❌ Xóa", callback_data=f"del_{tx_id}_{bd}")], [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{bd}")]]
        await q.edit_message_text("Thao tác:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("edit_"):
        p = d.split("_"); context.user_data['state'] = f"awaiting_edit_{p[1]}_{p[2]}"; await q.edit_message_text("📝 Nhập số tiền mới:")
    elif d.startswith("del_"):
        p = d.split("_"); conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (p[1],)); conn.commit(); conn.close()
        pg = None if p[2] == "recent" else int(p[2]); m, mk = get_history_menu(pg); await q.edit_message_text("✅ Đã xóa.\n\n" + m, reply_markup=mk)
    elif d.startswith("view_page_"):
        m, mk = get_history_menu(int(d.split("_")[2])); await q.edit_message_text(m, reply_markup=mk)
    elif d == "back_to_recent" or d.startswith("back_view_"):
        m, mk = get_history_menu(); await q.edit_message_text(m, reply_markup=mk)
    elif d.startswith("bal_"):
        context.user_data['state'] = f"awaiting_balance_{d.split('_')[1]}"; await q.edit_message_text(f"Nhập số dư {d.split('_')[1]}:")
    elif d.startswith("cat_"):
        p = d.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]; await q.edit_message_text(f"Nhập tiền {p[1]} cho {p[2]}:")

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document.file_name == DB_FILE:
        f = await update.message.document.get_file(); await f.download_to_drive(DB_FILE); await update.message.reply_text("✅ Restore thành công!", reply_markup=get_main_menu())

def main():
    init_db(); app = Application.builder().token(os.environ.get("BOT_TOKEN")).build()
    app.add_handler(CommandHandler("start", handle_text)); app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc)); app.add_handler(CallbackQueryHandler(handle_callback)); app.run_polling()

if __name__ == '__main__': main()
