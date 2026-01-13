import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Sử dụng backend không cần GUI
from datetime import datetime
from matplotlib.patches import Patch
import sys
import io
import os

# Cấu hình encoding cho Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Đọc dữ liệu tickets
print("Dang doc du lieu tu cleaned_tickets_history.csv...")
df = pd.read_csv('cleaned_tickets_history.csv')

# Chuyển đổi cột Date sang kiểu datetime
df['Date'] = pd.to_datetime(df['Date'])

# Đảm bảo CID và Phone là string trong df tickets
if 'CID' in df.columns:
    df['CID'] = df['CID'].fillna('').astype(str).str.replace('.0', '', regex=False).str.replace('nan', '', regex=False).str.strip()
    # Fill any remaining None/NaN values with empty string
    df['CID'] = df['CID'].apply(lambda x: '' if pd.isna(x) or str(x).lower() == 'nan' else str(x))
else:
    df['CID'] = ''

if 'Phone' in df.columns:
    df['Phone'] = df['Phone'].fillna('').astype(str).str.replace('.0', '', regex=False).str.replace('nan', '', regex=False).str.strip()
    # Fill any remaining None/NaN values with empty string
    df['Phone'] = df['Phone'].apply(lambda x: '' if pd.isna(x) or str(x).lower() == 'nan' else str(x))
else:
    df['Phone'] = ''

# Load reference data từ CSV files
training_cids = set()
training_phones = set()
digits_cids = set()
digits_phones = set()

