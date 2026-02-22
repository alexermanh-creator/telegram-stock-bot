import sqlite3
import pandas as pd
import io
import datetime
import os

DB_FILE = 'portfolio.db'

class ReportExporter:
    def export_excel_report(self):
        try:
            if not os.path.exists(DB_FILE): return None
            conn = sqlite3.connect(DB_FILE)
            
            # Đọc dữ liệu từ DB
            df_assets = pd.read_sql_query("SELECT category, current_value FROM assets", conn)
            df_tx = pd.read_sql_query("SELECT category, type, amount, date FROM transactions", conn)
            target_val = (conn.execute("SELECT value FROM settings WHERE key='target_asset'").fetchone() or [500000000])[0]
            conn.close()

            # --- XỬ LÝ LOGIC TÀI CHÍNH ---
            summary_data = []
            for cat in ['Crypto', 'Stock', 'Cash']:
                curr = df_assets[df_assets['category'] == cat]['current_value'].sum()
                tx = df_tx[df_tx['category'] == cat]
                nap = tx[tx['type'] == 'Nạp']['amount'].sum()
                rut = tx[tx['type'] == 'Rút']['amount'].sum()
                von = nap - rut
                lai_lo = curr - von
                pct = (lai_lo / von * 100) if von != 0 else 0
                
                summary_data.append({
                    'Danh mục': cat,
                    'Vốn thực (Cost)': von,
                    'Giá trị hiện tại': curr,
                    'Lãi/Lỗ (VNĐ)': lai_lo,
                    'Hiệu suất (%)': round(pct, 2)
                })

            df_s = pd.DataFrame(summary_data)
            output = io.BytesIO()

            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_s.to_excel(writer, sheet_name='Dashboard', index=False, startrow=4)
                df_tx.sort_values('date', ascending=False).to_excel(writer, sheet_name='Giao_Dich_Chi_Tiet', index=False)

                workbook = writer.book
                ws = writer.sheets['Dashboard']

                # Định dạng chuyên nghiệp
                title_fmt = workbook.add_format({'bold': True, 'font_size': 18, 'font_color': '#1F4E78'})
                header_fmt = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC', 'border': 1, 'align': 'center'})
                num_fmt = workbook.add_format({'num_format': '#,##0', 'border': 1})
                pct_fmt = workbook.add_format({'num_format': '0.0"%"', 'border': 1})
                red_fmt = workbook.add_format({'font_color': '#9C0006', 'bg_color': '#FFC7CE', 'num_format': '#,##0', 'border': 1})
                green_fmt = workbook.add_format({'font_color': '#006100', 'bg_color': '#C6EFCE', 'num_format': '#,##0', 'border': 1})

                # Header báo cáo
                ws.write('A1', 'HỆ THỐNG QUẢN TRỊ GIA SẢN CÁ NHÂN', title_fmt)
                ws.write('A2', f'Dữ liệu tính đến: {datetime.datetime.now().strftime("%d/%m/%Y %H:%M")}')
                ws.write('A3', f'Mục tiêu tài chính: {int(target_val):,} VNĐ')

                # Áp dụng format màu cho Lãi/Lỗ
                ws.conditional_format('D6:D8', {'type': 'cell', 'criteria': '>=', 'value': 0, 'format': green_fmt})
                ws.conditional_format('D6:D8', {'type': 'cell', 'criteria': '<', 'value': 0, 'format': red_fmt})
                ws.set_column('A:E', 18, num_fmt)

                # --- VẼ BIỂU ĐỒ 1: PHÂN BỔ TÀI SẢN (PIE) ---
                chart1 = workbook.add_chart({'type': 'pie'})
                chart1.add_series({
                    'name': 'Tỷ trọng tài sản',
                    'categories': ['Dashboard', 5, 0, 7, 0],
                    'values':     ['Dashboard', 5, 2, 7, 2],
                    'data_labels': {'percentage': True, 'font': {'size': 10}},
                })
                chart1.set_title({'name': 'Cơ cấu Danh mục Hiện tại'})
                ws.insert_chart('G2', chart1)

                # --- VẼ BIỂU ĐỒ 2: HIỆU SUẤT LÃI LỖ (COLUMN) ---
                chart2 = workbook.add_chart({'type': 'column'})
                chart2.add_series({
                    'name': 'Mức sinh lời (VNĐ)',
                    'categories': ['Dashboard', 5, 0, 7, 0],
                    'values':     ['Dashboard', 5, 3, 7, 3],
                    'fill':       {'color': '#4F81BD'}
                })
                chart2.set_title({'name': 'So sánh Lãi/Lỗ giữa các kênh'})
                ws.insert_chart('G18', chart2)

            output.seek(0)
            return output
        except Exception as e:
            print(f"Lỗi Report: {e}")
            return None

reporter = ReportExporter()
