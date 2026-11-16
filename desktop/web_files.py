"""Disk-backed, bounded file transfers for one authenticated web connection."""
import io
import hashlib
import mimetypes
import os
from pathlib import Path
import shutil
import tempfile
import uuid

from PIL import Image

from file_transfer import RECEIVED
from protocol import MAX_FILES, MAX_FILE_COUNT, MAX_IMAGE, safe_filename, b64, unb64

WEB_CHUNK = 16 * 1024
STREAM_BLOCK = 1024 * 1024


def file_manifest(paths):
    if not 1 <= len(paths) <= MAX_FILE_COUNT:
        raise ValueError('Choose between 1 and 20 files')
    files = []
    total = 0
    for path in paths:
        path = Path(path)
        if not path.is_file():
            raise ValueError('Zip folders before sending them')
        size = path.stat().st_size
        total += size
        if total > MAX_FILES:
            raise ValueError('Files exceed 300 MB in total')
        files.append({'name': safe_filename(path.name), 'size': size,
                      'type': mimetypes.guess_type(path.name)[0] or 'application/octet-stream'})
    return files


class WebFiles:
    def __init__(self, bridge):
        self.bridge = bridge
        self.temp = tempfile.TemporaryDirectory(prefix='ClipBridge-web-')
        self.folder = Path(self.temp.name)
        self.upload = None
        self.download = None

    def close(self):
        self.temp.cleanup()

    def dispatch(self, path, data):
        if self.bridge.state.paused:
            raise ValueError('Sync is paused on the PC. Start syncing first.')
        if not self.bridge.clipboard:
            raise ValueError('Update the Windows companion for files and photos')
        if path == '/v2/files/begin':
            return self.begin(data)
        if path == '/v2/files/put':
            return self.put(data)
        if path == '/v2/files/put-stream':
            return self.put_stream(data)
        if path == '/v2/files/commit':
            return self.commit(data)
        if path == '/v2/files/current':
            return self.current(data)
        if path == '/v2/files/get':
            return self.get(data)
        if path == '/v2/files/get-stream':
            return self.get_stream(data)
        if path == '/v2/files/ack':
            task = self.download
            if not task or data.get('id') != task['id']:
                raise ValueError('Unknown file transfer')
            if data.get('saved') is not True:
                raise ValueError('The phone has not received the files')
            if self.bridge.outbox and self.bridge.outbox['id'] == task['outbox']:
                self.bridge.outbox = None
            self.bridge.status = 'Files received by the web app · ready for another transfer'
            return {'ok': True}
        raise ValueError('Unknown file operation')

    def begin(self, data):
        if self.upload:
            raise ValueError('Finish the current upload first')
        files = data.get('files')
        if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILE_COUNT:
            raise ValueError('Choose between 1 and 20 files')
        total = 0
        paths = []
        for index, file in enumerate(files):
            name = safe_filename(file['name'])
            size = file['size']
            if type(size) is not int or size < 0:
                raise ValueError('Invalid file size')
            total += size
            if total > MAX_FILES:
                raise ValueError('Files exceed 300 MB in total')
            target = self.folder / 'upload' / str(index) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.touch()
            paths.append(target)
        self.upload = {'id': str(uuid.uuid4()), 'paths': paths, 'sizes': [file['size'] for file in files]}
        return {'ok': True, 'id': self.upload['id'], 'chunk_size': WEB_CHUNK,
                'stream_version': 1, 'stream_block_size': STREAM_BLOCK}

    def put(self, data):
        task = self.upload
        if not task or data.get('id') != task['id']:
            raise ValueError('Unknown upload')
        index = data.get('index')
        if type(index) is not int or not 0 <= index < len(task['paths']):
            raise ValueError('Invalid file index')
        target = task['paths'][index]
        if type(data.get('offset')) is not int or data['offset'] != target.stat().st_size:
            raise ValueError('Invalid file offset')
        raw = unb64(data['data'])
        if not raw or len(raw) > WEB_CHUNK or target.stat().st_size + len(raw) > task['sizes'][index]:
            raise ValueError('Invalid chunk size')
        with target.open('ab') as output:
            output.write(raw)
        return {'ok': True}

    def commit(self, data):
        task = self.upload
        if not task or data.get('id') != task['id']:
            raise ValueError('Unknown upload')
        if [p.stat().st_size for p in task['paths']] != task['sizes']:
            raise ValueError('Incomplete upload')
        png = None
        if len(task['paths']) == 1:
            try:
                with Image.open(task['paths'][0]) as image:
                    if image.width * image.height <= 24_000_000:
                        output = io.BytesIO()
                        image.convert('RGBA').save(output, format='PNG')
                        if output.tell() <= MAX_IMAGE:
                            png = output.getvalue()
            except (OSError, ValueError, Image.DecompressionBombError):
                pass
        batch = RECEIVED / str(uuid.uuid4())
        RECEIVED.mkdir(parents=True, exist_ok=True)
        self.upload = None
        try:
            # One rename publishes the complete batch on this Windows volume.
            staging = Path(tempfile.mkdtemp(prefix='.web-', dir=RECEIVED))
            try:
                targets = []
                for index, source in enumerate(task['paths']):
                    target = staging / str(index) / source.name
                    target.parent.mkdir()
                    shutil.copyfile(source, target)
                    targets.append(str(batch / str(index) / source.name))
                os.replace(staging, batch)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
            try:
                self.bridge.clipboard.write_paths(targets, png)
            except (OSError, ValueError, MemoryError):
                return {'ok': True, 'copied': False, 'image_copied': False,
                        'message': 'Saved in Received files. Clipboard is busy. Open Received files to copy them.'}
            self.bridge.status = 'Phone files saved and copied · ready for another transfer'
            return {'ok': True, 'copied': True, 'image_copied': bool(png)}
        except Exception:
            if batch.exists():
                shutil.rmtree(batch)
            raise

    def current(self, data):
        if self.download:
            raise ValueError('Finish this download before requesting another')
        clipboard = self.bridge.clipboard
        outbox = self.bridge.outbox if data.get('selection') else None
        paths = outbox['paths'] if outbox else clipboard.read_paths()
        if paths:
            files = file_manifest(paths)
            sources = []
            total = 0
            for index, (source, file) in enumerate(zip(paths, files)):
                target = self.folder / 'download' / str(index) / file['name']
                target.parent.mkdir(parents=True)
                with Path(source).open('rb') as incoming, target.open('wb') as output:
                    while raw := incoming.read(min(1024 * 1024, MAX_FILES - total + 1)):
                        total += len(raw)
                        if total > MAX_FILES:
                            raise ValueError('Files exceed 300 MB in total')
                        output.write(raw)
                file['size'] = target.stat().st_size
                sources.append(target)
        else:
            item = clipboard.read()
            if not item:
                return {'ok': True, 'item': None}
            if item['kind'] == 'text':
                if len(item['text'].encode('utf-8')) > 4096:
                    raise ValueError('The PC clipboard exceeds the 4 KB text limit')
                return {'ok': True, 'item': item}
            if item['kind'] != 'image':
                raise ValueError('Copy text, a photo, or files on Windows first')
            target = self.folder / 'clipboard.png'
            target.write_bytes(unb64(item['data']))
            sources = [target]
            files = file_manifest(sources)
        identity = str(uuid.uuid4())
        self.download = {'id': identity, 'paths': sources, 'outbox': outbox['id'] if outbox else None}
        return {'ok': True, 'item': {'kind': 'files', 'id': identity, 'files': files, 'chunk_size': WEB_CHUNK,
                                    'stream_version': 1, 'stream_block_size': STREAM_BLOCK}}

    def put_stream(self, data):
        task = self.upload
        if not task or data.get('id') != task['id']:
            raise ValueError('Unknown upload')
        index, offset, size = data.get('index'), data.get('offset'), data.get('size')
        if type(index) is not int or not 0 <= index < len(task['paths']):
            raise ValueError('Invalid file index')
        target = task['paths'][index]
        if type(offset) is not int or offset != target.stat().st_size:
            raise ValueError('Invalid file offset')
        raw = data.get('_binary')
        if (type(size) is not int or not 1 <= size <= STREAM_BLOCK or not isinstance(raw, bytes)
                or len(raw) != size or offset + size > task['sizes'][index]):
            raise ValueError('Invalid stream size')
        # The digest is inside the authenticated command. Verify before writing.
        if hashlib.sha256(raw).hexdigest() != data.get('sha256'):
            raise ValueError('File integrity check failed')
        with target.open('ab') as output:
            output.write(raw)
        return {'ok': True}

    def get_stream(self, data):
        task = self.download
        if not task or data.get('id') != task['id']:
            raise ValueError('Unknown download')
        index, offset, size = data.get('index'), data.get('offset'), data.get('size')
        if (type(index) is not int or not 0 <= index < len(task['paths'])
                or type(offset) is not int or offset < 0 or type(size) is not int
                or not 1 <= size <= STREAM_BLOCK):
            raise ValueError('Invalid file position')
        target = task['paths'][index]
        if offset + size > target.stat().st_size:
            raise ValueError('Invalid stream size')
        with target.open('rb') as source:
            source.seek(offset)
            raw = source.read(size)
        if len(raw) != size:
            raise ValueError('Incomplete file received')
        return {'ok': True, 'size': size, 'sha256': hashlib.sha256(raw).hexdigest(), '_binary': raw}

    def get(self, data):
        task = self.download
        if not task or data.get('id') != task['id']:
            raise ValueError('Unknown download')
        index, offset = data.get('index'), data.get('offset')
        if type(index) is not int or not 0 <= index < len(task['paths']) or type(offset) is not int or offset < 0:
            raise ValueError('Invalid file position')
        with task['paths'][index].open('rb') as source:
            source.seek(offset)
            return {'ok': True, 'data': b64(source.read(WEB_CHUNK))}
