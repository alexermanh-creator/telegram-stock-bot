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
    
    # Logic nâng cấp DB cũ nếu chưa có cột note
    try:
        c.execute("ALTER TABLE transactions ADD COLUMN note TEXT")
    except sqlite3.OperationalError:
        pass

    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('target_asset', 500000000)")
    
    c.execute("SELECT COUNT(*) FROM transactions")
    if c.fetchone()[0] == 0 and INITIAL_TRANSACTIONS:
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", INITIAL_ASSETS)
        # SỬA LỖI: Thêm giá trị rỗng cho cột note để khớp 5 cột dữ liệu mẫu
        processed_tx = [(*t, "") for t in INITIAL_TRANSACTIONS]
        c.executemany("INSERT INTO transactions (category, type, amount, date, note) VALUES (?, ?, ?, ?, ?)", processed_tx)
    conn.commit()
    conn.close()

def format_m(amount): return f"{amount / 1000000:.1f}M" if amount != 0 else "0"
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
def get_sys_menu(): 
    return ReplyKeyboardMarkup([
        ['💾 Backup DB', '♻️ Restore DB'],
        ['📊 Xuất Excel', '❓ Hướng dẫn'],
        ['🏠 Menu Chính']
    ], resize_keyboard=True)

def get_history_menu(page=None):
    conn = sqlite3.connect(DB_FILE)
    rows = conn.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY date DESC, id DESC").fetchall(); conn.close()
    if not rows: return "Chưa có giao dịch.", None
    PAGE_SIZE = 10
    if page is None: display, bd, msg = rows[:10], "recent", "📜 10 GIAO DỊCH GẦN NHẤT\n\nClick để Sửa/Xóa:"
    else: start = page * PAGE_SIZE; display, bd, msg = rows[start:start+PAGE_SIZE], str(page), f"📜 LỊCH SỬ (Trang {page+1})"
    kb = []
    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    for i, r in enumerate(display): kb.append([InlineKeyboardButton(f"{emojis[i] if i<10 else i+1}. {r[1]} | {r[2]} {format_money(r[3])} ({r[4]})", callback_data=f"hist_{r[0]}_{bd}")])
    if page is None: kb.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_page_0")])
    else:
        nav = []
        if page > 0: nav.append(InlineKeyboardButton("⬅️ Trước", callback_data=f"view_page_{page-1}"))
        if (page+1)*PAGE_SIZE < len(rows): nav.append(InlineKeyboardButton("Sau ➡️", callback_data=f"view_page_{page+1}"))
        if nav: kb.append(nav)
        kb.append([InlineKeyboardButton("⬅️ Đóng", callback_data="back_to_recent")])
    return msg, InlineKeyboardMarkup(kb)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip(); state = context.user_data.get('state')

    if text in ['/start', '🏠 Menu Chính']:
        context.user_data.clear(); await update.message.reply_text("🏠 DASHBOARD CHÍNH", reply_markup=get_main_menu()); return

    elif text in ['/xoa_tri_nho', '🧹 Xóa trí nhớ AI']:
        portfolio_ai.chat_history = []
        await update.message.reply_text("🧹 Đã xóa sạch trí nhớ của AI! Bộ não đã được làm trống.")
        return

    if text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu())

    elif text == '💾 Backup DB':
        if os.path.exists(DB_FILE):
            await update.message.reply_document(document=open(DB_FILE, 'rb'), filename=DB_FILE, caption="📦 File Database dự phòng.")
        else: await update.message.reply_text("❌ Chưa có dữ liệu.")

    elif text == '♻️ Restore DB':
        await update.message.reply_text("🛠️ Gửi file `portfolio.db` để khôi phục.", parse_mode='Markdown')

    elif text == '📊 Xuất Excel':
        loading = await update.message.reply_text("⌛ Đang tạo báo cáo...")
        excel_file = reporter.export_excel_report()
        if excel_file:
            await loading.delete()
            await update.message.reply_document(document=excel_file, filename=f"Bao_Cao_{datetime.datetime.now().strftime('%d-%m-%Y')}.xlsx")
        else:
            await loading.delete()
            await update.message.reply_text("❌ Lỗi tạo báo cáo.")

    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True))

    elif text == '🤖 Trợ lý AI':
        context.user_data['state'] = 'chatting_ai'
        ai_menu = ReplyKeyboardMarkup([['🧹 Xóa trí nhớ AI', '🏠 Menu Chính']], resize_keyboard=True)
        await update.message.reply_text("🤖 AI đã sẵn sàng! Hãy gõ câu hỏi để tôi soi bảng tài sản.", reply_markup=ai_menu)
        return

    elif state == 'chatting_ai':
        s = get_stats(); d = s['details']
        loading = await update.message.reply_text("⌛ AI đang phân tích tài sản thực tế...")
        
        full_context = (
            f"BÁO CÁO TÀI SẢN CHI TIẾT:\n"
            f"- Tổng NAV hiện có: {format_money(s['total_val'])}đ\n"
            f"- Hiệu suất: {s['total_lai_pct']:.2f}% (Lãi: {format_money(s['total_lai'])}đ)\n"
            f"- Vốn nạp ròng: {format_money(s['total_von'])}đ\n"
            f"- Mục tiêu: {s['progress']:.1f}% đến mốc {format_money(s['target_asset'])}\n\n"
            f"DANH MỤC:\n"
            f"1. 🟡 CRYPTO: Hiện có {format_money(d['Crypto']['hien_co'])}, Vốn {format_money(d['Crypto']['von'])}, Lãi {d['Crypto']['pct']:.1f}%\n"
            f"2. 📈 STOCK: Hiện có {format_money(d['Stock']['hien_co'])}, Vốn {format_money(d['Stock']['von'])}, Lãi {d['Stock']['pct']:.1f}%\n"
            f"3. 💵 TIỀN MẶT: {format_money(d['Cash']['hien_co'])}đ"
        )
        try:
            reply = await portfolio_ai.get_advice(text, full_context)
            await loading.delete(); await update.message.reply_text(reply)
        except Exception as e:
            await loading.delete(); await update.message.reply_text(f"❌ Lỗi: {e}")
        return

    elif text == '💰 Xem Tổng Tài sản':
        s = get_stats(); d = s['details']
        msg = (f"🏆 *TỔNG TÀI SẢN*\n`{format_money(s['total_val'])}` VNĐ\n"
               f"{'📈' if s['total_lai']>=0 else '📉'} {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"🎯 Mục tiêu: {s['progress']:.1f}% (`{format_money(s['total_val'])} / {format_money(s['target_asset'])}`)\n"
               f"----------------------------------\n"
               f"🟡 *CRYPTO*: {format_money(d['Crypto']['hien_co'])} (Lãi {d['Crypto']['pct']:.1f}%)\n"
               f"📈 *STOCK*: {format_money(d['Stock']['hien_co'])} (Lãi {d['Stock']['pct']:.1f}%)\n"
               f"💵 *TIỀN MẶT*: {format_money(d['Cash']['hien_co'])}")
        await update.message.reply_text(msg, parse_mode='Markdown')

    elif text == '📈 Biểu đồ':
        conn = sqlite3.connect(DB_FILE); txs = conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC").fetchall(); conn.close()
        if txs:
            daily = {}; s = get_stats()
            for ds, t, a in txs: daily[ds] = daily.get(ds, 0) + (a if t == 'Nạp' else -a)
            dates, caps, cur = [], [], 0
            for d_str in sorted(daily.keys()): cur += daily[d_str]; dates.append(datetime.datetime.strptime(d_str, "%Y-%m-%d")); caps.append(cur)
            fig, ax = plt.subplots(figsize=(10, 5)); ax.plot(dates, caps, color='#1f77b4', label='Vốn ròng'); ax.fill_between(dates, caps, alpha=0.15)
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x/1000000:,.0f}M"))
            buf = io.BytesIO(); plt.savefig(buf, format='png'); plt.close(); buf.seek(0)
            await update.message.reply_photo(photo=buf)

    elif text == '🥧 Phân bổ':
        s = get_stats(); d = s['details']; labels = [l for l in ['Crypto', 'Stock', 'Cash'] if d[l]['hien_co'] > 0]; vals = [d[l]['hien_co'] for l in labels]
        if vals: plt.figure(figsize=(6,6)); plt.pie(vals, labels=labels, autopct='%1.1f%%'); buf = io.BytesIO(); plt.savefig(buf, format='png'); plt.close(); buf.seek(0); await update.message.reply_photo(photo=buf)

    elif text == '📜 Lịch sử': msg, mk = get_history_menu(); await update.message.reply_text(msg, reply_markup=mk)
    elif text == '💵 Cập nhật Số dư': await update.message.reply_text("Chọn tài sản:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"), InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]]))
    elif text in ['➕ Nạp tiền', '➖ Rút tiền']: a = 'nap' if 'Nạp' in text else 'rut'; await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{a}_Crypto"), InlineKeyboardButton("📈 Stock", callback_data=f"cat_{a}_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data=f"cat_{a}_Cash")]]))
    elif text == '💳 Quỹ Tiền mặt': d = get_stats()['details']['Cash']; await update.message.reply_text(f"💵 TIỀN MẶT: {format_money(d['hien_co'])}")
    
    elif text == '🎯 Đặt Mục tiêu': context.user_data['state'] = 'awaiting_target'; await update.message.reply_text("🎯 Nhập mục tiêu (số tiền VNĐ):")
    elif state == 'awaiting_target':
        nt = parse_amount(text)
        if nt: 
            conn = sqlite3.connect(DB_FILE); conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_asset', ?)", (nt,)); conn.commit(); conn.close()
            await update.message.reply_text(f"✅ Đã đặt mục tiêu: {format_money(nt)}", reply_markup=get_asset_menu())
        context.user_data.clear()

    # NÂNG CẤP: Quy trình Nhập tiền -> Hỏi Ghi chú
    elif state in ['awaiting_nap', 'awaiting_rut']:
        amt = parse_amount(text)
        if amt:
            context.user_data['temp_amt'] = amt
            context.user_data['prev_state'] = state
            context.user_data['state'] = 'awaiting_note'
            await update.message.reply_text("📝 Nhập ghi chú mục đích (Gõ '.' để bỏ qua):")
        return

    elif state == 'awaiting_note':
        amt = context.user_data.get('temp_amt')
        cat = context.user_data.get('category')
        t_type = 'Nạp' if context.user_data.get('prev_state') == 'awaiting_nap' else 'Rút'
        note = "" if text == "." else text
        conn = sqlite3.connect(DB_FILE); c = conn.cursor()
        c.execute("INSERT INTO transactions (category, type, amount, date, note) VALUES (?, ?, ?, ?, ?)", 
                  (cat, t_type, amt, datetime.datetime.now().strftime("%Y-%m-%d"), note))
        tx_id = c.lastrowid; conn.commit(); conn.close()
        context.user_data.clear()
        await update.message.reply_text(f"✅ Đã lưu {t_type} {format_money(amt)} vào {cat}.\n📝 Ghi chú: {note if note else 'Trống'}", 
                                       reply_markup=get_main_menu())
        return

    elif state and state.startswith('awaiting_balance_'):
        cat, amt = state.split("_")[2], parse_amount(text)
        if amt is not None:
            conn = sqlite3.connect(DB_FILE); conn.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES ('Cash', ?)", (amt,)); conn.commit(); conn.close()
            await update.message.reply_text(f"✅ Cập nhật {cat} xong.", reply_markup=get_asset_menu())
        context.user_data.clear()

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); d = q.data
    if d.startswith("undo_"):
        conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (d.split("_")[1],)); conn.commit(); conn.close()
        await q.edit_message_text("✅ Đã hoàn tác!")
    elif d.startswith("hist_"):
        p = d.split("_"); tx_id, bd = p[1], p[2]
        kb = [[InlineKeyboardButton("❌ Xóa", callback_data=f"del_{tx_id}_{bd}"), InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{bd}")]]; 
        await q.edit_message_text("Thao tác:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("del_"):
        p = d.split("_"); conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (p[1],)); conn.commit(); conn.close()
        m, mk = get_history_menu(None if p[2] == "recent" else int(p[2]))
        await q.edit_message_text("✅ Đã xóa.\n" + m, reply_markup=mk)
    elif d.startswith("view_page_"): m, mk = get_history_menu(int(d.split("_")[2])); await q.edit_message_text(m, reply_markup=mk)
    elif d == "back_to_recent" or d.startswith("back_view_"): m, mk = get_history_menu(); await q.edit_message_text(m, reply_markup=mk)
    elif d.startswith("bal_"): context.user_data['state'] = f"awaiting_balance_{d.split('_')[1]}"; await q.edit_message_text(f"Nhập số dư {d.split('_')[1]}:")
    elif d.startswith("cat_"): 
        p = d.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]
        await q.edit_message_text(f"Nhập số tiền {p[1]} cho {p[2]}:")

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.document.file_name == DB_FILE:
        f = await update.message.document.get_file(); await f.download_to_drive(DB_FILE)
        await update.message.reply_text("✅ Restore thành công!", reply_markup=get_main_menu())

def main():
    init_db(); token = os.environ.get("BOT_TOKEN")
    if not token: return
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler(["start", "xoa_tri_nho"], handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == '__main__': main()
