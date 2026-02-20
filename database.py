
import sqlite3, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "portfolio.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT,
        type TEXT,
        amount REAL,
        date TEXT
    )
    """)
    c.execute("""
    CREATE TABLE IF NOT EXISTS values_now (
        category TEXT PRIMARY KEY,
        value REAL
    )
    """)
    conn.commit()
    conn.close()

def seed_data():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM transactions")
    if c.fetchone()[0] == 0:
        # Seed totals
        c.execute("INSERT INTO transactions (category,type,amount,date) VALUES ('crypto','deposit',348500000,'2024-01-01')")
        c.execute("INSERT INTO transactions (category,type,amount,date) VALUES ('crypto','withdraw',250500000,'2024-06-01')")
        c.execute("INSERT INTO transactions (category,type,amount,date) VALUES ('stock','deposit',267300000,'2024-02-01')")
        c.execute("INSERT INTO transactions (category,type,amount,date) VALUES ('stock','withdraw',156500000,'2024-08-01')")
        c.execute("INSERT OR REPLACE INTO values_now VALUES ('crypto',20000000)")
        c.execute("INSERT OR REPLACE INTO values_now VALUES ('stock',123000000)")
        conn.commit()
    conn.close()
