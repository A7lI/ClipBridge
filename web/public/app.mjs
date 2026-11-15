import { keyFromLink, maxText, request, validateFiles, sendFiles, receiveFiles } from './transport.mjs';
import { showFiles, clearFiles } from './files.mjs';

const byId = id => document.getElementById(id);
const storageKey = 'clipbridge.web.pairing.v1';
const status = byId('status');
const draft = byId('draft');
const received = byId('received');
const incoming = byId('incoming');
const cameraView = byId('camera-view');
const qrPhoto = byId('qr-photo');
const qrCanvas = document.createElement('canvas');
const qrContext = qrCanvas.getContext('2d', { willReadFrequently: true });
let pairing;
try { pairing = localStorage.getItem(storageKey); } catch { pairing = null; }
let active;
let camera;
let selectedFiles = [];

function say(message, error = false) {
  status.textContent = message;
  status.hidden = !message;
  status.toggleAttribute('data-error', error);
}

function render() {
  byId('pairing').hidden = Boolean(pairing);
  byId('transfer').hidden = !pairing;
  for (const button of document.querySelectorAll('main button')) button.disabled = Boolean(active);
  byId('send-selected').disabled = Boolean(active) || !selectedFiles.length;
  byId('cancel-transfer').disabled = false;
  byId('send-files').disabled = Boolean(active);
  byId('send-photos').disabled = Boolean(active);
}

async function run(progress, operation, files = false) {
  if (active) return;
  const controller = new AbortController();
  active = controller;
  const timeout = setTimeout(() => controller.abort(new Error('The PC did not respond. Check that both devices are on the same Wi-Fi and ClipBridge is running.')), files ? 900000 : 18000);
  byId('transfer-progress').hidden = !files;
  byId('progress').value = 0;
  render();
  say(progress);
  try {
    await operation(controller.signal);
  } catch (error) {
    if (error.name !== 'AbortError') say(error.message || 'The transfer could not be completed.', true);
  } finally {
    clearTimeout(timeout);
    active = undefined;
    byId('transfer-progress').hidden = true;
    render();
  }
}

function pair(link) {
  stopCamera();
  let key;
  try {
    key = keyFromLink(link.trim());
  } catch {
    say('Use the web pairing QR or link shown in ClipBridge on your PC.', true);
    return;
  }
  return run('Verifying the PC…', async signal => {
    const result = await request(key, '/v1/pair', undefined, signal);
    let saved = true;
    try { localStorage.setItem(storageKey, key); } catch { saved = false; }
    pairing = key;
    clearReceived();
    if (!saved) {
      say('Paired for this session. Browser storage is unavailable, so pair again after reopening.');
    } else {
      say(result.paused ? 'Paired. Start syncing on the PC to transfer text.' : 'Paired. Your PC is ready for transfers.');
    }
  });
}

function clearReceived() {
  received.hidden = true;
  incoming.value = '';
  clearFiles();
}

function fileProgress(done, total) {
  const percent = total ? Math.floor(done * 100 / total) : 100;
  byId('progress').value = percent;
  say(`Transferring ${percent}% · ${(done / 1024 / 1024).toFixed(1)} of ${(total / 1024 / 1024).toFixed(1)} MB`);
}

function upload(files) {
  try { validateFiles(files); } catch (error) { say(error.message, true); return; }
  return run('Connecting to send files…', async signal => {
    const result = await sendFiles(pairing, files, signal, fileProgress);
    say(result.message || (result.image_copied ? 'Photo saved on the PC and copied for pasting as an image or file.' : 'Files saved on the PC and copied. Paste them in Explorer with Ctrl+V.'));
  }, true);
}

function download(selection) {
  return run('Connecting to receive…', async signal => {
    clearReceived();
    const result = await receiveFiles(pairing, selection, signal, fileProgress);
    if (!result.item) return say('Copy text, photos, or files on Windows, then try again.');
    if (result.item.kind === 'text') {
      incoming.value = result.item.text;
      received.hidden = false;
      say('Text received.');
    } else {
      showFiles(result.files, say);
      say('Files received. Save or share them before closing the app.');
    }
  }, true);
}

for (const id of ['send-files', 'send-photos']) {
  byId(id).addEventListener('change', event => {
    try {
      const files = Array.from(event.target.files);
      validateFiles(files);
      selectedFiles = files;
      byId('selected-files').textContent = files.map(file => file.name).join(', ');
    } catch (error) {
      selectedFiles = [];
      byId('selected-files').textContent = '';
      say(error.message, true);
    }
    render();
  });
}
byId('send-selected').addEventListener('click', () => upload(selectedFiles));
byId('receive-files').addEventListener('click', () => download(true));
byId('cancel-transfer').addEventListener('click', () => {
  active?.abort(new Error('Transfer cancelled. Check Received files on the PC before retrying a send.'));
});

function send(text) {
  if (!text || new TextEncoder().encode(text).length > maxText || text.includes('\0')) {
    say('Enter text up to 4 KB without null characters.', true);
    return;
  }
  return run('Sending…', async signal => {
    await request(pairing, '/v1/clipboard', { kind: 'text', text }, signal);
    say('Sent to the Windows clipboard.');
  });
}

