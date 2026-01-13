import pandas as pd
import sys
import io

# Cấu hình encoding cho Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def find_header_row(df_raw, sheet_name):
    """
    Tìm hàng header trong dataframe
    Trả về index của hàng header (0-based)
    """
    # Tìm hàng có chứa từ khóa header phổ biến
    header_keywords = ['date', 'name', 'no', 'phone', 'salon', 'note', 'card', 'training', 'email', 'contact']
    best_row = 0
    best_score = 0
    
    for idx in range(min(10, len(df_raw))):  # Chỉ kiểm tra 10 hàng đầu
        row_values = [str(val).lower() if pd.notna(val) else '' for val in df_raw.iloc[idx].values]
        row_str = ' '.join(row_values)
        
        # Đếm số từ khóa header xuất hiện
        keyword_count = sum(1 for keyword in header_keywords if keyword in row_str)
        
        # Đếm số giá trị không rỗng trong hàng
        non_empty_count = sum(1 for val in row_values if val and val != 'nan')
        
        # Tính điểm (ưu tiên nhiều keyword và nhiều giá trị)
        score = keyword_count * 2 + non_empty_count
        
        if score > best_score:
            best_score = score
            best_row = idx
    
    return best_row

def find_cid_column(df_cleaned):
    """
    Tìm cột CID trong dataframe (fuzzy matching)
    Trả về tên cột nếu tìm thấy, None nếu không
    Ưu tiên: CID exact > CID contains > Client Code/Salon Code > Code (standalone)
    """
    # Danh sách từ khóa loại trừ (không match)
    exclude_keywords = ['void', 'mistake', 'app', 'ticket', 'mid', 'iso', 'code', 'unified', 'phone']
    
    # Ưu tiên 1: Tìm exact match "CID"
    for col in df_cleaned.columns:
        col_lower = str(col).lower().strip()
        if col_lower == 'cid':
            return col
    
    # Ưu tiên 2: Tìm "CID" trong tên cột (như "CID Code", "Client CID")
    for col in df_cleaned.columns:
        col_lower = str(col).lower().strip()
        if 'cid' in col_lower:
            # Kiểm tra không phải từ khóa loại trừ
            if not any(exclude in col_lower for exclude in ['void', 'mistake']):
                return col
    
    # Ưu tiên 3: Tìm "Client Code" hoặc "Salon Code" (không phải "App Code", "ISO Code")
    for col in df_cleaned.columns:
        col_lower = str(col).lower().strip()
        if ('client code' in col_lower or 'salon code' in col_lower) and 'app' not in col_lower:
            return col
    
    # Ưu tiên 4: Tìm "Code" standalone (không kèm từ khác)
    for col in df_cleaned.columns:
        col_lower = str(col).lower().strip()
        if col_lower == 'code':
            return col
        # Chỉ match nếu "code" ở đầu hoặc cuối và không có từ loại trừ
        if (col_lower.startswith('code ') or col_lower.endswith(' code')) and \
           not any(exclude in col_lower for exclude in exclude_keywords):
            return col
    
    return None

