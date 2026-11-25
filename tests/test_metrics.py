"""Unit test logic thống kê (Thành viên C). Chạy: python3 -m unittest discover -s tests -v"""
import sys
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.metrics_service import (  # noqa: E402
    VN_TZ, DateRange, InvalidRangeError, MetricsService, average_per_day,
    build_daily_revenue, classify_paying_customers, growth_rate, parse_range, total_revenue,
)

D = Decimal


def vn(y, m, d, h=12, mi=0):
    return datetime(y, m, d, h, mi, tzinfo=VN_TZ)


PERIOD = DateRange(date(2026, 11, 1), date(2026, 11, 10))  # 10 ngày


class FakeRepo:
    def __init__(self, orders=(), first=None, signups=None, refunds=(0, D(0))):
        self._orders, self._first = list(orders), first or {}
        self._signups, self._refunds = signups or {}, refunds

    def paid_orders(self, period):
        return [o for o in self._orders if period.contains(o[2])]

    def first_paid_times(self, ids):
        return {i: self._first[i] for i in ids if i in self._first}

    def signup_count(self, period):
        return self._signups.get(period.start, 0)

    def refunds(self, period):
        return self._refunds


class ParseRangeTests(unittest.TestCase):
    def test_valid(self):
        r = parse_range("2026-11-01", "2026-11-10")
        self.assertEqual((r.start, r.end, r.days), (date(2026, 11, 1), date(2026, 11, 10), 10))

    def test_single_day(self):
        self.assertEqual(parse_range("2026-11-05", "2026-11-05").days, 1)

    def test_invalid_inputs(self):
        for a, b in [(None, "2026-11-01"), ("2026-11-01", None), ("abc", "2026-11-01"),
                     ("2026-13-01", "2026-13-02"), ("2026-11-10", "2026-11-01"),
                     ("2025-01-01", "2026-11-01")]:
            with self.subTest(a=a, b=b), self.assertRaises(InvalidRangeError):
                parse_range(a, b)

    def test_boundaries_half_open_utc7(self):
        self.assertTrue(PERIOD.contains(vn(2026, 11, 1, 0, 0)))
        self.assertTrue(PERIOD.contains(vn(2026, 11, 10, 23, 59)))
        self.assertFalse(PERIOD.contains(vn(2026, 11, 11, 0, 0)))
        self.assertFalse(PERIOD.contains(vn(2026, 10, 31, 23, 59)))

    def test_previous_period_same_length(self):
        p = PERIOD.previous()
        self.assertEqual((p.start, p.end, p.days), (date(2026, 10, 22), date(2026, 10, 31), 10))


class GrowthTests(unittest.TestCase):
    def test_increase(self):
        self.assertEqual(growth_rate(15, 10), 50.0)

    def test_decrease(self):
        self.assertEqual(growth_rate(5, 10), -50.0)

    def test_same(self):
        self.assertEqual(growth_rate(10, 10), 0.0)

    def test_previous_zero_is_none(self):
        self.assertIsNone(growth_rate(5, 0))
        self.assertIsNone(growth_rate(0, 0))

    def test_rounding(self):
        self.assertEqual(growth_rate(2, 3), -33.33)


class PayingCustomerTests(unittest.TestCase):
    def test_first_vs_returning(self):
        orders = [(1, vn(2026, 11, 2)), (2, vn(2026, 11, 3))]
        first = {1: vn(2026, 10, 1), 2: vn(2026, 11, 3)}  # KH1 mua lại, KH2 lần đầu
        r = classify_paying_customers(orders, first, PERIOD)
        self.assertEqual(r, {"total": 2, "firstTime": 1, "returning": 1})

    def test_distinct_when_multiple_orders(self):
        orders = [(1, vn(2026, 11, 2)), (1, vn(2026, 11, 5)), (1, vn(2026, 11, 8))]
        r = classify_paying_customers(orders, {1: vn(2026, 10, 1)}, PERIOD)
        self.assertEqual(r["total"], 1)
        self.assertEqual(r["returning"], 1)

    def test_multiple_orders_in_first_period_counted_once_as_first(self):
        orders = [(1, vn(2026, 11, 2)), (1, vn(2026, 11, 5))]
        r = classify_paying_customers(orders, {1: vn(2026, 11, 2)}, PERIOD)
        self.assertEqual(r, {"total": 1, "firstTime": 1, "returning": 0})

    def test_groups_sum_to_total(self):
        orders = [(i, vn(2026, 11, 1 + i % 9)) for i in range(1, 21)]
        first = {i: (vn(2026, 11, 1 + i % 9) if i % 3 else vn(2026, 9, 1)) for i in range(1, 21)}
        r = classify_paying_customers(orders, first, PERIOD)
        self.assertEqual(r["firstTime"] + r["returning"], r["total"])

    def test_empty(self):
        self.assertEqual(classify_paying_customers([], {}, PERIOD),
                         {"total": 0, "firstTime": 0, "returning": 0})

    def test_missing_first_paid_falls_back_to_period(self):
        r = classify_paying_customers([(9, vn(2026, 11, 4))], {}, PERIOD)
        self.assertEqual(r["firstTime"], 1)


