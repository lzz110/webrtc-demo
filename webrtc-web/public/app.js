/**
 * WebRTC Web 端：仅接收 Mac 端音频，解码后走扬声器播放
 * - 信令：WebSocket 与 server.js 同端口 /ws
 * - 媒体：不发送任何 track，只通过 ontrack 接收远端音频
 * - 工作模式：始终作为被叫（answerer），由 Mac 端发起 Offer
 */

const roomIdEl = document.getElementById('roomId');
const btnJoinOrLeave = document.getElementById('btnJoinOrLeave');
const signalingStatus = document.getElementById('signalingStatus');
const peersCount = document.getElementById('peersCount');
const callStatus = document.getElementById('callStatus');
const remoteLevelEl = document.getElementById('remoteLevel');
const remoteAudio = document.getElementById('remoteAudio');
const netTupleEl = document.getElementById('netTuple');
const btnUnmute = document.getElementById('btnUnmute');

let ws = null;
let pc = null;
let remoteAnalyser = null;
let animationId = null;
let currentRoomId = null;
let netTupleTimer = null;

const config = { iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] };

// ---------- 信令 ----------
function getWsUrl() {
  const base = location.origin.replace(/^http/, 'ws');
  return `${base}/ws`;
}

function updateSignalingStatus(text, isError = false) {
  signalingStatus.textContent = text;
  signalingStatus.className = 'status' + (isError ? ' error' : '');
}

function leaveRoom() {
  const room = currentRoomId || 'demo';
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.close();
    ws = null;
  }
  currentRoomId = null;
  if (netTupleTimer) {
    clearInterval(netTupleTimer);
    netTupleTimer = null;
  }
  if (netTupleEl) netTupleEl.textContent = '网络端口对: —';
  btnJoinOrLeave.textContent = '加入房间';
  roomIdEl.disabled = false;
  updateSignalingStatus('已离开房间 ' + room);
  peersCount.textContent = '';
  cleanupPeer();
  console.log('已离开房间 ' + room);
}

function fmtAddrPort(c) {
  if (!c) return '—';
  const ip = c.ip || c.address || '';
  const port = c.port != null ? String(c.port) : '';
  return ip && port ? `${ip}:${port}` : '—';
}

async function updateNetTupleOnce() {
  if (!pc || pc.connectionState === 'closed') return;
  try {
    const stats = await pc.getStats();
    let selectedPair = null;
    stats.forEach((r) => {
      if (r.type === 'transport' && r.selectedCandidatePairId) {
        selectedPair = stats.get(r.selectedCandidatePairId) || null;
      }
    });
    if (!selectedPair) return;
    const local = stats.get(selectedPair.localCandidateId);
    const remote = stats.get(selectedPair.remoteCandidateId);
    const text = `网络端口对: ${fmtAddrPort(local)} ↔ ${fmtAddrPort(remote)} (protocol=${selectedPair.protocol || 'udp'})`;
    if (netTupleEl) netTupleEl.textContent = text;
  } catch {
    // ignore
  }
}

btnJoinOrLeave.onclick = () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    leaveRoom();
    return;
  }
  const roomId = roomIdEl.value.trim() || 'default';
  roomIdEl.disabled = true;
  const wsUrl = getWsUrl();
  updateSignalingStatus('连接中…');
  try {
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'join', roomId, peerId: 'web_recv_' + Date.now() }));
    };
    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'joined') {
          currentRoomId = msg.roomId;
          btnJoinOrLeave.textContent = '离开房间';
          updateSignalingStatus('已加入房间: ' + msg.roomId + '（等待 Mac 端发起 Offer）');
        } else if (msg.type === 'peers') {
          peersCount.textContent = '当前房间人数: ' + msg.count;
        } else if (msg.type === 'signal') {
          handleSignal(msg.payload);
        } else if (msg.type === 'error') {
          updateSignalingStatus(msg.message || '错误', true);
        }
      } catch (err) {
        console.error(err);
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
      cleanupPeer();
    };
    ws.onerror = () => updateSignalingStatus('WebSocket 错误', true);
  } catch (err) {
    roomIdEl.disabled = false;
    updateSignalingStatus('连接失败: ' + err.message, true);
  }
};

function sendSignal(payload) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'signal', payload }));
  }
}

