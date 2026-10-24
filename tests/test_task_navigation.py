from threading import Thread
import pytest
from werkzeug.serving import make_server
from test_reader import app

@pytest.fixture
def live_empty(app):
    server=make_server("127.0.0.1",0,app)
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield "http://127.0.0.1:"+str(server.server_port)
    finally:server.shutdown();thread.join(timeout=5);server.server_close()
