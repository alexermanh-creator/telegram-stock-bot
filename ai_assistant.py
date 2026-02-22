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
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            res = requests.get(url, timeout=10)
            if res.status_code == 200:
                models = res.json().get('models', [])
                flash_models = [m['name'] for m in models if 'generateContent' in m['supportedGenerationMethods'] and 'flash' in m['name']]
                other_models = [m['name'] for m in models if 'generateContent' in m['supportedGenerationMethods'] and 'flash' not in m['name']]
                return flash_models + other_models
        except: pass
        return ["models/gemini-1.5-flash", "models/gemini-2.0-flash", "models/gemini-1.5-pro"]

    async def get_advice(self, user_query, full_asset_data):
        if not self.api_key: return "❌ Lỗi: Thiếu GEMINI_API_KEY trong biến môi trường."
        
        if not self.available_models:
            self.available_models = self.fetch_available_models()

        # NÂNG CẤP: System context cụ thể hơn để AI phân tích số liệu thực tế
        system_context = (
            f"BỐI CẢNH TÀI SẢN CHI TIẾT:\n{full_asset_data}\n\n"
            f"VAI TRÒ: Bạn là CFO kỷ luật thép. Hãy soi kỹ bảng tài sản trên.\n"
            f"NHIỆM VỤ: Phân tích tỷ trọng, lãi lỗ từng nhóm. Cảnh báo rủi ro dựa trên con số.\n"
            f"PHONG CÁCH: Trả lời ngắn, gắt, dựa trực tiếp trên số liệu. Không nói suông.\n"
            f"CÂU HỎI: {user_query}"
        )

        if len(self.chat_history) > 4: self.chat_history = self.chat_history[-4:]
        api_contents = self.chat_history.copy()
        api_contents.append({"role": "user", "parts": [{"text": system_context}]})

        def try_all_models():
            for model_path in self.available_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={self.api_key}"
                try:
                    res = requests.post(url, json={"contents": api_contents, "generationConfig": {"temperature": 0.5}}, timeout=25)
                    if res.status_code == 200:
                        data = res.json()
                        if 'candidates' in data and data['candidates'][0]['content']['parts'][0]['text']:
                            return data['candidates'][0]['content']['parts'][0]['text']
                    continue 
                except:
                    continue
            return "❌ Tất cả model Gemini đang bận. Thử lại sau ít phút."

        ai_reply = await asyncio.to_thread(try_all_models)
        
        if not ai_reply.startswith("❌"):
            self.chat_history.append({"role": "user", "parts": [{"text": user_query}]})
            self.chat_history.append({"role": "model", "parts": [{"text": ai_reply}]})
        return ai_reply

portfolio_ai = PortfolioAI()
