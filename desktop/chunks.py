"""Small encrypted messages for large files; never enlarge the HTTP body limit."""
import tempfile
import time
import uuid
from pathlib import Path

from protocol import MAX_FILES, MAX_FILE_COUNT, safe_filename, b64, unb64
from file_transfer import pack_files

CHUNK = 192 * 1024  # Divisible by three: base64 slices remain independently decodable.
TRANSFER_SECONDS = 900


class Chunks:
    def __init__(self):
        self.uploads = {}

    def clear(self):
        for task in self.uploads.values():
            task['temp'].cleanup()
        self.uploads.clear()

    def dispatch(self, path, data, source):
        now = time.monotonic()
        for identity, task in list(self.uploads.items()):
            if now > task['deadline']:
                task['temp'].cleanup()
                del self.uploads[identity]
        if path == '/v1/files/begin':
            files = data['files']
            if not isinstance(files, list) or not 1 <= len(files) <= MAX_FILE_COUNT:
                raise ValueError('Select 1–20 files')
            names = [safe_filename(f['name']) for f in files]
            if len(self.uploads) >= 2:
                raise ValueError('Wait for the current uploads to finish')
            identity = str(uuid.uuid4())
            temp = tempfile.TemporaryDirectory(prefix='ClipBridge-upload-')
            paths = []
            for i, name in enumerate(names):
                folder = Path(temp.name)/str(i)
                folder.mkdir()
                file = folder/name
                file.touch()
                paths.append(file)
            self.uploads[identity] = dict(temp=temp, paths=paths, source=source,
                                          total=0, deadline=now+TRANSFER_SECONDS)
            return {'ok': True, 'id': identity, 'chunk_size': CHUNK}
        task = self.uploads.get(data.get('id'))
        if not task or task['source'] != source:
            raise ValueError('Unknown file upload')
        if path == '/v1/files/cancel':
            task['temp'].cleanup()
            del self.uploads[data['id']]
            return {'ok': True}
        if path == '/v1/files/put':
            index, offset = data['index'], data['offset']
            if type(index) is not int or not 0 <= index < len(task['paths']):
                raise ValueError('Invalid file index')
            target = task['paths'][index]
            if type(offset) is not int or offset != target.stat().st_size:
                raise ValueError('Invalid file offset')
            if len(data['data']) > CHUNK//3*4:
                raise ValueError('Chunk too large')
            raw = unb64(data['data'])
            if not raw or len(raw) > CHUNK or task['total']+len(raw) > MAX_FILES:
                raise ValueError('Files exceed 300 MB in total or invalid chunk')
            with target.open('ab') as out:
                out.write(raw)
            task['total'] += len(raw)
            return {'ok': True}
        if path == '/v1/files/commit':
            sizes = data.get('sizes')
            if sizes != [p.stat().st_size for p in task['paths']]:
                raise ValueError('Incomplete upload')
            try:
                return pack_files(task['paths'])
            finally:
                task['temp'].cleanup()
                del self.uploads[data['id']]
        raise ValueError('Unknown file endpoint')


def manifest(item, identity):
    return dict(kind='files', chunk_id=identity, files=[
        dict(name=f['name'], size=len(f['data'])//4*3-(2 if f['data'].endswith('==') else 1 if f['data'].endswith('=') else 0))
        for f in item['files']])


def get_chunk(item, data):
    index, offset = data['index'], data['offset']
    if type(index) is not int or not 0 <= index < len(item['files']) or type(offset) is not int or offset < 0 or offset % CHUNK:
        raise ValueError('Invalid chunk position')
    encoded = item['files'][index]['data']
    start = offset//3*4
    return {'ok': True, 'data': encoded[start:start+CHUNK//3*4]}
