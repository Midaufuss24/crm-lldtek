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
from PIL import Image, ImageDraw
import streamlit.components.v1 as components

# ==========================================
# 1. CẤU HÌNH & LOGO & ONBOARDING
# ==========================================
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

# --- UI CSS ---
st.markdown("""
<style>
    .stApp { font-family: 'Segoe UI', sans-serif; }
    .stTextArea textarea, .stTextInput input { font-family: 'Consolas', monospace; font-weight: 500; border-radius: 5px; }
    div[data-testid="stTextInput"] input[aria-label="⚡ Tra cứu CID nhanh:"] { border: 2px solid #ff4b4b; background-color: #fff0f0; color: black; font-weight: bold; }
    footer {visibility: hidden;}
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
</style>
""", unsafe_allow_html=True)

# --- KEEP-ALIVE CHỐNG TIMEOUT ---
components.html(
    """<script>setInterval(function() {window.parent.postMessage('lldtek_keep_alive_ping', '*');}, 60000);</script>""",
    height=0, width=0
)

# --- DATABASE SETUP (V154.6: BỔ SUNG CỘT GHI NHỚ VICI_ID) ---
def init_db():
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, Date TEXT, Salon_Name TEXT, Phone TEXT, Issue_Category TEXT, Note TEXT, Status TEXT, Created_At TEXT, CID TEXT, Contact TEXT, Card_16_Digits TEXT, Training_Note TEXT, Demo_Note TEXT, Agent_Name TEXT, Support_Time TEXT, Caller_Info TEXT, ISO_System TEXT, Ticket_Type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS cid_cache (cid TEXT PRIMARY KEY, salon_name TEXT)''')
    
    # BẢNG USERS VÀ TẠO DATA MẶC ĐỊNH
    c.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, is_active INTEGER, last_seen TEXT)''')
    
    # Ép thêm cột vici_id vào DB cũ nếu chưa có để phục vụ Ghi nhớ đăng nhập
    try:
        c.execute("ALTER TABLE users ADD COLUMN vici_id TEXT")
    except:
        pass

    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        agents_list = ["Phương Loan", "Hương Giang", "Phương Anh", "Tuấn Võ", "Thùy Dung", "Phương Hồ", "Chiến Phạm", "Anh Đạt", "Tiến Dương", "Schang Sanh", "Tuyết Anh", "Liên Chi", "Anh Thư"]
        for a in agents_list:
            r = 'Admin' if a in ["Phương Loan", "Thùy Dung"] else 'Agent'
            c.execute("INSERT INTO users VALUES (?, '123456', ?, 1, '', '')", (a, r))
        c.execute("INSERT OR IGNORE INTO users VALUES ('admin', 'admin123', 'Admin', 1, '', '')")
    
    conn.commit()
    conn.close()
init_db()

# ==========================================
# HỆ THỐNG ĐĂNG NHẬP & XÁC THỰC (V154.6 - ULTIMATE SERVER-SIDE REMEMBER ME)
# ==========================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.user_role = ""

qp = st.query_params
vici_user_param = qp.get("user", "")
js_auto_user = qp.get("auto_login_js", "")

# --- A. XỬ LÝ ĐĂNG XUẤT (NẾU CÓ YÊU CẦU TỪ NÚT ĐĂNG XUẤT) ---
if st.session_state.get("clear_storage", False):
    # Xóa trí nhớ ID VICI trong DB
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute("UPDATE users SET vici_id='' WHERE username=?", (st.session_state.current_user,))
    conn.commit()
    conn.close()

    # Xóa JS Local Storage fallback
    clear_js = """
    <script>
        try { window.parent.localStorage.removeItem('crm_auto_user'); } catch(e) {}
        try { window.localStorage.removeItem('crm_auto_user'); } catch(e) {}
        let url = new URL(window.location.href);
        url.searchParams.delete('auto_login_js');
        window.history.replaceState({}, document.title, url.toString());
    </script>
    """
    components.html(clear_js, height=0, width=0)
    
    st.session_state.clear_storage = False
    st.session_state.logged_in = False
    st.session_state.current_user = ""
    st.session_state.user_role = ""
    st.rerun()

# --- B. KIỂM TRA ĐĂNG NHẬP TỰ ĐỘNG ---
if not st.session_state.logged_in:
    
    # 1. SERVER-SIDE MAPPING (Ưu tiên số 1: Tự động vô thẳng cực mượt khi bấm CRM trên VICI)
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

    # 2. LOCAL STORAGE FALLBACK (Dành cho việc tắt app mở lại từ Link lưu Bookmark)
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
            if "auto_login_js" in st.query_params:
                del st.query_params["auto_login_js"] 
            st.rerun()

# --- C. HIỂN THỊ FORM ĐĂNG NHẬP (NẾU CHƯA THỂ AUTO-LOGIN) ---
if not st.session_state.logged_in:
    # Script mồi quét Local Storage ngầm
    check_js = """
    <script>
        try {
            let saved_user = window.parent.localStorage.getItem('crm_auto_user') || window.localStorage.getItem('crm_auto_user');
            if (saved_user) {
                let url = new URL(window.location.href);
                if (!url.searchParams.has('auto_login_js') && !url.searchParams.has('user')) {
                    url.searchParams.set('auto_login_js', saved_user);
                    window.location.replace(url.toString());
                }
            }
        } catch(e) {}
    </script>
    """
    components.html(check_js, height=0, width=0)

    st.markdown("<br><h1 style='text-align: center; color: #4CAF50;'>🔐 HỆ THỐNG LLDTEK CRM</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Vui lòng đăng nhập để bắt đầu phiên làm việc</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        with st.form("login_form"):
            user_input = st.text_input("👤 Tên nhân viên (Username)")
            pass_input = st.text_input("🔑 Mật khẩu", type="password")
            
            # CHECKBOX GHI NHỚ QUAN TRỌNG
            remember_me = st.checkbox("💾 Ghi nhớ đăng nhập (Sẽ tự động vào app cho các phiên sau)", value=True)
            
            if st.form_submit_button("Đăng Nhập", use_container_width=True):
                conn = sqlite3.connect('crm_data.db')
                c = conn.cursor()
                c.execute("SELECT role, is_active FROM users WHERE username=? AND password=?", (user_input, pass_input))
                res = c.fetchone()
                if res:
                    if res[1] == 1:
                        # NẾU TÍCH GHI NHỚ: Bắt đầu ghim ID VICI vào tài khoản này
                        if remember_me:
                            if vici_user_param:
                                c.execute("UPDATE users SET vici_id=? WHERE username=?", (vici_user_param, user_input))
                            st.session_state.trigger_js_remember = user_input # Dành cho lưu local storage
                        
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
    st.stop() # Chặn không cho render app bên dưới khi chưa vào được

# --- D. NẠP THẺ NHỚ LOCAL STORAGE NGAY SAU KHI ĐĂNG NHẬP ---
if 'trigger_js_remember' in st.session_state:
    js_save = f"""
    <script>
        try {{ window.parent.localStorage.setItem('crm_auto_user', '{st.session_state.trigger_js_remember}'); }} catch(e) {{}}
        try {{ window.localStorage.setItem('crm_auto_user', '{st.session_state.trigger_js_remember}'); }} catch(e) {{}}
    </script>
    """
    components.html(js_save, height=0, width=0)
    del st.session_state['trigger_js_remember']

# CẬP NHẬT TRẠNG THÁI ONLINE (LAST SEEN)
conn = sqlite3.connect('crm_data.db')
c = conn.cursor()
c.execute("UPDATE users SET last_seen=? WHERE username=?", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), st.session_state.current_user))
conn.commit()
conn.close()


