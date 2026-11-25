# G04 – Genie Vina KITS

Thiết kế dữ liệu cho REST API chỉ số vận hành Connext GNOM.

- [ERD, ràng buộc và quy ước chỉ số](docs/erd.md)
- [Schema PostgreSQL](database/schema.sql)
- [Script sinh dữ liệu giả](scripts/generate_seed.py)
- [API thống kê (phần C)](docs/metrics-api.md)
- [Phần A: hợp đồng API khách hàng và bàn giao](docs/customer-api.md)

## Chạy API khách hàng (phần A)

Backend dùng FastAPI + PostgreSQL, Python 3.10+. Từ thư mục gốc:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Điền kết quả sinh ngẫu nhiên vào `JWT_SECRET` trong `.env`; đặt `DATABASE_URL` trỏ tới database PostgreSQL của bạn. Sau đó nạp schema và seed theo hướng dẫn bên dưới, rồi khởi động:

```sh
uvicorn app.main:app --reload --env-file .env
```

Swagger: http://127.0.0.1:8000/docs. OpenAPI JSON: http://127.0.0.1:8000/openapi.json.

Trong khi thành viên D chưa tích hợp API đăng nhập, tạo JWT thử nghiệm bằng CLI local (không phải endpoint phát token):

```sh
python scripts/create_demo_token.py --member-id 1
```

ID mẫu: `1` ADMIN, `2` OPERATOR, `3` VIEWER. Copy token vào nút **Authorize** của Swagger. Token thử nghiệm hết hạn sau 30 phút. API xác minh chữ ký HS256, `sub`, `exp`, kiểm tra thành viên tồn tại và đọc quyền hiện tại từ database. Đăng nhập/logout và danh sách token đã thu hồi thuộc phần D, chưa triển khai trong phần A; điểm tích hợp là `app/auth.py:get_principal`.

Ví dụ gọi API sau khi thay `YOUR_TOKEN` bằng JWT:

```sh
curl 'http://127.0.0.1:8000/api/customers?page=1&size=20&country=VN' \
  -H 'Authorization: Bearer YOUR_TOKEN'

curl -X POST http://127.0.0.1:8000/api/customers \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{"customerCode":"DEMO-001","name":"Khách giả lập","country":"VN","signupMethod":"EMAIL","signedUpAt":"2026-11-24T09:00:00+07:00"}'
```

## Kiểm thử API

Chạy riêng unit test, không cần PostgreSQL hoặc biến môi trường:

```sh
python -m pytest tests/unit -q
```

Unit test kiểm tra validation model khách hàng, PATCH một phần, JWT/chữ ký/thuật toán/thời hạn, ma trận quyền, cấu hình bắt buộc và xử lý lỗi không lộ thông tin nội bộ. Fixture trong `tests/unit/conftest.py` chặn mọi kết nối database ngoài ý muốn.

Chạy toàn bộ test, gồm kiểm thử HTTP trên PostgreSQL:

```sh
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/genie_vina_test python -m pytest -q
```

Database kiểm thử phải tồn tại và tài khoản phải có quyền tạo schema. Bộ test tự tạo schema tên ngẫu nhiên, nạp schema/seed rồi xóa riêng schema đó khi kết thúc; không xóa bảng ở schema mặc định. Không có `TEST_DATABASE_URL` thì test HTTP được đánh dấu skipped, vẫn chạy unit test và test dữ liệu giả. Test HTTP kiểm tra CRUD, lưu dữ liệu thật, phân trang, bộ lọc, JWT, quyền, lỗi đầu vào, transaction rollback, ràng buộc ngày/FK, tạo trùng đồng thời và Swagger.

Cấu trúc backend:

```text
app/
  main.py        # FastAPI, định dạng lỗi chung, OpenAPI
  config.py      # Biến môi trường bắt buộc
  db.py          # Kết nối và transaction theo request
  auth.py        # Xác minh JWT, phân quyền; tích hợp phần D tại đây
  models.py      # Request/response, kiểm tra đầu vào
  customers.py   # 5 endpoint CRUD khách hàng
```

## Chạy dữ liệu mẫu

Yêu cầu PostgreSQL 14+ và Python 3.10+. Tạo database rỗng, chạy từ thư mục gốc:

```sh
psql -d genie_vina -v ON_ERROR_STOP=1 -f database/schema.sql
python3 scripts/generate_seed.py --output database/seed.sql
psql -d genie_vina -v ON_ERROR_STOP=1 -f database/seed.sql
```

Mặc định: 60 khách hàng, kỳ dữ liệu 30 ngày từ 2026-10-26 đến hết 2026-11-24, random seed `42`. Có thêm khách đăng ký và thanh toán trước kỳ để kiểm tra mua lại và so sánh kỳ trước. Tên và email đều là dữ liệu tổng hợp; email dùng miền `.invalid`.

```sh
python3 scripts/generate_seed.py --customers 100 --days 60 --end-date 2026-11-24 --seed 123 --output /tmp/genie-seed.sql
python3 -m unittest discover -s tests -v
```

Sau khi nạp seed mặc định, kiểm tra trực tiếp các ràng buộc và trigger (dữ liệu thử được rollback):

```sh
psql -d genie_vina -v ON_ERROR_STOP=1 -f tests/verify_database.sql
```

Script chỉ xuất SQL, không kết nối database. Seed chạy trong một transaction, từ chối chạy nếu bất kỳ bảng nghiệp vụ nào đã có dữ liệu và không xóa dữ liệu cũ. `database/seed.sql` là file sinh tự động, không cần commit.

Tài khoản mẫu: `admin@example.invalid`, `operator@example.invalid`, `viewer@example.invalid`; mật khẩu `DemoOnly!2026`. Hash dùng định dạng `pbkdf2_sha256$600000$salt$base64digest` (PBKDF2-HMAC-SHA256, tương thích định dạng Django). Backend cần hỗ trợ định dạng này hoặc đổi hàm tạo hash theo encoder của framework trước khi nạp seed. Chỉ dùng các tài khoản này cho thử nghiệm.

Khi đổi trạng thái đơn, đặt người thao tác và lý do trong cùng transaction/kết nối để trigger tự ghi lịch sử:

```sql
BEGIN;
SET LOCAL app.member_id = '2';
SET LOCAL app.change_reason = 'Đã xác nhận thanh toán';
UPDATE orders SET status = 'PAID', paid_at = CURRENT_TIMESTAMP WHERE id = 1;
COMMIT;
```

API vẫn phải kiểm tra JWT và quyền; session setting trong database chỉ ghi nhận người thao tác, không thay thế xác thực.
