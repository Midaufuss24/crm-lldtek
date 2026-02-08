import requests
import time
import sys
import subprocess # Thư viện để gọi lệnh Windows

# --- CẤU HÌNH ---
# 1. IP Máy chủ Local (Port 8501)
LOCAL_URL = "http://172.16.0.86:8501"

# 2. Link Cloud (Dự phòng)
CLOUD_URL = "https://crm-lldtek.streamlit.app"

def check_server(url):
    """Ping kiểm tra xem server có sống không"""
    try:
        requests.get(url, timeout=1) 
        return True
    except:
        return False

def open_app_mode(url):
    """Mở URL dưới dạng Cửa sổ Ứng dụng độc lập (No tabs, no address bar)"""
    try:
        # Lệnh này yêu cầu Windows mở Chrome ở chế độ APP
        # Nếu máy không có Chrome, nó sẽ không chạy (nhưng 99% máy đều có)
        subprocess.Popen(f'start chrome --app={url}', shell=True)
    except Exception as e:
        # Dự phòng: Nếu lỗi thì mở trình duyệt thường
        import webbrowser
        webbrowser.open(url)

def main():
    # In ra màn hình console (nếu có) để debug
    print("--- LLDTEK CRM LAUNCHER (APP MODE) ---")
    
    target_url = CLOUD_URL # Mặc định
    
    # Logic kiểm tra Server
    if check_server(LOCAL_URL):
        print(f"✅ Local Server ONLINE: {LOCAL_URL}")
        target_url = LOCAL_URL
    else:
        print(f"☁️ Local OFF. Switching to CLOUD: {CLOUD_URL}")
    
    print(f"🚀 Opening App Window: {target_url}")
    time.sleep(1)
    
    # --- THAY ĐỔI QUAN TRỌNG Ở ĐÂY ---
    open_app_mode(target_url) 

if __name__ == '__main__':
    main()