# --- CÁC HÀM CACHE & CẢNH BÁO TRÙNG LẶP ---
def get_cached_salon(cid):
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute("SELECT salon_name FROM cid_cache WHERE cid=?", (cid,))
    res = c.fetchone()
    conn.close()
    return res[0] if res else None

def save_cached_salon(cid, name):
    if not cid or not name: return
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO cid_cache (cid, salon_name) VALUES (?, ?)", (cid, name))
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
# 2. AUTO-DETECT SHEETS (NGUYÊN BẢN)
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

# ==========================================
# 3. HELPER FUNCTIONS
# ==========================================
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

# ==========================================
# 4. BOT SEARCH ENGINE
# ==========================================
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

# ==========================================
# 5. GOOGLE SHEET & FORMATTING
# ==========================================
def save_to_master_db_gsheet(df):
    status_box = st.status("🛠️ Đang thực hiện lưu Database...", expanded=True)
    try:
        if df.empty:
            status_box.update(label="❌ Dữ liệu Rỗng!", state="error")
            return False, "Không có dữ liệu để lưu."

        status_box.write("1. Kết nối Google Drive...")
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials)
        
        try: 
            sh = gc.open(MASTER_DB_FILE)
        except: 
            return False, f"Không tìm thấy file '{MASTER_DB_FILE}'."

        try: 
            ws = sh.worksheet("CID")
        except: 
            ws = sh.add_worksheet(title="CID", rows=1000, cols=10)

        status_box.write("2. Đang map đúng cột dữ liệu...")
        count = 0
        for index, row in df.iterrows():
            try: 
                name_val = row['Name'] 
            except: 
                name_val = row.iloc[1] if len(row) > 1 else ""
            try: 
                cid_val = row['CID'] 
            except: 
                cid_val = row.iloc[2] if len(row) > 2 else ""
            try: 
                agent_val = row['Agent'] 
            except: 
                agent_val = row.iloc[4] if len(row) > 4 else "" 
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
        ws.format(f"I{row_idx}", fmt_left_clip)               
        ws.format(f"J{row_idx}", fmt_left_wrap)               
        ws.format(f"K{row_idx}", fmt_center_clip)             
    except Exception as e:
        pass

def save_to_google_sheet(ticket_data):
    try:
        sh, target_ws, sheet_name = get_target_worksheet(ticket_data['Date_Obj'])
        if not target_ws: 
            return False, sheet_name
        
        all_values = target_ws.get_values("A7:B1000") 
        
        start_row = 7
        target_row_idx = -1
        last_stt_val = 0 
        
        for i, row in enumerate(all_values):
            real_row_idx = start_row + i
            val_stt = str(row[0]).strip() if len(row) > 0 else ""
            val_name = str(row[1]).strip() if len(row) > 1 else ""
            
            if val_name:
                if val_stt.isdigit():
                    last_stt_val = int(val_stt)
                continue 
            
            if not val_name:
                target_row_idx = real_row_idx
                if not val_stt:
                    new_stt = last_stt_val + 1
                    target_ws.update_cell(target_row_idx, 1, new_stt) 
                break
        
        if target_row_idx == -1: 
            return False, "⚠️ Sheet quá đầy (Hơn 1000 dòng). Vui lòng dọn dẹp."

        full_note = ticket_data['Note']
        if ticket_data['Ticket_Type'] == "Training": 
            full_note = ticket_data['Training_Note'] + " | " + full_note
        if ticket_data['Ticket_Type'] == "Request (16 Digits)": 
            full_note = ticket_data['Card_16_Digits'] + " | " + full_note
        
        row_data = [
            ticket_data['Agent_Name'], 
            ticket_data['Support_Time'], 
            ticket_data['End_Time'], 
            ticket_data['Duration'], 
            ticket_data['Salon_Name'], 
            ticket_data['CID'], 
            ticket_data['Phone'], 
            ticket_data['Caller_Info'], 
            full_note, 
            ticket_data['Status']
        ]
        
        target_ws.update(f"B{target_row_idx}:K{target_row_idx}", [row_data])
        
        status_val = ticket_data['Status']
        color = 'red' if "Support" in status_val else 'black'
        apply_full_format(target_ws, target_row_idx, color)
        
        return True, f"✅ Đã lưu vào dòng **{target_row_idx}**"
        
    except Exception as e: 
        return False, f"❌ Lỗi: {str(e)}"

