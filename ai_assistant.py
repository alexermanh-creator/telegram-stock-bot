import google.generativeai as genai
import os

class PortfolioAI:
    def __init__(self, api_key):
        # Giữ nguyên cấu trúc khởi tạo và model flash để tối ưu tốc độ/chi phí
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.chat_history = []
        
        # Nâng cấp hướng dẫn hệ thống để AI "soi" bảng tài sản gắt hơn
        self.system_instructions = (
            "Bạn là một chuyên gia Quản trị rủi ro tài chính (CFO) với phong cách kỷ luật thép, đanh thép.\n"
            "Nhiệm vụ: Phân tích bảng dữ liệu TÀI SẢN CHI TIẾT (vốn, lãi, lỗ, tỷ trọng) của người dùng.\n"
            "QUY TẮC PHÂN TÍCH:\n"
            "1. Tỷ trọng: Nếu một loại tài sản chiếm quá 50%, cảnh báo rủi ro tập trung.\n"
            "2. Kỷ luật: Nếu lỗ > 20% mà chưa cắt, hãy phê bình gay gắt.\n"
            "3. Thanh khoản: Nếu Tiền mặt quá thấp, cảnh báo rủi ro mất khả năng chi trả.\n"
            "4. Phong cách: Ngắn gọn, tập trung vào con số thực tế, không nói sáo rỗng."
        )

    async def get_advice(self, user_msg, detailed_assets_context):
        """
        detailed_assets_context: Chuỗi dữ liệu bóc tách chi tiết từ bảng Tài sản.
        """
        # Hợp nhất chỉ dẫn hệ thống, dữ liệu tài sản và câu hỏi của người dùng
        prompt = (
            f"{self.system_instructions}\n\n"
            f"DỮ LIỆU TÀI SẢN CHI TIẾT HIỆN TẠI:\n{detailed_assets_context}\n\n"
            f"CÂU HỎI CỦA NGƯỜI DÙNG: {user_msg}"
        )

        # GIỮ NGUYÊN TÍNH NĂNG CŨ: Chỉ nhớ tối đa 4 lượt hội thoại để tối ưu Gemini
        if len(self.chat_history) > 4:
            self.chat_history.pop(0)

        try:
            response = self.model.generate_content(prompt)
            # Lưu lịch sử để duy trì mạch hội thoại
            self.chat_history.append({"user": user_msg, "bot": response.text})
            return response.text
        except Exception as e:
            return f"❌ Lỗi AI: {str(e)}"

# Khởi tạo instance (giữ nguyên cách bạn đang gọi trong main.py)
portfolio_ai = PortfolioAI(os.environ.get("GEMINI_API_KEY"))
