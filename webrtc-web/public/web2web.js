/**
 * Web ↔ Web 互通测试：仅两个浏览器标签页，便于排查 DataChannel / 信令问题
 * 信令统一用显式序列化：{ type, sdp } / { type, candidate: { candidate, sdpMLineIndex, sdpMid } }
 */

const roomIdEl = document.getElementById('roomId');
const btnJoinOrLeave = document.getElementById('btnJoinOrLeave');
const signalingStatus = document.getElementById('signalingStatus');
const myPeerIdEl = document.getElementById('myPeerId');
const peersCount = document.getElementById('peersCount');
const btnStartCall = document.getElementById('btnStartCall');
const callStatus = document.getElementById('callStatus');
const localLevelEl = document.getElementById('localLevel');
const remoteLevelEl = document.getElementById('remoteLevel');
const remoteAudio = document.getElementById('remoteAudio');
const messageInput = document.getElementById('messageInput');
const btnSend = document.getElementById('btnSend');
const messageList = document.getElementById('messageList');
const fileInput = document.getElementById('fileInput');
const btnSendFile = document.getElementById('btnSendFile');
const debugLogEl = document.getElementById('debugLog');

let ws = null;
let pc = null;
let localStream = null;
let dataChannel = null;
let localAnalyser = null;
let remoteAnalyser = null;
let animationId = null;
let currentRoomId = null;
let myPeerId = null;
let messageItems = [];

const config = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

function debug(msg, isRecv = false) {
  const last = debugLogEl.lastElementChild;
  if (last) {
    const t = last.textContent;
    const i = t.indexOf('] ');
    if (i !== -1 && t.slice(i + 2) === msg) return;
  }
  const line = document.createElement('div');
  line.className = isRecv ? 'recv' : '';
  line.textContent = `[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${msg}`;
  debugLogEl.appendChild(line);
  debugLogEl.scrollTop = debugLogEl.scrollHeight;
  console.log(msg);
}

function debugErr(msg) {
  const line = document.createElement('div');
  line.className = 'err';
  line.textContent = `[${new Date().toLocaleTimeString('zh-CN', { hour12: false })}] ${msg}`;
  debugLogEl.appendChild(line);
  debugLogEl.scrollTop = debugLogEl.scrollHeight;
  console.error(msg);
}

function getWsUrl() {
  const base = location.origin.replace(/^http/, 'ws');
  return `${base}/ws`;
}

function updateSignalingStatus(text, isError = false) {
  signalingStatus.textContent = text;
  signalingStatus.className = 'status' + (isError ? ' error' : '');
}

function leaveRoom() {
  const room = currentRoomId ?? 'demo';
  if (ws && ws.readyState === WebSocket.OPEN) ws.close();
  ws = null;
  currentRoomId = null;
  stopLevelMeters();
  btnJoinOrLeave.textContent = '加入房间';
  roomIdEl.disabled = false;
  updateSignalingStatus('已离开房间 ' + room);
  myPeerId = null;
  myPeerIdEl.textContent = '本端 peerId: —';
  peersCount.textContent = '';
  btnStartCall.disabled = true;
  debug('已离开房间 ' + room);
}

btnJoinOrLeave.onclick = async () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    leaveRoom();
    return;
  }
  const roomId = roomIdEl.value.trim() || 'demo';
  roomIdEl.disabled = true;
  updateSignalingStatus('连接中…');
  try {
    ws = new WebSocket(getWsUrl());
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'join', roomId, peerId: 'web_' + Date.now() }));
    };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'joined') {
          currentRoomId = msg.roomId;
          myPeerId = msg.peerId || null;
          myPeerIdEl.textContent = '本端 peerId: ' + (myPeerId || '—');
          btnJoinOrLeave.textContent = '离开房间';
          updateSignalingStatus('已加入房间: ' + msg.roomId);
          btnStartCall.disabled = false;
          debug('已加入房间: ' + msg.roomId + ', peerId: ' + (myPeerId || '—'));
        } else if (msg.type === 'peers') {
          peersCount.textContent = '当前房间人数: ' + msg.count;
        } else if (msg.type === 'signal') {
          debug('收到 signal: ' + (msg.payload?.type || '?'), true);
          handleSignal(msg.payload);
        } else if (msg.type === 'error') {
          updateSignalingStatus(msg.message || '错误', true);
          debugErr(msg.message);
        }
      } catch (err) {
        debugErr(String(err));
      }
    };
    ws.onclose = () => {
      if (currentRoomId != null) {
        const room = currentRoomId;
        currentRoomId = null;
        updateSignalingStatus('已离开房间 ' + room);
      } else {
        updateSignalingStatus('已断开');
      }
      btnJoinOrLeave.textContent = '加入房间';
      roomIdEl.disabled = false;
      peersCount.textContent = '';
      btnStartCall.disabled = true;
    };
    ws.onerror = () => updateSignalingStatus('WebSocket 错误', true);
  } catch (err) {
    roomIdEl.disabled = false;
    updateSignalingStatus('连接失败: ' + err.message, true);
    debugErr(err.message);
  }
};

