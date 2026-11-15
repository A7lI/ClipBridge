"""Find an already-paired PC on the LAN without broadcasting the pairing key."""
import base64
import hashlib
import hmac
import ipaddress
import json
import socket
import threading

PORT = 48722


def mac(key, message):
    return base64.b64encode(hmac.new(key, message.encode('ascii'), hashlib.sha256).digest()).decode('ascii')


def discovery_reply(key, data, tcp_port):
    request = json.loads(data)
    nonce = request['nonce']
    if not isinstance(nonce, str) or len(nonce) > 64 or len(base64.b64decode(nonce, validate=True)) != 16:
        return None
    expected = mac(key, 'CB1 discover '+nonce)
    if not hmac.compare_digest(str(request.get('auth', '')), expected):
        return None
    return json.dumps({'nonce': nonce, 'port': tcp_port,
                       'auth': mac(key, 'CB1 here '+nonce+' '+str(tcp_port))}).encode('ascii')


class Discovery:
    def __init__(self, key, tcp_port):
        self.key = key
        self.tcp_port = tcp_port
        self.stopped = threading.Event()
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self.socket.bind(('0.0.0.0', PORT))
            self.socket.settimeout(.5)
        except OSError:
            self.socket.close()
            raise
        threading.Thread(target=self.run, daemon=True, name='ClipBridgeDiscovery').start()

    def run(self):
        while not self.stopped.is_set():
            try:
                data, address = self.socket.recvfrom(2048)
                if not ipaddress.ip_address(address[0]).is_private:
                    continue
                reply = discovery_reply(self.key, data, self.tcp_port)
                if reply:
                    self.socket.sendto(reply, address)
            except socket.timeout:
                continue
            except (OSError, ValueError, KeyError, TypeError):
                continue

    def close(self):
        self.stopped.set()
        self.socket.close()