def update_google_sheet_row(date_str, phone, salon_name, new_status, new_note):
    try:
        try: 
            date_obj = pd.to_datetime(date_str, format='%m/%d/%Y')
        except: 
            date_obj = pd.to_datetime(date_str)
            
        sh, target_ws, sheet_name = get_target_worksheet(date_obj)
        if not target_ws: 
            return False, sheet_name
            
        all_values = target_ws.get_all_values()
        target_row_idx = -1
        
        for idx, row in enumerate(all_values):
            if idx < 6: 
                continue
            if len(row) > 7:
                row_phone = str(row[7]).strip()
                row_salon = str(row[5]).strip()
                if phone in row_phone and salon_name in row_salon: 
                    target_row_idx = idx + 1
                    break
                    
        if target_row_idx != -1:
            target_ws.update_cell(target_row_idx, 10, new_note)
            target_ws.update_cell(target_row_idx, 11, new_status)
            color = 'blue' if "Done" in new_status else ('red' if "Support" in new_status else 'black')
            apply_full_format(target_ws, target_row_idx, color)
            return True, f"✅ Đã cập nhật (Dòng {target_row_idx})"
        else: 
            return False, f"⚠️ Không tìm thấy dòng khớp"
    except Exception as e: 
        return False, f"❌ Lỗi Update: {str(e)}"

# ==========================================
# 6. LOAD DATA & GLOBAL
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def load_gsheet_data(selected_sheets):
    if not selected_sheets: 
        return pd.DataFrame()
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
                        if len(raw) < 2: 
                            continue
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
                                if "Note" in df_d.columns: 
                                    df_d["Issue_Category"] = df_d["Note"]
                                df_d["Date"] = construct_date_from_context(None, s_name, ws.title)
                                df_d["Ticket_Type"] = "Support"
                                df_d["Status"] = df_d["Status"].replace({"Pending": "Support", "pending": "Support"})
                                all_data.append(df_d)
                    except: 
                        continue
            except: 
                pass
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
            else: 
                master_data['CID'] = pd.DataFrame()
        except: 
            master_data['CID'] = pd.DataFrame()
            
        try: 
            ws_note = sh.worksheet("NOTE")
            master_data['NOTE'] = pd.DataFrame(ws_note.get_all_values())
        except: 
            master_data['NOTE'] = pd.DataFrame()
            
        try: 
            ws_conf = sh.worksheet("CONFIRMATION")
            raw_conf = ws_conf.get_all_values()
            if len(raw_conf) > 1:
                headers = clean_headers(raw_conf[1])
                master_data['CONFIRMATION'] = pd.DataFrame(raw_conf[2:], columns=headers) 
            else: 
                master_data['CONFIRMATION'] = pd.DataFrame()
        except: 
            master_data['CONFIRMATION'] = pd.DataFrame()
            
        try: 
            ws_term = None
            for w in sh.worksheets(): 
                if "terminal" in w.title.lower(): 
                    ws_term = w
                    break
            if ws_term: 
                master_data['TERMINAL'] = pd.DataFrame(ws_term.get_all_values())
        except: 
            master_data['TERMINAL'] = pd.DataFrame()
            
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
        else: 
            return False, "⚠️ Không tìm thấy CID này."
    except Exception as e: 
        return False, f"❌ Lỗi: {str(e)}"

# ==========================================
# 7. GIAO DIỆN CHÍNH & PHÂN QUYỀN
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

# PHÂN QUYỀN GIAO DIỆN CHỌN NHÂN VIÊN
if st.session_state.user_role == 'Admin':
    default_idx = active_users.index(st.session_state.current_user) if st.session_state.current_user in active_users else 0
    sel_agent = st.sidebar.selectbox("Nhân viên:", active_users, index=default_idx, key="agent_selectbox")
else:
    sel_agent = st.session_state.current_user
    st.sidebar.markdown(f"👤 **Xin chào, {sel_agent}**")
    st.sidebar.caption("Chức vụ: Nhân viên")

# XÓA TRÍ NHỚ ĐĂNG NHẬP KHI BẤM NÚT ĐĂNG XUẤT (V154.6)
if st.sidebar.button("🚪 Đăng xuất", type="secondary"):
    st.session_state.clear_storage = True
    st.rerun()

# =========================================================
# MODULE 1: MINI-DASHBOARD CHO CÁ NHÂN
# =========================================================
if sel_agent:
    df_sidebar = load_gsheet_data(sheets)
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

# CẬP NHẬT MENU THEO QUYỀN
menu_options = ["🆕 New Ticket", "📌 Cần Follow-up", "🗂️ Tra cứu Master Data", "🔍 Search & History"]
if st.session_state.user_role == 'Admin':
    menu_options.append("📊 Dashboard (SUP Only)")
    menu_options.append("👥 Quản lý Nhân sự")
menu = st.sidebar.selectbox("Menu", menu_options)

# KHỞI TẠO BIẾN FORM_KEY ĐỂ TÁI SINH FORM MỚI HOÀN TOÀN KHI LƯU
if 'form_key' not in st.session_state:
    st.session_state.form_key = 0

if 'ticket_start_time' not in st.session_state:
    st.session_state.ticket_start_time = None

# HÀM XÓA FORM AN TOÀN TUYỆT ĐỐI
def clear_form():
    st.session_state.form_key += 1
    fk = st.session_state.form_key
    st.session_state[f"ticket_phone_{fk}"] = ""
    st.session_state[f"ticket_salon_{fk}"] = ""
    st.session_state[f"ticket_cid_{fk}"] = ""
    st.session_state[f"ticket_owner_{fk}"] = ""
    st.session_state[f"ticket_note_{fk}"] = ""
    st.session_state.ticket_start_time = None
    if 'vici_cache' in st.session_state:
        del st.session_state['vici_cache']

