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

Router thống kê được đăng ký trong `app/main.py` cùng backend chung, dùng chung `DATABASE_URL`, JWT và định dạng phản hồi/lỗi. Chạy backend và lấy token thử theo hướng dẫn trong [README](../README.md) (mục "Chạy API khách hàng"), ví dụ:

```sh
python scripts/create_demo_token.py --member-id 3   # VIEWER cũng xem được thống kê
uvicorn app.main:app --reload --env-file .env
```

Mở http://127.0.0.1:8000/docs, bấm **Authorize**, dán token rồi thử `GET /api/metrics/summary` và `GET /api/metrics/daily`. Hoặc dùng curl:

```sh
curl 'http://127.0.0.1:8000/api/metrics/summary?from=2026-10-26&to=2026-11-24' \
  -H 'Authorization: Bearer YOUR_TOKEN'
```

## Tích hợp với backend chung

- Xác thực và phân quyền dùng `require_roles('ADMIN', 'OPERATOR', 'VIEWER')` từ `app/auth.py`; kết nối DB lấy từ `Database` (`app/db.py`).
- Phản hồi dùng `Envelope` trong `app/models.py`; lỗi 400/401/403/503 đi qua các exception handler trong `app/main.py`.
- `PostgresMetricsRepository` tự dùng cursor `dict_row` nên không phụ thuộc `row_factory` của connection.