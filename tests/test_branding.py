from test_reader import app, client
from test_reader_navigation import markup


def test_brand_favicon_across_pages(client):
    for path in ('/', '/sources/new/rss', '/settings'):
        result=client.get(path)
        assert result.status_code==200
        tree=markup(result.data)
        assert tree.find('.//link[@rel="icon"]').get('href')=='/static/brand-mark.svg'
        assert tree.find('.//span[@class="app-brand-mark"]').get('aria-hidden')=='true'
    asset=client.get('/static/brand-mark.svg')
    assert asset.status_code==200 and asset.mimetype=='image/svg+xml'
    assert b'viewBox="0 0 32 32"' in asset.data
