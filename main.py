import os
import sqlite3
import logging
import datetime
import io
import matplotlib.pyplot as plt
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

# --- 1. KHỞI TẠO DATABASE ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (category TEXT PRIMARY KEY, current_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, type TEXT, amount REAL, date TEXT)''')
    
    c.execute("SELECT COUNT(*) FROM assets")
    if c.fetchone()[0] == 0:
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", 
                      [('Crypto', 20000000), ('Stock', 123000000)])
        c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", [
            ('Crypto', 'Nạp', 348500000, '2024-01-01'),
            ('Crypto', 'Rút', 250500000, '2024-01-02'),
            ('Stock', 'Nạp', 267300000, '2024-01-01'),
            ('Stock', 'Rút', 156500000, '2024-01-02')
        ])
    conn.commit()
    conn.close()

# --- 2. HÀM HỖ TRỢ ---
def format_m(amount):
    return f"{amount / 1000000:.1f}M" if amount != 0 else "0"

def format_money(amount):
    return f"{int(amount):,}"

def get_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT category, current_value FROM assets")
    assets = {row[0]: row[1] for row in c.fetchall()}
    c.execute("SELECT category, type, SUM(amount) FROM transactions GROUP BY category, type")
    txs = c.fetchall()
    conn.close()

    stats = {'Crypto': {'Nạp': 0, 'Rút': 0}, 'Stock': {'Nạp': 0, 'Rút': 0}}
    for cat, t_type, amt in txs:
        if cat in stats:
            stats[cat][t_type] = amt

    c_hien_co = assets.get('Crypto', 0)
    s_hien_co = assets.get('Stock', 0)
    
    c_nap, c_rut = stats['Crypto']['Nạp'], stats['Crypto']['Rút']
    s_nap, s_rut = stats['Stock']['Nạp'], stats['Stock']['Rút']
    
    c_von = c_nap - c_rut
    s_von = s_nap - s_rut
    c_lai = c_hien_co - c_von
    s_lai = s_hien_co - s_von
    
    c_lai_pct = (c_lai / c_von * 100) if c_von > 0 else 0
    s_lai_pct = (s_lai / s_von * 100) if s_von > 0 else 0
    
    tong_tai_san = c_hien_co + s_hien_co
    tong_nap = c_nap + s_nap
    tong_rut = c_rut + s_rut
    tong_von = tong_nap - tong_rut
    tong_lai = tong_tai_san - tong_von
    tong_lai_pct = (tong_lai / tong_von * 100) if tong_von > 0 else 0

    return {
        'tong_tai_san': tong_tai_san, 'tong_lai': tong_lai, 'tong_lai_pct': tong_lai_pct,
        'tong_nap': tong_nap, 'tong_rut': tong_rut,
        'c_hien_co': c_hien_co, 'c_von': c_von, 'c_nap': c_nap, 'c_rut': c_rut, 'c_lai': c_lai, 'c_lai_pct': c_lai_pct,
        's_hien_co': s_hien_co, 's_von': s_von, 's_nap': s_nap, 's_rut': s_rut, 's_lai': s_lai, 's_lai_pct': s_lai_pct
    }

