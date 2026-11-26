"""Calendar-day reports in Asia/Ho_Chi_Minh, including both boundary days."""
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth import Database
from app.customers import READ
from app.models import Envelope, ErrorEnvelope

TZ = ZoneInfo('Asia/Ho_Chi_Minh')
router = APIRouter(prefix='/api/metrics', tags=['Metrics'], dependencies=READ,
                   responses={c: {'model': ErrorEnvelope} for c in (400,401,403,500,503)})

class Period(BaseModel):
    fromDate: date
    toDate: date
    days: int
    timezone: str = 'Asia/Ho_Chi_Minh'

class Summary(Period):
    payingCustomers: int
    firstTimeCustomers: int
    returningCustomers: int
    newRegistrations: int
    previousRegistrations: int
    registrationGrowthPercent: Decimal | None
    revenue: Decimal
    averageDailyRevenue: Decimal
    refundAmount: Decimal
    refundCount: int

class DailyItem(BaseModel):
    date: date
    revenue: Decimal

class Daily(Period):
    items: list[DailyItem]

class Window:
    def __init__(self, from_: Annotated[date, Query(alias='from')], to: Annotated[date, Query()]):
        if from_ > to or to == date.max:
            raise HTTPException(400,'Invalid date interval')
        self.days = (to-from_).days+1
        # A bounded reporting range avoids accidental unbounded scans and huge responses.
        if self.days > 3660 or from_.toordinal() <= self.days:
            raise HTTPException(400,'Date interval must contain at most 3660 days and allow a previous period')
        self.from_date, self.to_date = from_, to
        self.start = datetime.combine(from_,time.min,TZ)
        self.end = datetime.combine(to+timedelta(days=1),time.min,TZ)
        self.previous = self.start-timedelta(days=self.days)

    def metadata(self):
        return {'fromDate':self.from_date,'toDate':self.to_date,'days':self.days,'timezone':str(TZ)}

WindowDep = Annotated[Window, Depends()]

def money(value):
    return Decimal(value).quantize(Decimal('0.01'),rounding=ROUND_HALF_UP)

def calculate_summary(customers, orders, window):
    """Pure calculation shared by API and unit tests; all order history is required."""
    valid = [o for o in orders if o['status']=='PAID']
    first = {}
    for order in valid:
        cid = order['customer_id']
        first[cid] = min(first.get(cid,order['paid_at']),order['paid_at'])
    in_period = [o for o in valid if window.start <= o['paid_at'] < window.end]
    payers = {o['customer_id'] for o in in_period}
    newcomers = {cid for cid in payers if window.start <= first[cid] < window.end}
    current = sum(window.start <= c['signed_up_at'] < window.end for c in customers)
    previous = sum(window.previous <= c['signed_up_at'] < window.start for c in customers)
    refunds = [o for o in orders if o['refunded_at'] is not None and window.start <= o['refunded_at'] < window.end]
    revenue = sum((o['amount'] for o in in_period),Decimal(0))
    return {**window.metadata(), 'payingCustomers':len(payers),'firstTimeCustomers':len(newcomers),
            'returningCustomers':len(payers-newcomers),'newRegistrations':current,'previousRegistrations':previous,
            'registrationGrowthPercent':money(Decimal(current-previous)*100/previous) if previous else None,
            'revenue':money(revenue),'averageDailyRevenue':money(revenue/window.days),
            'refundAmount':money(sum((o['amount'] for o in refunds),Decimal(0))),'refundCount':len(refunds)}

def calculate_daily(orders, window):
    totals = {window.from_date+timedelta(days=i):Decimal(0) for i in range(window.days)}
    for order in orders:
        if order['status']=='PAID' and window.start <= order['paid_at'] < window.end:
            totals[order['paid_at'].astimezone(TZ).date()] += order['amount']
    return {**window.metadata(),'items':[{'date':day,'revenue':money(total)} for day,total in totals.items()]}

def report_data(connection, window):
    # One statement gives both datasets the same snapshot under concurrent writes.
    rows = connection.execute('''SELECT customer_id,amount,status,paid_at,refunded_at,
        NULL::timestamptz AS signed_up_at FROM orders
        WHERE (status='PAID' AND paid_at < %s) OR (refunded_at >= %s AND refunded_at < %s)
        UNION ALL
        SELECT NULL,NULL,NULL,NULL,NULL,signed_up_at FROM customers
        WHERE signed_up_at >= %s AND signed_up_at < %s''',
        (window.end,window.start,window.end,window.previous,window.end)).fetchall()
    return ([r for r in rows if r['signed_up_at'] is not None],
            [r for r in rows if r['signed_up_at'] is None])

@router.get('/summary',response_model=Envelope[Summary],summary='Paying customers, registrations, revenue and refunds')
def summary(connection: Database, window: WindowDep):
    customers, orders = report_data(connection,window)
    return {'status':200,'message':'success','data':calculate_summary(customers,orders,window)}

@router.get('/daily',response_model=Envelope[Daily],summary='Daily revenue including days with no payments')
def daily(connection: Database, window: WindowDep):
    _, orders = report_data(connection,window)
    return {'status':200,'message':'success','data':calculate_daily(orders,window)}
