from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from psycopg import sql

from app.auth import Database, require_roles
from app.models import (
    Country, CustomerCreate, CustomerOut, CustomerPage, CustomerPatch,
    Envelope, ErrorEnvelope, SignupMethod,
)

router = APIRouter(prefix='/api/customers', tags=['Customers'], responses={
    code: {'model': ErrorEnvelope, 'description': description}
    for code, description in {
        400: 'Invalid input', 401: 'Missing/invalid JWT', 403: 'Insufficient permissions',
        404: 'Customer not found', 409: 'Duplicate code or related data conflict',
        503: 'Database unavailable',
    }.items()
})
READ = [Depends(require_roles('ADMIN', 'OPERATOR', 'VIEWER'))]
WRITE = [Depends(require_roles('ADMIN', 'OPERATOR'))]
ADMIN = [Depends(require_roles('ADMIN'))]
CustomerId = Annotated[int, Path(gt=0, le=9223372036854775807)]
COLUMNS = '''id, customer_code AS "customerCode", name, country,
             signup_method AS "signupMethod", signed_up_at AS "signedUpAt"'''
FIELD_MAP = {'customerCode': 'customer_code', 'name': 'name', 'country': 'country',
             'signupMethod': 'signup_method', 'signedUpAt': 'signed_up_at'}


def require_customer(row):
    if row is None:
        raise HTTPException(404, 'Customer not found')
    return row


@router.post('', status_code=201, response_model=Envelope[CustomerOut], dependencies=WRITE,
             summary='Create customer (ADMIN / OPERATOR)')
def create_customer(body: CustomerCreate, connection: Database):
    row = connection.execute(
        f'''INSERT INTO customers(customer_code, name, country, signup_method, signed_up_at)
            VALUES (%s, %s, %s, %s, %s) RETURNING {COLUMNS}''',
        (body.customerCode, body.name, body.country, body.signupMethod.value, body.signedUpAt),
    ).fetchone()
    return {'status': 201, 'message': 'success', 'data': row}


@router.get('', response_model=Envelope[CustomerPage], dependencies=READ,
            summary='List customers with pagination and filters (all roles)')
def list_customers(
    connection: Database,
    page: Annotated[int, Query(ge=1, le=1000000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    country: Annotated[Country | None, Query()] = None,
    signupMethod: Annotated[SignupMethod | None, Query()] = None,
):
    conditions, params = [], []
    if q is not None:
        term = q.strip()
        if not term:
            raise HTTPException(400, 'Search term cannot be blank')
        # Escape LIKE wildcards as well as using parameterized SQL.
        literal = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
        conditions.append('(name ILIKE %s OR customer_code ILIKE %s)')
        params.extend([f'%{literal}%', f'%{literal}%'])
    if country is not None:
        conditions.append('country = %s')
        params.append(country)
    if signupMethod is not None:
        conditions.append('signup_method = %s')
        params.append(signupMethod.value)
    where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
    # One statement gives count and rows the same snapshot under concurrent writes.
    rows = connection.execute(
        f'''WITH filtered AS (SELECT {COLUMNS} FROM customers {where}),
            paged AS (SELECT * FROM filtered ORDER BY id DESC LIMIT %s OFFSET %s)
            SELECT (SELECT COUNT(*) FROM filtered) AS total,
                   COALESCE((SELECT jsonb_agg(to_jsonb(p) ORDER BY p.id DESC) FROM paged p), '[]'::jsonb) AS items''',
        [*params, size, (page - 1) * size],
    ).fetchone()
    total = rows['total']
    return {'status': 200, 'message': 'success', 'data': {
        'items': rows['items'], 'page': page, 'size': size, 'total': total,
        'totalPages': (total + size - 1) // size,
    }}


@router.get('/{id}', response_model=Envelope[CustomerOut], dependencies=READ,
            summary='Get customer detail (all roles)')
def get_customer(id: CustomerId, connection: Database):
    row = connection.execute(f'SELECT {COLUMNS} FROM customers WHERE id = %s', (id,)).fetchone()
    return {'status': 200, 'message': 'success', 'data': require_customer(row)}


@router.patch('/{id}', response_model=Envelope[CustomerOut], dependencies=WRITE,
              summary='Update customer (ADMIN / OPERATOR)')
def patch_customer(id: CustomerId, body: CustomerPatch, connection: Database):
    changes = body.model_dump(exclude_unset=True)
    # Identifiers come only from the fixed mapping, never from raw client strings.
    assignments = sql.SQL(', ').join(
        sql.SQL('{} = %s').format(sql.Identifier(FIELD_MAP[field])) for field in changes
    )
    values = [value.value if isinstance(value, SignupMethod) else value for value in changes.values()]
    query = sql.SQL('UPDATE customers SET {} WHERE id = %s RETURNING {}').format(assignments, sql.SQL(COLUMNS))
    row = connection.execute(query, [*values, id]).fetchone()
    return {'status': 200, 'message': 'success', 'data': require_customer(row)}


@router.delete('/{id}', response_model=Envelope[None], dependencies=ADMIN,
               summary='Delete customer without related data (ADMIN only)')
def delete_customer(id: CustomerId, connection: Database):
    # FK RESTRICT is authoritative, including races with new orders/AI results.
    row = connection.execute('DELETE FROM customers WHERE id = %s RETURNING id', (id,)).fetchone()
    require_customer(row)
    return {'status': 200, 'message': 'success', 'data': None}
