import json
from pathlib import Path
import secrets
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'desktop'))
from protocol import b64
from server import State
from local_sender import LocalSender, send_selection, pipe_name
from multiprocessing import AuthenticationError
from multiprocessing.connection import Client, PipeClient


class Speech:
    def available(self):return False


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.state=State(secrets.token_bytes(32),lambda value:None,Speech())
        self.state.pause(False)
        self.item={'kind':'files','files':[{'name':'binary.bin','data':b64(b'\x00binary\xff')}]}

    def poll(self,device='phone',capable=1):
        return self.state.dispatch('/v1/poll',{'device':device,'after':-1,'file_delivery':capable})

    def test_files_survive_clipboard_updates_and_require_device_ack(self):
        self.poll();identity=self.state.deliveries.enqueue(self.item)
        self.state.publish({'kind':'text','text':'new clipboard'},'pc')
        poll=self.poll();self.assertEqual(poll['item']['text'],'new clipboard')
        self.assertEqual(poll['transfer']['id'],identity)
        self.assertEqual(poll['transfer']['item'],self.item)
        self.assertIsNone(self.poll('other-phone')['transfer'])
        with self.assertRaises(ValueError):self.state.dispatch('/v1/files/ack',{'device':'other-phone','id':identity,'saved':True})
        self.state.dispatch('/v1/files/ack',{'device':'phone','id':identity,'saved':True})
        self.assertTrue(self.state.deliveries.wait(identity)['ok'])
        self.assertIsNone(self.poll()['transfer'])
        self.state.dispatch('/v1/files/ack',{'device':'phone','id':identity,'saved':True})

    def test_old_phone_disconnected_and_queue_limit(self):
        self.poll(capable=0)
        with self.assertRaises(ValueError):self.state.deliveries.enqueue(self.item)
        self.poll()
        for _ in range(4):self.state.deliveries.enqueue(self.item)
        with self.assertRaises(ValueError):self.state.deliveries.enqueue(self.item)
        self.state.deliveries.last_poll-=36
        with self.assertRaises(ValueError):self.state.deliveries.enqueue(self.item)

    def test_save_failure_pause_and_timeout_never_report_success(self):
        self.poll();identity=self.state.deliveries.enqueue(self.item)
        self.state.dispatch('/v1/files/ack',{'device':'phone','id':identity,'saved':False,'error':'Storage full'})
        with self.assertRaisesRegex(ValueError,'Storage full'):self.state.deliveries.wait(identity)
        identity=self.state.deliveries.enqueue(self.item);self.state.pause(True)
        with self.assertRaisesRegex(ValueError,'paused'):self.state.deliveries.wait(identity)
        self.state.pause(False);identity=self.state.deliveries.enqueue(self.item)
        with self.state.changed:
            self.state.deliveries.pending[0]['deadline']=time.monotonic()-1
            self.state.deliveries.prune()
        with self.assertRaisesRegex(ValueError,'timed out'):self.state.deliveries.wait(identity)

    def test_named_pipe_selection_routes_exact_unicode_names_without_clipboard(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp);files=[folder/'spaces & العربية.txt',folder/'empty.txt']
            files[0].write_bytes(b'original bytes');files[1].touch()
            received=[];key=secrets.token_bytes(32)
            sender=LocalSender(folder,key,lambda item:received.append(item) or {'ok':True,'message':'Saved'})
            try:
                with PipeClient(pipe_name(folder)):
                    pass
                with self.assertRaises(AuthenticationError):
                    Client(pipe_name(folder), family='AF_PIPE', authkey=secrets.token_bytes(32))
                with self.assertRaisesRegex(ValueError,'reopen ClipBridge-PC.exe from File Explorer'):
                    send_selection(folder,secrets.token_bytes(32),files)
                self.assertEqual(received,[])
                result=send_selection(folder,key,files)
                self.assertTrue(result['ok'])
                self.assertEqual([f['name'] for f in received[0]['files']],[f.name for f in files])
                self.assertEqual(received[0]['files'][0]['data'],b64(b'original bytes'))
            finally:sender.close()

    def test_explicit_send_waits_until_phone_confirms(self):
        self.poll();done=[]
        worker=threading.Thread(target=lambda:done.append(self.state.send_files(self.item)))
        worker.start()
        with self.state.changed:self.state.changed.wait_for(lambda:bool(self.state.deliveries.pending),timeout=2)
        self.assertEqual(done,[])
        identity=self.poll()['transfer']['id']
        self.state.dispatch('/v1/files/ack',{'device':'phone','id':identity,'saved':True})
        worker.join(2);self.assertTrue(done[0]['ok'])


if __name__=='__main__':unittest.main()