function sendSignal(payload) {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  ws.send(JSON.stringify({ type: 'signal', payload }));
  if (payload.type) debug('发送 signal: ' + payload.type);
}

function createPeerConnection() {
  if (pc) return pc;
  pc = new RTCPeerConnection(config);
  debug('已创建 RTCPeerConnection');

  pc.onicecandidate = (e) => {
    if (e.candidate) {
      const c = e.candidate;
      sendSignal({
        type: 'ice',
        candidate: {
          candidate: c.candidate,
          sdpMLineIndex: c.sdpMLineIndex,
          sdpMid: c.sdpMid ?? ''
        }
      });
    }
  };
  pc.oniceconnectionstatechange = () => {
    callStatus.textContent = pc.iceConnectionState;
    debug('ICE 状态: ' + pc.iceConnectionState);
    if (['disconnected', 'failed', 'closed'].includes(pc.iceConnectionState)) {
      stopLevelMeters();
    }
  };
  pc.ontrack = (e) => {
    if (e.streams && e.streams[0]) {
      remoteAudio.srcObject = e.streams[0];
      setupRemoteLevelMeter(e.streams[0]);
      debug('收到远端音轨');
    }
  };

  return pc;
}

async function handleSignal(payload) {
  if (!payload || typeof payload.type !== 'string') return;

  if (payload.type === 'offer') {
    if (!localStream) {
      try {
        callStatus.textContent = '收到 Offer，获取麦克风…';
        localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      } catch (e) {
        callStatus.textContent = '麦克风失败: ' + e.message;
        debugErr(e.message);
        return;
      }
    }
    createPeerConnection();
    pc.ondatachannel = (e) => {
      dataChannel = e.channel;
      setupDataChannel(dataChannel);
      messageInput.disabled = false;
      btnSend.disabled = false;
      debug('收到对端 DataChannel');
    };
    localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));
    setupLocalLevelMeter(localStream);

    const sdp = new RTCSessionDescription({ type: 'offer', sdp: payload.sdp });
    try {
      await pc.setRemoteDescription(sdp);
      debug('已 setRemoteDescription(offer)');
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      sendSignal({ type: 'answer', sdp: pc.localDescription.sdp });
      callStatus.textContent = '已回复 Answer';
      messageInput.disabled = false;
      btnSend.disabled = false;
    } catch (err) {
      callStatus.textContent = 'Error: ' + err.message;
      debugErr('handleSignal(offer): ' + err.message);
    }
    return;
  }

  if (!pc) return;

  if (payload.type === 'answer') {
    if (pc.signalingState !== 'have-local-offer') {
      debug('忽略 answer：当前状态 ' + pc.signalingState);
      return;
    }
    try {
      const sdp = new RTCSessionDescription({ type: 'answer', sdp: payload.sdp });
      await pc.setRemoteDescription(sdp);
      callStatus.textContent = '已连接';
      debug('已 setRemoteDescription(answer)，连接成功');
    } catch (err) {
      callStatus.textContent = 'Error: ' + err.message;
      debugErr('setRemoteDescription(answer): ' + err.message);
    }
    return;
  }

  if (payload.type === 'ice' && payload.candidate) {
    try {
      await pc.addIceCandidate(new RTCIceCandidate(payload.candidate));
    } catch (err) {
      debugErr('addIceCandidate: ' + err.message);
    }
  }
}

