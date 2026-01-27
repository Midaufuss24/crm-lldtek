import subprocess
import requests
import os
import webbrowser
import sys
import time

# =========================================================
# 1. CẤU HÌNH (Sửa lại IP và Link Cloud của bạn nếu cần)
# =========================================================
LOCAL_URL = "http://172.16.0.86:8503"
CLOUD_URL = "https://lldtek-crm.streamlit.app"

def check_local_alive(url):
    """
    Kiểm tra xem Server Local có sống không.
    Timeout 1 giây để phản hồi nhanh.
    """
    try:
        requests.head(url, timeout=1.0)
        return True
    except:
        return False

def find_browser_info():
    """
    Tìm đường dẫn trình duyệt và trả về: (Đường dẫn, Loại trình duyệt)
    Ưu tiên: Chrome -> Edge -> Firefox
    """
    browser_map = {
        "chrome": [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expanduser(r"~\AppData\Local\Google\Chrome\Application\chrome.exe")
        ],
        "edge": [
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        ],
        "firefox": [
            r"C:\Program Files\Mozilla Firefox\firefox.exe",
            r"C:\Program Files (x86)\Mozilla Firefox\firefox.exe"
        ]
    }

    for browser_type, paths in browser_map.items():
        for path in paths:
            if os.path.exists(path):
                return path, browser_type
    
    return None, None

def main():
    print("------------------------------------------------")
    print("    🚀 CRM LLDTEK LAUNCHER SYSTEM")
    print("------------------------------------------------")

    # 1. KIỂM TRA MẠNG ĐỂ CHỌN SERVER
    if check_local_alive(LOCAL_URL):
        final_url = LOCAL_URL
        print(f"✅ TRẠNG THÁI: KẾT NỐI LOCALHOST")
        print(f"🔗 URL: {final_url}")
    else:
        final_url = CLOUD_URL
        print(f"☁️ TRẠNG THÁI: KẾT NỐI CLOUD STREAMLIT")
        print(f"🔗 URL: {final_url}")

    # 2. TÌM TRÌNH DUYỆT
    browser_path, browser_type = find_browser_info()

    if browser_path:
        print(f"🔎 Trình duyệt: {browser_type.upper()}")
        print(f"📂 Path: {browser_path}")
        print("🚀 Đang khởi động ứng dụng...")

        # 3. MỞ APP THEO TỪNG LOẠI TRÌNH DUYỆT
        if browser_type in ["chrome", "edge"]:
            # Chrome và Edge dùng chung cờ --app để ẩn thanh địa chỉ
            subprocess.Popen([browser_path, f"--app={final_url}", "--start-maximized"])
        
        elif browser_type == "firefox":
            # Firefox không hỗ trợ --app chuẩn, dùng -new-window
            subprocess.Popen([browser_path, "-new-window", final_url])
            
    else:
        # Fallback: Nếu máy quá cũ không có 3 trình duyệt trên
        print("⚠️ Không tìm thấy Chrome/Edge/Firefox. Mở trình duyệt mặc định...")
        webbrowser.open(final_url)

if __name__ == '__main__':
    main()