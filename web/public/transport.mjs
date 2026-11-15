const utf8 = new TextEncoder();
const decoder = new TextDecoder();
export const maxText = 4096;
const maxMessage = 49152;

function base64(bytes) {
  return btoa(String.fromCharCode(...bytes));
}

function fromBase64(value) {
  return Uint8Array.from(atob(value), char => char.charCodeAt(0));
}

function hex(bytes) {
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('');
}

function pairingKey(value) {
  if (!/^[A-Za-z0-9_-]{43}$/.test(value)) throw new Error('Use the web pairing QR shown in ClipBridge on your PC.');
  return fromBase64(value.replaceAll('-', '+').replaceAll('_', '/') + '=');
}

export function keyFromLink(value) {
  const link = new URL(value);
  const home = new URL('./', location.href);
  if (link.origin !== home.origin || link.pathname !== home.pathname || link.search || link.username || link.password) {
    throw new Error('Use the web pairing QR for this ClipBridge page.');
  }
  const key = new URLSearchParams(link.hash.slice(1)).get('pair') ?? '';
  pairingKey(key);
  return key;
}

async function seal(key, path, value) {
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const cipher = await crypto.subtle.encrypt({ name: 'AES-GCM', iv: nonce, additionalData: utf8.encode(`CB1 ${path}`) },
    key, utf8.encode(JSON.stringify({ ...value, time: Date.now() / 1000 })));
  return { nonce: base64(nonce), data: base64(new Uint8Array(cipher)) };
}

async function open(key, path, nonce, raw) {
  if (typeof raw !== 'string' || raw.length > maxMessage) throw new Error('The PC returned an invalid reply.');
  const wire = JSON.parse(raw);
  const clear = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: fromBase64(wire.nonce),
    additionalData: utf8.encode(`CB1 reply ${path} ${nonce}`) }, key, fromBase64(wire.data));
  return JSON.parse(decoder.decode(clear));
}

function waitEvent(target, eventName, failures, signal, errorMessage) {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      target.removeEventListener(eventName, success);
      for (const event of failures) target.removeEventListener(event, fail);
      signal.removeEventListener('abort', abort);
    };
    const success = event => { cleanup(); resolve(event); };
    const fail = event => {
      cleanup();
      const message = event.code === 4004 ? 'The PC is offline. Open ClipBridge and enable iPhone web pairing.' : errorMessage;
      reject(new Error(message));
    };
    const abort = () => { cleanup(); reject(signal.reason); };
    if (signal.aborted) return abort();
    target.addEventListener(eventName, success);
    for (const event of failures) target.addEventListener(event, fail);
    signal.addEventListener('abort', abort);
  });
}

async function gatherIce(peer, signal) {
  while (peer.iceGatheringState !== 'complete') {
    await waitEvent(peer, 'icegatheringstatechange', [], signal);
  }
}

