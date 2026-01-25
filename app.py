import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import gspread
from google.oauth2.service_account import Credentials
import time
import re
import pytz

# --- THƯ VIỆN CHẠY NGẦM ---
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
st.set_page_config(page_title="CRM - LLDTEK", page_icon="🏢", layout="wide")

AVAILABLE_SHEETS = [
    "2-3-4 DAILY REPORT 12/25",
    "2-3-4 DAILY REPORT 01/26"
]

MASTER_DB_FILE = "CID Salon"
SUP_USERS = ["Phương Loan", "Thùy Dung"]
IGNORED_TAB_NAMES = ["form request", "sheet 4", "sheet4", "request", "request daily", "total", "summary", "copy of", "bản sao"]
KEEP_COLUMNS = ["Date", "Salon_Name", "Agent_Name", "Phone", "CID", "Owner", "Note", "Status", "Issue_Category", "Support_Time", "End_Time", "Ticket_Type", "Caller_Info", "ISO_System", "Training_Note", "Demo_Note", "Card_16_Digits"]

# --- CSS UI ---
st.markdown("""
<style>
    .stApp { font-family: 'Segoe UI', sans-serif; }
    .stTextArea textarea, .stTextInput input { font-family: 'Consolas', monospace; font-weight: 500; border-radius: 5px; }
    div[data-testid="metric-container"] { background-color: #262730; border: 1px solid #41444e; padding: 15px; border-radius: 8px; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
    div[data-testid="metric-container"] label { color: #d0d0d0 !important; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color: #ffffff !important; font-weight: bold; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] { height: 45px; border-radius: 5px; font-weight: 600; color: #e0e0e0; background-color: #262730; border: 1px solid #41444e; }
    .stTabs [aria-selected="true"] { background-color: #ff4b4b !important; color: white; border-color: #ff4b4b !important; }
    div[data-testid="stDataFrame"] { border: 1px solid #41444e; border-radius: 5px; }
    .timer-box { padding: 10px; border-radius: 5px; background-color: #1e3a8a; color: white; text-align: center; font-weight: bold; margin-bottom: 10px; }
    div[data-testid="stTextInput"] input[aria-label="⚡ Nhập CID (Auto-Fill & Check):"] { border: 2px solid #ff4b4b; background-color: #fff0f0; color: black; font-weight: bold; }
    .info-card { background-color: #262730; border: 1px solid #41444e; border-radius: 8px; padding: 15px; margin-bottom: 10px; height: 100%; }
    .info-title { color: #ff4b4b; font-weight: bold; font-size: 1.1em; margin-bottom: 8px; border-bottom: 1px solid #555; padding-bottom: 5px; }
    .info-content { color: #e0e0e0; font-size: 0.95em; white-space: pre-wrap; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. HELPER FUNCTIONS
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
    search_str_1 = now.strftime("%m/%y"); search_str_2 = f"{now.month}/{now.strftime('%y')}"
    defaults = []
    for s in AVAILABLE_SHEETS:
        if search_str_1 in s or search_str_2 in s: defaults.append(s)
    return defaults if defaults else ([AVAILABLE_SHEETS[-1]] if AVAILABLE_SHEETS else [])

def clean_headers(headers):
    seen = {}; result = []
    for h in headers:
        h = str(h).strip(); h = "Unnamed" if not h else h
        if h in seen: seen[h] += 1; result.append(f"{h}_{seen[h]}")
        else: seen[h] = 0; result.append(h)
    return result

def construct_date_from_context(val, sheet_name, tab_name):
    match = re.search(r'(\d{1,2})/(\d{2})', sheet_name)
    file_year = "20" + match.group(2) if match else str(datetime.now().year)
    file_month = match.group(1) if match else "01"
    day_str = str(tab_name).strip()
    if "/" in day_str and len(day_str) <= 5: return f"{day_str}/{file_year}"
    if day_str.isdigit() and int(day_str) <= 31: return f"01/{day_str}/{file_year}"
    return f"{tab_name}/{file_year}"

def format_date_display(val):
    try: return pd.to_datetime(str(val), errors='coerce').strftime('%m/%d/%Y') if not pd.isna(val) and str(val).strip() != "" else str(val)
    except: return str(val)

def safe_process_dataframe(df, rename_map):
    df = df.rename(columns=rename_map); df = df.loc[:, ~df.columns.duplicated()]
    for col in KEEP_COLUMNS: 
        if col not in df.columns: df[col] = ""
    return df[KEEP_COLUMNS]

def parse_vici_comments(comment_str):
    if not comment_str: return "", ""
    clean_str = comment_str.replace('"', '').strip()
    match = re.search(r'(\d{4,6})$', clean_str)
    if match:
        cid = match.group(1)
        name = clean_str[:match.start()].strip()
        return name, cid
    return "", ""

# ==========================================
# 3. SYSTEM SEARCH ENGINE (SMART SWITCH)
# ==========================================
def run_search_engine(search_term):
    # [V62 CHECK] Kiểm tra xem có chìa khóa Web không
    if "web_account" not in st.secrets:
        return "CLOUD_MODE" # Trả về tín hiệu đang chạy trên Cloud

    chrome_options = Options()
    prefs = {"profile.managed_default_content_settings.images": 2, "profile.default_content_setting_values.notifications": 2}
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument("--ignore-ssl-errors")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get("https://lldtek.org"); wait = WebDriverWait(driver, 20)
        try:
            login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Login')]")))
            login_btn.click(); time.sleep(2)
        except: pass 

        user_input = None; pass_input = None
        try:
            inputs = driver.find_elements(By.TAG_NAME, "input")
            for i in inputs:
                t = i.get_attribute("type")
                if t == "text" or t == "email": 
                    if not user_input: user_input = i
                elif t == "password": pass_input = i
            if not user_input and len(inputs) > 0: user_input = inputs[0]
            if not pass_input and len(inputs) > 1: pass_input = inputs[1]
        except: pass

        if user_input and pass_input:
            user_input.send_keys(st.secrets["web_account"]["username"])
            pass_input.send_keys(st.secrets["web_account"]["password"])
            time.sleep(0.5)
            try: pass_input.submit()
            except:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    if "submit" in btn.text.lower():
                        btn.click(); break
        else: return None

        time.sleep(3); driver.get("https://lldtek.org/salon/web/pos/list")
        try:
            search_box = wait.until(EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search']")))
            search_box.clear(); search_box.send_keys(search_term); time.sleep(0.5); search_box.send_keys(Keys.ENTER)
            try:
                search_btns = driver.find_elements(By.TAG_NAME, "button")
                for btn in search_btns:
                    if "search" in btn.text.lower():
                        btn.click(); break
            except: pass
        except: return None
            
        time.sleep(4); soup = BeautifulSoup(driver.page_source, 'html.parser')
        all_tables = soup.find_all('table'); target_table = None; max_rows = 0
        for tbl in all_tables:
            rows_count = len(tbl.find_all('tr'))
            if rows_count > max_rows:
                headers_text = tbl.get_text().lower()
                if "cid" in headers_text or "name" in headers_text or "phone" in headers_text:
                    max_rows = rows_count; target_table = tbl
        
        if target_table:
            headers = []
            header_row = target_table.find('thead')
            if header_row:
                for th in header_row.find_all(['th', 'td']): headers.append(th.get_text(strip=True))
            else:
                first_tr = target_table.find('tr')
                if first_tr:
                    for th in first_tr.find_all(['th', 'td']): headers.append(th.get_text(strip=True))
            rows = []
            tbody = target_table.find('tbody')
            data_rows = tbody.find_all('tr') if tbody else target_table.find_all('tr')[1:]
            for tr in data_rows:
                cells = tr.find_all('td')
                if len(cells) > 0:
                    row_data = [td.get_text(strip=True) for td in cells]
                    if len(row_data) == 1 and "no data" in row_data[0].lower(): continue
                    rows.append(row_data)
            if rows:
                if len(headers) != len(rows[0]): headers = [f"Col_{i+1}" for i in range(len(rows[0]))]
                return pd.DataFrame(rows, columns=headers)
            else: return pd.DataFrame()
        else: return None
    except Exception: return None
    finally: driver.quit()

# ==========================================
# 4. GOOGLE SHEET SYNC
# ==========================================
def get_target_worksheet(date_obj):
    month_year_1 = date_obj.strftime("%m/%y"); month_year_2 = f"{date_obj.month}/{date_obj.strftime('%y')}"
    target_sheet_name = None
    for s in AVAILABLE_SHEETS:
        if month_year_1 in s or month_year_2 in s: target_sheet_name = s; break
    if not target_sheet_name: return None, None, f"⚠️ Không tìm thấy file Report tháng {month_year_1}"
    credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
    gc = gspread.authorize(credentials); sh = gc.open(target_sheet_name)
    day_str = str(date_obj.day)
    target_ws = None
    for ws in sh.worksheets():
        if ws.title.strip() == day_str or ws.title.startswith(f"{day_str}/"): target_ws = ws; break
    if not target_ws: target_ws = sh.worksheets()[-1]
    return sh, target_ws, target_sheet_name

def apply_full_format(ws, row_idx, color_type):
    colors = {'red': {"red": 1.0, "green": 0.0, "blue": 0.0}, 'blue': {"red": 0.0, "green": 0.0, "blue": 1.0}, 'black': {"red": 0.0, "green": 0.0, "blue": 0.0}}
    fmt_spec = {"textFormat": {"fontFamily": "Times New Roman", "fontSize": 12, "foregroundColor": colors.get(color_type, colors['black'])}, "verticalAlignment": "MIDDLE"}
    try: ws.format(f"B{row_idx}:K{row_idx}", fmt_spec)
    except: pass

def save_to_google_sheet(ticket_data):
    try:
        sh, target_ws, sheet_name = get_target_worksheet(ticket_data['Date_Obj'])
        if not target_ws: return False, sheet_name
        all_values = target_ws.get_values("A7:K150"); target_row_idx = -1; current_stt = ""
        for i, row in enumerate(all_values):
            real_row_idx = 7 + i
            val_stt = str(row[0]).strip() if len(row) > 0 else ""; val_name = str(row[1]).strip() if len(row) > 1 else ""; val_salon = str(row[5]).strip() if len(row) > 5 else ""
            if not val_stt: break
            if val_stt and val_name == "" and val_salon == "": target_row_idx = real_row_idx; current_stt = val_stt; break
        if target_row_idx == -1: return False, "⚠️ Hết dòng trống! Vui lòng kéo thêm STT trong Excel."
        full_note = ticket_data['Note']
        if ticket_data['Ticket_Type'] == "Training": full_note = ticket_data['Training_Note'] + " | " + full_note
        if ticket_data['Ticket_Type'] == "Request (16 Digits)": full_note = ticket_data['Card_16_Digits'] + " | " + full_note
        row_data = [ticket_data['Agent_Name'], ticket_data['Support_Time'], ticket_data['End_Time'], "", ticket_data['Salon_Name'], ticket_data['CID'], ticket_data['Phone'], ticket_data['Caller_Info'], full_note, ticket_data['Status']]
        target_ws.update(f"B{target_row_idx}:K{target_row_idx}", [row_data])
        status_val = ticket_data['Status']; color = 'red' if "Support" in status_val else 'black'; apply_full_format(target_ws, target_row_idx, color)
        return True, f"✅ Đã điền vào dòng **{target_row_idx}** (STT: {current_stt})"
    except Exception as e: return False, f"❌ Lỗi: {str(e)}"

def update_google_sheet_row(date_str, phone, salon_name, new_status, new_note):
    try:
        try: date_obj = pd.to_datetime(date_str, format='%m/%d/%Y')
        except: date_obj = pd.to_datetime(date_str)
        sh, target_ws, sheet_name = get_target_worksheet(date_obj)
        if not target_ws: return False, sheet_name
        all_values = target_ws.get_all_values(); target_row_idx = -1
        for idx, row in enumerate(all_values):
            if idx < 6: continue
            if len(row) > 7:
                row_phone = str(row[7]).strip(); row_salon = str(row[5]).strip()
                if phone in row_phone and salon_name in row_salon: target_row_idx = idx + 1; break
        if target_row_idx != -1:
            target_ws.update_cell(target_row_idx, 10, new_note); target_ws.update_cell(target_row_idx, 11, new_status)
            color = 'blue' if "Done" in new_status else ('red' if "Support" in new_status else 'black'); apply_full_format(target_ws, target_row_idx, color)
            return True, f"✅ Đã cập nhật (Dòng {target_row_idx})"
        else: return False, f"⚠️ Không tìm thấy dòng khớp"
    except Exception as e: return False, f"❌ Lỗi Update: {str(e)}"

def update_confirmation_note(cid, new_note):
    try:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials); sh = gc.open(MASTER_DB_FILE)
        ws = sh.worksheet("CONFIRMATION")
        cell = ws.find(cid)
        if cell:
            ws.update_cell(cell.row, 5, new_note)
            return True, "✅ Đã cập nhật Note thành công!"
        else: return False, "⚠️ Không tìm thấy CID này."
    except Exception as e: return False, f"❌ Lỗi: {str(e)}"

# ==========================================
# 5. LOAD DATA & MASTER DB
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def load_gsheet_data(selected_sheets):
    if not selected_sheets: return pd.DataFrame()
    try:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials); all_data = []
        for idx, s_name in enumerate(selected_sheets):
            try:
                sh = gc.open(s_name); tabs = [ws for ws in sh.worksheets() if ws.title.lower().strip() not in IGNORED_TAB_NAMES]
                for i, ws in enumerate(tabs):
                    try:
                        raw = ws.get_all_values()
                        if len(raw) < 2: continue
                        if len(ws.title) < 10 or "/" in ws.title:
                            header_idx = -1
                            for r_idx, row in enumerate(raw[:10]):
                                if "salon" in "".join([str(c).lower() for c in row]): header_idx = r_idx; break
                            if header_idx != -1:
                                df_d = pd.DataFrame(raw[header_idx+1:], columns=clean_headers(raw[header_idx]))
                                rename = {"Salon Name": "Salon_Name", "Name": "Agent_Name", "Time": "Support_Time", "Owner": "Caller_Info", "Phone": "Phone", "CID": "CID", "Note": "Note", "Status": "Status"}
                                df_d = safe_process_dataframe(df_d, rename)
                                if "Note" in df_d.columns: df_d["Issue_Category"] = df_d["Note"]
                                df_d["Date"] = construct_date_from_context(None, s_name, ws.title); df_d["Ticket_Type"] = "Support"; df_d["Status"] = df_d["Status"].replace({"Pending": "Support", "pending": "Support"})
                                all_data.append(df_d)
                    except: continue
            except: pass
        return pd.concat(all_data, ignore_index=True).replace({'nan': '', 'None': '', 'NaN': ''}) if all_data else pd.DataFrame()
    except Exception as e: st.error(f"Lỗi: {e}"); return pd.DataFrame()

@st.cache_data(ttl=3600, show_spinner=False)
def load_master_db():
    try:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials); sh = gc.open(MASTER_DB_FILE)
        master_data = {}
        try: 
            ws_cid = sh.worksheet("CID"); raw_cid = ws_cid.get_all_values()
            if len(raw_cid) > 1:
                headers = clean_headers(raw_cid[0])
                master_data['CID'] = pd.DataFrame(raw_cid[1:], columns=headers)
            else: master_data['CID'] = pd.DataFrame()
        except: master_data['CID'] = pd.DataFrame()
        try: ws_note = sh.worksheet("NOTE"); master_data['NOTE'] = pd.DataFrame(ws_note.get_all_values())
        except: master_data['NOTE'] = pd.DataFrame()
        try: 
            ws_conf = sh.worksheet("CONFIRMATION"); raw_conf = ws_conf.get_all_values()
            if len(raw_conf) > 1:
                headers = clean_headers(raw_conf[1]) 
                master_data['CONFIRMATION'] = pd.DataFrame(raw_conf[2:], columns=headers) 
            else: master_data['CONFIRMATION'] = pd.DataFrame()
        except: master_data['CONFIRMATION'] = pd.DataFrame()
        try: 
            ws_term = None
            for w in sh.worksheets(): 
                if "terminal" in w.title.lower(): ws_term = w; break
            if ws_term: master_data['TERMINAL'] = pd.DataFrame(ws_term.get_all_values())
        except: master_data['TERMINAL'] = pd.DataFrame()
        return master_data
    except Exception as e: return {"Error": str(e)}

def init_db():
    conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, Date TEXT, Salon_Name TEXT, Phone TEXT, Issue_Category TEXT, Note TEXT, Status TEXT, Created_At TEXT, CID TEXT, Contact TEXT, Card_16_Digits TEXT, Training_Note TEXT, Demo_Note TEXT, Agent_Name TEXT, Support_Time TEXT, Caller_Info TEXT, ISO_System TEXT, Ticket_Type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit(); conn.close()

def insert_ticket(date, salon, phone, issue, note, status, cid, agent, time_str, caller, ticket_type, iso="", train_note="", demo_note="", card_info=""):
    conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
    created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''INSERT INTO tickets (Date, Salon_Name, Phone, Issue_Category, Note, Status, Created_At, CID, Agent_Name, Support_Time, Caller_Info, Ticket_Type, ISO_System, Training_Note, Demo_Note, Card_16_Digits) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (date, salon, phone, issue, note, status, created, cid, agent, time_str, caller, ticket_type, iso, train_note, demo_note, card_info))
    conn.commit(); conn.close()

def update_ticket(tid, status, note, salon, phone, cid, caller, card_16="", exp_date=""):
    conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
    extra = f"{card_16} | EXP: {exp_date}" if exp_date else card_16
    sql = '''UPDATE tickets SET Status=?, Note=?, Salon_Name=?, Phone=?, CID=?, Caller_Info=?, Card_16_Digits=? WHERE id=?''' if extra else '''UPDATE tickets SET Status=?, Note=?, Salon_Name=?, Phone=?, CID=?, Caller_Info=? WHERE id=?'''
    params = (status, note, salon, phone, cid, caller, extra, tid) if extra else (status, note, salon, phone, cid, caller, tid)
    c.execute(sql, params); conn.commit(); conn.close()

def save_current_agent_to_db():
    if 'agent_selectbox' in st.session_state:
        conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('current_agent', ?)", (st.session_state.agent_selectbox,))
        conn.commit(); conn.close()

def get_saved_agent_from_db(agent_list):
    conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='current_agent'"); result = c.fetchone(); conn.close()
    return agent_list.index(result[0]) if result and result[0] in agent_list else 0

init_db()

# ==========================================
# 6. GIAO DIỆN CHÍNH
# ==========================================
st.sidebar.title("🏢 CRM - LLDTEK")
if st.sidebar.button("🔄 Cập nhật Dữ liệu Mới"): st.cache_data.clear(); st.rerun()

default_sheets = get_current_month_sheet()
sheets = st.sidebar.multiselect("Dữ liệu Report:", AVAILABLE_SHEETS, default=default_sheets)
df = load_gsheet_data(sheets)

st.sidebar.markdown("---")
agents = ["Phương Loan", "Hương Giang", "Phương Anh", "Tuấn Võ", "Thùy Dung", "Phương Hồ", "Chiến Phạm", "Anh Đạt", "Tiến Dương", "Schang Sanh", "Tuyết Anh", "Liên Chi", "Anh Thư"]
all_agents = [""] + agents
default_index = get_saved_agent_from_db(all_agents)
sel_agent = st.sidebar.selectbox("Nhân viên:", all_agents, index=default_index, key="agent_selectbox", on_change=save_current_agent_to_db)

menu_options = ["🆕 New Ticket", "🗂️ Tra cứu Master Data", "🔍 Search & History"]
if sel_agent in SUP_USERS: menu_options.append("📊 Dashboard (SUP Only)")
menu = st.sidebar.selectbox("Menu", menu_options)

if menu == "🆕 New Ticket":
    st.title("🆕 Tạo Ticket Mới")
    houston_now = get_company_time()
    
    if "ticket_start_time" not in st.session_state or st.session_state.ticket_start_time is None:
        st.session_state.ticket_start_time = houston_now
    start_time_display = format_excel_time(st.session_state.ticket_start_time)
    st.markdown(f"""<div class="timer-box">⏱️ TICKET ĐANG GHI NHẬN TỪ: {start_time_display} (Houston)</div>""", unsafe_allow_html=True)
    
    col_af1, col_af2 = st.columns([1, 2])
    auto_cid = col_af1.text_input("⚡ Nhập CID (Auto-Fill & Check):", placeholder="VD: 07562")
    
    if "auto_fill_salon" not in st.session_state: st.session_state.auto_fill_salon = ""
    if "auto_fill_cid" not in st.session_state: st.session_state.auto_fill_cid = ""

    if auto_cid and auto_cid != st.session_state.auto_fill_cid:
        master_data = load_master_db()
        df_cid = master_data.get('CID', pd.DataFrame())
        found_info = False
        if not df_cid.empty:
            mask = df_cid.iloc[:, 1].astype(str).str.strip().str.contains(auto_cid.strip(), case=False, na=False)
            res = df_cid[mask]
            if not res.empty:
                found_salon = res.iloc[0, 0]
                st.session_state.auto_fill_salon = str(found_salon)
                st.session_state.auto_fill_cid = auto_cid
                found_info = True
                st.success(f"✅ Đã tìm thấy: **{found_salon}**")
        if not found_info:
            st.warning("⚠️ Không tìm thấy Info."); st.session_state.auto_fill_salon = ""; st.session_state.auto_fill_cid = auto_cid

        df_conf = master_data.get('CONFIRMATION', pd.DataFrame())
        if not df_conf.empty:
            found_warning = False
            for idx, row in df_conf.iterrows():
                if len(row) > 2:
                    cell_cid = str(row[2]).strip()
                    if auto_cid.strip() in cell_cid and auto_cid.strip() != "":
                        note_content = str(row[4]) if len(row) > 4 else "Không có nội dung"
                        st.error(f"🔥 CẢNH BÁO ĐẶC BIỆT: {note_content}")
                        found_warning = True
            if not found_warning: st.success("✅ Tiệm này không có cảnh báo đặc biệt (CONFIRMATION).")

        if not df.empty and 'Date_Obj' in df.columns:
            today_str = houston_now.strftime('%m/%d/%Y')
            df['Date_Str'] = df['Date_Obj'].dt.strftime('%m/%d/%Y')
            mask_today = (df['Date_Str'] == today_str) & (df['CID'].astype(str).str.contains(auto_cid.strip(), case=False, na=False))
            df_dup = df[mask_today]
            if not df_dup.empty:
                st.info(f"ℹ️ Tiệm này đã có **{len(df_dup)}** ticket hôm nay:")
                st.dataframe(df_dup[['Support_Time', 'Agent_Name', 'Status', 'Note']], use_container_width=True)

    qp = st.query_params; def_phone = qp.get("phone", ""); def_comments = qp.get("comments", "")
    
    def_salon = st.session_state.auto_fill_salon if st.session_state.auto_fill_salon else ""
    def_cid = st.session_state.auto_fill_cid if st.session_state.auto_fill_cid else ""

    if not def_salon and def_comments:
        parsed_name, parsed_cid = parse_vici_comments(def_comments)
        def_salon = parsed_name
        if not def_cid: def_cid = parsed_cid

    if not def_cid: def_cid = qp.get("cid", "")
    def_owner = qp.get("owner", "")

    with st.expander("🔍 Dữ liệu gốc từ VICI (Bấm để xem/backup)", expanded=False):
        c_raw1, c_raw2 = st.columns(2); 
        c_raw1.text(f"Raw Comments: {def_comments}")
        c_raw2.text(f"Parsed Name: {def_salon}")
        c_raw2.text(f"Parsed CID: {def_cid}")

    if def_phone: st.success(f"📞 VICI CONNECTED: **{def_salon}** - {def_phone}")
    st.markdown("---")
    
    if not sel_agent: st.warning("⚠️ Vui lòng chọn Tên Nhân Viên trước!"); st.stop()
    ticket_type = st.radio("Loại:", ["Report (Hỗ trợ)", "Training", "Demo", "SMS Refill", "SMS Drafting", "Request (16 Digits)"], horizontal=True)
    st.markdown("---")
    
    with st.form("new_ticket_form", clear_on_submit=False): 
        c1, c2, c3 = st.columns([1, 2.5, 1]); d = c1.date_input("📅 Ngày", houston_now); salon = c2.text_input("🏠 Tên Tiệm", value=def_salon); cid = c3.text_input("🆔 CID", value=def_cid)
        c4, c5 = st.columns(2); phone = c4.text_input("📞 Phone *", value=def_phone); caller = c5.text_input("👤 Owner/Caller", value=def_owner)
        iso_val, train_note, demo_note, card_info, note_content = "", "", "", "", ""; status_opts = ["Support", "Done", "No Answer"]
        if ticket_type == "Report (Hỗ trợ)": st.caption(f"Start Time: {start_time_display}"); note_content = st.text_area("Chi tiết *", height=150)
        elif ticket_type == "Training":
            col_iso, col_other = st.columns([1, 1]); iso_opt = col_iso.selectbox("ISO", ["Spoton", "1ST", "TMS", "TMDSpoton", "Khác"]); iso_val = iso_opt if iso_opt != "Khác" else col_other.text_input("Nhập ISO khác")
            topics = st.multiselect("Topics:", ["Mainscreen", "APPT", "Guest List", "Payment", "GC", "Report", "Settings"]); detail = st.text_area("Chi tiết:"); train_note = f"Topics: {', '.join(topics)} | Note: {detail}"; note_content = st.text_area("Ghi chú chung *", height=100)
        elif ticket_type == "Demo": demo_note = st.text_input("Mục đích"); note_content = st.text_area("Diễn biến *", height=150)
        elif ticket_type == "SMS Refill": st.info("💰 Mua gói SMS"); pkg = st.radio("Gói:", ["$50 (2k)", "$100 (5k)", "$200 (11k)", "$300 (17.5k)"]); c_num = st.text_input("Card Num"); c_exp = st.text_input("EXP"); note_content = f"REFILL SMS: {pkg}"; card_info = f"Pkg: {pkg} | Card: {c_num} | Exp: {c_exp}"
        elif ticket_type == "SMS Drafting": st.info("📝 Soạn SMS"); process = st.text_area("Diễn biến"); draft = st.text_area("Nội dung chốt"); note_content = f"DIỄN BIẾN: {process}\nCHỐT: {draft}"; status_opts = ["Support", "Done"]
        elif ticket_type == "Request (16 Digits)": mid = st.text_input("MID"); amt = st.text_input("Amount"); note_content = f"MID: {mid} | Amt: {amt}"; status_opts = ["Request", "Forwarded", "Support", "Done"]
        st.markdown("---"); status = st.selectbox("📌 Trạng thái", status_opts)
        
        if st.form_submit_button("💾 LƯU & ĐỒNG BỘ", type="primary", use_container_width=True):
            if phone:
                end_dt = get_company_time(); end_time_str = format_excel_time(end_dt)
                start_dt = st.session_state.ticket_start_time if st.session_state.ticket_start_time else end_dt; start_time_str = format_excel_time(start_dt); dt_str = start_dt.strftime('%m/%d/%Y')
                insert_ticket(dt_str, salon, phone, note_content, note_content, status, cid, sel_agent, start_time_str, caller, ticket_type, iso_val, train_note, demo_note, card_info)
                ticket_data = {'Date_Obj': start_dt, 'Date_Str': dt_str, 'Salon_Name': salon, 'Agent_Name': sel_agent, 'Support_Time': start_time_str, 'End_Time': end_time_str, 'Phone': phone, 'CID': cid, 'Note': note_content, 'Status': status, 'Caller_Info': caller, 'Ticket_Type': ticket_type, 'Training_Note': train_note, 'Card_16_Digits': card_info}
                with st.spinner("⏳ Đang điền vào form Google Sheet..."): success, msg = save_to_google_sheet(ticket_data)
                if success: 
                    st.success(f"{msg}\n✅ Đã lưu SQLite & GSheet!"); st.toast("Đã lưu xong!", icon="✅"); 
                    st.session_state.ticket_start_time = None; st.session_state.auto_fill_salon = ""; st.session_state.auto_fill_cid = "" 
                    time.sleep(1); st.rerun()
                else: st.warning(f"✅ Đã lưu SQLite nhưng ❌ Lỗi GSheet: {msg}")
            else: st.warning("⚠️ Vui lòng nhập ít nhất Số điện thoại.")

elif menu == "🗂️ Tra cứu Master Data":
    st.title("🗂️ Tra cứu Master Data (CID Salon)")
    with st.spinner("Đang tải dữ liệu từ file CID Salon..."): master_data = load_master_db()
    if "Error" in master_data: st.error(f"❌ Lỗi: {master_data['Error']}"); st.info("💡 Check quyền Share file 'CID Salon'.")
    else:
        tab_cid, tab_conf, tab_note, tab_term = st.tabs(["🔎 Tra cứu CID/Tiệm", "🚨 Special (Confirm)", "📝 ISO & General Note", "🔧 Terminal Fix"])
        
        with tab_cid:
            st.subheader("🔎 Tìm kiếm Thông tin Tiệm (Database Tổng)")
            st.caption("💡 Hệ thống sẽ ưu tiên tìm trong file Master Data. Nếu không có, sẽ tự động mở rộng tìm kiếm.")
            
            df_cid = master_data.get('CID', pd.DataFrame())
            search_term = st.text_input("Nhập CID hoặc Tên Tiệm để tra cứu:", placeholder="VD: 07562 hoặc Elite Nails")
            
            if st.button("🚀 Tìm kiếm", type="primary"):
                if search_term:
                    # 1. Tìm trong Master Data trước
                    found_local = False
                    if not df_cid.empty:
                        mask = df_cid.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
                        res = df_cid[mask]
                        if not res.empty:
                            st.success(f"✅ Đã tìm thấy {len(res)} kết quả trong Master Data:")
                            st.dataframe(res, use_container_width=True)
                            found_local = True
                    
                    # 2. Nếu không thấy -> Kích hoạt tìm kiếm mở rộng (Bot)
                    if not found_local:
                        st.info("⚠️ Không thấy trong Master Data. Đang tra cứu hệ thống mở rộng...")
                        
                        # Hiển thị spinner "ảo" để người dùng không biết là đang chạy Bot
                        with st.spinner("🔄 Đang kết nối dữ liệu hệ thống (Vui lòng đợi 10-15s)..."):
                            result_df = run_search_engine(search_term)
                            
                            if isinstance(result_df, pd.DataFrame) and not result_df.empty:
                                st.success(f"✅ Đã tìm thấy dữ liệu bổ sung:")
                                st.dataframe(result_df, use_container_width=True)
                            elif result_df == "CLOUD_MODE":
                                st.warning("⚠️ Chế độ Tra cứu Mở rộng chỉ khả dụng trên mạng nội bộ (Localhost).")
                            else:
                                st.warning("❌ Không tìm thấy thông tin nào trên toàn bộ hệ thống.")
                else:
                    st.warning("Vui lòng nhập từ khóa.")
            
            # Hiển thị mặc định nếu chưa search
            if not search_term and not df_cid.empty:
                with st.expander("Xem toàn bộ danh sách Master Data (Cũ)", expanded=False):
                    st.dataframe(df_cid, height=400, use_container_width=True)
        
        with tab_conf:
            st.subheader("🚨 Danh sách Tiệm cần Lưu ý Đặc biệt (CONFIRMATION)")
            df_conf = master_data.get('CONFIRMATION', pd.DataFrame())
            
            search_conf = st.text_input("🔎 Tìm kiếm Note Đặc biệt (Nhập CID/Tên/Note):")
            if not df_conf.empty:
                if search_conf:
                    mask_conf = df_conf.astype(str).apply(lambda x: x.str.contains(search_conf, case=False, na=False)).any(axis=1)
                    st.dataframe(df_conf[mask_conf], use_container_width=True)
                else: st.dataframe(df_conf, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### 📝 Cập nhật Note cho Tiệm")
            with st.form("update_note_form"):
                target_cid = st.text_input("Nhập CID cần Note:")
                new_note_content = st.text_area("Nội dung Note mới:")
                if st.form_submit_button("Lưu Note lên Sheet"):
                    if target_cid and new_note_content:
                        with st.spinner("Đang ghi vào sheet CONFIRMATION..."):
                            success, msg = update_confirmation_note(target_cid, new_note_content)
                            if success: st.success(msg); st.cache_data.clear()
                            else: st.error(msg)
                    else: st.warning("Vui lòng nhập đủ CID và Nội dung.")

        with tab_note: 
            st.subheader("📝 Kiến thức chung & ISO (NOTE)")
            df_note = master_data.get('NOTE', pd.DataFrame())
            if not df_note.empty:
                cols = st.columns(2)
                for index, row in df_note.iterrows():
                    title = str(row[0]).strip() if len(row) > 0 else ""
                    content = str(row[1]).strip() if len(row) > 1 else ""
                    if title and content:
                        with cols[index % 2]:
                            st.markdown(f"""<div class="info-card"><div class="info-title">{title}</div><div class="info-content">{content}</div></div>""", unsafe_allow_html=True)
            else: st.info("Chưa có dữ liệu Note.")
        
        with tab_term: 
            st.subheader("🔧 Terminal Integrate & Update")
            df_term = master_data.get('TERMINAL', pd.DataFrame())
            if not df_term.empty:
                search_term = st.text_input("🔎 Tìm kiếm lỗi Terminal:", placeholder="Nhập mã lỗi hoặc tên máy...")
                for index, row in df_term.iterrows():
                    if index == 0 and "Terminal" in str(row[0]): continue
                    term_name = str(row[0]).strip() if len(row) > 0 else ""
                    error_name = str(row[1]).strip() if len(row) > 1 else ""
                    full_title = f"🔌 {term_name} - {error_name}"
                    fix_integrate = str(row[2]).strip() if len(row) > 2 else ""
                    fix_update = str(row[3]).strip() if len(row) > 3 else ""
                    content_text = f"{fix_integrate} {fix_update}"
                    if search_term and search_term.lower() not in full_title.lower() and search_term.lower() not in content_text.lower(): continue
                    if term_name or error_name:
                        with st.expander(full_title):
                            if fix_integrate: st.markdown(f"**🛠️ Integrate:**\n{fix_integrate}")
                            if fix_update: st.markdown(f"**📲 Update:**\n{fix_update}")

elif menu == "🔍 Search & History":
    st.title("🔍 Tra cứu & Lịch sử"); term = st.text_input("🔎 Nhập từ khóa (Tên tiệm, SĐT, CID):"); filter_type = st.radio("Lọc:", ["Tất cả", "Training", "Request (16 Digits)", "SMS"], horizontal=True)
    if term:
        mask = pd.Series([False]*len(df)); cols = ['Salon_Name', 'Phone', 'CID', 'Agent_Name', 'Date']; valid = [c for c in cols if c in df.columns]; 
        for c in valid: mask |= df[c].astype(str).str.lower().str.contains(term.lower(), na=False)
        df_search = df[mask].copy()
        if filter_type == 'Training': df_search = df_search[df_search['Ticket_Type'] == 'Training']
        elif filter_type == 'Request (16 Digits)': df_search = df_search[df_search['Ticket_Type'].str.contains('Request', na=False)]
        elif filter_type == 'SMS': df_search = df_search[df_search['Ticket_Type'].str.contains('SMS', na=False)]
        if not df_search.empty:
            if "Date" in df_search.columns: df_search['Date_Obj'] = pd.to_datetime(df_search['Date'], errors='coerce'); df_search = df_search.sort_values('Date_Obj', ascending=False)
            df_search['Display_Date'] = df_search['Date'].apply(format_date_display)
            cols = ['Display_Date','Agent_Name','Ticket_Type','Salon_Name','Note','Status']; 
            if filter_type == 'Request (16 Digits)': cols.append('Card_16_Digits')
            final_cols = [c for c in cols if c in df_search.columns]
            @st.dialog("📝 CẬP NHẬT TICKET (2 CHIỀU)")
            def edit_ticket(row):
                st.info(f"🏠 {row.get('Salon_Name')} | {row.get('Ticket_Type')}"); st.text_area("Nội dung hiện tại (Read-only):", value=str(row.get('Note')), height=100, disabled=True); new_card, new_exp = "", ""; 
                if "Request" in str(row.get('Ticket_Type')): st.markdown("---"); st.warning("💳 **KHU VỰC SUP NHẬP THÔNG TIN THẺ**"); c1, c2 = st.columns(2); current_card = str(row.get('Card_16_Digits', '')); curr_num = current_card.split('|')[0].strip() if '|' in current_card else current_card; new_card = c1.text_input("16 Số Thẻ (Full)", value=curr_num); new_exp = c2.text_input("EXP Date")
                st.markdown("---"); new_status = st.selectbox("Trạng thái mới", ["Support", "Done", "No Answer", "Request", "Forwarded by SUP"], index=0); new_note = st.text_area("Cập nhật / Bổ sung Ghi chú:", value=str(row.get('Note')), height=150)
                if st.button("Lưu Thay Đổi (Cập nhật 2 nơi)"):
                    update_ticket(row.get('id'), new_status, new_note, row.get('Salon_Name'), row.get('Phone'), row.get('CID'), row.get('Caller_Info'), new_card, new_exp)
                    with st.spinner("Đang cập nhật Google Sheet & Đổi màu..."):
                        date_str = row.get('Display_Date'); 
                        if not date_str: date_str = row.get('Date')
                        success, msg = update_google_sheet_row(date_str, row.get('Phone'), row.get('Salon_Name'), new_status, new_note)
                    if success: st.success(f"✅ Đã cập nhật Database!\n{msg}"); st.rerun()
                    else: st.warning(f"✅ Đã cập nhật Database nhưng ❌ {msg}"); st.rerun()
            event = st.dataframe(df_search[final_cols], hide_index=True, use_container_width=True, selection_mode="single-row", on_select="rerun", column_config={"Note": st.column_config.TextColumn("Nội dung", width="large")}); 
            if len(event.selection.rows) > 0: edit_ticket(df_search.iloc[event.selection.rows[0]])
        else: st.info("Không tìm thấy kết quả.")

elif menu == "📊 Dashboard (SUP Only)":
    st.title("📊 Trung Tâm Điều Hành (Deep Analytics)"); company_now = get_company_time(); st.toast(f"📍 Múi giờ Houston: {company_now.strftime('%H:%M - %d/%m')}", icon="🕒")
    if not df.empty:
        df_chart = df.copy(); 
        if 'Date' in df_chart.columns: df_chart['Date_Obj'] = pd.to_datetime(df_chart['Date'], errors='coerce'); df_chart = df_chart.dropna(subset=['Date_Obj'])
        with st.expander("📅 BỘ LỌC DỮ LIỆU", expanded=True):
            col_filter, col_range = st.columns([1, 2]); filter_mode = col_filter.radio("Thời gian:", ["Hôm nay", "Tuần này", "Tháng này"], horizontal=True); today_company = company_now.date()
            if filter_mode == "Hôm nay": d_start, d_end = today_company, today_company
            elif filter_mode == "Tuần này": d_start, d_end = today_company - timedelta(days=today_company.weekday()), today_company
            else: d_start, d_end = today_company.replace(day=1), today_company
            mask = (df_chart['Date_Obj'].dt.date >= d_start) & (df_chart['Date_Obj'].dt.date <= d_end); df_filtered = df_chart.loc[mask].copy()
        if df_filtered.empty: st.warning(f"⚠️ Không có dữ liệu trong khoảng {d_start} đến {d_end} (Giờ Houston).")
        else:
            tab1, tab2, tab3 = st.tabs(["📈 Tổng Quan & KPI", "🚨 Phân Tích & Top Tiệm", "🏆 Hiệu Suất Team"])
            with tab1:
                total = len(df_filtered); df_filtered['Status_Norm'] = df_filtered['Status'].astype(str).str.lower()
                done = len(df_filtered[df_filtered['Status_Norm'].str.contains('done')]); pending = len(df_filtered[df_filtered['Status_Norm'].str.contains('pending')|df_filtered['Status_Norm'].str.contains('support')])
                c1, c2, c3, c4 = st.columns(4); c1.metric("Tổng Ticket", total); c2.metric("Done", done, f"{(done/total*100):.1f}%"); c3.metric("Support (Pending)", pending, delta_color="inverse"); c4.metric("Request Thẻ", len(df_filtered[df_filtered['Status_Norm'].str.contains('request')]))
                st.markdown("---"); daily_counts = df_filtered.groupby(df_filtered['Date_Obj'].dt.date).size().reset_index(name='Tickets'); fig_line = px.line(daily_counts, x='Date_Obj', y='Tickets', markers=True, title="📉 Xu hướng Ticket", template="plotly_dark"); st.plotly_chart(fig_line, use_container_width=True)
            with tab2:
                col_salon, col_issue = st.columns([1, 1])
                with col_salon:
                    st.markdown("### 🏪 Top 10 Tiệm Gọi Nhiều Nhất")
                    if 'Salon_Name' in df_filtered.columns:
                        top_salons = df_filtered['Salon_Name'].value_counts().nlargest(10).reset_index(); top_salons.columns = ['Tên Tiệm', 'Số lần gọi']; st.dataframe(top_salons, hide_index=True, use_container_width=True, column_config={"Số lần gọi": st.column_config.ProgressColumn("Cường độ", format="%d", min_value=0, max_value=int(top_salons['Số lần gọi'].max()))})
                with col_issue:
                    st.markdown("### 📋 Top Vấn Đề"); 
                    if 'Issue_Category' in df_filtered.columns: issues = df_filtered['Issue_Category'].fillna("Khác").astype(str).str.strip(); top_issues = issues.value_counts().nlargest(10).reset_index(); top_issues.columns = ['Vấn đề', 'Số lượng']; fig_bar = px.bar(top_issues, x='Số lượng', y='Vấn đề', orientation='h', text='Số lượng', color='Số lượng', color_continuous_scale='Redor', template="plotly_dark"); fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}); st.plotly_chart(fig_bar, use_container_width=True)
            with tab3:
                st.markdown("### 🏆 Bảng Xếp Hạng Năng Suất")
                if 'Agent_Name' in df_filtered.columns:
                    agent_stats = df_filtered['Agent_Name'].value_counts().reset_index(); agent_stats.columns = ['Nhân viên', 'Tổng Ticket']
                    pending_stats = df_filtered[df_filtered['Status_Norm'].str.contains('pending')|df_filtered['Status_Norm'].str.contains('support')]['Agent_Name'].value_counts().reset_index(); pending_stats.columns = ['Nhân viên', 'Support (Pending)']
                    final_stats = pd.merge(agent_stats, pending_stats, on='Nhân viên', how='left').fillna(0); final_stats['Support (Pending)'] = final_stats['Support (Pending)'].astype(int)
                    st.dataframe(final_stats, hide_index=True, use_container_width=True, column_config={"Tổng Ticket": st.column_config.ProgressColumn("Khối lượng công việc", format="%d", min_value=0, max_value=int(final_stats['Tổng Ticket'].max())), "Support (Pending)": st.column_config.NumberColumn("Đang nợ (Support)", format="%d ⚠️")})
    else: st.info("Vui lòng chọn file dữ liệu.")