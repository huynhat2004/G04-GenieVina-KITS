# Kịch bản thuyết trình và demo

File chỉnh sửa được: [Genie-Vina.pptx](Genie-Vina.pptx), 13 slide có speaker notes. Sinh lại bằng `python scripts/build_presentation.py` sau khi cài `requirements-tools.txt`.

## Phân bổ 10–12 phút

| Slide | Nội dung | Thời gian |
|---|---|---|
| 1–2 | Bối cảnh, vấn đề và phạm vi | 1 phút |
| 3–5 | Kiến trúc, ERD và quyết định kỹ thuật | 2 phút |
| 6–8 | API, phân quyền và trạng thái/audit | 2 phút |
| 9–10 | Giải thích bốn chỉ số và tình huống biên | 2 phút |
| 11 | Bằng chứng kiểm thử | 1 phút |
| 12 | Demo | 2–3 phút |
| 13 | Phân công, Git và bàn giao | 1 phút |

## Demo qua Swagger

1. Chạy schema, seed và ứng dụng theo README. Mở `/docs`.
2. `POST /api/auth/login` với `admin@example.invalid` / `DemoOnly!2026`. Copy accessToken vào Authorize.
3. `GET /api/metrics/summary?from=2026-10-26&to=2026-11-24`, rồi daily cùng kỳ. Chỉ ra ngày 0; tổng daily bằng revenue; hai nhóm khách không trùng nhau.
4. Tạo khách có customerCode riêng (ví dụ `DEMO-LIVE-001`, đổi mã nếu chạy lại), ngày đăng ký `2026-11-24T09:00:00+07:00`. Tạo đơn Basic amount `500000` cho ID nhận được. Trạng thái ban đầu PENDING.
5. Đổi trạng thái sang PAID với lý do. Xem chi tiết và `/status-history`, chỉ ra changedBy lấy từ JWT.
6. Xem summary/daily với from=to=ngày demo hiện tại theo giờ Việt Nam. Thanh toán ghi thời điểm thật của server nên không xuất hiện trong kỳ seed cũ.
7. Chuyển REFUNDED với lý do, xem lại summary. Đơn không còn tính doanh thu PAID; refundAmount/refundCount tăng. Thử chuyển ngược PAID nhận 400.
8. Thử xóa khách có đơn nhận 409. Ghi nhận QUOTE hoặc WEBSITE và lọc theo customerId.
9. Login viewer@example.invalid, thay token trong Authorize. GET thành công; POST khách hoặc đổi trạng thái trả 403.
10. Logout, dùng lại token để GET nhận 401. Chạy pytest để trình bày kết quả kiểm chứng.

## Câu hỏi nên giải thích được

- Vì sao có createdAt của orders ngoài đề? Để kiểm tra tạo đơn sau đăng ký và thanh toán sau tạo đơn.
- Vì sao dùng Decimal/NUMERIC? Không phát sinh sai số nhị phân khi cộng tiền; API trả chuỗi thập phân.
- Vì sao khách mua hai lần trong kỳ đầu không là khách mua lại? Hai nhóm phân hoạch theo lần PAID đầu tiên trên toàn lịch sử.
- Vì sao hoàn tiền có thể đổi doanh thu kỳ cũ? Đề chỉ coi status hiện PAID là hợp lệ, nên REFUNDED bị loại.
- Vì sao dùng trigger và khóa hàng? Bảo vệ tính nhất quán khi có nhiều request và khi thao tác trực tiếp database.
- Vì sao tăng trưởng null khi kỳ trước 0? Phép chia không xác định; không gán tùy tiện 100%.
- Vì sao không dùng role từ JWT? Quyền hiện tại có thể thay đổi trước khi token hết hạn.
- Tại sao thêm revoked_tokens? JWT tự chứa không thể bị thu hồi ngay nếu không lưu trạng thái bổ sung.

Trước khi nộp, nhóm điền tên thành viên thật và xác nhận review PR độc lập. Không có dữ liệu cá nhân thật trong seed.
