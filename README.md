# Genie Vina – API chỉ số vận hành Connext GNOM

REST API FastAPI + PostgreSQL cho toàn bộ bài tập: khách hàng, đơn hàng, lịch sử trạng thái, kết quả AI, xác thực JWT và bốn chỉ số vận hành. Có 16 thao tác HTTP, Swagger, dữ liệu giả, unit test và kiểm thử tích hợp PostgreSQL.

- [ERD, PK/FK và quyết định thiết kế](docs/erd.md)
- [Đặc tả API và ví dụ](docs/api.md)
- [Đối chiếu yêu cầu và kiểm chứng](docs/acceptance.md)
- [Quy trình Git và phân công](docs/git-workflow.md)
- [Kịch bản demo và thuyết trình](docs/presentation.md)
- [PowerPoint](docs/Genie-Vina.pptx)
- [OpenAPI toàn hệ thống](API/openapi.json)

## Cài đặt và chạy

Python 3.10+, PostgreSQL 14+. Chạy từ thư mục gốc:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Điền chuỗi ngẫu nhiên vào `JWT_SECRET` trong `.env`; đặt `DATABASE_URL` trỏ tới database riêng đã tạo. Không commit `.env`.

Nếu dùng Docker, có thể khởi động PostgreSQL local bằng:

```sh
docker compose up -d --wait
```

Đặt `DATABASE_URL=postgresql://postgres:local-demo-only@localhost:54329/genie_vina` khi dùng compose được cung cấp. Nạp schema và dữ liệu một lần vào database rỗng:

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/schema.sql
python scripts/generate_seed.py --output database/seed.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f database/seed.sql
uvicorn app.main:app --reload --env-file .env
```

Các lệnh `psql` cần `DATABASE_URL` đã được export trong shell; file `.env` chỉ được uvicorn tự nạp khi có `--env-file`. Nếu không có `psql` local, nạp vào compose bằng:

```sh
docker compose exec -T db psql -U postgres -d genie_vina -v ON_ERROR_STOP=1 < database/schema.sql
python scripts/generate_seed.py --output database/seed.sql
docker compose exec -T db psql -U postgres -d genie_vina -v ON_ERROR_STOP=1 < database/seed.sql
```

Database đã có schema bản trước chỉ cần chạy `database/migrations/001_revoked_tokens.sql`; không chạy lại schema/seed. Không tự động sửa database khi app khởi động.

Swagger: http://127.0.0.1:8000/docs. OpenAPI JSON: http://127.0.0.1:8000/openapi.json.

Đăng nhập tại `POST /api/auth/login`:

```json
{"email":"admin@example.invalid","password":"DemoOnly!2026"}
```

Copy `data.accessToken` vào **Authorize** trên Swagger. Token hết hạn sau 30 phút. Tài khoản khác: `operator@example.invalid`, `viewer@example.invalid`, cùng mật khẩu thử nghiệm trên. ADMIN toàn quyền; OPERATOR tạo/sửa dữ liệu, đổi trạng thái; VIEWER chỉ đọc/thống kê. Logout thu hồi token hiện tại, có hiệu lực cả khi restart ứng dụng.

## Kiểm thử

Không cần PostgreSQL:

```sh
python -m pytest tests/unit tests/test_seed.py -q
```

Kiểm thử toàn bộ trên database thử nghiệm riêng:

```sh
TEST_DATABASE_URL=postgresql://postgres:local-demo-only@localhost:54329/genie_vina python -m pytest -q
```

Test tạo schema ngẫu nhiên và tự xóa riêng schema đó; không xóa bảng nghiệp vụ ở schema mặc định. Nếu không có `TEST_DATABASE_URL`, test HTTP bị skipped. Kiểm tra ràng buộc/trigger bằng SQL (dữ liệu thử được rollback):

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f tests/verify_database.sql
```

## Dữ liệu và quy ước

Mặc định script tạo 60 khách, 3 thành viên đủ vai trò, dữ liệu trong 30 ngày 26/10–24/11/2026 và giao dịch trước kỳ để kiểm tra mua lại. Tên tổng hợp, email miền `.invalid`, không dùng thông tin cá nhân thật. Cấu hình tối thiểu 50 khách và 30 ngày; random seed mặc định `42`, kết quả tái lập được.

```sh
python scripts/generate_seed.py --customers 100 --days 60 --end-date 2026-11-24 --seed 123 --output /tmp/genie-seed.sql
```

Seed chạy trong một transaction và từ chối khi bảng nghiệp vụ đã có dữ liệu. Mật khẩu PBKDF2-HMAC-SHA256, 600.000 vòng; tài khoản mẫu chỉ dành cho demo.

Thống kê nhận `from`, `to` dạng `YYYY-MM-DD`, bao gồm hai ngày theo `Asia/Ho_Chi_Minh`. Đơn hiện PAID mới hợp lệ. Hoàn tiền tính riêng theo refundedAt. Tiền và tỷ lệ trả dưới dạng chuỗi thập phân chính xác; tăng trưởng trả null nếu kỳ trước bằng 0. Chi tiết công thức trong [ERD](docs/erd.md).

## Cấu trúc

```text
app/
  main.py         # Router, Swagger, lỗi thống nhất
  config.py       # DATABASE_URL, JWT_SECRET bắt buộc
  db.py           # Kết nối, transaction theo request
  auth.py         # JWT, token bị thu hồi, phân quyền
  sessions.py     # Đăng nhập, đăng xuất
  models.py       # Model khách hàng và response chung
  customers.py    # CRUD khách hàng
  operations.py   # Đơn hàng, trạng thái, lịch sử, AI
  metrics.py      # Công thức, API summary/daily
```

`API/openapi.json` và `API/orders.yaml` được sinh từ ứng dụng bằng `python scripts/export_openapi.py`; tránh sửa riêng hợp đồng làm lệch runtime. Tạo lại PPT bằng `python scripts/build_presentation.py`. Các thư viện hỗ trợ bàn giao nằm trong `requirements-tools.txt`.
