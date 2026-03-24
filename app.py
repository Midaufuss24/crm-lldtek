import sys
import google.generativeai as genai
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials
import time
import re
import pytz
from urllib.parse import urlencode
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image, ImageDraw
import streamlit.components.v1 as components

# Ép nạp thư viện khi đóng gói file .exe
if getattr(sys, 'frozen', False):
    import gspread, google.auth, google.oauth2.service_account, pandas, plotly, sqlite3, pytz

# ==========================================
# CẤU HÌNH AI - BẢN CINEMA MODE & TRÍ NHỚ (v2.5)
# ==========================================
# THAY API KEY MỚI CỦA BẠN VÀO DÒNG BÊN DƯỚI:
GOOGLE_API_KEY = "AIzaSyCbySj19PNjkVHcpCYR5U8OnrjGM2cb3AQ" 
genai.configure(api_key=GOOGLE_API_KEY)

@st.dialog("🤖 LLDTEK AI ASSISTANT - CINEMA MODE", width="large")
def ai_assistant_dialog(initial_issue):
    st.markdown("""
        <style>
            div[data-testid="stDialog"] div[role="dialog"] { width: 95vw; max-width: 95vw; height: 90vh; }
            .stChatFloatingInputContainer { bottom: 20px; }
        </style>
    """, unsafe_allow_html=True)

    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "user", "parts": [f"Tôi cần hỗ trợ lỗi này: {initial_issue}"]},
            {"role": "model", "parts": ["Chào Chiến! Tôi đã nắm thông tin lỗi. Bạn có ảnh chụp lỗi hay câu hỏi nào thêm không?"]}
        ]

    chat_box = st.container(height=500)
    with chat_box:
        for msg in st.session_state.messages:
            role = "assistant" if msg["role"] == "model" else "user"
            with st.chat_message(role):
                st.markdown(msg["parts"][0])

    uploaded_file = st.file_uploader("📸 Đính kèm ảnh lỗi (AI sẽ phân tích hình ảnh):", type=["jpg", "png", "jpeg"])
    
    if prompt := st.chat_input("Nhập câu hỏi tiếp theo..."):
        st.session_state.messages.append({"role": "user", "parts": [prompt]})
        with chat_box:
            with st.chat_message("user"):
                st.markdown(prompt)

        with chat_box:
            with st.chat_message("assistant"):
                try:
                    model = genai.GenerativeModel('gemini-2.5-flash')
                    if uploaded_file:
                        img = Image.open(uploaded_file)
                        st.image(img, width=300)
                        response = model.generate_content([prompt, img])
                    else:
                        formatted_history = []
                        for m in st.session_state.messages[:-1]:
                            role_map = "user" if m["role"] == "user" else "model"
                            formatted_history.append({"role": role_map, "parts": m["parts"]})
                            
                        chat_session = model.start_chat(history=formatted_history)
                        response = chat_session.send_message(prompt)

                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "model", "parts": [response.text]})
                except Exception as e:
                    st.error(f"❌ Lỗi AI: {str(e)}")
                    st.stop()
        st.rerun()

def create_tech_logo():
    img = Image.new('RGB', (256, 256), color=(10, 25, 47)) 
    d = ImageDraw.Draw(img)
    d.line([(128, 128), (128, 50)], fill=(200, 200, 200), width=8)
    d.line([(128, 128), (60, 190)], fill=(200, 200, 200), width=8)
    d.line([(128, 128), (196, 190)], fill=(200, 200, 200), width=8)
    d.ellipse([(98, 98), (158, 158)], fill=(0, 255, 255), outline=(255, 255, 255), width=3)
    d.ellipse([(108, 30), (148, 70)], fill=(255, 255, 255))
    d.ellipse([(40, 170), (80, 210)], fill=(255, 255, 255))
    d.ellipse([(176, 170), (216, 210)], fill=(255, 255, 255))
    return img

try:
    app_icon = create_tech_logo()
    st.set_page_config(page_title="CRM - LLDTEK", page_icon=app_icon, layout="wide")
except:
    st.set_page_config(page_title="CRM - LLDTEK", page_icon="📡", layout="wide")

