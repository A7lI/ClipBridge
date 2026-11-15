"""Small authenticated, encrypted LAN protocol shared with the Android client."""
import base64
import json
import os
import re
import threading
import time

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAX_IMAGE = 12 * 1024 * 1024
MAX_FILES = 300 * 1024 * 1024
MAX_FILE_COUNT = 20
MAX_AUDIO = 16000 * 2 * 60
MAX_BODY = 24 * 1024 * 1024


def b64(data):
    return base64.b64encode(data).decode('ascii')


def unb64(value):
    return base64.b64decode(value, validate=True)


class Protocol:
    def __init__(self, key):
        self.cipher = AESGCM(key)
        self.seen = {}
        self.lock = threading.Lock()

    def open(self, path, body):
        envelope = json.loads(body)
        nonce = unb64(envelope['nonce'])
        if len(nonce) != 12:
            raise ValueError('Invalid nonce')
        raw = self.cipher.decrypt(nonce, unb64(envelope['data']), ('CB1 ' + path).encode())
        value = json.loads(raw)
        now = time.time()
        if abs(value['time'] - now) > 120:
            raise ValueError('Device clocks differ. Enable automatic date and time.')
        with self.lock:
            self.seen = {k: v for k, v in self.seen.items() if now-v < 125}
            if nonce in self.seen:
                raise ValueError('Repeated request')
            self.seen[nonce] = now
        return value, envelope['nonce']

    def seal(self, path, request_nonce, value):
        nonce = os.urandom(12)
        aad = ('CB1 reply ' + path + ' ' + request_nonce).encode()
        data = self.cipher.encrypt(nonce, json.dumps(value, ensure_ascii=False).encode(), aad)
        return json.dumps({'nonce': b64(nonce), 'data': b64(data)}).encode()


def validate_clip(value):
    """Normalize supported data before either machine touches its clipboard."""
    if not isinstance(value, dict):
        raise ValueError('Invalid clipboard item')
    kind = value.get('kind')
    if kind == 'text':
        text = value.get('text')
        if not isinstance(text, str) or len(text.encode('utf-8')) > 1024 * 1024 or '\x00' in text:
            raise ValueError('Text must be under 1 MB with no null characters')
        return {'kind': 'text', 'text': text}
    if kind == 'image':
        data = unb64(value['data'])
        if len(data) > MAX_IMAGE:
            raise ValueError('Image exceeds 12 MB')
        import io
        from PIL import Image
        with Image.open(io.BytesIO(data)) as im:
            if im.width * im.height > 24_000_000:
                raise ValueError('Image exceeds 24 megapixels')
            im.load()
            out = io.BytesIO()
            im.convert('RGBA').save(out, format='PNG')
        if out.tell() > MAX_IMAGE:
            raise ValueError('PNG image exceeds 12 MB')
        return {'kind': 'image', 'data': b64(out.getvalue())}
    if kind == 'files':
        files = value.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILE_COUNT:
            raise ValueError('Send between 1 and 20 files at a time')
        result, total = [], 0
        for file in files:
            if not isinstance(file, dict):
                raise ValueError('Invalid file')
            name = safe_filename(file.get('name'))
            data = unb64(file['data'])
            total += len(data)
            if total > MAX_FILES:
                raise ValueError('Files exceed 300 MB in total')
            result.append({'name': name, 'data': b64(data)})
        return {'kind': 'files', 'files': result}
    raise ValueError('Only text, images and files are supported')


def safe_filename(name):
    if not isinstance(name, str) or not name or len(name) > 240:
        raise ValueError('Invalid filename')
    if name in ('.', '..') or re.search(r'[\x00-\x1f<>:"/\\|?*]', name) or name.endswith((' ', '.')):
        raise ValueError('Unsafe filename')
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}:
        raise ValueError('Reserved filename')
    return name
