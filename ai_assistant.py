import os
import asyncio
import requests

# Lấy Key từ Railway Variables
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        self.model_url = None

    def get_dynamic_model_url(self):
        """Tự động quét và tìm đường link model Flash miễn phí mới nhất của Google"""
        if self.model_url:
            return self.model_url
        
        try:
            # 1. Quét danh sách các model Google đang cho phép API Key này dùng
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            response = requests.get(list_url, timeout=10)
            response.raise_for_status()
            models_data = response.json().get('models', [])
            
            # 2. Lọc ra các model hỗ trợ chat
            valid_models = [
                m['name'] for m in models_data 
                if 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            
            # 3. Ưu tiên tìm dòng "flash" (vì dòng này Google cho dùng miễn phí rất nhiều)
            # Không quan tâm nó là 1.5, 2.0 hay 3.0, cứ có 'flash' là lấy.
            target_model = None
            flash_models = [m for m in valid_models if 'flash' in m.lower()]
            
            if flash_models:
                target_model = flash_models[0] # Lấy model flash đầu tiên tìm được
            elif valid_models:
                target_model = valid_models[0] # Nếu xui quá không có flash, lấy tạm model khả dụng đầu tiên
                
            if target_model:
                print(f"✅ Đã dò radar thành công. Model đang dùng: {target_model}")
                # Ráp đường link hoàn chỉnh
                self.model_url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={self.api_key}"
                return self.model_url
            else:
                return None
        except Exception as e:
            print(f"❌ Lỗi dò radar model: {e}")
            # Nếu radar hỏng do mạng, dùng tên dự phòng thế hệ mới
            return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"

    async def get_advice(self, user_query, s):
        if not self.api_key:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY."
        
        # Lấy URL linh hoạt thay vì bịa tên cố định
        url = self.get_dynamic_model_url()
        if not url:
            return "❌ API Key của bạn không có quyền truy cập vào bất kỳ model nào của Google."

        prompt_text = (
            f"Bạn là chuyên gia tư vấn tài chính. Dữ liệu của tôi:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"- Chứng khoán: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Yêu cầu: Trả lời ngắn gọn, thông minh bằng văn bản thuần túy, TUYỆT ĐỐI KHÔNG dùng ký tự Markdown (*, #)."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {"temperature": 0.7}
        }
        headers = {'Content-Type': 'application/json'}

        def fetch_google_api():
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=15)
                response.raise_for_status() 
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            except requests.exceptions.HTTPError as err:
                return f"❌ Google từ chối truy cập (Mã {err.response.status_code}):\n{err.response.text}"
            except Exception as e:
                return f"❌ Lỗi đường truyền: {str(e)}"

        try:
            ai_reply = await asyncio.wait_for(asyncio.to_thread(fetch_google_api), timeout=15.0)
            return ai_reply
        except asyncio.TimeoutError:
            return "⏳ Máy chủ AI Google đang quá tải. Bạn hãy thử lại sau nhé!"
        except Exception as e:
            return f"❌ Lỗi xử lý luồng AI: {str(e)}"

# Khởi tạo instance
portfolio_ai = PortfolioAI()
