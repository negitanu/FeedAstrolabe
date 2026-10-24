"""Fixed, pinned OpenRouter HTTPS. Never retry a possibly charged POST."""
from decimal import Decimal, InvalidOperation, ROUND_CEILING
import json
import os
import re
import time

from flask import current_app
from .assistant_http import ModelError
from .fetch import PinnedHTTP, public_address
from .social_http import retry_time

MAX_INPUT = 32768


class RouterError(ModelError):
    def __init__(self, code, retry_at=None):
        super().__init__(code)
        self.retry_at = retry_at


def configured():
    return bool(current_app.config.get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_API_KEY'))


def credential():
    value = current_app.config.get('OPENROUTER_API_KEY') or os.environ.get('OPENROUTER_API_KEY', '')
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9._-]{16,4096}', value):
        raise RouterError('openrouter-credential-unconfigured')
    return value


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate-key')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('non-finite')))


def micro_usd(value):
    try:
        if isinstance(value, bool) or not isinstance(value, (int, float, str)):
            raise ValueError()
        amount = Decimal(str(value))
        if not amount.is_finite() or not 0 <= amount <= 100:
            raise ValueError()
        return int((amount*1000000).to_integral_value(rounding=ROUND_CEILING))
    except (ValueError, InvalidOperation, OverflowError):
        raise RouterError('openrouter-cost-invalid') from None


def request(wire, *, host='openrouter.ai', path='/api/v1/chat/completions', api_key=None, response_headers=False, method='POST', extra_headers=None, timeout=90):
    conn = None
    try:
        if not isinstance(wire, str) or len(wire.encode()) > MAX_INPUT:
            raise RouterError('openrouter-input-size')
        secret = credential() if api_key is None else api_key
        deadline = time.monotonic()+timeout
        address = public_address(host, 443)
        remaining = deadline-time.monotonic()
        if remaining <= 0:
            raise RouterError('openrouter-timeout')
        conn = PinnedHTTP(host, 443, address, True, min(10, remaining))
        conn.request(method, path, body=wire.encode() if method=='POST' else None, headers={
            'Authorization': 'Bearer '+secret, 'Content-Type': 'application/json', 'Accept': 'application/json',
            'Accept-Encoding': 'identity', 'User-Agent': 'FeedAstrolabe/0.16', 'X-OpenRouter-Title': 'FeedAstrolabe', **(extra_headers or {})})
        # A non-streaming completion can take longer than the connection timeout.
        remaining = deadline-time.monotonic()
        if remaining<=0:
            raise RouterError('openrouter-timeout')
        if conn.sock:
            conn.sock.settimeout(min(60,remaining))
        response = conn.getresponse()
        if response.status == 429:
            raise RouterError('openrouter-rate-limited', retry_time({k.lower(): v for k, v in response.getheaders()}))
        if response.status != 200:
            raise RouterError('openrouter-http-'+str(response.status))
        if response.getheader('Content-Encoding', 'identity').lower() not in ('', 'identity'):
            raise RouterError('openrouter-encoding')
        if int(response.getheader('Content-Length', '0')) > 1048576:
            raise RouterError('openrouter-response-size')
        raw = bytearray()
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise RouterError('openrouter-timeout')
            if conn.sock:
                conn.sock.settimeout(min(10, remaining))
            part = response.read1(min(65536, 1048577-len(raw)))
            if not part:
                break
            raw.extend(part)
            if len(raw) > 1048576:
                raise RouterError('openrouter-response-size')
        data = strict_json(raw)
        return (data, {k.lower():v for k,v in response.getheaders()}) if response_headers else data
    except RouterError:
        raise
    except Exception:
        raise RouterError('openrouter-transport-or-format') from None
    finally:
        if conn:
            conn.close()


def generate(config, wire, input_bound):
    return validate_response(config, request(wire), input_bound)


def validate_response(config, data, input_bound):
    actual_model = data.get('model') if isinstance(data,dict) else None
    base_model = config['model'].split(':')[0]
    valid_model = isinstance(actual_model,str) and (actual_model==config['model'] or re.fullmatch(re.escape(base_model)+r'(?:-(?:[0-9]{8}|[0-9]{4}-[0-9]{2}-[0-9]{2}))?',actual_model))
    if not isinstance(data, dict) or data.get('error') or not valid_model:
        raise RouterError('openrouter-response-shape')
    choices = data.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict) or choices[0].get('finish_reason') != 'stop':
        raise RouterError('openrouter-incomplete-response')
    message = choices[0].get('message')
    if not isinstance(message, dict) or message.get('role') != 'assistant' or message.get('tool_calls') or message.get('function_call') or message.get('refusal'):
        raise RouterError('openrouter-tools-or-refusal')
    text = message.get('content')
    if not isinstance(text, str) or len(text) > 16000:
        raise RouterError('openrouter-output-size')
    usage = data.get('usage')
    if not isinstance(usage, dict) or any(type(usage.get(k)) is not int or usage[k]<0 for k in ('prompt_tokens', 'completion_tokens')):
        raise RouterError('openrouter-usage-unknown')
    if usage['prompt_tokens'] > input_bound or usage['completion_tokens'] > config['max_output_tokens']:
        raise RouterError('openrouter-token-budget')
    actual = micro_usd(usage.get('cost'))
    generation_id = data.get('id')
    if not isinstance(generation_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', generation_id):
        raise RouterError('openrouter-lineage-invalid')
    lineage = {'adapter':'openrouter-topics-v1', 'requested_model':config['model'], 'response_model':data['model'], 'generation_id':generation_id}
    return text, {'prompt_tokens':usage['prompt_tokens'], 'completion_tokens':usage['completion_tokens'], 'cost_micro_usd':actual}, lineage
