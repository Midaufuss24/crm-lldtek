import webview
import requests
import sys
import time

# =========================================================
# CẤU HÌNH ĐƯỜNG DẪN (Bạn sửa lại cho đúng IP và Link Cloud)
# =========================================================
LOCAL_URL = "http://172.16.0.86:8503"          # IP máy của bạn (Server Local)
CLOUD_URL = "https://lldtek-crm.streamlit.app" # Link trên Cloud

def check_local_server_alive(url, timeout=1.5):
    """
    Hàm kiểm tra xem Server Local có sống không.
    Timeout = 1.5s (Nếu quá 1.5s không trả lời thì coi như tắt)
    """
    try:
        # Gửi thử 1 request nhẹ
        response = requests.head(url, timeout=timeout)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False

def main():
    # 1. Kiểm tra trạng thái Server
    # print("Đang kiểm tra kết nối tới máy chủ...") # Dùng khi debug
    
    is_local_alive = check_local_server_alive(LOCAL_URL)
    
    if is_local_alive:
        final_url = LOCAL_URL
        window_title = "CRM - LLDTEK (Mode: Local High Speed 🚀)"
        # print("=> Đã kết nối Local!")
    else:
        final_url = CLOUD_URL
        window_title = "CRM - LLDTEK (Mode: Cloud Backup ☁️)"
        # print("=> Không thấy Local, chuyển sang Cloud!")

    # 2. Khởi tạo cửa sổ App
    webview.create_window(
        title=window_title,
        url=final_url,
        width=1200,
        height=800,
        confirm_close=True,
        resizable=True
    )
    
    # 3. Chạy App
    webview.start()

if __name__ == '__main__':
    main()