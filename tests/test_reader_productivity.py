from urllib.parse import urlencode, urlsplit, parse_qs
import pytest
from werkzeug.datastructures import MultiDict
from feedastrolabe import create_app
from feedastrolabe.db import get_db, init_database, connect
from test_reader import app, client, post, subscribe
from test_reader_platform import ids
from test_reader_navigation import markup


def test_visits_independent_restart_delete(app,client,tmp_path):
    subscribe(client)
    assert client.get('/?article=1').status_code==200
    post(client,'/articles/1/read',{'value':'1'})
    post(client,'/articles/2/star',{'value':'1'})
    with app.app_context():assert get_db().execute('SELECT count(*) FROM article_visits').fetchone()[0]==0
    assert client.post('/articles/1/visit').status_code==400
    assert post(client,'/articles/999/visit').status_code==404
    for identifier in (1,2,1):
        assert post(client,f'/articles/{identifier}/visit',headers={'X-Reader-Visit':'1'}).status_code==204
    restarted=create_app({'TESTING':True,'DATA_DIR':app.instance_path})
    with restarted.app_context():
        db=get_db()
        assert [r[0] for r in db.execute('SELECT article_id FROM article_visits ORDER BY visited_at DESC')]==[1,2]
        assert db.execute('SELECT is_read,is_starred FROM articles WHERE id=1').fetchone()[:]==(1,0)
        assert db.execute('SELECT is_read,is_starred FROM articles WHERE id=2').fetchone()[:]==(0,1)
        with db:db.execute('DELETE FROM articles WHERE id=1')
        assert db.execute('SELECT count(*) FROM article_visits').fetchone()[0]==1
    assert ids(client.get('/?view=history'))==[2]


def test_history_migration_and_bundle(app,client,tmp_path):
    subscribe(client)
    with app.app_context():
        db=get_db()
        with db:
            db.execute('DROP TABLE article_visits')
            db.execute('PRAGMA user_version=18')
    from feedastrolabe.evidence_backup import backup_bundle,restore_bundle
    backup_bundle(app.config['DATABASE'],tmp_path/'schema18-bundle')
    restore_bundle(tmp_path/'schema18-bundle',tmp_path/'schema18-restored'/'feeds.sqlite3')
    with connect(tmp_path/'schema18-restored'/'feeds.sqlite3') as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==19
        assert db.execute('SELECT count(*) FROM articles').fetchone()[0]==2
        assert db.execute('SELECT count(*) FROM article_visits').fetchone()[0]==0
    init_database(app.config['DATABASE'])
    post(client,'/articles/1/visit')
    backup_bundle(app.config['DATABASE'],tmp_path/'bundle')
    restore_bundle(tmp_path/'bundle',tmp_path/'restored'/'feeds.sqlite3')
    with connect(tmp_path/'restored'/'feeds.sqlite3') as db:
        assert db.execute('PRAGMA user_version').fetchone()[0]==19
        assert db.execute('SELECT count(*) FROM article_visits').fetchone()[0]==1
        assert db.execute('SELECT count(*) FROM articles').fetchone()[0]==2


def test_sort_keysets_neighbours_history_and_scope(app,client):
    subscribe(client)
    with app.app_context(),get_db() as db:
        for n in range(3,75):
            db.execute('INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at) VALUES(?,1,?,?,?, ?,?)',
                       (n,str(n),f'Article {n}','','needle','2026-10-08'))
    first=client.get('/?sort=oldest')
    seen=ids(first)
    next_url=markup(first.data).find('.//*[@data-article-loader]').get('data-more-url')
    assert client.get(next_url.replace('sort=oldest','sort=newest')).status_code==400
    while next_url:
        result=client.get(next_url)
        assert result.status_code==200
        seen+=ids(type('Response',(),{'data':result.json['html'].encode()})())
        next_url=result.json['next']
    with app.app_context():
        expected=[r[0] for r in get_db().execute('SELECT id FROM articles ORDER BY published_at,id')]
    assert seen==expected and len(seen)==len(set(seen))==74
    detail=client.get('/?sort=oldest&article=30')
    nav=markup(detail.data).find('.//a[@rel="next"]')
    assert 'article=31' in nav.get('href') and 'sort=oldest' in nav.get('href')
    response=post(client,'/articles/30/read-next',{'sort':'oldest'})
    assert 'article=31' in response.location and 'sort=oldest' in response.location
    for n in (74,1,30):post(client,f'/articles/{n}/visit')
    assert ids(client.get('/?view=history'))==[30,1,74]
    assert client.get('/?sort=arbitrary').status_code==400
    assert client.get('/?sort=recent').status_code==400


