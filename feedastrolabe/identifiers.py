"""Validate HTTP database identifiers before routing or scoped operations."""
from flask import abort
from werkzeug.exceptions import BadRequest
from werkzeug.routing import IntegerConverter

MAX_ID = 2**63 - 1


class DatabaseIDConverter(IntegerConverter):
    regex = r'[0-9]{1,19}'

    def to_python(self, value):
        identifier = super().to_python(value)
        if not 1 <= identifier <= MAX_ID:
            raise BadRequest(description='ID は正の整数で指定してください。')
        return identifier


def single_value(values, name, default=None):
    entries = values.getlist(name)
    if not entries:
        return default
    if len(entries) != 1:
        abort(400, description=name + ' は一つだけ指定してください。')
    return entries[0]


def optional_id(values, name):
    value = single_value(values, name, '').strip()
    if not value:
        return None
    if not value.isascii() or not value.isdecimal() or len(value) > 19 or not 1 <= int(value) <= MAX_ID:
        abort(400, description=name + ' は正の整数 ID で指定してください。')
    return int(value)
