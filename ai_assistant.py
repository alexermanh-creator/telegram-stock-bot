import os
import asyncio
import google.generativeai as genai

# Lấy API Key từ biến môi trường
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.primary_model_name = 'gemini-1.5-flash'
        self.fallback_model_name = 'gemini-1.5-flash-latest'
        self.legacy_model_name = 'gemini-pro'
        
        if GEMINI_KEY:
            try:
                genai.configure(api_key=GEMINI_KEY)
            except Exception as e:
                print(f"Lỗi cấu hình AI: {e}")

    async def get_advice(self, user_query, s):
        if not GEMINI_KEY:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY trên Railway."
        
        # Xây dựng ngữ cảnh từ dữ liệu thật của bạn
        prompt = (
            f"Bạn là trợ lý tài chính cá nhân. Dữ liệu danh mục hiện tại:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"- Chứng khoán: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"Câu hỏi của người dùng: {user_query}\n"
            f"Yêu cầu: Trả lời ngắn gọn, chuyên nghiệp, đưa ra lời khuyên nếu cần."
        )

        try:
            # Lần thử 1: Gọi model chính
            model = genai.GenerativeModel(self.primary_model_name)
            response = await asyncio.to_thread(model.generate_content, prompt)
            return response.text
            
        except Exception as e:
            error_msg = str(e)
            # Nếu gặp lỗi 404, kích hoạt cơ chế dự phòng
            if "404" in error_msg or "not found" in error_msg:
                try:
                    # Lần thử 2: Gọi model có hậu tố -latest
                    fallback_model = genai.GenerativeModel(self.fallback_model_name)
                    response = await asyncio.to_thread(fallback_model.generate_content, prompt)
                    return response.text
                except:
                    try:
                        # Lần thử 3: Gọi model gemini-pro (model ổn định cũ)
                        legacy_model = genai.GenerativeModel(self.legacy_model_name)
                        response = await asyncio.to_thread(legacy_model.generate_content, prompt)
                        return response.text
                    except Exception as fallback_err:
                        return f"❌ Lỗi AI (Đã thử mọi model dự phòng): {fallback_err}"
            
            # Nếu không phải lỗi 404 thì báo lỗi gốc
            return f"❌ Lỗi kết nối AI: {error_msg}"

# Khởi tạo đối tượng
portfolio_ai = PortfolioAI()
