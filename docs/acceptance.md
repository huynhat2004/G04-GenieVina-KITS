# Đối chiếu yêu cầu hai ảnh đề bài

## Ma trận nghiệm thu

| Yêu cầu | Sản phẩm | Kiểm chứng |
|---|---|---|
| ERD 5 bảng, PK/FK và 1:N | docs/erd.md, database/schema.sql | tests/verify_database.sql |
| customers đủ trường và CRUD | app/models.py, app/customers.py | tests/test_customers_api.py |
| orders, status, history | app/operations.py, trigger database | tests/test_operations_api.py |
| ai_results, QUOTE/WEBSITE | app/operations.py | tests/test_operations_api.py |
| members, mật khẩu hash | database/schema.sql, app/sessions.py | tests/unit/test_sessions.py, test login HTTP |
| Cấp/thu hồi JWT | app/sessions.py, app/auth.py, revoked_tokens | test login/logout + kiểm tra database |
| ADMIN/OPERATOR/VIEWER | require_roles + đọc role từ DB | tests/unit/test_auth.py, HTTP phân quyền |
| Tiền >0, mã khách unique | Pydantic + SQL constraints | test model và duplicate/concurrent HTTP |
| Khách tồn tại, ngày không trước đăng ký | validate_event + SQL triggers | HTTP 400/404, SQL constraints |
| Không xóa khách có đơn | FK RESTRICT | test xóa 409, concurrency HTTP |
| Chuyển trạng thái đúng, audit tự động | FOR UPDATE + trigger trong transaction | test PAID/FAILED/REFUNDED và hai payment đồng thời |
| Chỉ số 1 khách trả phí/lần đầu/mua lại | calculate_summary | unit test nhiều đơn, lịch sử trước kỳ |
| Chỉ số 2 đăng ký/tăng trưởng | calculate_summary | unit test kỳ trước, chia 0, tăng trưởng âm |
| Chỉ số 3 doanh thu/trung bình/hoàn tiền | calculate_summary | unit test Decimal và hoàn tiền |
| Chỉ số 4 doanh thu đủ từng ngày | calculate_daily | unit test UTC+07, ngày 0, HTTP tổng daily = revenue |
| API thống kê from–to | app/metrics.py | HTTP validation, dữ liệu seed PostgreSQL |
| Swagger cho mọi endpoint | app/main.py, API/openapi.json | test 16 thao tác, validate OpenAPI |
| Response và lỗi thống nhất | Envelope, global handlers | tests/unit/test_error_handlers.py + HTTP |
| ≥50 khách, ≥30 ngày, dữ liệu giả | scripts/generate_seed.py | tests/test_seed.py: 50/60/120 khách, 30/90 ngày |
| Git nhánh/PR/commit có nghĩa | docs/git-workflow.md, PR template | Nhánh triển khai riêng; review do thành viên khác thực hiện |
| PPT và giải thích quyết định | docs/Genie-Vina.pptx, docs/presentation.md | Script sinh PPT tái lập được |

Kết quả đã chạy: **146 test đạt**, không skipped; SQL constraints/trigger và migration đạt. Xem [biên bản kiểm chứng](validation.md).

## Kiểm chứng tái lập

```sh
python -m pytest tests/unit tests/test_seed.py -q
TEST_DATABASE_URL=<database-thu-nghiem> python -m pytest -q
python scripts/export_openapi.py
python scripts/build_presentation.py
```

Test HTTP chạy trên PostgreSQL thật trong schema ngẫu nhiên rồi tự xóa. Không có TEST_DATABASE_URL thì skip, không được coi skipped là đã kiểm chứng tích hợp. Test độc lập cho công thức dùng kết quả kỳ vọng tính sẵn; test HTTP kiểm tra việc lấy dữ liệu và response của API.

## Những việc cần người trong nhóm hoàn tất

Điền tên thật vào bảng phân công; thực hiện review PR độc lập trước merge; trình bày và nộp link GitHub/PPT theo quy định lớp. Không tự tạo lịch sử làm việc của năm người. Phần mềm không tích hợp cổng thanh toán hay mô hình AI vì đề chỉ yêu cầu quản lý bản ghi và chỉ số.
