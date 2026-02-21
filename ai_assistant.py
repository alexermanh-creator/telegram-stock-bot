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
                # Tự động quét model, ưu tiên gemini-1.5-flash, nếu không có thì dùng gemini-pro
                models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
                target_model = 'models/gemini-pro' # Dự phòng mặc định
                
                for m in models:
                    if '1.5-flash' in m:
                        target_model = m
                        break
                        
                # Bỏ tiền tố 'models/' để khớp SDK mới
                target_model = target_model.replace('models/', '')
                self.model = genai.GenerativeModel(target_model)
                print(f"✅ Đã kết nối AI với model: {target_model}")
            except Exception as e:
                print(f"❌ Lỗi khởi tạo AI: {e}")

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
            return f"❌ Lỗi kết nối Google AI: {str(e)}"

portfolio_ai = PortfolioAI()
