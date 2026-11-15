import hashlib
import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
import unittest
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'desktop'))
from protocol import Protocol, MAX_FILES, MAX_BODY, b64, unb64
from chunks import CHUNK, Chunks
from server import State, Server
from file_transfer import save_files


class Speech:
    def available(self): return False


class LargeTransferTests(unittest.TestCase):
    def test_upload_ownership_offsets_size_and_cleanup(self):
        chunks = Chunks()
        try:
            identity = chunks.dispatch('/v1/files/begin', {'files':[{'name':'x'}]}, 'phone')['id']
            put = dict(id=identity, index=0, offset=0, data=b64(b'abc'))
            with self.assertRaises(ValueError): chunks.dispatch('/v1/files/put',put,'other')
            chunks.dispatch('/v1/files/put',put,'phone')
            with self.assertRaises(ValueError): chunks.dispatch('/v1/files/put',put,'phone')
            with self.assertRaises(ValueError): chunks.dispatch('/v1/files/commit',dict(id=identity,sizes=[4]),'phone')
            chunks.uploads[identity]['total'] = MAX_FILES
            with self.assertRaises(ValueError): chunks.dispatch('/v1/files/put',dict(put,offset=3),'phone')
            folder = Path(chunks.uploads[identity]['temp'].name)
            chunks.dispatch('/v1/files/cancel',dict(id=identity),'phone')
            self.assertFalse(folder.exists())
            self.assertEqual(chunks.uploads,{})
        finally: chunks.clear()

    def test_real_300_mb_encrypted_upload_and_download(self):
        self.assertEqual(MAX_FILES,300*1024*1024)
        key = secrets.token_bytes(32)
        client = Protocol(key)
        with tempfile.TemporaryDirectory() as folder:
            saved=[]
            state=State(key,lambda item:saved.extend(save_files(item,folder)),Speech())
            state.pause(False)
            server=Server(('127.0.0.1',0),state)
            threading.Thread(target=server.serve_forever,daemon=True).start()
            def request(path, **value):
                nonce=secrets.token_bytes(12)
                payload=json.dumps(dict(value,time=time.time(),device='phone')).encode()
                body=json.dumps(dict(nonce=b64(nonce),data=b64(client.cipher.encrypt(nonce,payload,('CB1 '+path).encode())))).encode()
                self.assertLess(len(body),1024*1024)
                with urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:{server.server_port}'+path,data=body),timeout=60) as reply:
                    envelope=json.load(reply)
                raw=client.cipher.decrypt(unb64(envelope['nonce']),unb64(envelope['data']),('CB1 reply '+path+' '+b64(nonce)).encode())
                result=json.loads(raw)
                self.assertTrue(result['ok'],result)
                return result
            try:
                identity=request('/v1/files/begin',files=[dict(name='300MB.bin')])['id']
                block=bytes(range(256))*(CHUNK//256)
                encoded=b64(block)
                expected=hashlib.sha256()
                for offset in range(0,MAX_FILES,CHUNK):
                    expected.update(block)
                    request('/v1/files/put',id=identity,index=0,offset=offset,data=encoded)
                request('/v1/files/commit',id=identity,sizes=[MAX_FILES])
                with Path(saved[0]).open('rb') as file:
                    self.assertEqual(hashlib.file_digest(file,'sha256').digest(),expected.digest())
                state.publish(state.item,'pc')
                result=request('/v1/poll',after=-1,file_delivery=1,file_chunks=1)
                manifest=result['item']
                self.assertEqual(manifest['files'][0]['size'],MAX_FILES)
                digest=hashlib.sha256()
                for offset in range(0,MAX_FILES,CHUNK):
                    reply=request('/v1/files/get',id=manifest['chunk_id'],index=0,offset=offset)
                    digest.update(unb64(reply['data']))
                self.assertEqual(digest.digest(),expected.digest())
                state.pause(True)
                self.assertEqual(state.chunks.uploads,{})
            finally:
                server.shutdown()
                server.server_close()


if __name__ == '__main__': unittest.main(verbosity=2)
