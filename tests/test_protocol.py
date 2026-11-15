import base64
import io
import json
from pathlib import Path
import secrets
import sys
import threading
import time
import unittest
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'desktop'))
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from PIL import Image
from protocol import Protocol, b64, unb64, validate_clip
from server import Server, State
from app import protect


class FakeSpeech:
    def available(self):return True
    def transcribe(self,audio):return 'Local dictation'


class Tests(unittest.TestCase):
    def setUp(self):self.key=secrets.token_bytes(32)
    def envelope(self,path,payload=None,nonce=None):
        nonce=nonce or secrets.token_bytes(12)
        value=dict(payload or {},time=time.time(),device='test-android')
        raw=AESGCM(self.key).encrypt(nonce,json.dumps(value).encode(),('CB1 '+path).encode())
        return json.dumps({'nonce':b64(nonce),'data':b64(raw)}).encode()
    def test_authentication_replay_and_path_binding(self):
        p=Protocol(self.key);body=self.envelope('/v1/poll')
        value,nonce=p.open('/v1/poll',body)
        self.assertEqual(value['device'],'test-android')
        with self.assertRaises(Exception):p.open('/v1/poll',body)
        with self.assertRaises(Exception):Protocol(self.key).open('/v1/clipboard',body)
        with self.assertRaises(Exception):Protocol(secrets.token_bytes(32)).open('/v1/poll',body)
        response=json.loads(p.seal('/v1/poll',nonce,{'ok':True}))
        decoded=AESGCM(self.key).decrypt(unb64(response['nonce']),unb64(response['data']),('CB1 reply /v1/poll '+nonce).encode())
        self.assertTrue(json.loads(decoded)['ok'])
        with self.assertRaises(Exception):AESGCM(self.key).decrypt(unb64(response['nonce']),unb64(response['data']),b'wrong request')
    def test_clipboard_validation(self):
        self.assertEqual(validate_clip({'kind':'text','text':'English العربية 🔑'})['text'],'English العربية 🔑')
        for invalid in [{'kind':'text','text':'bad\x00text'},{'kind':'html'},{'kind':'image','data':b64(b'not an image')},{'kind':'text','text':3}]:
            with self.assertRaises(Exception):validate_clip(invalid)
        raw=io.BytesIO();Image.new('RGB',(32,24),'#8ee3c3').save(raw,'JPEG')
        out=validate_clip({'kind':'image','data':b64(raw.getvalue())})
        image=Image.open(io.BytesIO(unb64(out['data'])))
        self.assertEqual(image.format,'PNG');self.assertEqual(image.size,(32,24))
    def test_pause_and_bidirectional_routing(self):
        received=[];state=State(self.key,received.append,FakeSpeech());clip={'kind':'text','text':'from Android'}
        result=state.dispatch('/v1/clipboard',{'device':'phone','item':clip})
        self.assertFalse(result['ok']);self.assertEqual(received,[])
        state.pause(False)
        result=state.dispatch('/v1/clipboard',{'device':'phone','item':clip});self.assertTrue(result['ok']);self.assertEqual(received,[clip])
        poll=state.dispatch('/v1/poll',{'device':'phone','after':-1});self.assertIsNone(poll['item'])
        state.publish({'kind':'text','text':'from PC'},'pc')
        poll=state.dispatch('/v1/poll',{'device':'phone','after':-1});self.assertEqual(poll['item']['text'],'from PC')
        state.pause(True);self.assertIsNone(state.item)
    def test_http_encrypted_roundtrip(self):
        state=State(self.key,lambda item:None,FakeSpeech());server=Server(('127.0.0.1',0),state)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            path='/v1/poll';body=self.envelope(path,{'after':-1});req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=body,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=3) as result:reply=json.load(result)
            nonce=json.loads(body)['nonce'];raw=AESGCM(self.key).decrypt(unb64(reply['nonce']),unb64(reply['data']),('CB1 reply '+path+' '+nonce).encode())
            self.assertTrue(json.loads(raw)['paused'])
            with self.assertRaises(urllib.error.HTTPError) as rejected:urllib.request.urlopen(req,timeout=3)
            self.assertEqual(rejected.exception.code,401)
            req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=self.envelope(path,{'after':-1}),headers={'Origin':'http://untrusted.test'})
            with self.assertRaises(urllib.error.HTTPError) as rejected:urllib.request.urlopen(req,timeout=3)
            self.assertEqual(rejected.exception.code,403)
        finally:server.shutdown();server.server_close()
    def test_windows_protected_pairing_key(self):
        encrypted=protect(self.key);self.assertNotEqual(encrypted,self.key);self.assertEqual(protect(encrypted,decrypt=True),self.key)

    def test_ios_pairs_and_reads_live_windows_text_without_polling(self):
        clipboard_text = 'Copied before the phone opened\nالعربية 😀'

        def read_text():
            return clipboard_text

        def write(item):
            nonlocal clipboard_text
            clipboard_text = item['text']

        state = State(self.key, write, FakeSpeech(), read_text=read_text)
        state.pause(False)
        server = Server(('127.0.0.1', 0), state)
        threading.Thread(target=server.serve_forever, daemon=True).start()

        def post(path, payload=None):
            body = self.envelope(path, payload)
            nonce = json.loads(body)['nonce']
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{path}', data=body)
            with urllib.request.urlopen(request, timeout=3) as response:
                reply = json.load(response)
            aad = f'CB1 reply {path} {nonce}'.encode()
            return json.loads(AESGCM(self.key).decrypt(unb64(reply['nonce']), unb64(reply['data']), aad))

        try:
            current = '/v1/clipboard/current'
            request = urllib.request.Request(f'http://127.0.0.1:{server.server_port}{current}', data=b'{}')
            with self.assertRaises(urllib.error.HTTPError) as rejected:
                urllib.request.urlopen(request, timeout=3)
            self.assertEqual(rejected.exception.code, 401)
            rejected.exception.close()
            self.assertEqual(post('/v1/pair'), {'ok': True, 'paused': False})
            self.assertEqual(state.last_seen, 0)
            self.assertEqual(post(current)['item'], {'kind': 'text', 'text': clipboard_text})
            self.assertIsNone(state.item)
            revision = state.revision
            clipboard_text = 'A newer Windows copy'
            self.assertEqual(post(current)['item']['text'], clipboard_text)
            self.assertEqual(state.revision, revision)
            clipboard_text = None
            self.assertIsNone(post(current)['item'])
            text = 'Sent from the iPhone\nمرحبا 🌉'
            self.assertTrue(post('/v1/clipboard', {'item': {'kind': 'text', 'text': text}})['ok'])
            self.assertEqual(clipboard_text, text)
            state.pause(True)
            self.assertEqual(post('/v1/pair'), {'ok': True, 'paused': True})
            self.assertFalse(post(current)['ok'])
        finally:
            server.shutdown()
            server.server_close()

    def test_large_photo_survives_double_base64_envelope(self):
        received=[];state=State(self.key,received.append,FakeSpeech());state.pause(False)
        raw=io.BytesIO();Image.frombytes('RGBA',(2000,1500),secrets.token_bytes(12_000_000)).save(raw,'PNG')
        item={'kind':'image','data':b64(raw.getvalue())}
        path='/v1/clipboard';body=self.envelope(path,{'item':item})
        self.assertGreater(len(body),19*1024*1024)
        server=Server(('127.0.0.1',0),state);threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            req=urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=body,headers={'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=15) as result:reply=json.load(result)
            value=AESGCM(self.key).decrypt(unb64(reply['nonce']),unb64(reply['data']),('CB1 reply '+path+' '+json.loads(body)['nonce']).encode())
            self.assertTrue(json.loads(value)['ok']);self.assertEqual(len(received),1)
            self.assertEqual(Image.open(io.BytesIO(unb64(received[0]['data']))).size,(2000,1500))
        finally:server.shutdown();server.server_close()


if __name__=='__main__':unittest.main(verbosity=2)
