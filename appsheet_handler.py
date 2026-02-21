import requests
import json
import os
from datetime import datetime

# Lấy URL Apps Script từ biến môi trường (Environment Variable) trên Railway
# Điều này giúp bảo mật link Web App của bạn
APPSHEET_WEB_APP_URL = os.getenv("APPSHEET_URL")

def sync_to_appsheet(category, amount, note, transaction_type="Chi tiêu"):
    """
    Hàm gửi dữ liệu sang Google Sheets (AppSheet)
    """
    if not APPSHEET_WEB_APP_URL:
        print("❌ Lỗi: Chưa cấu hình APPSHEET_URL trên Railway.")
        return False

    # Chuẩn bị dữ liệu theo đúng cấu trúc bảng của bạn
    payload = {
        "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "type": transaction_type,
        "category": category,
        "amount": amount,
        "note": note
    }

    try:
        response = requests.post(
            APPSHEET_WEB_APP_URL, 
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            print("✅ Đã đồng bộ sang AppSheet thành công.")
            return True
        else:
            print(f"⚠️ Lỗi đồng bộ: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi kết nối AppSheet: {str(e)}")
        return False