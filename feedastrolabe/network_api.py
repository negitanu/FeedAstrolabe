"""Authenticated scoped passive network history and explicit lookup reservation."""
import json
from flask import Blueprint,request
from .research_api import errors,page
from .keys import authenticate_api
from . import network_intelligence as n,research as r
api=Blueprint('network_api',__name__,url_prefix='/api/v1');api.before_request(authenticate_api)

def decoded(row):
    item=dict(row)
    for field in ('normalized','changes'):
        if field in item:item[field]=json.loads(item[field])
    return item

@api.get('/workspaces/<int:identifier>/network-watches')
def watches(identifier):
    with errors():r.find('workspace',identifier)
    return page('SELECT * FROM network_watches WHERE workspace_id=?',[identifier])

@api.post('/workspaces/<int:identifier>/network-watches')
def create(identifier):
    with errors():wid=n.save_watch(identifier,request.get_json())
    return detail(wid),201

@api.get('/network-watches/<int:identifier>')
def detail(identifier):
    with errors():return {'data':n.card(identifier)}

@api.patch('/network-watches/<int:identifier>')
def update(identifier):
    with errors():item=n.watch(identifier);n.save_watch(item['workspace_id'],request.get_json(),identifier)
    return detail(identifier)

@api.post('/network-watches/<int:identifier>/lookup')
def lookup(identifier):
    if request.get_data():
        from flask import abort
        abort(400,description='Empty body required')
    with errors():return {'data':n.lookup(identifier)},202

@api.get('/network-watches/<int:identifier>/observations')
def observations(identifier):
    with errors():n.watch(identifier)
    return page('SELECT * FROM network_observations WHERE watch_id=?',[identifier],transform=decoded)

@api.get('/network-watches/<int:identifier>/events')
def events(identifier):
    with errors():n.watch(identifier)
    return page('SELECT * FROM network_events WHERE watch_id=?',[identifier],transform=decoded)
