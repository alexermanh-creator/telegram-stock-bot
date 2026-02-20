import os
import sqlite3
import logging
import datetime
import io
import re
import matplotlib
matplotlib.use('Agg') # Tránh lỗi vẽ biểu đồ trên server
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
    
    if tx_count <= 4:
        c.execute("DELETE FROM assets")
        c.execute("DELETE FROM transactions")
        
        c.executemany("INSERT INTO assets (category, current_value) VALUES (?, ?)", 
                      [('Crypto', 20000000), ('Stock', 123000000), ('Cash', 0)])
        
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

# --- 2. HÀM HỖ TRỢ VÀ MENU ĐA CẤP ---
def format_m(amount):
    return f"{amount / 1000000:.1f}M" if amount != 0 else "0"

def format_money(amount):
    return f"{int(amount):,}"

# HÀM DỊCH SỐ THÔNG MINH (VD: 10tr -> 10000000)
def parse_amount(text):
    text_lower = text.lower().strip().replace(',', '').replace(' ', '')
    # Tìm kiếm mẫu số + chữ (VD: 10.5tr, 50m, 1ty)
    match = re.search(r'^([\d\.]+)(tr|triệu|trieu|m|tỷ|ty|k|nghìn)?$', text_lower)
    if match:
        val = float(match.group(1))
        unit = match.group(2)
        if unit in ['tr', 'triệu', 'trieu', 'm']:
            return val * 1000000
        elif unit in ['tỷ', 'ty']:
            return val * 1000000000
        elif unit in ['k', 'nghìn']:
            return val * 1000
        else:
            return val # Nếu gõ số trơn (10000000)
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
    keyboard = [
        ['🏦 Quản lý Tài sản', '💸 Giao dịch'],
        ['📊 Thống kê', '⚙️ Hệ thống']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_asset_menu():
    keyboard = [
        ['💰 Xem Tổng Tài sản', '💵 Cập nhật Số dư'],
        ['💳 Quỹ Tiền mặt', '🎯 Đặt Mục tiêu'],
        ['🏠 Menu Chính']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_tx_menu():
    keyboard = [
        ['➕ Nạp tiền', '➖ Rút tiền'],
        ['🏠 Menu Chính']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_stats_menu():
    keyboard = [
        ['📜 Lịch sử', '🥧 Phân bổ', '📈 Biểu đồ'],
        ['🏠 Menu Chính']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_sys_menu():
    keyboard = [
        ['💾 Backup DB', '♻️ Restore DB'],
        ['❓ Hướng dẫn', '🏠 Menu Chính']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_history_menu(page=None):
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
        display_rows = rows[:10]
        msg = "📜 10 GIAO DỊCH GẦN NHẤT\n\nClick để Sửa/Xóa:"
        back_data = "recent"
    else:
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
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Chào mừng bạn đến với Hệ thống Quản lý Tài sản!\n"
        "Vui lòng chọn danh mục tính năng bên dưới:", 
        reply_markup=get_main_menu()
    )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # 3.1. ĐIỀU HƯỚNG MENU ĐA CẤP
    menu_navs = ['🏦 Quản lý Tài sản', '💸 Giao dịch', '📊 Thống kê', '⚙️ Hệ thống', '🏠 Menu Chính']
    if text in menu_navs:
        context.user_data.clear()
        
    if text == '🏠 Menu Chính':
        await update.message.reply_text("🏠 Bạn đang ở Menu Chính:", reply_markup=get_main_menu())
        return
    elif text == '🏦 Quản lý Tài sản':
        await update.message.reply_text("🏦 QUẢN LÝ TÀI SẢN\nChọn chức năng bạn muốn sử dụng:", reply_markup=get_asset_menu())
        return
    elif text == '💸 Giao dịch':
        await update.message.reply_text("💸 GIAO DỊCH\nChọn loại giao dịch cần ghi nhận:", reply_markup=get_tx_menu())
        return
    elif text == '📊 Thống kê':
        await update.message.reply_text("📊 THỐNG KÊ & PHÂN TÍCH\nXem tình hình tài chính của bạn:", reply_markup=get_stats_menu())
        return
    elif text == '⚙️ Hệ thống':
        await update.message.reply_text("⚙️ HỆ THỐNG\nSao lưu, phục hồi dữ liệu hoặc xem hướng dẫn:", reply_markup=get_sys_menu())
        return

    # 3.2. KIỂM TRA TRẠNG THÁI NHẬP LIỆU (CÓ DÙNG parse_amount)
    state = context.user_data.get('state')
    
    # NHẬP CẬP NHẬT SỐ DƯ (MỚI)
    if state and str(state).startswith('awaiting_balance_'):
        cat = state.split("_")[2]
        amount = parse_amount(text)
        if amount is not None:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES (?, ?)", (cat, amount))
            conn.commit()
            conn.close()
            context.user_data.clear()
            await update.message.reply_text(f"✅ Đã cập nhật số dư của {cat} thành: {format_money(amount)}", reply_markup=get_asset_menu())
        else:
            await update.message.reply_text("⚠️ Vui lòng nhập số hợp lệ (VD: 10tr, 15M, 20000000):")
        return

    # NHẬP NẠP/RÚT
    elif state in ['awaiting_nap', 'awaiting_rut']:
        amount = parse_amount(text)
        if amount is not None:
            cat = context.user_data.get('category')
            tx_type = 'Nạp' if state == 'awaiting_nap' else 'Rút'
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT INTO transactions (category, type, amount, date) VALUES (?, ?, ?, ?)", 
                      (cat, tx_type, amount, date_str))
            tx_id = c.lastrowid
            conn.commit()
            conn.close()
            context.user_data.clear()
            
            keyboard = [[InlineKeyboardButton("↩️ Hoàn tác", callback_data=f"undo_{tx_id}")]]
            await update.message.reply_text(
                f"✅ Đã ghi nhận {tx_type} {format_money(amount)} vào {cat}.", 
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await update.message.reply_text("⚠️ Vui lòng nhập số tiền hợp lệ (VD: 10tr, 15M, 20000000):")
        return

    # SỬA LỊCH SỬ
    elif state and str(state).startswith('awaiting_edit_'):
        new_amount = parse_amount(text)
        if new_amount is not None:
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
        else:
            await update.message.reply_text("⚠️ Vui lòng nhập số tiền hợp lệ (VD: 10tr, 15M, 20000000):")
        return
        
    # XỬ LÝ NLP CHO MỤC TIÊU
    elif state == 'awaiting_target':
        s = get_stats()
        tong_von = s['tong_von']
        text_lower = text.lower()
        new_target = None
        
        if 'hòa vốn' in text_lower or 'hoà vốn' in text_lower:
            new_target = tong_von
        else:
            match_rel = re.search(r'(lãi|lời|âm|lỗ)\s*([\d\.]+)\s*(%|tr|triệu|tỷ|ty|m|k)?', text_lower)
            if match_rel:
                action = match_rel.group(1)
                val = float(match_rel.group(2))
                unit = match_rel.group(3)
                sign = 1 if action in ['lãi', 'lời'] else -1
                
                if unit == '%': new_target = tong_von + sign * (tong_von * val / 100)
                elif unit in ['tr', 'triệu', 'm']: new_target = tong_von + sign * (val * 1000000)
                elif unit in ['tỷ', 'ty']: new_target = tong_von + sign * (val * 1000000000)
                elif unit in ['k', 'nghìn']: new_target = tong_von + sign * (val * 1000)
                else: new_target = tong_von + sign * val
            else:
                new_target = parse_amount(text_lower)
        
        if new_target is not None:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('target_asset', ?)", (new_target,))
            conn.commit()
            conn.close()
            context.user_data.clear()
            await update.message.reply_text(
                f"✅ Đã thiết lập mục tiêu tài sản: {format_money(new_target)}\n"
                f"(Dựa trên tổng vốn hiện tại: {format_m(tong_von)})", 
                reply_markup=get_asset_menu()
            )
        else:
            await update.message.reply_text("⚠️ Không hiểu cú pháp. Bạn có thể gõ: Hòa vốn, Lãi 10%, Âm 50tr, hoặc 500tr:")
        return

    # 3.3. XỬ LÝ CÁC NÚT CHỨC NĂNG CỤ THỂ
    # --- Nhóm Quản lý Tài sản ---
    if text == '💰 Xem Tổng Tài sản':
        s = get_stats()
        t_ts = s['tong_tai_san']
        c_pct = (s['c_hien_co'] / t_ts * 100) if t_ts > 0 else 0
        s_pct = (s['s_hien_co'] / t_ts * 100) if t_ts > 0 else 0
        cash_pct = (s['cash_hien_co'] / t_ts * 100) if t_ts > 0 else 0

        reply = (
            f"🏆 TỔNG TÀI SẢN\n"
            f"{format_m(s['tong_tai_san'])}\n"
            f"{'📈' if s['tong_lai'] >= 0 else '📉'} {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)\n"
            f"🎯 Tiến độ mục tiêu: {s['target_progress']:.1f}% ({format_m(s['tong_tai_san'])} / {format_m(s['target_asset'])})\n\n"
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
            f"💵 TIỀN MẶT ({cash_pct:.0f}%)\n"
            f"💰 Số dư: {format_m(s['cash_hien_co'])}\n"
            f"📥 Nạp: {format_m(s['cash_nap'])}\n"
            f"📤 Rút: {format_m(s['cash_rut'])}\n"
        )
        await update.message.reply_text(reply)

    elif text == '💵 Cập nhật Số dư':
        keyboard = [
            [InlineKeyboardButton("🪙 Crypto", callback_data="bal_Crypto"),
             InlineKeyboardButton("📈 Stock", callback_data="bal_Stock")],
            [InlineKeyboardButton("💵 Tiền mặt", callback_data="bal_Cash")]
        ]
        await update.message.reply_text("Chọn tài sản bạn muốn cập nhật số dư:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif text == '💳 Quỹ Tiền mặt':
        s = get_stats()
        reply = (
            f"💵 QUỸ TIỀN MẶT\n\n"
            f"💰 Số dư hiện tại: {format_money(s['cash_hien_co'])}\n"
            f"📥 Tổng nạp vào: {format_money(s['cash_nap'])}\n"
            f"📤 Tổng rút ra: {format_money(s['cash_rut'])}\n\n"
            f"💡 Mẹo: Khi bạn rút tiền từ Stock/Crypto ra thành tiền mặt, hãy dùng chức năng ➖ Rút tiền (Stock) rồi ➕ Nạp tiền (Tiền mặt)."
        )
        await update.message.reply_text(reply)

    elif text == '🎯 Đặt Mục tiêu':
        context.user_data['state'] = 'awaiting_target'
        prompt = (
            "🎯 NHẬP MỤC TIÊU BẠN MUỐN HƯỚNG TỚI:\n\n"
            "Bot có thể tự hiểu tiếng Việt, ví dụ:\n"
            "▫️ Hòa vốn\n"
            "▫️ Lãi 10% hoặc Âm 5%\n"
            "▫️ Lãi 50tr hoặc Lỗ 20tr\n"
            "▫️ 500tr hoặc 1.5 tỷ\n"
            "▫️ 500000000 (số cụ thể)"
        )
        await update.message.reply_text(prompt)

    # --- Nhóm Giao dịch ---
    elif text in ['➕ Nạp tiền', '➖ Rút tiền']:
        action = 'nap' if 'Nạp' in text else 'rut'
        keyboard = [
            [InlineKeyboardButton("🪙 Crypto", callback_data=f"cat_{action}_Crypto"),
             InlineKeyboardButton("📈 Stock", callback_data=f"cat_{action}_Stock")],
            [InlineKeyboardButton("💵 Tiền mặt", callback_data=f"cat_{action}_Cash")]
        ]
        await update.message.reply_text("Chọn danh mục:", reply_markup=InlineKeyboardMarkup(keyboard))

    # --- Nhóm Thống kê ---
    elif text == '📜 Lịch sử':
        msg, markup = get_history_menu(page=None)
        if markup:
            await update.message.reply_text(msg, reply_markup=markup)
        else:
            await update.message.reply_text(msg)

    elif text == '🥧 Phân bổ':
        s = get_stats()
        fig, ax = plt.subplots(figsize=(5,5))
        labels_all = ['Crypto', 'Stock', 'Tiền mặt']
        sizes_all = [s['c_hien_co'], s['s_hien_co'], s['cash_hien_co']]
        colors_all = ['#f39c12', '#3498db', '#2ecc71']
        
        filtered_labels = [l for l, sz in zip(labels_all, sizes_all) if sz > 0]
        filtered_sizes = [sz for sz in sizes_all if sz > 0]
        filtered_colors = [c for c, sz in zip(colors_all, sizes_all) if sz > 0]
        
        if sum(filtered_sizes) == 0:
            await update.message.reply_text("Tài sản đang trống.")
            return
            
        ax.pie(filtered_sizes, labels=filtered_labels, autopct='%1.1f%%', startangle=90, colors=filtered_colors)
        ax.axis('equal')  
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        
        cap_text = ""
        for l, sz in zip(labels_all, sizes_all):
            pct = (sz / sum(sizes_all)) * 100 if sum(sizes_all) > 0 else 0
            cap_text += f"{l}: {pct:.0f}%\n"
            
        await update.message.reply_photo(photo=buf, caption=cap_text)

    elif text == '📈 Biểu đồ':
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT date, type, amount FROM transactions ORDER BY date ASC")
        txs = c.fetchall()
        conn.close()

        if not txs:
            await update.message.reply_text("Chưa có đủ dữ liệu giao dịch để vẽ biểu đồ.")
            return

        daily_txs = {}
        for date_str, tx_type, amt in txs:
            if date_str not in daily_txs:
                daily_txs[date_str] = 0
            if tx_type == 'Nạp': daily_txs[date_str] += amt
            else: daily_txs[date_str] -= amt

        dates = []
        capitals = []
        current_capital = 0
        sorted_dates = sorted(daily_txs.keys())
        
        for d in sorted_dates:
            current_capital += daily_txs[d]
            dates.append(datetime.datetime.strptime(d, "%Y-%m-%d"))
            capitals.append(current_capital)

        s = get_stats()
        tong_tai_san = s['tong_tai_san']
        
        fig, ax = plt.subplots(figsize=(10, 5))
        
        ax.plot(dates, capitals, label="Vốn thực (Nạp - Rút)", color='#3498db', marker='.', linewidth=2)
        
        today = datetime.datetime.now()
        color_trend = '#2ecc71' if tong_tai_san >= capitals[-1] else '#e74c3c'
        ax.plot([dates[-1], today], [capitals[-1], tong_tai_san], 
                label=f"Tổng tài sản hiện tại ({format_m(tong_tai_san)})", 
                color=color_trend, marker='o', linestyle='--', linewidth=2, markersize=8)

        ax.yaxis.set_major_formatter(ticker.FuncFormatter(lambda x, pos: f"{x/1000000:,.0f}M"))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%Y'))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        plt.xticks(rotation=45)
        
        ax.set_title(f"BIỂU ĐỒ BIẾN ĐỘNG TÀI SẢN\nLãi/Lỗ: {format_money(s['tong_lai'])} ({s['tong_lai_pct']:.1f}%)", fontsize=12, fontweight='bold')
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.6)
        
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        plt.close(fig)
        
        await update.message.reply_photo(photo=buf, caption="📈 Trục ngang: Thời gian | Trục dọc: Số tiền\n▫️ Đường Xanh dương: Dòng tiền vốn bạn đổ vào.\n▫️ Đường Đứt nét: Sự chênh lệch (Lãi/lỗ) so với Tài sản hiện tại.")

    # --- Nhóm Hệ thống ---
    elif text == '💾 Backup DB':
        if os.path.exists(DB_FILE):
            await update.message.reply_document(document=open(DB_FILE, 'rb'))
        else:
            await update.message.reply_text("Không tìm thấy dữ liệu.")

    elif text == '♻️ Restore DB':
        await update.message.reply_text("Vui lòng gửi file portfolio.db để Restore dữ liệu.")

    elif text == '❓ Hướng dẫn':
        guide = (
            "📘 HƯỚNG DẪN SỬ DỤNG BOT:\n\n"
            "1️⃣ Quản lý Tài sản: Dùng để xem số dư tổng quát, thiết lập mục tiêu hoặc cập nhật số dư (hỗ trợ nhập nhanh 10tr, 50m, 1.5 tỷ).\n"
            "2️⃣ Giao dịch: Mỗi khi nạp tiền hay rút tiền khỏi sàn/ví, hãy vào đây ấn Nạp/Rút để bot ghi nhớ Vốn.\n"
            "3️⃣ Thống kê: Xem các biểu đồ và xem danh sách Lịch sử (có thể Sửa/Xóa giao dịch lỡ nhập sai).\n"
            "4️⃣ Hệ thống: Nhớ tải file Backup DB định kỳ về máy nhé!"
        )
        await update.message.reply_text(guide)

    else:
        await update.message.reply_text("Lệnh không xác định. Vui lòng sử dụng Menu bên dưới:", reply_markup=get_main_menu())

# --- 4. XỬ LÝ INLINE KEYBOARD (NÚT BẤM DƯỚI TIN NHẮN) ---
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("undo_"):
        tx_id = data.split("_")[1]
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
        conn.commit()
        conn.close()
        await query.edit_message_text("✅ Đã HOÀN TÁC (xóa) giao dịch bạn vừa nhập thành công!")

    elif data.startswith("bal_"):
        cat = data.split("_")[1]
        context.user_data['state'] = f"awaiting_balance_{cat}"
        await query.edit_message_text(f"Đã chọn {cat}.\nNhập số dư hiện tại (VD: 10tr, 50M, 1.5 tỷ):")

    elif data.startswith("cat_"):
        parts = data.split("_")
        action, cat = parts[1], parts[2]
        context.user_data['state'] = f"awaiting_{action}"
        context.user_data['category'] = cat
        await query.edit_message_text(f"Đã chọn {cat}.\nNhập số tiền {'nạp' if action == 'nap' else 'rút'} (VD: 500k, 10tr, 50M):")

    elif data.startswith("hist_"):
        parts = data.split("_")
        tx_id = parts[1]
        back_to = parts[2]
        
        keyboard = [
            [InlineKeyboardButton("✏️ Sửa", callback_data=f"edit_{tx_id}_{back_to}"),
             InlineKeyboardButton("❌ Xóa", callback_data=f"del_{tx_id}_{back_to}")],
            [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"back_view_{back_to}")]
        ]
        await query.edit_message_text("Bạn muốn làm gì?", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("edit_"):
        parts = data.split("_")
        tx_id = parts[1]
        back_to = parts[2]
        context.user_data['state'] = f"awaiting_edit_{tx_id}_{back_to}"
        await query.edit_message_text("📝 Nhập số tiền mới cho giao dịch này (VD: 10tr, 50M):")

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

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if doc.file_name == DB_FILE:
        file = await context.bot.get_file(doc.file_id)
        await file.download_to_drive(DB_FILE)
        await update.message.reply_text("✅ Restore thành công!", reply_markup=get_main_menu())
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
