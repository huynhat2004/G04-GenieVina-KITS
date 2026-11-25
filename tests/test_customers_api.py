from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import psycopg
import pytest

from tests.conftest import TEST_SECRET


def auth(member=1, **overrides):
    claims = {'sub': str(member), 'exp': datetime.now(timezone.utc) + timedelta(minutes=5)}
    claims.update(overrides)
    return {'Authorization': 'Bearer ' + jwt.encode(claims, TEST_SECRET, algorithm='HS256')}


def body(**changes):
    result = {'customerCode': 'TEST-' + uuid4().hex, 'name': 'Khách thử nghiệm',
              'country': 'VN', 'signupMethod': 'EMAIL', 'signedUpAt': '2026-11-24T09:00:00+07:00'}
    result.update(changes)
    return result


def assert_response(response, status):
    assert response.status_code == status, response.text
    assert set(response.json()) == {'status', 'message', 'data'}
    assert response.json()['status'] == status
    return response.json()['data']


def test_full_crud_persists_and_patch_preserves_omitted_fields(client, api_database):
    payload = body(name='  Khách thử nghiệm  ')
    row = assert_response(client.post('/api/customers', json=payload, headers=auth(2)), 201)
    cid = row['id']
    assert row['name'] == payload['name'].strip()
    assert set(row) == {'id', 'customerCode', 'name', 'country', 'signupMethod', 'signedUpAt'}
    with psycopg.connect(api_database) as connection:
        assert connection.execute('SELECT customer_code FROM customers WHERE id = %s', (cid,)).fetchone()[0] == payload['customerCode']
    read = assert_response(client.get(f'/api/customers/{cid}', headers=auth(3)), 200)
    assert read == row
    patched = assert_response(client.patch(f'/api/customers/{cid}', json={'name': 'Tên mới'}, headers=auth(2)), 200)
    assert patched == dict(row, name='Tên mới')
    assert_response(client.delete(f'/api/customers/{cid}', headers=auth()), 200)
    assert_response(client.get(f'/api/customers/{cid}', headers=auth()), 404)


def test_pagination_filters_and_literal_search(client):
    code = 'FILTER-' + uuid4().hex[:12]
    for index in range(3):
        assert_response(client.post('/api/customers', json=body(customerCode=f'{code}-{index}',
            name='Literal%_\\Test', country='KR', signupMethod='GOOGLE'), headers=auth()), 201)
    params = {'q': code, 'country': 'KR', 'signupMethod': 'GOOGLE', 'size': 2}
    first = assert_response(client.get('/api/customers', params=params, headers=auth(3)), 200)
    second = assert_response(client.get('/api/customers', params={**params, 'page': 2}, headers=auth(3)), 200)
    assert first['total'] == 3 and first['totalPages'] == 2
    assert len(first['items']) == 2 and len(second['items']) == 1
    assert first['items'][0]['id'] > first['items'][1]['id'] > second['items'][0]['id']
    beyond = assert_response(client.get('/api/customers', params={**params, 'page': 10}, headers=auth()), 200)
    assert beyond['items'] == [] and beyond['total'] == 3
    for term in ['%', '_', '\\']:
        matches = assert_response(client.get('/api/customers', params={'q': term}, headers=auth()), 200)
        assert matches['total'] == 3


def test_duplicate_create_and_patch_roll_back(client):
    payload = body()
    assert_response(client.post('/api/customers', json=payload, headers=auth()), 201)
    assert_response(client.post('/api/customers', json=payload, headers=auth()), 409)
    other = assert_response(client.post('/api/customers', json=body(), headers=auth()), 201)
    assert_response(client.patch(f"/api/customers/{other['id']}", json={'customerCode': payload['customerCode'], 'name': 'Must roll back'}, headers=auth()), 409)
    unchanged = assert_response(client.get(f"/api/customers/{other['id']}", headers=auth()), 200)
    assert unchanged == other


def test_simultaneous_duplicate_create(client):
    payload = body()
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: client.post('/api/customers', json=payload, headers=auth()), range(2)))
    assert sorted(response.status_code for response in responses) == [201, 409]


@pytest.mark.parametrize('change', [
    {'customerCode': ''}, {'customerCode': ' '}, {'customerCode': 'X' * 41},
    {'name': ' '}, {'name': 'X' * 201}, {'country': 'vn'}, {'country': 'VNN'},
    {'signupMethod': 'OTHER'}, {'signedUpAt': '2026-11-24T09:00:00'},
    {'signedUpAt': 'not-a-date'}, {'name': None}, {'id': 1}, {'role': 'ADMIN'},
])
def test_create_validation(client, change):
    response = client.post('/api/customers', json=body(**change), headers=auth())
    data = assert_response(response, 400)
    assert data['errors']


