import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if hasattr(sys.stdout, "reconfigure"):          # in tiếng Việt ổn định trên Windows
    sys.stdout.reconfigure(encoding="utf-8")

# =============================== CẤU HÌNH (nhóm thống nhất ở đây) ===============================
BASE = Path(__file__).resolve().parent
INPUT_NAME = "raw_dataset.csv"
OUTPUT = BASE / "cleaned_dataset.csv"
REPORT = BASE / "cleaning_report.csv"

N_COUNTRIES = 5                # số quốc gia mục tiêu (plan: 3-5), tự chọn theo độ phủ dữ liệu
SELECTED_COUNTRIES = None      # hoặc ghi tay, vd ["france", "germany", "belgium", "spain", "united-kingdom"]

DROP_NO_NAME = True            # bỏ sản phẩm không có tên
MAX_MISSING_CORE = 0           # cho phép thiếu tối đa bao nhiêu chỉ số trọng yếu (0 = phải đủ hết)
DROP_INCONSISTENT_ENERGY = True  # bỏ dòng năng lượng mâu thuẫn với fat/đạm/đường (Atwater)
ENERGY_TOL_REL, ENERGY_TOL_ABS = 0.20, 30    # dung sai kiểm tra Atwater
IQR_K = 3.0                    # ngưỡng cờ ngoại lai thống kê (chỉ gắn cờ, KHÔNG xóa)

ENERGY = "energy-kcal_100g"
CORE = [ENERGY, "fat_100g", "saturated-fat_100g", "sugars_100g", "salt_100g", "proteins_100g"]
NUTRIENTS_G = ["fat_100g", "saturated-fat_100g", "sugars_100g", "salt_100g", "proteins_100g", "fiber_100g"]
# =================================================================================================

steps = []


def record(step, df, note=""):
    n = len(df)
    prev = steps[-1]["rows_after"] if steps else n
    steps.append({"step": step, "rows_after": n, "removed": prev - n, "note": note})
    print(f"[{len(steps):02d}] {step}: {n:,} dòng" + (f" (-{prev - n:,})" if prev - n else "") + (f"  | {note}" if note else ""))


def find_input():
    p = BASE / INPUT_NAME
    if p.exists():
        return p
    alt = sorted(BASE.glob("raw_dataset*.csv"))
    if alt:
        print(f"Không thấy {INPUT_NAME}, dùng: {alt[0].name}")
        return alt[0]
    print(f"KHÔNG TÌM THẤY file dữ liệu trong: {BASE}")
    print("Các file đang có:", [x.name for x in BASE.iterdir()])
    sys.exit(1)


# ===================================== 1. ĐỌC DỮ LIỆU =====================================
df = pd.read_csv(find_input(), dtype={"code": str}, encoding="utf-8-sig")
df.columns = df.columns.str.strip()
record("Đọc dữ liệu thô", df)

# ===================================== 2. LÀM SẠCH CHUỖI =====================================
text_cols = ["code", "product_name", "brands", "categories_tags", "countries_tags",
             "nutriscore_grade", "serving_size", "main_category"]
for c in text_cols:
    s = df[c].astype("string").str.replace(r"\s+", " ", regex=True).str.strip()
    df[c] = s.replace("", pd.NA)
for c in ["product_name", "brands", "serving_size"]:          # ký tự lỗi encoding
    df.loc[df[c].str.contains("\ufffd", na=False), c] = pd.NA

# ===================================== 3. MÃ VẠCH & TRÙNG LẶP =====================================
df = df[df["code"].str.fullmatch(r"\d+", na=False)].copy()
df = df.drop_duplicates(subset="code", keep="first")
record("Bỏ mã vạch không phải số + bỏ trùng mã vạch", df)
df = df[df["code"].str.len().between(8, 14)].copy()          # EAN-8/UPC-A/EAN-13/GTIN-14; mã ngắn hơn là mã nội bộ
record("Bỏ mã vạch sai độ dài (< 8 hoặc > 14 chữ số)", df)

