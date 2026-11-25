# G04 – Genie Vina KITS

Thiết kế dữ liệu cho REST API chỉ số vận hành Connext GNOM.

- [ERD, ràng buộc và quy ước chỉ số](docs/erd.md)
- [Schema PostgreSQL](database/schema.sql)
- [Script sinh dữ liệu giả](scripts/generate_seed.py)
- [API thống kê (phần C)](docs/metrics-api.md)

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
