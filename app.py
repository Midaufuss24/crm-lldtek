import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import admin_page
import services

# Google Sheets configuration
AVAILABLE_SHEETS = [
    "TOTAL REPORT 2025",
    "TOTAL REPORT 2026",
    "2-3-4 DAILY REPORT 12/25",
    "2-3-4 DAILY REPORT 01/26"
]

# Helper function to load data from Google Sheets
def load_gsheet_data(selected_sheets):
    """Load data from Google Sheets with error handling"""
    if not selected_sheets or len(selected_sheets) == 0:
        return pd.DataFrame()  # Return empty DataFrame if no sheets selected
    
    try:
        return services.load_data_from_gsheet(selected_sheets)
    except Exception as e:
        return pd.DataFrame()  # Return empty DataFrame on error

# Cấu hình trang
st.set_page_config(
    page_title="CRM - LLDTEK",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Database functions
def init_db():
    """Khởi tạo database và bảng tickets"""
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Date TEXT NOT NULL,
            Salon_Name TEXT NOT NULL,
            Phone TEXT NOT NULL,
            Issue_Category TEXT NOT NULL,
            Note TEXT,
            Status TEXT NOT NULL DEFAULT 'Pending',
            Created_At TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()
    # Chạy migration để thêm các cột mới
    migrate_db()

def migrate_db():
    """Thêm các cột mới vào bảng tickets nếu chưa có"""
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    
    # Kiểm tra và thêm các cột mới
    columns_to_add = [
        ('CID', 'TEXT'),
        ('Contact', 'TEXT'),
        ('Card_16_Digits', 'TEXT'),
        ('Training_Note', 'TEXT'),
        ('Demo_Note', 'TEXT'),
        ('Agent_Name', 'TEXT'),
        ('Support_Time', 'TEXT'),
        ('Caller_Info', 'TEXT')
    ]
    
    for column_name, column_type in columns_to_add:
        try:
            # Kiểm tra xem cột đã tồn tại chưa
            c.execute(f"PRAGMA table_info(tickets)")
            columns = [row[1] for row in c.fetchall()]
            
            if column_name not in columns:
                # Thêm cột mới nếu chưa có
                c.execute(f'ALTER TABLE tickets ADD COLUMN {column_name} {column_type}')
                conn.commit()
        except sqlite3.OperationalError as e:
            # Bỏ qua lỗi nếu cột đã tồn tại
            if "duplicate column name" not in str(e).lower():
                print(f"Warning: {e}")
    
    conn.close()

def insert_ticket(date, salon_name, phone, issue_category, note, status='Pending', 
                  cid=None, contact=None, card_16_digits=None, training_note=None, demo_note=None,
                  agent_name=None, support_time=None, caller_info=None):
    """Thêm ticket mới vào database"""
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('''
        INSERT INTO tickets (Date, Salon_Name, Phone, Issue_Category, Note, Status, Created_At,
                            CID, Contact, Card_16_Digits, Training_Note, Demo_Note,
                            Agent_Name, Support_Time, Caller_Info)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (date, salon_name, phone, issue_category, note, status, created_at,
          cid, contact, card_16_digits, training_note, demo_note,
          agent_name, support_time, caller_info))
    conn.commit()
    conn.close()

def get_ticket_by_id(ticket_id, df_search_results=None, selected_sheets=None):
    """Lấy thông tin ticket theo ID từ Google Sheets hoặc search results"""
    # If search results DataFrame is provided, use it (for compatibility with search)
    if df_search_results is not None and not df_search_results.empty:
        ticket_row = df_search_results[df_search_results['id'] == ticket_id]
        if not ticket_row.empty:
            row = ticket_row.iloc[0]
            return {
                'id': int(row.get('id', ticket_id)),
                'Date': row.get('Date', ''),
                'Salon_Name': row.get('Salon_Name', ''),
                'Phone': row.get('Phone', ''),
                'Issue_Category': row.get('Issue_Category', ''),
                'Note': row.get('Note', ''),
                'Status': row.get('Status', ''),
                'Created_At': row.get('Created_At', ''),
                'CID': row.get('CID', None),
                'Contact': row.get('Contact', None),
                'Card_16_Digits': row.get('Card_16_Digits', None),
                'Training_Note': row.get('Training_Note', None),
                'Demo_Note': row.get('Demo_Note', None),
                'Agent_Name': row.get('Agent_Name', None),
                'Support_Time': row.get('Support_Time', None),
                'Caller_Info': row.get('Caller_Info', None)
            }
    
    # Use selected_sheets from session state if not provided
    if selected_sheets is None:
        selected_sheets = st.session_state.get('sheet_selection', [])
    
    # Fallback: Try to load from Google Sheets
    df = load_gsheet_data(selected_sheets)
    
    if not df.empty and ticket_id <= len(df):
        # Use ticket_id as index (since we generate sequential IDs in search)
        try:
            row = df.iloc[ticket_id - 1]  # ticket_id is 1-based
            return {
                'id': ticket_id,
                'Date': row.get('Date', ''),
                'Salon_Name': row.get('Salon_Name', ''),
                'Phone': row.get('Phone', ''),
                'Issue_Category': row.get('Issue_Category', ''),
                'Note': row.get('Note', ''),
                'Status': row.get('Status', ''),
                'Created_At': row.get('Created_At', ''),
                'CID': row.get('CID', None),
                'Contact': row.get('Contact', None),
                'Card_16_Digits': row.get('Card_16_Digits', None),
                'Training_Note': row.get('Training_Note', None),
                'Demo_Note': row.get('Demo_Note', None),
                'Agent_Name': row.get('Agent_Name', None),
                'Support_Time': row.get('Support_Time', None),
                'Caller_Info': row.get('Caller_Info', None)
            }
        except (IndexError, KeyError):
            pass
    
    return None

def update_ticket(ticket_id, status, note):
    """Cập nhật Status và Note của ticket"""
    conn = sqlite3.connect('crm_data.db')
    c = conn.cursor()
    c.execute('''
        UPDATE tickets
        SET Status = ?, Note = ?
        WHERE id = ?
    ''', (status, note, ticket_id))
    conn.commit()
    conn.close()

def search_tickets(search_term, filter_type=None, selected_sheets=None):
    """Tìm kiếm tickets theo Salon Name, Phone, CID, hoặc Agent_Name"""
    # Use selected_sheets from session state if not provided
    if selected_sheets is None:
        selected_sheets = st.session_state.get('sheet_selection', [])
    
    # Load data from Google Sheets
    df = load_gsheet_data(selected_sheets)
    
    if df.empty:
        return df
    
    # Convert search term to lowercase for case-insensitive search
    search_lower = search_term.lower()
    
    # Search in Salon_Name, Phone, CID, and Agent_Name columns
    mask = (
        df['Salon_Name'].astype(str).str.lower().str.contains(search_lower, na=False) |
        df['Phone'].astype(str).str.lower().str.contains(search_lower, na=False) |
        df['CID'].astype(str).str.lower().str.contains(search_lower, na=False) |
        df['Agent_Name'].astype(str).str.lower().str.contains(search_lower, na=False)
    )
    
    df_filtered = df[mask].copy()
    
    # Apply filter_type if specified
    if filter_type == 'Training':
        df_filtered = df_filtered[
            df_filtered['Training_Note'].notna() & 
            (df_filtered['Training_Note'].astype(str) != '')
        ]
    elif filter_type == 'Demo':
        df_filtered = df_filtered[
            df_filtered['Demo_Note'].notna() & 
            (df_filtered['Demo_Note'].astype(str) != '')
        ]
    
    # Sort by Created_At descending (if column exists)
    if 'Created_At' in df_filtered.columns:
        # Convert Created_At to datetime if it's not already
        df_filtered['Created_At'] = pd.to_datetime(df_filtered['Created_At'], errors='coerce')
        df_filtered = df_filtered.sort_values('Created_At', ascending=False, na_position='last')
    
    # Add a temporary 'id' column for compatibility (using index)
    df_filtered = df_filtered.reset_index(drop=True)
    df_filtered.insert(0, 'id', range(1, len(df_filtered) + 1))
    
    return df_filtered

def get_all_tickets(filter_type=None, selected_sheets=None):
    """Lấy tất cả tickets từ Google Sheets"""
    # Use selected_sheets from session state if not provided
    if selected_sheets is None:
        selected_sheets = st.session_state.get('sheet_selection', [])
    
    # Load data from Google Sheets
    df = load_gsheet_data(selected_sheets)
    
    if df.empty:
        return df
    
    # Apply filter_type if specified
    if filter_type == 'Training':
        df = df[
            df['Training_Note'].notna() & 
            (df['Training_Note'].astype(str) != '')
        ].copy()
    elif filter_type == 'Demo':
        df = df[
            df['Demo_Note'].notna() & 
            (df['Demo_Note'].astype(str) != '')
        ].copy()
    
    # Sort by Created_At descending (if column exists)
    if 'Created_At' in df.columns:
        # Convert Created_At to datetime if it's not already
        df['Created_At'] = pd.to_datetime(df['Created_At'], errors='coerce')
        df = df.sort_values('Created_At', ascending=False, na_position='last')
    
    return df

# Khởi tạo database
init_db()

# Sidebar menu
st.sidebar.title("🏢 CRM - LLDTEK")
st.sidebar.markdown("---")

# Data Source Selection (Multi-Sheet Selection)
st.sidebar.subheader("📂 Select Data Source (Months)")
selected_sheets = st.sidebar.multiselect(
    "Select months to load data from:",
    options=AVAILABLE_SHEETS,
    default=[AVAILABLE_SHEETS[-1]] if AVAILABLE_SHEETS else [],  # Default to last item (current month)
    key="sheet_selection"
)

# Check if no sheets are selected - show message in main area
if not selected_sheets or len(selected_sheets) == 0:
    st.sidebar.warning("⚠️ Please select at least one month to view data.")
    st.info("ℹ️ **Please select at least one month from the sidebar to view data.**")
    st.stop()  # Stop execution if no sheets selected

st.sidebar.markdown("---")

# Agent selection (Session login)
agent_list = [
    "Nguyễn Trần Phương Loan",
    "Nguyễn Hương Giang",
    "Nguyễn Thị Phương Anh",
    "Võ Ngọc Tuấn",
    "Nguyễn Thị Thùy Dung",
    "Hồ Ngọc Mỹ Phượng",
    "Phạm Ngọc Chiến",
    "Trương Anh Đạt",
    "Dương Nhật Tiến",
    "Lưu Schang Sanh",
    "Lê Thị Tuyết Anh",
    "Đinh Thị Liên Chi",
    "Nguyễn Thị Anh Thư"
]

selected_agent = st.sidebar.selectbox(
    "Chọn Nhân Viên Hỗ Trợ",
    options=[""] + agent_list,
    index=0,
    key="agent_selection"
)

if selected_agent:
    st.sidebar.info(f"👤 Đang đăng nhập: **{selected_agent}**")

st.sidebar.markdown("---")

# Admin Access Section
st.sidebar.subheader("🔐 Admin Access")
is_manager = st.sidebar.checkbox("Login as Manager", key="manager_checkbox")

admin_authenticated = False
if is_manager:
    admin_password = st.sidebar.text_input(
        "Enter Manager Password:",
        type="password",
        key="admin_password"
    )
    
    # Hardcoded password for now (should be changed to secure method in production)
    if admin_password == "admin123":
        admin_authenticated = True
        st.sidebar.success("✅ Manager Access Granted")
    elif admin_password:
        st.sidebar.error("❌ Incorrect Password")

st.sidebar.markdown("---")

# Menu chính (only show if not admin)
if not admin_authenticated:
    main_menu = st.sidebar.selectbox(
        "Menu chính",
        ["🆕 New Ticket", "🔍 Search & History", "📊 Dashboard & Report"]
    )

    # Filter cho Training/Demo (chỉ hiển thị ở Search & History)
    filter_type = None
    if main_menu == "🔍 Search & History":
        st.sidebar.markdown("---")
        st.sidebar.subheader("🔍 Bộ lọc nhanh")
        filter_option = st.sidebar.radio(
            "Lọc theo loại:",
            ["Tất cả", "Training", "Demo"],
            index=0
        )
        if filter_option == "Training":
            filter_type = "Training"
        elif filter_option == "Demo":
            filter_type = "Demo"

    # Menu dữ liệu (chỉ hiển thị ở Dashboard & Report)
    data_page = None
    if main_menu == "📊 Dashboard & Report":
        st.sidebar.markdown("---")
        st.sidebar.subheader("📊 Dữ liệu & Báo cáo")
        data_page = st.sidebar.radio(
            "Chọn trang:",
            ["📊 Dashboard", "🎓 Training List", "🔢 16 Digits", "📞 Contact List"],
            index=0
        )
        page = data_page
    else:
        page = main_menu

# Main content area
# Check if admin is authenticated - show admin dashboard
if admin_authenticated:
    # Get all tickets data for admin dashboard from Google Sheets
    df_all_tickets = get_all_tickets(selected_sheets=selected_sheets)
    if not df_all_tickets.empty:
        admin_page.show_admin_dashboard(df_all_tickets)
    else:
        st.error("❌ No data available. Please check your Google Sheets configuration or select different months.")
elif page == "🆕 New Ticket":
    st.title("🆕 Tạo Ticket Mới")
    st.markdown("---")
    
    # Kiểm tra agent đã chọn
    if not selected_agent or selected_agent == "":
        st.warning("⚠️ Vui lòng chọn nhân viên hỗ trợ ở sidebar trước khi tạo ticket mới.")
    
    with st.form("new_ticket_form", clear_on_submit=True):
        # Field 1: Support Time (Date & Time)
        col_date, col_time = st.columns(2)
        with col_date:
            support_date = st.date_input("Thời gian hỗ trợ (Ngày)", value=datetime.now().date())
        with col_time:
            support_time_only = st.time_input("Thời gian hỗ trợ (Giờ)", value=datetime.now().time())
        support_time = datetime.combine(support_date, support_time_only)
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Field 2: Salon Name
            salon_name = st.text_input("Tên Tiệm *", placeholder="Nhập tên tiệm")
            # Field 3: Note CID
            cid = st.text_input("Note CID", placeholder="Nhập CID")
            # Field 4: Phone
            phone = st.text_input("Số Phone *", placeholder="Nhập số điện thoại")
        
        with col2:
            # Field 5: Caller Info
            caller_info = st.text_input("Thông tin người gọi", placeholder="Nhập thông tin người gọi")
            status = st.selectbox("📌 Trạng thái", ["Pending", "Done", "No Answer"], index=0)
        
        # Training and Demo on same row
        col_train, col_demo = st.columns(2)
        with col_train:
            training_note = st.text_input("🎓 Training", placeholder="Nhập ghi chú training (optional)")
        with col_demo:
            demo_note = st.text_input("🎬 Demo", placeholder="Nhập ghi chú demo (optional)")
        
        # Main Note Area - Ghi chú/Vấn đề
        issue_category = st.text_area("Ghi chú/Vấn đề *", placeholder="Nhập ghi chú hoặc vấn đề chi tiết...", height=100)
        
        submitted = st.form_submit_button("💾 Lưu Ticket", use_container_width=True)
        
        if submitted:
            if not selected_agent or selected_agent == "":
                st.error("❌ Vui lòng chọn nhân viên hỗ trợ ở sidebar!")
            elif salon_name and phone and issue_category:
                try:
                    # Format support_time
                    support_time_str = support_time.strftime('%Y-%m-%d %H:%M:%S') if support_time else datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # Use support_time date for Date field
                    date_str = support_time.strftime('%Y-%m-%d') if support_time else datetime.now().strftime('%Y-%m-%d')
                    
                    insert_ticket(
                        date_str,
                        salon_name,
                        phone,
                        issue_category,
                        issue_category,  # Using issue_category as Note
                        status,
                        cid if cid else None,
                        None,  # contact removed
                        None,  # card_16_digits removed
                        training_note if training_note else None,
                        demo_note if demo_note else None,
                        selected_agent if selected_agent else None,
                        support_time_str,
                        caller_info if caller_info else None
                    )
                    st.success(f"✅ Đã lưu ticket thành công cho {salon_name}!")
                except Exception as e:
                    st.error(f"❌ Lỗi khi lưu ticket: {str(e)}")
            else:
                st.warning("⚠️ Vui lòng điền đầy đủ các trường bắt buộc (*)")

elif page == "🔍 Search & History":
    st.title("🔍 Tìm kiếm & Lịch sử")
    st.markdown("---")
    
    search_term = st.text_input("🔎 Tìm kiếm theo Tên tiệm hoặc Số điện thoại", placeholder="Nhập tên tiệm hoặc số điện thoại...")
    
    if search_term:
        df = search_tickets(search_term, filter_type)
        
        if not df.empty:
            st.success(f"✅ Tìm thấy {len(df)} ticket(s)")
            
            # Hiển thị bảng với khả năng sort (không hiển thị ID)
            df_display = df.drop(columns=['id']) if 'id' in df.columns else df.copy()
            
            # Xử lý dữ liệu: Fill NaN values
            if 'Agent_Name' in df_display.columns:
                df_display['Agent_Name'] = df_display['Agent_Name'].fillna('')
            if 'CID' in df_display.columns:
                df_display['CID'] = df_display['CID'].fillna('').astype(str).str.replace('nan', '', regex=False)
            
            # Reorder columns
            primary_columns = ['Date', 'Agent_Name', 'Salon_Name', 'CID', 'Phone', 'Issue_Category', 'Note', 'Status']
            other_columns = [col for col in df_display.columns if col not in primary_columns]
            column_order = [col for col in primary_columns if col in df_display.columns] + other_columns
            df_display = df_display[column_order]
            
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Date": st.column_config.DateColumn("Ngày", format="DD/MM/YYYY"),
                    "Agent_Name": "Nhân viên",
                    "Salon_Name": "Tên tiệm",
                    "Phone": "Số điện thoại",
                    "Issue_Category": "Vấn đề",
                    "Note": "Chi tiết",
                    "Status": st.column_config.SelectboxColumn(
                        "Trạng thái",
                        options=["Pending", "Done", "No Answer"]
                    ),
                    "Support_Time": st.column_config.TextColumn("Thời gian hỗ trợ"),
                    "Caller_Info": "Thông tin người gọi",
                    "CID": "CID",
                    "Created_At": st.column_config.DatetimeColumn("Thời gian tạo", format="DD/MM/YYYY HH:mm:ss")
                }
            )
            
            # Thống kê nhanh
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Tổng số ticket", len(df))
            with col2:
                pending_count = len(df[df['Status'] == 'Pending'])
                st.metric("Pending", pending_count)
            with col3:
                done_count = len(df[df['Status'] == 'Done'])
                st.metric("Done", done_count)
            
            st.markdown("---")
            st.subheader("✏️ Cập nhật Ticket")
            
            # Chọn ticket để cập nhật
            if 'id' in df.columns:
                # Tạo danh sách ticket để chọn
                ticket_options = {}
                for idx, row in df.iterrows():
                    ticket_display = f"ID {row['id']} - {row['Salon_Name']} - {row['Phone']} - {row['Status']} ({row['Date']})"
                    ticket_options[ticket_display] = int(row['id'])
                
                selected_ticket_display = st.selectbox(
                    "📋 Chọn ticket cần cập nhật",
                    options=list(ticket_options.keys()),
                    index=0
                )
                
                if selected_ticket_display:
                    selected_ticket_id = ticket_options[selected_ticket_display]
                    ticket_info = get_ticket_by_id(selected_ticket_id, df_search_results=df, selected_sheets=selected_sheets)
                    
                    if ticket_info:
                        with st.form("update_ticket_form"):
                            st.write("**Thông tin ticket:**")
                            col1, col2 = st.columns(2)
                            with col1:
                                st.info(f"**Tên tiệm:** {ticket_info['Salon_Name']}\n\n**Số điện thoại:** {ticket_info['Phone']}\n\n**Vấn đề:** {ticket_info['Issue_Category']}")
                            with col2:
                                st.info(f"**Ngày:** {ticket_info['Date']}\n\n**Trạng thái hiện tại:** {ticket_info['Status']}\n\n**Ngày tạo:** {ticket_info['Created_At']}")
                            
                            st.markdown("---")
                            
                            # Form cập nhật
                            col1, col2 = st.columns(2)
                            with col1:
                                new_status = st.selectbox(
                                    "📌 Trạng thái mới *",
                                    options=["Pending", "Done"],
                                    index=0 if ticket_info['Status'] == 'Pending' else 1
                                )
                            
                            with col2:
                                st.write("") # Spacing
                                st.write("")
                            
                            # Note hiện tại
                            current_note = ticket_info['Note'] if ticket_info['Note'] else ""
                            new_note = st.text_area(
                                "📝 Chi tiết (Note) - Có thể thêm ghi chú mới",
                                value=current_note,
                                height=150,
                                help="Bạn có thể giữ nguyên hoặc thêm ghi chú mới vào note hiện tại"
                            )
                            
                            submitted = st.form_submit_button("💾 Cập nhật Ticket", use_container_width=True)
                            
                            if submitted:
                                try:
                                    update_ticket(selected_ticket_id, new_status, new_note)
                                    st.success(f"✅ Đã cập nhật ticket ID {selected_ticket_id} thành công!")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Lỗi khi cập nhật ticket: {str(e)}")
        else:
            st.info("ℹ️ Không tìm thấy ticket nào phù hợp với từ khóa tìm kiếm.")
    else:
        st.info("ℹ️ Vui lòng nhập từ khóa tìm kiếm để xem lịch sử tickets.")

elif page == "📊 Dashboard":
    st.title("📊 Dashboard & Báo cáo")
    st.markdown("---")
    
    # Lấy tất cả dữ liệu từ Google Sheets
    df = get_all_tickets(selected_sheets=selected_sheets)

    # ----------------------------------------------------
    # 👇 ĐÂY LÀ ĐOẠN CODE KIỂM TRA DỮ LIỆU CHUẨN (ĐÃ FIX)
    if not df.empty:
        with st.expander("🛠️ DEBUG - KIỂM TRA DỮ LIỆU GỐC", expanded=True):
            st.error(f"👇 KẾT QUẢ ĐỌC FILE (Tổng dòng: {len(df)})")
            st.write("Danh sách cột tìm thấy:", df.columns.tolist())
            st.dataframe(df.head(5))
    else:
        st.error("⚠️ KHÔNG TÌM THẤY DỮ LIỆU! (Hãy kiểm tra lại file Google Sheet)")
    # ----------------------------------------------------
    
    if not df.empty:
        # Chuyển đổi Date sang datetime (dayfirst=False for MM/DD/YYYY format, errors='coerce' để xử lý dữ liệu không hợp lệ)
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=False, errors='coerce')
        df['Created_At'] = pd.to_datetime(df['Created_At'], dayfirst=False, errors='coerce')
        
        # Tổng quan metrics - Hàng 1
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📋 Tổng số ticket", len(df))
        with col2:
            pending_count = len(df[df['Status'] == 'Pending'])
            st.metric("⏳ Pending", pending_count, delta=None)
        with col3:
            done_count = len(df[df['Status'] == 'Done'])
            st.metric("✅ Done", done_count, delta=None)
        with col4:
            if len(df) > 0:
                completion_rate = (done_count / len(df)) * 100
                st.metric("📈 Tỷ lệ hoàn thành", f"{completion_rate:.1f}%")
        
        # Tổng quan metrics - Hàng 2 (Training & Demo)
        col5, col6 = st.columns(2)
        with col5:
            training_count = len(df[df['Training_Note'].notna() & (df['Training_Note'] != '')])
            st.metric("🎓 Tổng Training", training_count, delta=None)
        with col6:
            demo_count = len(df[df['Demo_Note'].notna() & (df['Demo_Note'] != '')])
            st.metric("🎬 Tổng Demo", demo_count, delta=None)
        
        st.markdown("---")
        
        # Biểu đồ 1: Số lượng ticket theo trạng thái
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📊 Ticket theo Trạng thái")
            status_counts = df['Status'].value_counts()
            fig_status = px.pie(
                values=status_counts.values,
                names=status_counts.index,
                color=status_counts.index,
                color_discrete_map={'Pending': '#FFA500', 'Done': '#00AA00', 'No Answer': '#CCCCCC'},
                hole=0.4
            )
            fig_status.update_traces(textposition='inside', textinfo='percent+label')
            fig_status.update_layout(showlegend=True, height=400)
            st.plotly_chart(fig_status, use_container_width=True)
        
        with col2:
            st.subheader("📈 Top 5 Vấn đề hay gặp nhất")
            issue_counts = df['Issue_Category'].value_counts().head(5)
            fig_issues = px.bar(
                x=issue_counts.values,
                y=issue_counts.index,
                orientation='h',
                labels={'x': 'Số lượng', 'y': 'Vấn đề'},
                color=issue_counts.values,
                color_continuous_scale='Blues'
            )
            fig_issues.update_layout(showlegend=False, height=400)
            fig_issues.update_traces(texttemplate='%{x}', textposition='outside')
            st.plotly_chart(fig_issues, use_container_width=True)
        
        st.markdown("---")
        
        # Biểu đồ 2: Số lượng ticket theo ngày
        st.subheader("📅 Số lượng ticket theo ngày")
        # Lọc bỏ các dòng có Date là NaT trước khi groupby
        df_with_date = df[df['Date'].notna()].copy()
        if not df_with_date.empty:
            daily_counts = df_with_date.groupby(df_with_date['Date'].dt.date).size().reset_index(name='Số lượng')
            daily_counts = daily_counts.sort_values('Date')
            
            fig_daily = px.line(
                daily_counts,
                x='Date',
                y='Số lượng',
                markers=True,
                labels={'Date': 'Ngày', 'Số lượng': 'Số lượng ticket'},
                title="Biểu đồ đường số lượng ticket theo ngày"
            )
            fig_daily.update_traces(line_color='#1976d2', line_width=3, marker_size=8)
            fig_daily.update_layout(
                xaxis=dict(tickformat='%d/%m/%Y'),
                height=450,
                hovermode='x unified'
            )
            st.plotly_chart(fig_daily, use_container_width=True)
        else:
            st.info("ℹ️ Không có dữ liệu ngày tháng hợp lệ để hiển thị biểu đồ.")
        
        st.markdown("---")
        
        # Bảng Training và Demo
        col_train, col_demo = st.columns(2)
        
        with col_train:
            st.subheader("🎓 5 Tiệm Training gần nhất")
            # Lọc tickets có Training_Note
            df_training = df[df['Training_Note'].notna() & (df['Training_Note'] != '')].copy()
            if not df_training.empty:
                # Sắp xếp theo Created_At giảm dần và lấy top 5
                df_training_sorted = df_training.sort_values('Created_At', ascending=False).head(5)
                # Chọn các cột cần hiển thị
                df_training_display = df_training_sorted[['Date', 'Salon_Name', 'Phone', 'Training_Note']].copy()
                df_training_display = df_training_display.rename(columns={
                    'Date': 'Ngày',
                    'Salon_Name': 'Tên tiệm',
                    'Phone': 'Số điện thoại',
                    'Training_Note': 'Note'
                })
                # Format Date
                df_training_display['Ngày'] = pd.to_datetime(df_training_display['Ngày'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y')
                df_training_display['Ngày'] = df_training_display['Ngày'].fillna('')
                
                st.dataframe(
                    df_training_display,
                    use_container_width=True,
                    hide_index=True,
                    height=300
                )
            else:
                st.info("ℹ️ Chưa có dữ liệu Training nào.")
        
        with col_demo:
            st.subheader("🎬 5 Tiệm Demo gần nhất")
            # Lọc tickets có Demo_Note
            df_demo = df[df['Demo_Note'].notna() & (df['Demo_Note'] != '')].copy()
            if not df_demo.empty:
                # Sắp xếp theo Created_At giảm dần và lấy top 5
                df_demo_sorted = df_demo.sort_values('Created_At', ascending=False).head(5)
                # Chọn các cột cần hiển thị
                df_demo_display = df_demo_sorted[['Date', 'Salon_Name', 'Phone', 'Demo_Note']].copy()
                df_demo_display = df_demo_display.rename(columns={
                    'Date': 'Ngày',
                    'Salon_Name': 'Tên tiệm',
                    'Phone': 'Số điện thoại',
                    'Demo_Note': 'Note'
                })
                # Format Date
                df_demo_display['Ngày'] = pd.to_datetime(df_demo_display['Ngày'], dayfirst=True, errors='coerce').dt.strftime('%d/%m/%Y')
                df_demo_display['Ngày'] = df_demo_display['Ngày'].fillna('')
                
                st.dataframe(
                    df_demo_display,
                    use_container_width=True,
                    hide_index=True,
                    height=300
                )
            else:
                st.info("ℹ️ Chưa có dữ liệu Demo nào.")
        
        st.markdown("---")
        
        # Hiển thị bảng dữ liệu thô (optional)
        with st.expander("📋 Xem dữ liệu chi tiết"):
            st.dataframe(
                df.sort_values('Created_At', ascending=False),
                use_container_width=True,
                hide_index=True
            )
    else:
        st.info("ℹ️ Chưa có dữ liệu ticket nào. Vui lòng tạo ticket mới ở trang 'New Ticket'.")

elif page == "🎓 Training List":
    st.title("🎓 Danh sách Training")
    st.markdown("---")
    
    try:
        # Đọc file CSV
        df_training = pd.read_csv('cleaned_training.csv')
        
        # Tìm kiếm theo tên Salon
        search_term = st.text_input("🔎 Tìm kiếm theo tên Salon", placeholder="Nhập tên salon để tìm kiếm...")
        
        if search_term:
            # Lọc dữ liệu
            df_filtered = df_training[df_training['Salon Name'].str.contains(search_term, case=False, na=False)]
        else:
            df_filtered = df_training
        
        # Xóa các cột Unnamed
        columns_to_drop = [col for col in df_filtered.columns if 'Unnamed' in str(col)]
        df_display = df_filtered.drop(columns=columns_to_drop, errors='ignore')
        
        # Xóa các dòng hoàn toàn trống
        df_display = df_display.dropna(how='all')
        
        if not df_display.empty:
            st.success(f"✅ Hiển thị {len(df_display)} bản ghi")
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ Không tìm thấy dữ liệu phù hợp.")
            
    except FileNotFoundError:
        st.error("❌ Không tìm thấy file cleaned_training.csv")
    except Exception as e:
        st.error(f"❌ Lỗi khi đọc dữ liệu: {str(e)}")

elif page == "🔢 16 Digits":
    st.title("🔢 Danh sách 16 Digits")
    st.markdown("---")
    
    try:
        # Đọc file CSV
        df_digits = pd.read_csv('cleaned_16digits.csv')
        
        # Chuyển đổi các cột số thành string để tránh format số học
        numeric_columns = ['Card Last 4', 'Amount', 'Extra Due', 'Missed Tip', 'Refund', 'Ticket No.']
        for col in df_digits.columns:
            if col in numeric_columns:
                df_digits[col] = df_digits[col].astype(str)
        
        # Xóa các cột Unnamed
        columns_to_drop = [col for col in df_digits.columns if 'Unnamed' in str(col)]
        df_display = df_digits.drop(columns=columns_to_drop, errors='ignore')
        
        # Xóa các dòng hoàn toàn trống
        df_display = df_display.dropna(how='all')
        
        if not df_display.empty:
            st.success(f"✅ Hiển thị {len(df_display)} bản ghi")
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ Không có dữ liệu.")
            
    except FileNotFoundError:
        st.error("❌ Không tìm thấy file cleaned_16digits.csv")
    except Exception as e:
        st.error(f"❌ Lỗi khi đọc dữ liệu: {str(e)}")

elif page == "📞 Contact List":
    st.title("📞 Danh sách Contact")
    st.markdown("---")
    
    try:
        # Đọc file CSV
        df_contact = pd.read_csv('cleaned_contact.csv')
        
        # Xóa các cột Unnamed
        columns_to_drop = [col for col in df_contact.columns if 'Unnamed' in str(col)]
        df_display = df_contact.drop(columns=columns_to_drop, errors='ignore')
        
        # Xóa các dòng hoàn toàn trống
        df_display = df_display.dropna(how='all')
        
        if not df_display.empty:
            st.success(f"✅ Hiển thị {len(df_display)} bản ghi")
            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ Không có dữ liệu.")
            
    except FileNotFoundError:
        st.error("❌ Không tìm thấy file cleaned_contact.csv")
    except Exception as e:
        st.error(f"❌ Lỗi khi đọc dữ liệu: {str(e)}")