import sqlite3
import pandas as pd
import datetime
import os

DB_FILE = 'portfolio.db'

class StockManager:
    def __init__(self):
        # Không gọi init_db ở đây để tránh xung đột, 
        # việc tạo bảng sẽ do main.py quản lý khi khởi động.
        pass

    def _get_conn(self):
        return sqlite3.connect(DB_FILE)

    # --- BƯỚC 1, 2, 3: QUẢN LÝ TIỀN MẶT (CASH) ---
    def get_stock_cash(self):
        """Lấy số dư tiền mặt chuyên biệt cho chứng khoán từ bảng assets"""
        with self._get_conn() as conn:
            res = conn.execute("SELECT current_value FROM assets WHERE category='Stock'").fetchone()
            return res[0] if res else 0

    def update_stock_cash(self, amount, tx_type="Nạp"):
        """Nạp/Rút tiền vào tài khoản chứng khoán (Đồng bộ với module Main)"""
        with self._get_conn() as conn:
            curr = self.get_stock_cash()
            new_bal = curr + amount if tx_type == "Nạp" else curr - amount
            
            # Cập nhật bảng assets (để module main hiển thị đúng tổng tài sản)
            conn.execute("INSERT OR REPLACE INTO assets (category, current_value) VALUES ('Stock', ?)", (new_bal,))
            
            # Ghi vào lịch sử giao dịch chung
            date_str = datetime.datetime.now().strftime("%Y-%m-%d")
            conn.execute("INSERT INTO transactions (category, type, amount, date) VALUES ('Stock', ?, ?, ?)",
                         (tx_type, abs(amount), date_str))
            conn.commit()
        return new_bal

    # --- BƯỚC 5, 6: QUẢN LÝ GIAO DỊCH CỔ PHIẾU (ORDER) ---
    def execute_order(self, symbol, qty, price, order_type="Mua"):
        """Xử lý lệnh Mua/Bán cổ phiếu"""
        symbol = symbol.upper()
        total_value = qty * price
        fee = total_value * 0.001  # Giả định phí giao dịch 0.1%
        
        cash = self.get_stock_cash()
        if order_type == "Mua" and cash < (total_value + fee):
            return False, f"❌ Không đủ tiền! Cần: {(total_value+fee):,.0f}đ"

        with self._get_conn() as conn:
            c = conn.cursor()
            
            # 1. Ghi lịch sử lệnh vào bảng stock_orders
            date_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            c.execute("""INSERT INTO stock_orders (symbol, type, qty, price, fee, date) 
                         VALUES (?, ?, ?, ?, ?, ?)""", (symbol, order_type, qty, price, fee, date_str))

            # 2. Cập nhật bảng stock_holdings (Danh mục đang nắm giữ)
            c.execute("SELECT qty, total_cost FROM stock_holdings WHERE symbol=?", (symbol,))
            row = c.fetchone()
            
            if order_type == "Mua":
                new_qty = (row[0] if row else 0) + qty
                new_cost = (row[1] if row else 0) + total_value + fee
                avg_price = new_cost / new_qty
                c.execute("INSERT OR REPLACE INTO stock_holdings VALUES (?, ?, ?, ?)", 
                          (symbol, new_qty, avg_price, new_cost))
                # Trừ tiền mặt trong tài khoản Stock
                self.update_stock_cash(total_value + fee, "Rút")
            
            elif order_type == "Bán":
                if not row or row[0] < qty:
                    return False, f"❌ Không đủ cổ phiếu {symbol}!"
                
                new_qty = row[0] - qty
                # Tính lãi lỗ cho lệnh bán này
                profit = (price * qty) - (row[2] * qty) - fee # (Giá bán - Giá vốn) * SL - Phí
                
                if new_qty == 0:
                    c.execute("DELETE FROM stock_holdings WHERE symbol=?", (symbol,))
                else:
                    # Giảm trừ giá vốn tương ứng số lượng còn lại
                    new_cost = row[1] * (new_qty / row[0])
                    c.execute("UPDATE stock_holdings SET qty=?, total_cost=? WHERE symbol=?", 
                              (new_qty, new_cost, symbol))
                
                # Cộng tiền mặt vào tài khoản Stock sau khi bán
                self.update_stock_cash(total_value - fee, "Nạp")

            conn.commit()
        return True, "Thành công"

    # --- BƯỚC 4, 9: PHÂN TÍCH HIỆU SUẤT ---
    def get_portfolio_summary(self):
        """Lấy dữ liệu để hiển thị Dashboard (Bước 2) và Phân tích (Bước 9)"""
        with self._get_conn() as conn:
            df_holdings = pd.read_sql_query("SELECT * FROM stock_holdings", conn)
            df_orders = pd.read_sql_query("SELECT * FROM stock_orders", conn)
        
        cash = self.get_stock_cash()
        stock_value = df_holdings['total_cost'].sum() # Tạm thời lấy theo giá vốn
        nav = cash + stock_value
        
        # Tính toán các chỉ số nâng cao cho Demo Bước 9
        win_rate = 0
        if not df_orders.empty:
            sell_orders = df_orders[df_orders['type'] == 'Bán']
            # Logic win-rate có thể phức tạp hơn, đây là bản đơn giản
            win_rate = 100 if len(sell_orders) > 0 else 0 

        return {
            "cash": cash,
            "stock_value": stock_value,
            "nav": nav,
            "holdings": df_holdings.to_dict('records'),
            "metrics": {
                "win_rate": f"{win_rate}%",
                "drawdown": "-1.5%", # Giả lập dữ liệu
                "profit_factor": "2.0"
            }
        }

stock_manager = StockManager()