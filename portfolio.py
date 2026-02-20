
import sqlite3

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
        date TEXT
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
        "INSERT INTO transactions (user_id, category, type, amount, date) VALUES (?, ?, ?, ?, ?)",
        (user_id, category, ttype, amount, date)
    )

    conn.commit()
    conn.close()


def delete_transaction(tx_id, user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM transactions WHERE id=? AND user_id=?", (tx_id, user_id))
    conn.commit()
    conn.close()


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


def get_history(user_id, category):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    SELECT id, type, amount, date
    FROM transactions
    WHERE user_id=? AND category=?
    ORDER BY date DESC
    """, (user_id, category))

    rows = c.fetchall()
    conn.close()
    return rows


def get_all_transactions(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
    SELECT id, category, type, amount, date
    FROM transactions
    WHERE user_id=?
    ORDER BY date DESC
    """, (user_id,))

    rows = c.fetchall()
    conn.close()
    return rows


def get_report(user_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    categories = ["crypto", "stock"]
    result = {}

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

        result[cat] = {
            "deposit": deposit,
            "withdraw": withdraw,
            "value": value,
            "profit": profit
        }

    conn.close()
    return result
