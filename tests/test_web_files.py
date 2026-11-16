from pathlib import Path
import secrets
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'desktop'))
from protocol import MAX_FILES, b64, unb64
from web_files import WebFiles, WEB_CHUNK, STREAM_BLOCK, file_manifest


class WebFilesTests(unittest.TestCase):
    def setUp(self):
        self.saved = tempfile.TemporaryDirectory()
        self.patch = patch('web_files.RECEIVED', Path(self.saved.name))
        self.patch.start()
        self.bridge = Mock()
        self.bridge.state.paused = False
        self.bridge.outbox = None
        self.files = WebFiles(self.bridge)

    def tearDown(self):
        self.files.close()
        self.patch.stop()
        self.saved.cleanup()

    def test_full_upload_duplicate_names_and_file_clipboard(self):
        names = ['notes.txt', 'notes.txt', 'empty.bin']
        values = [secrets.token_bytes(WEB_CHUNK + 5), 'مرحبا'.encode(), b'']
        result = self.files.dispatch('/v2/files/begin', {'files': [dict(name=name, size=len(raw)) for name, raw in zip(names, values)]})
        identity = result['id']
        for index, raw in enumerate(values):
            for offset in range(0, len(raw), WEB_CHUNK):
                self.files.dispatch('/v2/files/put', dict(id=identity, index=index, offset=offset, data=b64(raw[offset:offset+WEB_CHUNK])))
        reply = self.files.dispatch('/v2/files/commit', {'id': identity})
        self.assertTrue(reply['copied'])
        paths, png = self.bridge.clipboard.write_paths.call_args.args
        self.assertEqual([Path(path).read_bytes() for path in paths], values)
        self.assertEqual([Path(path).name for path in paths], names)
        self.assertIsNone(png)
        with self.assertRaisesRegex(ValueError, 'Unknown upload'):
            self.files.dispatch('/v2/files/commit', {'id': identity})

    def test_sizes_pause_offsets_and_incomplete_upload(self):
        with self.assertRaisesRegex(ValueError, '300 MB'):
            self.files.dispatch('/v2/files/begin', {'files': [dict(name='big.bin', size=MAX_FILES+1)]})
        with self.assertRaises(ValueError):
            self.files.dispatch('/v2/files/begin', {'files': [dict(name='../bad', size=1)]})
        identity = self.files.dispatch('/v2/files/begin', {'files': [dict(name='max.bin', size=MAX_FILES)]})['id']
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            self.files.dispatch('/v2/files/commit', {'id': identity})
        with self.assertRaisesRegex(ValueError, 'offset'):
            self.files.dispatch('/v2/files/put', dict(id=identity,index=0,offset=1,data=b64(b'123')))
        self.bridge.state.paused = True
        with self.assertRaisesRegex(ValueError, 'paused'):
            self.files.dispatch('/v2/files/put', dict(id=identity,index=0,offset=0,data=b64(b'123')))
        self.assertEqual(list(Path(self.saved.name).iterdir()), [])

    def test_download_snapshot_and_outbox_ack_binding(self):
        source = self.files.folder / 'source.bin'
        raw = secrets.token_bytes(40001)
        source.write_bytes(raw)
        self.bridge.outbox = {'id':'selected-batch','paths':[str(source)]}
        info = self.files.dispatch('/v2/files/current', {'selection':True})['item']
        source.write_bytes(b'changed after offer')
        result = b''
        for offset in range(0,len(raw),WEB_CHUNK):
            result += unb64(self.files.dispatch('/v2/files/get', dict(id=info['id'],index=0,offset=offset))['data'])
        self.assertEqual(result,raw)
        self.bridge.outbox = {'id':'new-batch','paths':[str(source)]}
        self.files.dispatch('/v2/files/ack', dict(id=info['id'],saved=True))
        self.assertEqual(self.bridge.outbox['id'],'new-batch')

    def test_cancelled_session_removes_staging_files(self):
        identity = self.files.begin({'files':[dict(name='partial.bin',size=10)]})['id']
        self.files.put(dict(id=identity,index=0,offset=0,data=b64(b'123')))
        stage = self.files.folder
        self.files.close()
        self.assertFalse(stage.exists())
        self.bridge.clipboard.write_paths.assert_not_called()

    def test_manifest_enforces_combined_limit(self):
        source = self.files.folder / 'max.bin'
        with source.open('wb') as output:
            output.truncate(MAX_FILES)
        self.assertEqual(file_manifest([source])[0]['size'],MAX_FILES)
        with self.assertRaisesRegex(ValueError,'300 MB'):
            file_manifest([source,source])

    def test_stream_blocks_verify_before_writing_and_keep_legacy_compatible(self):
        raw = secrets.token_bytes(STREAM_BLOCK + 17)
        begin = self.files.begin({'files': [dict(name='stream.bin', size=len(raw))]})
        self.assertEqual(begin['chunk_size'], WEB_CHUNK)
        self.assertEqual(begin['stream_version'], 1)
        self.assertEqual(begin['stream_block_size'], STREAM_BLOCK)
        request = dict(id=begin['id'], index=0, offset=0, size=STREAM_BLOCK,
                       _binary=raw[:STREAM_BLOCK], sha256='wrong')
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.files.dispatch('/v2/files/put-stream', request)
        self.assertEqual(self.files.upload['paths'][0].stat().st_size, 0)
        request['sha256'] = hashlib.sha256(request['_binary']).hexdigest()
        self.files.dispatch('/v2/files/put-stream', request)
        with self.assertRaisesRegex(ValueError, 'offset'):
            self.files.dispatch('/v2/files/put-stream', request)
        # Mixing an existing chunk client with the new capability stays valid.
        self.files.put(dict(id=begin['id'], index=0, offset=STREAM_BLOCK, data=b64(raw[STREAM_BLOCK:])))
        self.files.commit({'id': begin['id']})
        paths = self.bridge.clipboard.write_paths.call_args.args[0]
        self.assertEqual(Path(paths[0]).read_bytes(), raw)
        self.bridge.clipboard.read_paths.return_value = paths
        info = self.files.current({})['item']
        result = self.files.dispatch('/v2/files/get-stream', dict(id=info['id'], index=0, offset=0, size=STREAM_BLOCK))
        self.assertEqual(result['_binary'], raw[:STREAM_BLOCK])
        self.assertEqual(result['sha256'], hashlib.sha256(result['_binary']).hexdigest())
        for size in (0, STREAM_BLOCK + 1, True):
            with self.assertRaises(ValueError):
                self.files.dispatch('/v2/files/get-stream', dict(id=info['id'], index=0, offset=0, size=size))
        with self.assertRaises(ValueError):
            self.files.dispatch('/v2/files/get-stream', dict(id=info['id'], index=0, offset=len(raw), size=1))
        self.bridge.state.paused = True
        with self.assertRaisesRegex(ValueError, 'paused'):
            self.files.dispatch('/v2/files/get-stream', dict(id=info['id'], index=0, offset=0, size=1))


if __name__ == '__main__':
    unittest.main()
