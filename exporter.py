import sqlite3
import pandas as pd
import io
import datetime
import os

DB_FILE = 'portfolio.db'

class ReportExporter:
    def export_excel_report(self):
        try:
            if not os.path.exists(DB_FILE):
                return None
            
            conn = sqlite3.connect(DB_FILE)
            # 1. Lấy dữ liệu chi tiết
            df_tx = pd.read_sql_query("SELECT date as 'Ngày', category as 'Danh mục', type as 'Loại', amount as 'Số tiền' FROM transactions ORDER BY date DESC", conn)
            df_assets = pd.read_sql_query("SELECT category as 'Danh mục', current_value as 'Giá trị hiện có' FROM assets", conn)
            conn.close()

            output = io.BytesIO()
            # 2. Sử dụng xlsxwriter để vẽ biểu đồ tự động
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_assets.to_excel(writer, sheet_name='Tong_Quan', index=False)
                df_tx.to_excel(writer, sheet_name='Lich_Su_Chi_Tiet', index=False)
                
                workbook  = writer.book
                worksheet = writer.sheets['Tong_Quan']

                # Vẽ biểu đồ hình tròn (Tỷ trọng tài sản)
                chart = workbook.add_chart({'type': 'pie'})
                max_row = len(df_assets) + 1
                chart.add_series({
                    'name': 'Phân bổ tài sản',
                    'categories': ['Tong_Quan', 1, 0, max_row - 1, 0],
                    'values':     ['Tong_Quan', 1, 1, max_row - 1, 1],
                    'data_labels': {'percentage': True, 'position': 'outside_end'},
                })
                chart.set_title({'name': 'Tỷ trọng Danh mục Đầu tư'})
                worksheet.insert_chart('D2', chart)

            output.seek(0)
            return output
        except Exception:
            return None

# Khởi tạo để main.py có thể gọi
reporter = ReportExporter()