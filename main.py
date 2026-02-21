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
from stock_manager import stock_manager
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
    
    # 1. Tạo các bảng cơ bản của hệ thống
    c.execute('''CREATE TABLE IF NOT EXISTS assets (category TEXT PRIMARY KEY, current_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, type TEXT, amount REAL, date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value REAL)''')
    
    # 2. Tạo các bảng dành riêng cho MODULE CHỨNG KHOÁN (Khớp với Demo)
    c.execute('''CREATE TABLE IF NOT EXISTS stock_holdings 
                 (symbol TEXT PRIMARY KEY, qty INTEGER, avg_price REAL, total_cost REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stock_orders 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, type TEXT, 
                  qty INTEGER, price REAL, fee REAL, date TEXT)''')

    # 3. Khởi tạo mục tiêu tài sản mặc định
    c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('target_asset', 500000000)")
    
    # 4. Kiểm tra và nạp dữ liệu ban đầu từ data.py (chỉ nạp nếu DB trống)
    c.execute("SELECT COUNT(*) FROM transactions")
    if c.fetchone()[0] == 0:
        if INITIAL_ASSETS:
            c.executemany("INSERT OR IGNORE INTO assets (category, current_value) VALUES (?, ?)", INITIAL_ASSETS)
        if INITIAL_TRANSACTIONS:
            c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", INITIAL_TRANSACTIONS)
        
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
def get_asset_menu(): 
    return ReplyKeyboardMarkup([
        ['💰 Xem Tổng Tài sản', '📈 Chứng khoán'], 
        ['💵 Cập nhật Số dư', '💳 Quỹ Tiền mặt'], 
        ['🎯 Đặt Mục tiêu', '🏠 Menu Chính']
    ], resize_keyboard=True)

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

    elif text == '📈 Chứng khoán':
        s = get_stats()
        d = s['details'].get('Stock', {'hien_co': 0, 'nap': 0})
        
        if d['hien_co'] == 0 and d['nap'] == 0:
            msg = (
                "👋 **CHÀO MỪNG BẠN ĐẾN VỚI CHỨNG KHOÁN**\n\n"
                "Bạn chưa có dữ liệu tài khoản.\n"
                "Hãy bắt đầu bằng cách nộp tiền để thực hiện giao dịch."
            )
            kb = [
                [InlineKeyboardButton("💵 Nộp tiền Stock", callback_data="cat_nap_Stock")],
                [InlineKeyboardButton("📂 Import dữ liệu", callback_data="stock_import")],
                [InlineKeyboardButton("❓ Hướng dẫn", callback_data="stock_help")]
            ]
        else:
            summary = stock_manager.get_portfolio_summary()
            msg = (
                "📊 **TÀI KHOẢN CHỨNG KHOÁN**\n\n"
                f"💰 **Tổng tài sản:** {format_money(summary['nav'])}đ\n"
                f"💵 **Tiền mặt:** {format_money(summary['cash'])}đ\n"
                f"📈 **Giá trị cổ phiếu:** {format_money(summary['stock_value'])}đ\n"
                f"💹 **Lãi/Lỗ:** 0% (Dựa trên giá vốn)"
            )
            kb = [
                [InlineKeyboardButton("➕ Giao dịch", callback_data="stock_trade"),
                 InlineKeyboardButton("📂 Danh mục", callback_data="stock_holdings")],
                [InlineKeyboardButton("📊 Phân tích", callback_data="stock_analysis"),
                 InlineKeyboardButton("📜 Lịch sử", callback_data="stock_history")],
                [InlineKeyboardButton("⬅️ Quay lại Menu chính", callback_data="back_to_main")]
            ]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(kb), parse_mode='Markdown')
        return

    elif text in ['/xoa_tri_nho', '🧹 Xóa trí nhớ AI']:
        portfolio_ai.chat_history = []
        await update.message.reply_text("🧹 Đã xóa sạch trí nhớ của AI! Hãy bắt đầu lại nhé.")
        return

    if text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=get_sys_menu())
    elif text == '💾 Backup DB':
        if os.path.exists(DB_FILE): await update.message.reply_document(document=open(DB_FILE, 'rb'), filename=DB_FILE, caption="📦 File Database dự phòng.")
        else: await update.message.reply_text("❌ Chưa có dữ liệu.")
    elif text == '♻️ Restore DB': await update.message.reply_text("🛠️ Gửi file `portfolio.db` để khôi phục.")
    elif text == '📊 Xuất Excel':
        loading = await update.message.reply_text("⌛ Đang vẽ biểu đồ...")
        excel_file = reporter.export_excel_report()
        await loading.delete()
        if excel_file: await update.message.reply_document(document=excel_file, filename="Bao_Cao.xlsx")
        else: await update.message.reply_text("❌ Lỗi tạo báo cáo.")
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True))
    elif text == '🤖 Trợ lý AI':
        context.user_data['state'] = 'chatting_ai'
        await update.message.reply_text("🤖 AI đã sẵn sàng!", reply_markup=ReplyKeyboardMarkup([['🧹 Xóa trí nhớ AI', '🏠 Menu Chính']], resize_keyboard=True))
    elif state == 'chatting_ai':
        loading = await update.message.reply_text("⌛ AI đang phân tích...")
        reply = await portfolio_ai.get_advice(text, get_stats())
        await loading.delete(); await update.message.reply_text(reply)
    elif text == '💰 Xem Tổng Tài sản':
        s = get_stats(); d = s['details']
        msg = (f"🏆 *TỔNG TÀI SẢN*\n`{format_money(s['total_val'])}` VNĐ\n"
               f"📈 Lãi/Lỗ: {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"📈 *STOCK*\n💰 Hiện có: {format_money(d['Stock']['hien_co'])}")
        await update.message.reply_text(msg, parse_mode='Markdown')
    elif text == '📈 Biểu đồ':
        conn = sqlite3.connect(DB_FILE); txs = conn.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC").fetchall(); conn.close()
        if txs:
            daily = {}; s = get_stats()
            for ds, t, a in txs: daily[ds] = daily.get(ds, 0) + (a if t == 'Nạp' else -a)
            dates, caps, cur = [], [], 0
            for d_str in sorted(daily.keys()): cur += daily[d_str]; dates.append(datetime.datetime.strptime(d_str, "%Y-%m-%d")); caps.append(cur)
            fig, ax = plt.subplots(figsize=(10, 5)); ax.plot(dates, caps, marker='o'); buf = io.BytesIO(); plt.savefig(buf, format='png'); plt.close(); buf.seek(0)
            await update.message.reply_photo(photo=buf)
    elif text == '🥧 Phân bổ':
        s = get_stats(); d = s['details']; labels = [l for l in ['Crypto', 'Stock', 'Cash'] if d[l]['hien_co'] > 0]; vals = [d[l]['hien_co'] for l in labels]
        if vals: plt.figure(figsize=(6,6)); plt.pie(vals, labels=labels, autopct='%1.1f%%'); buf = io.BytesIO(); plt.savefig(buf, format='png'); plt.close(); buf.seek(0); await update.message.reply_photo(photo=buf)
    elif text == '📜 Lịch sử': msg, mk = get_history_menu(); await update.message.reply_text(msg, reply_markup=mk)
    elif text == '💵 Cập nhật Số dư': await update.message.reply_text("Chọn tài sản:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"), InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]]))
    elif text in ['➕ Nạp tiền', '➖ Rút tiền']: a = 'nap' if 'Nạp' in text else 'rut'; await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{a}_Crypto"), InlineKeyboardButton("📈 Stock", callback_data=f"cat_{a}_Stock")], [InlineKeyboardButton("💵 Tiền mặt", callback_data=f"cat_{a}_Cash")]]))
    elif text == '🎯 Đặt Mục tiêu': context.user_data['state'] = 'awaiting_target'; await update.message.reply_text("🎯 Nhập mục tiêu:")
    elif state == 'awaiting_target':
        nt = parse_amount(text)
        if nt: 
            conn = sqlite3.connect(DB_FILE); conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_asset', ?)", (nt,)); conn.commit(); conn.close()
            await update.message.reply_text(f"✅ Mục tiêu: {format_money(nt)}", reply_markup=get_asset_menu())
    elif state and state.startswith('awaiting_balance_'):
        cat, amt = state.split("_")[2], parse_amount(text)
        if amt is not None:
            conn = sqlite3.connect(DB_FILE); conn.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amt)); conn.commit(); conn.close()
            await update.message.reply_text(f"✅ Đã cập nhật {cat}.", reply_markup=get_asset_menu())
    elif state in ['awaiting_nap', 'awaiting_rut']:
        amt = parse_amount(text)
        if amt is not None:
            cat, t_type = context.user_data.get('category'), ('Nạp' if state == 'awaiting_nap' else 'Rút')
            conn = sqlite3.connect(DB_FILE); c = conn.cursor(); c.execute("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", (cat, t_type, amt, datetime.datetime.now().strftime("%Y-%m-%d"))); tx_id = c.lastrowid; conn.commit(); conn.close()
            await update.message.reply_text(f"✅ Đã ghi nhận {t_type} vào {cat}.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Hoàn tác", callback_data=f"undo_{tx_id}")]]))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; await q.answer(); d = q.data
    if d == "back_to_main":
        await q.edit_message_text("🏠 DASHBOARD CHÍNH (Quay lại từ Stock)")
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Chọn tính năng:", reply_markup=get_main_menu())
    elif d.startswith("undo_"):
        conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (d.split("_")[1],)); conn.commit(); conn.close()
        await q.edit_message_text("✅ Đã hoàn tác!")
    elif d.startswith("hist_"):
        p = d.split("_"); tx_id, bd = p[1], p[2]
        kb = [[InlineKeyboardButton("✏️ Sửa", callback_data=f"edit_{tx_id}_{bd}"), InlineKeyboardButton("❌ Xóa", callback_data=f"del_{tx_id}_{bd}")], [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{bd}")]]
        await q.edit_message_text("Thao tác:", reply_markup=InlineKeyboardMarkup(kb))
    elif d.startswith("edit_"): context.user_data['state'] = f"awaiting_edit_{d.split('_')[1]}_{d.split('_')[2]}"; await q.edit_message_text("📝 Nhập số tiền mới:")
    elif d.startswith("del_"):
        conn = sqlite3.connect(DB_FILE); conn.execute("DELETE FROM transactions WHERE id = ?", (d.split("_")[1],)); conn.commit(); conn.close()
        await q.edit_message_text("✅ Đã xóa.")
    elif d.startswith("view_page_"): m, mk = get_history_menu(int(d.split("_")[2])); await q.edit_message_text(m, reply_markup=mk)
    elif d.startswith("bal_"): context.user_data['state'] = f"awaiting_balance_{d.split('_')[1]}"; await q.edit_message_text(f"Nhập số dư {d.split('_')[1]}:")
    elif d.startswith("cat_"): p = d.split("_"); context.user_data['state'], context.user_data['category'] = f"awaiting_{p[1]}", p[2]; await q.edit_message_text(f"Nhập tiền {p[1]} cho {p[2]}:")

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
