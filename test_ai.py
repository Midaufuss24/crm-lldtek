import google.generativeai as genai

# Dán API Key của bạn vào đây
API_KEY = "AIzaSyCbySj19PNjkVHcpCYR5U8OnrjGM2cb3AQ"

genai.configure(api_key=API_KEY)

print("--- ĐANG KIỂM TRA KẾT NỐI VÀ DANH SÁCH MODEL ---")

try:
    # 1. Liệt kê các model khả dụng
    available_models = []
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            print(f"✅ Tìm thấy model: {m.name}")

    if not available_models:
        print("❌ Không tìm thấy model nào khả dụng cho Key này.")
    else:
        # 2. Chạy thử một câu lệnh đơn giản với model đầu tiên tìm thấy
        target_model = available_models[0] 
        print(f"\n🚀 Đang chạy thử với model: {target_model}...")
        
        model = genai.GenerativeModel(target_model)
        response = model.generate_content("Xin chào, bạn có hoạt động không?")
        
        print("\n🤖 AI trả lời:")
        print(response.text)
        print("\n✨ KẾT NỐI THÀNH CÔNG!")

except Exception as e:
    print(f"\n❌ ĐÃ XẢY RA LỖI: {str(e)}")