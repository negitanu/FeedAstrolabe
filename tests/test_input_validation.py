import pytest

from feedastrolabe import collection
from feedastrolabe.db import get_db
from test_reader import app, client, post, subscribe, RSS, META
from test_phase_two import authorization


@pytest.mark.parametrize('field,value', [('view','invalid'), ('q','x'*201), ('workspace','0'), ('tag',str(2**63))])
def test_invalid_filter_does_not_broaden_bulk_read(app, client, field, value):
    subscribe(client)
    assert post(client, '/articles/read-all', {field:value}).status_code == 400
    with app.app_context():
        assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0] == 0


@pytest.mark.parametrize('field', ['view','q','workspace','tag'])
def test_repeated_filter_does_not_broaden_bulk_read(app, client, field):
    from werkzeug.datastructures import MultiDict
    subscribe(client)
    with client.session_transaction() as session:
        csrf = session['csrf']
    data=MultiDict([('csrf',csrf), (field,''), (field,'1')])
    assert client.post('/articles/read-all', data=data).status_code == 400
    with app.app_context():
        assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0] == 0


@pytest.mark.parametrize('value', ['bad', '-1', '0', str(2**63), '9'*5000], ids=['text','negative','zero','overflow','huge'])
def test_invalid_reader_scope_does_not_mark_other_articles_read(app, client, value):
    subscribe(client)
    subscribe(client, 'https://example.com/other')
    response = post(client, '/articles/read-all', {'feed': value})
    assert response.status_code == 400
    with app.app_context():
        assert get_db().execute('SELECT sum(is_read),sum(is_starred) FROM articles').fetchone()[:] == (0, 0)


@pytest.mark.parametrize('value', ['bad', '-1', '0', str(2**63), '9'*5000], ids=['text','negative','zero','overflow','huge'])
def test_invalid_refresh_target_does_not_fetch(app, client, monkeypatch, value):
    subscribe(client)
    calls = []
    monkeypatch.setattr(collection, 'fetch', lambda *args: calls.append(args) or (RSS, META))
    assert post(client, '/refresh', {'feed': value}).status_code == 400
    assert calls == []


def test_repeated_selector_does_not_broaden_scope(app, client, monkeypatch):
    from werkzeug.datastructures import MultiDict
    subscribe(client)
    subscribe(client, 'https://example.com/other')
    with client.session_transaction() as session:
        csrf = session['csrf']
    calls = []
    monkeypatch.setattr(collection, 'fetch', lambda *args: calls.append(args) or (RSS, META))
    body = MultiDict([('csrf', csrf), ('feed', '1'), ('feed', '2')])
    assert client.post('/articles/read-all', data=body).status_code == 400
    assert client.post('/refresh', data=body).status_code == 400
    assert client.get('/?feed=1&feed=2').status_code == 400
    assert calls == []
    with app.app_context():
        assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0] == 0


def test_valid_empty_and_missing_reader_targets(app, client, monkeypatch):
    subscribe(client)
    subscribe(client, 'https://example.com/other')
    calls = []
    monkeypatch.setattr(collection, 'fetch', lambda *args: calls.append(args) or (RSS, META))
    assert post(client, '/refresh', {'feed': '1'}).status_code == 302
    assert [args[0] for args in calls] == ['https://example.com/feed']
    calls.clear()
    assert post(client, '/refresh', {'feed': '999'}).status_code == 404
    assert calls == []
    assert post(client, '/refresh', {'feed': ''}).status_code == 302
    assert len(calls) == 2
    assert post(client, '/articles/read-all', {'feed': '1'}).status_code == 302
    with app.app_context():
        assert get_db().execute('SELECT sum(is_read) FROM articles WHERE feed_id=2').fetchone()[0] == 0
    assert post(client, '/articles/read-all', {'feed': ''}).status_code == 302
    with app.app_context():
        assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0] == 4


@pytest.mark.parametrize('name', ['feed', 'article'])
@pytest.mark.parametrize('value', ['bad', '-1', '0', str(2**63), '9'*5000], ids=['text','negative','zero','overflow','huge'])
def test_invalid_reader_query_returns_400(client, name, value):
    assert client.get('/', query_string={name: value}).status_code == 400


@pytest.mark.parametrize('value', ['0', str(2**63), '9'*5000], ids=['zero','overflow','huge'])
def test_invalid_route_ids_rejected_without_mutation(app, client, value):
    subscribe(client)
    headers = authorization(app, 'write')[2]
    for method, path, kwargs in [
        ('get', '/api/v1/feeds/', {}),
        ('get', '/api/v1/articles/', {}),
        ('patch', '/api/v1/feeds/', {'json': {'enabled': False}}),
        ('delete', '/api/v1/feeds/', {}),
        ('patch', '/api/v1/articles/', {'json': {'is_read': True}}),
    ]:
        assert getattr(client, method)(path+value, headers=headers, **kwargs).status_code == (404 if len(value)>19 else 400)
    assert post(client, '/feeds/'+value+'/delete').status_code == (404 if len(value)>19 else 400)
    assert post(client, '/articles/'+value+'/read', {'value': '1'}).status_code == (404 if len(value)>19 else 400)
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0] == 1
        assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0] == 0
