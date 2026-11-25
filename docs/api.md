# Hợp đồng API toàn hệ thống

Nguồn chính xác: Swagger `/docs`, `/openapi.json` và bản xuất `API/openapi.json`. `API/orders.yaml` là tập con đơn hàng/AI được sinh từ cùng model, dùng OpenAPI 3.1.0 của FastAPI. Tất cả response có `{ "status": 200, "message": "success", "data": ... }`. Lỗi cũng có ba trường, `data` có thể null hoặc chi tiết validation. Tiền `NUMERIC(18,2)` được trả dạng chuỗi thập phân, ví dụ `"500000.00"`.

## Endpoint và quyền

| Phương thức | Đường dẫn | Quyền | Mục đích |
|---|---|---|---|
| POST | `/api/auth/login` | Công khai | Đăng nhập, cấp JWT 30 phút |
| POST | `/api/auth/logout` | Cả ba vai trò | Thu hồi JWT đang dùng |
| POST | `/api/customers` | ADMIN, OPERATOR | Tạo khách |
| GET | `/api/customers` | Cả ba | Danh sách khách |
| GET | `/api/customers/{id}` | Cả ba | Chi tiết khách |
| PATCH | `/api/customers/{id}` | ADMIN, OPERATOR | Sửa khách |
| DELETE | `/api/customers/{id}` | ADMIN | Xóa khách không có dữ liệu liên quan |
| POST | `/api/orders` | ADMIN, OPERATOR | Tạo đơn PENDING |
| GET | `/api/orders` | Cả ba | Danh sách đơn |
| GET | `/api/orders/{id}` | Cả ba | Chi tiết đơn |
| PATCH | `/api/orders/{id}/status` | ADMIN, OPERATOR | Chuyển trạng thái, ghi lịch sử |
| GET | `/api/orders/{id}/status-history` | Cả ba | Lịch sử phân trang |
| POST | `/api/ai-results` | ADMIN, OPERATOR | Ghi nhận một lần dùng AI |
| GET | `/api/ai-results` | Cả ba | Tra cứu kết quả AI |
| GET | `/api/metrics/summary?from=&to=` | Cả ba | Chỉ số 1, 2, 3 |
| GET | `/api/metrics/daily?from=&to=` | Cả ba | Chỉ số 4 |

## JWT và mật khẩu

Login nhận `email`, `password`; email so sánh không phân biệt hoa/thường. Sai email hoặc mật khẩu trả cùng lỗi 401. Mật khẩu kiểm tra bằng PBKDF2-HMAC-SHA256 tương thích seed. JWT ký HS256, có sub, iat, exp và jti. Không tin role do client cung cấp: mỗi request đọc quyền hiện tại từ database.

Gửi `Authorization: Bearer <accessToken>` cho mọi endpoint trừ login. Logout lưu SHA-256 của token vào `revoked_tokens`, token lập tức không dùng được nữa, kể cả sau khi restart. Logout không thu hồi những phiên khác của cùng thành viên. Token thiếu/sai chữ ký/hết hạn/đã thu hồi trả 401 và Bearer challenge. Có thể định kỳ chạy `DELETE FROM revoked_tokens WHERE expires_at <= CURRENT_TIMESTAMP` để dọn bản ghi đã hết tác dụng.

## Đơn hàng và AI

Tạo đơn:

```json
{"customerId":1,"packageName":"Basic","amount":"500000.00"}
```

`amount` hữu hạn, >0, tối đa 18 chữ số và 2 chữ số thập phân; không nhận trạng thái ban đầu do client tự đặt. `createdAt` là ISO 8601 có timezone, tùy chọn, mặc định thời gian server. Khách phải tồn tại; thời điểm sự kiện không trước ngày đăng ký.

Đổi trạng thái:

```json
{"newStatus":"PAID","reason":"Đã xác nhận thanh toán"}
```

`reason` bắt buộc, trim, 1–500 ký tự. Chỉ `PENDING → PAID/FAILED`, `PAID → REFUNDED`; cùng trạng thái cũng bị từ chối 400. Server tự gán paidAt/refundedAt khi chuyển trạng thái. Hoàn tiền toàn bộ giá trị đơn; không có trường refund riêng. Server lấy changedBy từ JWT và ghi lịch sử bằng trigger trong cùng transaction. Response trả bản ghi lịch sử, gồm cả previousStatus và changedAt.

Khóa hàng `FOR UPDATE` tuần tự hóa hai request cùng đổi trạng thái: chỉ một request thanh toán được thành công, request còn lại đọc trạng thái mới và bị từ chối 400; chỉ có một dòng lịch sử. Lỗi ghi lịch sử rollback luôn thay đổi đơn.