@st.dialog("⚠️ XÁC NHẬN LƯU TICKET")
def confirm_save_dialog(data_pack, is_duplicate=False):
    if is_duplicate:
        st.error("🚨 CẢNH BÁO TRÙNG LẶP: Bạn vừa lưu 1 ticket cho SĐT này cách đây ít phút! Hãy chắc chắn bạn không lưu nhầm.")
        
    st.markdown(f"""<div style="text-align: center;"><h3 style="color: #4CAF50;">{data_pack['Salon_Name']}</h3><p><b>SĐT:</b> {data_pack['Phone']} | <b>Trạng thái:</b> {data_pack['Status']}</p>
    <p><b>⏱️ Thời gian:</b> {data_pack['Duration']} phút ({data_pack['Support_Time']} - {data_pack['End_Time']})</p>
    <hr><p style="text-align: left;"><b>Nội dung:</b><br>{data_pack['Note']}</p></div>""", unsafe_allow_html=True)
    
    if st.button("✅ ĐỒNG Ý LƯU & CLEAR FORM", type="primary", use_container_width=True):
        insert_ticket(data_pack['Date_Str'], data_pack['Salon_Name'], data_pack['Phone'], data_pack['Note'], data_pack['Note'], data_pack['Status'], data_pack['CID'], data_pack['Agent_Name'], data_pack['Support_Time'], data_pack['Caller_Info'], data_pack['Ticket_Type'], "", data_pack['Training_Note'], "", data_pack['Card_16_Digits'])
        with st.spinner("⏳ Đang đồng bộ Google Sheet..."):
            success, msg = save_to_google_sheet(data_pack)
        if success: 
            st.toast("✅ Lưu thành công! Khởi tạo form mới...", icon="✨")
            clear_form() # Tăng Key lên 1 để đập bỏ form cũ
            time.sleep(0.5)
            st.rerun() 
        else: 
            st.error(f"Lỗi GSheet: {msg}")

# ==========================================
# 8. MAIN LOGIC (VỚI LAYOUT 2 CỘT TỐI ƯU UX)
# ==========================================

