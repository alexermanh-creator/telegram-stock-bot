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
                # Khởi tạo model chuẩn
                self.model = genai.GenerativeModel('gemini-1.5-flash')
            except Exception as e:
                print(f"Lỗi khởi tạo AI: {e}")

    async def get_advice(self, user_query, s):
        if not self.model:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY trên Railway."
        
        # Ngữ cảnh dữ liệu gửi sang AI
        prompt = (
            f"Bạn là chuyên gia tài chính. Dữ liệu thực tế của tôi:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"- Chứng khoán: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Hãy trả lời bằng tiếng Việt, phân tích ngắn gọn và thông minh."
        )

        try:
            # Bọc luồng gọi AI trong asyncio.wait_for với thời gian chờ tối đa 15 giây
            response = await asyncio.wait_for(
                asyncio.to_thread(self.model.generate_content, prompt),
                timeout=15.0
            )
            return response.text
        except asyncio.TimeoutError:
            # PHẢN HỒI KHI AI KHÔNG TRẢ LỜI (QUÁ TẢI)
            return "⏳ Máy chủ AI của Google hiện đang quá tải và không phản hồi kịp. Bạn vui lòng thử lại sau nhé!"
        except Exception as e:
            return f"❌ Lỗi AI: {str(e)}"

# Khởi tạo instance
portfolio_ai = PortfolioAI()