def clean_dataframe(sheet_name):
    """
    Làm sạch dataframe:
    - Tìm và đặt header
    - Xóa các dòng hoàn toàn trống
    - Chuẩn hóa tên cột
    - Tìm và đổi tên cột CID
    - Đặt CID lên đầu
    """
    # Đọc raw data để tìm header
    df_raw = pd.read_excel('2-3-4 DAILY REPORT 12_25.xlsx', sheet_name=sheet_name, header=None, nrows=20)
    
    # Tìm hàng header
    header_row = find_header_row(df_raw, sheet_name)
    
    # Đọc lại với header đúng
    df_cleaned = pd.read_excel('2-3-4 DAILY REPORT 12_25.xlsx', sheet_name=sheet_name, header=header_row)
    
    # Xóa các dòng hoàn toàn trống (tất cả giá trị là NaN hoặc empty)
    df_cleaned = df_cleaned.dropna(how='all')
    
    # Chuẩn hóa tên cột (xóa khoảng trắng thừa và xuống dòng)
    df_cleaned.columns = [str(col).strip().replace('\n', ' ').replace('\r', '') if pd.notna(col) else f'Unnamed_{i}' for i, col in enumerate(df_cleaned.columns)]
    
    # Xóa các cột hoàn toàn trống (nếu có)
    df_cleaned = df_cleaned.dropna(axis=1, how='all')
    
    # Xóa các dòng có tất cả giá trị là NaN (sau khi đã set header)
    df_cleaned = df_cleaned.dropna(how='all')
    
    # Tìm và đổi tên cột CID
    cid_col = find_cid_column(df_cleaned)
    cid_found = False
    original_cid_col = None
    
    if cid_col:
        original_cid_col = cid_col
        # Nếu cột CID đã tồn tại và không phải tên chuẩn, đổi tên
        if cid_col != 'CID':
            df_cleaned = df_cleaned.rename(columns={cid_col: 'CID'})
        cid_found = True
    else:
        # Nếu không tìm thấy CID, tạo cột CID rỗng
        df_cleaned['CID'] = ''
        cid_found = False
    
    # Đặt cột CID lên đầu tiên
    if 'CID' in df_cleaned.columns:
        cols = ['CID'] + [col for col in df_cleaned.columns if col != 'CID']
        df_cleaned = df_cleaned[cols]
    
    return df_cleaned, cid_found, original_cid_col

def process_sheet(sheet_name, output_file):
    """
    Xử lý một sheet và xuất ra CSV
    """
    print(f"\n{'='*70}")
    print(f"Dang xu ly sheet: {sheet_name}")
    print(f"{'='*70}")
    
    try:
        # Làm sạch dữ liệu
        df_cleaned, cid_found, original_cid_col = clean_dataframe(sheet_name)
        
        # Xác nhận CID
        if cid_found:
            print(f"✅ Tim thay cot CID (ten goc: '{original_cid_col}')")
        else:
            print(f"⚠️ Khong tim thay cot CID, da tao cot CID trong")
        
        # Xuất ra CSV
        df_cleaned.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        print(f"✅ Da xuat thanh cong: {output_file}")
        print(f"   So dong: {len(df_cleaned)}")
        print(f"   So cot: {len(df_cleaned.columns)}")
        print(f"   Cot CID: {'Co' if 'CID' in df_cleaned.columns else 'Khong'}")
        if 'CID' in df_cleaned.columns:
            cid_count = df_cleaned['CID'].notna().sum() - (df_cleaned['CID'] == '').sum()
            print(f"   So dong co CID: {cid_count}/{len(df_cleaned)}")
        
        return df_cleaned
        
    except Exception as e:
        print(f"❌ Loi khi xu ly sheet {sheet_name}: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

# File Excel
excel_file = '2-3-4 DAILY REPORT 12_25.xlsx'

print("=" * 70)
print("IMPORT CAC SHEET DAC BIET TU FILE EXCEL")
print("=" * 70)

# Danh sách các sheet cần xử lý
sheets_to_process = [
    ('Training', 'cleaned_training.csv'),
    ('16 Digits', 'cleaned_16digits.csv'),
    ('Contact', 'cleaned_contact.csv')
]

# Dictionary để lưu các dataframe đã xử lý
processed_dataframes = {}

# Xử lý từng sheet
for sheet_name, output_file in sheets_to_process:
    df = process_sheet(sheet_name, output_file)
    if df is not None:
        processed_dataframes[sheet_name] = df

# In tên các cột của từng file CSV
print("\n" + "=" * 70)
print("TEN CAC COT CUA TUNG FILE CSV VUA TAO:")
print("=" * 70)

for sheet_name, output_file in sheets_to_process:
    if sheet_name in processed_dataframes:
        df = processed_dataframes[sheet_name]
        print(f"\n📄 {output_file} (từ sheet '{sheet_name}'):")
        print(f"   Tổng số cột: {len(df.columns)}")
        print(f"   Các cột:")
        for i, col in enumerate(df.columns, 1):
            print(f"      {i:2d}. {col}")
    else:
        print(f"\n❌ Không thể xử lý sheet '{sheet_name}'")

print("\n" + "=" * 70)
print("HOAN TAT!")
print("=" * 70)
