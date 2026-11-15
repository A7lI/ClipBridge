import { PhoneSession, readInvitation } from './phone-transport.mjs';
import { validateFiles } from './transport.mjs';
import { showFiles, clearFiles } from './files.mjs';
import { drawQR, readQR, readQRPhoto } from './phone-qr.mjs';
import { prepareOffline } from './offline.mjs';

const byId = id => document.getElementById(id);
let session, activeSend, selected = [], camera, preparing = false, hasReceived = false;
function say(message, error = false) {
  const status = byId('status'); status.textContent = message; status.hidden = !message; status.toggleAttribute('data-error', error);
}
function render() {
  const connected = Boolean(session?.ready);
  byId('phone-transfers').hidden = !connected && !hasReceived;
  byId('phone-connected').hidden = !connected;
  byId('phone-setup').hidden = connected;
  byId('disconnect-phone').hidden = !session;
  for (const id of ['create-phone', 'scan-phone', 'choose-phone-qr', 'join-phone-button', 'phone-mode']) byId(id).disabled = preparing;
  for (const id of ['phone-send-text', 'phone-paste', 'phone-files', 'phone-photos']) byId(id).disabled = Boolean(activeSend) || !connected;
  byId('phone-send-files').disabled = Boolean(activeSend) || !connected || !selected.length;
  byId('phone-cancel-send').hidden = !activeSend;
}
function createSession() {
  stopCamera(); session?.close();
  const next = new PhoneSession(); session = next;
  byId('invitation').hidden = true;
  byId('phone-received-text').hidden = true; clearFiles();
  hasReceived = false;
  byId('phone-send-status').textContent = ''; byId('phone-receive-status').textContent = '';
  next.addEventListener('connected', ({ detail }) => {
    if (session !== next) return;
    byId('phone-code').textContent = detail.code;
    byId('invitation-link').value = '';
    byId('invitation').hidden = true;
    say('Connected. Check the code on both phones before sharing.'); render();
  });
  next.addEventListener('disconnected', ({ detail }) => {
    if (session !== next) return;
    activeSend?.abort(new Error(detail.message));
    byId('phone-offer').hidden = true;
    byId('phone-receive-progress').hidden = true;
    session = undefined; byId('invitation').hidden = true;
    // Received files stay visible after disconnecting until another session starts.
    byId('phone-transfers').hidden = false;
    byId('phone-connected').hidden = true; byId('phone-setup').hidden = false;
    byId('disconnect-phone').hidden = true;
    say(detail.message, true);
  });
  next.addEventListener('offer', ({ detail }) => {
    byId('phone-offer-description').textContent = detail.kind === 'text' ? `Text from the other phone: ${detail.text.slice(0, 180)}` : `${detail.files.length} file(s) · ${(detail.files.reduce((sum, f) => sum + f.size, 0) / 1024 / 1024).toFixed(1)} MB\n${detail.files.map(f => f.name).join(', ')}`;
    byId('phone-offer').hidden = false;
    byId('phone-receive-status').textContent = hasReceived ? 'Save previous files first. Accepting another file transfer replaces the previous received file list.' : 'Waiting for you to accept or decline.';
  });
  next.addEventListener('waiting', () => { byId('phone-send-status').textContent = 'Waiting for the other phone to accept…'; });
  next.addEventListener('progress', ({ detail }) => {
    const progress = byId(`phone-${detail.direction}-progress`);
    progress.hidden = false; progress.value = detail.total ? detail.done * 100 / detail.total : 100;
    byId(`phone-${detail.direction}-status`).textContent = `${detail.direction === 'send' ? 'Sending' : 'Receiving'} ${(detail.done / 1024 / 1024).toFixed(1)} of ${(detail.total / 1024 / 1024).toFixed(1)} MB`;
  });
  next.addEventListener('received', ({ detail }) => {
    hasReceived = true;
    byId('phone-offer').hidden = true; byId('phone-receive-progress').hidden = true;
    if (detail.kind === 'text') {
      byId('phone-incoming').value = detail.text; byId('phone-received-text').hidden = false;
      byId('phone-receive-status').textContent = 'Text received. Tap Copy text to paste it in another app.';
    } else {
      showFiles(detail.files, say);
      byId('phone-receive-status').textContent = 'Files received. Save or share them before closing this screen.';
    }
  });
  next.addEventListener('cancelled', () => {
    byId('phone-offer').hidden = true; byId('phone-receive-progress').hidden = true;
    byId('phone-receive-status').textContent = 'The sender cancelled. No partial files were saved.';
  });
  render(); return next;
}
async function prepare(operation) {
  if (preparing || activeSend) return;
  preparing = true; render();
  try { await operation(); }
  catch (error) { session?.close(error.message || 'Could not connect. Try a new invitation.'); say(error.message, true); }
  finally { preparing = false; render(); }
}
function showInvitation(link, answer = false) {
  byId('invitation-title').textContent = answer ? 'Return QR' : 'Your private invitation';
  byId('invitation-link').value = link;
  byId('invitation-note').textContent = answer ? 'Ask the first phone to scan this return QR. Keep this screen open.' : byId('phone-mode').value === 'offline' ? 'The second phone scans this QR, then shows a return QR. Scan that return QR here to finish connecting.' : 'Have the other phone scan this QR, or send it the private link. Keep this screen open.';
  drawQR(byId('invitation-qr'), link);
  if (byId('invitation-qr').hidden) byId('invitation-note').textContent += ' The code is too large for one QR; copy the pairing code instead.';
  byId('invitation').hidden = false;
}
byId('create-phone').addEventListener('click', () => prepare(async () => {
  const next = createSession(); say('Creating an invitation…');
  const link = byId('phone-mode').value === 'offline' ? await next.offline() : await next.online('host');
  if (session !== next || next.closed) return;
  showInvitation(link); say('Invitation ready. Connect the other phone.');
}));
async function join(value) {
  stopCamera();
  return prepare(async () => {
    const invitation = await readInvitation(value);
    if (invitation.kind === 'answer') {
      if (!session) throw new Error('Create an offline invitation on this phone before scanning its return QR.');
      say('Connecting locally…'); await session.answer(invitation); return;
    }
    const next = createSession();
    byId('phone-mode').value = invitation.kind === 'offer' ? 'offline' : 'online'; updateMode();
    say('Connecting to the other phone…');
    if (invitation.kind === 'offer') showInvitation(await next.offline(invitation), true);
    else await next.online('guest', invitation.secret);
  });
}
byId('join-phone').addEventListener('submit', event => { event.preventDefault(); const value = byId('join-phone-link').value; byId('join-phone-link').value = ''; join(value); });
function updateMode() {
  byId('mode-note').textContent = byId('phone-mode').value === 'offline' ? 'No internet is needed after this page is saved for offline use. Both phones must be on the same Wi-Fi or hotspot. Pairing uses an invitation QR and a return QR.' : 'Both phones need internet. Transfers are encrypted between the phones and relayed without saving files on the server.';
}
byId('phone-mode').addEventListener('change', updateMode);
byId('copy-invitation').addEventListener('click', async () => {
  try { await navigator.clipboard.writeText(byId('invitation-link').value); say('Invitation copied. Share it only with the intended phone.'); }
  catch { byId('invitation-link').select(); say('Select the invitation and use Copy.'); }
});
byId('share-invitation').hidden = !navigator.share;
byId('share-invitation').addEventListener('click', async () => {
  try { await navigator.share({ title: 'ClipBridge phone invitation', text: 'Open this invitation in ClipBridge. Keep both phones open.', url: byId('invitation-link').value }); }
  catch (error) { if (error.name !== 'AbortError') say('Use Copy invitation instead.', true); }
});
async function send(item) {
  if (activeSend || !session?.ready) return;
  const controller = new AbortController(); activeSend = controller; render();
  const timeout = setTimeout(() => controller.abort(new Error('Transfer timed out. Keep both phones open and try again.')), 30 * 60 * 1000);
  try { await session.send(item, controller.signal); byId('phone-send-status').textContent = 'Received by the other phone. Ask them to save any files before closing.'; }
  catch (error) { byId('phone-send-status').textContent = error.message || 'Could not send. Check the other phone before retrying.'; }
  finally { clearTimeout(timeout); activeSend = undefined; byId('phone-send-progress').hidden = true; render(); }
}
byId('phone-send-text').addEventListener('click', () => send({ kind: 'text', text: byId('phone-draft').value }));
byId('phone-send-files').addEventListener('click', () => send({ kind: 'files', files: selected }));
for (const id of ['phone-files', 'phone-photos']) byId(id).addEventListener('change', event => {
  try { const files = Array.from(event.target.files); validateFiles(files); selected = files; byId('phone-selection').textContent = files.map(f => f.name).join(', '); }
  catch (error) { selected = []; byId('phone-selection').textContent = ''; say(error.message, true); }
  render();
});
byId('phone-draft').addEventListener('paste', event => {
  const files = Array.from(event.clipboardData?.files || []);
  if (files.length) { event.preventDefault(); send({ kind: 'files', files }); }
});
byId('phone-paste').addEventListener('click', async () => {
  try {
    if (navigator.clipboard.read) {
      const values = await navigator.clipboard.read(); const image = values.find(v => v.types.includes('image/png'));
      if (image) return send({ kind: 'files', files: [new File([await image.getType('image/png')], 'Pasted photo.png', { type: 'image/png' })] });
    }
    send({ kind: 'text', text: await navigator.clipboard.readText() });
  } catch { say('Paste into the text field or choose a photo or file.', true); }
});
byId('phone-cancel-send').addEventListener('click', () => activeSend?.abort(new Error('Transfer cancelled. Check the other phone before retrying.')));
for (const [id, accept] of [['phone-accept', true], ['phone-decline', false]]) byId(id).addEventListener('click', async () => {
  byId('phone-offer').hidden = true;
  try { await session?.accept(accept); if (!accept) byId('phone-receive-status').textContent = 'Transfer declined.'; }
  catch (error) { say(error.message, true); }
});
byId('phone-copy-text').addEventListener('click', async () => {
  try {
    if (window.ClipBridgePhone?.copyText) window.ClipBridgePhone.copyText(byId('phone-incoming').value);
    else await navigator.clipboard.writeText(byId('phone-incoming').value);
    say('Text copied.');
  } catch { byId('phone-incoming').select(); say('Select the text and use Copy.'); }
});
byId('disconnect-phone').addEventListener('click', () => { stopCamera(); session?.close(); render(); });

