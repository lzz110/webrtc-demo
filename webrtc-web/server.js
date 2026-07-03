/**
 * WebRTC 信令服务器
 * 同一 room 内的两端（Web / Mac）通过 WebSocket 交换 SDP 与 ICE
 */
const express = require('express');
const { WebSocketServer } = require('ws');
const path = require('path');

const PORT = process.env.PORT || 8080;
const app = express();

app.use(express.static(path.join(__dirname, 'public')));
const server = app.listen(PORT, () => {
  console.log(`http://localhost:${PORT}`);
});

const wss = new WebSocketServer({ server, path: '/ws' });

const rooms = new Map();

function ensureRoom(roomId) {
  if (!rooms.has(roomId)) rooms.set(roomId, new Set());
  return rooms.get(roomId);
}

wss.on('connection', (ws, req) => {
  let roomId = null;
  let peerId = null;

  ws.on('message', (raw) => {
    try {
      const msg = JSON.parse(raw.toString());
      if (msg.type === 'join') {
        roomId = msg.roomId || 'default';
        peerId = msg.peerId || `peer_${Date.now()}`;
        const room = ensureRoom(roomId);
        room.add(ws);
        ws.peerId = peerId;
        ws.roomId = roomId;
        ws.send(JSON.stringify({ type: 'joined', roomId, peerId }));
        broadcastToRoom(roomId, ws, { type: 'peers', count: room.size });
        return;
      }
      if (msg.type === 'signal' && roomId) {
        broadcastToRoom(roomId, ws, { type: 'signal', from: peerId, payload: msg.payload });
        return;
      }
    } catch (e) {
      ws.send(JSON.stringify({ type: 'error', message: e.message }));
    }
  });

  ws.on('close', () => {
    if (roomId) {
      const room = ensureRoom(roomId);
      room.delete(ws);
      if (room.size === 0) rooms.delete(roomId);
      else broadcastToRoom(roomId, null, { type: 'peers', count: room.size });
    }
  });
});

function broadcastToRoom(roomId, excludeWs, data) {
  const room = ensureRoom(roomId);
  const payload = JSON.stringify(data);
  room.forEach((w) => {
    if (w !== excludeWs && w.readyState === 1) w.send(payload);
  });
}
