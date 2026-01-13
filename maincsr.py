import pandas as pd
import os

# --- CẤU HÌNH TÊN FILE (Bạn sửa lại tên file nếu khác nhé) ---
EXCEL_FILE = '2-3-4 DAILY REPORT 12_25.xlsx'

print("⏳ Đang bắt đầu xử lý dữ liệu... Đợi chút nhé!")

try:
    # 1. XỬ LÝ DANH SÁCH KHÁCH HÀNG (Sheet SALON CID)
    print("... Đang đọc danh sách Salon...")
    # Thường header nằm ở dòng 1 hoặc 2, code này sẽ tự tìm
    df_salon = pd.read_excel(EXCEL_FILE, sheet_name='SALON CID', header=0)
    
    # Chọn đúng cột cần thiết (Sửa tên cột nếu file thật của bạn khác)
    # Giả định cột A là Salon Name, Cột B là CID dựa trên file bạn gửi
    if 'Salon Name' not in df_salon.columns:
         # Nếu không tìm thấy header chuẩn, thử đọc không header và gán thủ công
         df_salon = pd.read_excel(EXCEL_FILE, sheet_name='SALON CID', header=None)
         df_salon = df_salon.iloc[:, [0, 1]] # Lấy 2 cột đầu
         df_salon.columns = ['Salon Name', 'CID']
    
    df_salon = df_salon[['Salon Name', 'CID']].dropna(subset=['CID'])
    df_salon['CID'] = df_salon['CID'].astype(str).str.strip()
    
    # Xuất file Salon Master
    df_salon.to_csv('cleaned_salons_master.csv', index=False)
    print("✅ Đã tạo xong file: cleaned_salons_master.csv")

    # 2. XỬ LÝ LỊCH SỬ TICKET (Gộp các sheet ngày 1 -> 31)
    print("... Đang gộp lịch sử các ngày...")
    all_tickets = []
    
    # Lặp qua các sheet tên là "1", "2", ..., "31"
    # Bạn có thể điều chỉnh range(1, 32) nếu tháng có ít ngày hơn
    xls = pd.ExcelFile(EXCEL_FILE)
    
    for day in range(1, 32):
        sheet_name = str(day)
        if sheet_name in xls.sheet_names:
            try:
                # Dựa vào file bạn gửi, header thường ở dòng 4 (index 3)
                # Nhưng an toàn nhất là đọc và tìm dòng chứa chữ "Salon Name"
                df_day = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=3)
                
                # Kiểm tra xem có đúng cột không, nếu không thử header=2
                if 'Salon Name' not in df_day.columns:
                     df_day = pd.read_excel(EXCEL_FILE, sheet_name=sheet_name, header=2)
                
                # Thêm cột Ngày tháng
                df_day['Date'] = f"2024-12-{day:02d}" # Giả định tháng 12/2024
                
                # Lọc lấy các cột quan trọng
                cols_needed = ['Name', 'Time', 'Salon Name', 'CID', 'Phone', 'Owner', 'Note', 'Status', 'Date']
                # Chỉ lấy các cột có tồn tại trong file
                actual_cols = [c for c in cols_needed if c in df_day.columns]
                df_day = df_day[actual_cols]
                
                all_tickets.append(df_day)
            except Exception as e:
                print(f"⚠️ Bỏ qua ngày {day}: {e}")

    if all_tickets:
        df_history = pd.concat(all_tickets, ignore_index=True)
        df_history = df_history.dropna(subset=['Salon Name']) # Bỏ dòng trống
        df_history.to_csv('cleaned_tickets_history.csv', index=False)
        print(f"✅ Đã tạo xong file: cleaned_tickets_history.csv ({len(df_history)} tickets)")
    else:
        print("❌ Không tìm thấy dữ liệu ngày nào cả.")

    print("\n🎉 XONG! Bạn đã có 2 file CSV sạch để Vibe Coding.")

except Exception as e:
    print(f"\n❌ Lỗi rồi: {e}")
    print("👉 Gợi ý: Kiểm tra lại tên file Excel hoặc cài thư viện: pip install pandas openpyxl")