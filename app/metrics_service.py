"""Logic tính chỉ số vận hành (Thành viên C).

Gồm 2 phần:
  1. Hàm thuần (không đụng DB) -> dễ unit test.
  2. PostgresMetricsRepository -> chạy SQL theo schema database/schema.sql.

Quy ước lấy từ docs/erd.md:
  - from/to là NGÀY, bao gồm cả hai đầu, tính theo múi giờ Asia/Ho_Chi_Minh (UTC+7).
  - Kỳ trước có cùng số ngày, liền ngay trước kỳ hiện tại.
  - Đơn hợp lệ = status PAID, tính theo paid_at.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable, Protocol

VN_TZ = timezone(timedelta(hours=7))  # Việt Nam không có DST
MAX_RANGE_DAYS = 366                  # chặn truy vấn quá lớn
TWO_PLACES = Decimal("0.01")


class InvalidRangeError(ValueError):
    """from/to không hợp lệ -> API trả 400."""


# --------------------------------------------------------------------------- #
# Khoảng thời gian
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DateRange:
    start: date  # bao gồm
    end: date    # bao gồm

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def start_at(self) -> datetime:
        return datetime.combine(self.start, time.min, tzinfo=VN_TZ)

    @property
    def end_at(self) -> datetime:
        """Mốc loại trừ: 00:00 của ngày sau `end` -> khoảng nửa mở [start_at, end_at)."""
        return datetime.combine(self.end + timedelta(days=1), time.min, tzinfo=VN_TZ)

    def contains(self, moment: datetime) -> bool:
        return self.start_at <= moment < self.end_at

    def previous(self) -> "DateRange":
        d = self.days
        return DateRange(self.start - timedelta(days=d), self.start - timedelta(days=1))

    def iter_days(self) -> Iterable[date]:
        for i in range(self.days):
            yield self.start + timedelta(days=i)

    def to_dict(self) -> dict:
        return {"from": self.start.isoformat(), "to": self.end.isoformat(), "days": self.days}


def parse_range(from_value: str | None, to_value: str | None) -> DateRange:
    """Chuyển chuỗi YYYY-MM-DD thành DateRange, ném InvalidRangeError nếu sai."""
    if not from_value or not to_value:
        raise InvalidRangeError("Thiếu tham số from hoặc to (định dạng YYYY-MM-DD)")
    try:
        start = date.fromisoformat(from_value)
        end = date.fromisoformat(to_value)
    except ValueError:
        raise InvalidRangeError("from/to phải có định dạng YYYY-MM-DD") from None
    if start > end:
        raise InvalidRangeError("from không được lớn hơn to")
    if (end - start).days + 1 > MAX_RANGE_DAYS:
        raise InvalidRangeError(f"Khoảng thời gian tối đa {MAX_RANGE_DAYS} ngày")
    return DateRange(start, end)


# --------------------------------------------------------------------------- #
# Hàm tính toán thuần
# --------------------------------------------------------------------------- #
def money(value: Decimal) -> float:
    """Làm tròn 2 chữ số để trả JSON."""
    return float(Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def growth_rate(current: int, previous: int) -> float | None:
    """% tăng/giảm so với kỳ trước. Kỳ trước = 0 -> None (không xác định)."""
    if previous == 0:
        return None
    rate = (Decimal(current) - Decimal(previous)) / Decimal(previous) * 100
    return float(rate.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def classify_paying_customers(
    period_orders: Iterable[tuple[int, datetime]],
    first_paid_at: dict[int, datetime],
    period: DateRange,
) -> dict:
    """Chỉ số 1: khách trả phí (distinct), tách Lần đầu / Thanh toán lại.

    period_orders: (customer_id, paid_at) của đơn hợp lệ TRONG kỳ.
    first_paid_at: customer_id -> MIN(paid_at) trên toàn bộ lịch sử đơn PAID.
    Khách "lần đầu" nếu đơn hợp lệ đầu tiên của họ nằm trong kỳ; khách mua
    nhiều đơn trong kỳ đầu tiên vẫn chỉ tính 1 lần và thuộc nhóm "lần đầu".
    """
    earliest_in_period: dict[int, datetime] = {}
    for customer_id, paid_at in period_orders:
        current = earliest_in_period.get(customer_id)
        if current is None or paid_at < current:
            earliest_in_period[customer_id] = paid_at

    first_time = 0
    for customer_id, earliest in earliest_in_period.items():
        first = first_paid_at.get(customer_id, earliest)  # dự phòng nếu thiếu
        if period.contains(first):
            first_time += 1

    total = len(earliest_in_period)
    return {"total": total, "firstTime": first_time, "returning": total - first_time}


def total_revenue(amounts: Iterable[Decimal]) -> Decimal:
    return sum((Decimal(a) for a in amounts), Decimal("0"))


def average_per_day(revenue: Decimal, days: int) -> Decimal:
    """Trung bình/ngày chia cho TOÀN BỘ số ngày của kỳ (kể cả ngày doanh thu 0)."""
    return Decimal(revenue) / Decimal(days)


def local_date(moment: datetime) -> date:
    """Ngày theo giờ Việt Nam. Datetime không có tz được coi là UTC."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(VN_TZ).date()


