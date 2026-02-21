import os
import asyncio
import google.generativeai as genai

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.model = None
        if GEMINI_KEY:
            try:
                genai.configure(api_key=GEMINI_KEY)
                # Chỉ dùng duy nhất model chuẩn mới nhất. TUYỆT ĐỐI không lùi về gemini-pro.
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                print(f"Lỗi khởi tạo AI: {e}")

    async def get_advice(self, user_query, s):
        if not self.model:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY hoặc API Key bị lỗi."
        
        prompt = (
            f"Bạn là chuyên gia tư vấn tài chính. Dữ liệu của tôi:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"- Chứng khoán: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Yêu cầu QUAN TRỌNG: Trả lời ngắn gọn, thông minh bằng văn bản thuần túy. TUYỆT ĐỐI KHÔNG dùng các ký tự đặc biệt như dấu sao (*), thăng (#) hay in đậm."
        )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(self.model.generate_content, prompt),
                timeout=15.0
            )
            return response.text
        except asyncio.TimeoutError:
            return "⏳ Máy chủ AI Google đang quá tải (chờ quá 15s). Bạn hãy thử lại sau nhé!"
        except Exception as e:
            # Nếu vẫn báo lỗi, bot sẽ gợi ý bạn đổi API Key mới
            return f"❌ Lỗi từ Google AI: {str(e)}\n\n👉 Gợi ý: API Key của bạn có thể đã cũ hoặc bị khóa. Hãy vào Google AI Studio tạo 1 Key mới và cập nhật lại nhé!"

portfolio_ai = PortfolioAI()
