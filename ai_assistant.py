import os
import asyncio
import requests
import json

# Lấy Key từ Railway
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        # GỌI ĐÍCH DANH ĐƯỜNG LINK GỐC, KHÔNG QUA THƯ VIỆN TRUNG GIAN
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={self.api_key}"

    async def get_advice(self, user_query, s):
        if not self.api_key:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY trên Railway."
        
        # Ngữ cảnh dữ liệu gửi sang AI
        prompt_text = (
            f"Bạn là chuyên gia tư vấn tài chính cá nhân. Dữ liệu thực tế của tôi:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s['details']['Crypto']['hien_co']):,} VNĐ\n"
            f"- Chứng khoán: {int(s['details']['Stock']['hien_co']):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Yêu cầu: Trả lời bằng tiếng Việt, phân tích chuyên nghiệp và thân thiện."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}]
        }
        headers = {'Content-Type': 'application/json'}

        def make_request():
            # Gọi API và giới hạn thời gian chờ 15 giây để bot không bao giờ bị treo
            return requests.post(self.url, headers=headers, json=payload, timeout=15)

        try:
            # Chạy không đồng bộ (Không làm đơ các chức năng Nạp/Rút khác)
            response = await asyncio.to_thread(make_request)
            
            if response.status_code != 200:
                return f"❌ Máy chủ Google từ chối ({response.status_code}):\n{response.text}"
            
            data = response.json()
            try:
                # Bóc tách câu trả lời từ Google
                bot_reply = data['candidates'][0]['content']['parts'][0]['text']
                return bot_reply
            except KeyError:
                return f"❌ Không đọc được dữ liệu JSON từ Google:\n{response.text}"
                
        except Exception as e:
            return f"❌ Mất kết nối tới Google AI: {str(e)}"

# Khởi tạo đối tượng
portfolio_ai = PortfolioAI()
