export const mobileRoute = /^\/mobile\/([a-f0-9]{64})\/(host|guest)$/;
const lifetime = 2 * 60 * 60 * 1000;

export async function openMobile(context, request) {
  const role = mobileRoute.exec(new URL(request.url).pathname)[2];
  const other = role === 'host' ? 'guest' : 'host';
  if (context.getWebSockets(role).length) return new Response('This phone is already connected', { status: 409 });
  if (role === 'guest' && !context.getWebSockets('host').length) return new Response('Invitation expired. Create a new one.', { status: 410 });
  const [client, socket] = Object.values(new WebSocketPair());
  context.acceptWebSocket(socket, [role]);
  socket.serializeAttachment({ mobile: true, role, expires: Date.now() + lifetime, tokens: 256, updated: Date.now() });
  await context.storage.setAlarm(Date.now() + lifetime);
  const peer = context.getWebSockets(other)[0];
  if (peer) {
    socket.send(JSON.stringify({ event: 'ready' }));
    peer.send(JSON.stringify({ event: 'ready' }));
  }
  return new Response(null, { status: 101, webSocket: client });
}

export function relayMobile(context, socket, raw) {
  const info = socket.deserializeAttachment();
  if (!(raw instanceof ArrayBuffer) || raw.byteLength < 32 || raw.byteLength > 66 * 1024) {
    socket.close(1009, 'Invalid transfer frame');
    return;
  }
  const now = Date.now();
  info.tokens = Math.min(256, info.tokens + (now - info.updated) * .128) - 1;
  info.updated = now;
  if (now > info.expires || info.tokens < 0) {
    socket.close(1008, 'Session limit reached. Pair again.');
    return;
  }
  socket.serializeAttachment(info);
  const other = context.getWebSockets(info.role === 'host' ? 'guest' : 'host')[0];
  if (other) other.send(raw);
  else socket.close(4004, 'The other phone disconnected');
}

export function closeMobile(context, socket) {
  const role = socket.deserializeAttachment()?.role;
  for (const peer of context.getWebSockets(role === 'host' ? 'guest' : 'host')) {
    peer.close(4004, 'The other phone disconnected');
  }
}