async function startCall() {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  try {
    callStatus.textContent = '获取麦克风…';
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    createPeerConnection();

    localStream.getTracks().forEach((t) => pc.addTrack(t, localStream));
    setupLocalLevelMeter(localStream);

    dataChannel = pc.createDataChannel('msg', { ordered: true });
    setupDataChannel(dataChannel);
    messageInput.disabled = false;
    btnSend.disabled = false;
    debug('已创建 DataChannel(msg)');

    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    sendSignal({ type: 'offer', sdp: pc.localDescription.sdp });
    callStatus.textContent = '已发送 Offer，等待 Answer…';
  } catch (err) {
    callStatus.textContent = 'Error: ' + err.message;
    debugErr('startCall: ' + err.message);
  }
}

function setupDataChannel(ch) {
  ch.onopen = () => {
    addMessageToList({ type: 'system', text: '（DataChannel 已连接）' });
    debug('DataChannel 已打开');
    messageInput.disabled = false;
    btnSend.disabled = false;
    if (btnSendFile) btnSendFile.disabled = false;
  };
  ch.onclose = () => {
    addMessageToList({ type: 'system', text: '（DataChannel 已关闭）' });
    debug('DataChannel 已关闭');
    if (btnSendFile) btnSendFile.disabled = true;
  };
  ch.onmessage = (e) => {
    debug('收到 DataChannel 消息: ' + (e.data?.length ?? 0) + ' 字节', true);
    handleReceivedData(e.data);
  };
}

function handleReceivedData(raw) {
  try {
    const obj = typeof raw === 'string' ? JSON.parse(raw) : JSON.parse(new TextDecoder().decode(raw));
    if (obj.type === 'msg' && obj.id != null && obj.text != null) {
      addMessageToList({ type: 'received', text: obj.text });
      sendRaw(JSON.stringify({ type: 'ack', id: obj.id }));
      return;
    }
    if (obj.type === 'file' && obj.id != null && obj.name && obj.data) {
      const b64 = obj.data;
      const mime = obj.mime || 'application/octet-stream';
      const size = obj.size || 0;
      const byteChars = atob(b64);
      const buf = new Uint8Array(byteChars.length);
      for (let i = 0; i < byteChars.length; i++) buf[i] = byteChars.charCodeAt(i);
      const blob = new Blob([buf], { type: mime });
      const url = URL.createObjectURL(blob);
      const label = `[文件] ${obj.name} (${formatFileSize(size)})`;
      addMessageToList({ type: 'received', text: label, isFile: true, fileName: obj.name, fileUrl: url });
      sendRaw(JSON.stringify({ type: 'ack', id: obj.id }));
      return;
    }
    if (obj.type === 'ack' && obj.id != null) {
      setMessageDelivered(obj.id);
      return;
    }
  } catch (_) {}
  addMessageToList({ type: 'received', text: typeof raw === 'string' ? raw : new TextDecoder().decode(raw) });
}

function sendRaw(str) {
  if (dataChannel && dataChannel.readyState === 'open') dataChannel.send(str);
}

function setMessageDelivered(msgId) {
  const item = messageItems.find((m) => m.id === msgId);
  if (item) item.delivered = true;
  renderMessageList();
}

function addMessageToList(entry) {
  const time = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  const id = entry.id ?? (entry.type === 'sent' ? 's_' + Date.now() + '_' + Math.random().toString(36).slice(2) : null);
  messageItems.push({
    id,
    time,
    text: entry.text,
    type: entry.type,
    delivered: entry.delivered ?? false,
    isFile: entry.isFile ?? false,
    fileName: entry.fileName ?? null,
    fileUrl: entry.fileUrl ?? null
  });
  renderMessageList();
}

