from itsdangerous import URLSafeTimedSerializer
from werkzeug.datastructures import MultiDict
from feedastrolabe import discovery
from feedastrolabe.db import get_db
from test_reader import app, client, post, RSS, META
from test_reader_navigation import markup


def plan(response):
    return markup(response.data).find('.//input[@name="plan"]').get('value')


def test_site_candidates_preview_and_confirm(app,client,monkeypatch):
    html=b'<link rel="alternate" type="application/rss+xml" href="../rss" title="RSS"><link rel="alternate" type="application/atom+xml" href="https://example.com/atom"><link rel="alternate" type="application/rss+xml" href="../rss">'
    calls=[]
    def fetch(url,**kwargs):
        calls.append(url)
        return (html,dict(META,url='https://example.com/news/page')) if len(calls)==1 else (RSS,META)
    monkeypatch.setattr(discovery,'fetch',fetch)
    found=post(client,'/sources/discover',{'url':'https://example.com/','folder':'Tech'})
    assert found.status_code==200 and len(calls)==1
    assert 'https://example.com/rss' in found.text and 'https://example.com/atom' in found.text
    result=post(client,'/sources/discover',{'url':'https://example.com/rss','folder':'Tech'})
    assert 'First story' in result.text and result.status_code==200
    with app.app_context(): assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0]==0
    token=plan(result)
    assert post(client,'/sources/confirm',{'plan':token+'x','folder':'Tech'}).status_code==400
    other=app.test_client()
    assert post(other,'/sources/confirm',{'plan':token,'folder':'Tech'}).status_code==400
    response=post(client,'/sources/confirm',{'plan':token,'folder':'Tech'})
    assert response.status_code==303
    assert post(client,'/sources/confirm',{'plan':token,'folder':'Tech'}).status_code==400
    with app.app_context():
        assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0]==1
        assert get_db().execute('SELECT folder FROM feeds').fetchone()[0]=='Tech'
        assert get_db().execute('SELECT count(*) FROM articles').fetchone()[0]==2


def test_discovery_bounds_invalid_and_expired(app,client,monkeypatch):
    parser=discovery.Alternates('https://example.com/')
    parser.feed('<link rel type><link rel="alternate" type="application/rss+xml" href="javascript:bad">'+''.join(f'<link rel="alternate" type="application/rss+xml" href="/{i}">' for i in range(30)))
    assert len(parser.candidates)==8
    monkeypatch.setattr(discovery,'fetch',lambda *a,**kw:(b'<html>No feed</html>',META))
    assert post(client,'/sources/discover',{'url':'https://example.com/'}).status_code==400
    monkeypatch.setattr(discovery,'fetch',lambda *a,**kw:(_ for _ in ()).throw(ValueError('private blocked')))
    assert post(client,'/sources/discover',{'url':'https://example.com/'}).status_code==400
    monkeypatch.setattr(discovery,'fetch',lambda *a,**kw:(RSS,META))
    token=plan(post(client,'/sources/discover',{'url':'https://example.com/feed'}))
    monkeypatch.setattr(discovery,'MAX_AGE',-1)
    assert post(client,'/sources/confirm',{'plan':token}).status_code==400
    assert client.post('/sources/confirm',data={'plan':token}).status_code==400
    with app.app_context():assert get_db().execute('SELECT count(*) FROM feeds').fetchone()[0]==0
