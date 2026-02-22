import os
import asyncio
import requests
import datetime
import time

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        self.model_url = None
        self.chat_history = [] 

    def get_dynamic_model_url(self):
        if self.model_url: return self.model_url
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            response = requests.get(list_url, timeout=10)
            valid_models = [m['name'] for m in response.json().get('models', []) if 'generateContent' in m.get('supportedGenerationMethods', [])]
            target = next((m for m in valid_models if 'flash' in m.lower()), valid_models[0] if valid_models else None)
            if target: self.model_url = f"https://generativelanguage.googleapis.com/v1beta/{target}:generateContent?key={self.api_key}"
            return self.model_url
        except: return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"

    # NÂNG CẤP NHỎ Ở ĐÂY: Nhận thêm full_asset_data
    async def get_advice(self, user_query, full_asset_data):
        if not self.api_key: return "lỗi: thiếu gemini_api_key trong biến môi trường."
        url = self.get_dynamic_model_url()
        
        # NÂNG CẤP NHỎ Ở ĐÂY: Gắn dữ liệu vào câu prompt gốc của bạn
        system_context = (
            f"dữ liệu tài sản hiện tại: {full_asset_data}\n"
            f"nhiệm vụ: tư vấn tối ưu tương lai. tập trung vào tái cơ cấu tỷ trọng để giảm rủi ro và đạt mục tiêu nhanh nhất. "
            f"phản hồi ngắn, gắt, kỷ luật, không markdown đặc biệt.\n"
            f"câu hỏi: {user_query}"
        )

        # Trí nhớ hội thoại rút gọn (giữ 4 tin nhắn gần nhất để siêu tiết kiệm)
        if len(self.chat_history) > 4: self.chat_history = self.chat_history[-4:]
        api_contents = self.chat_history.copy()
        api_contents.append({"role": "user", "parts": [{"text": system_context}]})

        def fetch_google_api():
            for attempt in range(2):
                try:
                    res = requests.post(url, json={"contents": api_contents, "generationConfig": {"temperature": 0.4}}, timeout=20)
                    res.raise_for_status()
                    return res.json()['candidates'][0]['content']['parts'][0]['text']
                except Exception as e:
                    if "429" in str(e) and attempt == 0:
                        time.sleep(5)
                        continue
                    return f"lỗi api: {str(e)}"

        ai_reply = await asyncio.to_thread(fetch_google_api)
        if not ai_reply.startswith("lỗi"):
            # Lưu trí nhớ dạng rút gọn
            self.chat_history.append({"role": "user", "parts": [{"text": user_query}]})
            self.chat_history.append({"role": "model", "parts": [{"text": ai_reply}]})
        return ai_reply

portfolio_ai = PortfolioAI()
