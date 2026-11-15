import { mobileRoute, openMobile, relayMobile, closeMobile } from './mobile-relay.mjs';

const roomRoute = /^\/signal\/([a-f0-9]{64})\/(pc|phone\/([a-f0-9]{32}))$/;
const maxMessage = 49152;

export default {
  fetch(request, env) {
    const url = new URL(request.url);
    const mobile = mobileRoute.exec(url.pathname);
    if (mobile) {
      if (request.method !== 'GET' || request.headers.get('Upgrade')?.toLowerCase() !== 'websocket') return new Response('WebSocket required', { status: 426 });
      if (request.headers.get('Origin') !== url.origin) return new Response('Origin denied', { status: 403 });
      return env.PAIRING_ROOMS.getByName('mobile:' + mobile[1]).fetch(request);
    }
    const match = roomRoute.exec(url.pathname);
    if (!match) return new Response('Not found', { status: 404 });
    if (request.method !== 'GET' || request.headers.get('Upgrade')?.toLowerCase() !== 'websocket') {
      return new Response('WebSocket required', { status: 426 });
    }
    const origin = request.headers.get('Origin');
    if (match[3] ? origin !== url.origin : origin !== null) {
      return new Response('Origin denied', { status: 403 });
    }
    return env.PAIRING_ROOMS.getByName(match[1]).fetch(request);
  }
};

export class PairingRoom {
  constructor(context) {
    this.context = context;
  }

  fetch(request) {
    if (mobileRoute.test(new URL(request.url).pathname)) return openMobile(this.context, request);
    const [, , , peer] = roomRoute.exec(new URL(request.url).pathname);
    const [client, socket] = Object.values(new WebSocketPair());
    const isPC = !peer;
    const desktop = this.context.getWebSockets('pc');
    if (isPC && desktop.length) return new Response('PC already connected', { status: 409 });
    const busy = !isPC && (this.context.getWebSockets('phone').length >= 4 || this.context.getWebSockets(peer).length);
    this.context.acceptWebSocket(socket, isPC ? ['pc'] : ['phone', peer]);
    socket.serializeAttachment({ peer });
    if (!isPC && !desktop.length) socket.close(4004, 'PC is offline');
    else if (busy) socket.close(4008, 'PC is busy');
    return new Response(null, { status: 101, webSocket: client });
  }

  webSocketMessage(socket, raw) {
    if (socket.deserializeAttachment()?.mobile) return relayMobile(this.context, socket, raw);
    if (typeof raw !== 'string' || raw.length > maxMessage) {
      socket.close(1009, 'Invalid message size');
      return;
    }
    try {
      const { peer, offered } = socket.deserializeAttachment();
      const message = JSON.parse(raw);
      if (peer) {
        if (offered) return;
        const desktop = this.context.getWebSockets('pc')[0];
        if (!desktop) return socket.close(4004, 'PC is offline');
        const offer = JSON.stringify({ peer, signal: message });
        if (offer.length > maxMessage) return socket.close(1009, 'Invalid message size');
        socket.serializeAttachment({ peer, offered: true });
        desktop.send(offer);
      } else if (typeof message.peer === 'string' && /^[a-f0-9]{32}$/.test(message.peer)) {
        this.context.getWebSockets(message.peer)[0]?.send(JSON.stringify(message.signal));
      }
    } catch {
      socket.close(1007, 'Invalid signaling message');
    }
  }

  webSocketClose(socket) {
    if (socket.deserializeAttachment()?.mobile) return closeMobile(this.context, socket);
    if (!socket.deserializeAttachment()?.peer) {
      for (const phone of this.context.getWebSockets('phone')) phone.close(4004, 'PC disconnected');
    }
  }

  webSocketError(socket) {
    socket.close(1011, 'Pairing connection ended');
  }

  alarm() {
    for (const socket of this.context.getWebSockets()) {
      const info = socket.deserializeAttachment();
      if (info?.mobile && Date.now() >= info.expires) socket.close(1008, 'Session expired. Pair again.');
    }
  }
}
