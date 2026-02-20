
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

    c.execute("""
    CREATE TABLE IF NOT EXISTS values_now (
        user_id INTEGER,
        category TEXT,
        value REAL,
        PRIMARY KEY (user_id, category)
    )
    """)

    conn.commit()
    conn.close()


def add_transaction(user_id, category, ttype, amount, date):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO transactions (user_id, category, type, amount, date, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, category, ttype, amount, date, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def update_transaction(user_id, tx_id, amount, date):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "UPDATE transactions SET amount=?, date=? WHERE id=? AND user_id=?",
        (amount, date, tx_id, user_id)
    )
    conn.commit()
    conn.close()


def delete_transaction(user_id, tx_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id))
    conn.commit()
    conn.close()


def get_history(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
    SELECT id, category, type, amount, date
    FROM transactions
    WHERE user_id=?
    ORDER BY date ASC
    """, (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows


def set_value(user_id, category, value):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
    INSERT INTO values_now (user_id, category, value)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id, category)
    DO UPDATE SET value=excluded.value
    """, (user_id, category, value))
    conn.commit()
    conn.close()


def get_report(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    categories = ["crypto", "stock"]
    result = {}

    total_value = 0
    total_capital = 0

    for cat in categories:

        c.execute("""
        SELECT type, SUM(amount)
        FROM transactions
        WHERE user_id=? AND category=?
        GROUP BY type
        """, (user_id, cat))

        deposit = 0
        withdraw = 0

        for ttype, total in c.fetchall():
            if ttype == "deposit":
                deposit = total or 0
            if ttype == "withdraw":
                withdraw = total or 0

        c.execute(
            "SELECT value FROM values_now WHERE user_id=? AND category=?",
            (user_id, cat)
        )
        row = c.fetchone()
        value = row[0] if row else 0

        capital = deposit - withdraw
        profit = value - capital
        percent = (profit / capital * 100) if capital != 0 else 0

        total_value += value
        total_capital += capital

        result[cat] = {
            "deposit": deposit,
            "withdraw": withdraw,
            "value": value,
            "capital": capital,
            "profit": profit,
            "percent": percent
        }

    total_profit = total_value - total_capital
    total_percent = (total_profit / total_capital * 100) if total_capital != 0 else 0

    conn.close()

    return result, total_value, total_profit, total_percent
