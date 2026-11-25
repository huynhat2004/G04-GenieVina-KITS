from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.metrics import Window, calculate_summary, calculate_daily


def ts(value):
    return datetime.fromisoformat(value)


def order(cid, amount, paid=None, refunded=None, status='PAID'):
    return {'customer_id':cid,'amount':Decimal(amount),'paid_at':ts(paid) if paid else None,
            'refunded_at':ts(refunded) if refunded else None,'status':status}


def test_distinct_first_time_returning_refunds_and_previous_period():
    w = Window(ts('2026-11-01').date(),ts('2026-11-02').date())
    customers = [{'signed_up_at':ts(s)} for s in [
        '2026-10-30T00:00:00+07:00','2026-11-01T00:00:00+07:00',
        '2026-11-02T23:59:59+07:00','2026-11-03T00:00:00+07:00']]
    orders = [order(1,'100','2026-10-01T00:00:00+07:00'),
        order(1,'200','2026-11-01T01:00:00+07:00'),
        order(1,'300','2026-11-02T01:00:00+07:00'),
        order(2,'400','2026-11-01T01:00:00+07:00'),
        order(2,'500','2026-11-02T01:00:00+07:00'),
        order(3,'700','2026-10-01T01:00:00+07:00','2026-11-02T01:00:00+07:00','REFUNDED'),
        order(4,'900',status='FAILED')]
    result = calculate_summary(customers,orders,w)
    assert (result['payingCustomers'],result['firstTimeCustomers'],result['returningCustomers']) == (2,1,1)
    assert result['revenue'] == Decimal('1400.00')
    assert result['averageDailyRevenue'] == Decimal('700.00')
    assert (result['refundAmount'],result['refundCount']) == (Decimal('700.00'),1)
    assert (result['newRegistrations'],result['previousRegistrations'],result['registrationGrowthPercent']) == (2,1,Decimal('100.00'))


def test_vietnam_midnight_boundaries_zero_days_and_decimal_rounding():
    w = Window(ts('2026-11-01').date(),ts('2026-11-03').date())
    orders = [order(1,'0.01','2026-10-31T17:00:00+00:00'),
        order(2,'10','2026-10-31T16:59:59+00:00'),
        order(3,'10','2026-11-03T17:00:00+00:00')]
    daily = calculate_daily(orders,w)
    assert [i['revenue'] for i in daily['items']] == [Decimal('0.01'),0,0]
    result = calculate_summary([],orders,w)
    assert result['averageDailyRevenue'] == Decimal('0.00')
    assert result['registrationGrowthPercent'] is None
    assert sum(i['revenue'] for i in daily['items']) == result['revenue']


def test_refunded_earlier_payment_does_not_make_customer_returning():
    w = Window(ts('2026-11-01').date(),ts('2026-11-01').date())
    orders = [order(1,'100','2026-10-01T00:00:00+07:00','2026-10-02T00:00:00+07:00','REFUNDED'),
              order(1,'200','2026-11-01T00:00:00+07:00')]
    result = calculate_summary([],orders,w)
    assert result['firstTimeCustomers'] == 1
    assert result['returningCustomers'] == 0
    assert result['refundCount'] == 0


def test_empty_and_negative_growth():
    w = Window(ts('2026-11-01').date(),ts('2026-11-01').date())
    result = calculate_summary([{'signed_up_at':ts('2026-10-31T01:00:00+07:00')}],[],w)
    assert result['registrationGrowthPercent'] == Decimal('-100.00')
    assert result['revenue'] == result['refundAmount'] == 0
    assert calculate_daily([],w)['items'][0]['revenue'] == 0


@pytest.mark.parametrize('start,end', [('2026-11-02','2026-11-01'),('2000-01-01','2026-11-01'),('9999-12-31','9999-12-31'),('0001-01-01','0001-01-01')])
def test_invalid_period(start,end):
    with pytest.raises(HTTPException) as exc:
        Window(ts(start).date(),ts(end).date())
    assert exc.value.status_code == 400
