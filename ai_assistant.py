import os
import asyncio
import requests

# Lấy Key từ Railway Variables
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        self.model_name = None # Sẽ tự động tìm

    def get_valid_model(self):
        if self.model_name:
            return self.model_name
            
        try:
            # 1. Gọi Google để lấy danh sách model mà API Key này được phép dùng
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            models = response.json().get('models', [])
            
            # Lọc ra các model hỗ trợ sinh văn bản
            valid_models = [m['name'] for m in models if 'generateContent' in m.get('supportedGenerationMethods', [])]
            
            # 2. Tìm model phù hợp nhất
            target = None
            # Ưu tiên số 1: Gemini 1.5 Flash mới nhất
            for m in valid_models:
                if 'gemini-1.5-flash' in m:
                    target = m
                    break
            
            # Nếu không có Flash, tìm bản Pro hoặc bản cũ
            if not target:
                for m in valid_models:
                    if 'gemini-1.5-pro' in m or 'gemini-pro' in m:
                        target = m
                        break
            
            if target:
                self.model_name = target
                print(f"✅ Đã dò thành công model: {target}")
                return target
            else:
                return None
        except Exception as e:
            print("❌ Lỗi khi quét danh sách model:", e)
            # Fallback nếu việc quét thất bại
            return "models/gemini-1.5-flash-latest"

    async def get_advice(self, user_query, s):
        if not self.api_key:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY trên Railway."
        
        # Tự động lấy cái tên model chuẩn xác nhất của Google
        model_to_use = self.get_valid_model()
        if not model_to_use:
            return "❌ API Key của bạn không có quyền truy cập vào các model ngôn ngữ của Gemini."

        prompt_text = (
            f"Bạn là chuyên gia tư vấn tài chính. Dữ liệu của tôi:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"- Chứng khoán: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Yêu cầu: Trả lời ngắn gọn, thông minh bằng văn bản thuần túy, TUYỆT ĐỐI KHÔNG dùng ký tự Markdown (*, #)."
        )

        # Cổng v1beta linh hoạt nhất, kết hợp với tên model vừa quét được
        url = f"https://generativelanguage.googleapis.com/v1beta/{model_to_use}:generateContent?key={self.api_key}"
        
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
                return f"❌ Google từ chối model ({model_to_use}): Mã lỗi {err.response.status_code}\nChi tiết: {err.response.text}"
            except Exception as e:
                return f"❌ Lỗi đường truyền: {str(e)}"

        try:
            ai_reply = await asyncio.to_thread(fetch_google_api)
            return ai_reply
        except Exception as e:
            return f"❌ Lỗi xử lý luồng AI: {str(e)}"

portfolio_ai = PortfolioAI()
