"""Bounded newline JSON framing for the private observation Unix socket."""
import json

MAX_MESSAGE = 8 * 1024 * 1024
MAX_TEXT = 50000
ERRORS = {
    'attachment': '添付を安全に抽出できません。形式・暗号化・解析上限を確認してください。',
    'selector': '対象要素が見つからないか、空です。CSS セレクターと待機時間を確認してください。',
    'invalid_selector': 'CSS セレクターが不正です。標準の CSS セレクターを指定してください。',
    'timeout': 'ページ観測が時間上限を超えました。',
    'network': 'ページを安全に取得できません。公開 URL・同一 origin・取得上限を確認してください。',
    'size': '観測テキストが 50,000 文字の上限を超えています。範囲を狭めてください。',
    'browser': 'ブラウザーを起動できないか、観測に失敗しました。renderer の稼働を確認してください。',
    'protocol': 'ページ観測サービスの応答が不正です。',
    'unavailable': 'ページ観測サービスに接続できません。renderer と接続パスを確認してください。',
}


class ObservationError(ValueError):
    def __init__(self, code):
        self.code = code if isinstance(code,str) and code in ERRORS else 'browser'
        super().__init__(ERRORS[self.code])


def send_message(stream, value, maximum=MAX_MESSAGE):
    data = json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode() + b'\n'
    if len(data) > maximum:
        raise ObservationError('protocol')
    stream.write(data)
    stream.flush()


def receive_message(stream, maximum=MAX_MESSAGE):
    try:
        data = stream.readline(maximum + 1)
        if not data or len(data) > maximum or not data.endswith(b'\n'):
            raise ValueError()
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except Exception:
        raise ObservationError('protocol') from None