function decodeQR(image, width, height, maxSize, crop = false) {
  const w = crop ? Math.round(width * .65) : width;
  const h = crop ? Math.round(height * .65) : height;
  const scale = Math.min(1, maxSize / Math.max(w, h));
  qrCanvas.width = Math.max(1, Math.round(w * scale));
  qrCanvas.height = Math.max(1, Math.round(h * scale));
  qrContext.drawImage(image, (width - w) / 2, (height - h) / 2, w, h, 0, 0, qrCanvas.width, qrCanvas.height);
  const pixels = qrContext.getImageData(0, 0, qrCanvas.width, qrCanvas.height);
  return window.jsQR(pixels.data, qrCanvas.width, qrCanvas.height)?.data;
}

function stopCamera() {
  if (!camera) return;
  clearInterval(camera.frames);
  clearTimeout(camera.timeout);
  camera.stream?.getTracks().forEach(track => track.stop());
  camera = undefined;
  cameraView.srcObject = null;
  byId('camera').hidden = true;
}

function cameraError(session, message) {
  if (camera !== session) return;
  stopCamera();
  say(message, true);
}

async function startCamera() {
  if (camera || active) return;
  const session = {};
  camera = session;
  byId('camera').hidden = false;
  say('Opening the camera…');
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
    if (camera !== session) {
      stream.getTracks().forEach(track => track.stop());
      return;
    }
    session.stream = stream;
    for (const track of stream.getVideoTracks()) {
      track.addEventListener('ended', () => cameraError(session, 'The camera stopped. Try Scan again or choose a QR photo.'), { once: true });
    }
    cameraView.srcObject = stream;
    await cameraView.play();
    if (camera !== session) return;
    say('');
    session.frames = setInterval(() => {
      if (cameraView.readyState < 2 || !cameraView.videoWidth || !cameraView.videoHeight) return;
      try {
        const code = decodeQR(cameraView, cameraView.videoWidth, cameraView.videoHeight, 1100);
        if (code && code.includes('#pair=')) pair(code);
        else if (code?.startsWith('clipbridge://')) say('Open iPhone web pairing on Windows and scan the QR code in that window.');
      } catch {
        cameraError(session, 'The camera image could not be read. Choose a QR photo or use the pairing link.');
      }
    }, 250);
    session.timeout = setTimeout(() => cameraError(session, 'No ClipBridge web QR found. Move closer to the PC’s code or choose a QR photo.'), 30000);
  } catch {
    cameraError(session, 'Could not open the camera. Check camera access, choose a QR photo, or use the pairing link.');
  }
}

async function scanPhoto(file) {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    await new Promise((resolve, reject) => {
      image.onload = resolve;
      image.onerror = reject;
      image.src = url;
    });
    return decodeQR(image, image.naturalWidth, image.naturalHeight, 1920)
      ?? decodeQR(image, image.naturalWidth, image.naturalHeight, 1920, true);
  } finally {
    URL.revokeObjectURL(url);
  }
}

byId('scan').addEventListener('click', startCamera);
byId('stop-scan').addEventListener('click', () => { stopCamera(); say(''); });
byId('choose-photo').addEventListener('click', () => { stopCamera(); qrPhoto.click(); });
qrPhoto.addEventListener('change', async () => {
  const file = qrPhoto.files[0];
  if (!file) return;
  stopCamera();
  say('Reading the QR photo…');
  try {
    const code = await scanPhoto(file);
    if (code) await pair(code);
    else say('No QR code found in the photo. Try a closer photo or use the pairing link.', true);
  } catch {
    say('Could not open the photo. Choose another image or use the pairing link.', true);
  } finally {
    qrPhoto.value = '';
  }
});

byId('pair-form').addEventListener('submit', event => {
  event.preventDefault();
  const input = byId('pair-link');
  const link = input.value;
  input.value = '';
  pair(link);
});

byId('forget').addEventListener('click', () => {
  try { localStorage.removeItem(storageKey); } catch { /* Pairing may only exist in memory. */ }
  pairing = null;
  clearReceived();
  draft.value = '';
  render();
  say('Pairing removed from this device.');
});

byId('send').addEventListener('click', () => send(draft.value));
byId('paste').addEventListener('click', async () => {
  try {
    if (navigator.clipboard.read) {
      const items = await navigator.clipboard.read();
      const image = items.find(item => item.types.includes('image/png'));
      if (image) return await upload([new File([await image.getType('image/png')], 'Pasted photo.png', { type: 'image/png' })]);
      const text = items.find(item => item.types.includes('text/plain'));
      if (text) return await send(await (await text.getType('text/plain')).text());
    }
    await send(await navigator.clipboard.readText());
  }
  catch { say('Paste into the text field, then tap Send to PC.', true); }
});

draft.addEventListener('paste', event => {
  const files = Array.from(event.clipboardData?.files || []);
  if (files.length && !active) { event.preventDefault(); upload(files); }
});

byId('get').addEventListener('click', () => download(false));

byId('copy').addEventListener('click', async () => {
  try {
    await navigator.clipboard.writeText(incoming.value);
    say('Copied to your clipboard.');
  } catch {
    incoming.select();
    say('Select the text and use the Copy menu.', true);
  }
});

window.addEventListener('pagehide', () => { stopCamera(); active?.abort(); });
byId('install').hidden = window.matchMedia('(display-mode: standalone)').matches || navigator.standalone === true;
render();
if (location.hash.startsWith('#pair=')) {
  const link = location.href;
  history.replaceState(null, '', location.pathname);
  pair(link);
}