# ===================================== 4. TÊN SẢN PHẨM =====================================
name = df["product_name"]
junk = name.isna() | name.str.fullmatch(r"\d+", na=False) | (name == df["code"]) | (name.str.len() <= 2)
df.loc[junk, "product_name"] = pd.NA
if DROP_NO_NAME:
    df = df[df["product_name"].notna()].copy()
record("Bỏ sản phẩm không có tên hợp lệ", df)

# ===================================== 5. THƯƠNG HIỆU =====================================
first_brand = df["brands"].str.split(",").str[0].str.strip()
key = first_brand.str.lower()
canon = first_brand.groupby(key).agg(lambda x: x.value_counts().index[0])
df["brand_main"] = key.map(canon)

# ===================================== 6. DANH MỤC & QUỐC GIA =====================================
def clean_tags(s):
    if pd.isna(s):
        return pd.NA
    items = [re.sub(r"^[a-z]{2}:", "", t.strip()) for t in s.split(",") if t.strip()]
    return "; ".join(dict.fromkeys(items)) if items else pd.NA


df["categories"] = df["categories_tags"].map(clean_tags)
df["countries"] = df["countries_tags"].map(clean_tags)
df = df.drop(columns=["categories_tags", "countries_tags"])
df["n_categories"] = df["categories"].str.count(";").add(1).fillna(0).astype(int)

# --- chọn quốc gia mục tiêu theo độ phủ dữ liệu (bỏ nhãn 'world') ---
country_lists = df["countries"].fillna("").str.split("; ")
counts = country_lists.explode().value_counts()
counts = counts[~counts.index.isin(["", "world"])]
selected = SELECTED_COUNTRIES or counts.head(N_COUNTRIES).index.tolist()
print("     Quốc gia mục tiêu:", {c: int(counts.get(c, 0)) for c in selected})
for c in selected:
    df[f"country_{c}"] = country_lists.map(lambda lst, c=c: c in lst)
df = df[df[[f"country_{c}" for c in selected]].any(axis=1)].copy()
country_lists = df["countries"].fillna("").str.split("; ")
df["n_countries"] = country_lists.map(len)
df["n_selected_countries"] = df[[f"country_{c}" for c in selected]].sum(axis=1)   # bán ở mấy nước mục tiêu
df["country_single"] = pd.NA                                  # nước duy nhất (nếu chỉ bán ở 1 nước mục tiêu) -> dùng cho so sánh quốc gia (RQ3)
for c in selected:
    df.loc[df[f"country_{c}"] & (df["n_selected_countries"] == 1), "country_single"] = c
record(f"Giữ sản phẩm bán tại {len(selected)} quốc gia mục tiêu", df)

# ===================================== 7. NHÃN THAM CHIẾU =====================================
bad = df["nutriscore_grade"].str.lower().isin(["unknown", "not-applicable"])
df.loc[bad, "nutriscore_grade"] = pd.NA
df["nutriscore_grade"] = df["nutriscore_grade"].str.upper()
df.loc[~df["nutriscore_grade"].isin(list("ABCDE")), "nutriscore_grade"] = pd.NA
df["nova_group"] = df["nova_group"].round().astype("Int64")
df.loc[~df["nova_group"].isin([1, 2, 3, 4]), "nova_group"] = pd.NA
df["additives_n"] = df["additives_n"].round().astype("Int64")
df.loc[df["additives_n"] < 0, "additives_n"] = pd.NA
df["main_category"] = df["main_category"].str.lower()

# ===================================== 8. CHUẨN HÓA ĐƠN VỊ (per 100g) =====================================
# Dữ liệu đã ở dạng *_100g. Phần quy đổi dưới đây chỉ chạy nếu file có các cột đơn vị khác.
if "energy-kj_100g" in df.columns:                       # kJ -> kcal
    kj = pd.to_numeric(df["energy-kj_100g"], errors="coerce")
    df[ENERGY] = df[ENERGY].fillna(kj / 4.184)
