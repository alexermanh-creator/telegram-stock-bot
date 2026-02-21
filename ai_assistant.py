import os
import asyncio
import google.generativeai as genai

# Lấy API Key từ biến môi trường Railway
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.model = None
        if GEMINI_KEY:
            try:
                genai.configure(api_key=GEMINI_KEY)
                # Sử dụng tên model chuẩn để SDK tự khớp API v1 ổn định
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                print(f"Lỗi cấu hình AI: {e}")

    async def get_advice(self, user_query, s):
        if not self.model:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY trên Railway."
        
        # Xây dựng ngữ cảnh dựa trên dữ liệu thật từ main.py gửi sang
        prompt = (
            f"Bạn là chuyên gia tài chính. Dữ liệu thực tế của tôi:\n"
            f"- Tổng tài sản: {int(s['total_val']):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s['total_lai_pct']:.2f}%\n"
            f"- Crypto: {int(s['details']['Crypto']['hien_co']):,} VNĐ\n"
            f"- Chứng khoán: {int(s['details']['Stock']['hien_co']):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Trả lời: Ngắn gọn, chuyên nghiệp, xưng hô 'tôi' và 'bạn'."
        )

        try:
            # Xử lý không đồng bộ để bot không bị treo
            response = await asyncio.to_thread(self.model.generate_content, prompt)
            return response.text
        except Exception as e:
            return f"❌ Lỗi AI: {str(e)}"

# Khởi tạo đối tượng toàn cục
portfolio_ai = PortfolioAI()