def test_detailed_search_preserves_scope_and_bulk(app,client):
    subscribe(client)
    subscribe(client,'https://example.com/other')
    with app.app_context(),get_db() as db:
        db.execute("UPDATE articles SET source_published_at='2026-10-07 15:30:00',published_at='2026-10-07 15:30:00',title='Alpha',search_text='needle red' WHERE id=1")
        db.execute("UPDATE articles SET source_published_at='2026-10-07 14:59:59',title='needle red',search_text='Alpha' WHERE id=2")
        db.execute("UPDATE articles SET source_published_at='2026-10-07 16:00:00',search_text='needle red blocked' WHERE id=3")
        db.execute("UPDATE articles SET source_published_at=NULL,search_text='needle red' WHERE id=4")
        db.execute("UPDATE settings SET display_timezone='Asia/Tokyo'")
    values={'q':'needle','search_in':'body','any_terms':'blue\nred','exclude':'blocked','date_from':'2026-10-08','date_to':'2026-10-08','sources':[1,2],'sort':'oldest'}
    result=client.get('/?'+urlencode(values,doseq=True))
    assert result.status_code==200 and ids(result)==[1]
    detail=client.get('/?'+urlencode({**values,'article':1},doseq=True))
    tree=markup(detail.data)
    read_form=tree.find('.//form[@action="/articles/1/read"]')
    assert [x.get('value') for x in read_form.findall('input[@name="sources"]')]==['1','2']
    assert read_form.find('input[@name="search_in"]').get('value')=='body'
    post(client,'/articles/read-all',values)
    with app.app_context():assert [r[0] for r in get_db().execute('SELECT id FROM articles WHERE is_read=1')]==[1]
    values['q']='red';values['search_in']='title';values.pop('date_from');values.pop('date_to');values['exclude']=''
    assert ids(client.get('/?'+urlencode(values,doseq=True)))==[2]


@pytest.mark.parametrize('query',[{'date_from':'2026-02-30'},{'date_from':'2026-10-09','date_to':'2026-10-08'},
    {'search_in':'sql'},{'sources':['1','1']},{'sources':['0']},{'sources':['999999999999999999999']},
    {'any_terms':'\n'.join(str(n) for n in range(11))},{'exclude':'x'*201}])
def test_invalid_detailed_filters_do_not_mutate(app,client,query):
    subscribe(client)
    assert client.get('/?'+urlencode(query,doseq=True)).status_code==400
    assert post(client,'/articles/read-all',query).status_code==400
    with app.app_context():assert get_db().execute('SELECT sum(is_read) FROM articles').fetchone()[0]==0


def test_search_unknown_source_and_literal_matching(app,client):
    subscribe(client)
    assert client.get('/?sources=999').status_code==404
    assert ids(client.get('/?q=100%25'))==[1]
    assert ids(client.get('/?any_terms=100_'))==[]
    assert ids(client.get('/?exclude=100%25'))==[2]
    assert client.get('/?search_in=title&search_in=body').status_code==400


@pytest.fixture
def productivity_data(app):
    with app.app_context(),get_db() as db:
        for n in (1,2):
            db.execute('INSERT INTO feeds(id,url,title,folder,created_at) VALUES(?,?,?,?,?)',(n,f'https://example.com/{n}',f'情報源 {n}','ニュース','2026-10-25'))
        for n in range(1,91):
            stamp=f'2026-10-{1+n%20:02d} 12:00:00'
            db.execute('INSERT INTO articles(id,feed_id,guid,title,content,search_text,published_at,source_published_at) VALUES(?,?,?,?,?,?,?,?)',
                       (n,1+n%2,str(n),f'記事 {n}','<p>body match 内容</p>','body match 内容',stamp,stamp))


def test_date_cursor_rejects_timezone_change(app,client,productivity_data):
    with app.app_context(),get_db() as db:
        db.execute("UPDATE articles SET source_published_at='2026-10-08 12:00:00'")
    result=client.get('/?date_from=2026-10-08&date_to=2026-10-08')
    more=markup(result.data).find('.//*[@data-article-loader]').get('data-more-url')
    assert client.get(more).status_code==200
    with app.app_context(),get_db() as db:db.execute("UPDATE settings SET display_timezone='Asia/Tokyo'")
    assert client.get(more).status_code==400
