"""Provider selection; credentials and wire contracts never cross gateways."""
import os
import re
from urllib.parse import quote
from flask import current_app
from . import openrouter_http as http

PROVIDERS = {'openrouter':{'name':'OpenRouter','key':'OPENROUTER_API_KEY'},
             'orcarouter':{'name':'OrcaRouter','key':'ORCAROUTER_API_KEY'}}


def configured(provider='openrouter'):
    if provider not in PROVIDERS:
        return False
    key = PROVIDERS[provider]['key']
    return bool(current_app.config.get(key) or os.environ.get(key))


def supported(provider, model):
    if model.startswith(('openrouter/','orcarouter/')):
        return False
    # Orca's structured-output support is upstream-dependent; do not imply tools are JSON schema.
    return provider == 'openrouter' or model.startswith(('openai/','google/','x-ai/'))


def generate(config, wire, input_bound):
    if config.get('provider','openrouter') == 'openrouter':
        return http.generate(config,wire,input_bound)
    return orca_generate(config,wire,input_bound)


def orca_generate(config,wire,input_bound):
    key = current_app.config.get('ORCAROUTER_API_KEY') or os.environ.get('ORCAROUTER_API_KEY','')
    if not isinstance(key,str) or not re.fullmatch(r'[A-Za-z0-9._-]{16,4096}',key):
        raise http.RouterError('orcarouter-credential-unconfigured')
    if not supported('orcarouter', config['model']):
        raise http.RouterError('orcarouter-model-unsupported')
    try:
        data, headers = http.request(wire,host='api.orcarouter.ai',path='/v1/chat/completions',api_key=key,
                                     response_headers=True,extra_headers={'X-OrcaRouter-Include-Cost':'true'})
        if not isinstance(data,dict) or not isinstance(data.get('usage'),dict):
            raise http.RouterError('orcarouter-usage-unknown')
        request_id = headers.get('x-orca-request-id','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,200}',request_id):
            raise http.RouterError('orcarouter-lineage-invalid')
        cost = data['usage'].get('cost_usd')
        settled = False
        # Never replay a charged POST. Receipt lookup is bounded and read-only.
        if cost is None:
            for attempt in range(2):
                try:
                    receipt = http.request('',host='api.orcarouter.ai',path='/v1/generation?id='+quote(request_id,safe=''),api_key=key,method='GET',timeout=10)
                    if not isinstance(receipt,dict) or not isinstance(receipt.get('data'),dict):
                        break
                    record = receipt['data']
                    if record.get('id') != request_id or record.get('cost_currency','USD') != 'USD':
                        break
                    cost = record.get('total_cost');settled = cost is not None;break
                except http.RouterError as exc:
                    if exc.code != 'openrouter-http-404' or attempt == 1:
                        break
        normalized={**data,'id':request_id,'usage':{**data['usage'],'cost':cost}}
        text,usage,lineage=http.validate_response(config,normalized,input_bound)
        lineage.update(adapter='orcarouter-topics-v1',provider='orcarouter',cost_source='settlement' if settled else 'inline')
        return text,usage,lineage
    except http.RouterError as exc:
        raise http.RouterError(exc.code.replace('openrouter-','orcarouter-',1),exc.retry_at) from None
