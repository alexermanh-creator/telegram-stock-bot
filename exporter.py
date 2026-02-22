import sqlite3
import pandas as pd
import io
import os

DB_FILE = 'portfolio.db'

class ReportExporter:
    def export_excel_report(self):
        try:
            if not os.path.exists(DB_FILE): return None
            conn = sqlite3.connect(DB_FILE)
            df_tx = pd.read_sql_query("SELECT category, type, amount, date, note FROM transactions", conn)
            conn.close()

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_tx.columns = ['Danh mục', 'Loại', 'Số tiền', 'Ngày', 'Ghi chú']
                df_tx.sort_values('Ngày', ascending=False).to_excel(writer, sheet_name='Giao_Dich', index=False)
                # Tự động dãn cột Ghi chú
                writer.sheets['Giao_Dich'].set_column('E:E', 40)
            output.seek(0)
            return output
        except: return None

reporter = ReportExporter()
