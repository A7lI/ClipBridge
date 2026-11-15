"""Download ClipBridge's pinned Canary model into app-managed storage."""
import hashlib
import os
from pathlib import Path
import threading
from urllib.request import Request, urlopen

MODEL_REVISION = '8b01fc77ac169a0a05c5c0332bbfe54acf65c26f'
MODEL_NAME = 'canary-180m-flash-Q8_0.gguf'
MODEL_URL = f'https://huggingface.co/handy-computer/canary-180m-flash-gguf/resolve/{MODEL_REVISION}/{MODEL_NAME}'
MODEL_SIZE = 218447648
MODEL_SHA256 = 'f942ab746040b531a29ab78ca3afc8dc9564efd8e4c942b5541e53644be9c408'
MODEL_DIRECTORY = Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))/'ClipBridge'/'Models'
DEFAULT_MODEL = MODEL_DIRECTORY/MODEL_NAME
_download_lock = threading.Lock()


class DownloadCancelled(Exception):
    pass


def verified(path):
    path = Path(path)
    if not path.is_file() or path.stat().st_size != MODEL_SIZE:
        return False
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest() == MODEL_SHA256


def download_model(destination=DEFAULT_MODEL, progress=lambda received, total: None,
                   cancel=None):
    """Only promote a complete, hash-verified download; preserve any old model."""
    destination = Path(destination)
    cancel = cancel or threading.Event()
    if not _download_lock.acquire(blocking=False):
        raise RuntimeError('A voice-model download is already running.')
    lock = None
    partial = destination.with_suffix('.gguf.download')
    owns_lock = False
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # A Windows byte-range lock also protects against another app instance.
        # Closing the handle releases it even after a crash; no stale lock state.
        lock = destination.with_suffix('.gguf.lock').open('a+b')
        if os.name == 'nt':
            import msvcrt
            if lock.tell() == 0:
                lock.write(b'0'); lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise RuntimeError('Another ClipBridge window is downloading the model.') from exc
        owns_lock = True
        if cancel.is_set():
            raise DownloadCancelled()
        if verified(destination):
            progress(MODEL_SIZE, MODEL_SIZE)
            return destination
        request = Request(MODEL_URL, headers={'User-Agent': 'ClipBridge/0.5.0', 'Accept-Encoding': 'identity'})
        digest, received = hashlib.sha256(), 0
        progress(0, MODEL_SIZE)
        with urlopen(request, timeout=15) as response, partial.open('wb') as target:
            if not response.geturl().startswith('https://'):
                raise ValueError('The model download must use HTTPS.')
            if response.status != 200:
                raise ValueError('The model server did not return a complete file.')
            length = response.headers.get('Content-Length')
            if length is not None and int(length) != MODEL_SIZE:
                raise ValueError('The model server returned an unexpected file size.')
            while True:
                if cancel.is_set():
                    raise DownloadCancelled()
                block = response.read(1024*1024)
                if not block:
                    break
                received += len(block)
                if received > MODEL_SIZE:
                    raise ValueError('The downloaded model is larger than expected.')
                target.write(block)
                digest.update(block)
                progress(received, MODEL_SIZE)
            target.flush()
            os.fsync(target.fileno())
        if cancel.is_set():
            raise DownloadCancelled()
        if received != MODEL_SIZE or digest.hexdigest() != MODEL_SHA256:
            raise ValueError('The model download was incomplete or failed its integrity check. Please retry.')
        partial.replace(destination)
        return destination
    finally:
        if owns_lock:
            partial.unlink(missing_ok=True)
        if lock is not None:
            lock.close()
        _download_lock.release()
