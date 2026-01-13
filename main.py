import pandas as pd
import os
import re
import sys
import io

# Cấu hình encoding cho Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- CẤU HÌNH TÊN FILE (Bạn sửa lại tên file nếu khác nhé) ---
EXCEL_FILE = '2-3-4 DAILY REPORT 12_25.xlsx'

def find_column_fuzzy(df_columns, keyword, exclude_columns=None):
    """
    Tìm cột có chứa keyword (case-insensitive, fuzzy matching)
    Trả về tên cột nếu tìm thấy, None nếu không
    """
    if exclude_columns is None:
        exclude_columns = []
    keyword_lower = keyword.lower()
    for col in df_columns:
        if col in exclude_columns:
            continue
        if keyword_lower in str(col).lower():
            return col
    return None

def find_columns_by_keywords(df_columns, keywords):
    """
    Tìm các cột dựa trên danh sách keywords (fuzzy matching)
    Trả về dictionary: {standard_name: actual_column_name}
    Ưu tiên tìm các từ khóa dài hơn trước (sắp xếp theo độ dài giảm dần)
    """
    found_columns = {}
    used_columns = set()
    
    # Sắp xếp keywords theo độ dài giảm dần để ưu tiên từ khóa dài hơn
    sorted_keywords = sorted(keywords, key=len, reverse=True)
    
    for keyword in sorted_keywords:
        col = find_column_fuzzy(df_columns, keyword, exclude_columns=list(used_columns))
        if col:
            used_columns.add(col)
            # Tạo tên chuẩn hóa từ keyword
            standard_name = keyword.title() if keyword.islower() else keyword
            found_columns[standard_name] = col
    
    return found_columns

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
                
                # Các cột bắt buộc (exact match)
                cols_exact = ['Name', 'Time', 'Salon Name', 'CID', 'Phone', 'Owner', 'Note', 'Status', 'Date']
                actual_cols = [c for c in cols_exact if c in df_day.columns]
                
                # Thêm các cột tìm được vào danh sách (đổi tên về tên chuẩn)
                column_mapping = {}
                card_16_col = None  # Để tránh duplicate mapping cho Card/16
                
                # CRITICAL: Ensure Name and CID are preserved (fuzzy match if exact match fails)
                if 'Name' not in actual_cols:
                    name_col = find_column_fuzzy(df_day.columns, 'Name')
                    if name_col:
                        actual_cols.append(name_col)
                        column_mapping[name_col] = 'Name'
                
                if 'CID' not in actual_cols:
                    cid_col = find_column_fuzzy(df_day.columns, 'CID')
                    if cid_col:
                        actual_cols.append(cid_col)
                        column_mapping[cid_col] = 'CID'
                
                # Tìm các cột mới bằng fuzzy matching
                # Keywords để tìm: Contact, Card (hoặc 16 Digits), Training, Demo
                fuzzy_keywords = ['Contact', 'Card', '16', 'Training', 'Demo']
                fuzzy_columns = find_columns_by_keywords(df_day.columns, fuzzy_keywords)
                
                for standard_name, actual_name in fuzzy_columns.items():
                    if actual_name not in actual_cols:
                        # Chuẩn hóa tên cột
                        standard_lower = standard_name.lower()
                        if standard_lower in ['card', '16']:
                            # Nếu chưa có cột Card_16_Digits, thêm vào
                            if card_16_col is None:
                                card_16_col = actual_name
                                actual_cols.append(actual_name)
                                column_mapping[actual_name] = 'Card_16_Digits'
                            # Nếu đã có, bỏ qua (có thể "Card" và "16" match cùng một cột hoặc khác nhau)
                        else:
                            # Thêm cột vào danh sách
                            actual_cols.append(actual_name)
                            if standard_lower == 'training':
                                column_mapping[actual_name] = 'Training_Note'
                            elif standard_lower == 'demo':
                                column_mapping[actual_name] = 'Demo_Note'
                            elif standard_lower == 'contact':
                                column_mapping[actual_name] = 'Contact'
                            else:
                                column_mapping[actual_name] = standard_name
                
                # Lọc lấy các cột cần thiết
                df_day = df_day[actual_cols]
                
                # Đổi tên các cột fuzzy matching về tên chuẩn
                if column_mapping:
                    df_day = df_day.rename(columns=column_mapping)
                
                all_tickets.append(df_day)
            except Exception as e:
                print(f"⚠️ Bỏ qua ngày {day}: {e}")

    if all_tickets:
        df_history = pd.concat(all_tickets, ignore_index=True)
        df_history = df_history.dropna(subset=['Salon Name']) # Bỏ dòng trống
        
        # CRITICAL: Final check - ensure Name and CID are present in output
        if 'CID' not in df_history.columns:
            df_history['CID'] = ''
        if 'Name' not in df_history.columns:
            df_history['Name'] = ''
        
        # Final data type safety: Convert CID and Name to string, clean values
        df_history['CID'] = df_history['CID'].astype(str).str.strip()
        df_history['CID'] = df_history['CID'].replace(['nan', 'None', 'NaT'], '')
        df_history['Name'] = df_history['Name'].astype(str).str.strip()
        df_history['Name'] = df_history['Name'].replace(['nan', 'None', 'NaT'], '')
        
        df_history.to_csv('cleaned_tickets_history.csv', index=False)
        print(f"✅ Đã tạo xong file: cleaned_tickets_history.csv ({len(df_history)} tickets)")
        print(f"   Columns in CSV: {', '.join(df_history.columns.tolist())}")
    else:
        print("❌ Không tìm thấy dữ liệu ngày nào cả.")

    print("\n🎉 XONG! Bạn đã có 2 file CSV sạch để Vibe Coding.")

except Exception as e:
    print(f"\n❌ Lỗi rồi: {e}")
    print("👉 Gợi ý: Kiểm tra lại tên file Excel hoặc cài thư viện: pip install pandas openpyxl")