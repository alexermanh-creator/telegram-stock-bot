import os
import asyncio
import requests
import json

# Lấy Key từ Railway Variables
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        # BỎ QUA THƯ VIỆN SDK, CHỈ ĐỊNH ĐÍCH DANH ĐƯỜNG LINK GỐC CỦA GOOGLE
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"

    async def get_advice(self, user_query, s):
        if not self.api_key:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY trên Railway."
        
        # Ngữ cảnh dữ liệu gửi sang AI (Đọc từ main.py)
        prompt_text = (
            f"Bạn là chuyên gia tư vấn tài chính cá nhân. Dữ liệu thực tế của tôi:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"- Chứng khoán: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Yêu cầu: Trả lời bằng tiếng Việt, phân tích thông minh, chuyên nghiệp và thân thiện."
        )

        # Định dạng gói tin gửi đi theo chuẩn cấu trúc của Google
        payload = {
            "contents": [{
                "parts": [{"text": prompt_text}]
            }]
        }
        headers = {'Content-Type': 'application/json'}

        # Hàm gửi request trực tiếp
        def make_request():
            response = requests.post(self.url, headers=headers, data=json.dumps(payload))
            response.raise_for_status() # Bắt lỗi nếu đường link hoặc Key sai
            return response.json()

        try:
            # Chạy không đồng bộ để bot Telegram không bị treo
            data = await asyncio.to_thread(make_request)
            
            # Bóc tách câu trả lời từ gói tin JSON tải về
            text_response = data['candidates'][0]['content']['parts'][0]['text']
            return text_response
            
        except requests.exceptions.HTTPError as err:
            # Nếu Key sai hoặc hết hạn, nó sẽ báo lỗi chi tiết ở đây
            return f"❌ Lỗi API Google: {err.response.text}"
        except Exception as e:
            return f"❌ Lỗi xử lý dữ liệu: {str(e)}"

# Khởi tạo đối tượng
portfolio_ai = PortfolioAI()
