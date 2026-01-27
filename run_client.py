import sys
import requests
from PyQt5.QtWidgets import QApplication
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QIcon

# =========================================================
# CẤU HÌNH (Sửa lại IP và Link Cloud của bạn)
# =========================================================
LOCAL_URL = "http://172.16.0.86:8503"
CLOUD_URL = "https://lldtek-crm.streamlit.app"
APP_TITLE = "CRM - LLDTEK SYSTEM"

def check_local_alive(url):
    """Kiểm tra xem Server Local có sống không"""
    try:
        requests.head(url, timeout=1.0) # Ping nhanh trong 1s
        return True
    except:
        return False

def main():
    # 1. Khởi tạo ứng dụng giao diện
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)

    # 2. Kiểm tra mạng để chọn Link
    if check_local_alive(LOCAL_URL):
        final_url = LOCAL_URL
        print(f"✅ Đã kết nối Local: {final_url}")
    else:
        final_url = CLOUD_URL
        print(f"☁️ Đã chuyển sang Cloud: {final_url}")

    # 3. Tạo trình duyệt WebView
    web = QWebEngineView()
    web.setWindowTitle(APP_TITLE)
    web.resize(1200, 800) # Kích thước mặc định
    
    # Load trang web
    web.load(QUrl(final_url))
    
    # Hiển thị
    web.show()

    # Giữ app chạy
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()