if menu == "🆕 New Ticket":
    st.title("🆕 Tạo Ticket Mới")
    houston_now = get_company_time()
    fk = st.session_state.form_key # Lấy Key hiện tại của Form
    
    # BẮT LINK VICI VÀ LÀM SẠCH URL CHỐNG KẸT APP
    qp = st.query_params
    if any(k in qp for k in ["phone", "address", "comments", "first"]):
        st.session_state.vici_cache = {
            "title": qp.get("title", ""), "first": qp.get("first", ""), "last": qp.get("last", ""), "address": qp.get("address", ""),
            "city": qp.get("city", ""), "state": qp.get("state", ""), "zip": qp.get("zip", ""), "vendor_id": qp.get("vendor_id", ""),
            "phone": qp.get("phone", ""), "alt_phone": qp.get("alt_phone", ""), "email": qp.get("email", ""), "comments": qp.get("comments", ""), "user": qp.get("user", "")
        }
        
        if st.session_state.vici_cache['phone']: 
            st.session_state[f"ticket_phone_{fk}"] = st.session_state.vici_cache['phone']
        if st.session_state.vici_cache['user']: 
            st.session_state[f"ticket_owner_{fk}"] = st.session_state.vici_cache['user']
        
        def smart_parse(text):
            if not text: return None, None
            match = re.search(r'\b(\d{4,6})\b', text) 
            if match: 
                return match.group(1), text[:match.start()].strip(' -:,|#').strip()
            return None, text 

        f_cid, f_name = smart_parse(st.session_state.vici_cache['address'])
        if not f_cid: 
            f_cid, f_name = smart_parse(st.session_state.vici_cache['comments'])
        
        if f_cid: 
            st.session_state[f"ticket_cid_{fk}"] = f_cid
            if f_name: 
                st.session_state[f"ticket_salon_{fk}"] = f_name
            st.toast(f"🤖 Auto-Detected VICI: {f_name} (CID: {f_cid})")
        
        # Xóa các thông tin VICI trên URL để đảm bảo Form không bị kẹt khi Lưu
        st.query_params.clear()

    if st.session_state.ticket_start_time is None: 
        st.session_state.ticket_start_time = houston_now
        
    start_time_display = format_excel_time(st.session_state.ticket_start_time)
    
    st.markdown(f"""<div style="padding: 10px; background-color: #262730; border-radius: 5px; border: 1px solid #4e4f57; text-align: center; margin-bottom: 20px;"><span style="font-size: 1.2em;">⏱️</span> <span style="font-weight: bold; color: #ff4b4b;">TICKET STARTED:</span> <span style="font-family: monospace; font-size: 1.2em;">{start_time_display} (Houston)</span></div>""", unsafe_allow_html=True)

    if not sel_agent: 
        st.warning("⚠️ Vui lòng chọn Tên Nhân Viên trước!")
        st.stop()

    # ================= LAYOUT 2 CỘT =================
    col_left, col_right = st.columns([1.1, 1], gap="large")

    with col_left:
        st.markdown("### 🏢 THÔNG TIN KHÁCH HÀNG")
        
        # Hiển thị thông tin VICI nếu có
        if 'vici_cache' in st.session_state and st.session_state.vici_cache:
            v = st.session_state.vici_cache
            with st.expander(f"📡 DỮ LIỆU TỪ VICI: {v['first']} {v['last']} (Click mở)", expanded=False):
                c1, c2, c3, c4 = st.columns(4)
                if c1.button("🏢 Lấy Address", use_container_width=True): 
                    st.session_state[f"ticket_salon_{fk}"] = v['address']
                    st.rerun()
                if c2.button("📝 Chép Note", use_container_width=True): 
                    cur_note = st.session_state.get(f"ticket_note_{fk}", "")
                    st.session_state[f"ticket_note_{fk}"] = (cur_note + "\n" + v['comments']).strip()
                    st.rerun()
                if c3.button("🆔 Lấy Vendor", use_container_width=True): 
                    st.session_state[f"ticket_cid_{fk}"] = v['vendor_id']
                    st.rerun()
                if c4.button("🗑️ Xóa VICI", use_container_width=True): 
                    del st.session_state.vici_cache
                    st.rerun()
                st.caption(f"**Name:** {v['title']} {v['first']} {v['last']} | **Phone:** {v['phone']}")
                st.caption(f"**Address:** {v['address']}, {v['city']}, {v['state']} {v['zip']}")
                if v['comments']: 
                    st.code(v['comments'], language="text")

        # Ô kiểm tra CID & Chức năng Cache
        c_cid, c_btn = st.columns([3, 1])
        auto_cid = c_cid.text_input("⚡ Tra cứu CID nhanh:", key=f"input_cid_trigger_{fk}", placeholder="Nhập CID...")
        
        if c_btn.button("🔍 Check", use_container_width=True) or auto_cid:
             clean_input = auto_cid.strip()
             if clean_input:
                 with st.spinner("Đang tìm kiếm..."):
                    found_name = get_cached_salon(clean_input)
                    if found_name: 
                        st.success(f"⚡ Cache: {found_name}")
                    else:
                        master_data = load_master_db()
                        df_cid = master_data.get('CID', pd.DataFrame())
                        if not df_cid.empty:
                            try:
                                name_col = df_cid.columns[0]
                                cid_col = df_cid.columns[1] if len(df_cid.columns) > 1 else df_cid.columns[0]
                                mask = df_cid[cid_col].apply(lambda x: clean_input == str(x).strip() or clean_input in str(x).strip())
                                res = df_cid[mask]
                                if not res.empty: 
                                    found_name = str(res.iloc[0][name_col])
                                    st.success(f"✅ Excel: {found_name}")
                            except: pass
                        
                        if not found_name and not is_cloud_mode:
                            bot_res = run_search_engine(clean_input)
                            if bot_res is not None and not bot_res.empty:
                                try: 
                                    found_name = bot_res.iloc[0, 1] if bot_res.shape[1] > 1 else str(bot_res.iloc[0, 0])
                                    st.success(f"🤖 Bot: {found_name}")
                                except: pass
                    
                    if found_name:
                        st.session_state[f"ticket_salon_{fk}"] = found_name
                        st.session_state[f"ticket_cid_{fk}"] = clean_input
                        save_cached_salon(clean_input, found_name)

        # CÁC Ô NHẬP LIỆU GẮN FORM KEY
        new_phone = st.text_input("📞 Số Điện Thoại *", key=f"ticket_phone_{fk}")
        new_salon = st.text_input("🏠 Tên Tiệm", key=f"ticket_salon_{fk}")
        
        c_i1, c_i2 = st.columns(2)
        new_cid = c_i1.text_input("🆔 CID", key=f"ticket_cid_{fk}")
        new_caller = c_i2.text_input("👤 Người Gọi", key=f"ticket_owner_{fk}")

        # =================================================================
        # BẢN CẢI TIẾN: SMART HISTORY + DIALOG XEM CHI TIẾT
        # =================================================================
        @st.dialog("📄 CHI TIẾT TICKET")
        def view_past_ticket(r):
            st.info(f"**Nhân viên xử lý:** {r.get('Agent_Name', 'N/A')} | **Thời gian:** {r.get('Date', '')} {r.get('Support_Time', '')}")
            st.markdown(f"**Trạng thái:** {map_status_badge(r.get('Status', ''))}")
            c_dia1, c_dia2 = st.columns(2)
            c_dia1.markdown(f"**Tên Tiệm:** {str(r.get('Salon_Name', ''))}")
            c_dia1.markdown(f"**Người Gọi:** {str(r.get('Caller_Info', ''))}")
            c_dia2.markdown(f"**Số Phone:** `{str(r.get('Phone', ''))}`")
            c_dia2.markdown(f"**CID:** `{str(r.get('CID', ''))}`")
            st.markdown("---")
            st.markdown("**Chi tiết Ghi chú:**")
            st.text_area("Note (Read-only)", value=str(r.get('Note', '')), height=180, disabled=True, label_visibility="collapsed")

        if new_phone or new_cid:
            df_hist = load_gsheet_data(sheets)
            if not df_hist.empty:
                mask = pd.Series([False] * len(df_hist))
                if new_phone:
                    mask |= df_hist['Phone'].astype(str).str.contains(str(new_phone).strip(), na=False)
                if new_cid:
                    clean_cid = str(new_cid).strip()
                    if clean_cid:
                        mask |= df_hist['CID'].astype(str).apply(lambda x: clean_cid == str(x).strip() or clean_cid in str(x).strip())
                
                match = df_hist[mask]
                
                if not match.empty:
                    today_str = houston_now.strftime('%m/%d/%Y')
                    match['Display_Date'] = match['Date'].apply(format_date_display)
                    
                    today_tickets = match[match['Display_Date'] == today_str]
                    recent = match.sort_values(by='Date', key=lambda x: pd.to_datetime(x, errors='coerce'), ascending=False).head(4)
                    
                    st.markdown("<br>", unsafe_allow_html=True) 
                    
                    if not today_tickets.empty:
                        agents_today = ", ".join(today_tickets['Agent_Name'].dropna().unique())
                        st.error(f"🚨 CHÚ Ý: Tiệm này đã gọi {len(today_tickets)} lần TRONG HÔM NAY! (Bởi: {agents_today})")
                        with st.expander(f"🔥 XEM LỊCH SỬ HÔM NAY & GẦN ĐÂY", expanded=True):
                            for idx, r in recent.iterrows():
                                is_today = "🔥 [HÔM NAY]" if r.get('Display_Date') == today_str else "🕰️"
                                col_info, col_btn = st.columns([4, 1])
                                with col_info:
                                    st.markdown(f"**{is_today} {r.get('Date')} {r.get('Support_Time', '')} | {r.get('Agent_Name')}** - {map_status_badge(r.get('Status', ''))}")
                                    st.caption(f"📝 {str(r.get('Note'))[:80]}...")
                                with col_btn:
                                    if st.button("Chi tiết", key=f"btn_today_{idx}"):
                                        view_past_ticket(r)
                                st.divider()
                    else:
                        with st.expander(f"🕰️ LỊCH SỬ GẦN ĐÂY ({len(match)} ticket)", expanded=False):
                            for idx, r in recent.iterrows():
                                col_info, col_btn = st.columns([4, 1])
                                with col_info:
                                    st.markdown(f"**🕰️ {r.get('Date')} {r.get('Support_Time', '')} | {r.get('Agent_Name')}** - {map_status_badge(r.get('Status', ''))}")
                                    st.caption(f"📝 {str(r.get('Note'))[:80]}...")
                                with col_btn:
                                    if st.button("Chi tiết", key=f"btn_old_{idx}"):
                                        view_past_ticket(r)
                                st.divider()

    with col_right:
        st.markdown("### 🛠️ NỘI DUNG XỬ LÝ")
        ticket_type = st.selectbox("Loại Ticket:", ["Report (Hỗ trợ)", "Training", "Demo", "SMS Refill", "SMS Drafting", "Request (16 Digits)"])
        
        iso_val, train_note, demo_note, card_info, note_content = "", "", "", "", ""
        status_opts = ["Support", "Done", "No Answer"]
        
        if ticket_type == "Report (Hỗ trợ)": 
            new_note = st.text_area("Chi tiết hỗ trợ *", key=f"ticket_note_{fk}", height=180)
            note_content = new_note
        elif ticket_type == "Training": 
            col_iso, col_other = st.columns([1, 1])
            iso_opt = col_iso.selectbox("ISO", ["Spoton", "1ST", "TMS", "TMDSpoton", "Khác"])
            iso_val = iso_opt if iso_opt != "Khác" else col_other.text_input("Nhập ISO khác")
            topics = st.multiselect("Topics:", ["Mainscreen", "APPT", "Guest List", "Payment", "GC", "Report", "Settings"])
            detail = st.text_area("Chi tiết Topics:")
            train_note = f"Topics: {', '.join(topics)} | Note: {detail}"
            new_note = st.text_area("Ghi chú chung *", key=f"ticket_note_{fk}", height=100)
            note_content = new_note
        elif ticket_type == "Demo": 
            demo_note = st.text_input("Mục đích")
            new_note = st.text_area("Diễn biến *", key=f"ticket_note_{fk}", height=150)
            note_content = new_note
        elif ticket_type == "SMS Refill": 
            st.info("💰 Mua gói SMS")
            pkg = st.radio("Gói:", ["$50 (2k)", "$100 (5k)", "$200 (11k)", "$300 (17.5k)"])
            c_num = st.text_input("Card Num")
            c_exp = st.text_input("EXP")
            note_content = f"REFILL SMS: {pkg}"
            card_info = f"Pkg: {pkg} | Card: {c_num} | Exp: {c_exp}"
        elif ticket_type == "SMS Drafting": 
            st.info("📝 Soạn SMS")
            process = st.text_area("Diễn biến")
            draft = st.text_area("Nội dung chốt")
            note_content = f"DIỄN BIẾN: {process}\nCHỐT: {draft}"
            status_opts = ["Support", "Done"]
        elif ticket_type == "Request (16 Digits)": 
            mid = st.text_input("MID")
            amt = st.text_input("Amount")
            note_content = f"MID: {mid} | Amt: {amt}"
            status_opts = ["Request", "Forwarded", "Support", "Done"]
        
        st.markdown("---")
        status = st.selectbox("📌 Trạng thái cuối", status_opts)
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("💾 LƯU TICKET & ĐỒNG BỘ", type="primary", use_container_width=True):
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
                    'Card_16_Digits': card_info
                }
                
                is_dup = check_recent_duplicate(new_phone, sel_agent)
                confirm_save_dialog(data_pack, is_duplicate=is_dup)
            else: 
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
                            st.success(f"✅ Đã cập nhật Database!\n{msg}")
                            st.rerun()
                        else: 
                            st.warning(f"✅ Đã cập nhật Database nhưng ❌ {msg}")
                            st.rerun()

                event_fu = st.dataframe(df_pending[final_cols_fu], hide_index=True, use_container_width=True, selection_mode="single-row", on_select="rerun", column_config={"Note": st.column_config.TextColumn("Nội dung", width="large")})
                if len(event_fu.selection.rows) > 0:
                    process_followup_ticket(df_pending.iloc[event_fu.selection.rows[0]])
            else:
                st.success("🎉 Chúc mừng! Bạn không có ticket nào đang tồn đọng cần xử lý.")
        else:
            st.info("Chưa có dữ liệu.")

