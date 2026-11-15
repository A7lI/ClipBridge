import json
from pathlib import Path
import secrets
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'desktop'))
import app
from speech import LocalSpeech, validate_model


class ModelSelectionTests(unittest.TestCase):
    def test_selects_renamed_gguf_and_saves_without_starting_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            model = directory/'My Canary voice model.gguf'
            model.write_bytes(b'GGUF'+bytes(24))
            previous = Mock(model=model)
            ui = object.__new__(app.App)
            ui.speech = previous
            ui.state = SimpleNamespace(speech=previous)
            ui.settings = {'cipher_source': 'old/script.py'}
            ui.auto_sync = True
            ui.key = secrets.token_bytes(32)
            ui.voice_status = Mock()
            ui.model_path = Mock()
            with patch.object(app.filedialog, 'askopenfilename', return_value=str(model)) as picker, \
                 patch.object(app, 'APPDATA', directory), patch.object(app, 'CONFIG', directory/'settings.json'), \
                 patch('speech.subprocess.Popen') as process:
                ui.choose_model()
                self.assertEqual(picker.call_args.kwargs['filetypes'][0], ('GGUF voice models', '*.gguf'))
                process.assert_not_called()
            saved = json.loads((directory/'settings.json').read_text('utf-8'))
            self.assertEqual(saved['voice_model'], str(model.resolve()))
            self.assertNotIn('cipher_source', saved)
            self.assertEqual(ui.speech.model, model.resolve())
            self.assertIsNone(ui.speech.process)
            previous.close.assert_called_once()
            self.assertIs(ui.state.speech, ui.speech)

    def test_invalid_file_does_not_replace_existing_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary)/'not-a-model.gguf'
            model.write_text('This is not GGUF')
            ui = object.__new__(app.App)
            previous = Mock(model=model)
            ui.speech = previous
            with patch.object(app.filedialog, 'askopenfilename', return_value=str(model)), \
                 patch.object(app.messagebox, 'showerror') as error:
                ui.choose_model()
            self.assertIs(ui.speech, previous)
            previous.close.assert_not_called()
            error.assert_called_once()

    def test_cancel_keeps_existing_selection(self):
        ui = object.__new__(app.App)
        previous = Mock(model=Path('C:/missing/model.gguf'))
        ui.speech = previous
        with patch.object(app.filedialog, 'askopenfilename', return_value=''):
            ui.choose_model()
        self.assertIs(ui.speech, previous)
        previous.close.assert_not_called()

    def test_python_source_is_not_an_accepted_model(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)/'local_stt.py'
            source.write_bytes(b'GGUF')
            with self.assertRaises(ValueError):
                validate_model(source)


if __name__ == '__main__':
    unittest.main(verbosity=2)
