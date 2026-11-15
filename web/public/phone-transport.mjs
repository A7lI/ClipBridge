import { validateFiles, maxBytes, maxText } from './transport.mjs';

const encoder = new TextEncoder(), decoder = new TextDecoder();
const chunkSize = 32 * 1024;
const to64 = bytes => btoa(String.fromCharCode(...bytes)).replaceAll('+', '-').replaceAll('/', '_').replaceAll('=', '');
const from64 = value => Uint8Array.from(atob(value.replaceAll('-', '+').replaceAll('_', '/')), c => c.charCodeAt(0));
const randomId = () => crypto.randomUUID();
const opposite = role => role === 'host' ? 'guest' : 'host';
const home = () => new URL('./phone', location.href);
function checkSecret(secret) {
  if (!/^[A-Za-z0-9_-]{43}$/.test(secret)) throw new Error('This is not a ClipBridge phone invitation.');
  return from64(secret);
}

export async function packInvitation(kind, data) {
  const stream = new Blob([JSON.stringify(data)]).stream().pipeThrough(new CompressionStream('deflate'));
  const bytes = new Uint8Array(await new Response(stream).arrayBuffer());
  if (bytes.length > 12000) throw new Error('Pairing information is too large. Turn off extra VPN/network adapters and try again.');
  const url = home();
  url.hash = `${kind}=${to64(bytes)}`;
  return url.href;
}

export async function readInvitation(value) {
  const url = new URL(value.trim());
  if (url.origin !== home().origin || ![home().pathname, home().pathname + '.html'].includes(url.pathname) || url.search || url.username || url.password) throw new Error('Use a ClipBridge phone-to-phone invitation.');
  const fields = new URLSearchParams(url.hash.slice(1));
  if (fields.has('mobile')) {
    checkSecret(fields.get('mobile'));
    return { kind: 'mobile', secret: fields.get('mobile') };
  }
  const kind = fields.has('offer') ? 'offer' : fields.has('answer') ? 'answer' : '';
  const value64 = fields.get(kind);
  if (!kind || !value64 || value64.length > 16000 || !/^[A-Za-z0-9_-]+$/.test(value64)) throw new Error('Use a ClipBridge phone invitation or return QR.');
  // Bound decompression even for a hostile QR/photo.
  const reader = new Blob([from64(value64)]).stream().pipeThrough(new DecompressionStream('deflate')).getReader();
  let size = 0; const parts = [];
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 32768) throw new Error('Pairing information is too large.');
      parts.push(value);
    }
  } finally { await reader.cancel(); }
  const data = JSON.parse(await new Blob(parts).text());
  if (data.v !== 1 || typeof data.sdp !== 'string' || data.sdp.length > 30000) throw new Error('Invalid offline pairing information.');
  if (kind === 'offer') checkSecret(data.secret);
  else if (!/^[a-f0-9]{64}$/.test(data.room)) throw new Error('Invalid return QR.');
  return { kind, ...data };
}

async function gather(peer) {
  if (peer.iceGatheringState === 'complete') return;
  await new Promise((resolve, reject) => {
    const timer = setTimeout(() => { cleanup(); reject(new Error('Could not prepare the local connection. Check Wi-Fi and try again.')); }, 12000);
    const changed = () => { if (peer.iceGatheringState === 'complete') { cleanup(); resolve(); } };
    const cleanup = () => { clearTimeout(timer); peer.removeEventListener('icegatheringstatechange', changed); };
    peer.addEventListener('icegatheringstatechange', changed);
  });
}