try:
    if os.path.exists('cleaned_training.csv'):
        print("Dang doc du lieu tu cleaned_training.csv...")
        df_training = pd.read_csv('cleaned_training.csv')
        
        # Chuẩn hóa cột Phone và CID
        if 'Phone' not in df_training.columns:
            phone_cols = [c for c in df_training.columns if 'phone' in str(c).lower()]
            if phone_cols:
                df_training['Phone'] = df_training[phone_cols[0]]
            else:
                df_training['Phone'] = ''
        
        if 'CID' not in df_training.columns:
            df_training['CID'] = ''
        
        # Chuyển đổi sang string và loại bỏ .0
        df_training['CID'] = df_training['CID'].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_training['Phone'] = df_training['Phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
        
        # Tạo set các giá trị để match
        training_cids = set(df_training['CID'].dropna().unique())
        training_phones = set(df_training['Phone'].dropna().unique())
        
        # Loại bỏ giá trị rỗng và 'nan'
        training_cids = {c for c in training_cids if c and c != 'nan' and c != ''}
        training_phones = {p for p in training_phones if p and p != 'nan' and p != ''}
        
        print(f"  Loaded {len(training_phones)} phones and {len(training_cids)} CIDs from Training")
    else:
        print("  File cleaned_training.csv not found, skipping Training data")
except Exception as e:
    print(f"  Error loading cleaned_training.csv: {e}")

try:
    if os.path.exists('cleaned_16digits.csv'):
        print("Dang doc du lieu tu cleaned_16digits.csv...")
        df_16digits = pd.read_csv('cleaned_16digits.csv')
        
        # Chuẩn hóa cột Phone và CID
        if 'Phone' not in df_16digits.columns:
            phone_cols = [c for c in df_16digits.columns if 'phone' in str(c).lower()]
            if phone_cols:
                df_16digits['Phone'] = df_16digits[phone_cols[0]]
            else:
                df_16digits['Phone'] = ''
        
        if 'CID' not in df_16digits.columns:
            df_16digits['CID'] = ''
        
        # Chuyển đổi sang string và loại bỏ .0
        df_16digits['CID'] = df_16digits['CID'].astype(str).str.replace('.0', '', regex=False).str.strip()
        df_16digits['Phone'] = df_16digits['Phone'].astype(str).str.replace('.0', '', regex=False).str.strip()
        
        # Tạo set các giá trị để match
        digits_cids = set(df_16digits['CID'].dropna().unique())
        digits_phones = set(df_16digits['Phone'].dropna().unique())
        
        # Loại bỏ giá trị rỗng và 'nan'
        digits_cids = {c for c in digits_cids if c and c != 'nan' and c != ''}
        digits_phones = {p for p in digits_phones if p and p != 'nan' and p != ''}
        
        print(f"  Loaded {len(digits_phones)} phones and {len(digits_cids)} CIDs from 16 Digits")
    else:
        print("  File cleaned_16digits.csv not found, skipping 16 Digits data")
except Exception as e:
    print(f"  Error loading cleaned_16digits.csv: {e}")

# Thêm cột Training và 16 Digits
df['Training'] = ''
df['16 Digits'] = ''

# Match bằng Phone hoặc CID
for idx, row in df.iterrows():
    phone = str(row.get('Phone', '')).strip()
    cid = str(row.get('CID', '')).strip()
    
    # Loại bỏ .0 nếu có
    if phone.endswith('.0'):
        phone = phone[:-2]
    if cid.endswith('.0'):
        cid = cid[:-2]
    
    # Check Training
    if (phone and phone in training_phones) or (cid and cid in training_cids):
        df.at[idx, 'Training'] = 'Có'
    else:
        df.at[idx, 'Training'] = 'Không'
    
    # Check 16 Digits
    if (phone and phone in digits_phones) or (cid and cid in digits_cids):
        df.at[idx, '16 Digits'] = 'Có'
    else:
        df.at[idx, '16 Digits'] = 'Không'

print(f"\nReport DataFrame created with {len(df)} rows")
print(f"Training matches (Có): {(df['Training'] == 'Có').sum()}")
print(f"16 Digits matches (Có): {(df['16 Digits'] == 'Có').sum()}")

# Đếm số lượng ticket theo từng ngày
tickets_by_date = df.groupby('Date').size().reset_index(name='Số lượng ticket')
tickets_by_date = tickets_by_date.sort_values('Date')

# Tìm ngày có nhiều ticket nhất
max_day = tickets_by_date.loc[tickets_by_date['Số lượng ticket'].idxmax()]
print(f"\nPHAN TICH DU LIEU TICKET")
print("=" * 50)
print(f"Tong so ticket: {len(df)}")
print(f"So ngay co du lieu: {len(tickets_by_date)}")
print(f"\nNGAY DONG KHACH NHAT:")
print(f"  Ngay: {max_day['Date'].strftime('%d/%m/%Y')}")
print(f"  So luong ticket: {max_day['Số lượng ticket']}")

# Hiển thị top 5 ngày có nhiều ticket nhất
print(f"\nTOP 5 NGAY CO NHIEU TICKET NHAT:")
top_5 = tickets_by_date.nlargest(5, 'Số lượng ticket')
for idx, row in top_5.iterrows():
    print(f"  {row['Date'].strftime('%d/%m/%Y')}: {row['Số lượng ticket']} ticket")

# Vẽ biểu đồ
plt.figure(figsize=(14, 7))

# Tìm vị trí ngày có nhiều ticket nhất
max_idx = tickets_by_date['Số lượng ticket'].idxmax()
max_pos = tickets_by_date.index.get_loc(max_idx)

# Tạo danh sách màu - màu đỏ cho ngày có nhiều ticket nhất
colors = ['#d32f2f' if i == max_pos else '#1976d2' for i in range(len(tickets_by_date))]

# Vẽ biểu đồ cột
bars = plt.bar(range(len(tickets_by_date)), tickets_by_date['Số lượng ticket'], 
        color=colors, alpha=0.7, edgecolor='black', linewidth=1)

# Tùy chỉnh biểu đồ
plt.xlabel('Ngày', fontsize=12, fontweight='bold')
plt.ylabel('Số lượng ticket', fontsize=12, fontweight='bold')
plt.title('Số lượng ticket theo từng ngày', fontsize=14, fontweight='bold', pad=20)

# Đặt nhãn trục x
dates_labels = [date.strftime('%d/%m') for date in tickets_by_date['Date']]
plt.xticks(range(len(tickets_by_date)), dates_labels, rotation=45, ha='right')

# Thêm chú thích
legend_elements = [
    Patch(facecolor='#d32f2f', alpha=0.7, label=f"Ngày đông nhất: {tickets_by_date.loc[max_idx, 'Date'].strftime('%d/%m/%Y')} ({tickets_by_date.loc[max_idx, 'Số lượng ticket']} ticket)"),
    Patch(facecolor='#1976d2', alpha=0.7, label='Các ngày khác')
]
plt.legend(handles=legend_elements)

# Thêm giá trị trên mỗi cột
for i, v in enumerate(tickets_by_date['Số lượng ticket']):
    plt.text(i, v + max(tickets_by_date['Số lượng ticket']) * 0.01, str(v), 
             ha='center', va='bottom', fontsize=8, fontweight='bold')

# Thêm grid
plt.grid(axis='y', alpha=0.3, linestyle='--')

# Điều chỉnh layout
plt.tight_layout()

# Lưu biểu đồ
output_file = 'tickets_by_date_chart.png'
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"\nDa luu bieu do: {output_file}")

# Hiển thị thống kê tổng quan
print(f"\nTHONG KE TONG QUAN:")
print(f"  Trung bình ticket/ngày: {tickets_by_date['Số lượng ticket'].mean():.2f}")
print(f"  Trung vị ticket/ngày: {tickets_by_date['Số lượng ticket'].median():.2f}")
print(f"  Ngày ít ticket nhất: {tickets_by_date.loc[tickets_by_date['Số lượng ticket'].idxmin(), 'Date'].strftime('%d/%m/%Y')} ({tickets_by_date['Số lượng ticket'].min()} ticket)")

# Lưu Report DataFrame với các cột mới (optional)
# df.to_csv('tickets_report_with_training_16digits.csv', index=False)
# print(f"\nDa luu report DataFrame: tickets_report_with_training_16digits.csv")
