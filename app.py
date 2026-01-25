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
import pytz # Thư viện xử lý múi giờ

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
st.set_page_config(page_title="CRM - LLDTEK", page_icon="🏢", layout="wide")

AVAILABLE_SHEETS = ["2-3-4 DAILY REPORT 12/25", "2-3-4 DAILY REPORT 01/26"]
SUP_USERS = ["Nguyễn Trần Phương Loan", "Nguyễn Thị Thùy Dung"]
IGNORED_TAB_NAMES = ["form request", "sheet 4", "sheet4", "request", "request daily", "total", "summary", "copy of", "bản sao"]
KEEP_COLUMNS = ["Date", "Salon_Name", "Agent_Name", "Phone", "CID", "Owner", "Note", "Status", "Issue_Category", "Support_Time", "Ticket_Type", "Caller_Info", "ISO_System", "Training_Note", "Demo_Note", "Card_16_Digits"]

# --- UI/UX PROFESSIONAL CSS ---
st.markdown("""
<style>
    .stApp { font-family: 'Segoe UI', sans-serif; }
    .stTextArea textarea, .stTextInput input { font-family: 'Consolas', monospace; font-weight: 500; border-radius: 5px; }
    
    /* KPI Cards */
    div[data-testid="metric-container"] {
        background-color: #262730; border: 1px solid #41444e; padding: 15px; border-radius: 8px; color: white; box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }
    div[data-testid="metric-container"] label { color: #d0d0d0 !important; }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] { color: #ffffff !important; font-weight: bold; }

    /* TAB STYLE */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background-color: transparent; }
    .stTabs [data-baseweb="tab"] {
        height: 45px; border-radius: 5px; font-weight: 600; font-size: 16px;
        color: #e0e0e0; background-color: #262730; border: 1px solid #41444e;
    }
    .stTabs [aria-selected="true"] {
        background-color: #ff4b4b !important; color: white !important; border-color: #ff4b4b !important;
    }
    
    div[data-testid="stDataFrame"] { border: 1px solid #41444e; border-radius: 5px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. HELPER FUNCTIONS (TIMEZONE HOUSTON)
# ==========================================
def get_company_time():
    """Lấy giờ vận hành theo Houston (US/Central)"""
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    return utc_now.astimezone(pytz.timezone('US/Central'))

def get_current_month_sheet():
    now = get_company_time()
    search_str_1 = now.strftime("%m/%y") 
    search_str_2 = f"{now.month}/{now.strftime('%y')}"
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

# ==========================================
# 3. LOAD DATA
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def load_gsheet_data(selected_sheets):
    if not selected_sheets: return pd.DataFrame()
    try:
        if "gcp_service_account" not in st.secrets: st.error("❌ Thiếu secrets.toml"); return pd.DataFrame()
        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes); gc = gspread.authorize(credentials)
        all_data = []
        progress_bar = st.progress(0); total_steps = len(selected_sheets)
        
        for idx, sheet_name in enumerate(selected_sheets):
            try:
                sh = gc.open(sheet_name); all_tabs = sh.worksheets()
                valid_tabs = [ws for ws in all_tabs if ws.title.lower().strip() not in IGNORED_TAB_NAMES]
                for i, ws in enumerate(valid_tabs):
                    progress_bar.progress((idx + (i / len(valid_tabs))) / total_steps, text=f"Đọc: {sheet_name} > {ws.title}")
                    try:
                        raw = ws.get_all_values(); 
                        if not raw or len(raw) < 2: continue
                        title_low = ws.title.lower()

                        if "16 digits" in title_low:
                            header_idx = 0
                            for r_idx, row in enumerate(raw[:5]):
                                if "date request" in "".join([str(c).lower() for c in row]): header_idx = r_idx; break
                            df_16 = pd.DataFrame(raw[header_idx+1:], columns=clean_headers(raw[header_idx]))
                            rename_map = {"Date Request": "Date", "Name": "Agent_Name", "SALON": "Salon_Name", "Note": "Note", "ISO": "ISO_System", "16 Digits": "Card_16_Digits", "Amount": "Support_Time"}
                            for c in df_16.columns: 
                                if "exp" in c.lower(): rename_map[c] = "Caller_Info"
                            df_16 = safe_process_dataframe(df_16, rename_map); df_16["Ticket_Type"] = "Request (16 Digits)"; df_16["Status"] = "Request"
                            df_16 = df_16[df_16["Salon_Name"].str.strip() != ""]
                            if not df_16.empty: all_data.append(df_16)
                            continue

                        if "training" in title_low:
                            header_idx = -1
                            for r_idx, row in enumerate(raw[:7]):
                                if "iso" in "".join([str(c).lower() for c in row]) and "salon" in "".join([str(c).lower() for c in row]): header_idx = r_idx; break
                            if header_idx != -1:
                                df_train = pd.DataFrame(raw[header_idx+1:], columns=clean_headers(raw[header_idx]))
                                rename_map = {"Date": "Date", "Salon": "Salon_Name", "ISO": "ISO_System", "Name": "Agent_Name", "Time": "Support_Time", "Phone": "Phone", "CID": "CID", "Note": "Note", "Owner": "Caller_Info"}
                                df_train = safe_process_dataframe(df_train, rename_map)
                                if "ISO_System" in df_train.columns: df_train["Training_Note"] = "ISO: " + df_train["ISO_System"]
                                df_train["Ticket_Type"] = "Training"; df_train["Status"] = "Done"
                                df_train = df_train[df_train["Salon_Name"].str.strip() != ""]
                                if not df_train.empty: all_data.append(df_train)
                            continue

                        if len(title_low) < 10 or "/" in title_low:
                            header_idx = -1
                            for r_idx, row in enumerate(raw[:10]):
                                if "salon" in "".join([str(c).lower() for c in row]) and "name" in "".join([str(c).lower() for c in row]): header_idx = r_idx; break
                            if header_idx != -1:
                                df_daily = pd.DataFrame(raw[header_idx+1:], columns=clean_headers(raw[header_idx]))
                                rename_map = {"Salon Name": "Salon_Name", "Name": "Agent_Name", "Time": "Support_Time", "Owner": "Caller_Info", "Phone": "Phone", "CID": "CID", "Note": "Note", "Status": "Status"}
                                df_daily = safe_process_dataframe(df_daily, rename_map)
                                if "Note" in df_daily.columns: df_daily["Issue_Category"] = df_daily["Note"]
                                df_daily = df_daily[df_daily['Salon_Name'].str.strip() != '']; df_daily["Date"] = construct_date_from_context(None, sheet_name, ws.title); df_daily["Ticket_Type"] = "Support"
                                if not df_daily.empty: all_data.append(df_daily)
                    except: continue
            except: pass
        progress_bar.empty()
        if all_data: return pd.concat(all_data, ignore_index=True).replace({'nan': '', 'None': '', 'NaN': ''})
        return pd.DataFrame()
    except Exception as e: st.error(f"Lỗi Load Data: {e}"); return pd.DataFrame()

# ==========================================
# 4. DATABASE & SETTINGS
# ==========================================
def init_db():
    conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (id INTEGER PRIMARY KEY AUTOINCREMENT, Date TEXT, Salon_Name TEXT, Phone TEXT, Issue_Category TEXT, Note TEXT, Status TEXT, Created_At TEXT, CID TEXT, Contact TEXT, Card_16_Digits TEXT, Training_Note TEXT, Demo_Note TEXT, Agent_Name TEXT, Support_Time TEXT, Caller_Info TEXT, ISO_System TEXT, Ticket_Type TEXT)''')
    try: c.execute("ALTER TABLE tickets ADD COLUMN ISO_System TEXT"); c.execute("ALTER TABLE tickets ADD COLUMN Ticket_Type TEXT")
    except: pass
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit(); conn.close()

def insert_ticket(date, salon, phone, issue, note, status, cid, agent, time_str, caller, ticket_type, iso="", train_note="", demo_note="", card_info=""):
    conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
    created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''INSERT INTO tickets (Date, Salon_Name, Phone, Issue_Category, Note, Status, Created_At, CID, Agent_Name, Support_Time, Caller_Info, Ticket_Type, ISO_System, Training_Note, Demo_Note, Card_16_Digits) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', (date, salon, phone, issue, note, status, created, cid, agent, time_str, caller, ticket_type, iso, train_note, demo_note, card_info))
    conn.commit(); conn.close()

def update_ticket(tid, status, note, salon, phone, cid, caller, card_16="", exp_date=""):
    conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
    if card_16 or exp_date:
        combined_card = f"{card_16} | EXP: {exp_date}" if exp_date else card_16
        c.execute('''UPDATE tickets SET Status=?, Note=?, Salon_Name=?, Phone=?, CID=?, Caller_Info=?, Card_16_Digits=? WHERE id=?''', (status, note, salon, phone, cid, caller, combined_card, tid))
    else: c.execute('''UPDATE tickets SET Status=?, Note=?, Salon_Name=?, Phone=?, CID=?, Caller_Info=? WHERE id=?''', (status, note, salon, phone, cid, caller, tid))
    conn.commit(); conn.close()

def save_current_agent_to_db():
    if 'agent_selectbox' in st.session_state:
        selected = st.session_state.agent_selectbox
        conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('current_agent', ?)", (selected,))
        conn.commit(); conn.close()

def get_saved_agent_from_db(agent_list):
    conn = sqlite3.connect('crm_data.db'); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key='current_agent'")
    result = c.fetchone(); conn.close()
    if result and result[0] in agent_list: return agent_list.index(result[0])
    return 0

init_db()

# ==========================================
# 5. GIAO DIỆN CHÍNH
# ==========================================
st.sidebar.title("🏢 CRM - LLDTEK")
if st.sidebar.button("🔄 Cập nhật Dữ liệu Mới"): st.cache_data.clear(); st.rerun()

default_sheets = get_current_month_sheet()
sheets = st.sidebar.multiselect("Dữ liệu:", AVAILABLE_SHEETS, default=default_sheets)
if not sheets: st.warning("Vui lòng chọn file dữ liệu!"); st.stop()
df = load_gsheet_data(sheets)

st.sidebar.markdown("---")
agents = ["Nguyễn Trần Phương Loan", "Nguyễn Hương Giang", "Nguyễn Thị Phương Anh", "Võ Ngọc Tuấn", "Nguyễn Thị Thùy Dung", "Hồ Ngọc Mỹ Phượng", "Phạm Ngọc Chiến", "Trương Anh Đạt", "Dương Nhật Tiến", "Lưu Schang Sanh", "Lê Thị Tuyết Anh", "Đinh Thị Liên Chi", "Nguyễn Thị Anh Thư"]
all_agents = [""] + agents
default_index = get_saved_agent_from_db(all_agents)
sel_agent = st.sidebar.selectbox("Nhân viên:", all_agents, index=default_index, key="agent_selectbox", on_change=save_current_agent_to_db)

menu_options = ["🆕 New Ticket", "🔍 Search & History"]
if sel_agent in SUP_USERS: menu_options.append("📊 Dashboard (SUP Only)")
menu = st.sidebar.selectbox("Menu", menu_options)

# --- NEW TICKET ---
if menu == "🆕 New Ticket":
    st.title("🆕 Tạo Ticket Mới")
    
    # [HIỂN THỊ GIỜ HOUSTON ĐỂ STAFF BIẾT]
    houston_now = get_company_time()
    st.caption(f"🕒 Giờ Houston: {houston_now.strftime('%H:%M:%S %p | %d/%m/%Y')}")
    
    qp = st.query_params; def_phone = qp.get("phone", ""); def_salon = qp.get("salon", ""); def_cid = qp.get("cid", ""); def_owner = qp.get("owner", "")
    if def_phone: st.success(f"📞 VICI CONNECTED: **{def_salon}** - {def_phone}")
    st.markdown("---")
    if not sel_agent: st.warning("⚠️ Vui lòng chọn Tên Nhân Viên trước!"); st.stop()
    ticket_type = st.radio("Chọn loại công việc:", ["Report (Hỗ trợ)", "Training", "Demo", "SMS Refill (Mua gói)", "SMS Drafting (Soạn tin)", "Request (16 Digits)"], horizontal=True)
    st.markdown("---")
    with st.form("new_ticket_form", clear_on_submit=False): 
        c1, c2, c3 = st.columns(3); d = c1.date_input("📅 Ngày Report", get_company_time()); salon = c2.text_input("🏠 Tên Tiệm *", value=def_salon); cid = c3.text_input("🆔 CID", value=def_cid)
        c4, c5 = st.columns(2); phone = c4.text_input("📞 Phone *", value=def_phone); caller = c5.text_input("👤 Owner / Người liên hệ", value=def_owner)
        iso_val, train_note, demo_note, card_info, note_content = "", "", "", "", ""; status_opts = ["Pending", "Done", "No Answer"]
        if ticket_type == "Report (Hỗ trợ)":
            t = st.time_input("⏰ Giờ Support", get_company_time()); note_content = st.text_area("Chi tiết vấn đề *", height=150)
        elif ticket_type == "Training":
            col_iso, col_other = st.columns([1, 1]); iso_opt = col_iso.selectbox("ISO System", ["Spoton", "1ST", "TMS", "TMDSpoton", "Khác"]); iso_val = iso_opt if iso_opt != "Khác" else col_other.text_input("Nhập tên ISO khác"); t = st.time_input("⏰ Giờ bắt đầu", get_company_time()); 
            with st.expander("Nội dung Training", expanded=True):
                topics = st.multiselect("Đã train:", ["Mainscreen", "APPT", "Guest List", "Payment", "GC", "Report", "Settings"]); detail = st.text_area("Chi tiết:"); train_note = f"Topics: {', '.join(topics)} | Note: {detail}"
            note_content = st.text_area("Ghi chú chung *", height=100)
        elif ticket_type == "Demo":
            t = st.time_input("⏰ Giờ Demo", get_company_time()); demo_note = st.text_input("Mục đích Demo"); note_content = st.text_area("Diễn biến Demo *", height=150)
        elif ticket_type == "SMS Refill (Mua gói)":
            t = st.time_input("⏰ Giờ", get_company_time()); st.info("💰 Khách mua thêm gói SMS")
            iso_sms = st.selectbox("ISO System", ["Spoton", "1ST", "TMS", "TMDSpoton", "MAC", "Khác"]); 
            if iso_sms == "MAC": st.error("❌ ISO MAC không hỗ trợ mua thêm SMS!")
            else:
                pkg = st.radio("Chọn gói:", ["$50 (2000 SMS)", "$100 (5000 SMS)", "$200 (11000 SMS)", "$300 (17500 SMS)"]); c_card, c_exp = st.columns(2); card_num = c_card.text_input("Card Number (16 số)"); card_exp = c_exp.text_input("EXP Date"); note_content = f"REFILL SMS: Gói {pkg}. Đã xin thông tin thẻ."; card_info = f"Pkg: {pkg} | Card: {card_num} | Exp: {card_exp}"
        elif ticket_type == "SMS Drafting (Soạn tin)":
            t = st.time_input("⏰ Giờ", get_company_time()); st.info("📝 Công cụ soạn thảo & theo dõi trạng thái SMS"); process_note = st.text_area("Ghi chú diễn biến / Yêu cầu gốc của khách (Thoải mái nhập):", height=80, placeholder="Ví dụ: Khách muốn gửi tin KM nhưng nội dung quá dài..."); st.markdown("---"); st.subheader("Nội dung SMS Chốt (Gửi đi)"); sms_count = st.radio("Số lượng tin nhắn:", ["1 Tin nhắn", "2 Tin nhắn"], horizontal=True)
            def check_len(text): return f"⚠️ {len(text)}/135 (Quá dài!)" if len(text) > 135 else f"✅ {len(text)}/135"
            draft1 = st.text_area("Nội dung SMS 1 (Chốt):", height=80); st.caption(check_len(draft1)); draft2 = ""; 
            if sms_count == "2 Tin nhắn": draft2 = st.text_area("Nội dung SMS 2 (Chốt):", height=80); st.caption(check_len(draft2))
            sms_step = st.selectbox("Tiến độ:", ["B1: Nhận yêu cầu / Soạn thảo (Pending)", "B2: Đã gửi cho Tiệm Confirm (Pending)", "B3: Tiệm đã OK - Gửi Group SUP (Pending)", "B4: SUP đã gửi xong - Báo khách (Done)"]); final_content = f"[SMS {sms_count}] {draft1}"; 
            if draft2: final_content += f" | {draft2}"; note_content = f"TIẾN ĐỘ: {sms_step}\nDIỄN BIẾN: {process_note}\nNỘI DUNG CHỐT: {final_content}"; status_opts = ["Done"] if "Done" in sms_step else ["Pending"]
        elif ticket_type == "Request (16 Digits)":
            st.info("📌 Form yêu cầu lấy thông tin thẻ / Refund / Charge"); t = st.time_input("⏰ Giờ", get_company_time()); r1, r2, r3 = st.columns(3); mid = r1.text_input("MID"); iso_req = r2.text_input("ISO System"); tkt_date = r3.date_input("Ngày của Ticket (Transaction Date)"); r4, r5, r6 = st.columns(3); card_type = r4.selectbox("Loại thẻ", ["Visa", "MC", "Discover", "Amex", "Debit", "Khác"]); last_4 = r5.text_input("Card Last 4"); amount = r6.text_input("Amount ($)"); r7, r8 = st.columns(2); app_code = r7.text_input("App Code"); tkt_no = r8.text_input("Ticket No."); issue_type = st.selectbox("Loại vấn đề:", ["Extra Due", "Missed Tip", "Void Mistake", "Xin thông tin thẻ", "Khác"]); extra_note = st.text_area("Ghi chú thêm:", height=80); note_content = (f"MID: {mid} | Salon: {salon} | Date Tkt: {tkt_date} | Card: {card_type}-{last_4} | Amt: ${amount} | Code: {app_code} | Tkt#: {tkt_no} | Type: {issue_type} | ISO: {iso_req} | Note: {extra_note}"); status_opts = ["Request", "Forwarded by SUP", "Pending", "Done"]
        st.markdown("---"); status = st.selectbox("📌 Trạng thái", status_opts)
        if st.form_submit_button("💾 LƯU TICKET", type="primary", use_container_width=True):
            if salon and phone:
                dt = datetime.combine(d, t); insert_ticket(dt.strftime('%m/%d/%Y'), salon, phone, note_content, note_content, status, cid, sel_agent, dt.strftime('%H:%M:%S'), caller, ticket_type, iso_val, train_note, demo_note, card_info); st.success(f"✅ Đã lưu ticket **{ticket_type}** cho: **{salon}**")
            else: st.warning("⚠️ Vui lòng điền đủ Tên Tiệm và Phone.")

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
            @st.dialog("📝 CẬP NHẬT TICKET")
            def edit_ticket(row):
                st.info(f"🏠 {row.get('Salon_Name')} | {row.get('Ticket_Type')}"); st.text_area("Nội dung hiện tại (Read-only):", value=str(row.get('Note')), height=100, disabled=True); new_card, new_exp = "", ""; 
                if "Request" in str(row.get('Ticket_Type')):
                    st.markdown("---"); st.warning("💳 **KHU VỰC SUP NHẬP THÔNG TIN THẺ**"); c1, c2 = st.columns(2); current_card = str(row.get('Card_16_Digits', '')); curr_num = current_card.split('|')[0].strip() if '|' in current_card else current_card; new_card = c1.text_input("16 Số Thẻ (Full)", value=curr_num); new_exp = c2.text_input("EXP Date")
                st.markdown("---"); new_status = st.selectbox("Trạng thái mới", ["Pending", "Done", "No Answer", "Request", "Forwarded by SUP"], index=0); new_note = st.text_area("Cập nhật / Bổ sung Ghi chú:", value=str(row.get('Note')), height=150)
                if st.button("Lưu Thay Đổi"): update_ticket(row.get('id'), new_status, new_note, row.get('Salon_Name'), row.get('Phone'), row.get('CID'), row.get('Caller_Info'), new_card, new_exp); st.success("Đã cập nhật!"); st.rerun()
            event = st.dataframe(df_search[final_cols], hide_index=True, use_container_width=True, selection_mode="single-row", on_select="rerun", column_config={"Note": st.column_config.TextColumn("Nội dung", width="large")}); 
            if len(event.selection.rows) > 0: edit_ticket(df_search.iloc[event.selection.rows[0]])
        else: st.info("Không tìm thấy kết quả.")

# --- DASHBOARD NÂNG CẤP (SUP ONLY) ---
elif menu == "📊 Dashboard (SUP Only)":
    st.title("📊 Trung Tâm Điều Hành (Deep Analytics)")
    
    # [CHECKPOINT] Kiểm tra và hiển thị giờ hiện tại đang dùng
    company_now = get_company_time()
    st.toast(f"📍 Đang sử dụng múi giờ Houston (US/Central): {company_now.strftime('%H:%M - %d/%m')}", icon="🕒")

    if not df.empty:
        df_chart = df.copy()
        if 'Date' in df_chart.columns:
            df_chart['Date_Obj'] = pd.to_datetime(df_chart['Date'], errors='coerce')
            df_chart = df_chart.dropna(subset=['Date_Obj'])
        
        # BỘ LỌC DỮ LIỆU
        with st.expander("📅 BỘ LỌC DỮ LIỆU", expanded=True):
            col_filter, col_range = st.columns([1, 2])
            filter_mode = col_filter.radio("Thời gian:", ["Hôm nay", "Tuần này", "Tháng này"], horizontal=True)
            
            # [FIX TIMEZONE V30] Sử dụng giờ của Công Ty (Houston)
            today_company = company_now.date()
            
            if filter_mode == "Hôm nay": d_start, d_end = today_company, today_company
            elif filter_mode == "Tuần này": d_start, d_end = today_company - timedelta(days=today_company.weekday()), today_company
            else: d_start, d_end = today_company.replace(day=1), today_company
            
            mask = (df_chart['Date_Obj'].dt.date >= d_start) & (df_chart['Date_Obj'].dt.date <= d_end)
            df_filtered = df_chart.loc[mask].copy()

        if df_filtered.empty:
            st.warning(f"⚠️ Không có dữ liệu trong khoảng {d_start} đến {d_end} (Giờ Houston).")
        else:
            # TABS ANALYTICS
            tab1, tab2, tab3 = st.tabs(["📈 Tổng Quan & KPI", "🚨 Phân Tích & Top Tiệm", "🏆 Hiệu Suất Team"])

            # --- TAB 1: KPI & TREND ---
            with tab1:
                total = len(df_filtered)
                df_filtered['Status_Norm'] = df_filtered['Status'].astype(str).str.lower()
                done = len(df_filtered[df_filtered['Status_Norm'].str.contains('done')])
                pending = len(df_filtered[df_filtered['Status_Norm'].str.contains('pending')])
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Tổng Ticket", total)
                c2.metric("Đã Xử Lý (Done)", done, f"{(done/total*100):.1f}% Rate")
                c3.metric("Đang Chờ (Pending)", pending, delta_color="inverse")
                c4.metric("Request Thẻ", len(df_filtered[df_filtered['Status_Norm'].str.contains('request')]))
                
                st.markdown("---")
                daily_counts = df_filtered.groupby(df_filtered['Date_Obj'].dt.date).size().reset_index(name='Tickets')
                fig_line = px.line(daily_counts, x='Date_Obj', y='Tickets', markers=True, 
                                   title="📉 Xu hướng Ticket theo ngày", template="plotly_dark")
                fig_line.update_layout(xaxis_title="Ngày", yaxis_title="Số lượng")
                st.plotly_chart(fig_line, use_container_width=True)

            # --- TAB 2: VẤN ĐỀ & TOP SALON (NEW V30) ---
            with tab2:
                col_salon, col_issue = st.columns([1, 1])
                
                # 1. [NEW] TOP SALON GỌI NHIỀU NHẤT
                with col_salon:
                    st.markdown("### 🏪 Top 10 Tiệm Gọi Nhiều Nhất")
                    if 'Salon_Name' in df_filtered.columns:
                        top_salons = df_filtered['Salon_Name'].value_counts().nlargest(10).reset_index()
                        top_salons.columns = ['Tên Tiệm', 'Số lần gọi']
                        
                        st.dataframe(
                            top_salons,
                            hide_index=True,
                            use_container_width=True,
                            column_config={
                                "Số lần gọi": st.column_config.ProgressColumn(
                                    "Cường độ",
                                    format="%d",
                                    min_value=0,
                                    max_value=int(top_salons['Số lần gọi'].max()),
                                )
                            }
                        )

                # 2. TOP VẤN ĐỀ
                with col_issue:
                    st.markdown("### 📋 Top Vấn Đề (Đã gộp nhóm)")
                    if 'Issue_Category' in df_filtered.columns:
                        issues = df_filtered['Issue_Category'].fillna("Khác").astype(str).str.strip()
                        top_issues = issues.value_counts().nlargest(10).reset_index()
                        top_issues.columns = ['Vấn đề', 'Số lượng']
                        
                        fig_bar = px.bar(top_issues, x='Số lượng', y='Vấn đề', orientation='h', 
                                         text='Số lượng', color='Số lượng',
                                         color_continuous_scale='Redor', template="plotly_dark")
                        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'})
                        st.plotly_chart(fig_bar, use_container_width=True)

            # --- TAB 3: HIỆU SUẤT NHÂN VIÊN ---
            with tab3:
                st.markdown("### 🏆 Bảng Xếp Hạng Năng Suất")
                if 'Agent_Name' in df_filtered.columns:
                    agent_stats = df_filtered['Agent_Name'].value_counts().reset_index()
                    agent_stats.columns = ['Nhân viên', 'Tổng Ticket']
                    pending_stats = df_filtered[df_filtered['Status_Norm'].str.contains('pending')]['Agent_Name'].value_counts().reset_index()
                    pending_stats.columns = ['Nhân viên', 'Pending']
                    final_stats = pd.merge(agent_stats, pending_stats, on='Nhân viên', how='left').fillna(0)
                    final_stats['Pending'] = final_stats['Pending'].astype(int)
                    
                    st.dataframe(
                        final_stats,
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Tổng Ticket": st.column_config.ProgressColumn("Khối lượng công việc", format="%d", min_value=0, max_value=int(final_stats['Tổng Ticket'].max())),
                            "Pending": st.column_config.NumberColumn("Đang nợ (Pending)", format="%d ⚠️")
                        }
                    )

    else: st.info("Vui lòng chọn file dữ liệu.")