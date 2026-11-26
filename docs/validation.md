# Biên bản kiểm chứng ngày 25/11/2026

## Đã thực hiện tại workspace

- `python -m pytest -q` với TEST_DATABASE_URL trỏ PostgreSQL 16 chạy trong Docker tạm: **146 passed**, 3 subtests passed; không skipped. Có một cảnh báo deprecation của thư viện TestClient/httpx, không làm thất bại test.
- Tạo schema kiểm chứng độc lập, nạp schema và seed mặc định, chạy `tests/verify_database.sql`: toàn bộ ràng buộc và trigger đạt; các thao tác thử được rollback.
- Mô phỏng database cũ thiếu revoked_tokens, chạy migration 001 hai lần: tạo bảng/index thành công và áp dụng lại không lỗi.
- `python scripts/export_openapi.py`: cả đặc tả toàn hệ thống và tập con Orders/AI đều qua openapi-spec-validator.
- `python scripts/build_presentation.py`: sinh PowerPoint 13 slide, mở lại bằng python-pptx, kiểm tra speaker notes và vị trí shape trong khổ slide.
- `git diff --check`: không có lỗi whitespace.

Kiểm thử PostgreSQL chạy trong schema tên ngẫu nhiên và schema được xóa sau khi xong. Database ứng dụng trong `.env` không bị sửa. Không khẳng định đã chạy CI trên GitHub hoặc đã có review độc lập; workflow được cung cấp để chạy khi push/PR.

## Giới hạn kiểm chứng

PowerPoint đã được kiểm tra cấu trúc và nội dung bằng thư viện; nhóm nên mở bằng PowerPoint để duyệt hiển thị trên máy thuyết trình. Phần mềm được kiểm chứng cho phạm vi bài tập, chưa benchmark tải production. Công thức thống kê đã có unit test độc lập và kiểm thử dữ liệu PostgreSQL; hiện aggregation dùng Python để giữ công thức dễ đọc ở quy mô đề.
