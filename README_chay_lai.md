# Hướng dẫn chạy lại (DAP391m – Nhóm 4)

Chạy **theo đúng thứ tự** trong cùng một thư mục (mỗi bước đọc file do bước trước tạo ra):

| Bước | File | Tạo ra |
|---|---|---|
| 1 | `Lam_sach.py` (từ `raw_dataset.csv`) | `cleaned_dataset.csv`, `cleaning_report.csv` |
| 2 | `03_eda.ipynb` | `eda_*.png` |
| 3 | `04_feature_selection.ipynb` | `train.csv`, `test.csv`, `feature_dataset.csv`, `fe_*.png` |
| 4 | `05_modeling.ipynb` | `cv_results.csv`, `model_*.joblib` (K-Means chạy trong file này) |
| 5 | `06_evaluation.ipynb` | `test_metrics.csv`, `feature_importance.csv`, `best_model.csv`, `model_comparison.csv`, `per_class_metrics.csv`, `kmeans_vs_label_*.csv`, `ml_*.png` |
| 6 | `07_conclusion.ipynb` | `final_model_comparison.png` |

`tong_hop_eda_den_ket_luan.ipynb` là bản gộp 5 phần của các notebook trên (chạy một lần từ trên xuống, cần `cleaned_dataset.csv` và `cleaning_report.csv` có sẵn).

Thư viện: `pip install -r requirements.txt`. Tất cả notebook đã được chạy lại từ đầu bằng bộ dữ liệu trong thư mục này nên số liệu trong phần nhận xét khớp với kết quả (seed cố định = 42).