st.markdown("""
<style>
    .stApp { font-family: 'Segoe UI', sans-serif; }
    .stTextArea textarea, .stTextInput input { font-family: 'Consolas', monospace; font-weight: 500; border-radius: 5px; }
    div[data-testid="stTextInput"] input[aria-label="⚡ Tra cứu CID nhanh:"] { border: 2px solid #ff4b4b; background-color: #fff0f0; color: black; font-weight: bold; }
    footer {visibility: hidden;}
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

components.html(
    """<script>setInterval(function() {window.parent.postMessage('lldtek_keep_alive_ping', '*');}, 60000);</script>""",
    height=0, width=0
)

# ==========================================
# CƠ SỞ DỮ LIỆU & BỘ CÔNG CỤ (SOP)
# ==========================================
def init_db():
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, Date TEXT, Salon_Name TEXT, Phone TEXT, Issue_Category TEXT, Note TEXT, Status TEXT, Created_At TEXT, CID TEXT, Contact TEXT, Card_16_Digits TEXT, Training_Note TEXT, Demo_Note TEXT, Agent_Name TEXT, Support_Time TEXT, Caller_Info TEXT, ISO_System TEXT, Ticket_Type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cid_cache (cid TEXT PRIMARY KEY, salon_name TEXT, phone TEXT, owner TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, is_active INTEGER, last_seen TEXT)''')
    
    # [V151] - TẠO BẢNG CHỨA KỊCH BẢN SOP VÀ BÁO ĐỘNG CỨU NÉT
    c.execute('''CREATE TABLE IF NOT EXISTS sops (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, device_name TEXT, steps TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS escalations (id INTEGER PRIMARY KEY AUTOINCREMENT, agent_name TEXT, salon_name TEXT, phone TEXT, note TEXT, status TEXT, created_at TEXT)''')
    
    try: c.execute("ALTER TABLE users ADD COLUMN vici_id TEXT")
    except: pass
    try: c.execute("ALTER TABLE cid_cache ADD COLUMN phone TEXT")
    except: pass
    try: c.execute("ALTER TABLE cid_cache ADD COLUMN owner TEXT")
    except: pass
    # [V152] Bảng chứa lệnh Giao việc nội bộ
    c.execute('''CREATE TABLE IF NOT EXISTS dispatches (id INTEGER PRIMARY KEY AUTOINCREMENT, target_agent TEXT, salon_name TEXT, phone TEXT, note TEXT, status TEXT, created_by TEXT, created_at TEXT)''')

    # Khởi tạo user mặc định
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        agents_list = ["Phương Loan", "Hương Giang", "Phương Anh", "Tuấn Võ", "Thùy Dung", "Phương Hồ", "Chiến Phạm", "Anh Đạt", "Tiến Dương", "Schang Sanh", "Tuyết Anh", "Liên Chi", "Anh Thư"]
        for a in agents_list:
            r = 'Admin' if a in ["Phương Loan", "Thùy Dung"] else 'Agent'
            c.execute("INSERT INTO users VALUES (?, '123456', ?, 1, '', '')", (a, r))
        c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'Admin', 1, '', '')")
        
    # [V151] - Khởi tạo bộ Data chuẩn LLDTEK nếu bảng trống
    c.execute("SELECT COUNT(*) FROM sops")
    if c.fetchone()[0] == 0:
        defaults_sops = [
            ('Phần cứng', 'PAX A800 / A920 / A35', 'Check IP cùng lớp mạng với System|Test connection|Khởi động lại PAX|Clear Batch'),
            ('Phần cứng', 'PAX E800', 'Kiểm tra nguồn điện|Check kết nối Wi-Fi/LAN|Thực hiện Ping Test|Reboot thiết bị'),
            ('Phần cứng', 'PAX Q30 / S300 / SP30', 'Kiểm tra chặt cáp kết nối (USB/RS232)|Check IP trùng khớp|Clear Batch|Download Param'),
            ('Phần cứng', 'EPSON TM30III / Thermal Receipt', 'Kiểm tra kẹt giấy / hết giấy / đóng nắp|Kiểm tra đèn báo lỗi|Check IP mạng LAN|Nhấn nút Feed test|Cài/Update lại Driver trên PC'),
            ('Phần cứng', 'Máy in GCube', 'Kiểm tra cáp nguồn|Kiểm tra đèn tín hiệu|In test trực tiếp trên máy|Re-pair Bluetooth / Reset IP'),
            ('Phần cứng', 'PC HP Touch Screen', 'Kiểm tra cáp mạng LAN/Internet|Khởi động lại PC|Mở task manager tắt app treo|Check kết nối với LLDTEK System'),
            ('Phần cứng', 'AT900 POS', 'Check kết nối Wi-Fi/LAN|Kiểm tra cảm ứng màn hình|Khởi động lại POS'),
            ('Phần cứng', 'Tablet Amazon / Ipad (Check-in)', 'Check kết nối Wi-Fi cùng mạng quán|Force Stop App|Xóa Cache App|Cập nhật App LLDTEK trên Store'),
            ('Phần mềm', 'Fix Ticket (Sửa bill)', 'Hỏi rõ số Ticket/Tên khách|Kiểm tra lịch sử giao dịch|Sửa dịch vụ/giá tiền|Xác nhận lưu thay đổi'),
            ('Phần mềm', 'Swap Tech (Đổi thợ)', 'Xác nhận tên thợ bị gán sai|Xác nhận tên thợ đúng|Vào System chọn Swap Tech|Check lại Report thợ'),
            ('Phần mềm', 'HD Adjust Tip', 'Xin mã Manager Pass|Tìm lại bill gốc cần sửa|Vào mục Adjust Tip nhập số tiền mới|Lưu và kiểm tra batch'),
            ('Phần mềm', 'Refund tiền / VOID Ticket', 'Yêu cầu Manager Pass|Thực hiện Void/Refund trên System|Thực hiện Refund tương ứng trên máy PAX|Thu hồi lại receipt cũ'),
            ('Phần mềm', 'Add thêm thợ (Technician)', 'Lấy thông tin thợ mới|Vào mục Tech Management|Tạo Profile thợ|Set quyền và Passcode')
        ]
        c.executemany("INSERT INTO sops (category, device_name, steps) VALUES (?, ?, ?)", defaults_sops)
    
    conn.commit()
    conn.close()

init_db()

def get_viber_copy_format(salon, cid, phone, owner, note):
    n = str(note)
    if '\n' in n: n = f'"{n}"'
    return f"{salon}\t{cid}\t{phone}\t{owner}\t{n}"

# ==========================================
# HỆ THỐNG ĐĂNG NHẬP
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.user_role = ""

qp = st.query_params
vici_user_param = qp.get("user", "")
js_auto_user = qp.get("auto_login_js", "")

if st.session_state.get("clear_storage", False):
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET vici_id='' WHERE username=?", (st.session_state.current_user,))
    conn.commit()
    conn.close()
    clear_js = """<script>try { window.parent.localStorage.removeItem('crm_auto_user'); } catch(e) {}
    try { window.localStorage.removeItem('crm_auto_user'); } catch(e) {}
    let url = new URL(window.location.href); url.searchParams.delete('auto_login_js');
    window.history.replaceState({}, document.title, url.toString());</script>"""
    components.html(clear_js, height=0, width=0)
    st.session_state.clear_storage = False
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.user_role = ""
    st.rerun()

if not st.session_state.logged_in:
    if vici_user_param:
        conn = sqlite3.connect('crm_data.db')
        c = conn.cursor()
        c.execute("SELECT username, role, is_active FROM users WHERE vici_id=? AND vici_id != '' AND vici_id IS NOT NULL", (vici_user_param,))
        res = c.fetchone()
        conn.close()
        if res and res[2] == 1:
            st.session_state.logged_in = True
            st.session_state.current_user = res[0]
            st.session_state.user_role = res[1]

    elif js_auto_user:
        conn = sqlite3.connect('crm_data.db')
        c = conn.cursor()
        c.execute("SELECT role, is_active FROM users WHERE username=?", (js_auto_user,))
        res = c.fetchone()
        conn.close()
        if res and res[1] == 1:
            st.session_state.logged_in = True
            st.session_state.current_user = js_auto_user
            st.session_state.user_role = res[0]
            if "auto_login_js" in st.query_params: del st.query_params["auto_login_js"] 
            st.rerun()

if not st.session_state.logged_in:
    check_js = """<script>try { let saved_user = window.parent.localStorage.getItem('crm_auto_user') || window.localStorage.getItem('crm_auto_user');
    if (saved_user) { let url = new URL(window.location.href); if (!url.searchParams.has('auto_login_js') && !url.searchParams.has('user')) {
    url.searchParams.set('auto_login_js', saved_user); window.location.replace(url.toString()); } } } catch(e) {}</script>"""
    components.html(check_js, height=0, width=0)

    st.markdown("<br><h1 style='text-align: center; color: #4CAF50;'>🔐 HỆ THỐNG LLDTEK CRM</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Vui lòng đăng nhập để bắt đầu phiên làm việc</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("👤 Tên nhân viên (Username)")
            pass_input = st.text_input("🔑 Mật khẩu", type="password")
            remember_me = st.checkbox("💾 Ghi nhớ đăng nhập", value=True)
            
            if st.form_submit_button("Đăng Nhập", use_container_width=True):
                conn = sqlite3.connect('crm_data.db')
                c = conn.cursor()
                c.execute("SELECT role, is_active FROM users WHERE username=? AND password=?", (user_input, pass_input))
                res = c.fetchone()
                if res:
                    if res[1] == 1:
                        if remember_me:
                            if vici_user_param:
                                c.execute("UPDATE users SET vici_id=? WHERE username=?", (vici_user_param, user_input))
                            st.session_state.trigger_js_remember = user_input 
                        
                        st.session_state.logged_in = True
                        st.session_state.current_user = user_input
                        st.session_state.user_role = res[0]
                        conn.commit()
                        conn.close()
                        st.rerun()
                    else:
                        st.error("❌ Tài khoản của bạn đã bị khóa. Vui lòng liên hệ Admin.")
                        conn.close()
                else:
                    st.error("❌ Sai tên đăng nhập hoặc mật khẩu!")
                    conn.close()
    st.stop() 

if 'trigger_js_remember' in st.session_state:
    js_save = f"""<script>try {{ window.parent.localStorage.setItem('crm_auto_user', '{st.session_state.trigger_js_remember}'); }} catch(e) {{}}
    try {{ window.localStorage.setItem('crm_auto_user', '{st.session_state.trigger_js_remember}'); }} catch(e) {{}}</script>"""
    components.html(js_save, height=0, width=0)
    del st.session_state['trigger_js_remember']

conn = sqlite3.connect('crm_data.db')
c = conn.cursor()
c.execute("UPDATE users SET last_seen=? WHERE username=?", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state.current_user))
conn.commit()
conn.close()

def check_recent_duplicate(phone, agent):
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute("SELECT Created_At FROM tickets WHERE Phone=? AND Agent_Name=? ORDER BY id DESC LIMIT 1", (phone, agent))
    res = c.fetchone()
    conn.close()
    if res:
        last_time = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
        if (datetime.now() - last_time).total_seconds() < 180:
            return True
    return False

# --- CHECK LIBS ---
HAS_BOT_LIBS = False
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    from webdriver_manager.chrome import ChromeDriverManager
    HAS_BOT_LIBS = True
except ImportError:
    HAS_BOT_LIBS = False

is_cloud_mode = False
if not HAS_BOT_LIBS or "web_account" not in st.secrets:
    is_cloud_mode = True

# ==========================================
# 2. AUTO-DETECT SHEETS 
# ==========================================
@st.cache_data(ttl=3600) 
def get_dynamic_sheets():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        gc = gspread.authorize(credentials)
        all_files = gc.list_spreadsheet_files()
        
        crm_files = [f['name'] for f in all_files if "DAILY REPORT" in f['name'].upper()]
        
        def parse_date_sort(filename):
            try:
                match = re.search(r'(\d{1,2})[/.-](\d{2,4})', filename)
                if match:
                    m, y = match.groups()
                    if len(y) == 4: y = y[-2:]
                    return datetime.strptime(f"{m}/{y}", "%m/%y")
                return datetime.min
            except: 
                return datetime.min
                
        crm_files.sort(key=parse_date_sort, reverse=True)
        return crm_files if crm_files else ["2-3-4 DAILY REPORT 03/26", "2-3-4 DAILY REPORT 02/26"]
    except Exception as e:
        return ["2-3-4 DAILY REPORT 03/26", "2-3-4 DAILY REPORT 02/26"]

AVAILABLE_SHEETS = get_dynamic_sheets()
MASTER_DB_FILE = "CID Salon"
IGNORED_TAB_NAMES = ["form request", "sheet 4", "sheet4", "request", "request daily", "total", "summary", "copy of", "bản sao", "copy"]
KEEP_COLUMNS = ["Date", "Salon_Name", "Agent_Name", "Phone", "CID", "Owner", "Note", "Status", "Issue_Category", "Support_Time", "End_Time", "Ticket_Type", "Caller_Info", "ISO_System", "Training_Note", "Demo_Note", "Card_16_Digits"]

def get_company_time():
    utc_now = datetime.now(pytz.utc)
    return utc_now.astimezone(pytz.timezone('US/Central'))

def format_excel_time(dt_obj):
    t_str = dt_obj.strftime('%I:%M:%S %p')
    if t_str.startswith('0'): return t_str[1:]
    return t_str

def get_current_month_sheet():
    now = get_company_time()
    search_str_1 = now.strftime("%m/%y")
    search_str_2 = f"{now.month}/{now.strftime('%y')}"
    defaults = []
    for s in AVAILABLE_SHEETS:
        if search_str_1 in s or search_str_2 in s: 
            defaults.append(s)
    return defaults if defaults else ([AVAILABLE_SHEETS[0]] if AVAILABLE_SHEETS else [])

def clean_headers(headers):
    seen = {}
    result = []
    for h in headers:
        h = str(h).strip()
        h = "Unnamed" if not h else h
        if h in seen: 
            seen[h] += 1
            result.append(f"{h}_{seen[h]}")
        else: 
            seen[h] = 0
            result.append(h)
    return result

def construct_date_from_context(val, sheet_name, tab_name):
    match = re.search(r'(\d{1,2})/(\d{2})', sheet_name)
    file_year = "20" + match.group(2) if match else str(datetime.now().year)
    file_month = match.group(1) if match else "01"
    day_str = str(tab_name).strip()
    if "/" in day_str and len(day_str) <= 5: 
        return f"{day_str}/{file_year}"
    if day_str.isdigit() and int(day_str) <= 31: 
        return f"{file_month}/{day_str}/{file_year}" 
    return f"{tab_name}/{file_year}"

def format_date_display(val):
    try: 
        return pd.to_datetime(str(val), errors='coerce').strftime('%m/%d/%Y') if not pd.isna(val) and str(val).strip() != "" else str(val)
    except: 
        return str(val)

def safe_process_dataframe(df, rename_map):
    df = df.rename(columns=rename_map)
    df = df.loc[:, ~df.columns.duplicated()]
    for col in KEEP_COLUMNS: 
        if col not in df.columns: 
            df[col] = ""
    return df[KEEP_COLUMNS]

def map_status_badge(status_str):
    s = str(status_str).lower()
    if "done" in s: return f"🟢 {status_str}"
    elif "support" in s or "pending" in s: return f"🔴 {status_str}"
    elif "request" in s or "forward" in s: return f"🟠 {status_str}"
    elif "no answer" in s: return f"⚫ {status_str}"
    return status_str

def extract_final_data(driver, search_term):
    try:
        html = driver.page_source
        dfs = pd.read_html(html)
        if dfs:
            for df in dfs:
                str_df = df.astype(str).sum(axis=1)
                if str_df.str.contains(search_term, case=False).any():
                     final_rows = df[str_df.str.contains(search_term, case=False)]
                     return final_rows
            return max(dfs, key=lambda x: x.shape[1])
        return None
    except: 
        return None

def run_search_engine(search_term):
    if is_cloud_mode: 
        return "CLOUD_MODE"
    status_log = st.empty()
    chrome_options = Options()
    chrome_options.page_load_strategy = 'eager'
    chrome_options.add_argument("--headless=new") 
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = None
    try:
        status_log.info("🚀 Bot đang khởi động...")
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        wait = WebDriverWait(driver, 15)
        
        driver.get("https://www.lldtek.org/salon/login")
        try:
            user_in = wait.until(EC.presence_of_element_located((By.NAME, "username")))
            pass_in = driver.find_element(By.NAME, "password")
            user_in.send_keys(st.secrets["web_account"]["username"])
            pass_in.send_keys(st.secrets["web_account"]["password"])
            pass_in.submit()
        except: 
            driver.quit()
            return None
        
        status_log.info("🔍 Đang tra cứu thông tin...")
        driver.get("https://lldtek.org/salon/web/pos/list")
        
        try:
            search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search')]")))
            target_input = search_btn.find_element(By.XPATH, "./preceding::input[1]")
            
            ph = str(target_input.get_attribute("placeholder")).lower()
            if "date" in ph or "mm/dd" in ph:
                status_log.error("❌ Bot nhầm ô Date.")
            else:
                target_input.click()
                target_input.clear()
                target_input.send_keys(search_term)
                driver.execute_script("arguments[0].click();", search_btn)
                status_log.info("⏳ Đang tải dữ liệu...")
                time.sleep(2.5)
                
                body_text = driver.find_element(By.TAG_NAME, "body").text
                if search_term in body_text:
                    status_log.success("✅ Đã tìm thấy dữ liệu!")
                    final_df = extract_final_data(driver, search_term)
                    driver.quit()
                    return final_df
                else:
                     status_log.warning("⚠️ Không tìm thấy kết quả phù hợp.")
            driver.quit()
            status_log.empty()
            return pd.DataFrame()
        except Exception as e:
            if driver: driver.quit()
            return None
    except Exception as e:
        if driver: driver.quit()
        return None

def save_to_master_db_gsheet(df):
    status_box = st.status("🛠️ Đang thực hiện lưu Database...", expanded=True)
    try:
        if df.empty:
            status_box.update(label="❌ Dữ liệu Rỗng!", state="error")
            return False, "Không có dữ liệu để lưu."

        status_box.write("1. Kết nối Google Drive...")
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials)
        
        try: sh = gc.open(MASTER_DB_FILE)
        except: return False, f"Không tìm thấy file '{MASTER_DB_FILE}'."

        try: ws = sh.worksheet("CID")
        except: ws = sh.add_worksheet(title="CID", rows=1000, cols=10)

        status_box.write("2. Đang map đúng cột dữ liệu...")
        count = 0
        for index, row in df.iterrows():
            try: name_val = row['Name'] 
            except: name_val = row.iloc[1] if len(row) > 1 else ""
            try: cid_val = row['CID'] 
            except: cid_val = row.iloc[2] if len(row) > 2 else ""
            try: agent_val = row['Agent'] 
            except: agent_val = row.iloc[4] if len(row) > 4 else "" 
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            row_data = [str(name_val), str(cid_val), str(agent_val), now_str]
            ws.append_row(row_data)
            count += 1
            
        status_box.update(label=f"✅ Đã lưu {count} dòng!", state="complete")
        return True, f"Đã lưu {count} dòng vào sheet CID."
        
    except Exception as e: 
        return False, str(e)

def get_target_worksheet(date_obj):
    month_year_1 = date_obj.strftime("%m/%y")
    month_year_2 = f"{date_obj.month}/{date_obj.strftime('%y')}"
    target_sheet_name = None
    for s in AVAILABLE_SHEETS:
        if month_year_1 in s or month_year_2 in s: 
            target_sheet_name = s
            break
            
    if not target_sheet_name: 
        return None, None, f"⚠️ Không tìm thấy file Report tháng {month_year_1}"
        
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(credentials)
    sh = gc.open(target_sheet_name)
    day_str = str(date_obj.day)
    target_ws = None
    for ws in sh.worksheets():
        if ws.title.strip() == day_str or ws.title.startswith(f"{day_str}/"): 
            target_ws = ws
            break
            
    if not target_ws: 
        target_ws = sh.worksheets()[-1]
    return sh, target_ws, target_sheet_name

def apply_full_format(ws, row_idx, color_type):
    colors = {'red': {"red": 1.0, "green": 0.0, "blue": 0.0}, 'blue': {"red": 0.0, "green": 0.0, "blue": 1.0}, 'black': {"red": 0.0, "green": 0.0, "blue": 0.0}}
    fg_color = colors.get(color_type, colors['black'])

    fmt_center_clip = {
        "textFormat": {"fontFamily": "Times New Roman", "fontSize": 12, "foregroundColor": fg_color},
        "verticalAlignment": "BOTTOM", "horizontalAlignment": "CENTER", "wrapStrategy": "CLIP"
    }
    
    fmt_left_clip = {
        "textFormat": {"fontFamily": "Times New Roman", "fontSize": 12, "foregroundColor": fg_color},
        "verticalAlignment": "BOTTOM", "horizontalAlignment": "LEFT", "wrapStrategy": "CLIP"
    }

    fmt_left_wrap = {
        "textFormat": {"fontFamily": "Times New Roman", "fontSize": 12, "foregroundColor": fg_color},
        "verticalAlignment": "BOTTOM", "horizontalAlignment": "LEFT", "wrapStrategy": "WRAP"
    }

    try:
        ws.format(f"B{row_idx}:E{row_idx}", fmt_center_clip)  
        ws.format(f"F{row_idx}", fmt_left_clip)                
        ws.format(f"G{row_idx}:H{row_idx}", fmt_center_clip)  
        ws.format(f"I{row_idx}", fmt_center_clip)   
        ws.format(f"J{row_idx}", fmt_left_wrap)                
        ws.format(f"K{row_idx}", fmt_left_clip)            
    except Exception as e:
        pass

def save_to_google_sheet(ticket_data):
    try:
        sh, target_ws, sheet_name = get_target_worksheet(ticket_data['Date_Obj'])
        if not target_ws: 
            return False, sheet_name
        
        # 1. LƯU VÀO TAB DAILY REPORT (Như cũ)
        all_values = target_ws.get_values("A7:K1000") 
        start_row = 7
        target_row_idx = -1
        last_stt_val = 0 
        
        for i, row in enumerate(all_values):
            real_row_idx = start_row + i
            row_padded = [str(x).strip() for x in row] + [""] * (11 - len(row))
            if bool(row_padded[1] or row_padded[5] or row_padded[7] or row_padded[9]):
                if row_padded[0].isdigit(): last_stt_val = int(row_padded[0])
                continue 
            else:
                target_row_idx = real_row_idx
                break
        
        if target_row_idx == -1: 
            target_row_idx = start_row + len(all_values)
                
        if target_row_idx > 6:
            if last_stt_val == 0:
                try:
                    prev_stt = target_ws.cell(target_row_idx - 1, 1).value
                    if prev_stt and str(prev_stt).isdigit(): last_stt_val = int(prev_stt)
                except: pass
            target_ws.update_cell(target_row_idx, 1, last_stt_val + 1)
        
        row_data = [
            ticket_data['Agent_Name'], ticket_data['Support_Time'], ticket_data['End_Time'], 
            ticket_data['Duration'], ticket_data['Salon_Name'], ticket_data['CID'], 
            ticket_data['Phone'], ticket_data['Caller_Info'], ticket_data['Note'], ticket_data['Status']
        ]
        target_ws.update(f"B{target_row_idx}:K{target_row_idx}", [row_data])
        
        color = 'red' if "Support" in ticket_data['Status'] else 'black'
        apply_full_format(target_ws, target_row_idx, color)

        # 2. [TÍNH NĂNG MỚI] LƯU TỰ ĐỘNG SANG TAB TRAINING HOẶC 16 DIGITS
        if ticket_data['Ticket_Type'] == 'Training':
            try:
                ws_train = sh.worksheet("Training")
                # Format: No | Date | Name | Time | Salon | CID | ISO | Phone | Owner | Email | Train 1 Date | Train 1 Note
                train_row = [
                    "", ticket_data['Date_Str'], ticket_data['Agent_Name'], ticket_data['Support_Time'],
                    ticket_data['Salon_Name'], ticket_data['CID'], ticket_data.get('Train_ISO', ''),
                    ticket_data['Phone'], ticket_data['Caller_Info'], ticket_data.get('Train_Email', ''),
                    ticket_data['Date_Str'], ticket_data['Training_Note']
                ]
                ws_train.append_row(train_row)
            except: pass

        elif ticket_data['Ticket_Type'] == 'Request (16 Digits)':
            try:
                ws_16 = sh.worksheet("16 Digits")
                c_dict = ticket_data.get('Card_Dict', {})
                # Format: Name | MID | SALON | Date | Card Last 4 | Amount | App Code | Ticket No | Extra Due | Missed Tip | Refund | Void Mistake | 16 Digits | Exp Date | ISO | Note
                row_16 = [
                    ticket_data['Agent_Name'], c_dict.get('MID', ''), ticket_data['Salon_Name'], ticket_data['Date_Str'],
                    c_dict.get('Card4', ''), c_dict.get('Amount', ''), c_dict.get('AppCode', ''), c_dict.get('TicketNo', ''),
                    c_dict.get('ExtraDue', ''), c_dict.get('MissedTip', ''), c_dict.get('Refund', ''), c_dict.get('VoidMistake', ''),
                    "", "", c_dict.get('ISO', ''), ticket_data['Status']
                ]
                ws_16.append_row(row_16)
            except: pass

        return True, f"✅ Đã lưu Daily Report (Dòng {target_row_idx}) và tự động đồng bộ Tab phụ."
    except Exception as e: 
        return False, f"❌ Lỗi: {str(e)}"

def update_google_sheet_row(date_str, phone, salon_name, new_status, new_note):
    try:
        try: date_obj = pd.to_datetime(date_str, format='%m/%d/%Y')
        except: date_obj = pd.to_datetime(date_str)
            
        sh, target_ws, sheet_name = get_target_worksheet(date_obj)
        if not target_ws: return False, sheet_name
            
        all_values = target_ws.get_all_values()
        target_row_idx = -1
        
        for idx, row in enumerate(all_values):
            if idx < 6: continue
            if len(row) > 7:
                row_phone = str(row[7]).strip()
                row_salon = str(row[5]).strip()
                if phone in row_phone and salon_name in row_salon: 
                    target_row_idx = idx + 1
                    break
                    
        if target_row_idx != -1:
            target_ws.update(f"J{target_row_idx}:K{target_row_idx}", [[new_note, new_status]])
            color = 'blue' if "Done" in new_status else ('red' if "Support" in new_status else 'black')
            apply_full_format(target_ws, target_row_idx, color)
            return True, f"✅ Đã cập nhật (Dòng {target_row_idx})"
        else: 
            return False, f"⚠️ Không tìm thấy dòng khớp"
    except Exception as e: 
        return False, f"❌ Lỗi Update: {str(e)}"

@st.cache_data(ttl=600, show_spinner=False)
def load_gsheet_data(selected_sheets):
    if not selected_sheets: return pd.DataFrame()
    try:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials)
        all_data = []
        for idx, s_name in enumerate(selected_sheets):
            try:
                sh = gc.open(s_name)
                tabs = [ws for ws in sh.worksheets() if not any(ign in ws.title.lower() for ign in IGNORED_TAB_NAMES)]
                for i, ws in enumerate(tabs):
                    try:
                        raw = ws.get_all_values()
                        if len(raw) < 2: continue
                        if len(ws.title) < 10 or "/" in ws.title:
                            header_idx = -1
                            for r_idx, row in enumerate(raw[:15]):
                                if "salon" in "".join([str(c).lower() for c in row]): 
                                    header_idx = r_idx
                                    break
                            if header_idx != -1:
                                df_d = pd.DataFrame(raw[header_idx+1:], columns=clean_headers(raw[header_idx]))
                                rename = {"Salon Name": "Salon_Name", "Name": "Agent_Name", "Time": "Support_Time", "Owner": "Caller_Info", "Phone": "Phone", "CID": "CID", "Note": "Note", "Status": "Status"}
                                df_d = safe_process_dataframe(df_d, rename)
                                if "Note" in df_d.columns: df_d["Issue_Category"] = df_d["Note"]
                                df_d["Date"] = construct_date_from_context(None, s_name, ws.title)
                                df_d["Ticket_Type"] = "Support"
                                df_d["Status"] = df_d["Status"].replace({"Pending": "Support", "pending": "Support"})
                                all_data.append(df_d)
                    except: continue
            except: pass
        if all_data:
            final_df = pd.concat(all_data, ignore_index=True).replace({'nan': '', 'None': '', 'NaN': ''})
            final_df = final_df.drop_duplicates(subset=['Phone', 'Date', 'Support_Time', 'Agent_Name']).reset_index(drop=True)
            return final_df
        return pd.DataFrame()
    except Exception as e: 
        st.error(f"Lỗi: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def load_master_db():
    try:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials)
        sh = gc.open(MASTER_DB_FILE)
        master_data = {}
        
        try: 
            ws_cid = sh.worksheet("CID")
            raw_cid = ws_cid.get_all_values()
            if len(raw_cid) > 1:
                headers = clean_headers(raw_cid[0])
                master_data['CID'] = pd.DataFrame(raw_cid[1:], columns=headers)
                master_data['CID'].columns = master_data['CID'].columns.str.strip()
            else: master_data['CID'] = pd.DataFrame()
        except: master_data['CID'] = pd.DataFrame()
            
        try: 
            ws_note = sh.worksheet("NOTE")
            master_data['NOTE'] = pd.DataFrame(ws_note.get_all_values())
        except: master_data['NOTE'] = pd.DataFrame()
            
        try: 
            ws_conf = sh.worksheet("CONFIRMATION")
            raw_conf = ws_conf.get_all_values()
            if len(raw_conf) > 1:
                headers = clean_headers(raw_conf[1])
                master_data['CONFIRMATION'] = pd.DataFrame(raw_conf[2:], columns=headers) 
            else: master_data['CONFIRMATION'] = pd.DataFrame()
        except: master_data['CONFIRMATION'] = pd.DataFrame()
            
        try: 
            ws_term = None
            for w in sh.worksheets(): 
                if "terminal" in w.title.lower(): 
                    ws_term = w
                    break
            if ws_term: master_data['TERMINAL'] = pd.DataFrame(ws_term.get_all_values())
        except: master_data['TERMINAL'] = pd.DataFrame()
            
        return master_data
    except Exception as e: 
        return {"Error": str(e)}

def insert_ticket(date, salon, phone, issue, note, status, cid, agent, time_str, caller, ticket_type, iso="", train_note="", demo_note="", card_info=""):
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''INSERT INTO tickets (Date, Salon_Name, Phone, Issue_Category, Note, Status, Created_At, CID, Agent_Name, Support_Time, Caller_Info, Ticket_Type, ISO_System, Training_Note, Demo_Note, Card_16_Digits) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (date, salon, phone, issue, note, status, created, cid, agent, time_str, caller, ticket_type, iso, train_note, demo_note, card_info))
    conn.commit()
    conn.close()

def update_ticket(tid, status, note, salon, phone, cid, caller, card_16="", exp_date=""):
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    extra = f"{card_16} | EXP: {exp_date}" if exp_date else card_16
    if extra:
        sql = '''UPDATE tickets SET Status=?, Note=?, Salon_Name=?, Phone=?, CID=?, Caller_Info=?, Card_16_Digits=? WHERE id=?'''
        params = (status, note, salon, phone, cid, caller, extra, tid)
    else:
        sql = '''UPDATE tickets SET Status=?, Note=?, Salon_Name=?, Phone=?, CID=?, Caller_Info=? WHERE id=?'''
        params = (status, note, salon, phone, cid, caller, tid)
    c.execute(sql, params)
    conn.commit()
    conn.close()

def update_confirmation_note(cid, new_note):
    try:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials)
        sh = gc.open(MASTER_DB_FILE)
        ws = sh.worksheet("CONFIRMATION")
        cell = ws.find(cid)
        if cell: 
            ws.update_cell(cell.row, 5, new_note)
            return True, "✅ Đã cập nhật Note thành công!"
        else: return False, "⚠️ Không tìm thấy CID này."
    except Exception as e: return False, f"❌ Lỗi: {str(e)}"

# ==========================================
# GIAO DIỆN CHÍNH & PHÂN QUYỀN
# ==========================================
st.sidebar.title("🏢 CRM - LLDTEK")

conn = sqlite3.connect('crm_data.db')
c = conn.cursor()
c.execute("SELECT username FROM users WHERE is_active=1")
active_users = [row[0] for row in c.fetchall()]
conn.close()

if st.sidebar.button("🔄 Cập nhật Dữ liệu Mới"): 
    st.cache_data.clear()
    st.rerun()

default_sheets = get_current_month_sheet()
sheets = st.sidebar.multiselect("Dữ liệu Report:", AVAILABLE_SHEETS, default=default_sheets)
st.sidebar.markdown("---")

if st.session_state.user_role == 'Admin':
    default_idx = active_users.index(st.session_state.current_user) if st.session_state.current_user in active_users else 0
    sel_agent = st.sidebar.selectbox("Nhân viên:", active_users, index=default_idx, key="agent_selectbox")
else:
    sel_agent = st.session_state.current_user
    st.sidebar.markdown(f"👤 **Xin chào, {sel_agent}**")
    st.sidebar.caption("Chức vụ: Nhân viên")

if st.sidebar.button("🚪 Đăng xuất", type="secondary"):
    st.session_state.clear_storage = True
    st.rerun()

df_sidebar = load_gsheet_data(sheets)
if sel_agent:
    if not df_sidebar.empty:
        today_str = get_company_time().strftime('%m/%d/%Y')
        df_sidebar['Display_Date'] = df_sidebar['Date'].apply(format_date_display)
        agent_today_df = df_sidebar[(df_sidebar['Display_Date'] == today_str) & (df_sidebar['Agent_Name'] == sel_agent)].copy()
        
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**🎯 Thành tích hôm nay của {sel_agent}**")
        if not agent_today_df.empty:
            agent_today_df['Status_Norm'] = agent_today_df['Status'].astype(str).str.lower()
            done_count = len(agent_today_df[agent_today_df['Status_Norm'].str.contains('done')])
            pending_count = len(agent_today_df[agent_today_df['Status_Norm'].str.contains('pending') | agent_today_df['Status_Norm'].str.contains('support')])
            c_sd1, c_sd2 = st.sidebar.columns(2)
            c_sd1.metric("✅ Done", done_count)
            c_sd2.metric("⚠️ Nợ", pending_count)
        else:
            c_sd1, c_sd2 = st.sidebar.columns(2)
            c_sd1.metric("✅ Done", 0)
            c_sd2.metric("⚠️ Nợ", 0)

menu_options = ["🆕 New Ticket", "📌 Cần Follow-up", "📥 Inbox Phân Việc", "🗂️ Tra cứu Master Data", "🔍 Search & History"]
if st.session_state.user_role == 'Admin':
    menu_options.append("📊 Dashboard (SUP Only)")
    menu_options.append("👥 Quản lý Nhân sự / SOP")
menu = st.sidebar.selectbox("Menu", menu_options)

if 'form_key' not in st.session_state: st.session_state.form_key = 0
if 'ticket_start_time' not in st.session_state: st.session_state.ticket_start_time = None

def clear_form():
    st.session_state.form_key += 1
    fk = st.session_state.form_key
    st.session_state[f"ticket_phone_{fk}"] = ""
    st.session_state[f"ticket_salon_{fk}"] = ""
    st.session_state[f"ticket_cid_{fk}"] = ""
    st.session_state[f"ticket_owner_{fk}"] = ""
    st.session_state[f"ticket_note_{fk}"] = ""
    st.session_state[f"ticket_warnings_{fk}"] = {}
    st.session_state.ticket_start_time = None
    if 'vici_cache' in st.session_state: del st.session_state['vici_cache']

@st.dialog("⚠️ XÁC NHẬN LƯU TICKET")
def confirm_save_dialog(data_pack, is_duplicate=False):
    if is_duplicate:
        st.error("🚨 CẢNH BÁO TRÙNG LẶP: Bạn vừa lưu 1 ticket cho SĐT này cách đây ít phút!")
        
    st.markdown(f"""<div style="text-align: center;"><h3 style="color: #4CAF50;">{data_pack['Salon_Name']}</h3><p><b>SĐT:</b> {data_pack['Phone']} | <b>Trạng thái:</b> {data_pack['Status']}</p>
    <p><b>⏱️ Thời gian:</b> {data_pack['Duration']} phút ({data_pack['Support_Time']} - {data_pack['End_Time']})</p></div>""", unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("**📋 COPY SANG VIBER (Click biểu tượng copy ở góc phải ô dưới đây):**")
    viber_str = get_viber_copy_format(data_pack['Salon_Name'], data_pack['CID'], data_pack['Phone'], data_pack['Caller_Info'], data_pack['Note'])
    st.code(viber_str, language="text")
    st.markdown("---")

    if st.button("✅ ĐỒNG Ý LƯU & CLEAR FORM", type="primary", use_container_width=True):
        insert_ticket(data_pack['Date_Str'], data_pack['Salon_Name'], data_pack['Phone'], data_pack['Note'], data_pack['Note'], data_pack['Status'], data_pack['CID'], data_pack['Agent_Name'], data_pack['Support_Time'], data_pack['Caller_Info'], data_pack['Ticket_Type'], "", data_pack['Training_Note'], "", data_pack['Card_16_Digits'])
        with st.spinner("⏳ Đang đồng bộ Google Sheet..."):
            success, msg = save_to_google_sheet(data_pack)
        if success: 
            if "messages" in st.session_state: del st.session_state.messages
            st.toast("✅ Đã lưu Ticket & Reset Trí nhớ AI!", icon="✨")
            clear_form()
            st.rerun() 
        else: 
            st.error(f"Lỗi GSheet: {msg}")

# ==========================================
# MODULE 1: NEW TICKET (TÍCH HỢP SMART TOOLKIT & LIVE PING)
# ==========================================
if menu == "🆕 New Ticket":
    st.title("🆕 Tạo Ticket Mới")
    houston_now = get_company_time()
    fk = st.session_state.form_key 
    
    for f in ["phone", "salon", "cid", "owner", "note"]:
        if f"ticket_{f}_{fk}" not in st.session_state:
            st.session_state[f"ticket_{f}_{fk}"] = ""
    if f"ticket_warnings_{fk}" not in st.session_state:
        st.session_state[f"ticket_warnings_{fk}"] = {}
            
    qp = st.query_params
    if any(k in qp for k in ["phone", "address", "comments", "first"]):
        st.session_state.vici_cache = {
            "title": qp.get("title", ""), "first": qp.get("first", ""), "last": qp.get("last", ""), "address": qp.get("address", ""),
            "city": qp.get("city", ""), "state": qp.get("state", ""), "zip": qp.get("zip", ""), "vendor_id": qp.get("vendor_id", ""),
            "phone": qp.get("phone", ""), "alt_phone": qp.get("alt_phone", ""), "email": qp.get("email", ""), "comments": qp.get("comments", ""), "user": qp.get("user", "")
        }
        
        if st.session_state.vici_cache['phone']: 
            st.session_state[f"ticket_phone_{fk}"] = st.session_state.vici_cache['phone']
            
        owner_name = f"{st.session_state.vici_cache.get('first', '')} {st.session_state.vici_cache.get('last', '')}".strip()
        if owner_name: st.session_state[f"ticket_owner_{fk}"] = owner_name
        
        def smart_parse(text):
            if not text: return None, None
            match = re.search(r'\b(\d{4,6})\b', text) 
            if match: return match.group(1), text[:match.start()].strip(' -:,|#').strip()
            return None, text 

        f_cid, f_name = smart_parse(st.session_state.vici_cache['address'])
        if not f_cid: f_cid, f_name = smart_parse(st.session_state.vici_cache['comments'])
        if f_cid: 
            st.session_state[f"ticket_cid_{fk}"] = f_cid
            if f_name: st.session_state[f"ticket_salon_{fk}"] = f_name
            st.toast(f"🤖 Auto-Detected VICI: {f_name} (CID: {f_cid})")
        st.query_params.clear()

    if st.session_state.ticket_start_time is None: 
        st.session_state.ticket_start_time = houston_now
        
    start_time_display = format_excel_time(st.session_state.ticket_start_time)
    st.markdown(f"""<div style="padding: 10px; background-color: #262730; border-radius: 5px; border: 1px solid #4e4f57; text-align: center; margin-bottom: 20px;"><span style="font-size: 1.2em;">⏱️</span> <span style="font-weight: bold; color: #ff4b4b;">TICKET STARTED:</span> <span style="font-family: monospace; font-size: 1.2em;">{start_time_display} (Houston)</span></div>""", unsafe_allow_html=True)

    if not sel_agent: 
        st.warning("⚠️ Vui lòng chọn Tên Nhân Viên trước!")
        st.stop()

    # --- [V151 TÍNH NĂNG MỚI] SMART DEVICE TOOLKIT ---
    st.markdown("### 🛠️ SMART DEVICE TOOLKIT (Chẩn đoán & Tạo Note Chuẩn)")
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM sops")
    cats = [r[0] for r in c.fetchall()]
    
    if cats:
        c_tk1, c_tk2, c_tk3 = st.columns([1, 1.5, 2])
        sop_cat = c_tk1.selectbox("Loại lỗi:", cats)
        
        c.execute("SELECT device_name, steps FROM sops WHERE category=?", (sop_cat,))
        sops_data = c.fetchall()
        device_names = [r[0] for r in sops_data]
        
        if device_names:
            sop_dev = c_tk2.selectbox("Thiết bị / Tác vụ:", device_names)
            steps_str = next(r[1] for r in sops_data if r[0] == sop_dev)
            steps_list = [s.strip() for s in steps_str.split('|') if s.strip()]
            
            selected_steps = c_tk3.multiselect("Checklist đã làm:", steps_list, default=steps_list)
            
            if st.button("⚡ Chèn Note Chuẩn"):
                new_text = f"[{sop_dev}] Đã xử lý: {', '.join(selected_steps)}."
                st.session_state[f"ticket_note_{fk}"] = (st.session_state[f"ticket_note_{fk}"] + "\n" + new_text).strip()
                st.rerun()
    conn.close()
    st.markdown("---")
        
    warn_obj = st.session_state.get(f"ticket_warnings_{fk}", {})
    if isinstance(warn_obj, dict) and warn_obj.get("data"):
        if warn_obj.get("called_today"):
            st.error("🚨 **BÁO ĐỘNG ĐỎ: KHÁCH HÀNG NÀY ĐÃ GỌI LÊN TRONG HÔM NAY!** Kiểm tra ngay lịch sử bên dưới để tránh lặp Ticket.")
        else:
            st.warning("📡 **RADAR: Các lần hỗ trợ gần đây của tiệm này:**")
        
        for item in warn_obj["data"]:
            status_icon = "🟢" if "done" in item['Trạng Thái'].lower() else "🔴"
            with st.expander(f"📅 {item['Ngày']} | 👤 {item['Nhân Viên']} | {status_icon} {item['Trạng Thái']}"):
                st.markdown("**Nội dung xử lý chi tiết (Bấm icon góc phải để Copy):**")
                st.code(item['Nội Dung Note'], language="text")

    ticket_type = st.selectbox("Loại Ticket:", ["Report (Hỗ trợ)", "Training", "Demo", "SMS Refill", "SMS Drafting", "Request (16 Digits)"])
    
    btn_vici_addr = btn_vici_note = btn_vici_cid = btn_vici_clear = False
    btn_auto_fill = btn_qn1 = btn_qn2 = btn_qn3 = btn_qn4 = btn_ai = btn_save = btn_ping = False

    with st.form(key=f"ticket_form_{fk}"):
        col_left, col_right = st.columns([1.1, 1], gap="large")

        with col_left:
            st.markdown("### 🏢 THÔNG TIN KHÁCH HÀNG")
            if 'vici_cache' in st.session_state and st.session_state.vici_cache:
                v = st.session_state.vici_cache
                with st.expander(f"📡 DỮ LIỆU TỪ VICI (Click mở)", expanded=False):
                    c1, c2, c3, c4 = st.columns(4)
                    btn_vici_addr = c1.form_submit_button("🏢 Lấy Address")
                    btn_vici_note = c2.form_submit_button("📝 Chép Note")
                    btn_vici_cid = c3.form_submit_button("🆔 Lấy Vendor")
                    btn_vici_clear = c4.form_submit_button("🗑️ Xóa VICI")
                    st.caption(f"**Name:** {v['title']} {v['first']} {v['last']} | **Phone:** {v['phone']}")
                    st.caption(f"**Address:** {v['address']}, {v['city']}, {v['state']} {v['zip']}")
                    if v['comments']: st.code(v['comments'], language="text")

            c_i1, c_i2 = st.columns(2)
            new_phone = c_i1.text_input("📞 Số Điện Thoại *", value=st.session_state[f"ticket_phone_{fk}"])
            new_cid = c_i2.text_input("🆔 CID", value=st.session_state[f"ticket_cid_{fk}"])
            
            new_salon = st.text_input("🏠 Tên Tiệm", value=st.session_state[f"ticket_salon_{fk}"])
            
            c_o1, c_o2 = st.columns([2.5, 1.5])
            new_caller = c_o1.text_input("👤 Người Gọi (Owner)", value=st.session_state[f"ticket_owner_{fk}"])
            st.markdown("<style>div[data-testid='stFormSubmitButton'] button { margin-top: 28px; }</style>", unsafe_allow_html=True)
            btn_auto_fill = c_o2.form_submit_button("⚡ Tự Điền & Radar")

        with col_right:
            st.markdown("### 🛠️ NỘI DUNG XỬ LÝ")
            iso_val, train_note, demo_note, card_info, note_content = "", "", "", "", ""
            new_note = ""
            status_opts = ["Support", "Done", "No Answer"]

            if ticket_type == "Report (Hỗ trợ)": 
                new_note = st.text_area("Chi tiết hỗ trợ *", value=st.session_state[f"ticket_note_{fk}"], height=210)
                note_content = new_note
                btn_ai = st.form_submit_button("💡 GIẢI MÃ LỖI VỚI AI CHAT", type="secondary")
                
            elif ticket_type == "Training": 
                st.info("🎓 Báo Cáo Training (Lưu đồng thời vào Tab Training)")
                col_iso, col_email = st.columns([1, 1])
                iso_opt = col_iso.selectbox("ISO", ["Spoton", "1ST", "TMS", "TMDSpoton", "CINCO", "Khác"])
                train_email = col_email.text_input("Email Tiệm (Nếu có)")
                topics = st.multiselect("Topics:", ["Main Screen", "Payment", "Adjust Tip & Void", "Report & Settlement", "APPT", "GC Sale", "Settings"])
                train_detail = st.text_area("Chi tiết quá trình (VD: Em đã charge $1 và close batch...):", height=100)
                
                # Format text y hệt ảnh
                generated_note = f"TRAINING\n{iso_opt}\nTopics: {', '.join(topics)}\n=> {train_detail}"
                st.text_area("Preview Note Daily Report:", value=generated_note, disabled=True)
                
                note_content = generated_note
                train_note = train_detail # Chỉ đẩy nội dung chi tiết vào Tab Training
                iso_val = iso_opt
                
            elif ticket_type == "Request (16 Digits)": 
                st.info("💳 Yêu Cầu Check / Add / Refund Thẻ (Lưu đồng thời vào Tab 16 Digits)")
                c_r1, c_r2, c_r3 = st.columns(3)
                req_iso = c_r1.selectbox("ISO", ["SPOTON", "1ST MC", "TMS", "TMD SPOTON", "TMD TMS", "MAC"])
                req_mid = c_r2.text_input("MID (Full/Last 4)")
                req_card4 = c_r3.text_input("Card Last 4 (VD: VS 1234)")

                c_r4, c_r5, c_r6 = st.columns(3)
                req_amt = c_r4.text_input("Amount (Total)")
                req_app = c_r5.text_input("App Code / Auth")
                req_ticket = c_r6.text_input("Ticket No.")

                st.markdown("**Số tiền Yêu Cầu (Nhập số tiền nếu có):**")
                c_t1, c_t2, c_t3, c_t4 = st.columns(4)
                req_misstip = c_t1.text_input("Missed Tip")
                req_refund = c_t2.text_input("Refund")
                req_extradue = c_t3.text_input("Extra Due")
                req_void = c_t4.text_input("Void Mistake")

                req_note_extra = st.text_input("Ghi chú thêm (VD: Nhờ 2 chị request Spoton giúp tiệm)")

                # Lắp ráp Note y hệt ảnh Daily Report của Chiến Phạm
                parts = []
                if req_amt: parts.append(f"Total: {req_amt}")
                if req_card4: parts.append(req_card4)
                if req_app: parts.append(f"AC: {req_app}")
                info_str = f"({', '.join(parts)})" if parts else ""

                req_types = []
                if req_misstip: req_types.append(f"Miss Tip {req_misstip}")
                if req_refund: req_types.append(f"Refund {req_refund}")
                if req_extradue: req_types.append(f"Extra Due {req_extradue}")
                if req_void: req_types.append(f"Void Mistake {req_void}")
                type_str = " | ".join(req_types)

                today_mmdd = get_company_time().strftime('%m/%d')
                generated_note = f"Ngày {today_mmdd} #{req_ticket} {info_str} {type_str}\n=> {req_note_extra}".strip()

                st.text_area("Preview Note Daily Report:", value=generated_note, disabled=True)
                note_content = generated_note

                # Gói data để lát hàm save ném sang Tab 16 Digits
                card_info = {
                    "ISO": req_iso, "MID": req_mid, "Card4": req_card4, "Amount": req_amt,
                    "AppCode": req_app, "TicketNo": req_ticket, "MissedTip": req_misstip,
                    "Refund": req_refund, "ExtraDue": req_extradue, "VoidMistake": req_void
                }
                
            elif ticket_type == "Demo": 
                demo_note = st.text_input("Mục đích Demo")
                new_note = st.text_area("Diễn biến *", height=150)
                note_content = f"DEMO: {demo_note}\n=> {new_note}"
            elif ticket_type == "SMS Refill": 
                st.info("💰 Mua gói SMS")
                pkg = st.radio("Gói:", ["$50 (2k)", "$100 (5k)", "$200 (11k)", "$300 (17.5k)"], horizontal=True)
                c_num = st.text_input("Card Num (4 số cuối)")
                c_exp = st.text_input("EXP")
                note_content = f"Tiệm cần refill {pkg} SMS\nCard Number: **** **** **** {c_num}\nEXP: {c_exp}\n=> Nhờ 2 chị chuyển billing refill giúp tiệm"
                card_info = f"Pkg: {pkg} | Card: {c_num} | Exp: {c_exp}"
            elif ticket_type == "SMS Drafting": 
                st.info("📝 Soạn SMS")
                draft = st.text_area("Nội dung SMS chốt với khách:")
                note_content = f"Soạn SMS:\n{draft}\n=> Đã confirm nội dung, nhờ 2 chị gửi ra cho khách giúp tiệm"
                status_opts = ["Support", "Done"]
            st.markdown("---")
            status = st.selectbox("📌 Trạng thái cuối", status_opts)
            st.markdown("<br>", unsafe_allow_html=True)
            
            c_btn1, c_btn2 = st.columns([2, 1])
            btn_save = c_btn1.form_submit_button("💾 LƯU TICKET & ĐỒNG BỘ", type="primary", use_container_width=True)
            # [V151 TÍNH NĂNG MỚI] NÚT PING SUP
            btn_ping = c_btn2.form_submit_button("🚨 CỨU NÉT!", type="secondary", use_container_width=True)

    def save_current_form_state():
        st.session_state[f"ticket_phone_{fk}"] = new_phone
        st.session_state[f"ticket_salon_{fk}"] = new_salon
        st.session_state[f"ticket_cid_{fk}"] = new_cid
        st.session_state[f"ticket_owner_{fk}"] = new_caller
        st.session_state[f"ticket_note_{fk}"] = new_note

    if btn_vici_addr:
        save_current_form_state(); st.session_state[f"ticket_salon_{fk}"] = v['address']; st.rerun()
    if btn_vici_note:
        save_current_form_state(); st.session_state[f"ticket_note_{fk}"] = (new_note + "\n" + v['comments']).strip(); st.rerun()
    if btn_vici_cid:
        save_current_form_state(); st.session_state[f"ticket_cid_{fk}"] = v['vendor_id']; st.rerun()
    if btn_vici_clear:
        save_current_form_state(); del st.session_state.vici_cache; st.rerun()

    if btn_auto_fill:
        save_current_form_state()
        lookup_val = new_phone.strip() if new_phone.strip() else new_cid.strip()
        st.session_state[f"ticket_warnings_{fk}"] = {} 
        
        if lookup_val:
            with st.spinner("Đang lục tìm & Quét Radar..."):
                found_data = None
                if df_sidebar is not None and not df_sidebar.empty:
                    df_search = df_sidebar.copy()
                    if 'Date_Obj' not in df_search.columns:
                        try: df_search['Date_Obj'] = pd.to_datetime(df_search['Date'], errors='coerce')
                        except: pass
                    if 'Date_Obj' in df_search.columns:
                        df_search = df_search.sort_values('Date_Obj', ascending=False)
                        
                    w_mask = pd.Series([False]*len(df_search))
                    w_mask |= df_search['Phone'].astype(str).str.contains(lookup_val, case=False, na=False)
                    w_mask |= df_search['CID'].astype(str).str.contains(lookup_val, case=False, na=False)
                    
                    if w_mask.any():
                        match_row = df_search[w_mask].iloc[0]
                        found_data = {"salon": str(match_row.get('Salon_Name', '')), "cid": str(match_row.get('CID', '')), "phone": str(match_row.get('Phone', '')), "owner": str(match_row.get('Caller_Info', ''))}

                if not found_data:
                    conn = sqlite3.connect('crm_data.db')
                    c = conn.cursor()
                    c.execute("SELECT Salon_Name, CID, Phone, Caller_Info FROM tickets WHERE Phone LIKE ? OR CID LIKE ? ORDER BY id DESC LIMIT 1", (f"%{lookup_val}%", f"%{lookup_val}%"))
                    res = c.fetchone()
                    if res: found_data = {"salon": res[0], "cid": res[1], "phone": res[2], "owner": res[3]}
                    conn.close()
                
                if not found_data:
                    master_data = load_master_db()
                    df_cid = master_data.get('CID', pd.DataFrame())
                    if not df_cid.empty:
                        try:
                            mask = df_cid.astype(str).apply(lambda x: x.str.contains(lookup_val, case=False, na=False)).any(axis=1)
                            res_df = df_cid[mask]
                            if not res_df.empty:
                                first_row = res_df.iloc[0]
                                cols = [str(c).lower().strip() for c in df_cid.columns]
                                def get_val(col_keywords, default_idx):
                                    for idx, c_name in enumerate(cols):
                                        if any(k in c_name for k in col_keywords): return str(first_row.iloc[idx])
                                    return str(first_row.iloc[default_idx]) if len(first_row) > default_idx else ""
                                found_data = {"salon": get_val(["salon", "name", "tiệm"], 0), "cid": get_val(["cid", "id"], 1) or lookup_val, "phone": get_val(["phone", "sđt", "tel"], 2), "owner": get_val(["owner", "caller", "contact"], 3)}
                        except: pass

                if found_data:
                    st.session_state[f"ticket_salon_{fk}"] = found_data.get("salon", "")
                    st.session_state[f"ticket_cid_{fk}"] = found_data.get("cid", "")
                    st.session_state[f"ticket_phone_{fk}"] = found_data.get("phone", "")
                    st.session_state[f"ticket_owner_{fk}"] = found_data.get("owner", "")
                    st.toast("✅ Đã tự động điền dữ liệu!", icon="⚡")
                    
                    radar_data, called_today, today_str = [], False, get_company_time().strftime('%m/%d/%Y')
                    if df_sidebar is not None and not df_sidebar.empty:
                        r_mask = pd.Series([False]*len(df_sidebar))
                        if found_data.get("phone", ""): r_mask |= df_sidebar['Phone'].astype(str).str.contains(found_data.get("phone", ""), case=False, na=False)
                        if found_data.get("cid", ""): r_mask |= df_sidebar['CID'].astype(str).str.contains(found_data.get("cid", ""), case=False, na=False)
                        if r_mask.any():
                            df_recent = df_sidebar[r_mask].copy()
                            if 'Date_Obj' not in df_recent.columns:
                                try: df_recent['Date_Obj'] = pd.to_datetime(df_recent['Date'], errors='coerce')
                                except: pass
                            if 'Date_Obj' in df_recent.columns: df_recent = df_recent.sort_values('Date_Obj', ascending=False)
                            for _, r in df_recent.head(5).iterrows():
                                d_str = format_date_display(r.get('Date',''))
                                if d_str == today_str: called_today = True
                                full_note_text = str(r.get('Issue_Category', r.get('Note', '')))
                                if r.get('Ticket_Type') == 'Training' and r.get('Training_Note'): full_note_text = str(r.get('Training_Note')) + " | " + full_note_text
                                radar_data.append({"Ngày": d_str, "Nhân Viên": r.get('Agent_Name', 'Unknown'), "Trạng Thái": r.get('Status', ''), "Nội Dung Note": full_note_text})
                            st.session_state[f"ticket_warnings_{fk}"] = {"data": radar_data, "called_today": called_today}
                else: st.warning("⚠️ Không tìm thấy tiệm trong DB. Vui lòng nhập tay.")
        st.rerun()

    if btn_ai:
        save_current_form_state()
        if new_note: ai_assistant_dialog(new_note)
        else: st.warning("⚠️ Vui lòng nhập nội dung lỗi trước.")
        
    # LOGIC NÚT PING CỨU NÉT
    if btn_ping:
        save_current_form_state()
        if new_salon or new_phone:
            conn = sqlite3.connect('crm_data.db')
            c = conn.cursor()
            created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute("INSERT INTO escalations (agent_name, salon_name, phone, note, status, created_at) VALUES (?, ?, ?, ?, 'Active', ?)",
                      (sel_agent, new_salon, new_phone, new_note, created))
            conn.commit()
            conn.close()
            st.error(f"🚨 ĐÃ PHÁT TÍN HIỆU CỨU NÉT LÊN DASHBOARD CỦA SUP! Vui lòng giữ máy với khách và chờ hỗ trợ.")
        else:
            st.warning("⚠️ Vui lòng điền ít nhất Tên tiệm hoặc Số điện thoại để SUP biết bạn đang hỗ trợ ai!")

    if btn_save:
        if new_phone: 
            end_dt = get_company_time()
            end_time_str = format_excel_time(end_dt)
            start_dt = st.session_state.ticket_start_time if st.session_state.ticket_start_time else end_dt
            duration_mins = int((end_dt - start_dt).total_seconds() / 60)
            start_time_str = format_excel_time(start_dt)
            dt_str = start_dt.strftime('%m/%d/%Y')
            
            data_pack = {
                'Date_Obj': start_dt, 
                'Date_Str': dt_str, 
                'Salon_Name': new_salon, 
                'Agent_Name': sel_agent, 
                'Support_Time': start_time_str, 
                'End_Time': end_time_str, 
                'Duration': duration_mins, 
                'Phone': new_phone, 
                'CID': new_cid, 
                'Note': note_content, 
                'Status': status, 
                'Caller_Info': new_caller, 
                'Ticket_Type': ticket_type, 
                'Training_Note': train_note, 
                'Card_16_Digits': str(card_info) if isinstance(card_info, dict) else card_info,
                'Card_Dict': card_info if isinstance(card_info, dict) else {}, # Chuyền dict sang tab 16 Digits
                'Train_ISO': iso_val if ticket_type == "Training" else "",
                'Train_Email': train_email if ticket_type == "Training" else ""
            }
            
            is_dup = check_recent_duplicate(new_phone, sel_agent)
            confirm_save_dialog(data_pack, is_duplicate=is_dup)
        else: 
            save_current_form_state()
            st.warning("⚠️ Vui lòng nhập Số điện thoại trước khi lưu.")

# =========================================================
# MODULE 2: TAB "CẦN FOLLOW-UP" CỦA CÁ NHÂN
# =========================================================
elif menu == "📌 Cần Follow-up":
    st.title(f"📌 Danh sách Cần Follow-up")
    if not sel_agent:
        st.warning("⚠️ Vui lòng chọn Tên Nhân Viên ở menu bên trái trước!")
    else:
        with st.spinner("⏳ Đang tải dữ liệu Follow-up..."):
            df_fu = load_gsheet_data(sheets)
        
        if not df_fu.empty:
            df_fu['Status_Norm'] = df_fu['Status'].astype(str).str.lower()
            mask_fu = (df_fu['Agent_Name'] == sel_agent) & (df_fu['Status_Norm'].str.contains('support') | df_fu['Status_Norm'].str.contains('pending'))
            df_pending = df_fu[mask_fu].copy()
            
            if not df_pending.empty:
                if "Date" in df_pending.columns: 
                    df_pending['Date_Obj'] = pd.to_datetime(df_pending['Date'], errors='coerce')
                    df_pending = df_pending.sort_values('Date_Obj', ascending=False)
                
                df_pending['Display_Date'] = df_pending['Date'].apply(format_date_display)
                df_pending['Status'] = df_pending['Status'].apply(map_status_badge)
                
                st.info(f"🚨 Hiện tại bạn đang có **{len(df_pending)}** ticket cần xử lý (Support/Pending). Vui lòng follow-up và chuyển sang Done.")
                
                cols_fu = ['Display_Date', 'Salon_Name', 'Phone', 'CID', 'Ticket_Type', 'Note', 'Status']
                final_cols_fu = [c for c in cols_fu if c in df_pending.columns]
                
                @st.dialog("📝 XỬ LÝ TICKET FOLLOW-UP")
                def process_followup_ticket(row):
                    st.info(f"🏠 {row.get('Salon_Name')} | {row.get('Ticket_Type')}")
                    
                    st.markdown("**📋 COPY SANG VIBER (Click biểu tượng copy):**")
                    viber_str = get_viber_copy_format(row.get('Salon_Name', ''), row.get('CID', ''), row.get('Phone', ''), row.get('Caller_Info', ''), row.get('Note', ''))
                    st.code(viber_str, language="text")
                    
                    st.text_area("Nội dung hiện tại (Read-only):", value=str(row.get('Note')), height=100, disabled=True)
                    st.markdown("---")
                    
                    new_status = st.selectbox("Trạng thái mới", ["Support", "Done", "No Answer", "Request", "Forwarded by SUP"], index=1)
                    current_note = str(row.get('Note'))
                    new_note = st.text_area("Cập nhật / Bổ sung Ghi chú:", value=current_note + "\n[Follow-up]: ", height=150)
                    
                    if st.button("Lưu Thay Đổi (Cập nhật 2 nơi)", type="primary"):
                        clean_status = re.sub(r'^[🟢🔴🟠⚫]\s*', '', str(new_status))
                        update_ticket(row.get('id'), clean_status, new_note, row.get('Salon_Name'), row.get('Phone'), row.get('CID'), row.get('Caller_Info'), str(row.get('Card_16_Digits', '')))
                        with st.spinner("Đang cập nhật Google Sheet & Đổi màu..."):
                            date_str = row.get('Display_Date') if row.get('Display_Date') else row.get('Date')
                            success, msg = update_google_sheet_row(date_str, row.get('Phone'), row.get('Salon_Name'), clean_status, new_note)
                        if success: 
                            st.cache_data.clear() 
                            st.success(f"✅ Đã cập nhật Database!\n{msg}")
                            time.sleep(1)
                            st.rerun()
                        else: 
                            st.warning(f"✅ Đã cập nhật Database nhưng ❌ {msg}")
                            st.rerun()

                event_fu = st.dataframe(df_pending[final_cols_fu], hide_index=True, use_container_width=True, selection_mode="single-row", on_select="rerun", column_config={"Note": st.column_config.TextColumn("Nội dung", width="large")})
                if len(event_fu.selection.rows) > 0: process_followup_ticket(df_pending.iloc[event_fu.selection.rows[0]])
            else: st.success("🎉 Chúc mừng! Bạn không có ticket nào đang tồn đọng cần xử lý.")
        else: st.info("Chưa có dữ liệu.")
# =========================================================
# =========================================================
# MODULE TÍNH NĂNG MỚI: INBOX PHÂN VIỆC TỪ SUP
# =========================================================
elif menu == "📥 Inbox Phân Việc":
    st.title("📥 Hộp Thư Phân Việc Từ SUP")
    if not sel_agent:
        st.warning("⚠️ Vui lòng chọn Tên Nhân Viên trước!")
    else:
        tab_pending, tab_history = st.tabs(["🔴 Việc Mới (Cần Nhận)", "🟢 Lịch Sử & Đang Xử Lý"])
        
        with tab_pending:
            conn = sqlite3.connect('crm_data.db')
            df_inbox = pd.read_sql_query("SELECT id, salon_name as 'Tên Tiệm', phone as 'SĐT', note as 'Nội dung dặn dò', created_by as 'Người giao', created_at as 'Thời gian giao' FROM dispatches WHERE target_agent=? AND status='Pending'", conn, params=(sel_agent,))
            conn.close()
            
            if df_inbox.empty:
                st.success("🎉 Bạn đang không có task mới nào. Rất tuyệt vời!")
            else:
                st.error(f"🚨 Có {len(df_inbox)} ticket mới từ SUP!")
                for idx, row in df_inbox.iterrows():
                    with st.expander(f"✉️ {row['Tên Tiệm']} - SĐT: {row['SĐT']} (Từ: {row['Người giao']})", expanded=True):
                        st.markdown(f"**⏰ Thời gian nhận:** {row['Thời gian giao']}")
                        st.info(f"**Lời dặn:** {row['Nội dung dặn dò']}")
                        
                        if st.button("🚀 XÁC NHẬN NHẬN TICKET NÀY", key=f"take_{row['id']}", type="primary"):
                            conn = sqlite3.connect('crm_data.db')
                            c = conn.cursor()
                            c.execute("UPDATE dispatches SET status='In Progress' WHERE id=?", (row['id'],))
                            conn.commit()
                            conn.close()
                            
                            fk = st.session_state.form_key
                            st.session_state[f"ticket_salon_{fk}"] = row['Tên Tiệm']
                            st.session_state[f"ticket_phone_{fk}"] = row['SĐT']
                            st.session_state[f"ticket_note_{fk}"] = f"[Giao từ {row['Người giao']}]: {row['Nội dung dặn dò']}\n\n-> Xử lý: "
                            
                            st.toast("✅ Đã nhận việc! Chuyển sang Tab 'New Ticket' để xử lý.", icon="🔥")
                            time.sleep(1)
                            st.rerun()

        with tab_history:
            conn = sqlite3.connect('crm_data.db')
            # Lấy các task Đang làm hoặc Đã xong
            df_hist = pd.read_sql_query("SELECT id, salon_name as 'Tên Tiệm', phone as 'SĐT', note as 'Nội dung dặn dò', created_by as 'Người giao', created_at as 'Thời gian giao', status as 'Trạng thái' FROM dispatches WHERE target_agent=? AND status != 'Pending' ORDER BY id DESC LIMIT 20", conn, params=(sel_agent,))
            conn.close()
            
            if df_hist.empty:
                st.info("Chưa có lịch sử nhận việc.")
            else:
                st.markdown("*(Tại đây bạn có thể xem lại các việc đã nhận, và đánh dấu Done khi xử lý xong để SUP biết)*")
                for idx, row in df_hist.iterrows():
                    status_color = "🟠 Đang xử lý" if row['Trạng thái'] == 'In Progress' else "🟢 Đã xong"
                    with st.expander(f"[{status_color}] {row['Tên Tiệm']} - SĐT: {row['SĐT']} (Từ: {row['Người giao']})"):
                        st.write(f"**Nội dung dặn dò:** {row['Nội dung dặn dò']}")
                        st.caption(f"Nhận lúc: {row['Thời gian giao']}")
                        
                        # Nếu đang xử lý thì hiện nút Báo Cáo Xong
                        if row['Trạng thái'] == 'In Progress':
                            if st.button("✅ Báo cáo ĐÃ XỬ LÝ XONG (Done)", key=f"done_{row['id']}"):
                                conn = sqlite3.connect('crm_data.db')
                                c = conn.cursor()
                                c.execute("UPDATE dispatches SET status='Done' WHERE id=?", (row['id'],))
                                conn.commit()
                                conn.close()
                                st.success("Đã báo cáo hoàn thành cho SUP!")
                                st.rerun()

# ==========================================
# KHU VỰC TÌM KIẾM MASTER DATA & HISTORY
# ==========================================
elif menu == "🗂️ Tra cứu Master Data":
    st.title("🗂️ Tra cứu Master Data (CID Salon)")
    with st.spinner("Đang tải Master Data..."): master_data = load_master_db()
    if "Error" in master_data: 
        st.error(f"❌ Lỗi: {master_data['Error']}"); st.info("💡 Check quyền Share file 'CID Salon'.")
    else:
        tab_cid, tab_conf, tab_note, tab_term = st.tabs(["🔎 Tra cứu CID/Tiệm", "🚨 Special (Confirm)", "📝 ISO & General Note", "🔧 Terminal Fix"])
        with tab_cid:
            st.subheader("🔎 Tìm kiếm Thông tin Tiệm")
            df_cid = master_data.get('CID', pd.DataFrame())
            col_s1, col_s2 = st.columns([3, 1])
            search_term = col_s1.text_input("Nhập CID hoặc Tên Tiệm:", placeholder="VD: 07562")
            if 'search_result_df' not in st.session_state: st.session_state.search_result_df = None
            enable_bot = st.checkbox("Bot Online (Dùng khi Master DB không có)", value=False)
            if st.button("🚀 Tìm kiếm", type="primary"):
                if search_term:
                    if not df_cid.empty:
                        mask = df_cid.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
                        st.dataframe(df_cid[mask], use_container_width=True)
                    if enable_bot:
                        if is_cloud_mode: st.warning("⚠️ Bot chỉ chạy trên Localhost.")
                        else:
                            with st.spinner(f"🤖 Bot đang tra cứu ngầm..."): st.session_state.search_result_df = run_search_engine(search_term)
            if st.session_state.search_result_df is not None and not st.session_state.search_result_df.empty:
                st.success(f"✅ Bot tìm thấy kết quả:")
                st.dataframe(st.session_state.search_result_df, use_container_width=True)
                if st.button("💾 Lưu kết quả vào Database"):
                    success, msg = save_to_master_db_gsheet(st.session_state.search_result_df)
                    if success: st.success(f"✅ {msg}"); st.balloons(); st.cache_data.clear()
                    else: st.error(f"❌ {msg}")
        with tab_conf:
             st.dataframe(master_data.get('CONFIRMATION', pd.DataFrame()), use_container_width=True)
             with st.form("upd_note"):
                 t_cid, t_note = st.text_input("CID"), st.text_area("Note mới") 
                 if st.form_submit_button("Lưu Note"): 
                     res, msg = update_confirmation_note(t_cid, t_note)
                     if res: st.success(msg) 
                     else: st.error(msg)
        with tab_note:
            df_note = master_data.get('NOTE', pd.DataFrame())
            if not df_note.empty:
                cols = st.columns(2)
                for index, row in df_note.iterrows():
                    title = str(row[0]).strip() if len(row) > 0 else ""
                    content = str(row[1]).strip() if len(row) > 1 else ""
                    if title and content:
                        with cols[index % 2]: st.markdown(f"""<div style="background:#f0f2f6;padding:15px;border-radius:10px;margin-bottom:10px;"><div style="color:#004085;font-weight:bold;">{title}</div><div>{content}</div></div>""", unsafe_allow_html=True)
        with tab_term:
            df_term = master_data.get('TERMINAL', pd.DataFrame())
            if not df_term.empty:
                search_term = st.text_input("🔎 Tìm kiếm lỗi Terminal:", placeholder="Nhập mã lỗi...")
                for index, row in df_term.iterrows():
                    if index == 0: continue
                    full_title = f"🔌 {str(row[0])} - {str(row[1])}"
                    if search_term and search_term.lower() not in full_title.lower(): continue
                    with st.expander(full_title): st.markdown(f"**🛠️ Integrate:**\n{str(row[2])}\n\n**📲 Update:**\n{str(row[3])}")

elif menu == "🔍 Search & History":
    st.title("🔍 Tra cứu & Lịch sử")
    with st.spinner("⏳ Đang tải dữ liệu lịch sử..."): df = load_gsheet_data(sheets)

    term = st.text_input("🔎 Nhập từ khóa (Tên tiệm, SĐT, CID):")
    filter_type = st.radio("Lọc:", ["Tất cả", "Training", "Request (16 Digits)", "SMS"], horizontal=True)
    
    if term and not df.empty:
        mask = pd.Series([False]*len(df))
        cols = ['Salon_Name', 'Phone', 'CID', 'Agent_Name', 'Date']
        valid = [c for c in cols if c in df.columns] 
        for c in valid: mask |= df[c].astype(str).str.lower().str.contains(term.lower(), na=False)
            
        df_search = df[mask].copy()
        if filter_type == 'Training': df_search = df_search[df_search['Ticket_Type'] == 'Training']
        elif filter_type == 'Request (16 Digits)': df_search = df_search[df_search['Ticket_Type'].str.contains('Request', na=False)]
        elif filter_type == 'SMS': df_search = df_search[df_search['Ticket_Type'].str.contains('SMS', na=False)]
            
        if not df_search.empty:
            if "Date" in df_search.columns: 
                df_search['Date_Obj'] = pd.to_datetime(df_search['Date'], errors='coerce')
                df_search = df_search.sort_values('Date_Obj', ascending=False)
                
            df_search['Display_Date'] = df_search['Date'].apply(format_date_display)
            df_search['Status'] = df_search['Status'].apply(map_status_badge)
            
            cols = ['Display_Date','Agent_Name','Ticket_Type','Salon_Name','Note','Status'] 
            if filter_type == 'Request (16 Digits)': cols.append('Card_16_Digits')
            final_cols = [c for c in cols if c in df_search.columns]
            
            @st.dialog("📝 CẬP NHẬT TICKET (2 CHIỀU)")
            def edit_ticket(row):
                st.info(f"🏠 {row.get('Salon_Name')} | {row.get('Ticket_Type')}")
                st.markdown("**📋 COPY SANG VIBER:**")
                st.code(get_viber_copy_format(row.get('Salon_Name', ''), row.get('CID', ''), row.get('Phone', ''), row.get('Caller_Info', ''), row.get('Note', '')), language="text")
                st.text_area("Nội dung hiện tại (Read-only):", value=str(row.get('Note')), height=100, disabled=True)
                new_card, new_exp = "", "" 
                if "Request" in str(row.get('Ticket_Type')): 
                    st.markdown("---"); st.warning("💳 **KHU VỰC SUP NHẬP THÔNG TIN THẺ**")
                    c1, c2 = st.columns(2)
                    current_card = str(row.get('Card_16_Digits', ''))
                    curr_num = current_card.split('|')[0].strip() if '|' in current_card else current_card
                    new_card = c1.text_input("16 Số Thẻ (Full)", value=curr_num)
                    new_exp = c2.text_input("EXP Date")
                st.markdown("---")
                new_status = st.selectbox("Trạng thái mới", ["Support", "Done", "No Answer", "Request", "Forwarded by SUP"], index=0)
                new_note = st.text_area("Cập nhật / Bổ sung Ghi chú:", value=str(row.get('Note')), height=150)
                
                if st.button("Lưu Thay Đổi (Cập nhật 2 nơi)"):
                    clean_status = re.sub(r'^[🟢🔴🟠⚫]\s*', '', str(new_status))
                    update_ticket(row.get('id'), clean_status, new_note, row.get('Salon_Name'), row.get('Phone'), row.get('CID'), row.get('Caller_Info'), new_card, new_exp)
                    with st.spinner("Đang cập nhật Google Sheet & Đổi màu..."):
                        date_str = row.get('Display_Date') if row.get('Display_Date') else row.get('Date')
                        success, msg = update_google_sheet_row(date_str, row.get('Phone'), row.get('Salon_Name'), clean_status, new_note)
                    if success: st.cache_data.clear(); st.success(f"✅ Đã cập nhật Database!\n{msg}"); time.sleep(1); st.rerun()
                    else: st.warning(f"✅ Đã cập nhật Database nhưng ❌ {msg}"); st.rerun()
                        
            event = st.dataframe(df_search[final_cols], hide_index=True, use_container_width=True, selection_mode="single-row", on_select="rerun", column_config={"Note": st.column_config.TextColumn("Nội dung", width="large")}) 
            if len(event.selection.rows) > 0: edit_ticket(df_search.iloc[event.selection.rows[0]])
        else: st.info("Không tìm thấy kết quả.")

# =========================================================
# MODULE 4: COMMAND CENTER (TÍCH HỢP XỬ LÝ CỨU NÉT)
# =========================================================
elif menu == "📊 Dashboard (SUP Only)":
    st.title("📊 Trung Tâm Điều Hành SUP (Command Center)")
    company_now = get_company_time()
    
    # --- [V151 TÍNH NĂNG MỚI] HIỂN THỊ CẢNH BÁO CỨU NÉT TỪ AGENT ---
    conn = sqlite3.connect('crm_data.db')
    df_esc = pd.read_sql_query("SELECT * FROM escalations WHERE status='Active'", conn)
    if not df_esc.empty:
        st.error(f"🚨 CẢNH BÁO: ĐANG CÓ {len(df_esc)} TÍN HIỆU CẦN CỨU NÉT TỪ AGENT! 🚨")
        for idx, row in df_esc.iterrows():
            with st.expander(f"🆘 Lệnh cứu nét từ [ {row['agent_name']} ] - Tiệm: {row['salon_name']} ({row['phone']})", expanded=True):
                st.markdown(f"**Lúc:** {row['created_at']}")
                st.code(row['note'], language="text")
                if st.button(f"✅ Đã tiếp nhận & Hỗ trợ xong (ID: {row['id']})", key=f"esc_{row['id']}"):
                    c = conn.cursor()
                    c.execute("UPDATE escalations SET status='Resolved' WHERE id=?", (row['id'],))
                    conn.commit()
                    st.toast("Đã đóng tín hiệu cứu nét!")
                    st.rerun()
    conn.close()
    # -------------------------------------------------------------

    with st.spinner("⏳ Đang tải dữ liệu vận hành..."): df = load_gsheet_data(sheets)
        
    if not df.empty:
        df_chart = df.copy() 
        if 'Date' in df_chart.columns: 
            df_chart['Date_Obj'] = pd.to_datetime(df_chart['Date'], errors='coerce')
            df_chart = df_chart.dropna(subset=['Date_Obj'])
            df_chart['Status_Norm'] = df_chart['Status'].astype(str).str.lower()
            
        with st.expander("📅 BỘ LỌC DỮ LIỆU", expanded=False):
            col_filter, col_range = st.columns([1, 2])
            filter_mode = col_filter.radio("Thời gian:", ["Hôm nay", "Tuần này", "Tháng này"], horizontal=True)
            today_company = company_now.date()
            if filter_mode == "Hôm nay": d_start, d_end = today_company, today_company
            elif filter_mode == "Tuần này": d_start, d_end = today_company - timedelta(days=today_company.weekday()), today_company
            else: d_start, d_end = today_company.replace(day=1), today_company
                
            mask = (df_chart['Date_Obj'].dt.date >= d_start) & (df_chart['Date_Obj'].dt.date <= d_end)
            df_filtered = df_chart.loc[mask].copy()
            
        if df_filtered.empty: st.warning(f"⚠️ Không có dữ liệu trong khoảng {d_start} đến {d_end}.")
        else:
            # Đã bổ sung lại tab_bao_cao và "📈 Xuất Báo Cáo"
            tab_giao_ca, tab_giao_viec, tab_email_iso, tab_diem_mu, tab_su_co, tab_bao_cao, tab_co_ban = st.tabs([
                "🔄 Trạm Giao Ca", "📥 Giao Việc", "📤 Gửi Email ISO", "🎯 Phân Tích Điểm Mù", "🚨 Bắt Mạch Sự Cố", "📈 Xuất Báo Cáo", "📊 Biểu Đồ"
            ])
            
            with tab_giao_ca:
                st.markdown("### 🔄 Trạm Bàn Giao Ca Sắp Tới")
                df_pending = df_filtered[df_filtered['Status_Norm'].str.contains('pending') | df_filtered['Status_Norm'].str.contains('support')].copy()
                if df_pending.empty: st.success("🎉 Cả team đã clear sạch ticket trong ca! Giao ca cực kỳ thoải mái.")
                else:
                    st.info(f"🚨 Đang có {len(df_pending)} ticket tồn đọng cần bàn giao cho ca sau.")
                    col_urg1, col_urg2 = st.columns(2)
                    with col_urg1:
                        st.markdown("**📌 Top Tiệm Gọi Nhiều Lần (Tồn đọng)**")
                        top_urgent = df_pending['Salon_Name'].value_counts().reset_index()
                        top_urgent.columns = ['Tên Tiệm', 'Số ticket đang treo']
                        st.dataframe(top_urgent[top_urgent['Số ticket đang treo'] > 1], hide_index=True, use_container_width=True)
                    with col_urg2:
                        st.markdown("**👤 Trách Nhiệm Tồn Đọng Theo Agent**")
                        pending_agent = df_pending['Agent_Name'].value_counts().reset_index()
                        pending_agent.columns = ['Agent', 'Số lượng']
                        st.dataframe(pending_agent, hide_index=True, use_container_width=True)
                    st.markdown("**📋 Chi Tiết Danh Sách Tồn Đọng**")
                    st.dataframe(df_pending[['Agent_Name', 'Salon_Name', 'Phone', 'Issue_Category', 'Note']], hide_index=True, use_container_width=True)
                    if st.button("✅ XÁC NHẬN NHẬN CA (Takeover)", type="primary"): st.toast("Ca mới đã được tiếp nhận!", icon="🚀"); st.balloons()
        # --- TÍNH NĂNG 1: TRẠM GIAO VIỆC NỘI BỘ (ĐÃ CẬP NHẬT TRA CỨU & TRACKING) ---
            with tab_giao_viec:
                st.markdown("### 📥 Trạm Giao Việc Nội Bộ (Dispatch Hub)")
                
                # 1. Khởi tạo biến nhớ tạm cho ô Auto-fill
                if 'disp_salon' not in st.session_state: st.session_state.disp_salon = ""
                if 'disp_phone' not in st.session_state: st.session_state.disp_phone = ""

                # 2. Cụm tra cứu nhanh bằng CID / Phone
                c_s1, c_s2 = st.columns([3, 1])
                search_kw = c_s1.text_input("🔍 Tra cứu nhanh (Nhập CID hoặc SĐT) để tự điền:")
                if c_s2.button("Tìm & Điền", use_container_width=True):
                    if search_kw:
                        with st.spinner("Đang lục tìm dữ liệu..."):
                            conn = sqlite3.connect('crm_data.db')
                            c = conn.cursor()
                            c.execute("SELECT Salon_Name, Phone FROM tickets WHERE CID LIKE ? OR Phone LIKE ? ORDER BY id DESC LIMIT 1", (f"%{search_kw}%", f"%{search_kw}%"))
                            res = c.fetchone()
                            conn.close()
                            
                            if res:
                                st.session_state.disp_salon = res[0]
                                st.session_state.disp_phone = res[1]
                                st.rerun()
                            else:
                                st.warning("⚠️ Không tìm thấy thông tin trong Database.")

                # 3. Form Giao việc đã được Auto-fill
                with st.form("dispatch_form"):
                    col_d1, col_d2, col_d3 = st.columns([1, 1, 1])
                    d_agent = col_d1.selectbox("Chọn Agent nhận việc:", active_users)
                    d_phone = col_d2.text_input("SĐT Khách (Bắt buộc):", value=st.session_state.disp_phone)
                    d_salon = col_d3.text_input("Tên Tiệm:", value=st.session_state.disp_salon)
                    d_note = st.text_input("Lời dặn dò cho Agent (Ví dụ: Gọi check lại mạng giùm chị, tiệm này đang gắt):")
                    
                    if st.form_submit_button("🚀 PHÓNG LỆNH GIAO VIỆC", type="primary"):
                        if d_phone:
                            conn = sqlite3.connect('crm_data.db')
                            c = conn.cursor()
                            created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            c.execute("INSERT INTO dispatches (target_agent, salon_name, phone, note, status, created_by, created_at) VALUES (?, ?, ?, ?, 'Pending', ?, ?)", 
                                      (d_agent, d_salon, d_phone, d_note, st.session_state.current_user, created))
                            conn.commit()
                            conn.close()
                            
                            # Xóa bộ nhớ form sau khi giao
                            st.session_state.disp_salon = ""
                            st.session_state.disp_phone = ""
                            st.success(f"✅ Đã giao ticket thành công cho {d_agent}!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("⚠️ Vui lòng nhập Số điện thoại của khách.")
                            
                # 4. Bảng Theo dõi tiến độ Giao việc
                st.markdown("---")
                st.markdown("### 📋 Lịch Sử & Tiến Độ Việc Đã Giao")
                conn = sqlite3.connect('crm_data.db')
                df_dispatched = pd.read_sql_query("SELECT id, target_agent as 'Giao cho', salon_name as 'Tên Tiệm', phone as 'SĐT', note as 'Nội dung', created_at as 'Lúc giao', status as 'Trạng thái' FROM dispatches ORDER BY id DESC LIMIT 50", conn)
                conn.close()
                
                if not df_dispatched.empty:
                    # Chuyển đổi trạng thái sang text tiếng Việt có biểu tượng
                    def color_status(val):
                        if val == 'Done': return '🟢 Đã xong'
                        elif val == 'In Progress': return '🟠 Đang làm'
                        return '🔴 Chưa nhận (Pending)'
                        
                    df_dispatched['Trạng thái'] = df_dispatched['Trạng thái'].apply(color_status)
                    st.dataframe(df_dispatched, hide_index=True, use_container_width=True)
                else:
                    st.info("Chưa có lệnh giao việc nào trong hệ thống.")
            # --- TÍNH NĂNG 2: CỔNG PHÓNG EMAIL TỰ ĐỘNG CHO ISO ---
            with tab_email_iso:
                st.markdown("### 📤 Cổng Gửi Email Tự Động (Auto-Email Gateway)")
                st.caption("Hệ thống tự động lọc các Ticket có trạng thái 'Request'. Bấm nút là Email mở ra với đầy đủ Tiêu đề, Nội dung, MID.")
                
                # Lọc ticket đang ở trạng thái Request
                df_requests = df_filtered[df_filtered['Status_Norm'].str.contains('request') | df_filtered['Ticket_Type'].str.contains('Request')].copy()
                
                if df_requests.empty:
                    st.success("🎉 Hiện không có Ticket nào cần gửi Request cho Hãng (ISO).")
                else:
                    for idx, req in df_requests.iterrows():
                        with st.expander(f"🎟️ {req.get('Salon_Name', 'Unknown')} - Phụ trách: {req.get('Agent_Name', '')} | CID: {req.get('CID', '')}", expanded=True):
                            st.write(f"**Nội dung Request:** {req.get('Note', '')}")
                            st.write(f"**Thông tin Thẻ/MID:** {req.get('Card_16_Digits', '')}")
                            
                            c_iso1, c_iso2, c_iso3 = st.columns(3)
                            
                            # Thuật toán tạo URL mailto chuẩn (Tự động điền To, Subject, Body)
                            subject = f"[LLDTEK - Urgent Support] Request for DBA: {req.get('Salon_Name', '')} - CID: {req.get('CID', '')}"
                            body = f"Hello Team,\n\nPlease assist with the following request:\n\nDBA: {req.get('Salon_Name', '')}\nCID: {req.get('CID', '')}\nPhone: {req.get('Phone', '')}\nDetails: {req.get('Note', '')}\nExtra Info (MID/Card): {req.get('Card_16_Digits', '')}\n\nThank you,\nLLDTEK Technical Support"
                            
                            import urllib.parse
                            def make_mailto(email_to):
                                return f"mailto:{email_to}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(body)}"
                            
                            # Thay email dưới đây bằng email thực của các ISO
                            c_iso1.link_button("📧 Phóng Email -> SPOTON", make_mailto("support@spoton.com"), use_container_width=True)
                            c_iso2.link_button("📧 Phóng Email -> 1ST", make_mailto("help@1st.com"), use_container_width=True)
                            c_iso3.link_button("📧 Phóng Email -> TMS", make_mailto("tech@tms.com"), use_container_width=True)
                            
                            st.caption("*(Lưu ý: Bấm nút trên sẽ tự động mở Outlook/Gmail trên máy bạn với đầy đủ nội dung được điền sẵn)*")
            with tab_diem_mu:
                st.markdown("### 🎯 Phân Tích Điểm Mù Kỹ Năng Kỹ Thuật")
                def categorize_issue(text):
                    t = str(text).lower()
                    if 'in' in t or 'printer' in t or 'epson' in t: return 'Lỗi Máy In'
                    if 'mạng' in t or 'network' in t or 'router' in t or 'wifi' in t: return 'Lỗi Mạng'
                    if 'đơ' in t or 'treo' in t or 'pos' in t: return 'Lỗi POS'
                    if 'thẻ' in t or 'card' in t or 'decline' in t or 'pax' in t: return 'Lỗi Cà Thẻ'
                    return 'Lỗi Khác'
                df_filtered['Nhóm_Lỗi'] = df_filtered['Note'].apply(categorize_issue)
                df_skill_pending = df_filtered[df_filtered['Status_Norm'].str.contains('support') | df_filtered['Status_Norm'].str.contains('pending')]
                if not df_skill_pending.empty:
                    cross_tab = pd.crosstab(df_skill_pending['Agent_Name'], df_skill_pending['Nhóm_Lỗi'])
                    fig_heatmap = px.imshow(cross_tab, text_auto=True, color_continuous_scale='Reds', aspect="auto", title="🔥 Heatmap Lỗi Đang Bị Treo Theo Agent")
                    st.plotly_chart(fig_heatmap, use_container_width=True)
                else: st.info("Không có dữ liệu ticket bị treo để phân tích.")

            with tab_su_co:
                st.markdown("### 🚨 Radar Bắt Mạch Sự Cố Diện Rộng (Outage Detector)")
                text_corpus = " ".join(df_filtered['Note'].fillna("").astype(str).str.lower().tolist())
                keywords = {
                    "T-Mobile / Internet": text_corpus.count("t-mobile") + text_corpus.count("tmobile") + text_corpus.count("mất mạng"),
                    "Decline / Gate (Cổng thanh toán)": text_corpus.count("decline") + text_corpus.count("host error"),
                    "PAX / Terminal": text_corpus.count("pax") + text_corpus.count("terminal"),
                    "Eero / Router": text_corpus.count("eero")
                }
                df_keywords = pd.DataFrame(list(keywords.items()), columns=['Từ khóa Cảnh Báo', 'Tần Suất Xuất Hiện']).sort_values(by='Tần Suất Xuất Hiện', ascending=False)
                highest_freq = df_keywords.iloc[0]['Tần Suất Xuất Hiện']
                if highest_freq > 10: st.error(f"🚨 **BÁO ĐỘNG ĐỎ:** Từ khóa **{df_keywords.iloc[0]['Từ khóa Cảnh Báo']}** xuất hiện bất thường ({highest_freq} lần). Check hãng gấp!")
                elif highest_freq > 5: st.warning(f"⚠️ **LƯU Ý:** Tần suất từ khóa **{df_keywords.iloc[0]['Từ khóa Cảnh Báo']}** đang tăng cao ({highest_freq} lần).")
                else: st.success("🟢 Hệ thống ổn định.")
                st.plotly_chart(px.bar(df_keywords, x='Tần Suất Xuất Hiện', y='Từ khóa Cảnh Báo', orientation='h', color='Tần Suất Xuất Hiện', color_continuous_scale='OrRd'), use_container_width=True)

            with tab_bao_cao:
                st.markdown("### 📈 Xuất Báo Cáo Giao Ban")
                total = len(df_filtered)
                done = len(df_filtered[df_filtered['Status_Norm'].str.contains('done')])
                pending = len(df_filtered[df_filtered['Status_Norm'].str.contains('pending')|df_filtered['Status_Norm'].str.contains('support')])
                report_str = f"📋 BÁO CÁO VẬN HÀNH LLDTEK - {d_start.strftime('%d/%m/%Y')}\n--------------------------------------------------\n**1. TỔNG QUAN TICKET:**\n- Tổng: {total} | Done: {done} | Support: {pending}\n\n**2. TOP NHÂN SỰ XUẤT SẮC:**\n"
                for i, (name, count) in enumerate(df_filtered[df_filtered['Status_Norm'].str.contains('done')]['Agent_Name'].value_counts().head(3).items()):
                    report_str += f"- Top {i+1}: {name} ({count} tickets done)\n"
                st.text_area("Copy gửi Group Zalo/Viber:", value=report_str, height=250)

            with tab_co_ban:
                # [THÊM LẠI THEO YÊU CẦU] BẢNG THỐNG KÊ NĂNG SUẤT TỪNG NHÂN SỰ
                st.markdown("### 🏆 Bảng Tổng Kết Năng Suất & Tồn Đọng Theo Agent")
                if 'Agent_Name' in df_filtered.columns:
                    agent_stats = df_filtered['Agent_Name'].value_counts().reset_index()
                    agent_stats.columns = ['Nhân viên', 'Tổng Ticket']
                    pending_stats = df_filtered[df_filtered['Status_Norm'].str.contains('pending') | df_filtered['Status_Norm'].str.contains('support')]['Agent_Name'].value_counts().reset_index()
                    pending_stats.columns = ['Nhân viên', 'Đang nợ (Support)']
                    done_stats = df_filtered[df_filtered['Status_Norm'].str.contains('done')]['Agent_Name'].value_counts().reset_index()
                    done_stats.columns = ['Nhân viên', 'Đã chốt (Done)']
                    final_stats = pd.merge(agent_stats, done_stats, on='Nhân viên', how='left').fillna(0)
                    final_stats = pd.merge(final_stats, pending_stats, on='Nhân viên', how='left').fillna(0)
                    for col in ['Tổng Ticket', 'Đã chốt (Done)', 'Đang nợ (Support)']: final_stats[col] = final_stats[col].astype(int)
                    st.dataframe(final_stats, hide_index=True, use_container_width=True, column_config={
                        "Tổng Ticket": st.column_config.ProgressColumn("Khối lượng công việc", format="%d", min_value=0, max_value=int(final_stats['Tổng Ticket'].max())),
                        "Đã chốt (Done)": st.column_config.NumberColumn("Đã chốt 🟢"),
                        "Đang nợ (Support)": st.column_config.NumberColumn("Đang nợ 🔴")
                    })
                st.markdown("---")
                daily_counts = df_filtered.groupby(df_filtered['Date_Obj'].dt.date).size().reset_index(name='Tickets')
                st.plotly_chart(px.line(daily_counts, x='Date_Obj', y='Tickets', markers=True, title="📉 Xu hướng Ticket", template="plotly_dark"), use_container_width=True)

# =========================================================
# MODULE 5: QUẢN LÝ NHÂN SỰ & CẤU HÌNH ADMIN (SOP)
# =========================================================
elif menu == "👥 Quản lý Nhân sự / SOP":
    st.title("👥 Quản lý Nhân sự & Cấu hình SOP")
    st.info("Khu vực này chỉ dành riêng cho Admin (SUP).")
    
    tab_users, tab_sops = st.tabs(["👤 Quản lý Tài khoản", "🛠️ Quản lý SOPs (Smart Toolkit)"])
    
    with tab_users:
        st.markdown("### 🛠️ Thêm / Cập nhật Tài khoản")
        conn = sqlite3.connect('crm_data.db')
        col_u1, col_u2, col_u3, col_u4 = st.columns(4)
        with st.form("user_management"):
            u_name = col_u1.text_input("Tên Nhân viên (Username)")
            u_pass = col_u2.text_input("Mật khẩu mới (Bỏ trống nếu không đổi)")
            u_role = col_u3.selectbox("Phân quyền", ["Agent", "Admin"])
            u_status = col_u4.selectbox("Trạng thái", ["Hoạt động", "Khóa"])
            
            if st.form_submit_button("Lưu thay đổi nhân sự", type="primary"):
                if u_name:
                    c = conn.cursor()
                    c.execute("SELECT * FROM users WHERE username=?", (u_name,))
                    exists = c.fetchone()
                    active_val = 1 if u_status == "Hoạt động" else 0
                    if exists:
                        if u_pass: c.execute("UPDATE users SET password=?, role=?, is_active=? WHERE username=?", (u_pass, u_role, active_val, u_name))
                        else: c.execute("UPDATE users SET role=?, is_active=? WHERE username=?", (u_role, active_val, u_name))
                        st.success(f"Đã cập nhật tài khoản: {u_name}")
                    else:
                        if not u_pass: u_pass = '123456' 
                        c.execute("INSERT INTO users (username, password, role, is_active, last_seen, vici_id) VALUES (?, ?, ?, ?, '', '')", (u_name, u_pass, u_role, active_val))
                        st.success(f"Đã tạo mới tài khoản: {u_name}")
                    conn.commit()
                    st.rerun()
                else: st.warning("Vui lòng nhập tên nhân viên!")
                    
        st.markdown("### 📋 Danh sách Tài khoản")
        df_users = pd.read_sql_query("SELECT username as 'Tên NV', password as 'Mật khẩu', role as 'Quyền', is_active as 'Trạng thái', last_seen as 'Hoạt động cuối' FROM users", conn)
        df_users['Trạng thái'] = df_users['Trạng thái'].apply(lambda x: "🟢 Hoạt động" if x==1 else "🔴 Khóa")
        st.dataframe(df_users, hide_index=True, use_container_width=True)
        conn.close()

    # --- [V151 TÍNH NĂNG MỚI] GIAO DIỆN QUẢN TRỊ SOP ---
    with tab_sops:
        st.markdown("### 📝 Bảng Cấu Hình Kịch Bản Xử Lý Lỗi (Smart Toolkit)")
        st.caption("Các kịch bản này sẽ hiển thị trực tiếp ở mục 'Tạo Ticket Mới' để nhân viên chọn và tạo Note tự động.")
        
        conn = sqlite3.connect('crm_data.db')
        df_sops = pd.read_sql_query("SELECT id, category as 'Phân Loại', device_name as 'Tên Thiết Bị / Tác Vụ', steps as 'Các Bước Kiểm Tra (Cách nhau bởi dấu |)' FROM sops", conn)
        st.dataframe(df_sops, hide_index=True, use_container_width=True)
        
        st.markdown("**✨ Thêm Mới / Sửa SOP**")
        with st.form("sop_form"):
            s_id = st.number_input("Nhập ID (Bỏ số 0 và nhập ID nếu muốn SỬA, giữ 0 nếu muốn THÊM MỚI)", value=0, step=1)
            s_cat = st.selectbox("Phân loại:", ["Phần cứng", "Phần mềm", "Khác"])
            s_dev = st.text_input("Tên Thiết bị / Tác vụ (Ví dụ: Máy in nhiệt, Đổi IP)")
            s_steps = st.text_area("Quy trình / Các bước (Bắt buộc dùng ký tự gạch đứng | để ngăn cách các bước)", placeholder="Bước 1 | Bước 2 | Bước 3")
            
            if st.form_submit_button("💾 Lưu Kịch Bản", type="primary"):
                if s_dev and s_steps:
                    c = conn.cursor()
                    if s_id == 0:
                        c.execute("INSERT INTO sops (category, device_name, steps) VALUES (?, ?, ?)", (s_cat, s_dev, s_steps))
                        st.success(f"Đã thêm kịch bản cho: {s_dev}")
                    else:
                        c.execute("UPDATE sops SET category=?, device_name=?, steps=? WHERE id=?", (s_cat, s_dev, s_steps, s_id))
                        st.success(f"Đã cập nhật kịch bản ID {s_id}")
                    conn.commit()
                    st.rerun()
                else: st.warning("Vui lòng điền đủ Tên Thiết bị và Quy trình!")
                
        st.markdown("**🗑️ Xóa SOP**")
        with st.form("del_sop_form"):
            del_id = st.number_input("Nhập ID cần xóa", value=0, step=1)
            if st.form_submit_button("Xóa Kịch Bản", type="primary"):
                 c = conn.cursor()
                 c.execute("DELETE FROM sops WHERE id=?", (del_id,))
                 conn.commit()
                 st.success("Đã xóa kịch bản thành công!")
                 st.rerun()
        conn.close()