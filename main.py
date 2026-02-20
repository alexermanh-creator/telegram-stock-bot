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

# --- 1. KHỞI TẠO DATABASE VÀ NẠP TOÀN BỘ DỮ LIỆU TỪ ẢNH ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (category TEXT PRIMARY KEY, current_value REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transactions 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, type TEXT, amount REAL, date TEXT)''')
    
    # Kiểm tra xem db đang trống hoặc đang chứa 4 dòng demo cũ thì xóa đi để nạp full data
    c.execute("SELECT COUNT(*) FROM transactions")
    tx_count = c.fetchone()[0]
    
    if tx_count <= 4:
        c.execute("DELETE FROM assets")
        c.execute("DELETE FROM transactions")
        
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", 
                      [('Crypto', 20000000), ('Stock', 123000000)])
        
        # TOÀN BỘ DỮ LIỆU TRÍCH XUẤT TỪ ẢNH CỦA BẠN
        full_data = [
            # CRYPTO NẠP
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
            # CRYPTO RÚT
            ('Crypto', 'Rút', 5000000, '2024-11-08'), ('Crypto', 'Rút', 24500000, '2025-06-25'),
            ('Crypto', 'Rút', 28000000, '2025-06-30'), ('Crypto', 'Rút', 30000000, '2025-07-01'),
            ('Crypto', 'Rút', 20000000, '2025-07-24'), ('Crypto', 'Rút', 20000000, '2025-07-30'),
            ('Crypto', 'Rút', 20000000, '2025-07-31'), ('Crypto', 'Rút', 20000000, '2025-08-05'),
            ('Crypto', 'Rút', 20000000, '2025-08-28'), ('Crypto', 'Rút', 20000000, '2025-09-23'),
            ('Crypto', 'Rút', 5000000, '2025-10-28'), ('Crypto', 'Rút', 10000000, '2025-11-03'),
            ('Crypto', 'Rút', 15000000, '2025-11-12'), ('Crypto', 'Rút', 13000000, '2026-01-28'),
            # STOCK NẠP
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
            # STOCK RÚT
            ('Stock', 'Rút', 7000000, '2025-02-27'), ('Stock', 'Rút', 80000000, '2025-06-27'),
            ('Stock', 'Rút', 2000000, '2025-07-23'), ('Stock', 'Rút', 3000000, '2025-08-26'),
            ('Stock', 'Rút', 10000000, '2025-08-30'), ('Stock', 'Rút', 50000000, '2025-12-24'),
            ('Stock', 'Rút', 4500000, '2025-12-29')
        ]
        c.executemany("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", full_data)
        
    conn.commit()
    conn.close()

# --- 2. HÀM HỖ TRỢ HIỂN THỊ ---
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

def get_history_menu(page=None):
    """Hàm xử lý chia trang cho Lịch sử để hiển thị được toàn bộ Data"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, category, type, amount, date FROM transactions ORDER BY date DESC, id DESC")
    rows = c.fetchall()
    conn.close()

    if not rows:
        return "Chưa có giao dịch nào.", None

    PAGE_SIZE = 10
    keyboard = []
    
    if page is None:
        # Chế độ Top 10 gần nhất
        display_rows = rows[:10]
        msg = "📜 10 GIAO DỊCH GẦN NHẤT\n\nClick để Sửa/Xóa:"
        back_data = "recent"
    else:
        # Chế độ Xem Full có phân trang
        start_idx = page * PAGE_SIZE
        display_rows = rows[start_idx : start_idx + PAGE_SIZE]
        total_pages = (len(rows) + PAGE_SIZE - 1) // PAGE_SIZE
        msg = f"📜 FULL LỊCH SỬ (Trang {page + 1}/{total_pages})\n\nClick để Sửa/Xóa:"
        back_data = str(page)

    emojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
    
    for i, row in enumerate(display_rows):
        emoji = emojis[i] if i < 10 else f"{i+1}."
        btn_text = f"{emoji} {row[1]} | {row[2]} {format_money(row[3])} ({row[4]})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"hist_{row[0]}_{back_data}")])
        
    if page is None:
        keyboard.append([InlineKeyboardButton("📄 Xem full lịch sử", callback_data="view_page_0")])
    else:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Trang trước", callback_data=f"view_page_{page-1}"))
        if (page + 1) * PAGE_SIZE < len(rows):
            nav_row.append(InlineKeyboardButton("Trang sau ➡️", callback_data=f"view_page_{page+1}"))
        if nav_row:
            keyboard.append(nav_row)
        keyboard.append([InlineKeyboardButton("⬅️ Đóng full lịch sử", callback_data="back_to_recent")])
        
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
            parts = state.split("_")
            tx_id = parts[2]
            back_to = parts[3]
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("UPDATE transactions SET amount = ? WHERE id = ?", (new_amount, tx_id))
            conn.commit()
            conn.close()
            context.user_data.clear()
            
            page = None if back_to == "recent" else int(back_to)
            msg, markup = get_history_menu(page)
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
        msg, markup = get_history_menu(page=None)
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

    if data.startswith("cat_"):
        parts = data.split("_")
        action, cat = parts[1], parts[2]
        context.user_data['state'] = f"awaiting_{action}"
        context.user_data['category'] = cat
        await query.edit_message_text(f"Đã chọn {cat}.\nNhập số tiền {'nạp' if action == 'nap' else 'rút'}:")

    # Bấm vào 1 giao dịch trong Lịch sử
    elif data.startswith("hist_"):
        parts = data.split("_")
        tx_id = parts[1]
        back_to = parts[2] # "recent" hoặc số trang (0, 1, 2...)
        
        keyboard = [
            [InlineKeyboardButton("✏️ Sửa", callback_data=f"edit_{tx_id}_{back_to}"),
             InlineKeyboardButton("❌ Xóa", callback_data=f"del_{tx_id}_{back_to}")],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{back_to}")]
        ]
        await query.edit_message_text("Bạn muốn làm gì?", reply_markup=InlineKeyboardMarkup(keyboard))

    # Bấm nút Sửa
    elif data.startswith("edit_"):
        parts = data.split("_")
        tx_id = parts[1]
        back_to = parts[2]
        context.user_data['state'] = f"awaiting_edit_{tx_id}_{back_to}"
        await query.edit_message_text("📝 Nhập số tiền mới cho giao dịch này:")

    # Bấm nút Xóa
    elif data.startswith("del_"):
        parts = data.split("_")
        tx_id = parts[1]
        back_to = parts[2]
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        conn.commit()
        conn.close()
        
        keyboard = [[InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{back_to}")]]
        await query.edit_message_text("✅ Đã xóa giao dịch thành công.", reply_markup=InlineKeyboardMarkup(keyboard))

    # Xử lý điều hướng các trang
    elif data.startswith("view_page_"):
        page = int(data.split("_")[2])
        msg, markup = get_history_menu(page)
        await query.edit_message_text(msg, reply_markup=markup)
        
    elif data.startswith("back_view_"):
        back_to = data.split("back_view_")[1]
        page = None if back_to == "recent" else int(back_to)
        msg, markup = get_history_menu(page)
        await query.edit_message_text(msg, reply_markup=markup)
        
    elif data == "back_to_recent":
        msg, markup = get_history_menu(page=None)
        await query.edit_message_text(msg, reply_markup=markup)

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
