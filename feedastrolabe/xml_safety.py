"""Validate untrusted XML without resolving entities or retaining its tree."""
from io import BytesIO

from defusedxml.ElementTree import iterparse


def validate_xml(data, *, max_bytes, max_elements, max_depth=64):
    if not isinstance(data, bytes) or not data or len(data) > max_bytes:
        raise ValueError('XML のサイズまたは形式が不正です。')
    try:
        stack = []
        count = 0
        for event, element in iterparse(BytesIO(data), events=('start', 'end'),
                                        forbid_dtd=True, forbid_entities=True, forbid_external=True):
            if event == 'start':
                stack.append(element)
                count += 1
                if len(stack) > max_depth or count > max_elements:
                    raise ValueError()
            else:
                stack.pop()
                element.clear()
                if stack:
                    stack[-1].remove(element)
    except Exception:
        # Never surface source XML, external identifiers or raw parser errors.
        raise ValueError('安全な XML を指定してください。DTD・実体参照・不正な構造は処理できません。') from None