for c in [x for x in df.columns if x.endswith("_mg_100g")]:  # mg -> g
    g_col = c.replace("_mg_100g", "_100g")
    df[g_col] = pd.to_numeric(df.get(g_col), errors="coerce").fillna(pd.to_numeric(df[c], errors="coerce") / 1000)

for c in CORE + ["fiber_100g"]:
    df[c] = pd.to_numeric(df[c], errors="coerce")
    df.loc[df[c] < 0, c] = np.nan

# --- khẩu phần: đọc số + đơn vị chuẩn g/ml (chỉ để tham chiếu, dinh dưỡng đã per 100g) ---
def parse_serving(s):
    if pd.isna(s):
        return (np.nan, pd.NA)
    t = s.lower().replace(",", ".")
    paren = re.search(r"\(([^)]*)\)", t)
    for chunk in ([paren.group(1)] if paren else []) + [t]:
        m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|mg|ml|cl|dl|l)\b", chunk)
        if m:
            v, u = float(m.group(1)), m.group(2)
            return {"kg": (v * 1000, "g"), "g": (v, "g"), "mg": (v / 1000, "g"), "ml": (v, "ml"),
                    "cl": (v * 10, "ml"), "dl": (v * 100, "ml"), "l": (v * 1000, "ml")}[u]
    return (np.nan, pd.NA)


parsed = df["serving_size"].map(parse_serving)
df["serving_value"] = parsed.str[0].astype(float)
df["serving_unit"] = parsed.str[1]
bad = (df["serving_value"] <= 0) | (df["serving_value"] > 5000)
df.loc[bad, ["serving_value", "serving_unit"]] = [np.nan, pd.NA]

# ===================================== 9. BẤT THƯỜNG VẬT LÝ =====================================
# Giá trị vô lý ở chỉ số trọng yếu -> đánh dấu cả dòng và loại bỏ (không đoán/sửa số liệu).
# Riêng chất xơ (không thuộc chỉ số trọng yếu) chỉ chuyển thành NaN.
anomaly = pd.Series(False, index=df.index)
n_bad = {}
bad = df[ENERGY] > 900                                     # năng lượng tối đa ~900 kcal/100g
n_bad[ENERGY + " > 900"] = int(bad.sum()); anomaly |= bad
for c in NUTRIENTS_G:                                      # chất dinh dưỡng (g) không thể > 100 g/100g
    bad = df[c] > 100
    n_bad[c + " > 100"] = int(bad.sum())
    if c in CORE:
        anomaly |= bad
    else:
        df.loc[bad, c] = np.nan
bad = df["saturated-fat_100g"] > df["fat_100g"] + 0.01     # béo bão hòa <= tổng béo
n_bad["saturated-fat > fat"] = int(bad.sum()); anomaly |= bad
total = df[["fat_100g", "sugars_100g", "proteins_100g", "fiber_100g", "salt_100g"]].sum(axis=1)
bad = total > 100.5                                        # tổng thành phần <= 100 g
n_bad["tổng thành phần > 100g"] = int(bad.sum()); anomaly |= bad
bad = (df[ENERGY] == 0) & (df[["fat_100g", "sugars_100g", "proteins_100g"]].sum(axis=1) > 1)
n_bad["energy = 0 nhưng có macro"] = int(bad.sum()); anomaly |= bad
print("     Dòng phi vật lý:", {k: v for k, v in n_bad.items() if v})
df = df[~anomaly].copy()
record("Bỏ bản ghi có giá trị phi vật lý", df, f"{int(anomaly.sum())} dòng")

# ===================================== 10. THIẾU THÔNG TIN TRỌNG YẾU =====================================
n_missing_core = df[CORE].isna().sum(axis=1)
df = df[n_missing_core <= MAX_MISSING_CORE].copy()
record(f"Bỏ bản ghi thiếu > {MAX_MISSING_CORE} chỉ số trọng yếu", df,
       "trọng yếu = năng lượng, béo, béo bão hòa, đường, muối, đạm")

