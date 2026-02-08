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
from PIL import Image, ImageDraw # Thêm thư viện vẽ ảnh

# ==========================================
# 1. CẤU HÌNH & LOGO
# ==========================================
def create_tech_logo():
    # 1. Tạo nền icon (256x256) màu Xanh Navy đậm (Tech Style)
    img = Image.new('RGB', (256, 256), color=(10, 25, 47)) 
    d = ImageDraw.Draw(img)
    
    # 2. Vẽ Mạng lưới kết nối (CRM Network)
    # Tâm (128, 128)
    # 3 Nhánh kết nối ra 3 hướng
    # Nhánh 1: Lên trên
    d.line([(128, 128), (128, 50)], fill=(200, 200, 200), width=8)
    # Nhánh 2: Xuống trái
    d.line([(128, 128), (60, 190)], fill=(200, 200, 200), width=8)
    # Nhánh 3: Xuống phải
    d.line([(128, 128), (196, 190)], fill=(200, 200, 200), width=8)
    
    # Vẽ các Node (Tròn)
    # Node Trung tâm (To nhất - Màu Cyan)
    d.ellipse([(98, 98), (158, 158)], fill=(0, 255, 255), outline=(255, 255, 255), width=3)
    
    # Node Vệ tinh (Nhỏ hơn - Màu Trắng)
    d.ellipse([(108, 30), (148, 70)], fill=(255, 255, 255))   # Top
    d.ellipse([(40, 170), (80, 210)], fill=(255, 255, 255))   # Left
    d.ellipse([(176, 170), (216, 210)], fill=(255, 255, 255)) # Right
    
    return img

# Cấu hình App với Logo tự vẽ
try:
    app_icon = create_tech_logo()
    st.set_page_config(page_title="CRM - LLDTEK", page_icon=app_icon, layout="wide")
except:
    st.set_page_config(page_title="CRM - LLDTEK", page_icon="📡", layout="wide")

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, Date TEXT, Salon_Name TEXT, Phone TEXT, Issue_Category TEXT, Note TEXT, Status TEXT, Created_At TEXT, CID TEXT, Contact TEXT, Card_16_Digits TEXT, Training_Note TEXT, Demo_Note TEXT, Agent_Name TEXT, Support_Time TEXT, Caller_Info TEXT, ISO_System TEXT, Ticket_Type TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit(); conn.close()
init_db()

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