export async function connection(secret, signal, operation) {
  if (!window.isSecureContext || !crypto.subtle) {
    throw new Error('Open ClipBridge over HTTPS in Safari to connect.');
  }
  if (!window.RTCPeerConnection) {
    throw new Error('This browser does not support the direct connection. Try Safari on iPhone or a current browser on Windows.');
  }
  const material = pairingKey(secret);
  const prefix = utf8.encode('ClipBridge web room v1\0');
  const room = hex(new Uint8Array(await crypto.subtle.digest('SHA-256', new Uint8Array([...prefix, ...material]))));
  const key = await crypto.subtle.importKey('raw', material, 'AES-GCM', false, ['encrypt', 'decrypt']);
  const identity = hex(crypto.getRandomValues(new Uint8Array(16)));
  const offerPath = `/web/offer/${identity}`;
  const peer = new RTCPeerConnection({ iceServers: [] });
  const setup = new AbortController();
  const abortSetup = () => setup.abort(signal.reason);
  signal.addEventListener('abort', abortSetup, { once: true });
  if (signal.aborted) abortSetup();
  const setupTimeout = setTimeout(() => setup.abort(new Error('Could not connect to the PC. Check the same Wi-Fi and web pairing.')), 18000);
  let socket;
  try {
    const channel = peer.createDataChannel('clipbridge-text');
    await peer.setLocalDescription(await peer.createOffer());
    await gatherIce(peer, setup.signal);
    const offer = await seal(key, offerPath, { sdp: peer.localDescription.sdp });
    const relay = new URL(`signal/${room}/phone/${identity}`, location.href);
    relay.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(relay);
    await waitEvent(socket, 'open', ['error', 'close'], setup.signal, 'Could not reach the pairing service. Check your internet connection.');
    signal.throwIfAborted();
    socket.send(JSON.stringify(offer));
    const response = await waitEvent(socket, 'message', ['error', 'close'], setup.signal, 'The pairing connection ended. Try again.');
    let answer;
    try {
      answer = await open(key, offerPath, offer.nonce, response.data);
    } catch {
      throw new Error('The PC’s pairing response could not be verified. Scan its current web QR code.');
    }
    socket.close();
    await peer.setRemoteDescription({ type: 'answer', sdp: answer.sdp });
    if (channel.readyState !== 'open') {
      await waitEvent(channel, 'open', ['error', 'close'], setup.signal, 'Could not connect directly. Check that both devices are on the same Wi-Fi.');
    }
    clearTimeout(setupTimeout);
    signal.removeEventListener('abort', abortSetup);
    return await operation(async (path, data = {}) => {
      const context = `/web/${identity}${path}`;
      const wire = await seal(key, context, { device: `web-${identity}`, ...data });
      signal.throwIfAborted();
      const replyPromise = waitEvent(channel, 'message', ['error', 'close'], signal,
        'The PC connection ended. Check Received files before retrying a send.');
      channel.send(JSON.stringify({ path, ...wire }));
      const reply = await replyPromise;
      const result = await open(key, context, wire.nonce, reply.data);
      if (!result.ok) throw new Error(result.error === 'Unknown endpoint' ? 'Update the Windows companion for photos and files.' : result.error || 'The PC could not complete the request.');
      return result;
    });
  } finally {
    clearTimeout(setupTimeout);
    signal.removeEventListener('abort', abortSetup);
    socket?.close();
    peer.close();
  }
}

export function request(secret, path, item, signal) {
  return connection(secret, signal, call => call(path, { item }));
}

export const maxFiles = 20;
export const maxBytes = 300 * 1024 * 1024;

export function validateFiles(files) {
  if (!files.length || files.length > maxFiles) throw new Error('Choose between 1 and 20 files.');
  if (files.reduce((total, file) => total + file.size, 0) > maxBytes) throw new Error('Files exceed 300 MB in total.');
}

export async function sendFiles(secret, files, signal, progress) {
  validateFiles(files);
  return connection(secret, signal, async call => {
    const upload = await call('/v2/files/begin', { files: files.map(file => ({ name: file.name, size: file.size })) });
    const chunkSize = upload.chunk_size;
    if (!Number.isInteger(chunkSize) || chunkSize < 1 || chunkSize > 16384) throw new Error('Invalid transfer size from the PC.');
    let transferred = 0;
    const total = files.reduce((sum, file) => sum + file.size, 0);
    for (let index = 0; index < files.length; index++) {
      const file = files[index];
      for (let offset = 0; offset < file.size; offset += chunkSize) {
        const data = new Uint8Array(await file.slice(offset, offset + chunkSize).arrayBuffer());
        await call('/v2/files/put', { id: upload.id, index, offset, data: base64(data) });
        transferred += data.length;
        progress(transferred, total);
      }
    }
    return call('/v2/files/commit', { id: upload.id });
  });
}

export async function receiveFiles(secret, selection, signal, progress) {
  return connection(secret, signal, async call => {
    const { item } = await call('/v2/files/current', { selection });
    if (!item || item.kind === 'text') return { item, files: [] };
    if (item.kind !== 'files') throw new Error('Unsupported clipboard item.');
    validateFiles(item.files);
    const total = item.files.reduce((sum, file) => sum + file.size, 0);
    if (item.files.some(file => !Number.isSafeInteger(file.size) || file.size < 0 || typeof file.name !== 'string')) {
      throw new Error('Invalid file details from the PC.');
    }
    const files = [];
    let transferred = 0;
    for (let index = 0; index < item.files.length; index++) {
      const file = item.files[index];
      const parts = [];
      for (let offset = 0; offset < file.size;) {
        const reply = await call('/v2/files/get', { id: item.id, index, offset });
        const bytes = fromBase64(reply.data);
        if (!bytes.length || bytes.length > 16384 || offset + bytes.length > file.size) throw new Error('Incomplete file received.');
        parts.push(new Blob([bytes]));
        offset += bytes.length;
        transferred += bytes.length;
        progress(transferred, total);
      }
      files.push(new File(parts, file.name, { type: file.type || 'application/octet-stream' }));
    }
    await call('/v2/files/ack', { id: item.id, saved: true });
    return { item, files };
  });
}