export class PhoneSession extends EventTarget {
  constructor() {
    super();
    this.sequence = 0;
    this.lastSequence = 0;
    this.pending = new Map();
    this.receiveChain = Promise.resolve();
    this.sendChain = Promise.resolve();
    this.closed = false;
  }
  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }

  async prepare(role, secret = to64(crypto.getRandomValues(new Uint8Array(32)))) {
    this.role = role;
    this.secret = secret;
    const material = checkSecret(secret);
    const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', new Uint8Array([...encoder.encode('ClipBridge phone v1\0'), ...material])));
    this.room = Array.from(digest, b => b.toString(16).padStart(2, '0')).join('');
    this.code = String(new DataView(digest.buffer).getUint32(0) % 1000000).padStart(6, '0');
    this.key = await crypto.subtle.importKey('raw', material, 'AES-GCM', false, ['encrypt', 'decrypt']);
    return this;
  }

  async online(role, secret) {
    await this.prepare(role, secret);
    const url = new URL(`mobile/${this.room}/${role}`, location.href);
    url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    this.socket = new WebSocket(url);
    this.socket.binaryType = 'arraybuffer';
    this.socket.addEventListener('message', event => {
      if (typeof event.data === 'string') {
        try { if (JSON.parse(event.data).event === 'ready') this.hello(); } catch { this.close('Invalid relay response.'); }
      } else this.queue(event.data);
    });
    this.socket.addEventListener('close', () => this.close('The other phone disconnected, the invitation expired, or the service limit was reached. Create or scan a new invitation.'));
    this.socket.addEventListener('error', () => this.close('Could not reach the online sharing service. Check internet access or use Offline nearby.'));
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => { cleanup(); reject(new Error('Online sharing did not connect. Check your internet connection.')); }, 15000);
      const open = () => { cleanup(); resolve(); };
      const error = () => { cleanup(); reject(new Error('Invitation is unavailable. Ask the other phone to create a new one.')); };
      const cleanup = () => { clearTimeout(timer); this.socket.removeEventListener('open', open); this.socket.removeEventListener('error', error); };
      this.socket.addEventListener('open', open);
      this.socket.addEventListener('error', error);
    });
    const invitation = home(); invitation.hash = 'mobile=' + this.secret;
    return invitation.href;
  }

  attach(channel) {
    this.channel = channel;
    channel.binaryType = 'arraybuffer';
    channel.addEventListener('message', event => this.queue(event.data));
    channel.addEventListener('open', () => this.hello());
    channel.addEventListener('close', () => this.close('The local connection ended. Keep both phones open and pair again.'));
    channel.addEventListener('error', () => this.close('The local connection failed. Check Wi-Fi or use Online.'));
  }

  async offline(offer) {
    if (!window.RTCPeerConnection) throw new Error('Local sharing needs WebRTC. Update your browser or use Online.');
    await this.prepare(offer ? 'guest' : 'host', offer?.secret);
    this.peer = new RTCPeerConnection({ iceServers: [] });
    this.peer.addEventListener('connectionstatechange', () => {
      if (this.peer.connectionState === 'failed') this.close('Could not connect locally. Use the same Wi-Fi/hotspot, or try Online.');
    });
    if (offer) {
      this.peer.addEventListener('datachannel', event => {
        if (event.channel.label === 'clipbridge-phone-v1' && !this.channel) this.attach(event.channel);
        else event.channel.close();
      });
      await this.peer.setRemoteDescription({ type: 'offer', sdp: offer.sdp });
      await this.peer.setLocalDescription(await this.peer.createAnswer());
    } else {
      this.attach(this.peer.createDataChannel('clipbridge-phone-v1'));
      await this.peer.setLocalDescription(await this.peer.createOffer());
    }
    await gather(this.peer);
    return packInvitation(offer ? 'answer' : 'offer', { v: 1, ...(offer ? { room: this.room } : { secret: this.secret }), sdp: this.peer.localDescription.sdp });
  }

  async answer(invitation) {
    if (!this.peer || this.role !== 'host' || invitation.room !== this.room) throw new Error('This return QR belongs to a different invitation.');
    await this.peer.setRemoteDescription({ type: 'answer', sdp: invitation.sdp });
  }

  hello() {
    if (this.helloSent || this.closed) return;
    this.helloSent = true;
    this.frame({ type: 'hello', role: this.role }).catch(error => this.close(error.message));
  }

  frame(meta, bytes = new Uint8Array()) {
    const action = this.sendChain.then(async () => {
      if (this.closed) throw new Error('The other phone is disconnected.');
      const json = encoder.encode(JSON.stringify(meta));
      if (json.length > 32768 || bytes.length > chunkSize) throw new Error('Transfer frame is too large.');
      const clear = new Uint8Array(4 + json.length + bytes.length);
      new DataView(clear.buffer).setUint32(0, json.length);
      clear.set(json, 4); clear.set(bytes, 4 + json.length);
      const seq = ++this.sequence;
      const nonce = crypto.getRandomValues(new Uint8Array(12));
      const cipher = new Uint8Array(await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce,
        additionalData: encoder.encode(`CB-phone1 ${this.room} ${this.role} ${seq}`) }, this.key, clear));
      const wire = new Uint8Array(16 + cipher.length);
      new DataView(wire.buffer).setUint32(0, seq); wire.set(nonce, 4); wire.set(cipher, 16);
      const transport = this.socket || this.channel;
      if (transport?.readyState !== (this.socket ? WebSocket.OPEN : 'open')) throw new Error('The other phone is disconnected.');
      transport.send(wire);
    });
    this.sendChain = action.catch(() => {});
    return action;
  }

  queue(wire) {
    this.receiveChain = this.receiveChain.then(() => this.read(wire)).catch(error => this.close(error.message || 'The transfer could not be verified. Pair again.'));
  }

  async read(wire) {
    if (!(wire instanceof ArrayBuffer) || wire.byteLength < 36 || wire.byteLength > 66 * 1024) throw new Error('Invalid transfer frame.');
    const seq = new DataView(wire).getUint32(0);
    if (seq !== this.lastSequence + 1) throw new Error('Transfer sequence could not be verified.');
    const raw = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: new Uint8Array(wire, 4, 12),
      additionalData: encoder.encode(`CB-phone1 ${this.room} ${opposite(this.role)} ${seq}`) }, this.key, new Uint8Array(wire, 16));
    const length = new DataView(raw).getUint32(0);
    if (length > 32768 || length > raw.byteLength - 4) throw new Error('Invalid transfer metadata.');
    const meta = JSON.parse(decoder.decode(new Uint8Array(raw, 4, length)));
    const bytes = new Uint8Array(raw, 4 + length);
    this.lastSequence = seq;
    if (meta.type === 'hello') {
      if (meta.role !== opposite(this.role) || this.ready) throw new Error('Unexpected pairing response.');
      this.ready = true; this.emit('connected', { code: this.code }); return;
    }
    if (!this.ready) throw new Error('Pairing was not verified.');
    if (meta.type === 'reply') {
      const request = this.pending.get(meta.request);
      if (request) { this.pending.delete(meta.request); request.resolve(meta); }
      return;
    }
    if (meta.type === 'cancel') {
      if (this.incoming?.id === meta.id) { this.incoming = null; this.emit('cancelled', {}); }
      return;
    }
    if (meta.type === 'offer') {
      if (this.incoming) return this.reply(meta, false, 'Finish or decline the current incoming transfer.');
      if (!/^[a-f0-9-]{36}$/.test(meta.id)) throw new Error('Invalid transfer ID.');
      if (meta.kind === 'text') {
        if (typeof meta.text !== 'string' || !meta.text || encoder.encode(meta.text).length > maxText || meta.text.includes('\0')) return this.reply(meta, false, 'Text supports up to 4 KB.');
      } else if (meta.kind === 'files') {
        validateFiles(meta.files);
        if (meta.files.some(f => !Number.isSafeInteger(f.size) || f.size < 0 || typeof f.name !== 'string' || !f.name || f.name.length > 240 || /[\x00-\x1f/\\]/.test(f.name))) throw new Error('Invalid file details.');
      } else throw new Error('Unsupported transfer.');
      this.incoming = { ...meta, accepted: false, parts: [], index: 0, offset: 0, done: 0, filesReceived: [] };
      this.emit('offer', meta); return;
    }
    const task = this.incoming;
    if (!task || task.id !== meta.id || !task.accepted) return this.reply(meta, false, 'Accept the incoming transfer first.');
    if (meta.type === 'chunk') {
      this.skipEmpty(task);
      const file = task.files[task.index];
      if (!file || meta.index !== task.index || meta.offset !== task.offset || !bytes.length || bytes.length > chunkSize || task.offset + bytes.length > file.size) throw new Error('Incomplete or invalid file chunk.');
      task.parts.push(new Blob([bytes])); task.offset += bytes.length; task.done += bytes.length;
      if (task.done > maxBytes) throw new Error('Files exceed 300 MB in total.');
      this.skipEmpty(task);
      this.emit('progress', { direction: 'receive', done: task.done, total: task.files.reduce((n, f) => n + f.size, 0) });
      return this.reply(meta, true);
    }
    if (meta.type === 'finish') {
      this.skipEmpty(task);
      if (task.index !== task.files.length) throw new Error('Incomplete files.');
      this.incoming = null;
      this.emit('received', { kind: 'files', files: task.filesReceived });
      return this.reply(meta, true);
    }
    throw new Error('Unsupported transfer message.');
  }

  skipEmpty(task) {
    while (task.index < task.files.length && task.offset === task.files[task.index].size) {
      const file = task.files[task.index];
      task.filesReceived.push(new File(task.parts, file.name, { type: file.type || 'application/octet-stream' }));
      task.parts = []; task.offset = 0; task.index++;
    }
  }

  reply(meta, ok, error) { return this.frame({ type: 'reply', request: meta.request, ok, error }); }

  async accept(accepted) {
    const task = this.incoming;
    if (!task || task.accepted) return;
    if (!accepted) { this.incoming = null; return this.reply(task, false, 'The other phone declined the transfer.'); }
    task.accepted = true;
    if (task.kind === 'text') {
      this.incoming = null;
      this.emit('received', { kind: 'text', text: task.text });
    }
    return this.reply(task, true);
  }

  ask(meta, bytes, signal, timeout = 60000) {
    signal.throwIfAborted();
    const request = randomId();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => finish(new Error('The other phone did not respond. Keep both screens open and try again.')), timeout);
      const abort = () => finish(signal.reason || new Error('Transfer cancelled.'));
      const finish = (error, value) => {
        clearTimeout(timer); signal.removeEventListener('abort', abort); this.pending.delete(request);
        if (error) reject(error); else if (!value.ok) reject(new Error(value.error || 'Transfer declined.')); else resolve(value);
      };
      this.pending.set(request, { resolve: value => finish(null, value), reject: error => finish(error) });
      signal.addEventListener('abort', abort, { once: true });
      this.frame({ ...meta, request }, bytes).catch(error => finish(error));
    });
  }

  async send(item, signal) {
    if (!this.ready || this.sending) throw new Error('Connect to a phone and finish the current send first.');
    const id = randomId();
    let offer;
    if (item.kind === 'text') {
      if (!item.text || encoder.encode(item.text).length > maxText || item.text.includes('\0')) throw new Error('Send text up to 4 KB.');
      offer = { kind: 'text', text: item.text };
    } else {
      validateFiles(item.files);
      offer = { kind: 'files', files: item.files.map(f => ({ name: f.name, size: f.size, type: f.type })) };
    }
    this.sending = id;
    try {
      this.emit('waiting', {});
      await this.ask({ type: 'offer', id, ...offer }, undefined, signal, 120000);
      if (item.kind === 'files') {
        let done = 0; const total = item.files.reduce((n, f) => n + f.size, 0);
        for (let index = 0; index < item.files.length; index++) {
          const file = item.files[index];
          for (let offset = 0; offset < file.size; offset += chunkSize) {
            const bytes = new Uint8Array(await file.slice(offset, offset + chunkSize).arrayBuffer());
            await this.ask({ type: 'chunk', id, index, offset }, bytes, signal);
            done += bytes.length; this.emit('progress', { direction: 'send', done, total });
          }
        }
        await this.ask({ type: 'finish', id }, undefined, signal);
      }
    } catch (error) {
      this.frame({ type: 'cancel', id }).catch(() => {});
      throw error;
    } finally { this.sending = null; }
  }

  close(message = 'Disconnected. Create or scan a new invitation to share again.') {
    if (this.closed) return;
    this.closed = true; this.ready = false; this.incoming = null;
    for (const pending of Array.from(this.pending.values())) pending.reject(new Error(message));
    this.socket?.close(); this.peer?.close();
    this.emit('disconnected', { message });
  }
}
