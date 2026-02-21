import os
import asyncio
import google.generativeai as genai

# Lấy Key từ Railway Variables
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.model = None
        if GEMINI_KEY:
            try:
                genai.configure(api_key=GEMINI_KEY)
                # Sử dụng model chuẩn
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                print(f"Lỗi khởi tạo AI: {e}")

    async def get_advice(self, user_query, s):
        if not self.model:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY trên Railway."
        
        # Ngữ cảnh dữ liệu gửi sang AI
        prompt = (
            f"Bạn là chuyên gia tài chính. Dữ liệu thực tế của tôi:\n"
            f"- Tổng tài sản: {int(s['total_val']):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s['total_lai_pct']:.2f}%\n"
            f"- Crypto: {int(s['details']['Crypto']['hien_co']):,} VNĐ\n"
            f"- Chứng khoán: {int(s['details']['Stock']['hien_co']):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Hãy trả lời bằng tiếng Việt, phân tích ngắn gọn và thông minh."
        )

        try:
            # Chạy trong thread riêng để không block Bot Telegram
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text
        except Exception as e:
            # In lỗi chi tiết nếu vẫn bị 404
            return f"❌ Lỗi AI: {str(e)}"

# Khởi tạo instance
portfolio_ai = PortfolioAI()