function renderMessageList() {
  messageList.innerHTML = '';
  messageItems.forEach((m) => {
    const li = document.createElement('li');
    if (m.type === 'received') li.classList.add('received');
    if (m.type === 'sent') li.classList.add('sent');
    let label = '';
    let content = m.text;
    if (m.type === 'sent') {
      label = '我发送: ';
      if (m.delivered) content += ' ✓已送达';
    } else if (m.type === 'received') {
      label = '对方: ';
    }
    let inner = `<span class="time">${m.time}</span> <span class="msg-label">${label}</span>`;
    if (m.isFile && m.fileUrl) {
      inner += `<a href="${m.fileUrl}" download="${m.fileName || 'file'}">${content}</a>`;
    } else {
      inner += content;
    }
    li.innerHTML = inner;
    messageList.appendChild(li);
  });
  messageList.scrollTop = messageList.scrollHeight;
}

function arrayBufferToBase64(buf) {
  let binary = '';
  const bytes = new Uint8Array(buf);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}

function formatFileSize(size) {
  if (size >= 1024 * 1024) return (size / (1024 * 1024)).toFixed(1) + ' MB';
  if (size >= 1024) return (size / 1024).toFixed(1) + ' KB';
  return size + ' B';
}

function sendFile() {
  if (!dataChannel || dataChannel.readyState !== 'open') return;
  if (!fileInput || !fileInput.files || fileInput.files.length === 0) return;
  const file = fileInput.files[0];
  const reader = new FileReader();
  reader.onload = () => {
    const base64 = arrayBufferToBase64(reader.result);
    const msgId = 'f_' + Date.now() + '_' + Math.random().toString(36).slice(2);
    const label = `[文件] ${file.name} (${formatFileSize(file.size)})`;
    addMessageToList({ id: msgId, type: 'sent', text: label, delivered: false, isFile: true });
    const payload = {
      type: 'file',
      id: msgId,
      name: file.name,
      size: file.size,
      mime: file.type || 'application/octet-stream',
      data: base64
    };
    sendRaw(JSON.stringify(payload));
  };
  reader.readAsArrayBuffer(file);
}

btnStartCall.onclick = () => startCall();

function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || !dataChannel || dataChannel.readyState !== 'open') return;
  const msgId = 'w_' + Date.now() + '_' + Math.random().toString(36).slice(2);
  addMessageToList({ id: msgId, type: 'sent', text, delivered: false });
  sendRaw(JSON.stringify({ type: 'msg', id: msgId, text }));
  messageInput.value = '';
}

messageInput.onkeydown = (e) => { if (e.key === 'Enter') sendMessage(); };
btnSend.onclick = sendMessage;
if (btnSendFile) btnSendFile.onclick = sendFile;

function setupLocalLevelMeter(stream) {
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  localAnalyser = ctx.createAnalyser();
  localAnalyser.fftSize = 256;
  src.connect(localAnalyser);
  runLevelMeters();
}

function setupRemoteLevelMeter(stream) {
  const ctx = new AudioContext();
  const src = ctx.createMediaStreamSource(stream);
  remoteAnalyser = ctx.createAnalyser();
  remoteAnalyser.fftSize = 256;
  src.connect(remoteAnalyser);
  if (!animationId) runLevelMeters();
}

function runLevelMeters() {
  const data = new Uint8Array(128);
  function tick() {
    if (localAnalyser) {
      localAnalyser.getByteFrequencyData(data);
      const v = data.slice(0, 32).reduce((a, b) => a + b, 0) / 32 / 255;
      localLevelEl.style.width = Math.min(100, v * 150) + '%';
    }
    if (remoteAnalyser) {
      remoteAnalyser.getByteFrequencyData(data);
      const v = data.slice(0, 32).reduce((a, b) => a + b, 0) / 32 / 255;
      remoteLevelEl.style.width = Math.min(100, v * 150) + '%';
    }
    animationId = requestAnimationFrame(tick);
  }
  tick();
}

function stopLevelMeters() {
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
  localLevelEl.style.width = '0%';
  remoteLevelEl.style.width = '0%';
  if (localStream) {
    localStream.getTracks().forEach((t) => t.stop());
    localStream = null;
  }
  if (pc) {
    pc.close();
    pc = null;
  }
  dataChannel = null;
  messageInput.disabled = true;
  btnSend.disabled = true;
}
