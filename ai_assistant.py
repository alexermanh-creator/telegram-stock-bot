import os
import asyncio
import google.generativeai as genai

# Lấy Key từ Railway Variables
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

class PortfolioAI:
    def __init__(self):
        self.model = None
        self.used_model_name = "Chưa xác định"
        
        if GEMINI_KEY:
            try:
                genai.configure(api_key=GEMINI_KEY)
                
                # 1. TỰ ĐỘNG DÒ TÌM: Lấy danh sách các model mà API Key của bạn được phép dùng
                available_models = [
                    m.name for m in genai.list_models() 
                    if 'generateContent' in m.supported_generation_methods
                ]
                
                # 2. CHỌN MODEL THÔNG MINH
                if available_models:
                    target_model = available_models[0] # Mặc định lấy model đầu tiên mà Google cho phép
                    
                    # Ưu tiên tìm các dòng model 1.5 mới nhất nếu có trong danh sách
                    flash_models = [m for m in available_models if '1.5-flash' in m]
                    pro_models = [m for m in available_models if '1.5-pro' in m]
                    
                    if flash_models:
                        target_model = flash_models[0]
                    elif pro_models:
                        target_model = pro_models[0]
                        
                    # Cắt bỏ chữ 'models/' ở đầu đi để tránh bị lỗi SDK
                    self.used_model_name = target_model.replace('models/', '')
                    
                    # Khởi tạo model bằng cái tên vừa quét được
                    self.model = genai.GenerativeModel(self.used_model_name)
                    print(f"✅ AI đã kết nối thành công với model: {self.used_model_name}")
                else:
                    print("❌ Lỗi: API Key của bạn không có quyền truy cập vào bất kỳ model AI nào.")
                    
            except Exception as e:
                print(f"❌ Lỗi khởi tạo hệ thống AI: {e}")

    async def get_advice(self, user_query, s):
        if not self.model:
            return "⚠️ Chưa cấu hình GEMINI_API_KEY hợp lệ hoặc API Key không có quyền truy cập."
        
        # Ngữ cảnh dữ liệu gửi sang AI
        prompt = (
            f"Bạn là chuyên gia tư vấn tài chính. Dữ liệu thực tế của tôi:\n"
            f"- Tổng tài sản: {int(s.get('total_val', 0)):,} VNĐ\n"
            f"- Lãi/Lỗ tổng: {s.get('total_lai_pct', 0):.2f}%\n"
            f"- Crypto: {int(s.get('details', {}).get('Crypto', {}).get('hien_co', 0)):,} VNĐ\n"
            f"- Chứng khoán: {int(s.get('details', {}).get('Stock', {}).get('hien_co', 0)):,} VNĐ\n"
            f"Câu hỏi: {user_query}\n"
            f"Yêu cầu: Hãy trả lời bằng tiếng Việt, phân tích ngắn gọn, thông minh và thân thiện."
        )

        try:
            # Chạy trong luồng phụ và giới hạn thời gian chờ tối đa 15 giây (chống treo)
            response = await asyncio.wait_for(
                asyncio.to_thread(self.model.generate_content, prompt),
                timeout=15.0
            )
            return response.text
        except asyncio.TimeoutError:
            return f"⏳ AI ({self.used_model_name}) đang xử lý quá lâu do máy chủ Google quá tải. Vui lòng thử lại sau!"
        except Exception as e:
            return f"❌ Lỗi gọi AI ({self.used_model_name}): {str(e)}"

# Khởi tạo đối tượng
portfolio_ai = PortfolioAI()