# --- UI CSS ---
st.markdown("""
<style>
    .stApp { font-family: 'Segoe UI', sans-serif; }
    .stTextArea textarea, .stTextInput input { font-family: 'Consolas', monospace; font-weight: 500; border-radius: 5px; }
    div[data-testid="stTextInput"] input[aria-label="⚡ Nhập CID (Auto-Fill & Check):"] { border: 2px solid #ff4b4b; background-color: #fff0f0; color: black; font-weight: bold; }
    footer {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. AUTO-DETECT SHEETS
# ==========================================
@st.cache_data(ttl=300) 
def get_dynamic_sheets():
    try:
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        gc = gspread.authorize(credentials)
        all_files = gc.list_spreadsheet_files()
        crm_files = [f['name'] for f in all_files if f['name'].upper().startswith("2-3-4 DAILY REPORT")]
        def parse_date_sort(filename):
            try:
                date_part = filename.upper().split("REPORT")[-1].strip()
                return datetime.strptime(date_part, "%m/%y")
            except:
                return datetime.min
        crm_files.sort(key=parse_date_sort, reverse=True)
        return crm_files if crm_files else ["2-3-4 DAILY REPORT 12/25", "2-3-4 DAILY REPORT 01/26", "2-3-4 DAILY REPORT 02/26"]
    except Exception as e:
        return ["2-3-4 DAILY REPORT 12/25", "2-3-4 DAILY REPORT 01/26", "2-3-4 DAILY REPORT 02/26"]

AVAILABLE_SHEETS = get_dynamic_sheets()
MASTER_DB_FILE = "CID Salon"
SUP_USERS = ["Phương Loan", "Thùy Dung"]
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
    search_str_1 = now.strftime("%m/%y"); search_str_2 = f"{now.month}/{now.strftime('%y')}"
    defaults = []
    for s in AVAILABLE_SHEETS:
        if search_str_1 in s or search_str_2 in s: defaults.append(s)
    return defaults if defaults else ([AVAILABLE_SHEETS[0]] if AVAILABLE_SHEETS else [])

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
    if day_str.isdigit() and int(day_str) <= 31: return f"{file_month}/{day_str}/{file_year}" 
    return f"{tab_name}/{file_year}"

def format_date_display(val):
    try: return pd.to_datetime(str(val), errors='coerce').strftime('%m/%d/%Y') if not pd.isna(val) and str(val).strip() != "" else str(val)
    except: return str(val)

def safe_process_dataframe(df, rename_map):
    df = df.rename(columns=rename_map); df = df.loc[:, ~df.columns.duplicated()]
    for col in KEEP_COLUMNS: 
        if col not in df.columns: df[col] = ""
    return df[KEEP_COLUMNS]

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
    except: return None

def run_search_engine(search_term):
    if is_cloud_mode: return "CLOUD_MODE"
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
        except: driver.quit(); return None
        
        status_log.info("🔍 Đang tra cứu thông tin...")
        driver.get("https://lldtek.org/salon/web/pos/list")
        
        try:
            search_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'search')]")))
            target_input = search_btn.find_element(By.XPATH, "./preceding::input[1]")
            
            ph = str(target_input.get_attribute("placeholder")).lower()
            if "date" in ph or "mm/dd" in ph:
                status_log.error("❌ Bot nhầm ô Date.")
            else:
                target_input.click(); target_input.clear(); target_input.send_keys(search_term)
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
            driver.quit(); status_log.empty(); return pd.DataFrame()
        except Exception as e:
            if driver: driver.quit(); return None
    except Exception as e:
        if driver: driver.quit(); return None

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
            status_box.update(label="❌ Lỗi mở File", state="error")
            return False, f"Không tìm thấy file '{MASTER_DB_FILE}'."

        try:
            ws = sh.worksheet("CID")
        except:
            ws = sh.add_worksheet(title="CID", rows=1000, cols=10)
            ws.append_row(["Salon Name", "CID", "Agent Name", "Updated At"])

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
            status_box.write(f"📝 Ghi: {row_data}")
            
            ws.append_row(row_data)
            count += 1
            
        status_box.update(label=f"✅ Đã lưu {count} dòng!", state="complete")
        return True, f"Đã lưu {count} dòng vào sheet CID."
        
    except Exception as e:
        status_box.update(label="❌ Lỗi Hệ Thống", state="error")
        return False, str(e)

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
    fmt_base = {"textFormat": {"fontFamily": "Times New Roman", "fontSize": 12, "foregroundColor": colors.get(color_type, colors['black'])}, "verticalAlignment": "BOTTOM"}
    fmt_center = fmt_base.copy(); fmt_center["horizontalAlignment"] = "CENTER"; fmt_center["wrapStrategy"] = "WRAP"
    fmt_left_clip = fmt_base.copy(); fmt_left_clip["horizontalAlignment"] = "LEFT"; fmt_left_clip["wrapStrategy"] = "CLIP"
    fmt_left_wrap = fmt_base.copy(); fmt_left_wrap["horizontalAlignment"] = "LEFT"; fmt_left_wrap["wrapStrategy"] = "WRAP"
    try:
        ws.format(f"B{row_idx}:K{row_idx}", fmt_center)
        ws.format(f"B{row_idx}:C{row_idx}", fmt_left_clip)
        ws.format(f"F{row_idx}", fmt_left_wrap)
        ws.format(f"J{row_idx}:K{row_idx}", fmt_left_wrap)
    except: pass

def save_to_google_sheet(ticket_data):
    try:
        sh, target_ws, sheet_name = get_target_worksheet(ticket_data['Date_Obj'])
        if not target_ws: return False, sheet_name
        all_values = target_ws.get_values("A7:K150"); target_row_idx = -1; current_stt = ""
        for i, row in enumerate(all_values):
            real_row_idx = 7 + i
            val_stt = str(row[0]).strip() if len(row) > 0 else ""; val_name = str(row[1]).strip() if len(row) > 1 else ""
            if not val_stt: break
            if val_stt and val_name == "": target_row_idx = real_row_idx; current_stt = val_stt; break
        if target_row_idx == -1: return False, "⚠️ Hết dòng trống! Vui lòng kéo thêm STT trong Excel."
        full_note = ticket_data['Note']
        if ticket_data['Ticket_Type'] == "Training": full_note = ticket_data['Training_Note'] + " | " + full_note
        if ticket_data['Ticket_Type'] == "Request (16 Digits)": full_note = ticket_data['Card_16_Digits'] + " | " + full_note
        row_data = [ticket_data['Agent_Name'], ticket_data['Support_Time'], ticket_data['End_Time'], "", ticket_data['Salon_Name'], ticket_data['CID'], ticket_data['Phone'], ticket_data['Caller_Info'], full_note, ticket_data['Status']]
        target_ws.update(f"B{target_row_idx}:K{target_row_idx}", [row_data])
        status_val = ticket_data['Status']; color = 'red' if "Support" in status_val else 'black'
        apply_full_format(target_ws, target_row_idx, color)
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
            color = 'blue' if "Done" in new_status else ('red' if "Support" in new_status else 'black')
            apply_full_format(target_ws, target_row_idx, color)
            return True, f"✅ Đã cập nhật (Dòng {target_row_idx})"
        else: return False, f"⚠️ Không tìm thấy dòng khớp"
    except Exception as e: return False, f"❌ Lỗi Update: {str(e)}"

# ==========================================
# 6. LOAD DATA & GLOBAL (FIX DUPLICATE & INDEX)
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def load_gsheet_data(selected_sheets):
    if not selected_sheets: return pd.DataFrame()
    try:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials); all_data = []
        for idx, s_name in enumerate(selected_sheets):
            try:
                sh = gc.open(s_name); tabs = [ws for ws in sh.worksheets() if not any(ign in ws.title.lower() for ign in IGNORED_TAB_NAMES)]
                for i, ws in enumerate(tabs):
                    try:
                        raw = ws.get_all_values()
                        if len(raw) < 2: continue
                        if len(ws.title) < 10 or "/" in ws.title:
                            header_idx = -1
                            for r_idx, row in enumerate(raw[:15]):
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
        if all_data:
            final_df = pd.concat(all_data, ignore_index=True).replace({'nan': '', 'None': '', 'NaN': ''})
            # --- FIX: DROP DUPLICATES & RESET INDEX ---
            final_df = final_df.drop_duplicates(subset=['Phone', 'Date', 'Support_Time', 'Agent_Name']).reset_index(drop=True)
            return final_df
        return pd.DataFrame()
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
                headers = clean_headers(raw_cid[0]); master_data['CID'] = pd.DataFrame(raw_cid[1:], columns=headers)
                master_data['CID'].columns = master_data['CID'].columns.str.strip()
            else: master_data['CID'] = pd.DataFrame()
        except: master_data['CID'] = pd.DataFrame()
        try: ws_note = sh.worksheet("NOTE"); master_data['NOTE'] = pd.DataFrame(ws_note.get_all_values())
        except: master_data['NOTE'] = pd.DataFrame()
        try: 
            ws_conf = sh.worksheet("CONFIRMATION"); raw_conf = ws_conf.get_all_values()
            if len(raw_conf) > 1:
                headers = clean_headers(raw_conf[1]); master_data['CONFIRMATION'] = pd.DataFrame(raw_conf[2:], columns=headers) 
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

def update_confirmation_note(cid, new_note):
    try:
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive'])
        gc = gspread.authorize(credentials); sh = gc.open(MASTER_DB_FILE)
        ws = sh.worksheet("CONFIRMATION")
        cell = ws.find(cid)
        if cell: ws.update_cell(cell.row, 5, new_note); return True, "✅ Đã cập nhật Note thành công!"
        else: return False, "⚠️ Không tìm thấy CID này."
    except Exception as e: return False, f"❌ Lỗi: {str(e)}"

# ==========================================
# 7. GIAO DIỆN CHÍNH
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

# --- SESSION STATE & AUTO CLEAR FORM ---
keys_to_init = ["ticket_phone", "ticket_salon", "ticket_cid", "ticket_owner", "ticket_note", "ticket_start_time"]
for k in keys_to_init:
    if k not in st.session_state: st.session_state[k] = "" if k != "ticket_start_time" else None

def clear_form():
    st.session_state.ticket_phone = ""
    st.session_state.ticket_salon = ""
    st.session_state.ticket_cid = ""
    st.session_state.ticket_owner = ""
    st.session_state.ticket_note = ""
    st.session_state.ticket_start_time = None

@st.dialog("⚠️ XÁC NHẬN LƯU TICKET")
def confirm_save_dialog(data_pack):
    st.markdown(f"""<div style="text-align: center;"><h3 style="color: #4CAF50;">{data_pack['Salon_Name']}</h3><p><b>SĐT:</b> {data_pack['Phone']} | <b>Trạng thái:</b> {data_pack['Status']}</p><hr><p style="text-align: left;"><b>Nội dung:</b><br>{data_pack['Note']}</p></div>""", unsafe_allow_html=True)
    if st.button("✅ ĐỒNG Ý LƯU & CLEAR FORM", type="primary", use_container_width=True):
        insert_ticket(data_pack['Date_Str'], data_pack['Salon_Name'], data_pack['Phone'], data_pack['Note'], data_pack['Note'], data_pack['Status'], data_pack['CID'], data_pack['Agent_Name'], data_pack['Support_Time'], data_pack['Caller_Info'], data_pack['Ticket_Type'], "", data_pack['Training_Note'], "", data_pack['Card_16_Digits'])
        with st.spinner("⏳ Đang đồng bộ Google Sheet..."):
            success, msg = save_to_google_sheet(data_pack)
        if success: 
            st.toast("✅ Lưu thành công!", icon="✨")
            clear_form() 
            time.sleep(1)
            st.rerun()
        else: st.error(f"Lỗi GSheet: {msg}")

if menu == "🆕 New Ticket":
    st.title("🆕 Tạo Ticket Mới")
    houston_now = get_company_time()
    
    # --- PHẦN 1: XỬ LÝ DỮ LIỆU VICI & UI/UX HIỆN ĐẠI ---
    qp = st.query_params
    
    # 1.1. Bắt dữ liệu từ URL và lưu vào Session State
    if any(k in qp for k in ["phone", "address", "comments", "first"]):
        st.session_state.vici_cache = {
            "title": qp.get("title", ""),
            "first": qp.get("first", ""),
            "last": qp.get("last", ""),
            "address": qp.get("address", ""),
            "city": qp.get("city", ""),
            "state": qp.get("state", ""),
            "zip": qp.get("zip", ""),
            "vendor_id": qp.get("vendor_id", ""),
            "phone": qp.get("phone", ""),
            "alt_phone": qp.get("alt_phone", ""),
            "email": qp.get("email", ""),
            "comments": qp.get("comments", ""),
            "user": qp.get("user", "")
        }
        
        # Auto-fill cơ bản
        if st.session_state.vici_cache['phone']: 
            st.session_state.ticket_phone = st.session_state.vici_cache['phone']
        st.session_state.ticket_owner = st.session_state.vici_cache['user']
        
        # Logic tách CID
        def smart_parse(text):
            if not text: return None, None
            match = re.search(r'\b(\d{4,6})\b', text) 
            if match:
                cid = match.group(1)
                name = text[:match.start()].strip(' -:,|#').strip()
                return cid, name
            return None, text 

        # Thử điền tên tiệm/CID
        if not st.session_state.ticket_cid:
            f_cid, f_name = smart_parse(st.session_state.vici_cache['address'])
            if not f_cid: f_cid, f_name = smart_parse(st.session_state.vici_cache['comments'])
            
            if f_cid: 
                st.session_state.ticket_cid = f_cid
                if f_name: st.session_state.ticket_salon = f_name
                st.toast(f"🤖 Auto-Detected: {f_name} (CID: {f_cid})")

        # Xóa URL
        st.query_params.clear()

    # 1.2. HIỂN THỊ UI/UX
    if 'vici_cache' in st.session_state and st.session_state.vici_cache:
        v = st.session_state.vici_cache
        
        with st.expander(f"📡 DỮ LIỆU VICI: {v['first']} {v['last']} - {v['phone']} (Click để mở)", expanded=True):
            
            # Hàng 1: Nút Quick Action
            st.markdown("##### ⚡ Thao tác nhanh:")
            c_act1, c_act2, c_act3, c_act4 = st.columns(4)
            
            if c_act1.button("🏢 Lấy Address làm Tên Tiệm", use_container_width=True):
                st.session_state.ticket_salon = v['address']
                st.rerun()
            
            if c_act2.button("📝 Chép Comment vào Note", use_container_width=True):
                st.session_state.ticket_note = (str(st.session_state.ticket_note) + "\n" + v['comments']).strip()
                st.rerun()
                
            if c_act3.button("🆔 Lấy Vendor ID làm CID", use_container_width=True):
                st.session_state.ticket_cid = v['vendor_id']
                st.rerun()
                
            if c_act4.button("🗑️ Xóa dữ liệu VICI", use_container_width=True):
                del st.session_state.vici_cache
                st.rerun()

            st.markdown("---")

            # Hàng 2: Grid Info
            col_info1, col_info2 = st.columns([1, 1])
            with col_info1:
                st.info("**👤 Thông tin cá nhân**")
                st.markdown(f"""
                - **Name:** {v['title']} {v['first']} {v['last']}
                - **Phone:** `{v['phone']}`
                - **Alt Phone:** `{v['alt_phone']}`
                - **Email:** {v['email']}
                """)
            with col_info2:
                st.warning("**📍 Địa chỉ & Hệ thống**")
                st.markdown(f"""
                - **Address:** {v['address']}
                - **City/State:** {v['city']}, {v['state']} {v['zip']}
                - **Vendor ID:** `{v['vendor_id']}`
                """)
            
            # Phần Comments
            if v['comments']:
                st.error("**💬 Comments / Ghi chú từ VICI:**")
                st.code(v['comments'], language="text")

    # --- PHẦN 2: FORM NHẬP LIỆU ---
    if st.session_state.ticket_start_time is None: st.session_state.ticket_start_time = houston_now
    start_time_display = format_excel_time(st.session_state.ticket_start_time)
    
    st.markdown(f"""
    <div style="padding: 10px; background-color: #262730; border-radius: 5px; border: 1px solid #4e4f57; text-align: center; margin-bottom: 20px;">
        <span style="font-size: 1.2em;">⏱️</span> 
        <span style="font-weight: bold; color: #ff4b4b;">TICKET STARTED:</span> 
        <span style="font-family: monospace; font-size: 1.2em;">{start_time_display} (Houston)</span>
    </div>
    """, unsafe_allow_html=True)

    col_af1, col_af2 = st.columns([1, 2])
    auto_cid = col_af1.text_input("⚡ Nhập CID (Auto-Fill & Check):", value=st.session_state.ticket_cid, placeholder="VD: 07562", key="input_cid_trigger")
    if auto_cid and st.session_state.ticket_cid != auto_cid:
         st.session_state.ticket_cid = auto_cid
         with st.spinner("Checking..."):
            master_data = load_master_db(); df_cid = master_data.get('CID', pd.DataFrame())
            if not df_cid.empty:
                cid_col = next((c for c in df_cid.columns if "cid" in c.lower() or "code" in c.lower()), df_cid.columns[1] if len(df_cid.columns)>1 else None)
                name_col = next((c for c in df_cid.columns if "name" in c.lower() or "salon" in c.lower()), df_cid.columns[0] if len(df_cid.columns)>0 else None)
                
                if cid_col and name_col:
                    mask = df_cid[cid_col].astype(str).str.strip() == auto_cid.strip()
                    res = df_cid[mask]
                    if not res.empty: 
                        st.session_state.ticket_salon = str(res.iloc[0][name_col])
                        st.success(f"✅ Auto-Fill: {st.session_state.ticket_salon}")
                    else: st.warning("⚠️ CID này chưa có trong file Excel")

    if not sel_agent: st.warning("⚠️ Vui lòng chọn Tên Nhân Viên trước!"); st.stop()
    ticket_type = st.radio("Loại:", ["Report (Hỗ trợ)", "Training", "Demo", "SMS Refill", "SMS Drafting", "Request (16 Digits)"], horizontal=True)
    c1, c2, c3 = st.columns([1, 2.5, 1]); d = c1.date_input("📅 Ngày", houston_now); salon = c2.text_input("🏠 Tên Tiệm", key="ticket_salon"); cid = c3.text_input("🆔 CID", key="ticket_cid")
    c4, c5 = st.columns(2); phone = c4.text_input("📞 Phone *", key="ticket_phone"); caller = c5.text_input("👤 Owner/Caller", key="ticket_owner")
    iso_val, train_note, demo_note, card_info, note_content = "", "", "", "", ""
    status_opts = ["Support", "Done", "No Answer"]
    if ticket_type == "Report (Hỗ trợ)": note_content = st.text_area("Chi tiết *", height=150, key="ticket_note")
    elif ticket_type == "Training": 
        col_iso, col_other = st.columns([1, 1]); iso_opt = col_iso.selectbox("ISO", ["Spoton", "1ST", "TMS", "TMDSpoton", "Khác"]); iso_val = iso_opt if iso_opt != "Khác" else col_other.text_input("Nhập ISO khác")
        topics = st.multiselect("Topics:", ["Mainscreen", "APPT", "Guest List", "Payment", "GC", "Report", "Settings"]); detail = st.text_area("Chi tiết:"); train_note = f"Topics: {', '.join(topics)} | Note: {detail}"; note_content = st.text_area("Ghi chú chung *", height=100, key="ticket_note")
    elif ticket_type == "Demo": demo_note = st.text_input("Mục đích"); note_content = st.text_area("Diễn biến *", height=150, key="ticket_note")
    elif ticket_type == "SMS Refill": st.info("💰 Mua gói SMS"); pkg = st.radio("Gói:", ["$50 (2k)", "$100 (5k)", "$200 (11k)", "$300 (17.5k)"]); c_num = st.text_input("Card Num"); c_exp = st.text_input("EXP"); note_content = f"REFILL SMS: {pkg}"; card_info = f"Pkg: {pkg} | Card: {c_num} | Exp: {c_exp}"
    elif ticket_type == "SMS Drafting": st.info("📝 Soạn SMS"); process = st.text_area("Diễn biến"); draft = st.text_area("Nội dung chốt"); note_content = f"DIỄN BIẾN: {process}\nCHỐT: {draft}"; status_opts = ["Support", "Done"]
    elif ticket_type == "Request (16 Digits)": mid = st.text_input("MID"); amt = st.text_input("Amount"); note_content = f"MID: {mid} | Amt: {amt}"; status_opts = ["Request", "Forwarded", "Support", "Done"]
    st.markdown("---"); status = st.selectbox("📌 Trạng thái", status_opts)
    
    if st.button("💾 LƯU & ĐỒNG BỘ", type="primary", use_container_width=True):
        if phone: 
            end_dt = get_company_time(); end_time_str = format_excel_time(end_dt)
            start_dt = st.session_state.ticket_start_time if st.session_state.ticket_start_time else end_dt
            start_time_str = format_excel_time(start_dt); dt_str = start_dt.strftime('%m/%d/%Y')
            data_pack = {'Date_Obj': start_dt, 'Date_Str': dt_str, 'Salon_Name': salon, 'Agent_Name': sel_agent, 'Support_Time': start_time_str, 'End_Time': end_time_str, 'Phone': phone, 'CID': cid, 'Note': note_content, 'Status': status, 'Caller_Info': caller, 'Ticket_Type': ticket_type, 'Training_Note': train_note, 'Card_16_Digits': card_info}
            
            # Xóa cache VICI sau khi lưu
            if 'vici_cache' in st.session_state: del st.session_state.vici_cache
            
            confirm_save_dialog(data_pack)
        else: st.warning("⚠️ Vui lòng nhập ít nhất Số điện thoại.")

elif menu == "🗂️ Tra cứu Master Data":
    st.title("🗂️ Tra cứu Master Data (CID Salon)")
    with st.spinner("Đang tải dữ liệu từ file CID Salon..."): master_data = load_master_db()
    if "Error" in master_data: st.error(f"❌ Lỗi: {master_data['Error']}"); st.info("💡 Check quyền Share file 'CID Salon'.")
    else:
        tab_cid, tab_conf, tab_note, tab_term = st.tabs(["🔎 Tra cứu CID/Tiệm", "🚨 Special (Confirm)", "📝 ISO & General Note", "🔧 Terminal Fix"])
        with tab_cid:
            st.subheader("🔎 Tìm kiếm Thông tin Tiệm")
            df_cid = master_data.get('CID', pd.DataFrame())
            col_s1, col_s2 = st.columns([3, 1])
            search_term = col_s1.text_input("Nhập CID hoặc Tên Tiệm:", placeholder="VD: 07562")
            
            if 'search_result_df' not in st.session_state: st.session_state.search_result_df = None
            
            enable_bot = st.checkbox("Bot Online", value=True)
            
            if st.button("🚀 Tìm kiếm", type="primary"):
                if search_term:
                    st.markdown("##### 📂 1. Kết quả trong Master Data (Local)")
                    if not df_cid.empty:
                        mask = df_cid.astype(str).apply(lambda x: x.str.contains(search_term, case=False, na=False)).any(axis=1)
                        res = df_cid[mask]
                        if not res.empty: st.dataframe(res, use_container_width=True)
                        else: st.warning("⚠️ Không tìm thấy trong file Excel.")
                    
                    if enable_bot:
                        st.markdown("---"); st.markdown("##### 🌐 2. Kết quả mở rộng từ hệ thống (Online)")
                        if is_cloud_mode: st.warning("⚠️ Bot chỉ chạy trên Localhost.")
                        else:
                            with st.spinner(f"🤖 Bot đang tra cứu ngầm..."):
                                st.session_state.search_result_df = run_search_engine(search_term)
                else: st.warning("Vui lòng nhập từ khóa.")

            if st.session_state.search_result_df is not None:
                if isinstance(st.session_state.search_result_df, pd.DataFrame) and not st.session_state.search_result_df.empty:
                    st.success(f"✅ Bot tìm thấy kết quả:"); st.dataframe(st.session_state.search_result_df, use_container_width=True)
                    if st.button("💾 Lưu kết quả vào Database"):
                        success, msg = save_to_master_db_gsheet(st.session_state.search_result_df)
                        if success: 
                            st.success(f"✅ {msg}")
                            st.balloons()
                            st.cache_data.clear()
                        else: st.error(f"❌ {msg}")
                elif isinstance(st.session_state.search_result_df, pd.DataFrame) and st.session_state.search_result_df.empty:
                    st.info("ℹ️ Không tìm thấy trên Web.")

        with tab_conf:
             st.dataframe(master_data.get('CONFIRMATION', pd.DataFrame()), use_container_width=True)
             st.markdown("---"); 
             with st.form("upd_note"):
                 t_cid = st.text_input("CID"); t_note = st.text_area("Note mới")
                 if st.form_submit_button("Lưu Note"):
                     res, msg = update_confirmation_note(t_cid, t_note); st.success(msg) if res else st.error(msg)
        with tab_note:
            df_note = master_data.get('NOTE', pd.DataFrame())
            if not df_note.empty:
                cols = st.columns(2)
                for index, row in df_note.iterrows():
                    title = str(row[0]).strip() if len(row) > 0 else ""; content = str(row[1]).strip() if len(row) > 1 else ""
                    if title and content:
                        with cols[index % 2]: st.markdown(f"""<div class="info-card"><div class="info-title">{title}</div><div class="info-content">{content}</div></div>""", unsafe_allow_html=True)
            else: st.info("Chưa có dữ liệu.")
        with tab_term:
            st.subheader("🔧 Terminal Integrate & Update")
            df_term = master_data.get('TERMINAL', pd.DataFrame())
            if not df_term.empty:
                search_term = st.text_input("🔎 Tìm kiếm lỗi Terminal:", placeholder="Nhập mã lỗi...")
                for index, row in df_term.iterrows():
                    if index == 0: continue
                    term_name = str(row[0]); error_name = str(row[1]); full_title = f"🔌 {term_name} - {error_name}"
                    fix_integrate = str(row[2]); fix_update = str(row[3])
                    if search_term and search_term.lower() not in full_title.lower(): continue
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