function stopCamera() {
  if (!camera) return;
  clearInterval(camera.timer); clearTimeout(camera.timeout); camera.stream?.getTracks().forEach(t => t.stop()); camera = undefined;
  byId('phone-camera').hidden = true; byId('phone-camera-view').srcObject = null;
}
byId('close-phone-camera').addEventListener('click', stopCamera);
byId('scan-phone').addEventListener('click', async () => {
  if (camera) return;
  const scan = {}; camera = scan;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } }, audio: false });
    if (camera !== scan) { stream.getTracks().forEach(t => t.stop()); return; }
    scan.stream = stream;
    const video = byId('phone-camera-view'); video.srcObject = stream; byId('phone-camera').hidden = false; await video.play();
    scan.timer = setInterval(() => {
      if (video.readyState < 2) return;
      try { const value = readQR(video, video.videoWidth, video.videoHeight); if (value) join(value); } catch { /* Wait for a clear frame. */ }
    }, 250);
    scan.timeout = setTimeout(() => { stopCamera(); say('No QR found. Move closer, choose a QR photo, or paste the invitation.', true); }, 45000);
  } catch { stopCamera(); say('Camera unavailable. Allow camera access, choose a QR photo, or paste the invitation.', true); }
});
byId('choose-phone-qr').addEventListener('click', () => { stopCamera(); byId('phone-qr-photo').click(); });
byId('phone-qr-photo').addEventListener('change', async event => {
  const file = event.target.files[0]; if (!file) return;
  try { const value = await readQRPhoto(file); if (!value) throw new Error('No QR found. Choose a closer photo or paste the invitation.'); await join(value); }
  catch (error) { say(error.message, true); }
  finally { event.target.value = ''; }
});
window.addEventListener('pagehide', () => { stopCamera(); activeSend?.abort(); session?.close(); });
prepareOffline(message => { byId('offline-ready').textContent = message; });
render();
function useInvitation() {
  if (!location.hash) return;
  const value = location.href; history.replaceState(null, '', location.pathname); join(value);
}
window.addEventListener('hashchange', useInvitation);
useInvitation();
