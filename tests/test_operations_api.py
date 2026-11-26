from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import psycopg
import pytest
from psycopg.rows import dict_row

from tests.test_customers_api import auth, body, assert_response
from app.metrics import Window, calculate_summary, calculate_daily


def create_customer(client):
    return assert_response(client.post('/api/customers',json=body(),headers=auth()),201)['id']


def create_order(client, cid):
    return assert_response(client.post('/api/orders',json={'customerId':cid,'packageName':'Basic','amount':'1234.50'},headers=auth(2)),201)


def test_orders_history_ai_and_customer_delete_guard(client,api_database):
    cid = create_customer(client)
    order = create_order(client,cid)
    oid = order['id']
    assert order['status']=='PENDING'
    assert_response(client.get(f'/api/orders/{oid}',headers=auth(3)),200)
    for status in ['PAID','REFUNDED']:
        history = assert_response(client.patch(f'/api/orders/{oid}/status',json={'newStatus':status,'reason':'Test '+status},headers=auth(2)),200)
        assert history['newStatus']==status and history['changedBy']==2
    assert_response(client.patch(f'/api/orders/{oid}/status',json={'newStatus':'PAID','reason':'Invalid'},headers=auth()),400)
    histories = assert_response(client.get(f'/api/orders/{oid}/status-history',headers=auth(3)),200)
    assert histories['pagination']['totalItems']==2
    assert histories['items'][0]['previousStatus']=='PAID'
    assert_response(client.delete(f'/api/customers/{cid}',headers=auth()),409)
    ai = assert_response(client.post('/api/ai-results',json={'customerId':cid,'type':'WEBSITE'},headers=auth(2)),201)
    assert ai['type']=='WEBSITE'
    for sort in ['id','createdAt']:
        data = assert_response(client.get('/api/ai-results',params={'customerId':cid,'type':'WEBSITE','sortBy':sort},headers=auth(3)),200)
        assert data['items'][0]['id']==ai['id']
    for sort in ['id','createdAt','paidAt','amount']:
        data = assert_response(client.get('/api/orders',params={'customerId':cid,'sortBy':sort,'limit':1},headers=auth(3)),200)
        assert data['items'][0]['id']==oid
    with psycopg.connect(api_database) as c:
        assert c.execute('SELECT status,paid_at IS NOT NULL,refunded_at IS NOT NULL FROM orders WHERE id=%s',(oid,)).fetchone()==('REFUNDED',True,True)


@pytest.mark.parametrize('path,payload', [
    ('/api/orders',{'customerId':9223372036854775807,'packageName':'Basic','amount':100}),
    ('/api/ai-results',{'customerId':9223372036854775807,'type':'QUOTE'}),
])
def test_unknown_customer(client,path,payload):
    assert_response(client.post(path,json=payload,headers=auth(2)),404)


@pytest.mark.parametrize('path,payload', [
    ('/api/orders',{'packageName':'Basic','amount':100}),
    ('/api/ai-results',{'type':'QUOTE'}),
])
def test_event_before_signup_and_viewer_cannot_write(client,path,payload):
    cid = create_customer(client)
    payload = {**payload,'customerId':cid,'createdAt':'2020-01-01T00:00:00Z'}
    assert_response(client.post(path,json=payload,headers=auth(2)),400)
    assert_response(client.post(path,json=payload,headers=auth(3)),403)


def test_status_invalid_transitions_and_concurrent_payment(client):
    oid = create_order(client,create_customer(client))['id']
    path = f'/api/orders/{oid}/status'
    assert_response(client.patch(path,json={'newStatus':'REFUNDED','reason':'invalid'},headers=auth()),400)
    assert_response(client.patch(path,json={'newStatus':'PAID','reason':'   '},headers=auth()),400)
    assert_response(client.patch(path,json={'newStatus':'PAID','reason':'viewer'},headers=auth(3)),403)
    def pay(_):
        return client.patch(path,json={'newStatus':'PAID','reason':'Concurrent'},headers=auth(2)).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(pay,range(2)))==[200,400]
    history = assert_response(client.get(f'/api/orders/{oid}/status-history',headers=auth()),200)
    assert history['pagination']['totalItems']==1


def test_failed_is_terminal_and_unknown_order(client):
    oid = create_order(client,create_customer(client))['id']
    assert_response(client.patch(f'/api/orders/{oid}/status',json={'newStatus':'FAILED','reason':'Payment failed'},headers=auth()),200)
    assert_response(client.patch(f'/api/orders/{oid}/status',json={'newStatus':'PAID','reason':'Retry'},headers=auth()),400)
    for suffix in ['', '/status-history']:
        assert_response(client.get('/api/orders/9223372036854775807'+suffix,headers=auth()),404)


def test_login_logout_persistent_revocation(client,api_database):
    for email in ['admin@example.invalid','operator@example.invalid','viewer@example.invalid']:
        data = assert_response(client.post('/api/auth/login',json={'email':email.upper(),'password':'DemoOnly!2026'}),200)
        headers = {'Authorization':'Bearer '+data['accessToken']}
        assert_response(client.get('/api/customers',headers=headers),200)
        assert_response(client.post('/api/auth/logout',headers=headers),200)
        assert_response(client.get('/api/customers',headers=headers),401)
        assert_response(client.post('/api/auth/logout',headers=headers),401)
    for email,password in [('unknown@example.invalid','wrong'),('admin@example.invalid','wrong')]:
        assert_response(client.post('/api/auth/login',json={'email':email,'password':password}),401)
    with psycopg.connect(api_database) as c:
        assert c.execute('SELECT count(*) FROM revoked_tokens').fetchone()[0]>=3


def test_metrics_against_all_database_events(client,api_database):
    start,end = '2026-10-26','2026-11-24'
    window = Window(datetime.fromisoformat(start).date(),datetime.fromisoformat(end).date())
    with psycopg.connect(api_database,row_factory=dict_row) as c:
        customers = c.execute('SELECT * FROM customers').fetchall()
        orders = c.execute('SELECT * FROM orders').fetchall()
    expected = calculate_summary(customers,orders,window)
    summary = assert_response(client.get('/api/metrics/summary',params={'from':start,'to':end},headers=auth(3)),200)
    for key in ['payingCustomers','firstTimeCustomers','returningCustomers','newRegistrations','previousRegistrations','refundCount']:
        assert summary[key]==expected[key]
    for key in ['revenue','averageDailyRevenue','refundAmount','registrationGrowthPercent']:
        assert Decimal(summary[key])==expected[key]
    daily = assert_response(client.get('/api/metrics/daily',params={'from':start,'to':end},headers=auth(3)),200)
    assert len(daily['items'])==30
    assert sum(Decimal(i['revenue']) for i in daily['items'])==Decimal(summary['revenue'])
    assert any(Decimal(i['revenue'])==0 for i in daily['items'])
    assert_response(client.get('/api/metrics/summary',params={'from':end,'to':start},headers=auth(3)),400)
    assert_response(client.get('/api/metrics/daily',params={'from':'invalid','to':end},headers=auth(3)),400)
    assert_response(client.get('/api/metrics/daily'),401)


def test_complete_openapi_documents_every_operation(client):
    schema = client.get('/openapi.json').json()
    assert sum(len([m for m in ops if m in {'get','post','patch','delete'}]) for ops in schema['paths'].values())==16
    for path,operations in schema['paths'].items():
        for operation in operations.values():
            assert '422' not in operation['responses']
            if path!='/api/auth/login':
                assert operation['security']
