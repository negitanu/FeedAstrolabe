"""Credential-free renderer. Docker enforces network_mode:none and no DB mount."""
import argparse
import base64
import fcntl
import multiprocessing
import os
from pathlib import Path
import signal
import socket
import stat

from .page_protocol import ObservationError, MAX_TEXT, send_message, receive_message


def render(job, fetch):
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    if (job.get('type') != 'capture' or not isinstance(job.get('url'), str) or len(job['url']) > 2048
            or not isinstance(job.get('selector'), str) or not 1 <= len(job['selector']) <= 500
            or type(job.get('settle_ms')) is not int or not 0 <= job['settle_ms'] <= 10000):
        raise ObservationError('protocol')
    network_failed = False
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True, proxy={'server': 'http://127.0.0.1:9'},
                args=['--proxy-bypass-list=<-loopback>', '--force-webrtc-ip-handling-policy=disable_non_proxied_udp', '--disable-background-networking'])
            try:
                context = browser.new_context(service_workers='block', accept_downloads=False, viewport={'width':1280,'height':720})
                context.route_web_socket('**/*', lambda ws: ws.close())
                page = context.new_page()
                page.set_default_timeout(10000)
                page.on('dialog', lambda dialog: dialog.dismiss())
                page.on('download', lambda download: download.cancel())
                context.on('page', lambda other: other.close() if other != page else None)
                def route_request(route):
                    nonlocal network_failed
                    request = route.request
                    if request.resource_type not in ('document','script','stylesheet','xhr','fetch'):
                        route.abort()
                        return
                    if request.resource_type == 'document' and request.frame != page.main_frame:
                        route.abort()
                        return
                    try:
                        response = fetch(request.url, request.method)
                        if response.get('type') != 'response':
                            raise ObservationError('network')
                        body = base64.b64decode(response['body'], validate=True)
                        route.fulfill(status=200, body=body, content_type=response['content_type'])
                    except Exception:
                        network_failed = True
                        route.abort()
                context.route('**/*', route_request)
                page.goto(job['url'], wait_until='domcontentloaded', timeout=30000)
                valid = page.evaluate('selector => {try {document.querySelectorAll(selector); return true;} catch {return false;}}',job['selector'])
                if not valid:
                    raise ObservationError('invalid_selector')
                try:
                    page.wait_for_function('selector => [...document.querySelectorAll(selector)].some(el => (el.innerText || "").trim())', arg=job['selector'], timeout=10000)
                except PlaywrightTimeout:
                    raise ObservationError('selector') from None
                page.wait_for_timeout(job['settle_ms'])
                value = page.evaluate('''({selector,limit}) => {
                    const elements = [...document.querySelectorAll(selector)];
                    if (elements.length > 5000) return {oversize:true};
                    const text = elements.map(el => el.innerText || '').join('\\n');
                    return text.length > limit ? {oversize:true} : {text};
                }''', {'selector':job['selector'],'limit':MAX_TEXT})
                if network_failed:
                    raise ObservationError('network')
                if value.get('oversize'):
                    raise ObservationError('size')
                if not value.get('text', '').strip():
                    raise ObservationError('selector')
                return value['text']
            finally:
                browser.close()
    except ObservationError:
        raise
    except PlaywrightTimeout:
        raise ObservationError('timeout') from None
    except Exception:
        raise ObservationError('network' if network_failed else 'browser') from None


def handle_connection(conn):
    os.setsid()
    conn.settimeout(40)
    with conn, conn.makefile('rwb') as stream:
        try:
            job = receive_message(stream)
            def fetch(url, method):
                send_message(stream, {'type':'fetch','url':url,'method':method})
                return receive_message(stream)
            text = render(job, fetch)
            send_message(stream, {'type':'result','text':text})
        except ObservationError as exc:
            try:
                send_message(stream, {'type':'error','code':exc.code})
            except Exception:
                pass
        except Exception:
            try:
                send_message(stream, {'type':'error','code':'browser'})
            except Exception:
                pass


def serve(endpoint, job_timeout=45):
    job_timeout = min(45, max(0.1, job_timeout))
    endpoint = Path(endpoint)
    endpoint.parent.mkdir(parents=True,exist_ok=True)
    endpoint.parent.chmod(0o700)
    with (endpoint.parent / 'renderer.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if endpoint.exists() or endpoint.is_symlink():
            if not stat.S_ISSOCK(endpoint.lstat().st_mode):
                raise ValueError('Renderer endpoint must be a Unix socket')
            endpoint.unlink()
        with socket.socket(socket.AF_UNIX) as server:
            server.bind(str(endpoint))
            endpoint.chmod(0o660)
            server.listen(4)
            print('Renderer ready',flush=True)
            while True:
                conn,_ = server.accept()
                process = multiprocessing.get_context('fork').Process(target=handle_connection,args=(conn,))
                process.start()
                process.join(job_timeout)
                if process.is_alive():
                    try:
                        with conn.makefile('rwb') as stream:
                            send_message(stream, {'type':'error','code':'timeout'})
                    except Exception:
                        pass
                # Kill the entire job group, including Chromium and driver.
                try:
                    os.killpg(process.pid,signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.join()
                conn.close()


def main():
    parser=argparse.ArgumentParser(description='Private Unix-socket renderer; use network-isolated Docker for public pages.')
    parser.add_argument('--socket',default=os.environ.get('FEEDASTROLABE_RENDER_SOCKET','/run/observer/renderer.sock'))
    args=parser.parse_args()
    serve(args.socket)


if __name__ == '__main__':
    main()