def build_daily_revenue(
    paid_orders: Iterable[tuple[Decimal, datetime]], period: DateRange
) -> list[dict]:
    """Chỉ số 4: doanh thu từng ngày, đủ mọi ngày trong kỳ, ngày trống = 0."""
    buckets = {day: Decimal("0") for day in period.iter_days()}
    for amount, paid_at in paid_orders:
        day = local_date(paid_at)
        if day in buckets:  # bỏ qua dữ liệu ngoài kỳ
            buckets[day] += Decimal(amount)
    return [{"date": day.isoformat(), "revenue": money(value)} for day, value in buckets.items()]


# --------------------------------------------------------------------------- #
# Service (ghép repository + hàm thuần)
# --------------------------------------------------------------------------- #
class MetricsRepository(Protocol):
    def paid_orders(self, period: DateRange) -> list[tuple[int, Decimal, datetime]]: ...
    def first_paid_times(self, customer_ids: list[int]) -> dict[int, datetime]: ...
    def signup_count(self, period: DateRange) -> int: ...
    def refunds(self, period: DateRange) -> tuple[int, Decimal]: ...


class MetricsService:
    def __init__(self, repository: MetricsRepository):
        self.repo = repository

    def summary(self, period: DateRange) -> dict:
        """Chỉ số 1 + 2 + 3 cho GET /api/metrics/summary."""
        previous = period.previous()

        orders = self.repo.paid_orders(period)
        customer_ids = sorted({cid for cid, _, _ in orders})
        first_paid = self.repo.first_paid_times(customer_ids) if customer_ids else {}
        paying = classify_paying_customers(
            [(cid, paid_at) for cid, _, paid_at in orders], first_paid, period
        )

        signups = self.repo.signup_count(period)
        previous_signups = self.repo.signup_count(previous)

        revenue = total_revenue(amount for _, amount, _ in orders)
        refund_count, refund_amount = self.repo.refunds(period)

        return {
            "period": period.to_dict(),
            "previousPeriod": previous.to_dict(),
            "payingCustomers": paying,
            "newSignups": {
                "count": signups,
                "previousCount": previous_signups,
                "growthRate": growth_rate(signups, previous_signups),
            },
            "revenue": {
                "total": money(revenue),
                "averagePerDay": money(average_per_day(revenue, period.days)),
            },
            "refunds": {"totalAmount": money(refund_amount), "orderCount": refund_count},
        }

    def daily(self, period: DateRange) -> dict:
        """Chỉ số 4 cho GET /api/metrics/daily."""
        orders = self.repo.paid_orders(period)
        return {
            "period": period.to_dict(),
            "items": build_daily_revenue(((a, t) for _, a, t in orders), period),
        }


# --------------------------------------------------------------------------- #
# Repository PostgreSQL (psycopg 3). Nhận connection đã mở sẵn.
# Cursor luôn dùng dict_row nên chạy đúng với mọi row_factory của connection.
# --------------------------------------------------------------------------- #
class PostgresMetricsRepository:
    def __init__(self, connection):
        self.conn = connection

    def _cursor(self):
        from psycopg.rows import dict_row

        return self.conn.cursor(row_factory=dict_row)

    def paid_orders(self, period: DateRange):
        sql = """SELECT customer_id, amount, paid_at FROM orders
                 WHERE status = 'PAID' AND paid_at >= %s AND paid_at < %s"""
        with self._cursor() as cur:
            cur.execute(sql, (period.start_at, period.end_at))
            return [(r["customer_id"], r["amount"], r["paid_at"]) for r in cur.fetchall()]

    def first_paid_times(self, customer_ids: list[int]):
        sql = """SELECT customer_id, MIN(paid_at) AS first_paid_at FROM orders
                 WHERE status = 'PAID' AND customer_id = ANY(%s)
                 GROUP BY customer_id"""
        with self._cursor() as cur:
            cur.execute(sql, (customer_ids,))
            return {r["customer_id"]: r["first_paid_at"] for r in cur.fetchall()}

    def signup_count(self, period: DateRange) -> int:
        sql = """SELECT COUNT(*) AS total FROM customers
                 WHERE signed_up_at >= %s AND signed_up_at < %s"""
        with self._cursor() as cur:
            cur.execute(sql, (period.start_at, period.end_at))
            return cur.fetchone()["total"]

    def refunds(self, period: DateRange):
        # Theo refunded_at, KHÔNG lọc status PAID (đơn hoàn có status REFUNDED)
        sql = """SELECT COUNT(*) AS total, COALESCE(SUM(amount), 0) AS amount FROM orders
                 WHERE refunded_at >= %s AND refunded_at < %s"""
        with self._cursor() as cur:
            cur.execute(sql, (period.start_at, period.end_at))
            row = cur.fetchone()
            return row["total"], Decimal(row["amount"])