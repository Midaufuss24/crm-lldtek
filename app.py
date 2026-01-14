import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials
import admin_page
import time

# --- CẤU HÌNH ---
AVAILABLE_SHEETS = [
    "TOTAL REPORT 2025",
    "TOTAL REPORT 2026",
    "2-3-4 DAILY REPORT 12/25",
    "2-3-4 DAILY REPORT 01/26"
]

st.set_page_config(page_title="CRM - LLDTEK", page_icon="🏢", layout="wide")

# --- CSS ---
st.markdown("""
<style>
    .stTextArea textarea { font-family: 'Consolas', monospace; }
    .stTextInput input { font-weight: bold; }
    div[data-testid="stDialog"] div[role="dialog"] { width: 80vw !important; max-width: 1000px !important; }
</style>
""", unsafe_allow_html=True)

# --- HÀM FORMAT NGÀY (MM/DD/YYYY) ---
def format_date_custom(val):
    if pd.isna(val) or str(val).strip() == "": return ""
    val_str = str(val).strip()
    try:
        # Thử parse datetime
        dt = pd.to_datetime(val_str, dayfirst=False, errors='coerce')
        if pd.isna(dt):
            dt = pd.to_datetime(val_str, dayfirst=True, errors='coerce')
        
        if not pd.isna(dt):
            return dt.strftime('%m/%d/%Y') # Chuẩn Mỹ: Tháng/Ngày/Năm
        return val_str
    except:
        return val_str

# --- HÀM LOAD DATA (LOGIC TÁCH BIỆT TOTAL vs DAILY) ---
@st.cache_data(ttl=60, show_spinner=False)
def load_gsheet_data(selected_sheets):
    if not selected_sheets: return pd.DataFrame()
    
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("❌ Thiếu secrets.toml")
            return pd.DataFrame()

        scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
        credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
        gc = gspread.authorize(credentials)
        
        all_data = []
        
        for sheet_name in selected_sheets:
            try:
                sh = gc.open(sheet_name)
                all_tabs = sh.worksheets()
                
                # --- PHÂN LOẠI FILE ---
                is_total_file = "TOTAL REPORT" in sheet_name.upper()
                
                # Xác định tab bắt đầu (Daily thường bỏ 2 tab đầu)
                start_idx = 0
                if not is_total_file and len(all_tabs) >= 3:
                    start_idx = 2

                for i in range(start_idx, len(all_tabs)):
                    ws = all_tabs[i]
                    for attempt in range(3):
                        try:
                            time.sleep(1.0 + attempt)
                            raw = ws.get_all_values()
                            if not raw: break

                            # --- TÌM HEADER ---
                            header_idx = -1
                            for r_idx, row in enumerate(raw[:15]):
                                row_str = " ".join([str(c).lower() for c in row])
                                if "salon" in row_str and ("name" in row_str or "tên" in row_str):
                                    header_idx = r_idx
                                    break
                            
                            if header_idx != -1 and len(raw) > header_idx + 1:
                                orig_headers = raw[header_idx]
                                uniq_headers = []
                                seen = {}
                                for h in orig_headers:
                                    h = str(h).strip()
                                    if h in seen:
                                        seen[h] += 1
                                        uniq_headers.append(f"{h}_{seen[h]}")
                                    else:
                                        seen[h] = 0
                                        uniq_headers.append(h)

                                df_part = pd.DataFrame(raw[header_idx+1:], columns=uniq_headers)
                                
                                # --- MAP TÊN CỘT ---
                                rename_map = {}
                                for col in df_part.columns:
                                    c_low = col.lower()
                                    # LOGIC QUAN TRỌNG:
                                    # Nếu là File Total -> Cột STT là Date
                                    # Nếu là File Daily -> Cột STT kệ nó (không map vào Date)
                                    if "stt" in c_low:
                                        if is_total_file: rename_map[col] = "Date"
                                        
                                    elif "salon" in c_low and "name" in c_low: rename_map[col] = "Salon_Name"
                                    elif "name" in c_low and "salon" not in c_low: rename_map[col] = "Agent_Name"
                                    elif "time" in c_low: rename_map[col] = "Support_Time"
                                    elif "owner" in c_low: rename_map[col] = "Caller_Info"
                                    elif "phone" in c_low: rename_map[col] = "Phone"
                                    elif "cid" in c_low: rename_map[col] = "CID"
                                    elif "note" in c_low: rename_map[col] = "Note"
                                    elif "status" in c_low: rename_map[col] = "Status"
                                
                                df_part = df_part.rename(columns=rename_map)
                                
                                if "Issue_Category" not in df_part.columns and "Note" in df_part.columns:
                                    df_part["Issue_Category"] = df_part["Note"]

                                df_part = df_part.astype(str)
                                
                                if 'Salon_Name' in df_part.columns:
                                    df_part = df_part[df_part['Salon_Name'].str.strip() != '']
                                    
                                    # --- XỬ LÝ DATE ---
                                    # 1. Nếu không có cột Date (File Daily), lấy từ tên Tab
                                    if "Date" not in df_part.columns:
                                        # Lấy năm từ tên file (2025, 2026)
                                        year_suffix = "/2025"
                                        if "2026" in sheet_name: year_suffix = "/2026"
                                        
                                        # Nếu tên tab đã có năm (VD: 01/26) thì giữ nguyên
                                        # Nếu tên tab chỉ là ngày (VD: 1, 2, 13) thì thêm tháng/năm
                                        tab_name = ws.title.strip()
                                        if len(tab_name) <= 2 and tab_name.isdigit():
                                            # Giả định lấy tháng từ tên file (VD: 01/26 -> Tháng 1)
                                            # Logic đơn giản: Lấy nguyên tên tab ghép với suffix năm
                                            # Để an toàn, ta lấy tên tab làm ngày luôn
                                            df_part["Date"] = f"{tab_name}{year_suffix}" 
                                        else:
                                            df_part["Date"] = tab_name

                                    # 2. Format lại cột Date
                                    df_part["Date"] = df_part["Date"].apply(format_date_custom)
                                    
                                    all_data.append(df_part)
                            break
                        except: continue
            except: pass

        if all_data:
            final_df = pd.concat(all_data, ignore_index=True)
            return final_df.replace({'nan': '', 'None': '', 'NaN': ''})
        return pd.DataFrame()

    except Exception as e:
        st.error(f"Lỗi: {e}")
        return pd.DataFrame()

