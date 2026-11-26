"""Generate the editable English presentation delivered with the assignment."""
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
NAVY, INK, BLUE, LIGHT, WHITE = '203864','172B4D','176B87','EFF4FA','FFFFFF'
slides = [
('GENIE VINA', 'Service Operations Metrics API', [
    'Connext GNOM · Estimator / Studio',
    'REST API · PostgreSQL · JWT · Automated Testing',
    'Team G04 — KITS 2026'],
    'Registration, payment, and refund data is scattered across administration tools. This project centralizes operational records and defines consistent business metrics.'),
('01 / THE CHALLENGE', 'From scattered data to consistent metrics', [
    'Manage customers, orders, and individual AI usage events.',
    'Track status changes: who changed what, when, and why.',
    'Report paying customers, registrations, revenue, and refunds.',
    'Deliver 16 HTTP operations, Swagger, tests, docs, and slides.'],
    'The scope is operational record management. QUOTE represents one software estimate; WEBSITE represents one generated website. Integrating an AI model or payment gateway is outside the assignment scope.'),
('02 / ARCHITECTURE', 'One request, one transaction', [
    'Client / Swagger → FastAPI → JWT validation → permissions.',
    'Pydantic validates requests; SQL values are parameterized.',
    'PostgreSQL enforces uniqueness, foreign keys, dates, and states.',
    'Commit before responding; roll back the entire operation on error.'],
    'The database dependency uses scope=function so the transaction finishes before a successful response is sent. Both the API and the database enforce business rules, including during concurrent writes.'),
('03 / DATA MODEL', 'ERD: five business entities', [],
    'Each child record belongs to one parent, with one-to-many relationships. customer_code is unique; member email is unique regardless of case. Foreign keys use RESTRICT to preserve related records. The additional technical table revoked_tokens has token_hash as its primary key and expires_at; it is separate from the five business entities.'),
('04 / DESIGN DECISIONS', 'Designing for correctness', [
    'NUMERIC(18,2) and Decimal preserve monetary precision.',
    'TIMESTAMPTZ; reporting days use Asia/Ho_Chi_Minh.',
    'FK RESTRICT blocks deleting customers with orders or AI events.',
    'created_at ensures events do not precede customer registration.',
    'PBKDF2 password hashes; SHA-256 hashes for revoked JWTs.'],
    'Refunds cover the full order amount. The system preserves paid_at and sets refunded_at. Neither plaintext passwords nor raw revoked tokens are stored. Monetary values are returned as decimal strings to preserve precision.'),
('05 / REST API', '16 operations, one response contract', [
    'Authentication: login / logout — 2 operations.',
    'Customers: create, list, detail, update, delete — 5.',
    'Orders, status updates, and status history — 5.',
    'AI results: record / query — 2.',
    'Metrics: summary / daily — 2.'],
    'Swagger documents request and response models, Bearer authentication, and errors. Every response contains status, message, and data. OpenAPI is generated from the running application models to keep the contract consistent with the code.'),
('06 / ACCESS CONTROL', 'Check current permissions on every request', [
    'ADMIN: all operations, including customer deletion.',
    'OPERATOR: create and update records; change order status.',
    'VIEWER: read records and view metrics only.',
    'HS256 JWTs expire after 30 minutes; logout revokes the token.',
    'Client-supplied role claims do not grant permissions.'],
    'Demonstrate a VIEWER write request returning 403. Log out and reuse the same token to receive 401. Roles are loaded from the database on every request, so role changes take effect without waiting for token expiry. Revocation persists across application restarts.'),
('07 / ORDER LIFECYCLE', 'Controlled transitions with an audit trail', [
    'PENDING → PAID or FAILED; PAID → REFUNDED.',
    'Reject reverse transitions and all unsupported state changes.',
    'A reason is required; the actor is identified through the JWT.',
    'FOR UPDATE row locks serialize concurrent payment requests.',
    'A trigger records history within the order update transaction.'],
    'If two requests attempt to pay the same order, one succeeds and the other is rejected after observing the updated PAID status. Only one history entry is created. If the history trigger fails, the order status update is rolled back as well.'),
('08 / METRICS 1–2', 'Count customers and compare equal periods', [
    'Paying customers: distinct customers with PAID orders in range.',
    'First-time: earliest paidAt across all currently PAID orders.',
    'Returning customers = paying customers − first-time customers.',
    'New registrations: signedUpAt within the reporting period.',
    'Growth uses an equal-length prior period; prior = 0 → null.'],
    'Count each paying customer once even if they place several orders. A customer whose first valid payment falls in the reporting period remains first-time even if they pay twice in that period. The first payment must be determined using all prior history, not just the requested period.'),
('09 / METRICS 3–4', 'Revenue, refunds, and days without sales', [
    'Revenue: SUM(amount) for currently PAID orders, by paidAt.',
    'Average daily revenue = revenue / all days in the period.',
    'Refunds: total amount and order count, by refundedAt.',
    'Daily revenue includes every date; days without sales return 0.',
    'Range: [from 00:00, day after to 00:00), UTC+07.'],
    'Do not subtract refunds from the defined revenue metric. Because a valid order must currently be PAID, refunding an order can change the report for its original payment period. This follows the assignment definition. Both from and to are included as local calendar days.'),
('10 / VERIFICATION', 'Test the cases that are easy to miscount', [
    'Unit tests: distinct counts, repeat buyers, growth, and decimals.',
    'UTC+07 boundaries, empty days, and refunds outside the period.',
    'HTTP tests on PostgreSQL: CRUD, roles, JWTs, and logout.',
    'Concurrent status updates and automatic history recording.',
    'Reproducible seed: 60 customers, 30 days, synthetic identities.'],
    'Run the README commands for the latest test count. Integration tests use randomly named schemas and clean them up afterwards, without modifying business tables in the default schema. Without TEST_DATABASE_URL, HTTP tests are skipped and must not be reported as verified.'),
('11 / LIVE DEMO', 'Connect operational events to the reports', [
    'Log in as ADMIN → create a customer → create a PENDING order.',
    'Mark it PAID → inspect history → view summary and daily metrics.',
    'Mark it REFUNDED → compare revenue and refund figures.',
    'Log in as VIEWER → attempt a write and receive 403.',
    'Log out → reuse the token and receive 401.'],
    'Use from=2026-10-26 and to=2026-11-24 for the default seed dataset. Use the current date in Vietnam for newly created demo payments. The server records the real payment timestamp, so new payments do not appear in the old seed period.'),
('12 / HANDOVER', 'Code, evidence, and team review', [
    'A: ERD / seed / customers; B: orders / AI; C: metrics / tests.',
    'D: authentication / Swagger; E: Git / docs / presentation.',
    'Use feature branches and PRs with clear validation steps.',
    'Require independent review before merging into main.',
    'Deliver GitHub, OpenAPI, a demo guide, and editable slides.'],
    'The team must enter real member names, complete an independent review, and submit the required links. Do not invent contribution history or reviewers. Possible extensions include SQL aggregation for larger datasets, login rate limiting, and production operations if the scope expands.'),
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
    prs=Presentation();prs.core_properties.language='en-US';prs.slide_width=Inches(13.333);prs.slide_height=Inches(7.5)
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
