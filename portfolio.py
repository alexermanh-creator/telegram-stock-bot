
import sqlite3

DB_NAME = "portfolio.db"

def conn():
    return sqlite3.connect(DB_NAME)

def get_cash():
    c = conn()
    cur = c.cursor()
    cur.execute("SELECT amount FROM cash WHERE id=1")
    row = cur.fetchone()
    c.close()
    return row[0] if row else 0

def set_cash(val):
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT OR REPLACE INTO cash (id, amount) VALUES (1,?)", (val,))
    c.commit()
    c.close()

def set_value(cat, val):
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT OR REPLACE INTO values_now (category, value) VALUES (?,?)", (cat, val))
    c.commit()
    c.close()

def add_tx(cat, typ, amt, date):
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT INTO transactions (category,type,amount,date) VALUES (?,?,?,?)", (cat, typ, amt, date))
    c.commit()
    c.close()

def get_report():
    c = conn()
    cur = c.cursor()

    result = {}
    total_deposit = 0
    total_withdraw = 0
    total_value = 0

    for cat in ["crypto","stock"]:
        cur.execute("SELECT type, SUM(amount) FROM transactions WHERE category=? GROUP BY type", (cat,))
        dep = 0
        wd = 0
        for t,v in cur.fetchall():
            if t == "deposit":
                dep = v or 0
            if t == "withdraw":
                wd = v or 0

        cur.execute("SELECT value FROM values_now WHERE category=?", (cat,))
        row = cur.fetchone()
        val = row[0] if row else 0

        capital = dep - wd
        profit = val - capital
        percent = (profit/capital*100) if capital else 0

        total_deposit += dep
        total_withdraw += wd
        total_value += val

        result[cat] = {
            "deposit": dep,
            "withdraw": wd,
            "value": val,
            "profit": profit,
            "percent": percent
        }

    cash = get_cash()
    total_value += cash
    invest_value = total_value - cash
    total_profit = total_value - (total_deposit - total_withdraw + cash)
    total_percent = (total_profit/(total_deposit-total_withdraw+cash)*100) if (total_deposit-total_withdraw+cash) else 0

    c.close()

    return result, total_value, total_profit, total_percent, total_deposit, total_withdraw, invest_value, cash