# --- DB FUNCTIONS ---
def init_db():
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        Date TEXT, Salon_Name TEXT, Phone TEXT, Issue_Category TEXT, Note TEXT, 
        Status TEXT, Created_At TEXT, CID TEXT, Contact TEXT, Card_16_Digits TEXT, 
        Training_Note TEXT, Demo_Note TEXT, Agent_Name TEXT, Support_Time TEXT, Caller_Info TEXT)''')
    conn.commit()
    conn.close()

def insert_ticket(date, salon, phone, issue, note, status, cid, contact, card, train, demo, agent, time_str, caller):
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''INSERT INTO tickets (Date, Salon_Name, Phone, Issue_Category, Note, Status, Created_At,
                CID, Contact, Card_16_Digits, Training_Note, Demo_Note, Agent_Name, Support_Time, Caller_Info)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                (date, salon, phone, issue, note, status, created, cid, contact, card, train, demo, agent, time_str, caller))
    conn.commit()
    conn.close()

def update_ticket(tid, status, note, salon, phone, cid, caller, train, demo):
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute('''UPDATE tickets SET Status=?, Note=?, Salon_Name=?, Phone=?, CID=?, Caller_Info=?, Training_Note=?, Demo_Note=? WHERE id=?''',
              (status, note, salon, phone, cid, caller, train, demo, tid))
    conn.commit()
    conn.close()

# --- SEARCH HELPER ---
def search_tickets(term, filter_type, sheets):
    df = load_gsheet_data(sheets)
    if df.empty: return df
    
    term = term.lower()
    # Tìm kiếm trên các cột hiển thị
    cols = ['Salon_Name', 'Phone', 'CID', 'Agent_Name', 'Date']
    valid = [c for c in cols if c in df.columns]
    
    mask = pd.Series([False]*len(df))
    for c in valid: mask |= df[c].astype(str).str.lower().str.contains(term, na=False)
    
    df = df[mask].copy()
    if filter_type == 'Training' and 'Training_Note' in df.columns:
        df = df[df['Training_Note'].str.strip() != '']
    elif filter_type == 'Demo' and 'Demo_Note' in df.columns:
        df = df[df['Demo_Note'].str.strip() != '']
        
    # Tạo ID giả để selection hoạt động
    df = df.reset_index(drop=True)
    if 'id' not in df.columns: df.insert(0, 'id', range(1, len(df)+1))
    return df

# --- INIT ---
init_db()

# --- SIDEBAR ---
st.sidebar.title("🏢 CRM - LLDTEK")

if st.sidebar.button("🔄 Xóa Cache & Tải lại"):
    st.cache_data.clear()
    st.rerun()

sheets = st.sidebar.multiselect("Dữ liệu tháng:", AVAILABLE_SHEETS, default=[AVAILABLE_SHEETS[-1]])
if not sheets: st.stop()

st.sidebar.markdown("---")
agents = ["Nguyễn Trần Phương Loan", "Nguyễn Hương Giang", "Nguyễn Thị Phương Anh", "Võ Ngọc Tuấn", "Nguyễn Thị Thùy Dung", "Hồ Ngọc Mỹ Phượng", "Phạm Ngọc Chiến", "Trương Anh Đạt", "Dương Nhật Tiến", "Lưu Schang Sanh", "Lê Thị Tuyết Anh", "Đinh Thị Liên Chi", "Nguyễn Thị Anh Thư"]
sel_agent = st.sidebar.selectbox("Nhân viên:", [""] + agents)

is_admin = st.sidebar.checkbox("Login Manager")
auth = False
if is_admin:
    if st.sidebar.text_input("Password:", type="password") == "admin123": auth = True

menu = st.sidebar.selectbox("Menu", ["🆕 New Ticket", "🔍 Search & History", "📊 Dashboard"]) if not auth else "Admin"

# --- PAGES ---

if menu == "Admin":
    df = load_gsheet_data(sheets)
    if not df.empty: admin_page.show_admin_dashboard(df)

elif menu == "🆕 New Ticket":
    st.title("🆕 Tạo Ticket Mới")
    st.markdown("---")
    
    with st.form("new_ticket", clear_on_submit=True):
        c1, c2, _ = st.columns([1,1,2])
        d = c1.date_input("📅 Ngày", datetime.now())
        t = c2.time_input("⏰ Giờ", datetime.now())
        salon = st.text_input("🏠 Tên Tiệm *")
        cc1, cc2, cc3 = st.columns(3)
        cid = cc1.text_input("🆔 CID")
        phone = cc2.text_input("📞 Phone *")
        caller = cc3.text_input("👤 Owner")
        issue = st.text_area("📄 Ghi chú / Vấn đề *", height=150)
        ct1, ct2, ct3 = st.columns(3)
        train = ct1.text_input("🎓 Training")
        demo = ct2.text_input("🎬 Demo")
        status = ct3.selectbox("📌 Trạng thái", ["Pending", "Done", "No Answer"])
        
        if st.form_submit_button("💾 LƯU TICKET", type="primary", use_container_width=True):
            if salon and phone and issue and sel_agent:
                dt = datetime.combine(d, t)
                date_str = dt.strftime('%m/%d/%Y') # Format chuẩn
                insert_ticket(date_str, salon, phone, issue, issue, status, cid, None, None, train, demo, sel_agent, dt.strftime('%H:%M:%S'), caller)
                st.success(f"✅ Đã lưu: {salon}")
            else: st.warning("⚠️ Thiếu thông tin bắt buộc")

elif menu == "🔍 Search & History":
    st.title("🔍 Tra cứu & Lịch sử")
    term = st.text_input("🔎 Nhập từ khóa:", placeholder="Tên tiệm, SĐT, CID...")
    filter_type = st.radio("Lọc:", ["Tất cả", "Training", "Demo"], horizontal=True)
    
    if term:
        df_search = search_tickets(term, None if filter_type=="Tất cả" else filter_type, sheets)
        
        if not df_search.empty:
            # Cấu hình cột hiển thị
            cols = ['Date','Agent_Name','Support_Time','CID','Salon_Name','Phone','Caller_Info','Note','Status']
            final_cols = [c for c in cols if c in df_search.columns]
            
            # --- POPUP EDIT ---
            @st.dialog("📝 CHỈNH SỬA TICKET")
            def edit_ticket_dialog(row):
                with st.form("edit_form"):
                    c1, c2 = st.columns([2, 1])
                    c1.info(f"🏠 **{row.get('Salon_Name')}**")
                    c2.caption(f"📅 {row.get('Date')} | ⏰ {row.get('Support_Time')}")
                    
                    new_salon = st.text_input("Tên Tiệm", value=row.get('Salon_Name', ''))
                    cc1, cc2, cc3 = st.columns(3)
                    new_cid = cc1.text_input("CID", value=row.get('CID', ''))
                    new_phone = cc2.text_input("Phone", value=row.get('Phone', ''))
                    new_caller = cc3.text_input("Owner", value=row.get('Caller_Info', ''))
                    new_note = st.text_area("Ghi chú (Notes)", value=row.get('Note', ''), height=150)
                    ct1, ct2, ct3 = st.columns(3)
                    new_train = ct1.text_input("Training", value=row.get('Training_Note', ''))
                    new_demo = ct2.text_input("Demo", value=row.get('Demo_Note', ''))
                    
                    curr_st = str(row.get('Status', 'Pending')).strip().capitalize()
                    valid_st = ["Pending", "Done", "No Answer"]
                    if curr_st not in valid_st: curr_st = "Pending"
                    idx = valid_st.index(curr_st)
                    new_status = ct3.selectbox("Trạng thái", valid_st, index=idx)
                    
                    if st.form_submit_button("💾 CẬP NHẬT"):
                        update_ticket(row.get('id'), new_status, new_note, new_salon, new_phone, new_cid, new_caller, new_train, new_demo)
                        st.success("Đã cập nhật!")
                        st.rerun()

            event = st.dataframe(
                df_search[final_cols],
                hide_index=True,
                use_container_width=True,
                selection_mode="single-row",
                on_select="rerun",
                column_config={
                    "Date": st.column_config.TextColumn("Ngày (MM/DD/YYYY)"), # Ép hiển thị text
                    "Note": st.column_config.TextColumn("Note", width="large"),
                    "Agent_Name": "Nhân viên",
                    "Caller_Info": "Owner"
                }
            )
            if len(event.selection.rows) > 0:
                edit_ticket_dialog(df_search.iloc[event.selection.rows[0]])
        else:
            st.info("Không tìm thấy kết quả.")

elif menu == "📊 Dashboard":
    st.title("📊 Tổng Quan Hoạt Động")
    st.info("⚠️ Dashboard đang bảo trì để tập trung vào tính năng Tra cứu.")