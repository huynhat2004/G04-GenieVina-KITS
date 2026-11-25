# Quy trình Git và phân công

Repository: https://github.com/huynhat2004/G04-GenieVina-KITS

## Phân công theo đề

| Thành viên | Phần phụ trách | File chính |
|---|---|---|
| A | ERD, seed, khách hàng | docs/erd.md, database/schema.sql, scripts/generate_seed.py, app/customers.py |
| B | Đơn hàng, trạng thái/lịch sử, kết quả AI | app/operations.py |
| C | Thống kê, unit test công thức | app/metrics.py, tests/unit/test_metrics.py |
| D | JWT, phân quyền, response, ngoại lệ, Swagger | app/auth.py, app/sessions.py, app/main.py |
| E | Git, tài liệu, thuyết trình | docs/, .github/pull_request_template.md |

Đây là ma trận trách nhiệm theo đề; không gán tên người thật hoặc giả lịch sử đóng góp. Nhóm cần điền tên thành viên và xác nhận phân công thực tế.

## Nhánh và review

Nhánh triển khai bổ sung: `feature/complete-operational-api`, tách từ main. Lịch sử trước đó đã có PR ERD (#1), Orders API specification (#2), Customer API (#3).

Nhánh: `feature/<chuc-nang>`, `fix/<loi>`, `docs/<chu-de>`. Commit mô tả thay đổi cụ thể, dùng `feat:`, `fix:`, `test:`, `docs:`. Không push trực tiếp main. Mỗi PR ghi vấn đề, hành vi sau thay đổi, lệnh test, tác động migration. Tối thiểu một thành viên khác review trước merge; tác giả tự kiểm tra không thay thế review độc lập.

Trình tự bàn giao: hoàn thiện nhánh → chạy toàn bộ test trên PostgreSQL riêng → xuất và validate OpenAPI → sinh PPT → mở PR → người khác review → sửa góp ý → merge. Không bịa tên reviewer, trạng thái phê duyệt, commit hoặc PR chưa tồn tại.

## Checklist reviewer

- Đối chiếu 16 thao tác HTTP với đề và Swagger.
- Token logout không dùng lại; VIEWER không ghi dữ liệu, OPERATOR không xóa khách.
- Chuyển trạng thái và lịch sử cùng transaction; hai thanh toán đồng thời chỉ thành công một.
- Thống kê đủ ngày 0, đếm distinct, có lịch sử trước kỳ và ranh giới UTC+07.
- Migration áp dụng cho database cũ; không chạy lại schema/seed đang có dữ liệu.
- Không commit `.env`, seed SQL sinh tự động hoặc token thật.
- Thử demo theo docs/presentation.md và mở PPT trước khi nộp.
