
import sqlite3

DB = "portfolio.db"

def conn():
    return sqlite3.connect(DB)

def get_totals():
    c = conn()
    cur = c.cursor()
    totals = {}
    dep_total = 0
    wd_total = 0

    for cat in ["crypto","stock"]:
        cur.execute("SELECT type, SUM(amount) FROM transactions WHERE category=? GROUP BY type", (cat,))
        dep = 0
        wd = 0
        for t,v in cur.fetchall():
            if t == "deposit": dep = v or 0
            if t == "withdraw": wd = v or 0

        cur.execute("SELECT value FROM values_now WHERE category=?", (cat,))
        row = cur.fetchone()
        val = row[0] if row else 0

        capital = dep - wd
        profit = val - capital
        percent = (profit/capital*100) if capital else 0

        dep_total += dep
        wd_total += wd

        totals[cat] = {
            "deposit": dep,
            "withdraw": wd,
            "value": val,
            "capital": capital,
            "profit": profit,
            "percent": percent
        }

    c.close()
    return totals, dep_total, wd_total

def set_value(cat, val):
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT OR REPLACE INTO values_now (category,value) VALUES (?,?)", (cat,val))
    c.commit()
    c.close()

def add_tx(cat, typ, amt, date):
    c = conn()
    cur = c.cursor()
    cur.execute("INSERT INTO transactions (category,type,amount,date) VALUES (?,?,?,?)", (cat,typ,amt,date))
    c.commit()
    c.close()
