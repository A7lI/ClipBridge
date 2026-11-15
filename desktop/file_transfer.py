"""Bounded file clipboard payloads; received files are saved, never executed."""
import os
from pathlib import Path
import uuid

from protocol import MAX_FILES, MAX_FILE_COUNT, b64, unb64, safe_filename, validate_clip

RECEIVED = Path(os.environ.get('LOCALAPPDATA', '.')) / 'ClipBridge' / 'Received'


def pack_files(paths):
    if not 1 <= len(paths) <= MAX_FILE_COUNT:
        raise ValueError('Copy between 1 and 20 files; folders are not supported')
    files, total = [], 0
    for path in paths:
        path = Path(path)
        if not path.is_file():
            raise ValueError('Folders cannot be shared; zip the folder first')
        name = safe_filename(path.name)
        with path.open('rb') as source:
            data = source.read(MAX_FILES - total + 1)
        total += len(data)
        if total > MAX_FILES:
            raise ValueError('Files exceed 300 MB in total')
        files.append({'name': name, 'data': b64(data)})
    return {'kind': 'files', 'files': files}


def save_files(item, destination=None):
    item = validate_clip(item)
    if item['kind'] != 'files':
        raise ValueError('Expected files')
    folder = Path(destination if destination is not None else RECEIVED) / str(uuid.uuid4())
    folder.mkdir(parents=True)
    paths = []
    for index, file in enumerate(item['files']):
        # Per-file folders retain duplicate names without overwriting anything.
        target = folder / str(index) / file['name']
        target.parent.mkdir()
        target.write_bytes(unb64(file['data']))
        paths.append(str(target.resolve()))
    return paths
