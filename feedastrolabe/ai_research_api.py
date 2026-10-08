"""Read/write key protected research metadata, sourced cards and evaluations."""
from flask import Blueprint,request,abort
from .keys import authenticate_api
from .research_api import errors,page
from . import ai_research as a,research as r
api=Blueprint('ai_api',__name__,url_prefix='/api/v1');api.before_request(authenticate_api)

@api.get('/workspaces/<int:identifier>/ai-watches')
def watches(identifier):
 with errors():r.find('workspace',identifier)
 return page('SELECT * FROM ai_watches WHERE workspace_id=?',[identifier])

@api.post('/workspaces/<int:identifier>/ai-watches')
def create_watch(identifier):
 with errors():wid=a.save_watch(identifier,request.get_json())
 return watch(wid),201

@api.get('/ai-watches/<int:identifier>')
def watch(identifier):
 with errors():return {'data':a.watch_card(identifier)}

@api.patch('/ai-watches/<int:identifier>')
def update_watch(identifier):
 with errors():item=a.find('ai_watches',identifier);a.save_watch(item['workspace_id'],request.get_json(),identifier)
 return watch(identifier)

@api.post('/ai-watches/<int:identifier>/lookup')
def lookup(identifier):
 if request.get_data():abort(400,description='Empty body required')
 with errors():return {'data':{'job_id':a.lookup(identifier)}},202

@api.get('/ai-watches/<int:identifier>/versions')
def versions(identifier):
 with errors():a.find('ai_watches',identifier)
 with errors():query=r.text(request.args.get('q',''),'q',100)
 return page('SELECT * FROM ai_versions WHERE watch_id=?'+(' AND instr(lower(payload),lower(?))>0' if query else ''),[identifier,query] if query else [identifier],transform=a.decoded)

@api.get('/workspaces/<int:identifier>/ai-cards')
def cards(identifier):
 with errors():r.find('workspace',identifier)
 return page('SELECT * FROM ai_cards WHERE workspace_id=?',[identifier],transform=a.decoded)

@api.post('/workspaces/<int:identifier>/ai-cards')
def create_card(identifier):
 with errors():cid=a.create_card(identifier,request.get_json())
 return card(cid),201

@api.get('/ai-cards/<int:identifier>')
def card(identifier):
 with errors():return {'data':a.card(identifier)}

@api.post('/ai-cards/<int:identifier>/links')
def link(identifier):
 with errors():lid=a.add_link(identifier,request.get_json())
 return {'data':{'id':lid}},201

@api.get('/ai-cards/<int:identifier>/benchmarks')
def benchmarks(identifier):
 with errors():a.find('ai_cards',identifier)
 return page('SELECT * FROM ai_benchmarks WHERE card_id=?',[identifier],transform=a.decoded)

@api.post('/ai-cards/<int:identifier>/benchmarks')
def create_benchmark(identifier):
 with errors():bid=a.benchmark(identifier,request.get_json())
 return {'data':{'id':bid}},201

@api.get('/ai-benchmarks/<int:left>/compare/<int:right>')
def compare(left,right):
 with errors():return {'data':a.compare(left,right)}
