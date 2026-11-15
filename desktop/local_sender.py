"""Same-user authenticated named pipe: Explorer launches a helper, never another LAN server."""
import hashlib
import hmac
import json
from multiprocessing.connection import Client, Listener
from multiprocessing import AuthenticationError
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from file_transfer import pack_files


def pipe_name(folder):
    identity = hashlib.sha256(str(Path(folder).resolve()).casefold().encode()).hexdigest()[:24]
    return r'\\.\pipe\ClipBridge-send-' + identity


def pipe_key(key):
    return hmac.digest(key, b'ClipBridge local file sender v1', 'sha256')


class LocalSender:
    def __init__(self, folder, key, send):
        self.alive = True
        self.send = send
        self.capacity = threading.BoundedSemaphore(4)
        self.listener = Listener(pipe_name(folder), family='AF_PIPE', authkey=pipe_key(key))
        threading.Thread(target=self.serve, daemon=True, name='ClipBridgeExplorer').start()

    def serve(self):
        while self.alive:
            try:
                connection = self.listener.accept()
            except EOFError:
                continue
            except OSError:
                if not self.alive:
                    break
                continue
            except Exception:
                continue
            if not self.capacity.acquire(blocking=False):
                connection.send_bytes(b'{"ok":false,"error":"Four transfers are already running."}')
                connection.close()
                continue
            threading.Thread(target=self.handle, args=(connection,), daemon=True).start()

    def handle(self, connection):
        try:
            if not connection.poll(5):
                return
            paths = json.loads(connection.recv_bytes(64*1024))
            if not isinstance(paths, list) or not 1 <= len(paths) <= 20 or not all(isinstance(path, str) and os.path.isabs(path) for path in paths):
                raise ValueError('Select 1–20 local files to send')
            result = self.send(pack_files(paths))
            connection.send_bytes(json.dumps(result).encode())
        except Exception as exc:
            try:
                connection.send_bytes(json.dumps({'ok': False, 'error': str(exc)[:240]}).encode())
            except (OSError, EOFError):
                pass
        finally:
            connection.close()
            self.capacity.release()

    def close(self):
        self.alive = False
        self.listener.close()


def send_selection(folder, key, paths, start_app=None):
    if not 1 <= len(paths) <= 20:
        raise ValueError('Select 1–20 files; folders are not supported')
    paths = [str(Path(path).resolve()) for path in paths]
    encoded = json.dumps(paths, ensure_ascii=False).encode('utf-8')
    if len(encoded) > 64*1024:
        raise ValueError('Selected file paths are too long')
    deadline, launched = time.monotonic()+10, False
    while True:
        try:
            connection = Client(pipe_name(folder), family='AF_PIPE', authkey=pipe_key(key))
            break
        except AuthenticationError as exc:
            raise ValueError('Close ClipBridge and reopen ClipBridge-PC.exe from File Explorer, then try again.') from exc
        except (FileNotFoundError, ConnectionRefusedError):
            if not launched and start_app is not None:
                start_app()
                launched = True
            if time.monotonic() >= deadline:
                raise ValueError('Open the updated ClipBridge PC app and try again.')
            time.sleep(.25)
    with connection:
        connection.send_bytes(encoded)
        if not connection.poll(920):
            raise ValueError('Delivery was not confirmed. Check Downloads/ClipBridge on your phone before retrying.')
        result = json.loads(connection.recv_bytes(4096))
    if not result.get('ok'):
        raise ValueError(result.get('error', 'Could not send selected files'))
    return result


def launch_companion():
    command = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).with_name('app.py'))]
    subprocess.Popen(command, env={**os.environ, 'PYINSTALLER_RESET_ENVIRONMENT': '1'}, creationflags=subprocess.CREATE_NO_WINDOW)