# ===================================== 11. NHẤT QUÁN NĂNG LƯỢNG (Atwater) =====================================
# Năng lượng phải nằm trong khoảng suy ra từ fat (9 kcal/g), đạm (4), carbohydrate (4).
# Cận dưới: carb >= đường. Cận trên: carb <= 100 - fat - đạm - muối.
fat, prot, sug, salt = df["fat_100g"], df["proteins_100g"], df["sugars_100g"], df["salt_100g"]
low = 9 * fat + 4 * prot + 4 * sug
high = 9 * fat + 4 * prot + 4 * (100 - fat - prot - salt).clip(lower=0)
inconsistent = (df[ENERGY] < (1 - ENERGY_TOL_REL) * low - ENERGY_TOL_ABS) | \
               (df[ENERGY] > (1 + ENERGY_TOL_REL) * high + ENERGY_TOL_ABS)
if DROP_INCONSISTENT_ENERGY:
    df = df[~inconsistent].copy()
record("Bỏ bản ghi năng lượng mâu thuẫn với thành phần (Atwater)", df, f"{int(inconsistent.sum())} dòng")

# ===================================== 12. TRÙNG NỘI DUNG =====================================
key_cols = ["_n", "_b"] + CORE
tmp = df.assign(_n=df["product_name"].str.lower(), _b=df["brand_main"].str.lower().fillna(""))
df = df[~tmp.duplicated(subset=key_cols, keep="first")].copy()
record("Bỏ bản ghi trùng nội dung (cùng tên + hãng + dinh dưỡng)", df)

# ===================================== 13. CỜ NGOẠI LAI THỐNG KÊ (chỉ gắn cờ) =====================================
flags = pd.DataFrame(index=df.index)
for c in CORE:
    g = df.groupby("main_category")[c]
    q1, q3 = g.transform(lambda s: s.quantile(0.25)), g.transform(lambda s: s.quantile(0.75))
    iqr = q3 - q1
    flags[c] = (df[c] < q1 - IQR_K * iqr) | (df[c] > q3 + IQR_K * iqr)
df["n_stat_outlier_flags"] = flags.sum(axis=1).astype(int)
df["has_fiber"] = df["fiber_100g"].notna()

# ===================================== 14. LƯU KẾT QUẢ =====================================
country_cols = [f"country_{c}" for c in selected]
order = (["code", "product_name", "brands", "brand_main", "main_category", "categories", "n_categories",
          "countries", "n_countries", "n_selected_countries", "country_single"] + country_cols +
         [ENERGY, "fat_100g", "saturated-fat_100g", "sugars_100g", "salt_100g", "proteins_100g", "fiber_100g",
          "additives_n", "serving_size", "serving_value", "serving_unit",
          "nutriscore_grade", "nutriscore_score", "nova_group",          # chỉ tham chiếu, KHÔNG làm feature
          "n_stat_outlier_flags", "has_fiber"])
df = df[order].reset_index(drop=True)
df.to_csv(OUTPUT, index=False, encoding="utf-8-sig")
pd.DataFrame(steps).to_csv(REPORT, index=False, encoding="utf-8-sig")

print("\n=== TÓM TẮT ===")
print(f"Dòng cuối cùng: {len(df):,}  (mục tiêu plan: 5.000 - 15.000)")
print("Theo nhóm ngành:\n" + df["main_category"].value_counts().to_string())
print("Theo quốc gia (1 SP có thể thuộc nhiều nước):\n" + df[country_cols].sum().to_string())
print("Chưa có Nutri-Score (nhóm cần dự đoán):", int(df["nutriscore_grade"].isna().sum()))
print("Tỷ lệ thiếu (%) các cột dinh dưỡng:\n" + (df[CORE + ["fiber_100g", "additives_n"]].isna().mean() * 100).round(1).to_string())
print(f"\nĐã lưu: {OUTPUT.name}, {REPORT.name}")