Danh sách đơn: `page=1`, `limit=10` (tối đa 100), `customerId`, `orderStatus`, `search` (chuỗi literal của packageName), `sortBy=id|amount|paidAt|createdAt`, `order=asc|desc`. Lịch sử nhận `page`, `limit`. Response danh sách:

```json
{"status":200,"message":"success","data":{"items":[],"pagination":{"page":1,"limit":10,"totalItems":0,"totalPages":0}}}
```

Ghi kết quả AI:

```json
{"customerId":1,"type":"QUOTE","createdAt":"2026-11-24T09:00:00+07:00"}
```

`type=QUOTE|WEBSITE`; createdAt tùy chọn. Một dòng là một lần dùng AI; đề không yêu cầu thực thi AI hoặc lưu nội dung kết quả. Tra cứu nhận `customerId`, `type`, `page`, `limit`, `sortBy=id|createdAt`, `order=asc|desc`.

API khách hàng giữ hợp đồng phân trang `size` của phần A; chi tiết trong [customer-api.md](customer-api.md).

## Thống kê

Hai API bắt buộc `from`, `to` là ngày `YYYY-MM-DD`. Bao gồm cả hai ngày ở múi giờ Asia/Ho_Chi_Minh. Chuyển thành `[from 00:00, ngày sau to 00:00)`; khoảng tối đa 3660 ngày và phải tồn tại kỳ trước trong lịch. Ngày đảo ngược/không hợp lệ/thiếu tham số trả 400.

Summary trả `fromDate`, `toDate`, `days`, `timezone` và:

| Trường | Công thức |
|---|---|
| payingCustomers | Distinct khách có đơn hiện PAID, paidAt trong kỳ |
| firstTimeCustomers | Khách trả phí có lần PAID hợp lệ đầu tiên trong toàn bộ lịch sử nằm trong kỳ |
| returningCustomers | payingCustomers − firstTimeCustomers |
| newRegistrations | Số signedUpAt trong kỳ |
| previousRegistrations | Số đăng ký kỳ liền trước cùng số ngày |
| registrationGrowthPercent | (hiện tại − trước) / trước × 100; null nếu trước = 0 |
| revenue | Tổng amount của đơn hiện PAID, paidAt trong kỳ |
| averageDailyRevenue | revenue / số ngày, gồm ngày không giao dịch |
| refundAmount | Tổng amount đơn có refundedAt trong kỳ |
| refundCount | Số đơn có refundedAt trong kỳ |

Daily trả metadata như summary và `items: [{"date":"2026-11-24","revenue":"0.00"}]`, đủ từng ngày theo thứ tự tăng dần. Tiền/tỷ lệ làm tròn HALF_UP đến 2 chữ số thập phân. Không tự trừ hoàn tiền khỏi revenue. Đơn REFUNDED không còn hợp lệ, vì vậy báo cáo của kỳ cũ có thể thay đổi sau hoàn tiền — đúng định nghĩa status=PAID của đề.

Truy vấn thống kê lấy dữ liệu khách và đơn trong cùng một SQL statement để dùng chung snapshot. Triển khai tham chiếu tính trên Python bằng Decimal, phù hợp dữ liệu bài tập; dữ liệu lớn cần chuyển aggregation về PostgreSQL và đo hiệu năng.

## Mã lỗi

400: đầu vào hoặc chuyển trạng thái sai; 401: chưa xác thực; 403: thiếu quyền; 404: tài nguyên không tồn tại; 409: unique/FK/ràng buộc dữ liệu; 500: lỗi nội bộ; 503: database không sẵn sàng. Không trả SQL, mật khẩu hoặc chi tiết kết nối cho client. Không bắt buộc UI frontend trong phạm vi đề.

## Mẫu đối chiếu dữ liệu seed mặc định

Ngay sau khi nạp seed mặc định, chưa sửa dữ liệu, gọi summary với `from=2026-10-26&to=2026-11-24` sẽ có:

```json
{
  "payingCustomers": 31,
  "firstTimeCustomers": 30,
  "returningCustomers": 1,
  "newRegistrations": 26,
  "previousRegistrations": 34,
  "registrationGrowthPercent": "-23.53",
  "revenue": "11354000.00",
  "averageDailyRevenue": "378466.67",
  "refundAmount": "3087000.00",
  "refundCount": 13
}
```

Daily có 30 ngày, tổng doanh thu bằng `11354000.00`; ngày 24/11/2026 có doanh thu `0.00`. Khi thay tham số seed hoặc chỉnh dữ liệu, kết quả thay đổi tương ứng.
