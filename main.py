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

# --- CẤU HÌNH HỆ THỐNG ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
DB_FILE = 'portfolio.db'
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# --- FIX LỖI 404 AI ---
if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        # Sử dụng model name ngắn gọn nhất để SDK tự khớp API v1
        ai_model = genai.GenerativeModel('gemini-1.5-flash')
    except Exception as e:
        logging.error(f"Khởi tạo AI thất bại: {e}")

# --- 1. KHỞI TẠO DATABASE (GIỮ NGUYÊN GỐC ỔN ĐỊNH) ---
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
    if c.fetchone()[0] == 0:
        # Nếu DB trống mới nạp dữ liệu mẫu của bạn
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", 
                      [('Crypto', 20000000), ('Stock', 123000000), ('Cash', 0)])
    conn.commit()
    conn.close()

# --- 2. HÀM HỖ TRỢ TÍNH TOÁN ---
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

    res = {}
    tv, tn, trut = 0, 0, 0
    for cat in ['Crypto', 'Stock', 'Cash']:
        hc = assets.get(cat, 0)
        nap, rut = s[cat]['Nạp'], s[cat]['Rút']
        von = nap - rut
        lai = hc - von
        res[cat] = {
            'hien_co': hc, 'nap': nap, 'rut': rut, 'von': von, 
            'lai': lai, 'pct': (lai / von * 100) if von != 0 else 0
        }
        tv += hc; tn += nap; trut += rut

    tvon = tn - trut
    tlai = tv - tvon
    return {
        'total_val': tv, 'total_von': tvon, 'total_lai': tlai, 
        'total_lai_pct': (tlai / tvon * 100) if tvon != 0 else 0,
        'total_nap': tn, 'total_rut': trut, 'target_asset': target_asset, 
        'progress': (tv / target_asset * 100) if target_asset > 0 else 0,
        'details': res
    }

