"""Generate the editable Vietnamese presentation delivered with the assignment."""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
NAVY, INK, BLUE, LIGHT, WHITE = '203864','172B4D','176B87','EFF4FA','FFFFFF'
slides = [
('GENIE VINA', 'API chỉ số vận hành dịch vụ', [
    'Connext GNOM · Estimator / Studio',
    'REST API · PostgreSQL · JWT · Kiểm thử',
    'Nhóm G04 — KITS 2026'],
    'Mở đầu: dữ liệu đăng ký, thanh toán, hoàn tiền đang phân tán. Hệ thống tập trung dữ liệu và đưa ra định nghĩa chỉ số rõ ràng.'),
('01 / BÀI TOÁN', 'Từ dữ liệu rời rạc đến chỉ số nhất quán', [
    'Quản lý khách hàng, đơn hàng và từng lần dùng AI.',
    'Theo dõi chuyển trạng thái: ai đổi, khi nào, vì sao.',
    'Báo cáo khách trả phí, đăng ký, doanh thu và hoàn tiền.',
    'Đầu ra: 16 thao tác HTTP, Swagger, test, tài liệu và PPT.'],
    'Phạm vi là quản lý bản ghi nghiệp vụ. QUOTE là một báo giá, WEBSITE là một website; không cần tích hợp mô hình AI hoặc cổng thanh toán.'),
('02 / KIẾN TRÚC', 'Một luồng request, một transaction', [
    'Client / Swagger → FastAPI → xác thực JWT → kiểm tra quyền.',
    'Pydantic kiểm tra request; SQL dùng tham số hóa.',
    'PostgreSQL kiểm tra unique, FK, ngày và trạng thái.',
    'Commit trước response; có lỗi thì rollback toàn bộ.'],
    'Giải thích dependency scope=function: transaction hoàn tất trước khi trả thành công. API và database cùng bảo vệ nghiệp vụ; database vẫn an toàn khi có ghi đồng thời.'),
('03 / DỮ LIỆU', 'ERD: 5 bảng nghiệp vụ', [],
    'Mỗi bảng con thuộc một cha; quan hệ 1:N. customer_code unique, email unique không phân biệt hoa/thường. FK RESTRICT bảo toàn dữ liệu. Bảng kỹ thuật revoked_tokens có token_hash PK và expires_at; không nằm trong 5 bảng nghiệp vụ.'),
('04 / QUYẾT ĐỊNH', 'Thiết kế để kiểm soát tính đúng', [
    'NUMERIC(18,2) và Decimal: tránh sai số tiền.',
    'TIMESTAMPTZ; ngày báo cáo theo Asia/Ho_Chi_Minh.',
    'FK RESTRICT: từ chối xóa khách có đơn hoặc AI.',
    'created_at bổ sung để kiểm tra sự kiện sau đăng ký.',
    'Mật khẩu PBKDF2; JWT đã logout lưu bằng SHA-256.'],
    'Hoàn tiền toàn bộ amount, giữ paid_at và thêm refunded_at. Không lưu password thô hay token thô. Tiền API trả chuỗi thập phân để giữ chính xác.'),
('05 / API', '16 thao tác, chung một hợp đồng', [
    'Xác thực: login / logout — 2 thao tác.',
    'Khách hàng: tạo, danh sách, chi tiết, sửa, xóa — 5.',
    'Đơn hàng + trạng thái + lịch sử — 5.',
    'Kết quả AI: ghi nhận / tra cứu — 2.',
    'Thống kê: summary / daily — 2.'],
    'Mở Swagger để xem model request/response, Bearer auth và lỗi. Response luôn có status, message, data. OpenAPI được xuất trực tiếp từ runtime, tránh hợp đồng lệch code.'),
('06 / PHÂN QUYỀN', 'Quyền được đọc từ database mỗi request', [
    'ADMIN: toàn bộ chức năng, gồm xóa khách.',
    'OPERATOR: nhập/sửa dữ liệu, đổi trạng thái đơn.',
    'VIEWER: chỉ đọc và xem thống kê.',
    'JWT HS256, thời hạn 30 phút; logout thu hồi bền vững.',
    'Role client tự khai không thay đổi quyền thực tế.'],
    'Demo VIEWER POST bị 403. Demo logout rồi dùng lại token nhận 401. Role từ database có hiệu lực ngay, không chờ token hết hạn.'),
('07 / TRẠNG THÁI', 'Chuyển trạng thái có kiểm soát', [
    'PENDING → PAID hoặc FAILED; PAID → REFUNDED.',
    'Không cho quay lại trạng thái cũ hay chuyển tùy ý.',
    'Lý do bắt buộc; người đổi lấy từ JWT.',
    'Khóa hàng FOR UPDATE bảo vệ thanh toán đồng thời.',
    'Trigger ghi lịch sử cùng transaction cập nhật đơn.'],
    'Hai request thanh toán cùng lúc: một thành công, một bị từ chối vì trạng thái đã PAID. Chỉ một dòng lịch sử. Nếu trigger thất bại, thay đổi trạng thái cũng rollback.'),
('08 / CHỈ SỐ 1–2', 'Đếm khách đúng, so sánh đúng kỳ', [
    'Khách trả phí: distinct khách có đơn hiện PAID trong kỳ.',
    'Lần đầu: MIN(paidAt) trên toàn bộ đơn hiện PAID.',
    'Mua lại = tổng khách trả phí − khách lần đầu.',
    'Đăng ký mới: signedUpAt trong khoảng báo cáo.',
    'Tăng trưởng so kỳ trước cùng số ngày; trước = 0 → null.'],
    'Một khách có nhiều đơn trong kỳ chỉ đếm một lần. Khách lần đầu mua hai lần trong cùng kỳ vẫn thuộc nhóm lần đầu, không thuộc cả hai nhóm. Tra lịch sử trước kỳ là bắt buộc.'),
('09 / CHỈ SỐ 3–4', 'Doanh thu, hoàn tiền và ngày không giao dịch', [
    'Doanh thu: SUM(amount), chỉ đơn hiện PAID theo paidAt.',
    'Trung bình ngày = doanh thu / toàn bộ số ngày trong kỳ.',
    'Hoàn tiền: tổng amount và số đơn theo refundedAt.',
    'Daily tạo đủ từng ngày; không giao dịch trả 0.',
    'Khoảng [from 00:00, ngày sau to 00:00), UTC+07.'],
    'Không tự trừ hoàn tiền khỏi doanh thu. Vì đơn hợp lệ phải đang PAID, hoàn tiền có thể làm thay đổi doanh thu của kỳ thanh toán cũ. Đây là hệ quả trực tiếp từ định nghĩa của đề.'),
('10 / KIỂM CHỨNG', 'Test các trường hợp dễ tính sai', [
    'Unit: distinct, mua lại, kỳ trước, chia 0, số thập phân.',
    'Biên ngày UTC+07, ngày trống, hoàn tiền ngoài kỳ.',
    'HTTP trên PostgreSQL: CRUD, role, JWT, logout.',
    'Đổi trạng thái đồng thời và lịch sử tự động.',
    'Seed tái lập: 60 khách, 30 ngày, dữ liệu tổng hợp.'],
    'Chạy lệnh trong README để có số test mới nhất. Schema kiểm thử ngẫu nhiên, tự xóa khi xong; không dùng database nghiệp vụ. Không có TEST_DATABASE_URL thì HTTP tests bị skip, không tính là đã kiểm chứng.'),
('11 / DEMO', 'Một kịch bản nối dữ liệu với báo cáo', [
    'Login ADMIN → tạo khách → tạo đơn PENDING.',
    'Đổi PAID → xem lịch sử → xem summary/daily.',
    'Đổi REFUNDED → đối chiếu doanh thu và hoàn tiền.',
    'Login VIEWER → thử ghi dữ liệu bị 403.',
    'Logout → dùng lại token bị 401.'],
    'Dùng from=2026-10-26 và to=2026-11-24 để xem seed; dùng ngày hiện tại Việt Nam để xem đơn demo mới. Không cần giả mạo thời điểm payment vì server tự ghi thời điểm thật.'),
('12 / BÀN GIAO', 'Code, bằng chứng và review của nhóm', [
    'A: ERD/seed/khách; B: đơn/AI; C: thống kê/test.',
    'D: xác thực/Swagger; E: Git/tài liệu/thuyết trình.',
    'Nhánh feature riêng; PR có mô tả và lệnh kiểm chứng.',
    'Review độc lập trước merge; không push trực tiếp main.',
    'GitHub + OpenAPI + hướng dẫn demo + PPT chỉnh sửa được.'],
    'Nhóm điền tên thành viên thật, thực hiện review và nộp link theo quy định lớp. Không giả lịch sử làm việc hoặc reviewer. Nêu hướng mở rộng: SQL aggregation cho dữ liệu lớn, rate limiting, vận hành production nếu có yêu cầu tiếp theo.'),
]


