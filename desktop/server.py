import ipaddress
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

from protocol import Protocol, MAX_BODY, MAX_AUDIO, unb64, validate_clip
from delivery import Deliveries
from chunks import Chunks, manifest, get_chunk


class State:
    def __init__(self, key, apply_clip, speech, *, read_text=None):
        self.protocol = Protocol(key)
        self.apply_clip = apply_clip
        self.speech = speech
        self.read_text = read_text
        self.changed = threading.Condition(threading.RLock())
        self.deliveries = Deliveries(self.changed)
        self.chunks = Chunks()
        self.chunk_devices = set()
        self.item = None
        self.revision = 0
        self.paused = True
        self.last_seen = 0
        self.device = ''
        self.last_event = 'Ready to pair'
        self.last_error = ''

    def publish(self, item, source):
        with self.changed:
            self.revision += 1
            self.item = dict(item, revision=self.revision, source=source)
            self.last_error = ''
            self.last_event = ('Phone → PC' if source != 'pc' else 'PC → phone') + ' · ' + item['kind']
            self.changed.notify_all()

    def pause(self, value):
        with self.changed:
            self.paused = value
            if value:
                self.deliveries.cancel()
                self.chunks.clear()
            self.item = None
            self.revision += 1
            self.changed.notify_all()

    def send_files(self, item):
        with self.changed:
            if self.paused:
                raise ValueError('Sync is paused on the PC. Resume it in ClipBridge first.')
            identity = self.deliveries.enqueue(item)
            self.last_event = 'Sending files to your phone…'
        result = self.deliveries.wait(identity)
        self.last_event = result['message']
        return result

    def dispatch(self, path, data, *, protocol=None):
        source = str(data.get('device', ''))
        if not source or len(source) > 80 or source == 'pc':
            raise ValueError('Invalid device ID')
        with self.changed:
            if protocol is not None and protocol is not self.protocol:
                raise ValueError('Pairing was reset on the PC. Scan the new QR code.')
            if path == '/v1/pair':
                return {'ok': True, 'paused': self.paused}
            if path == '/v1/clipboard/current':
                if self.paused:
                    return {'ok': False, 'error': 'Sync is paused on the PC. Start syncing first.'}
                if self.read_text is None:
                    return {'ok': False, 'error': 'Reading the PC clipboard is unavailable.'}
                text = self.read_text()
                item = validate_clip({'kind': 'text', 'text': text}) if text else None
                return {'ok': True, 'item': item}
            self.last_seen = time.monotonic()
            self.device = source
        if path == '/v1/poll':
            after = int(data.get('after', 0))
            with self.changed:
                capable = data.get('file_delivery') == 1
                if data.get('file_chunks') == 1:
                    self.chunk_devices.add(source)
                self.deliveries.offer(source, capable)
                self.changed.wait_for(lambda: self.revision != after or (capable and any(task['device'] == source for task in self.deliveries.pending)), timeout=15)
                transfer = self.deliveries.offer(source, capable) if not self.paused else None
                item = self.item if not self.paused and self.item and self.item['source'] != source else None
                if source in self.chunk_devices:
                    if transfer:
                        transfer = dict(transfer, item=manifest(transfer['item'], transfer['id']))
                    if item and item['kind'] == 'files':
                        item = dict(manifest(item, 'clipboard-'+str(self.revision)), revision=self.revision)
                else:
                    # Older phones cannot safely read a 300 MB JSON envelope.
                    if transfer and sum(len(f['data']) for f in transfer['item']['files']) > 16*1024*1024:
                        raise ValueError('Update the phone app to ClipBridge 0.6.0 for large files')
                    if item and item['kind'] == 'files' and sum(len(f['data']) for f in item['files']) > 16*1024*1024:
                        item = None
                return {'ok': True, 'revision': self.revision, 'item': item, 'paused': self.paused,
                        'voice': self.speech.available(), 'transfer': transfer}
        if path == '/v1/files/get':
            with self.changed:
                if self.paused:
                    raise ValueError('Sync is paused')
                identity = data.get('id')
                if identity == 'clipboard-'+str(self.revision) and self.item and self.item['source'] != source and self.item['kind'] == 'files':
                    return get_chunk(self.item, data)
                task = next((t for t in self.deliveries.pending if t['wire']['id'] == identity and t['device'] == source), None)
                if not task:
                    raise ValueError('Transfer expired or clipboard changed. Send the files again.')
                return get_chunk(task['wire']['item'], data)
        if path in ('/v1/files/begin', '/v1/files/put', '/v1/files/commit', '/v1/files/cancel'):
            with self.changed:
                if self.paused:
                    raise ValueError('Sync is paused')
                result = self.chunks.dispatch(path, data, source)
                if path == '/v1/files/commit':
                    self.apply_clip(result)
                    self.publish(result, source)
                    return {'ok': True, 'revision': self.revision}
                return result
        if path == '/v1/files/ack':
            self.deliveries.ack(source, str(data.get('id', '')), data.get('saved') is True,
                                data.get('error', 'Could not save files on phone'))
            return {'ok': True}
        if path == '/v1/clipboard':
            item = validate_clip(data['item'])
            # The clipboard callback and publish are one ordered operation. The
            # Windows observer uses this same lock to prevent reflection loops.
            with self.changed:
                if self.paused:
                    return {'ok': False, 'error': 'Sync is paused on the PC.'}
                self.apply_clip(item)
                self.publish(item, source)
                return {'ok': True, 'revision': self.revision}
        if path == '/v1/transcribe':
            audio = unb64(data['audio'])
            if not audio or len(audio) % 2 or len(audio) > MAX_AUDIO:
                raise ValueError('Record between 0 and 60 seconds of mono PCM16 audio')
            return {'ok': True, 'text': self.speech.transcribe(audio)}
        raise ValueError('Unknown endpoint')


class Server(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 8

    def __init__(self, address, state):
        self.state = state
        self.capacity = threading.BoundedSemaphore(8)
        super().__init__(address, Handler)

    def process_request(self, request, address):
        if not self.capacity.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except Exception:
            self.capacity.release()
            raise

    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.capacity.release()


class Handler(BaseHTTPRequestHandler):
    server_version = 'ClipBridge'

    def setup(self):
        super().setup()
        self.connection.settimeout(25)

    def log_message(self, *_):
        pass  # No clipboard, audio, addresses, or pairing secrets in logs.

    def reply(self, status, raw):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        request_nonce = None
        state = self.server.state
        protocol = state.protocol
        try:
            address = ipaddress.ip_address(self.client_address[0])
            if not address.is_private or self.headers.get('Origin'):
                self.reply(403, b'{"error":"Local paired app only"}')
                return
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY or self.headers.get('Transfer-Encoding'):
                self.reply(413, b'{"error":"Invalid request size"}')
                return
            body = self.rfile.read(length)
            if len(body) != length:
                return
            data, request_nonce = protocol.open(self.path, body)
        except Exception:
            self.reply(401, b'{"error":"Pairing failed or device clocks differ"}')
            return
        try:
            value = state.dispatch(self.path, data, protocol=protocol)
        except Exception as exc:
            state.last_error = str(exc)[:200]
            value = {'ok': False, 'error': state.last_error}
        try:
            self.reply(200, protocol.seal(self.path, request_nonce, value))
        except (OSError, TimeoutError):
            pass
