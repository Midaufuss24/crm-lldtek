# web_bot.py
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import streamlit as st

def get_web_data(search_term):
    """
    Hàm khởi động Chrome ẩn danh, đăng nhập và tìm kiếm dữ liệu
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # Chạy ngầm không hiện cửa sổ (bỏ dòng này nếu muốn xem nó chạy)
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Khởi tạo trình duyệt
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # 1. ĐĂNG NHẬP
        login_url = "https://lldtek.org/login"  # Dự đoán URL login
        driver.get(login_url)
        
        # Đợi ô username xuất hiện
        wait = WebDriverWait(driver, 10)
        
        # Tìm ô user (thường là input type text đầu tiên hoặc name='username')
        # Chiến thuật: Tìm input text đầu tiên trong form
        try:
            user_input = driver.find_element(By.CSS_SELECTOR, "input[name='username']") 
        except:
            user_input = driver.find_element(By.CSS_SELECTOR, "input[type='text']")
            
        pass_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
        submit_btn = driver.find_element(By.XPATH, "//button[contains(text(), 'SUBMIT')]") # Tìm nút có chữ SUBMIT
        
        # Nhập liệu từ secrets
        user_input.send_keys(st.secrets["web_account"]["username"])
        pass_input.send_keys(st.secrets["web_account"]["password"])
        submit_btn.click()
        
        # 2. VÀO TRANG TÌM KIẾM
        target_url = "https://lldtek.org/salon/web/pos/list"
        # Đợi chuyển trang xong (check url hoặc check element trang chủ)
        time.sleep(2) 
        driver.get(target_url)
        
        # 3. THỰC HIỆN TÌM KIẾM
        # Tìm ô search có placeholder="Search"
        search_box = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search']")))
        search_btn = driver.find_element(By.XPATH, "//button[contains(., 'SEARCH')]") # Tìm nút có chữ SEARCH
        
        search_box.clear()
        search_box.send_keys(search_term)
        search_btn.click()
        
        # 4. LẤY DỮ LIỆU BẢNG
        time.sleep(3) # Đợi bảng load (có thể thay bằng WebDriverWait chờ bảng xuất hiện)
        
        # Lấy HTML của bảng
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
        
        # Tìm bảng kết quả (thường là thẻ <table>)
        table = soup.find('table')
        if table:
            df = pd.read_html(str(table))[0]
            return df
        else:
            return None

    except Exception as e:
        return f"Lỗi: {str(e)}"
    finally:
        driver.quit()