def box(slide,x,y,w,h,text='',fill=LIGHT,size=18,color=INK):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,Inches(x),Inches(y),Inches(w),Inches(h))
    shape.fill.solid(); shape.fill.fore_color.rgb = RGBColor.from_string(fill)
    shape.line.fill.background()
    tf = shape.text_frame; tf.clear(); tf.word_wrap=True
    tf.margin_left=Inches(.2); tf.margin_top=Inches(.12)
    for i,line in enumerate(text.split('\n')):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph()
        p.text=line;p.font.name='Arial';p.font.size=Pt(size);p.font.color.rgb=RGBColor.from_string(color)
        p.space_after=Pt(6)
    return shape


def text(slide,x,y,w,h,value,size,color=INK,bold=False):
    shape=slide.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h))
    tf=shape.text_frame;tf.word_wrap=True
    for i,line in enumerate(value.split('\n')):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph();p.text=line
        p.font.name='Arial';p.font.size=Pt(size);p.font.bold=bold;p.font.color.rgb=RGBColor.from_string(color)
    return shape


def main():
    prs=Presentation();prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
    for i,(label,title,items,notes) in enumerate(slides):
        slide=prs.slides.add_slide(prs.slide_layouts[6])
        slide.background.fill.solid();slide.background.fill.fore_color.rgb=RGBColor.from_string(WHITE)
        box(slide,0,0,13.333,.12,fill=BLUE)
        text(slide,.65,.38,12,.35,label,13,BLUE,True)
        text(slide,.65,.95,12,1.05,title,30,NAVY,True)
        if i==3:
            box(slide,.6,2.2,3.4,2.55,'customers\nid PK · customer_code UK\nname · country\nsignup_method\nsigned_up_at',size=17)
            box(slide,4.8,2.2,3.4,2.65,'orders\nid PK · customer_id FK\npackage_name · amount\nstatus · created_at\npaid_at · refunded_at',size=17)
            box(slide,9,2.2,3.7,2.65,'order_status_histories\nid PK · order_id FK\nchanged_by FK\nprevious_status · new_status\nreason · changed_at',size=16)
            box(slide,.6,5.1,3.4,1.5,'ai_results\nid PK · customer_id FK\ntype · created_at',size=17)
            box(slide,9,5.1,3.7,1.5,'members\nid PK · email UK · name\npassword_hash · role · created_at',size=15)
            text(slide,4.0,3.25,.8,.4,'1 → N',12,BLUE,True)
            text(slide,8.2,3.25,.8,.4,'1 → N',12,BLUE,True)
            text(slide,1.3,4.72,2,.35,'1 ↓ N',12,BLUE,True)
            text(slide,9.8,4.74,2,.35,'N ↑ 1',12,BLUE,True)
        else:
            for n,item in enumerate(items):
                box(slide,.7,2.25+n*.79,.52,.52,f'{n+1:02}',fill=NAVY,size=12,color=WHITE)
                text(slide,1.45,2.23+n*.79,11.1,.7,item,21)
        text(slide,.7,7.02,11,.25,'G04  /  GENIE VINA  /  CONNEXT GNOM',10,BLUE)
        text(slide,12,6.98,.65,.3,f'{i+1:02}',12,NAVY,True)
        slide.notes_slide.notes_text_frame.text=notes
    dest=ROOT/'docs/Genie-Vina.pptx';prs.save(dest)
    reopened=Presentation(dest)
    assert len(reopened.slides)==len(slides)
    for slide in reopened.slides:
        assert slide.notes_slide.notes_text_frame.text
        for shape in slide.shapes:
            assert shape.left>=0 and shape.top>=0
            assert shape.left+shape.width<=prs.slide_width+10
            assert shape.top+shape.height<=prs.slide_height+10
    print(f'Generated and checked {len(slides)} slides: {dest.name}')


if __name__=='__main__':
    main()