def get_main_keyboard():
    keyboard = [
        ['💰 Tài sản', '📜 Lịch sử'],
        ['💵 Tài sản hiện có', '💳 Tiền mặt'],
        ['➕ Nạp thêm', '➖ Rút ra'],
        ['📊 Biểu đồ', '🥧 Phân bổ'],
        ['💾 Backup', '♻️ Restore'],
        ['⚙️ Cài đặt', '❓ Hướng dẫn']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_recent_history_menu():
    """Hàm tạo danh sách 10 giao dịch gần nhất dạng nút bấm"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY id DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()

    if not rows:
        return "Chưa có giao dịch nào.", None

    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    keyboard = []
    msg = "📜 LỊCH SỬ GIAO DỊCH\n\nClick 1 giao dịch:"
    
    for i, row in enumerate(rows):
        emoji = emojis[i] if i < 10 else f"{i+1}."
        btn_text = f"{emoji} {row[1]} — {row[2]} — {format_money(row[3])} — {row[4]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"hist_{row[0]}")])
        
    keyboard.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_full_hist")])
    return msg, InlineKeyboardMarkup(keyboard)

# --- 3. XỬ LÝ LỆNH TỪ BÀN PHÍM ---
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    stats = get_stats()
    text = (
        f"👋 Chào bạn\n\n"
        f"💰 Tổng tài sản: {format_m(stats['tong_tai_san'])}\n"
        f"📉 Lãi/Lỗ: {format_money(stats['tong_lai'])} ({stats['tong_lai_pct']:.1f}%)\n\n"
        f"Bạn chọn chức năng bên dưới 👇"
    )
    context.user_data.clear()
    await update.message.reply_text(text, reply_markup=get_main_keyboard())

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    menu_buttons = ['💰 Tài sản', '📜 Lịch sử', '💵 Tài sản hiện có', '💳 Tiền mặt', 
                    '➕ Nạp thêm', '➖ Rút ra', '📊 Biểu đồ', '🥧 Phân bổ', 
                    '💾 Backup', '♻️ Restore', '⚙️ Cài đặt', '❓ Hướng dẫn']
    if text in menu_buttons:
        context.user_data.clear()

    # --- KIỂM TRA TRẠNG THÁI NHẬP LIỆU ---
    state = context.user_data.get('state')
    
    if state == 'awaiting_assets':
        try:
            parts = text.lower().split()
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            for i in range(0, len(parts), 2):
                cat = parts[i].capitalize()
                val = float(parts[i+1])
                c.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, val))
            conn.commit()
            conn.close()
            context.user_data.clear()
            await update.message.reply_text("✅ Đã cập nhật tài sản hiện có")
        except Exception:
            await update.message.reply_text("⚠️ Sai cú pháp. Ví dụ:\ncrypto 20000000\nstock 123000000")
        return

    elif state in ['awaiting_nap', 'awaiting_rut']:
        try:
            amount = float(text)
            cat = context.user_data.get('category')
            tx_type = 'Nạp' if state == 'awaiting_nap' else 'Rút'
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", 
                      (cat, tx_type, amount, date_str))
            conn.commit()
            conn.close()
            context.user_data.clear()
            await update.message.reply_text(f"✅ Đã ghi nhận {tx_type} {format_money(amount)} vào {cat}.")
        except ValueError:
            await update.message.reply_text("⚠️ Vui lòng nhập số tiền hợp lệ:")
        return

    # Xử lý khi user đang nhập số tiền mới để SỬA lịch sử
    elif state and str(state).startswith('awaiting_edit_'):
        try:
            new_amount = float(text)
            tx_id = state.split("_")[2]
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE transactions SET amount = ? WHERE id = ?", (new_amount, tx_id))
            conn.commit()
            conn.close()
            context.user_data.clear()
            
            # Sau khi sửa xong, hiển thị lại list 10 giao dịch
            msg, markup = get_recent_history_menu()
            await update.message.reply_text(f"✅ Đã cập nhật thành {format_money(new_amount)}.\n\n{msg}", reply_markup=markup)
        except ValueError:
            await update.message.reply_text("⚠️ Vui lòng nhập số tiền hợp lệ (ví dụ: 15000000):")
        return

    # --- MENU CHÍNH ---
    if text == '💰 Tài sản':
        s = get_stats()
        t_ts = s['tong_tai_san']
        c_pct = (s['c_hien_co'] / t_ts * 100) if t_ts > 0 else 0
        s_pct = (s['s_hien_co'] / t_ts * 100) if t_ts > 0 else 0

        reply = (
            f"🏆 TỔNG TÀI SẢN\n"
            f"{format_m(s['tong_tai_san'])}\n"
            f"{'📈' if s['tong_lai'] >= 0 else '📉'} {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)\n\n"
            f"📥 Tổng nạp: {format_m(s['tong_nap'])}\n"
            f"📤 Tổng rút: {format_m(s['tong_rut'])}\n\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"🌕 CRYPTO ({c_pct:.0f}%)\n"
            f"💰 Tài sản hiện có: {format_m(s['c_hien_co'])}\n"
            f"🏦 Vốn thực: {format_m(s['c_von'])}\n\n"
            f"📥 Nạp: {format_m(s['c_nap'])}\n"
            f"📤 Rút: {format_m(s['c_rut'])}\n\n"
            f"{'📈' if s['c_lai'] >= 0 else '📉'} Lãi/Lỗ: {format_money(s['c_lai'])} ({s['c_lai_pct']:.1f}%)\n\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"📈 STOCK ({s_pct:.0f}%)\n"
            f"💰 Tài sản hiện có: {format_m(s['s_hien_co'])}\n"
            f"🏦 Vốn thực: {format_m(s['s_von'])}\n\n"
            f"📥 Nạp: {format_m(s['s_nap'])}\n"
            f"📤 Rút: {format_m(s['s_rut'])}\n\n"
            f"{'📈' if s['s_lai'] >= 0 else '📉'} Lãi/Lỗ: {format_m(s['s_lai'])} ({s['s_lai_pct']:.1f}%)\n\n"
            f"━━━━━━━━━━━━━━\n\n"
            f"💵 Tiền mặt: 0"
        )
        await update.message.reply_text(reply)

    elif text == '💵 Tài sản hiện có':
        context.user_data['state'] = 'awaiting_assets'
        await update.message.reply_text("Nhập tài sản hiện có:\n\nVí dụ:\ncrypto 20000000\nstock 123000000")

    elif text in ['➕ Nạp thêm', '➖ Rút ra']:
        action = 'nap' if 'Nạp' in text else 'rut'
        keyboard = [
            [InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{action}_Crypto")],
            [InlineKeyboardButton("📈 Stock", callback_data=f"cat_{action}_Stock")]
        ]
        await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == '📜 Lịch sử':
        msg, markup = get_recent_history_menu()
        if markup:
            await update.message.reply_text(msg, reply_markup=markup)
        else:
            await update.message.reply_text(msg)

    elif text == '🥧 Phân bổ':
        s = get_stats()
        fig, ax = plt.subplots(figsize=(5,5))
        sizes = [s['c_hien_co'], s['s_hien_co']]
        if sum(sizes) == 0:
            await update.message.reply_text("Tài sản đang trống.")
            return
        ax.pie(sizes, labels=['Crypto', 'Stock'], autopct='%1.1f%%', startangle=90, colors=['#f39c12', '#3498db'])
        ax.axis('equal')  
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        c_pct = (s['c_hien_co'] / sum(sizes)) * 100
        s_pct = (s['s_hien_co'] / sum(sizes)) * 100
        await update.message.reply_photo(photo=buf, caption=f"Crypto: {c_pct:.0f}%\nStock: {s_pct:.0f}%")

    elif text == '📊 Biểu đồ':
        fig, ax = plt.subplots(figsize=(8,4))
        ax.plot(['Tháng 1', 'Tháng 2', 'Tháng 3'], [90, 110, 143], marker='o', color='green')
        ax.set_title("Biểu đồ tăng trưởng tài sản theo thời gian\nROI: -31.5%")
        ax.grid(True)
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        await update.message.reply_photo(photo=buf, caption="Biểu đồ tăng trưởng tài sản theo thời gian\nROI %")

    elif text == '💾 Backup':
        if os.path.exists(DB_FILE):
            await update.message.reply_document(document=open(DB_FILE, 'rb'))
        else:
            await update.message.reply_text("Không tìm thấy dữ liệu.")

    elif text == '♻️ Restore':
        await update.message.reply_text("Vui lòng gửi file portfolio.db để Restore dữ liệu.")

    elif text == '❓ Hướng dẫn':
        guide = "📘 HƯỚNG DẪN SỬ DỤNG\n\n1. Nhập tài sản hiện có trước\n2. Dùng Nạp/Rút để ghi giao dịch\n3. Xem Tài sản để biết lãi lỗ\n4. Backup định kỳ"
        await update.message.reply_text(guide)

    else:
        await update.message.reply_text("Lệnh không xác định. Vui lòng chọn chức năng dưới đây:", reply_markup=get_main_keyboard())

# --- 4. XỬ LÝ NÚT BẤM DƯỚI TIN NHẮN (INLINE KEYBOARD) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # Xử lý Nạp / Rút
    if data.startswith("cat_"):
        parts = data.split("_")
        action, cat = parts[1], parts[2]
        context.user_data['state'] = f"awaiting_{action}"
        context.user_data['category'] = cat
        await query.edit_message_text(f"Đã chọn {cat}.\nNhập số tiền {'nạp' if action == 'nap' else 'rút'}:")

    # Bấm vào 1 giao dịch trong Lịch sử
    elif data.startswith("hist_"):
        tx_id = data.split("_")[1]
        keyboard = [
            [InlineKeyboardButton("✏️ Sửa", callback_data=f"edit_{tx_id}"),
             InlineKeyboardButton("❌ Xóa", callback_data=f"del_{tx_id}")],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data="back_hist_list")]
        ]
        await query.edit_message_text("Bạn muốn làm gì?", reply_markup=InlineKeyboardMarkup(keyboard))

    # Bấm nút Sửa
    elif data.startswith("edit_"):
        tx_id = data.split("_")[1]
        context.user_data['state'] = f"awaiting_edit_{tx_id}"
        await query.edit_message_text("📝 Nhập số tiền mới cho giao dịch này:")

    # Bấm nút Xóa
    elif data.startswith("del_"):
        tx_id = data.split("_")[1]
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        conn.commit()
        conn.close()
        
        keyboard = [[InlineKeyboardButton("⬅️ Quay lại", callback_data="back_hist_list")]]
        await query.edit_message_text("✅ Đã xóa giao dịch thành công.", reply_markup=InlineKeyboardMarkup(keyboard))

    # Nút Quay lại danh sách 10 giao dịch
    elif data == "back_hist_list":
        msg, markup = get_recent_history_menu()
        await query.edit_message_text(msg, reply_markup=markup)

    # Nút Xem full lịch sử
    elif data == "view_full_hist":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY date DESC, id DESC")
        rows = c.fetchall()
        conn.close()

        crypto_txs = [r for r in rows if r[1] == 'Crypto']
        stock_txs = [r for r in rows if r[1] == 'Stock']

        msg = "📜 FULL LỊCH SỬ GIAO DỊCH\n\n🌕 CRYPTO:\n"
        for r in crypto_txs:
            msg += f"🔹 {r[4]} | {r[2]}: {format_money(r[3])}\n"
            
        msg += "\n━━━━━━━━━━━━━━\n\n📈 STOCK:\n"
        for r in stock_txs:
            msg += f"🔹 {r[4]} | {r[2]}: {format_money(r[3])}\n"

        if len(msg) > 4000:
            msg = msg[:3800] + "\n\n... (Dữ liệu quá dài. Hãy tải file Backup để xem toàn bộ)"

        keyboard = [[InlineKeyboardButton("⬅️ Đóng", callback_data="close_msg")]]
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

    # Đóng tin nhắn
    elif data == "close_msg":
        await query.message.delete()

# Xử lý khi user Upload file Backup
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.file_name == DB_FILE:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(DB_FILE)
        await update.message.reply_text("✅ Restore thành công!", reply_markup=get_main_keyboard())
    else:
        await update.message.reply_text("⚠️ File không hợp lệ. Vui lòng gửi file portfolio.db")

# --- 5. CHẠY BOT ---
def main():
    init_db()
    TOKEN = os.environ.get("BOT_TOKEN")
    if not TOKEN:
        print("LỖI: Chưa cấu hình BOT_TOKEN")
        return

    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(handle_callback))
    
    print("🤖 Bot đang chạy...")
    app.run_polling()

if __name__ == '__main__':
    main()
