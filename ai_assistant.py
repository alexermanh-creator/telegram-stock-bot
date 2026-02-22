import os
import asyncio
import requests

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        self.chat_history = []
        self.models = ["models/gemini-1.5-flash", "models/gemini-2.0-flash"]

    async def get_advice(self, user_query, full_asset_data):
        if not self.api_key: return "Thiếu API Key."
        
        system_context = f"Dữ liệu: {full_asset_data}\nVai trò: CFO gắt gao. Phân tích số liệu, không nói suông.\nCâu hỏi: {user_query}"
        
        for model_path in self.models:
            url = f"https://generativelanguage.googleapis.com/v1beta/{model_path}:generateContent?key={self.api_key}"
            try:
                res = requests.post(url, json={"contents": [{"role": "user", "parts": [{"text": system_context}]}]}, timeout=25)
                if res.status_code == 200:
                    return res.json()['candidates'][0]['content']['parts'][0]['text']
            except: continue
        return "Tất cả model bận, thử lại sau."

portfolio_ai = PortfolioAI()