# ==========================================
# CÁC TAB KHÁC (TRA CỨU, MASTER DATA, DASHBOARD)
# ==========================================
elif menu == "🗂️ Tra cứu Master Data":
    st.title("🗂️ Tra cứu Master Data (CID Salon)")
    with st.spinner("Đang tải Master Data..."): 
        master_data = load_master_db()
    if "Error" in master_data: 
        st.error(f"❌ Lỗi: {master_data['Error']}")
        st.info("💡 Check quyền Share file 'CID Salon'.")
    else:
        tab_cid, tab_conf, tab_note, tab_term = st.tabs(["🔎 Tra cứu CID/Tiệm", "🚨 Special (Confirm)", "📝 ISO & General Note", "🔧 Terminal Fix"])
        
        with tab_cid:
            st.subheader("🔎 Tìm kiếm Thông tin Tiệm")
            df_cid = master_data.get('CID', pd.DataFrame())
            col_s1, col_s2 = st.columns([3, 1])
            search_term = col_s1.text_input("Nhập CID hoặc Tên Tiệm:", placeholder="VD: 07562")
            if 'search_result_df' not in st.session_state: 
                st.session_state.search_result_df = None
            enable_bot = st.checkbox("Bot Online", value=True)
            if st.button("🚀 Tìm kiếm", type="primary"):
                if search_term:
                    if not df_cid.empty:
                        mask = df_cid.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
                        st.dataframe(df_cid[mask], use_container_width=True)
                    if enable_bot:
                        if is_cloud_mode: 
                            st.warning("⚠️ Bot chỉ chạy trên Localhost.")
                        else:
                            with st.spinner(f"🤖 Bot đang tra cứu ngầm..."): 
                                st.session_state.search_result_df = run_search_engine(search_term)
                                
            if st.session_state.search_result_df is not None and not st.session_state.search_result_df.empty:
                st.success(f"✅ Bot tìm thấy kết quả:")
                st.dataframe(st.session_state.search_result_df, use_container_width=True)
                if st.button("💾 Lưu kết quả vào Database"):
                    success, msg = save_to_master_db_gsheet(st.session_state.search_result_df)
                    if success: 
                        st.success(f"✅ {msg}")
                        st.balloons()
                        st.cache_data.clear()
                    else: 
                        st.error(f"❌ {msg}")

        with tab_conf:
             st.dataframe(master_data.get('CONFIRMATION', pd.DataFrame()), use_container_width=True)
             with st.form("upd_note"):
                 t_cid = st.text_input("CID")
                 t_note = st.text_area("Note mới") 
                 if st.form_submit_button("Lưu Note"): 
                     res, msg = update_confirmation_note(t_cid, t_note)
                     if res:
                         st.success(msg) 
                     else:
                         st.error(msg)
                         
        with tab_note:
            df_note = master_data.get('NOTE', pd.DataFrame())
            if not df_note.empty:
                cols = st.columns(2)
                for index, row in df_note.iterrows():
                    title = str(row[0]).strip() if len(row) > 0 else ""
                    content = str(row[1]).strip() if len(row) > 1 else ""
                    if title and content:
                        with cols[index % 2]: 
                            st.markdown(f"""<div style="background:#f0f2f6;padding:15px;border-radius:10px;margin-bottom:10px;"><div style="color:#004085;font-weight:bold;">{title}</div><div>{content}</div></div>""", unsafe_allow_html=True)
                            
        with tab_term:
            df_term = master_data.get('TERMINAL', pd.DataFrame())
            if not df_term.empty:
                search_term = st.text_input("🔎 Tìm kiếm lỗi Terminal:", placeholder="Nhập mã lỗi...")
                for index, row in df_term.iterrows():
                    if index == 0: 
                        continue
                    full_title = f"🔌 {str(row[0])} - {str(row[1])}"
                    if search_term and search_term.lower() not in full_title.lower(): 
                        continue
                    with st.expander(full_title): 
                        st.markdown(f"**🛠️ Integrate:**\n{str(row[2])}\n\n**📲 Update:**\n{str(row[3])}")

