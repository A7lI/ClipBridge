import ctypes
import io
import json
from pathlib import Path
import secrets
import struct
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from contextlib import nullcontext
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from protocol import MAX_FILES, MAX_BODY, b64, unb64, safe_filename, validate_clip
from file_transfer import pack_files, save_files
from server import State, Server
import windows_clipboard as wc


class Speech:
    def available(self): return False


class FileTransferTests(unittest.TestCase):
    def test_unsafe_names_rejected_before_writing(self):
        for name in ['../secret', '..', 'C:\\secret', 'photo:stream', 'a\x00b', 'CON.txt', 'lpt1', 'trailing.', '/abs', '', 'x'*241]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                validate_clip({'kind': 'files', 'files': [{'name': name, 'data': b64(b'data')}]})
        self.assertEqual(safe_filename('تقرير 2026.pdf'), 'تقرير 2026.pdf')

    def test_roundtrip_binary_empty_and_duplicate_names(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a = root/'a'; a.mkdir(); b = root/'b'; b.mkdir()
            (a/'same.bin').write_bytes(bytes(range(256)))
            (b/'same.bin').write_bytes(b'other file')
            (a/'فارغ.txt').touch()
            paths = [a/'same.bin', b/'same.bin', a/'فارغ.txt']
            item = validate_clip(pack_files(paths))
            saved = [Path(p) for p in save_files(item, root/'received')]
            self.assertEqual([p.read_bytes() for p in saved], [p.read_bytes() for p in paths])
            self.assertEqual([p.name for p in saved], [p.name for p in paths])
            self.assertEqual(len(set(saved)), 3)
            self.assertEqual(wc.signature(item), wc.signature(pack_files(saved)))

    def test_limits_and_directories(self):
        with tempfile.TemporaryDirectory() as temp, patch('file_transfer.MAX_FILES',32), patch('protocol.MAX_FILES',32):
            root = Path(temp)
            with self.assertRaises(ValueError): pack_files([root])
            path = root/'large.bin'; path.write_bytes(bytes(33))
            with self.assertRaises(ValueError): pack_files([path])
            for entries in [[], [{'name': 'x', 'data': ''}]*21, [{'name':'x','data':b64(bytes(32))},{'name':'y','data':b64(b'x')}]]:
                with self.assertRaises(ValueError): validate_clip({'kind':'files','files':entries})

    def test_dropfiles_payload_and_reader_without_touching_clipboard(self):
        with tempfile.TemporaryDirectory() as temp:
            file=Path(temp)/'تقرير.txt';file.write_bytes(b'hello')
            item=pack_files([file]);writes=[]
            with patch.object(wc, 'opened', return_value=nullcontext()), patch.object(wc.user, 'EmptyClipboard', return_value=True), \
                 patch.object(wc, 'save_files', return_value=[str(file)]), patch.object(wc, 'put', side_effect=lambda fmt,data:writes.append((fmt,data))):
                wc.WindowsClipboard().write(item)
            fmt,raw=writes[0];self.assertEqual(fmt,15)
            self.assertEqual(struct.unpack('<IiiII',raw[:20]),(20,0,0,0,1))
            self.assertEqual(raw[20:].decode('utf-16-le'),str(file)+'\0\0')
            def query(handle,index,buffer,length):
                if index==0xffffffff:return 1
                if buffer is None:return len(str(file))
                buffer.value=str(file);return len(str(file))
            with patch.object(wc, 'opened', return_value=nullcontext()), patch.object(wc.user,'IsClipboardFormatAvailable',side_effect=lambda fmt:fmt==15), \
                 patch.object(wc.user,'GetClipboardData',return_value=1),patch.object(wc.shell,'DragQueryFileW',side_effect=query):
                self.assertEqual(wc.WindowsClipboard().read(),item)

    def test_maximum_file_encrypted_http_upload_and_phone_download(self):
        key=secrets.token_bytes(32)
        with tempfile.TemporaryDirectory() as temp:
            item={'kind':'files','files':[{'name':'payload.bin','data':b64(bytes(range(256))*((12*1024*1024)//256))}]}
            saved=[];state=State(key,lambda clip:saved.extend(save_files(clip,temp)),Speech());state.pause(False)
            server=Server(('127.0.0.1',0),state);threading.Thread(target=server.serve_forever,daemon=True).start()
            def request(path,value,device='android'):
                nonce=secrets.token_bytes(12);value=dict(value,time=time.time(),device=device)
                data=AESGCM(key).encrypt(nonce,json.dumps(value).encode(),('CB1 '+path).encode())
                body=json.dumps({'nonce':b64(nonce),'data':b64(data)}).encode();self.assertLessEqual(len(body),MAX_BODY)
                with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=body),timeout=20) as reply:envelope=json.load(reply)
                raw=AESGCM(key).decrypt(unb64(envelope['nonce']),unb64(envelope['data']),('CB1 reply '+path+' '+b64(nonce)).encode())
                return json.loads(raw)
            try:
                self.assertTrue(request('/v1/clipboard',{'item':item})['ok'])
                self.assertEqual(Path(saved[0]).read_bytes(),unb64(item['files'][0]['data']))
                self.assertIsNone(request('/v1/poll',{'after':-1})['item'])
                state.publish(item,'pc')
                self.assertEqual(request('/v1/poll',{'after':-1})['item']['files'],item['files'])
                state.pause(True);self.assertFalse(request('/v1/clipboard',{'item':item})['ok']);self.assertEqual(len(saved),1)
            finally:server.shutdown();server.server_close()


if __name__=='__main__':unittest.main()
