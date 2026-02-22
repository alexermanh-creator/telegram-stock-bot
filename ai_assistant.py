import os
import asyncio
import requests
import datetime
import time

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        # Danh sách ưu tiên: Thử 2.0 trước, rồi đến 1.5 Flash, rồi đến 1.5 Pro
        self.model_pool = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-flash-8b",
            "gemini-1.5-pro"
        ]
        self.current_model_idx = 0
        self.chat_history = [] 

    def get_url(self, model_name):
        return f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={self.api_key}"

    async def get_advice(self, user_query, full_asset_data):
        if not self.api_key: return "lỗi: thiếu gemini_api_key trong biến môi trường."
        
        system_context = (
            f"Bối cảnh tài chính:\n{full_asset_data}\n\n"
            f"Vai trò: CFO kỷ luật thép. Phân tích gắt, ngắn gọn, tập trung con số.\n"
            f"Câu hỏi: {user_query}"
        )

        if len(self.chat_history) > 4: self.chat_history = self.chat_history[-4:]
        api_contents = self.chat_history.copy()
        api_contents.append({"role": "user", "parts": [{"text": system_context}]})

        def fetch_with_fallback():
            # Thử lần lượt các model trong pool
            for i in range(len(self.model_pool)):
                model_name = self.model_pool[self.current_model_idx]
                url = self.get_url(model_name)
                try:
                    res = requests.post(url, json={"contents": api_contents, "generationConfig": {"temperature": 0.4}}, timeout=20)
                    
                    if res.status_code == 429:
                        # Nếu hết hạn (429), chuyển sang model tiếp theo trong danh sách
                        self.current_model_idx = (self.current_model_idx + 1) % len(self.model_pool)
                        continue 
                    
                    res.raise_for_status()
                    return res.json()['candidates'][0]['content']['parts'][0]['text']
                except Exception as e:
                    # Nếu lỗi khác hoặc hết danh sách, thử chuyển model tiếp
                    self.current_model_idx = (self.current_model_idx + 1) % len(self.model_pool)
                    if i == len(self.model_pool) - 1:
                        return f"lỗi toàn bộ model: {str(e)}"
                    continue
            return "lỗi: không có model nào phản hồi."

        ai_reply = await asyncio.to_thread(fetch_with_fallback)
        
        if not ai_reply.startswith("lỗi"):
            self.chat_history.append({"role": "user", "parts": [{"text": user_query}]})
            self.chat_history.append({"role": "model", "parts": [{"text": ai_reply}]})
        return ai_reply

portfolio_ai = PortfolioAI()
