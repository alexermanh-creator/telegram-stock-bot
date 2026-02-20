
import sqlite3
from datetime import datetime

DB_NAME = "portfolio.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        category TEXT,
        type TEXT,
        amount REAL,
        date TEXT,
        created_at TEXT
    )
    """)

    conn.commit()
    conn.close()


def add_transaction(user_id, category, ttype, amount, date):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (user_id, category, type, amount, date, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, category, ttype, float(amount), str(date), datetime.now().isoformat())
    )
    conn.commit()
    conn.close()
