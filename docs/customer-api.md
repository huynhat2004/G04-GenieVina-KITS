# Phần A – API khách hàng

Phạm vi: ERD, script dữ liệu giả và CRUD khách hàng. Không triển khai API đơn hàng, thống kê hoặc đăng nhập của các thành viên khác.

## Hợp đồng API

| Method | Endpoint | Quyền | Thành công |
|---|---|---|---|
| POST | `/api/customers` | ADMIN, OPERATOR | 201 |
| GET | `/api/customers` | ADMIN, OPERATOR, VIEWER | 200 |
| GET | `/api/customers/{id}` | ADMIN, OPERATOR, VIEWER | 200 |
| PATCH | `/api/customers/{id}` | ADMIN, OPERATOR | 200 |
| DELETE | `/api/customers/{id}` | ADMIN | 200 |

Response luôn có `status`, `message`, `data`; status trong body trùng HTTP status. Xóa thành công trả `data: null`. Không tìm thấy: 404; chưa xác thực/token sai: 401; thiếu quyền: 403; trùng mã hoặc xung đột dữ liệu liên quan: 409; đầu vào sai: 400.

Body tạo khách:

```json
{
  "customerCode": "DEMO-001",
  "name": "Khách giả lập 001",
  "country": "VN",
  "signupMethod": "EMAIL",
  "signedUpAt": "2026-11-24T09:00:00+07:00"
}
```

- `customerCode`: 1–40 ký tự sau khi trim; unique phân biệt hoa/thường, khớp schema.
- `name`: 1–200 ký tự sau khi trim.
- `country`: hai chữ cái viết hoa, ví dụ VN, KR; đây là kiểm tra định dạng, không phải tra cứu danh mục quốc gia.
- `signupMethod`: EMAIL / GOOGLE / MICROSOFT.
- `signedUpAt`: ISO 8601 có timezone; không nhận datetime thiếu timezone.
- Từ chối thuộc tính không được khai báo, ví dụ `id`, `role`.
- PATCH nhận một hoặc nhiều trường trên. Bỏ qua trường không gửi; không nhận `null`, body rỗng hoặc chuỗi chỉ có khoảng trắng.
- Không sửa ngày đăng ký vượt quá thời điểm đơn/kết quả AI đã tồn tại.
- Không xóa khách đã có đơn hoặc kết quả AI, giữ nguyên dữ liệu liên quan.

Danh sách có `page` (mặc định 1), `size` (mặc định 20, tối đa 100), `q` (tìm tên/mã), `country`, `signupMethod`. Sắp xếp cố định `id DESC`. `q` tìm chuỗi literal, không coi `%`/`_` là wildcard của người dùng. Response `data` chứa `items`, `page`, `size`, `total`, `totalPages`; trang vượt phạm vi trả danh sách rỗng.

## Bàn giao cho thành viên D

Các endpoint khách hàng phải tích hợp JWT thật. Không lấy vai trò từ header tự khai báo. Token dùng `sub` là ID của `members` dạng chuỗi và có `exp`; backend đọc vai trò hiện tại từ database để tránh dùng quyền cũ trong token. Thành viên D chịu trách nhiệm đăng nhập, phát hành/thu hồi token và thay dependency xác thực khi tích hợp cơ chế JWT chung.

Triển khai hiện tại dùng HS256 với `JWT_SECRET` tối thiểu 32 byte, cố định thuật toán khi verify. Đăng nhập/logout và kiểm tra danh sách token đã thu hồi chưa thuộc phần A. `scripts/create_demo_token.py` là công cụ local để thử seed, không được gắn thành endpoint.

## Transaction và tích hợp database

- `app/db.py:get_connection` cung cấp một kết nối dùng chung cho các dependency trong request. Thành công thì commit; lỗi thì rollback. Dependency có `scope='function'` để kết thúc transaction trước khi trả response thành công.
- POST/PATCH dựa vào unique constraint của PostgreSQL; không chỉ kiểm tra tồn tại trước khi ghi, nên hai request cùng mã vẫn chỉ có một request thành công.
- DELETE dựa vào FK `RESTRICT`, tránh khoảng trống giữa bước kiểm tra và bước xóa.
- PATCH chỉ xây dựng tên cột từ whitelist cố định; toàn bộ giá trị đều truyền dưới dạng query parameters.
- Danh sách lấy tổng số và dữ liệu trang trong một SQL statement, sử dụng cùng snapshot.
- Không tự tạo bảng khi ứng dụng khởi động. Nạp `database/schema.sql` một lần trước khi chạy; không nạp lại schema/seed vào database đang có dữ liệu.

Tham khảo cơ chế [dependency có yield của FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/) và [transaction của Psycopg](https://www.psycopg.org/psycopg3/docs/basic/transactions.html).

## Checklist bàn giao phần A

- [x] ERD 5 bảng, PK/FK và quan hệ 1–N.
- [x] Schema PostgreSQL và kiểm tra ràng buộc nghiệp vụ.
- [x] Script sinh ≥50 khách, dữ liệu ≥30 ngày, không dùng thông tin cá nhân thật.
- [x] POST/GET danh sách/GET chi tiết/PATCH/DELETE khách hàng.
- [x] Kiểm tra dữ liệu, unique mã, chặn xóa/sửa ngày gây xung đột.
- [x] Phân trang, tìm kiếm và bộ lọc.
- [x] Swagger/OpenAPI, response và lỗi thống nhất.
- [x] Điểm tích hợp xác thực/phân quyền với phần D.
- [x] Kiểm thử HTTP trên PostgreSQL thật và hướng dẫn chạy.
