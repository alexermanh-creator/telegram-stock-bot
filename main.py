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
    
    # Tạo thêm bảng Settings để lưu Mục tiêu tài sản
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
    
    # Lấy mục tiêu tài sản
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
