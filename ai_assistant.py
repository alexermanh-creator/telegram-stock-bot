import os
import asyncio
import requests
import time

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        self.chat_history = []
        self.available_models = []

    def fetch_available_models(self):
        """Lấy danh sách các model thực tế mà API Key của bạn được phép dùng"""
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                models = res.json().get('models', [])
                # Ưu tiên các model Flash vì tốc độ nhanh và hạn mức cao
                flash_models = [m['name'] for m in models if 'generateContent' in m['supportedGenerationMethods'] and 'flash' in m['name']]
                other_models = [m['name'] for m in models if 'generateContent' in m['supportedGenerationMethods'] and 'flash' not in m['name']]
                return flash_models + other_models
        except: pass
        # Fallback nếu không lấy được danh sách
        return ["models/gemini-1.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-pro"]

    async def get_advice(self, user_query, full_asset_data):
        if not self.api_key: return "❌ Lỗi: Thiếu GEMINI_API_KEY trong biến môi trường."
        
        # Cập nhật danh sách model nếu trống
        if not self.available_models:
            self.available_models = self.fetch_available_models()

        system_context = (
            f"dữ liệu tài sản hiện tại: {full_asset_data}\n"
            f"nhiệm vụ: tư vấn tối ưu tương lai. tập trung vào tái cơ cấu tỷ trọng để giảm rủi ro và đạt mục tiêu nhanh nhất. "
            f"phản hồi ngắn, gắt, kỷ luật, không markdown đặc biệt.\n"
            f"QUAN TRỌNG: Ở cuối câu trả lời, BẮT BUỘC phải xuống dòng và liệt kê đúng 3 gợi ý (đánh số 1, 2, 3) về các câu hỏi tiếp theo mà tôi nên hỏi bạn để tối ưu tài sản.\n"
            f"câu hỏi: {user_query}"
        )

        if len(self.chat_history) > 4: self.chat_history = self.chat_history[-4:]
        api_contents = self.chat_history.copy()
        api_contents.append({"role": "user", "parts": [{"text": system_context}]})

        def try_all_models():
            # Thử lần lượt các model trong danh sách khả dụng
            for model_path in self.available_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={self.api_key}"
                try:
                    res = requests.post(url, json={"contents": api_contents, "generationConfig": {"temperature": 0.5}}, timeout=25)
                    
                    if res.status_code == 200:
                        data = res.json()
                        if 'candidates' in data and data['candidates'][0]['content']['parts'][0]['text']:
                            return data['candidates'][0]['content']['parts'][0]['text']
                    
                    # Nếu gặp lỗi 429 (hết lượt) hoặc các lỗi khác, chuyển sang model tiếp theo
                    continue 
                except:
                    continue
            return "❌ Hiện tại tất cả model Gemini đều đang bận hoặc hết hạn mức. Vui lòng thử lại sau vài phút."

        ai_reply = await asyncio.to_thread(try_all_models)
        
        if not ai_reply.startswith("❌"):
            self.chat_history.append({"role": "user", "parts": [{"text": user_query}]})
            self.chat_history.append({"role": "model", "parts": [{"text": ai_reply}]})
        return ai_reply

portfolio_ai = PortfolioAI()

