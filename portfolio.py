
import sqlite3

DB_NAME = "portfolio.db"

def get_conn():
    return sqlite3.connect(DB_NAME)

def get_report():
    conn = get_conn()
    c = conn.cursor()

    categories = ["crypto", "stock"]
    result = {}

    total_value = 0
    total_capital = 0

    for cat in categories:
        c.execute(
            "SELECT type, SUM(amount) FROM transactions WHERE category=? GROUP BY type",
            (cat,),
        )

        deposit = 0
        withdraw = 0

        for ttype, total in c.fetchall():
            if ttype == "deposit":
                deposit = total or 0
            if ttype == "withdraw":
                withdraw = total or 0

        c.execute("SELECT value FROM values_now WHERE category=?", (cat,))
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
            "profit": profit,
            "percent": percent,
        }

    total_profit = total_value - total_capital
    total_percent = (total_profit / total_capital * 100) if total_capital != 0 else 0

    conn.close()
    return result, total_value, total_profit, total_percent

def set_value(category, value):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        '''
        INSERT INTO values_now (user_id, category, value)
        VALUES (1, ?, ?)
        ON CONFLICT(user_id, category)
        DO UPDATE SET value=excluded.value
        ''',
        (category, float(value)),
    )
    conn.commit()
    conn.close()
