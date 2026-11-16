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
from web_files import WebFiles, file_manifest, WEB_CHUNK, STREAM_BLOCK
import uuid


MAX_TEXT = 4096
MAX_MESSAGE = 49152
MAX_PEERS = 4
PEER_ID = re.compile(r'[a-f0-9]{32}\Z')
PATHS = {'/v1/pair', '/v1/clipboard', '/v1/clipboard/current'}
FILE_PATHS = {'/v2/files/begin', '/v2/files/put', '/v2/files/commit', '/v2/files/current', '/v2/files/get', '/v2/files/ack',
              '/v2/files/put-stream', '/v2/files/get-stream'}


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
        self.status = 'Connecting to the web appâ€¦'
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
            self.status = f'{len(files)} files ready Â· tap Receive files on the phone'

    async def listen(self):
        while not self.stop.is_set():
            peers = {}
            try:
                async with connect(self.socket_url, open_timeout=8, close_timeout=1, max_size=MAX_MESSAGE,
                                   compression=None, proxy=None, ping_interval=None) as socket:
                    self.status = 'Ready to pair Â· use the same Wi-Fi'
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
                self.status = 'Web app unavailable Â· reconnectingâ€¦'
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
        inbox = asyncio.Queue(maxsize=128)
        queued_bytes = 0
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
                nonlocal queued_bytes
                limit = WEB_CHUNK if isinstance(message, bytes) else MAX_MESSAGE
                if (not isinstance(message, (str, bytes)) or len(message) > limit
                        or inbox.full() or queued_bytes + len(message) > 2 * STREAM_BLOCK):
                    channel.close()
                    closed.set()
                    return
                queued_bytes += len(message)
                inbox.put_nowait(message)

            async def next_message():
                nonlocal queued_bytes
                message = await asyncio.wait_for(inbox.get(), timeout=30)
                queued_bytes -= len(message)
                return message

            async def consume():
                try:
                    while not closed.is_set():
                        message = await next_message()
                        if not isinstance(message, str):
                            raise ValueError('Unexpected file data')
                        await self.handle(channel, identity, message, files, next_message)
                except (OSError, ValueError, TimeoutError):
                    channel.close()
                    closed.set()

            pending = asyncio.create_task(consume())

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
            self.status = f'Web transfer ended ({type(error).__name__}) Â· retry from the phone'
        finally:
            closed.set()
            if pending:
                # A running disk/clipboard operation must finish before temp cleanup.
                # Wake a consumer waiting for the next command on peer shutdown.
                if not inbox.full():
                    inbox.put_nowait('')
                await asyncio.gather(pending, return_exceptions=True)
            await peer.close()
            files.close()

    async def handle(self, channel, identity, message, files, next_message=None):
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
            if path == '/v2/files/put-stream':
                size = data.get('size')
                if type(size) is not int or not 1 <= size <= STREAM_BLOCK or next_message is None:
                    raise ValueError('Invalid stream size')
                parts, received = [], 0
                while received < size:
                    frame = await next_message()
                    if not isinstance(frame, bytes) or not 1 <= len(frame) <= min(WEB_CHUNK, size - received):
                        raise ValueError('Invalid stream frame')
                    parts.append(frame)
                    received += len(frame)
                data['_binary'] = b''.join(parts)
            result = await asyncio.to_thread(self.dispatch, path, data, files)
        except (OSError, ValueError) as error:
            result = {'ok': False, 'error': str(error)[:200]}
        except Exception:
            result = {'ok': False, 'error': 'The PC could not access the clipboard.'}
        if channel.readyState == 'open':
            binary = result.pop('_binary', None)
            channel.send(self.protocol.seal(context, nonce, result).decode('ascii'))
            if binary:
                for offset in range(0, len(binary), WEB_CHUNK):
                    while channel.bufferedAmount > 256 * 1024:
                        if channel.readyState != 'open' or self.stop.is_set():
                            return
                        await asyncio.sleep(.002)
                    if channel.readyState != 'open':
                        return
                    channel.send(binary[offset:offset + WEB_CHUNK])

    def dispatch(self, path, data, files=None):
        with self.state.changed:
            if self.stop.is_set():
                return {'ok': False, 'error': 'Web pairing was turned off on the PC.'}
            if path in FILE_PATHS:
                return files.dispatch(path, data)
            return dispatch_text(self.state, path, data)
