import time
import pandas as pd
import requests


CATEGORY = "dairies"
TARGET_ROWS = 10000
PAGE_SIZE = 100
OUTPUT_FILE = "part4_dairies.csv"

FIELDS = [
    "code", "product_name", "brands", "categories_tags", "countries_tags",
    "nutriscore_grade", "nutriscore_score", "nova_group",
    "energy-kcal_100g", "fat_100g", "saturated-fat_100g", 
    "sugars_100g", "salt_100g", "proteins_100g", "fiber_100g",
    "additives_n",        # BẮT BUỘC để giải quyết RQ6
    "serving_size"        # Phục vụ kiểm tra chuẩn hóa
]

# Chia theo các thị trường lớn để tránh quá tải query và không lo chạm trần phân trang
COUNTRIES = ["france", "united-states", "germany", "spain", "united-kingdom", "italy", "belgium"]

HEADERS = {
    "User-Agent": "FPTU_DAP391m_Research/3.0 (academic_student_project@fpt.edu.vn)"
}

URL = "https://world.openfoodfacts.org/cgi/search.pl"

def crawl_data():
    collected_data = []
    seen_codes = set()

    print(f"--- Bắt đầu thu thập danh mục: {CATEGORY} ---")

    for country in COUNTRIES:
        if len(collected_data) >= TARGET_ROWS:
            break

        print(f"\n>> Đang lấy dữ liệu từ thị trường: {country}...")
        page = 1

        while page <= 25:  # Tối đa 2.500 sản phẩm mỗi quốc gia
            params = {
                "action": "process",
                "tagtype_0": "categories",
                "tag_contains_0": "contains",
                "tag_0": CATEGORY,
                "tagtype_1": "countries",
                "tag_contains_1": "contains",
                "tag_1": country,
                "fields": ",".join(FIELDS),
                "page_size": PAGE_SIZE,
                "page": page,
                "json": 1
            }

            try:
                res = requests.get(URL, params=params, headers=HEADERS, timeout=20)

                if res.status_code != 200:
                    print(f"Quốc gia {country} - Trang {page}: HTTP {res.status_code}. Nghỉ 3s...")
                    time.sleep(3)
                    page += 1
                    continue

                data = res.json()
                products = data.get("products", [])

                if not products:
                    break

                new_count = 0
                for p in products:
                    code = p.get("code")
                    if not code or code in seen_codes:
                        continue

                    seen_codes.add(code)
                    row = {f: p.get(f, None) for f in FIELDS}

                    # Gán nhãn danh mục gốc để sau này merge dữ liệu không bị mất nhãn (phục vụ RQ1 và Model)
                    row["main_category"] = CATEGORY

                    if isinstance(row.get("categories_tags"), list):
                        row["categories_tags"] = ", ".join(row["categories_tags"])
                    if isinstance(row.get("countries_tags"), list):
                        row["countries_tags"] = ", ".join(row["countries_tags"])

                    collected_data.append(row)
                    new_count += 1

                    if len(collected_data) >= TARGET_ROWS:
                        break

                print(f"Trang {page}: Lấy thêm {new_count} dòng | Tổng: {len(collected_data)}/{TARGET_ROWS}")

                # Lưu backup định kỳ
                if len(collected_data) % 500 < PAGE_SIZE and new_count > 0:
                    pd.DataFrame(collected_data).to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
                    print(f"-> Đã lưu tạm vào '{OUTPUT_FILE}'")

                if len(collected_data) >= TARGET_ROWS:
                    break

                page += 1
                time.sleep(1.0)  # Giãn cách an toàn tránh 503

            except Exception as e:
                print(f"Lỗi kết nối tại trang {page}: {e}. Chuyển trang tiếp...")
                page += 1
                time.sleep(2)

    df = pd.DataFrame(collected_data)
    df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
    print(f"\n Hoàn tất! Đã lưu {len(df)} dòng vào '{OUTPUT_FILE}'.")

if __name__ == "__main__":
    crawl_data()