@pytest.mark.parametrize('changes', [{}, {'name': None}, {'name': ' '}, {'id': 123}, {'signedUpAt': 'invalid'}])
def test_patch_validation(client, changes):
    assert_response(client.patch('/api/customers/1', json=changes, headers=auth()), 400)


@pytest.mark.parametrize('params', [{'size': 0}, {'size': 101}, {'page': 0}, {'country': 'vn'},
                                    {'signupMethod': 'OTHER'}, {'q': ' '}])
def test_query_validation(client, params):
    assert_response(client.get('/api/customers', params=params, headers=auth()), 400)


@pytest.mark.parametrize('method,payload', [('get', None), ('patch', {'name': 'Test'}), ('delete', None)])
def test_missing_customer(client, method, payload):
    kwargs = {'headers': auth()}
    if payload is not None:
        kwargs['json'] = payload
    assert_response(client.request(method, '/api/customers/999999', **kwargs), 404)


@pytest.mark.parametrize('cid', ['0', '-1', 'not-an-id', '9223372036854775808'])
def test_invalid_customer_id(client, cid):
    assert_response(client.get(f'/api/customers/{cid}', headers=auth()), 400)


def test_related_data_prevents_delete_and_signup_date_change(client):
    for cid in [1, 6]:  # Customer 1 has orders; customer 6 has AI results only.
        original = assert_response(client.get(f'/api/customers/{cid}', headers=auth()), 200)
        assert_response(client.delete(f'/api/customers/{cid}', headers=auth()), 409)
        assert_response(client.patch(f'/api/customers/{cid}', json={'signedUpAt': '2099-01-01T00:00:00+07:00'}, headers=auth()), 409)
        assert assert_response(client.get(f'/api/customers/{cid}', headers=auth()), 200) == original


def test_role_permissions(client):
    assert_response(client.post('/api/customers', json=body(), headers=auth(3)), 403)
    assert_response(client.patch('/api/customers/1', json={'name': 'Forbidden'}, headers=auth(3)), 403)
    assert_response(client.delete('/api/customers/1', headers=auth(2)), 403)
    assert_response(client.delete('/api/customers/1', headers=auth(3)), 403)


def test_missing_invalid_expired_and_nonexistent_tokens(client):
    assert_response(client.get('/api/customers'), 401)
    assert_response(client.get('/api/customers', headers={'Authorization': 'Bearer invalid'}), 401)
    assert_response(client.get('/api/customers', headers={'Authorization': 'Basic test'}), 401)
    assert_response(client.get('/api/customers', headers=auth(exp=datetime.now(timezone.utc) - timedelta(seconds=1))), 401)
    for member in [999999, 0, -1, 'not-an-id', '9' * 100]:
        assert_response(client.get('/api/customers', headers=auth(member)), 401)
    for claims in [{'sub': '1'}, {'exp': datetime.now(timezone.utc) + timedelta(minutes=1)}, {'sub': 1, 'exp': 9999999999}]:
        token = jwt.encode(claims, TEST_SECRET, algorithm='HS256')
        assert_response(client.get('/api/customers', headers={'Authorization': f'Bearer {token}'}), 401)
    token = jwt.encode({'sub': '1', 'exp': 9999999999}, 'different-secret-at-least-32-bytes-long', algorithm='HS256')
    assert_response(client.get('/api/customers', headers={'Authorization': f'Bearer {token}'}), 401)


def test_role_is_read_from_database_not_token(client, api_database):
    with psycopg.connect(api_database) as connection:
        mid = connection.execute("INSERT INTO members(email,password_hash,name,role) VALUES (%s,'unused','Test','VIEWER') RETURNING id", (uuid4().hex + '@example.invalid',)).fetchone()[0]
    headers = auth(mid, role='ADMIN')
    assert_response(client.post('/api/customers', json=body(), headers=headers), 403)


def test_swagger_and_openapi_match_runtime(client):
    assert client.get('/docs').status_code == 200
    schema = client.get('/openapi.json').json()
    assert {'/api/customers', '/api/customers/{id}'} <= set(schema['paths'])
    for path in (schema['paths']['/api/customers'], schema['paths']['/api/customers/{id}']):
        for operation in path.values():
            assert operation['security'] == [{'HTTPBearer': []}]
            assert '400' in operation['responses']
            assert '422' not in operation['responses']
    assert_response(client.get('/unknown'), 404)
    assert_response(client.put('/api/customers', headers=auth()), 405)


def test_malformed_json_uses_common_error_format(client):
    assert_response(client.post('/api/customers', content='{broken', headers={**auth(), 'Content-Type': 'application/json'}), 400)
