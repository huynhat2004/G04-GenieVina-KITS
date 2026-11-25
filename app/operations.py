"""Orders and AI event APIs. Status history is written by database triggers."""
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.auth import Database, require_roles
from app.customers import CustomerId, READ, WRITE
from app.models import Envelope, ErrorEnvelope, Principal

router = APIRouter(prefix='/api', responses={c: {'model': ErrorEnvelope} for c in (400, 401, 403, 404, 409, 500, 503)})

class OrderStatus(str, Enum):
    PENDING = 'PENDING'
    PAID = 'PAID'
    FAILED = 'FAILED'
    REFUNDED = 'REFUNDED'

class AIType(str, Enum):
    QUOTE = 'QUOTE'
    WEBSITE = 'WEBSITE'

class OrderCreate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    customerId: int = Field(gt=0, le=9223372036854775807)
    packageName: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    createdAt: AwareDatetime | None = None

class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    newStatus: OrderStatus
    reason: str = Field(min_length=1, max_length=500)

class AICreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    customerId: int = Field(gt=0, le=9223372036854775807)
    type: AIType
    createdAt: AwareDatetime | None = None

class OrderOut(BaseModel):
    id: int
    customerId: int
    packageName: str
    amount: Decimal
    status: OrderStatus
    createdAt: AwareDatetime
    paidAt: AwareDatetime | None
    refundedAt: AwareDatetime | None

class AIOut(BaseModel):
    id: int
    customerId: int
    type: AIType
    createdAt: AwareDatetime

class HistoryOut(BaseModel):
    id: int
    orderId: int
    previousStatus: OrderStatus
    newStatus: OrderStatus
    changedBy: int
    reason: str
    changedAt: AwareDatetime

class Pagination(BaseModel):
    page: int
    limit: int
    totalItems: int
    totalPages: int

class OrderPage(BaseModel):
    items: list[OrderOut]
    pagination: Pagination

class AIPage(BaseModel):
    items: list[AIOut]
    pagination: Pagination

class HistoryPage(BaseModel):
    items: list[HistoryOut]
    pagination: Pagination

ORDER_COLUMNS = '''id, customer_id AS "customerId", package_name AS "packageName", amount, status,
created_at AS "createdAt", paid_at AS "paidAt", refunded_at AS "refundedAt"'''
AI_COLUMNS = 'id, customer_id AS "customerId", type, created_at AS "createdAt"'
HISTORY_COLUMNS = '''id, order_id AS "orderId", previous_status AS "previousStatus",
new_status AS "newStatus", changed_by AS "changedBy", reason, changed_at AS "changedAt"'''
Page = Annotated[int, Query(ge=1, le=1000000)]
Limit = Annotated[int, Query(ge=1, le=100)]

def success(data, status=200):
    return {'status': status, 'message': 'success', 'data': data}

def existing(row, resource):
    if row is None:
        raise HTTPException(404, f'{resource} not found')
    return row

def validate_event(connection, customer_id, created_at):
    customer = existing(connection.execute('SELECT signed_up_at FROM customers WHERE id=%s FOR SHARE',
                                          (customer_id,)).fetchone(), 'Customer')
    if created_at < customer['signed_up_at']:
        raise HTTPException(400, 'Event cannot precede customer signup')

