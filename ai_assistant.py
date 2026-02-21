import os
import asyncio
import requests
import sqlite3
import datetime

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
DB_FILE = 'portfolio.db'

class PortfolioAI:
    def __init__(self):
        self.api_key = GEMINI_KEY
        self.model_url = None
        # BỘ NHỚ TRONG: Lưu lại 5 vòng hội thoại gần nhất (10 tin nhắn)
        self.chat_history = [] 

    def get_dynamic_model_url(self):
        if self.model_url:
            return self.model_url
        try:
            list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}"
            response = requests.get(list_url, timeout=10)
            response.raise_for_status()
            models_data = response.json().get('models', [])
            valid_models = [m['name'] for m in models_data if 'generateContent' in m.get('supportedGenerationMethods', [])]
            
            target_model = None
            flash_models = [m for m in valid_models if 'flash' in m.lower()]
            if flash_models:
                target_model = flash_models[0] 
            elif valid_models:
                target_model = valid_models[0] 
                
            if target_model:
                self.model_url = f"https://generativelanguage.googleapis.com/v1beta/{target_model}:generateContent?key={self.api_key}"
                return self.model_url
            return None
        except Exception:
            return f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"

    def get_all_history(self):
        try:
            if not os.path.exists(DB_FILE):
                return "Chưa có dữ liệu."
            conn = sqlite3.connect(DB_FILE)
            rows = conn.execute("SELECT category, type, amount, date FROM transactions ORDER BY date ASC, id ASC").fetchall()
            conn.close()
            
            if not rows:
                return "Chưa có giao dịch nào."
            
            history_str = ""
            for r in rows:
                history_str += f"- Ngày {r[3]}: {r[1]} {int(r[2]):,} VNĐ (Danh mục: {r[0]})\n"
            return history_str
        except Exception as e:
            return f"Không thể đọc lịch sử do lỗi: {e}"

    async def get_advice(self, user_query, s):
        if not self.api_key:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY."
        
        url = self.get_dynamic_model_url()
        if not url:
            return "❌ API Key không hợp lệ."

        # 1. BƠM TẦM NHÌN VĨ MÔ (Thời gian thực)
        current_time = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        
        # Lấy lịch sử giao dịch
        all_txs = self.get_all_history()

        # 2. CHẾ ĐỘ STRESS TEST (Kích hoạt nếu câu hỏi có chứa từ khóa)
        stress_test_mode = ""
        query_lower = user_query.lower()
        if "test danh mục" in query_lower or "stress test" in query_lower or "khủng hoảng" in query_lower:
            stress_test_mode = (
                f"🚨 CHẾ ĐỘ STRESS TEST ĐƯỢC KÍCH HOẠT: Hãy giả lập kịch bản thiên nga đen (Black Swan) ngay ngày mai. "
                f"Giả sử Crypto sập 30% và Chứng khoán sập 15%. Hãy tính toán chính xác tổng tài sản sẽ bốc hơi bao nhiêu tiền. "
                f"Lượng tiền mặt hiện tại có đủ để trung bình giá không hay sẽ bị kẹt thanh khoản? Hãy dọa khách hàng một chút để họ tỉnh táo."
            )

        # 3. ĐỊNH HÌNH NHÂN CÁCH & BỐI CẢNH (CHỈ BƠM VÀO CÂU HỎI HIỆN TẠI)
        system_context = (
            f"ĐÓNG VAI: Bạn là một Wealth Manager khắt khe. Thời gian hiện tại là {current_time}, thị trường Việt Nam.\n"
            f"📊 DỮ LIỆU TÀI CHÍNH:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Mục tiêu: {int(s.get('target_asset', 0)):,} VNĐ ({s.get('progress', 0):.1f}%)\n"
            f"- Vốn thực nạp: {int(s.get('total_von', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ: {int(s.get('total_lai', 0)):,} VNĐ ({s.get('total_lai_pct', 0):.2f}%)\n"
            f"- Phân bổ:\n"
            f"  + Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"  + Stock: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"  + Tiền mặt: {int(s.get('details', {}).get('Cash', {}).get('hien_co', 0)):,} VNĐ\n\n"
            f"📈 TOÀN BỘ LỊCH SỬ DÒNG TIỀN:\n{all_txs}\n\n"
            f"{stress_test_mode}\n"
            f"QUY TẮC: Trả lời đi thẳng vào vấn đề dựa trên dữ liệu. Ghi nhớ các câu hỏi trước của tôi để đối đáp tự nhiên. "
            f"TUYỆT ĐỐI KHÔNG dùng ký tự đặc biệt (*, #, in đậm).\n"
            f"-----------------\n"
            f"CÂU HỎI CỦA TÔI: {user_query}"
        )

        # 4. XỬ LÝ TRÍ NHỚ HỘI THOẠI (Context Memory)
        # Chỉ giữ lại 8 tin nhắn gần nhất (4 vòng hội thoại) để tránh nặng bộ nhớ
        if len(self.chat_history) > 8:
            self.chat_history = self.chat_history[-8:]

        # Tạo danh sách nội dung gửi đi bao gồm: Lịch sử cũ + Câu hỏi mới (kèm ngữ cảnh)
        api_contents = self.chat_history.copy()
        api_contents.append({"role": "user", "parts": [{"text": system_context}]})

        payload = {
            "contents": api_contents,
            "generationConfig": {"temperature": 0.4}
        }
        headers = {'Content-Type': 'application/json'}

        def fetch_google_api():
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=25)
                response.raise_for_status() 
                return response.json()['candidates'][0]['content']['parts'][0]['text']
            except requests.exceptions.HTTPError as err:
                return f"❌ Lỗi từ Google (Mã {err.response.status_code}):\n{err.response.text}"
            except Exception as e:
                return f"❌ Lỗi đường truyền: {str(e)}"

        try:
            ai_reply = await asyncio.wait_for(asyncio.to_thread(fetch_google_api), timeout=25.0)
            
            # NẾU THÀNH CÔNG, LƯU LẠI VÀO TRÍ NHỚ
            if not ai_reply.startswith("❌"):
                self.chat_history.append({"role": "user", "parts": [{"text": user_query}]}) # Lưu câu hỏi gốc (không kèm data để đỡ rác)
                self.chat_history.append({"role": "model", "parts": [{"text": ai_reply}]})
                
            return ai_reply
        except asyncio.TimeoutError:
            return "⏳ Chuyên gia AI đang phân tích toàn bộ lịch sử và trí nhớ, quá trình này hơi lâu. Bạn thử lại nhé!"
        except Exception as e:
            return f"❌ Lỗi xử lý luồng AI: {str(e)}"

portfolio_ai = PortfolioAI()