// ---------- WebRTC（仅作为被叫，仅接收音频） ----------
function createPeerConnection() {
  if (pc) return pc;
  pc = new RTCPeerConnection(config);

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
    callStatus.textContent = 'ICE: ' + pc.iceConnectionState;
    if (pc.iceConnectionState === 'connected' || pc.iceConnectionState === 'completed') {
      updateNetTupleOnce();
      if (!netTupleTimer) netTupleTimer = setInterval(updateNetTupleOnce, 1500);
    }
    if (['disconnected', 'failed', 'closed'].includes(pc.iceConnectionState)) {
      stopRemoteMeter();
    }
  };

  pc.onconnectionstatechange = () => {
    if (pc.connectionState === 'failed' || pc.connectionState === 'closed' || pc.connectionState === 'disconnected') {
      if (netTupleTimer) {
        clearInterval(netTupleTimer);
        netTupleTimer = null;
      }
    }
  };

  // 关键：远端 track 到达 → 挂到 <audio> 元素，浏览器自动解码并送扬声器
  pc.ontrack = (e) => {
    console.log('ontrack:', e.track.kind, 'streams=', e.streams.length);
    if (e.track.kind !== 'audio') {
      // 我们只关心音频；视频 track 即使来了也忽略
      return;
    }
    const stream = e.streams && e.streams[0] ? e.streams[0] : new MediaStream([e.track]);
    remoteAudio.srcObject = stream;
    // 自动播放可能被浏览器策略拦截，捕获后弹一个按钮让用户点一下
    const playPromise = remoteAudio.play();
    if (playPromise && typeof playPromise.then === 'function') {
      playPromise.catch((err) => {
        console.warn('remoteAudio.play() 被拒绝:', err);
        if (btnUnmute) {
          btnUnmute.style.display = '';
          btnUnmute.onclick = () => {
            remoteAudio.play().then(() => { btnUnmute.style.display = 'none'; }).catch(() => {});
          };
        }
      });
    }
    setupRemoteLevelMeter(stream);
  };

  return pc;
}

async function handleSignal(payload) {
  if (payload.type === 'offer') {
    callStatus.textContent = '收到 Offer，准备 Answer…';
    createPeerConnection();
    try {
      await pc.setRemoteDescription(new RTCSessionDescription({ type: 'offer', sdp: payload.sdp }));
      // 不 addTrack：所有 m-line 的方向会变成 recvonly（或 inactive），即只接收
      const answer = await pc.createAnswer();
      await pc.setLocalDescription(answer);
      sendSignal({ type: 'answer', sdp: pc.localDescription.sdp });
      callStatus.textContent = '已回复 Answer，等待媒体流…';
    } catch (err) {
      callStatus.textContent = 'Error: ' + err.message;
      console.error(err);
    }
    return;
  }
  if (!pc) return;
  if (payload.type === 'ice' && payload.candidate) {
    pc.addIceCandidate(new RTCIceCandidate(payload.candidate)).catch((err) => {
      console.warn('addIceCandidate 失败:', err);
    });
  }
}

function cleanupPeer() {
  stopRemoteMeter();
  if (pc) {
    try { pc.close(); } catch {}
    pc = null;
  }
  if (remoteAudio) remoteAudio.srcObject = null;
  callStatus.textContent = '等待 Mac 端发起 Offer…';
}

// ---------- 远端音频电平条 ----------
function setupRemoteLevelMeter(stream) {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const src = ctx.createMediaStreamSource(stream);
    remoteAnalyser = ctx.createAnalyser();
    remoteAnalyser.fftSize = 256;
    src.connect(remoteAnalyser);
    if (!animationId) runMeter();
  } catch (err) {
    console.warn('AudioContext 创建失败:', err);
  }
}

function runMeter() {
  const data = new Uint8Array(128);
  function tick() {
    if (remoteAnalyser) {
      remoteAnalyser.getByteFrequencyData(data);
      const v = data.slice(0, 32).reduce((a, b) => a + b, 0) / 32 / 255;
      remoteLevelEl.style.width = Math.min(100, v * 150) + '%';
    }
    animationId = requestAnimationFrame(tick);
  }
  tick();
}

function stopRemoteMeter() {
  if (animationId) {
    cancelAnimationFrame(animationId);
    animationId = null;
  }
  remoteAnalyser = null;
  if (remoteLevelEl) remoteLevelEl.style.width = '0%';
}