elif menu == "🔍 Search & History":
    st.title("🔍 Tra cứu & Lịch sử")
    with st.spinner("⏳ Đang tải dữ liệu lịch sử..."): 
        df = load_gsheet_data(sheets)

    term = st.text_input("🔎 Nhập từ khóa (Tên tiệm, SĐT, CID):")
    filter_type = st.radio("Lọc:", ["Tất cả", "Training", "Request (16 Digits)", "SMS"], horizontal=True)
    
    if term and not df.empty:
        mask = pd.Series([False]*len(df))
        cols = ['Salon_Name', 'Phone', 'CID', 'Agent_Name', 'Date']
        valid = [c for c in cols if c in df.columns] 
        for c in valid: 
            mask |= df[c].astype(str).str.lower().str.contains(term.lower(), na=False)
            
        df_search = df[mask].copy()
        
        if filter_type == 'Training': 
            df_search = df_search[df_search['Ticket_Type'] == 'Training']
        elif filter_type == 'Request (16 Digits)': 
            df_search = df_search[df_search['Ticket_Type'].str.contains('Request', na=False)]
        elif filter_type == 'SMS': 
            df_search = df_search[df_search['Ticket_Type'].str.contains('SMS', na=False)]
            
        if not df_search.empty:
            if "Date" in df_search.columns: 
                df_search['Date_Obj'] = pd.to_datetime(df_search['Date'], errors='coerce')
                df_search = df_search.sort_values('Date_Obj', ascending=False)
                
            df_search['Display_Date'] = df_search['Date'].apply(format_date_display)
            df_search['Status'] = df_search['Status'].apply(map_status_badge)
            
            cols = ['Display_Date','Agent_Name','Ticket_Type','Salon_Name','Note','Status'] 
            if filter_type == 'Request (16 Digits)': 
                cols.append('Card_16_Digits')
            final_cols = [c for c in cols if c in df_search.columns]
            
            @st.dialog("📝 CẬP NHẬT TICKET (2 CHIỀU)")
            def edit_ticket(row):
                st.info(f"🏠 {row.get('Salon_Name')} | {row.get('Ticket_Type')}")
                st.text_area("Nội dung hiện tại (Read-only):", value=str(row.get('Note')), height=100, disabled=True)
                new_card, new_exp = "", "" 
                
                if "Request" in str(row.get('Ticket_Type')): 
                    st.markdown("---")
                    st.warning("💳 **KHU VỰC SUP NHẬP THÔNG TIN THẺ**")
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
                    if success: 
                        st.success(f"✅ Đã cập nhật Database!\n{msg}")
                        st.rerun()
                    else: 
                        st.warning(f"✅ Đã cập nhật Database nhưng ❌ {msg}")
                        st.rerun()
                        
            event = st.dataframe(df_search[final_cols], hide_index=True, use_container_width=True, selection_mode="single-row", on_select="rerun", column_config={"Note": st.column_config.TextColumn("Nội dung", width="large")}) 
            if len(event.selection.rows) > 0: 
                edit_ticket(df_search.iloc[event.selection.rows[0]])
        else: 
            st.info("Không tìm thấy kết quả.")