# --- 3. GIAO DIỆN MENU ---
def get_main_menu(): return ReplyKeyboardMarkup([['🏦 Quản lý Tài sản', '💸 Giao dịch'], ['📊 Thống kê', '🤖 Trợ lý AI'], ['⚙️ Hệ thống']], resize_keyboard=True)
def get_asset_menu(): return ReplyKeyboardMarkup([['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'], ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'], ['🏠 Menu Chính']], resize_keyboard=True)
def get_stats_menu(): return ReplyKeyboardMarkup([['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'], ['🏠 Menu Chính']], resize_keyboard=True)

# --- 4. XỬ LÝ TEXT & AI ---
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip(); state = context.user_data.get('state')

    if text in ['/start', '🏠 Menu Chính']:
        context.user_data.clear()
        await update.message.reply_text("👋 Chào mừng bạn! Hãy chọn tính năng bên dưới:", reply_markup=get_main_menu()); return

    # --- TỔNG TÀI SẢN CHI TIẾT (GIỮ NGUYÊN BẢN ỔN ĐỊNH) ---
    if text == '💰 Xem Tổng Tài sản':
        s = get_stats(); d = s['details']
        msg = (f"🏆 *TỔNG TÀI SẢN*\n`{format_money(s['total_val'])}` VNĐ\n"
               f"{'📈' if s['total_lai']>=0 else '📉'} {format_money(s['total_lai'])} ({s['total_lai_pct']:.1f}%)\n"
               f"🎯 Mục tiêu: {s['progress']:.1f}% (`{format_money(s['total_val'])} / {format_money(s['target_asset'])}`)\n"
               f"----------------------------------\n"
               f"📤 Tổng nạp: {format_money(s['total_nap'])}\n📥 Tổng rút: {format_money(s['total_rut'])}\n"
               f"----------------------------------\n\n"
               f"🟡 *CRYPTO*\n💰 Hiện có: {format_money(d['Crypto']['hien_co'])}\n🏦 Vốn thực: {format_money(d['Crypto']['von'])}\n"
               f"📤 Nạp: {format_money(d['Crypto']['nap'])} | 📥 Rút: {format_money(d['Crypto']['rut'])}\n"
               f"📈 Lãi/Lỗ: {format_money(d['Crypto']['lai'])} ({d['Crypto']['pct']:.1f}%)\n\n"
               f"📈 *STOCK*\n💰 Hiện có: {format_money(d['Stock']['hien_co'])}\n🏦 Vốn thực: {format_money(d['Stock']['von'])}\n"
               f"📤 Nạp: {format_money(d['Stock']['nap'])} | 📥 Rút: {format_money(d['Stock']['rut'])}\n"
               f"📈 Lãi/Lỗ: {format_money(d['Stock']['lai'])} ({d['Stock']['pct']:.1f}%)\n\n"
               f"💵 *TIỀN MẶT*: {format_money(d['Cash']['hien_co'])}")
        await update.message.reply_text(msg, parse_mode='Markdown'); return

    # --- XỬ LÝ AI CHỐNG LỖI 404 ---
    elif text == '🤖 Trợ lý AI':
        context.user_data['state'] = 'chatting_ai'
        await update.message.reply_text("🤖 AI đã sẵn sàng! Hãy hỏi tôi về danh mục đầu tư của bạn:"); return

    if state == 'chatting_ai':
        if not GEMINI_KEY:
            await update.message.reply_text("⚠️ Chưa cấu hình API Key trên Railway."); return
        s = get_stats()
        prompt = (f"Bạn là chuyên gia tài chính. Dữ liệu thực tế: Tổng TS {format_money(s['total_val'])}, "
                  f"Lãi {s['total_lai_pct']:.1f}%. Crypto {format_money(s['details']['Crypto']['hien_co'])}, "
                  f"Stock {format_money(s['details']['Stock']['hien_co'])}. Trả lời ngắn gọn câu hỏi: {text}")
        loading = await update.message.reply_text("⌛ AI đang phân tích dữ liệu...")
        try:
            # Dùng asyncio.to_thread để không làm treo bot khi chờ AI
            response = await asyncio.to_thread(ai_model.generate_content, prompt)
            await loading.delete()
            await update.message.reply_text(response.text, parse_mode='Markdown')
        except Exception as e:
            await loading.delete()
            # Báo lỗi chi tiết để debug nếu Google vẫn từ chối
            await update.message.reply_text(f"❌ Lỗi kết nối AI: {str(e)}")
        return

    # --- ĐIỀU HƯỚNG CÁC MỤC KHÁC ---
    if text == '🏦 Quản lý Tài sản': await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN", reply_markup=get_asset_menu())
    elif text == '📊 Thống kê': await update.message.reply_text("📊 THỐNG KÊ", reply_markup=get_stats_menu())
    elif text == '💸 Giao dịch': await update.message.reply_text("💸 GIAO DỊCH", reply_markup=ReplyKeyboardMarkup([['➕ Nạp tiền', '➖ Rút tiền'], ['🏠 Menu Chính']], resize_keyboard=True))
    elif text == '⚙️ Hệ thống': await update.message.reply_text("⚙️ HỆ THỐNG", reply_markup=ReplyKeyboardMarkup([['💾 Backup DB', '♻️ Restore DB'], ['❓ Hướng dẫn', '🏠 Menu Chính']], resize_keyboard=True))

    # --- BIỂU ĐỒ (GIỮ NGUYÊN BẢN ỔN ĐỊNH) ---
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
            ax.plot([dates[-1], datetime.datetime.now()], [caps[-1], s['total_val']], label=f"Tài sản hiện có", color=color_t, marker='o', linestyle='--', linewidth=2)
            ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, p: f"{x/1000000:,.0f}M"))
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
            ax.grid(True, linestyle='--', alpha=0.4); ax.legend()
            buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=120); plt.close(); buf.seek(0)
            await update.message.reply_photo(photo=buf)

# --- 5. KHỞI CHẠY BOT ---
def main():
    init_db(); token = os.environ.get("BOT_TOKEN")
    if not token: return
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", handle_text))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    # Note: CallbackQueryHandler for Undo, History Edit should be added here similarly to your stable version
    app.run_polling()

if __name__ == '__main__': main()