def paged(connection, table, columns, conditions, params, sort, direction, page, limit):
    # All identifiers and sort expressions originate in code-controlled mappings.
    where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
    result = connection.execute(f'''WITH filtered AS (SELECT {columns} FROM {table}{where}),
        paged AS (SELECT * FROM filtered ORDER BY {sort} {direction}, id {direction} LIMIT %s OFFSET %s)
        SELECT (SELECT count(*) FROM filtered) AS total,
        COALESCE((SELECT jsonb_agg(to_jsonb(p) ORDER BY p.{sort} {direction}, p.id {direction}) FROM paged p), '[]'::jsonb) AS items''',
        [*params, limit, (page-1)*limit]).fetchone()
    total = result['total']
    return success({'items': result['items'], 'pagination': {
        'page': page, 'limit': limit, 'totalItems': total, 'totalPages': (total+limit-1)//limit}})

@router.post('/orders', tags=['Orders'], status_code=201, response_model=Envelope[OrderOut], dependencies=WRITE)
def create_order(body: OrderCreate, connection: Database):
    created = body.createdAt or datetime.now(timezone.utc)
    validate_event(connection, body.customerId, created)
    row = connection.execute(f'''INSERT INTO orders(customer_id,package_name,amount,created_at)
        VALUES (%s,%s,%s,%s) RETURNING {ORDER_COLUMNS}''',
        (body.customerId, body.packageName, body.amount, created)).fetchone()
    return success(row, 201)

@router.get('/orders', tags=['Orders'], response_model=Envelope[OrderPage], dependencies=READ)
def list_orders(connection: Database, page: Page=1, limit: Limit=10,
                orderStatus: OrderStatus | None=None, customerId: Annotated[int | None, Query(gt=0, le=9223372036854775807)]=None,
                search: Annotated[str | None, Query(max_length=100)]=None,
                sortBy: Literal['id','amount','paidAt','createdAt']='id', order: Literal['asc','desc']='desc'):
    conditions, params = [], []
    for column, value in [('status', orderStatus), ('customer_id', customerId)]:
        if value is not None:
            conditions.append(f'{column}=%s'); params.append(value)
    if search is not None:
        conditions.append('strpos(lower(package_name),lower(%s))>0'); params.append(search)
    sort = {'id':'id','amount':'amount','paidAt':'"paidAt"','createdAt':'"createdAt"'}[sortBy]
    return paged(connection,'orders',ORDER_COLUMNS,conditions,params,sort,order,page,limit)

@router.get('/orders/{id}', tags=['Orders'], response_model=Envelope[OrderOut], dependencies=READ)
def get_order(id: CustomerId, connection: Database):
    return success(existing(connection.execute(f'SELECT {ORDER_COLUMNS} FROM orders WHERE id=%s',(id,)).fetchone(),'Order'))

@router.patch('/orders/{id}/status', tags=['Order Status'], response_model=Envelope[HistoryOut])
def update_status(id: CustomerId, body: StatusUpdate, connection: Database,
                  principal: Annotated[Principal, Depends(require_roles('ADMIN','OPERATOR'))]):
    row = existing(connection.execute('SELECT status FROM orders WHERE id=%s FOR UPDATE',(id,)).fetchone(),'Order')
    if body.newStatus not in {'PENDING': ('PAID','FAILED'), 'PAID': ('REFUNDED',)}.get(row['status'], ()):
        raise HTTPException(400,'Invalid status transition')
    connection.execute("SELECT set_config('app.member_id',%s,true), set_config('app.change_reason',%s,true)",
                       (str(principal.id),body.reason))
    connection.execute('''UPDATE orders SET status=%s,
        paid_at=CASE WHEN %s='PAID' THEN clock_timestamp() ELSE paid_at END,
        refunded_at=CASE WHEN %s='REFUNDED' THEN clock_timestamp() ELSE refunded_at END WHERE id=%s''',
        (body.newStatus.value,body.newStatus.value,body.newStatus.value,id))
    return success(connection.execute(f'SELECT {HISTORY_COLUMNS} FROM order_status_histories WHERE order_id=%s ORDER BY id DESC LIMIT 1',(id,)).fetchone())

@router.get('/orders/{id}/status-history', tags=['Order Status'], response_model=Envelope[HistoryPage], dependencies=READ)
def history(id: CustomerId, connection: Database, page: Page=1, limit: Limit=10):
    existing(connection.execute('SELECT id FROM orders WHERE id=%s',(id,)).fetchone(),'Order')
    return paged(connection,'order_status_histories',HISTORY_COLUMNS,['order_id=%s'],[id],'id','desc',page,limit)

@router.post('/ai-results', tags=['AI Results'], status_code=201, response_model=Envelope[AIOut], dependencies=WRITE)
def create_ai(body: AICreate, connection: Database):
    created = body.createdAt or datetime.now(timezone.utc)
    validate_event(connection, body.customerId, created)
    return success(connection.execute(f'''INSERT INTO ai_results(customer_id,type,created_at)
        VALUES (%s,%s,%s) RETURNING {AI_COLUMNS}''',(body.customerId,body.type.value,created)).fetchone(),201)

@router.get('/ai-results', tags=['AI Results'], response_model=Envelope[AIPage], dependencies=READ)
def list_ai(connection: Database, page: Page=1, limit: Limit=10,
            customerId: Annotated[int | None, Query(gt=0, le=9223372036854775807)]=None,
            type: AIType | None=None, sortBy: Literal['id','createdAt']='id', order: Literal['asc','desc']='desc'):
    conditions, params = [], []
    for column,value in [('customer_id',customerId),('type',type)]:
        if value is not None:
            conditions.append(f'{column}=%s'); params.append(value)
    return paged(connection,'ai_results',AI_COLUMNS,conditions,params,{'id':'id','createdAt':'"createdAt"'}[sortBy],order,page,limit)
