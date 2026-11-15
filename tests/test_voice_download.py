import hashlib
import io
import queue
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'desktop'))
import voice_model as vm
import app


class Response(io.BytesIO):
    status = 200
    headers = {}
    def geturl(self):
        return 'https://model-cdn.example/model'


class VoiceDownloadTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name)/'Models/model.gguf'
        self.data = b'GGUF'+b'canary test weights'*100
        self.size = patch.object(vm, 'MODEL_SIZE', len(self.data)); self.size.start()
        self.sha = patch.object(vm, 'MODEL_SHA256', hashlib.sha256(self.data).hexdigest()); self.sha.start()
        self.addCleanup(self.size.stop); self.addCleanup(self.sha.stop)

    def test_download_installs_verified_model_automatically(self):
        changes=[]
        with patch.object(vm, 'urlopen', return_value=Response(self.data)) as network:
            result = vm.download_model(self.path, lambda done,total: changes.append((done,total)))
        self.assertEqual(result, self.path)
        self.assertEqual(result.read_bytes(), self.data)
        self.assertEqual(changes[-1], (len(self.data), len(self.data)))
        self.assertIn(vm.MODEL_REVISION, network.call_args.args[0].full_url)
        self.assertFalse(self.path.with_suffix('.gguf.download').exists())

    def test_existing_verified_download_does_not_use_network(self):
        self.path.parent.mkdir(); self.path.write_bytes(self.data)
        with patch.object(vm, 'urlopen') as network:
            self.assertEqual(vm.download_model(self.path), self.path)
            network.assert_not_called()

    def test_corruption_and_truncation_preserve_old_file(self):
        self.path.parent.mkdir(); self.path.write_bytes(b'previous model')
        for data in [self.data[:-1], b'X'+self.data[1:], self.data+b'X']:
            with self.subTest(size=len(data)), patch.object(vm,'urlopen',return_value=Response(data)):
                with self.assertRaises(ValueError):
                    vm.download_model(self.path)
            self.assertEqual(self.path.read_bytes(), b'previous model')
            self.assertFalse(self.path.with_suffix('.gguf.download').exists())

    def test_cancel_during_transfer_never_installs_partial_file(self):
        cancel=threading.Event()
        def progress(done,total):
            if done: cancel.set()
        with patch.object(vm,'urlopen',return_value=Response(self.data)):
            with self.assertRaises(vm.DownloadCancelled):
                vm.download_model(self.path, progress, cancel)
        self.assertFalse(self.path.exists())
        self.assertFalse(self.path.with_suffix('.gguf.download').exists())

    def test_failed_connection_can_be_retried(self):
        with patch.object(vm,'urlopen',side_effect=OSError('connection lost')):
            with self.assertRaises(OSError): vm.download_model(self.path)
        with patch.object(vm,'urlopen',return_value=Response(self.data)):
            self.assertEqual(vm.download_model(self.path), self.path)

    def test_rejects_http_redirect_and_unexpected_length(self):
        for response in [Response(self.data), Response(self.data)]:
            if not hasattr(self,'tested_http'):
                response.geturl=lambda:'http://insecure.example/model'; self.tested_http=True
            else:
                response.headers={'Content-Length':'1'}
            with patch.object(vm,'urlopen',return_value=response):
                with self.assertRaises(ValueError): vm.download_model(self.path)
        self.assertFalse(self.path.exists())

    def test_ui_activates_and_saves_download_without_picker(self):
        ui=object.__new__(app.App)
        ui.voice_events=queue.Queue(); ui.voice_events.put(('complete',self.path))
        previous=ui.speech=Mock()
        ui.state=SimpleNamespace(speech=previous)
        ui.download_button=Mock(); ui.choose_model_button=Mock(); ui.voice_progress=Mock(); ui.save=Mock()
        with patch.object(app.filedialog,'askopenfilename') as picker:
            ui.check_voice_download()
            picker.assert_not_called()
        self.assertEqual(ui.speech.model,self.path)
        self.assertIs(ui.state.speech,ui.speech)
        ui.save.assert_called_once(); previous.close.assert_called_once()


if __name__ == '__main__':
    unittest.main(verbosity=2)
