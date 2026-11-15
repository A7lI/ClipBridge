import base64
import json
from pathlib import Path
import secrets
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'desktop'))
import app
from discovery import discovery_reply, mac


class StartupTests(unittest.TestCase):
    def test_restart_restores_model_pairing_and_starts_sync(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary)
            model=folder/'My saved Canary.gguf';model.write_bytes(b'GGUF'+bytes(24))
            with patch.object(app,'APPDATA',folder), patch.object(app,'CONFIG',folder/'settings.json'), \
                 patch.object(app,'DEFAULT_MODEL',model), patch.object(app,'WindowsClipboard') as clipboard, \
                 patch.object(app,'Server') as server, patch.object(app,'Discovery'), patch.object(app,'LocalSender'), \
                 patch.object(app.threading,'Thread'), patch.object(app.App,'render'), patch.object(app.App,'tick'):
                clipboard.return_value.sequence.return_value=123
                server.return_value.server_port=48721
                first=app.App(Mock())
                key=first.key
                self.assertFalse(first.state.paused)
                self.assertTrue(first.auto_sync)
                second=app.App(Mock())
                self.assertEqual(second.key,key)
                self.assertEqual(second.speech.model,model)
                self.assertFalse(second.state.paused)
                saved=json.loads((folder/'settings.json').read_text('utf-8'))
                self.assertTrue(saved['auto_sync'])
                self.assertEqual(saved['voice_model'],str(model))

    def test_auto_start_can_be_disabled_without_losing_pairing(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder=Path(temporary);key=secrets.token_bytes(32)
            saved={'key':base64.b64encode(app.protect(key)).decode(), 'voice_model':'C:/saved/model.gguf','auto_sync':False}
            (folder/'settings.json').write_text(json.dumps(saved),'utf-8')
            with patch.object(app,'APPDATA',folder), patch.object(app,'CONFIG',folder/'settings.json'), \
                 patch.object(app,'WindowsClipboard'),patch.object(app,'Server') as server,patch.object(app,'Discovery'),patch.object(app,'LocalSender'), \
                 patch.object(app.threading,'Thread'),patch.object(app.App,'render'),patch.object(app.App,'tick'):
                server.return_value.server_port=48721
                restored=app.App(Mock())
                self.assertTrue(restored.state.paused)
                self.assertEqual(restored.key,key)
                self.assertEqual(str(restored.speech.model),str(Path('C:/saved/model.gguf')))

    def test_discovery_requires_existing_pairing_and_binds_reply_to_nonce(self):
        key=secrets.token_bytes(32);nonce=base64.b64encode(secrets.token_bytes(16)).decode()
        self.assertIsNone(discovery_reply(key,json.dumps({'nonce':nonce,'auth':'wrong'}),48721))
        request=json.dumps({'nonce':nonce,'auth':mac(key,'CB1 discover '+nonce)})
        reply=json.loads(discovery_reply(key,request,48721))
        self.assertEqual(reply['nonce'],nonce)
        self.assertEqual(reply['auth'],mac(key,'CB1 here '+nonce+' 48721'))
        self.assertNotEqual(reply['auth'],mac(secrets.token_bytes(32),'CB1 here '+nonce+' 48721'))


if __name__=='__main__':unittest.main(verbosity=2)