class RevenueTests(unittest.TestCase):
    def test_total_and_average_use_all_days(self):
        rev = total_revenue([D("100000"), D("50000.50")])
        self.assertEqual(rev, D("150000.50"))
        self.assertEqual(average_per_day(rev, 10), D("15000.05"))

    def test_zero_revenue(self):
        self.assertEqual(total_revenue([]), D(0))
        self.assertEqual(average_per_day(D(0), 7), D(0))


class DailyTests(unittest.TestCase):
    def test_fills_missing_days_with_zero(self):
        rows = [(D("100"), vn(2026, 11, 2)), (D("50"), vn(2026, 11, 2, 20)), (D("30"), vn(2026, 11, 5))]
        out = build_daily_revenue(rows, PERIOD)
        self.assertEqual(len(out), 10)
        by_day = {i["date"]: i["revenue"] for i in out}
        self.assertEqual(by_day["2026-11-01"], 0)
        self.assertEqual(by_day["2026-11-02"], 150)
        self.assertEqual(by_day["2026-11-05"], 30)
        self.assertEqual(by_day["2026-11-10"], 0)
        self.assertEqual([i["date"] for i in out], sorted(by_day))

    def test_timezone_boundary(self):
        # 17:30 UTC ngày 2/11 = 00:30 ngày 3/11 giờ Việt Nam
        utc_time = datetime(2026, 11, 2, 17, 30, tzinfo=timezone.utc)
        by_day = {i["date"]: i["revenue"] for i in build_daily_revenue([(D("10"), utc_time)], PERIOD)}
        self.assertEqual(by_day["2026-11-03"], 10)
        self.assertEqual(by_day["2026-11-02"], 0)

    def test_ignores_out_of_range(self):
        out = build_daily_revenue([(D("99"), vn(2026, 12, 1))], PERIOD)
        self.assertEqual(sum(i["revenue"] for i in out), 0)

    def test_sum_equals_total(self):
        rows = [(D("10.25"), vn(2026, 11, 1 + i)) for i in range(10)]
        self.assertEqual(sum(i["revenue"] for i in build_daily_revenue(rows, PERIOD)), 102.5)


class ServiceTests(unittest.TestCase):
    def test_summary_end_to_end(self):
        orders = [
            (1, D("200000"), vn(2026, 11, 2)),
            (1, D("300000"), vn(2026, 11, 6)),
            (2, D("500000"), vn(2026, 11, 3)),
        ]
        first = {1: vn(2026, 10, 15), 2: vn(2026, 11, 3)}
        repo = FakeRepo(orders, first,
                        signups={PERIOD.start: 15, PERIOD.previous().start: 10},
                        refunds=(2, D("120000")))
        s = MetricsService(repo).summary(PERIOD)
        self.assertEqual(s["payingCustomers"], {"total": 2, "firstTime": 1, "returning": 1})
        self.assertEqual(s["newSignups"], {"count": 15, "previousCount": 10, "growthRate": 50.0})
        self.assertEqual(s["revenue"], {"total": 1000000.0, "averagePerDay": 100000.0})
        self.assertEqual(s["refunds"], {"totalAmount": 120000.0, "orderCount": 2})
        self.assertEqual(s["period"], {"from": "2026-11-01", "to": "2026-11-10", "days": 10})
        self.assertEqual(s["previousPeriod"]["from"], "2026-10-22")

    def test_summary_empty_data(self):
        s = MetricsService(FakeRepo()).summary(PERIOD)
        self.assertEqual(s["payingCustomers"], {"total": 0, "firstTime": 0, "returning": 0})
        self.assertIsNone(s["newSignups"]["growthRate"])
        self.assertEqual(s["revenue"], {"total": 0.0, "averagePerDay": 0.0})
        self.assertEqual(s["refunds"], {"totalAmount": 0.0, "orderCount": 0})

    def test_refund_not_subtracted_from_revenue(self):
        repo = FakeRepo([(1, D("100"), vn(2026, 11, 2))], {1: vn(2026, 11, 2)}, refunds=(1, D("100")))
        s = MetricsService(repo).summary(PERIOD)
        self.assertEqual(s["revenue"]["total"], 100.0)

    def test_daily(self):
        repo = FakeRepo([(1, D("70"), vn(2026, 11, 4))])
        d = MetricsService(repo).daily(PERIOD)
        self.assertEqual(len(d["items"]), 10)
        self.assertEqual({i["date"]: i["revenue"] for i in d["items"]}["2026-11-04"], 70.0)

    def test_order_on_range_edge_included_next_day_excluded(self):
        repo = FakeRepo([(1, D("5"), vn(2026, 11, 10, 23, 59)), (2, D("7"), vn(2026, 11, 11, 0, 0))])
        s = MetricsService(repo).summary(PERIOD)
        self.assertEqual(s["revenue"]["total"], 5.0)


if __name__ == "__main__":
    unittest.main()