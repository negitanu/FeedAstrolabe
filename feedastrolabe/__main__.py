import os
from waitress import serve
from . import create_app

if __name__ == '__main__':
    serve(create_app(), host=os.environ.get('FEEDASTROLABE_BIND_HOST', '127.0.0.1'),
          port=int(os.environ.get('FEEDASTROLABE_PORT', '5000')), threads=4)
