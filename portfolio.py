
from database import get_conn

def get_portfolio():
    conn = get_conn()
    cur = conn.cursor()
    result = {}
    for cat in ["crypto","stock"]:
        cur.execute("SELECT type, SUM(amount) FROM transactions WHERE category=? GROUP BY type",(cat,))
        dep, wd = 0,0
        for t,v in cur.fetchall():
            if t=="deposit": dep=v or 0
            if t=="withdraw": wd=v or 0

        cur.execute("SELECT value FROM values_now WHERE category=?",(cat,))
        row = cur.fetchone()
        val = row[0] if row else 0

        capital = dep - wd
        profit = val - capital
        percent = (profit/capital*100) if capital else 0

        result[cat] = {
            "deposit":dep,
            "withdraw":wd,
            "value":val,
            "capital":capital,
            "profit":profit,
            "percent":percent
        }
    conn.close()
    return result

def set_value(cat, value):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO values_now VALUES (?,?)",(cat,value))
    conn.commit()
    conn.close()
