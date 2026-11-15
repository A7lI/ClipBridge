"""Connect the iPhone web app to the existing Windows clipboard operations."""
import asyncio
import hashlib
import json
import re
import threading
from urllib.parse import urlsplit

from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from protocol import Protocol, b64
from web_files import WebFiles, file_manifest
import uuid


MAX_TEXT = 4096
MAX_MESSAGE = 49152
MAX_PEERS = 4
PEER_ID = re.compile(r'[a-f0-9]{32}\Z')
PATHS = {'/v1/pair', '/v1/clipboard', '/v1/clipboard/current'}
FILE_PATHS = {'/v2/files/begin', '/v2/files/put', '/v2/files/commit', '/v2/files/current', '/v2/files/get', '/v2/files/ack'}


def web_urls(base, key):
    url = urlsplit(base)
    local_debug = url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1')
    if not url.hostname or url.username or url.password or url.query or url.fragment or (
        url.scheme != 'https' and not local_debug
    ):
        raise ValueError('Use an HTTPS URL for the ClipBridge web app.')
    base = f'{url.scheme}://{url.netloc}{url.path.rstrip("/")}/'
    room = hashlib.sha256(b'ClipBridge web room v1\x00' + key).hexdigest()
    ws = 'wss' if url.scheme == 'https' else 'ws'
    socket = f'{ws}://{url.netloc}{url.path.rstrip("/")}/signal/{room}/pc'
    secret = b64(key).replace('+', '-').replace('/', '_').rstrip('=')
    return base + '#pair=' + secret, socket


def dispatch_text(state, path, data):
    if path == '/v1/clipboard':
        item = data.get('item')
        if not isinstance(item, dict) or item.get('kind') != 'text':
            return {'ok': False, 'error': 'The web app accepts plain text.'}
        text = item.get('text')
        if not isinstance(text, str) or not text or len(text.encode('utf-8')) > MAX_TEXT:
            return {'ok': False, 'error': 'Send between 1 byte and 4 KB of text.'}
    reply = state.dispatch(path, data)
    if path == '/v1/clipboard/current' and reply.get('item'):
        if len(reply['item']['text'].encode('utf-8')) > MAX_TEXT:
            return {'ok': False, 'error': 'The PC clipboard exceeds the 4 KB web preview limit.'}
    return reply


class WebBridge:
    def __init__(self, base, key, state, clipboard=None):
        self.link, self.socket_url = web_urls(base, key)
        self.protocol = Protocol(key)
        self.state = state
        self.clipboard = clipboard
        self.outbox = None
        self.status = 'Connecting to the web app…'
        self.stop = threading.Event()
        self.loop = None
        self.task = None
        self.thread = threading.Thread(target=self.run, name='ClipBridgeWeb', daemon=True)
        self.thread.start()

    def run(self):
        async def serve():
            self.loop = asyncio.get_running_loop()
            self.task = asyncio.current_task()
            try:
                await self.listen()
            except asyncio.CancelledError:
                pass
            finally:
                self.task = None

        asyncio.run(serve())

    def close(self):
        self.stop.set()
        if self.task and self.loop:
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass

    def offer_paths(self, paths):
        files = file_manifest(paths)
        with self.state.changed:
            if self.stop.is_set() or self.state.paused:
                raise ValueError('Enable web pairing and start syncing first')
            self.outbox = {'id': str(uuid.uuid4()), 'paths': list(paths)}
            self.status = f'{len(files)} files ready · tap Receive files on the phone'

    async def listen(self):
        while not self.stop.is_set():
            peers = {}
            try:
                async with connect(self.socket_url, open_timeout=8, close_timeout=1, max_size=MAX_MESSAGE,
                                   compression=None, proxy=None, ping_interval=None) as socket:
                    self.status = 'Ready to pair · use the same Wi-Fi'
                    async for raw in socket:
                        if self.stop.is_set():
                            break
                        try:
                            message = json.loads(raw)
                            identity = message['peer']
                            if not PEER_ID.fullmatch(identity) or identity in peers or len(peers) >= MAX_PEERS:
                                continue
                            path = '/web/offer/' + identity
                            offer, nonce = self.protocol.open(path, json.dumps(message['signal']))
                            if not isinstance(offer.get('sdp'), str):
                                continue
                        except Exception:
                            continue
                        task = asyncio.create_task(self.negotiate(socket, identity, path, offer['sdp'], nonce))
                        peers[identity] = task
                        task.add_done_callback(lambda _, peer=identity: peers.pop(peer, None))
            except (OSError, TimeoutError, WebSocketException):
                self.status = 'Web app unavailable · reconnecting…'
            finally:
                remaining = list(peers.values())
                for task in remaining:
                    task.cancel()
                await asyncio.gather(*remaining, return_exceptions=True)
            if not self.stop.is_set():
                await asyncio.sleep(2)

    async def negotiate(self, socket, identity, path, sdp, nonce):
        peer = RTCPeerConnection(RTCConfiguration(iceServers=[]))
        closed = asyncio.Event()
        pending = None
        files = WebFiles(self)

        @peer.on('connectionstatechange')
        def state_changed():
            if peer.connectionState in ('closed', 'failed'):
                closed.set()

        @peer.on('datachannel')
        def attach(channel):
            nonlocal pending
            if channel.label != 'clipbridge-text':
                channel.close()
                return

            @channel.on('close')
            def channel_closed():
                closed.set()

            @channel.on('message')
            def received(message):
                nonlocal pending
                if pending is None or pending.done():
                    pending = asyncio.create_task(self.handle(channel, identity, message, files))

        try:
            async with asyncio.timeout(900):
                media = [line for line in sdp.splitlines() if line.startswith('m=')]
                if len(media) != 1 or not media[0].startswith('m=application '):
                    return
                async with asyncio.timeout(20):
                    await peer.setRemoteDescription(RTCSessionDescription(sdp=sdp, type='offer'))
                    await peer.setLocalDescription(await peer.createAnswer())
                answer = self.protocol.seal(path, nonce, {'sdp': peer.localDescription.sdp})
                await socket.send(json.dumps({'peer': identity, 'signal': json.loads(answer)}))
                await closed.wait()
        except Exception as error:
            self.status = f'Web transfer ended ({type(error).__name__}) · retry from the phone'
        finally:
            if pending:
                # A running disk/clipboard operation must finish before temp cleanup.
                await asyncio.gather(pending, return_exceptions=True)
            await peer.close()
            files.close()

    async def handle(self, channel, identity, message, files):
        try:
            if self.stop.is_set() or not isinstance(message, str) or len(message) > MAX_MESSAGE:
                return
            path = json.loads(message)['path']
            if path not in PATHS | FILE_PATHS:
                return
            # Bind requests to this one WebRTC operation as well as to the endpoint.
            context = f'/web/{identity}{path}'
            data, nonce = self.protocol.open(context, message)
        except Exception:
            return
        try:
            result = await asyncio.to_thread(self.dispatch, path, data, files)
        except (OSError, ValueError) as error:
            result = {'ok': False, 'error': str(error)[:200]}
        except Exception:
            result = {'ok': False, 'error': 'The PC could not access the clipboard.'}
        if channel.readyState == 'open':
            channel.send(self.protocol.seal(context, nonce, result).decode('ascii'))

    def dispatch(self, path, data, files=None):
        with self.state.changed:
            if self.stop.is_set():
                return {'ok': False, 'error': 'Web pairing was turned off on the PC.'}
            if path in FILE_PATHS:
                return files.dispatch(path, data)
            return dispatch_text(self.state, path, data)
