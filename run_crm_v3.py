import requests
import time
import sys
import subprocess

# --- CẤU HÌNH DÙNG HOSTNAME (KHÔNG LO ĐỔI IP) ---
HOSTNAME = "DESKTOP-EK0CH97"
LOCAL_URL = f"http://{HOSTNAME}:8501"
CLOUD_URL = "https://crm-lldtek.streamlit.app"

def check_server(url):
    try:
        # Thử ping vào Hostname
        requests.get(url, timeout=1.5) 
        return True
    except:
        return False

# Sửa lại hàm này trong file run_crm_v3.py
def open_app_mode(url):
    # Thay vì dùng 'start chrome --app', chúng ta chỉ dùng webbrowser 
    # để gửi URL vào trình duyệt mặc định đang có Extension
    import webbrowser
    webbrowser.open(url)
def main():
    print(f"--- LLDTEK CRM LAUNCHER ---")
    
    extra_params = ""
    if len(sys.argv) > 1:
        args = " ".join(sys.argv[1:])
        if "?" in args:
            extra_params = args[args.index("?"):]
    
    # Kiểm tra máy chủ Local qua Hostname
    if check_server(LOCAL_URL):
        print(f"✅ Local Server ONLINE: {HOSTNAME}")
        target_url = LOCAL_URL + extra_params
    else:
        print(f"☁️ Local OFF. Switching to CLOUD.")
        target_url = CLOUD_URL + extra_params
    
    open_app_mode(target_url) 

if __name__ == '__main__':
    main()