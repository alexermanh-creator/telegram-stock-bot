import os
import asyncio
import requests
import json

# Lấy Key từ Railway Variables
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        # Ép cứng gọi thẳng vào cổng v1 CHUẨN (Bỏ qua v1beta gây lỗi)
        self.url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={self.api_key}"

    async def get_advice(self, user_query, s):
        if not self.api_key:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY trên Railway."
        
        prompt_text = (
            f"Bạn là chuyên gia tư vấn tài chính. Dữ liệu của tôi:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"- Chứng khoán: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Yêu cầu: Trả lời ngắn gọn, thông minh bằng văn bản thuần túy, TUYỆT ĐỐI KHÔNG dùng ký tự Markdown (*, #)."
        )

        # Đóng gói dữ liệu gửi đi theo chuẩn thô của Google
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.7}
        }
        headers = {'Content-Type': 'application/json'}

        # Hàm call API trực tiếp không qua SDK
        def fetch_google_api():
            try:
                response = requests.post(self.url, headers=headers, json=payload, timeout=15)
                # Bắt lỗi nếu URL hoặc Key có vấn đề
                response.raise_for_status() 
                # Bóc tách câu trả lời từ Google
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            except requests.exceptions.HTTPError as err:
                return f"❌ Google từ chối truy cập: Mã lỗi {err.response.status_code}\nChi tiết: {err.response.text}"
            except Exception as e:
                return f"❌ Lỗi đường truyền: {str(e)}"

        try:
            # Chạy không đồng bộ để bot không bị treo
            ai_reply = await asyncio.to_thread(fetch_google_api)
            return ai_reply
        except Exception as e:
            return f"❌ Lỗi xử lý luồng AI: {str(e)}"

# Khởi tạo instance
portfolio_ai = PortfolioAI()