elif menu == "📊 Dashboard (SUP Only)":
    st.title("📊 Trung Tâm Điều Hành (Deep Analytics)")
    company_now = get_company_time()
    
    with st.spinner("⏳ Đang tải dữ liệu phân tích..."): 
        df = load_gsheet_data(sheets)
        
    if not df.empty:
        df_chart = df.copy() 
        if 'Date' in df_chart.columns: 
            df_chart['Date_Obj'] = pd.to_datetime(df_chart['Date'], errors='coerce')
            df_chart = df_chart.dropna(subset=['Date_Obj'])
            
        with st.expander("📅 BỘ LỌC DỮ LIỆU", expanded=True):
            col_filter, col_range = st.columns([1, 2])
            filter_mode = col_filter.radio("Thời gian:", ["Hôm nay", "Tuần này", "Tháng này"], horizontal=True)
            today_company = company_now.date()
            if filter_mode == "Hôm nay": 
                d_start, d_end = today_company, today_company
            elif filter_mode == "Tuần này": 
                d_start, d_end = today_company - timedelta(days=today_company.weekday()), today_company
            else: 
                d_start, d_end = today_company.replace(day=1), today_company
                
            mask = (df_chart['Date_Obj'].dt.date >= d_start) & (df_chart['Date_Obj'].dt.date <= d_end)
            df_filtered = df_chart.loc[mask].copy()
            
        if df_filtered.empty: 
            st.warning(f"⚠️ Không có dữ liệu trong khoảng {d_start} đến {d_end} (Giờ Houston).")
        else:
            tab1, tab2, tab3 = st.tabs(["📈 Tổng Quan & KPI", "🚨 Phân Tích & Top Tiệm", "🏆 Hiệu Suất Team"])
            with tab1:
                total = len(df_filtered)
                df_filtered['Status_Norm'] = df_filtered['Status'].astype(str).str.lower()
                done = len(df_filtered[df_filtered['Status_Norm'].str.contains('done')])
                pending = len(df_filtered[df_filtered['Status_Norm'].str.contains('pending')|df_filtered['Status_Norm'].str.contains('support')])
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Tổng Ticket", total)
                c2.metric("Done", done, f"{(done/total*100):.1f}%" if total>0 else "0%")
                c3.metric("Support (Pending)", pending, delta_color="inverse")
                c4.metric("Request Thẻ", len(df_filtered[df_filtered['Status_Norm'].str.contains('request')]))
                
                st.markdown("---")
                daily_counts = df_filtered.groupby(df_filtered['Date_Obj'].dt.date).size().reset_index(name='Tickets')
                fig_line = px.line(daily_counts, x='Date_Obj', y='Tickets', markers=True, title="📉 Xu hướng Ticket", template="plotly_dark")
                st.plotly_chart(fig_line, use_container_width=True)
                
            with tab2:
                col_salon, col_issue = st.columns([1, 1])
                with col_salon:
                    st.markdown("### 🏪 Top 10 Tiệm Gọi Nhiều Nhất")
                    if 'Salon_Name' in df_filtered.columns:
                        top_salons = df_filtered['Salon_Name'].value_counts().nlargest(10).reset_index()
                        top_salons.columns = ['Tên Tiệm', 'Số lần gọi']
                        st.dataframe(top_salons, hide_index=True, use_container_width=True, column_config={"Số lần gọi": st.column_config.ProgressColumn("Cường độ", format="%d", min_value=0, max_value=int(top_salons['Số lần gọi'].max()))})
                with col_issue:
                    st.markdown("### 📋 Top Vấn Đề") 
                    if 'Issue_Category' in df_filtered.columns: 
                        issues = df_filtered['Issue_Category'].fillna("Khác").astype(str).str.strip()
                        top_issues = issues.value_counts().nlargest(10).reset_index()
                        top_issues.columns = ['Vấn đề', 'Số lượng']
                        fig_bar = px.bar(top_issues, x='Số lượng', y='Vấn đề', orientation='h', text='Số lượng', color='Số lượng', color_continuous_scale='Redor', template="plotly_dark")
                        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_bar, use_container_width=True)
                        
            with tab3:
                st.markdown("### 🏆 Bảng Xếp Hạng Năng Suất")
                if 'Agent_Name' in df_filtered.columns:
                    agent_stats = df_filtered['Agent_Name'].value_counts().reset_index()
                    agent_stats.columns = ['Nhân viên', 'Tổng Ticket']
                    pending_stats = df_filtered[df_filtered['Status_Norm'].str.contains('pending')|df_filtered['Status_Norm'].str.contains('support')]['Agent_Name'].value_counts().reset_index()
                    pending_stats.columns = ['Nhân viên', 'Support (Pending)']
                    final_stats = pd.merge(agent_stats, pending_stats, on='Nhân viên', how='left').fillna(0)
                    final_stats['Support (Pending)'] = final_stats['Support (Pending)'].astype(int)
                    st.dataframe(final_stats, hide_index=True, use_container_width=True, column_config={"Tổng Ticket": st.column_config.ProgressColumn("Khối lượng công việc", format="%d", min_value=0, max_value=int(final_stats['Tổng Ticket'].max())), "Support (Pending)": st.column_config.NumberColumn("Đang nợ (Support)", format="%d ⚠️")})
    else: 
        st.info("Vui lòng chọn file dữ liệu.")

# =========================================================
# MODULE 3: QUẢN LÝ NHÂN SỰ (CHỈ ADMIN MỚI THẤY TAB NÀY)
# =========================================================
elif menu == "👥 Quản lý Nhân sự":
    st.title("👥 Quản lý Nhân sự & Phân quyền")
    st.info("Chỉ Admin (SUP) mới có quyền truy cập khu vực này.")
    
    conn = sqlite3.connect('crm_data.db')
    df_users = pd.read_sql_query("SELECT username as 'Tên NV', password as 'Mật khẩu', role as 'Quyền', is_active as 'Trạng thái', last_seen as 'Hoạt động cuối' FROM users", conn)
    df_users['Trạng thái'] = df_users['Trạng thái'].apply(lambda x: "🟢 Hoạt động" if x==1 else "🔴 Khóa")
    
    st.markdown("### 📋 Danh sách Tài khoản")
    st.dataframe(df_users, hide_index=True, use_container_width=True)
    
    st.markdown("---")
    st.markdown("### 🛠️ Thêm / Cập nhật Tài khoản")
    col_u1, col_u2, col_u3, col_u4 = st.columns(4)
    with st.form("user_management"):
        u_name = col_u1.text_input("Tên Nhân viên (Username)")
        u_pass = col_u2.text_input("Mật khẩu mới (Bỏ trống nếu không đổi)")
        u_role = col_u3.selectbox("Phân quyền", ["Agent", "Admin"])
        u_status = col_u4.selectbox("Trạng thái", ["Hoạt động", "Khóa"])
        
        if st.form_submit_button("Lưu thay đổi", type="primary"):
            if u_name:
                c = conn.cursor()
                c.execute("SELECT * FROM users WHERE username=?", (u_name,))
                exists = c.fetchone()
                active_val = 1 if u_status == "Hoạt động" else 0
                if exists:
                    if u_pass:
                        c.execute("UPDATE users SET password=?, role=?, is_active=? WHERE username=?", (u_pass, u_role, active_val, u_name))
                    else:
                        c.execute("UPDATE users SET role=?, is_active=? WHERE username=?", (u_role, active_val, u_name))
                    st.success(f"Đã cập nhật tài khoản: {u_name}")
                else:
                    if not u_pass: u_pass = '123456' # Mật khẩu mặc định nếu quên nhập
                    c.execute("INSERT INTO users (username, password, role, is_active, last_seen, vici_id) VALUES (?, ?, ?, ?, '', '')", (u_name, u_pass, u_role, active_val))
                    st.success(f"Đã tạo mới tài khoản: {u_name}")
                conn.commit()
                st.rerun()
            else:
                st.warning("Vui lòng nhập tên nhân viên!")
    conn.close()