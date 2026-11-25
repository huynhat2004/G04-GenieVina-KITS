# API thống kê (phần C)

Hai endpoint tính các chỉ số vận hành từ dữ liệu `customers` và `orders`, kèm unit test cho logic tính toán. Quy ước tính chỉ số theo mục "Quy ước thống kê đề xuất" trong [erd.md](erd.md).

| File | Vai trò |
|---|---|
| `app/metrics_service.py` | Hàm tính toán thuần, `MetricsService` và `PostgresMetricsRepository` (SQL) |
| `app/metrics_api.py` | Router FastAPI cho `/api/metrics/*`, Swagger tự sinh tại `/docs` |
| `tests/test_metrics.py` | 27 unit test, không cần database |

Tách logic khỏi SQL để test không cần database; `MetricsService` nhận repository qua tham số nên test dùng repository giả.

## Endpoint

| Phương thức · đường dẫn | Chỉ số | Quyền |
|---|---|---|
| `GET /api/metrics/summary?from=&to=` | 1 · 2 · 3 | ADMIN, OPERATOR, VIEWER |
| `GET /api/metrics/daily?from=&to=` | 4 | ADMIN, OPERATOR, VIEWER |

Tham số `from`, `to` có dạng `YYYY-MM-DD`, bao gồm cả hai ngày. Lỗi trả 400 khi thiếu tham số, sai định dạng, `from > to` hoặc khoảng vượt 366 ngày.

Ví dụ `GET /api/metrics/summary?from=2026-10-26&to=2026-11-24` trên dữ liệu seed mặc định:

```json
{
  "status": 200,
  "message": "success",
  "data": {
    "period": { "from": "2026-10-26", "to": "2026-11-24", "days": 30 },
    "previousPeriod": { "from": "2026-09-26", "to": "2026-10-25", "days": 30 },
    "payingCustomers": { "total": 31, "firstTime": 30, "returning": 1 },
    "newSignups": { "count": 26, "previousCount": 34, "growthRate": -23.53 },
    "revenue": { "total": 11354000, "averagePerDay": 378466.67 },
    "refunds": { "totalAmount": 3087000, "orderCount": 13 }
  }
}
```

`GET /api/metrics/daily` trả `data.period` và `data.items`, mỗi phần tử có dạng `{ "date": "2026-10-26", "revenue": 0 }`, đủ mọi ngày trong kỳ, ngày không có dữ liệu ghi 0.

## Quy tắc tính

- Đơn hợp lệ là đơn `status = 'PAID'`, tính theo `paid_at`. Ngày tính theo giờ Việt Nam (UTC+7), truy vấn theo khoảng nửa mở `[from 00:00, ngày sau to 00:00)`.
- Kỳ trước có cùng số ngày và liền ngay trước kỳ hiện tại.
- Khách trả phí đếm không trùng; "lần đầu" là khách có đơn hợp lệ đầu tiên (trên toàn bộ lịch sử) nằm trong kỳ, còn lại là "thanh toán lại". Hai nhóm cộng lại bằng tổng.
- Tăng trưởng đăng ký = `(hiện tại − kỳ trước) / kỳ trước × 100`, làm tròn 2 chữ số; kỳ trước bằng 0 thì trả `null`.
- Trung bình ngày = doanh thu / số ngày của kỳ, tính cả ngày doanh thu 0.
- Hoàn tiền tính theo `refunded_at` (không lọc `PAID`) và không bị trừ khỏi doanh thu. Đơn đã `REFUNDED` không còn là đơn hợp lệ.

## Chạy unit test

```sh
python -m unittest discover -s tests -v
```

Trên Windows dùng `py` thay cho `python`. Lệnh này chạy cả `tests/test_seed.py`; chỉ chạy phần C bằng `python -m unittest tests.test_metrics -v`.

## Chạy API với PostgreSQL

Nạp schema và seed như mục "Chạy dữ liệu mẫu" trong [README](../README.md), rồi:

```sh
pip install fastapi uvicorn "psycopg[binary]"
export DATABASE_URL="postgresql://postgres:postgres@localhost:5432/genie_vina"
uvicorn dev_main:app --reload
```

Trên PowerShell, đặt biến bằng `$env:DATABASE_URL = "..."`. `dev_main.py` là file chạy thử cục bộ (không commit), tạo `FastAPI()`, gắn `router` từ `app.metrics_api` và bỏ qua xác thực bằng `app.dependency_overrides[require_member] = lambda: None`. Mở http://127.0.0.1:8000/docs để thử.

## Điểm nối với các phần khác

- `require_member()` trong `app/metrics_api.py` là chỗ cắm dependency JWT của phần xác thực; cần cho phép cả ba vai trò.
- `get_db()` mở kết nối bằng biến `DATABASE_URL`; thay bằng hàm kết nối dùng chung của nhóm nếu có.
- Lỗi 400 hiện là `HTTPException`; phần xử lý ngoại lệ chung cần chuyển về định dạng `{ "status", "message", "data" }`.