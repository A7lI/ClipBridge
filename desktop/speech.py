"""Use a selected GGUF model as data, with ClipBridge's own speech worker."""
import base64
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

from voice_model import DEFAULT_MODEL

DEFAULT_RUNTIME = (Path(sys._MEIPASS)/'engines/ClipBridge-Voice.exe'
                   if getattr(sys, 'frozen', False) else Path(sys.executable))


def validate_model(path):
    """Check the selected data file without executing code or loading inference."""
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() != '.gguf':
        raise ValueError('Choose your Canary voice model (.gguf).')
    with path.open('rb') as model:
        if model.read(4) != b'GGUF':
            raise ValueError('This file is not a GGUF voice model.')
    return path


class LocalSpeech:
    def __init__(self, model=DEFAULT_MODEL, runtime=DEFAULT_RUNTIME):
        self.model = Path(model)
        self.runtime = Path(runtime)
        self.process = None
        self.responses = queue.Queue()
        self.lock = threading.Lock()
        self.process_lock = threading.Lock()
        self.serial = 0
        self.closed = False

    def problem(self):
        try:
            validate_model(self.model)
        except (OSError, ValueError):
            return 'Download Canary to enable voice typing.'
        if not self.runtime.is_file():
            return 'The local voice engine is missing from this PC.'
        return None

    def available(self):
        return self.problem() is None

    def _start(self):
        with self.process_lock:
            if self.closed:
                raise RuntimeError('The voice model selection changed. Try dictation again.')
            if self.process is not None and self.process.poll() is None:
                return
            problem = self.problem()
            if problem:
                raise RuntimeError(problem)
            # Keep the external interpreter's script directory separate from
            # the executable's bundled Python DLLs and extension modules.
            worker = (Path(sys._MEIPASS)/'workers/voice_worker.py' if getattr(sys, 'frozen', False)
                      else Path(__file__).resolve().parent/'voice_worker.py')
            env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
                       HF_HUB_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', OMP_NUM_THREADS='6',
                       PYINSTALLER_RESET_ENVIRONMENT='1')
            # The packaged speech engine includes its own Python and libraries.
            # Source runs use the developer's interpreter, never a Cipher path.
            command = ([str(self.runtime), '--model', str(self.model.resolve())]
                       if getattr(sys, 'frozen', False) else
                       [str(self.runtime), str(worker), '--model', str(self.model.resolve())])
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding='utf-8', bufsize=1, env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            responses = queue.Queue()
            self.process, self.responses = process, responses

            def receive():
                try:
                    for line in process.stdout:
                        try:
                            result = json.loads(line)
                            if isinstance(result, dict):
                                responses.put(result)
                        except ValueError:
                            pass
                except (OSError, ValueError):
                    pass
                finally:
                    responses.put({'ended': True})
            threading.Thread(target=receive, daemon=True, name='ClipBridgeVoiceResponses').start()

    def transcribe(self, audio):
        if not isinstance(audio, bytes) or not audio or len(audio) % 2 or len(audio) > 16000*2*60:
            raise ValueError('Voice recordings must be mono PCM16, up to 60 seconds.')
        with self.lock:
            self._start()
            self.serial += 1
            request_id = self.serial
            process, responses = self.process, self.responses
            try:
                process.stdin.write(json.dumps({'id': request_id, 'audio': base64.b64encode(audio).decode('ascii')})+'\n')
                process.stdin.flush()
            except (OSError, ValueError) as exc:
                raise RuntimeError('The local voice engine disconnected.') from exc
            deadline = time.monotonic()+120
            while time.monotonic() < deadline:
                try:
                    result = responses.get(timeout=.25)
                except queue.Empty:
                    continue
                if result.get('ended'):
                    raise RuntimeError('The local voice engine stopped. Try voice typing again.')
                if result.get('id') != request_id:
                    continue
                if not result.get('ok'):
                    raise RuntimeError(result.get('error', 'Voice recognition failed.'))
                return result.get('text', '')
            self._stop()
            raise RuntimeError('Voice recognition took too long. Try a shorter recording.')

    def _stop(self):
        with self.process_lock:
            process, self.process = self.process, None
        if process is None:
            return
        if process.poll() is None:
            if os.name == 'nt':
                try:
                    subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW, timeout=5)
                except (OSError, subprocess.SubprocessError):
                    pass
            try:
                process.kill()
                process.wait(timeout=3)
            except (OSError, subprocess.SubprocessError):
                pass
        for stream in (process.stdin, process.stdout):
            try:
                stream.close()
            except (OSError, ValueError):
                pass

    def close(self):
        with self.process_lock:
            self.closed = True
        self._stop()
