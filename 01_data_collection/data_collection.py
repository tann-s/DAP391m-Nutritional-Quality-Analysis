import os
import pandas as pd

# 1. Danh sách 4 file và danh mục tương ứng
FILES_CONFIG = [
    {"file": "part1_beverages.csv", "category": "beverages"},
    {"file": "part2_snacks.csv",    "category": "snacks"},
    {"file": "part3_meals.csv",     "category": "meals"},
    {"file": "part4_dairies.csv",     "category": "dairies"},
]

OUTPUT_FILE = "raw_dataset.csv"

def merge_data():
    dfs = []
    print("--- Bắt đầu đọc 4 file dữ liệu thô ---")

    for item in FILES_CONFIG:
        filepath = item["file"]
        category = item["category"]

        if os.path.exists(filepath):
            # Đọc file thô
            df = pd.read_csv(filepath, low_memory=False)
            
            # Gán danh mục chính nếu file gốc chưa có
            if "main_category" not in df.columns:
                df["main_category"] = category
            
            print(f"- Đã nạp '{filepath}': {len(df):,} dòng (Danh mục: {category})")
            dfs.append(df)
        else:
            print(f"- [CẢNH BÁO] Không tìm thấy file: {filepath}")

    if not dfs:
        print("Lỗi: Không tìm thấy file nào để gộp!")
        return

    # 2. Hợp nhất dữ liệu
    merged_df = pd.concat(dfs, ignore_index=True)
    total_before = len(merged_df)
    print(f"\n-> Tổng số dòng gộp lại: {total_before:,} dòng.")

    # 3. Khử trùng lặp mã vạch (code) nếu có sản phẩm dính ở nhiều file
    if "code" in merged_df.columns:
        merged_df.drop_duplicates(subset=["code"], keep="first", inplace=True)
        total_after = len(merged_df)
        duplicates_removed = total_before - total_after
        print(f"-> Đã loại bỏ {duplicates_removed:,} dòng trùng mã vạch 'code'.")
        print(f"-> Còn lại: {total_after:,} dòng duy nhất.")

    # 4. Xuất file kết quả thô hoàn chỉnh
    merged_df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n Hoàn tất! File dữ liệu thô đã được lưu vào: '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    merge_data()
