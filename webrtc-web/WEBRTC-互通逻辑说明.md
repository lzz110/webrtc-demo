# WebRTC 互通逻辑说明（基于 web2web 场景）

本文档基于 **Web ↔ Web** 双标签页实测流程，按时间顺序说明两端如何通过信令 + WebRTC 建立连接并收发消息/音频，便于理解整体互通场景。

---

## 一、角色与组件

| 角色 | 说明 |
|------|------|
| **信令服务器** | 本项目中 `server.js`，提供 HTTP 静态页 + WebSocket（`/ws`）。不参与媒体传输，只负责在「同一房间」内转发信令消息（谁发、谁收由房间决定）。 |
| **主叫（Offerer）** | 主动发起连接的一方。创建 `RTCPeerConnection`、添加本地音轨、创建 DataChannel、生成 **Offer（SDP）** 并经由信令发给对端。 |
| **被叫（Answerer）** | 被动接听的一方。收到 Offer 后创建 `RTCPeerConnection`、添加本地音轨、设置 **ondatachannel**、设置远端 SDP、生成 **Answer（SDP）** 并经由信令回给主叫。 |

**重要**：媒体和 DataChannel 数据**不经过信令服务器**，只在两端之间直连（P2P）。信令服务器只帮忙「交换 SDP 和 ICE」，让两端知道对方长什么样、怎么连。

---

## 二、互通整体流程（时间顺序）

```
标签页A（主叫）                    信令服务器                        标签页B（被叫）
      |                                  |                                  |
      |  1. 加入房间 roomId=demo         |                                  |
      |  ------------------------------> |                                  |
      |  <------------------------------  joined                            |
      |                                  |  2. 加入房间 roomId=demo         |
      |                                  |  <-------------------------------|
      |                                  |  ------------------------------->  joined
      |                                  |                                  |
      |  3. 点击「发起连接」             |                                  |
      |     - 获取麦克风 getUserMedia     |                                  |
      |     - 创建 RTCPeerConnection     |                                  |
      |     - addTrack(音频)             |                                  |
      |     - createDataChannel('msg')   |                                  |
      |     - createOffer()              |                                  |
      |     - setLocalDescription(offer) |                                  |
      |                                  |                                  |
      |  4. signal { type:'offer', sdp }  |                                  |
      |  ------------------------------> |  signal { type:'offer', sdp }     |
      |                                  |  ------------------------------->|
      |                                  |                                  |  5. 收到 Offer
      |                                  |                                  |     - getUserMedia
      |                                  |                                  |     - 创建 RTCPeerConnection
      |                                  |                                  |     - 设置 ondatachannel
      |                                  |                                  |     - addTrack(音频)
      |                                  |                                  |     - setRemoteDescription(offer)
      |                                  |                                  |     - createAnswer()
      |                                  |                                  |     - setLocalDescription(answer)
      |                                  |                                  |
      |                                  |  signal { type:'answer', sdp }     |
      |  <------------------------------ |  <-------------------------------|
      |  6. 收到 Answer                  |                                  |
      |     setRemoteDescription(answer) |                                  |
      |                                  |                                  |
      |  7. 双方交换 ICE 候选（多次）     |                                  |
      |  signal { type:'ice', candidate } |  signal { type:'ice', candidate } |
      |  <------------------------------> |  <------------------------------>|
      |     addIceCandidate(...)         |                                  |  addIceCandidate(...)
      |                                  |                                  |
      |  8. ICE 连接成功，连接状态变为 connected                            |
      |     DataChannel 触发 onopen       |                                  |  ondatachannel 收到通道
      |                                  |                                  |  DataChannel onopen
      |                                  |                                  |
      |  9. 之后：消息 / 音频 均通过 P2P 直连，不再经信令服务器              |
```

---

## 三、各阶段详解

### 1. 加入房间（信令层）

- 两端分别打开 `web2web.html`，房间号都填 **demo**，点击「加入房间」。
- 浏览器与 `ws://localhost:8080/ws` 建立 WebSocket，发送：
  ```json
  { "type": "join", "roomId": "demo", "peerId": "web_xxx" }
  ```
- 服务器把该连接加入房间 `demo`，并回复 `{ "type": "joined", "roomId": "demo" }`，同时向同房间所有连接广播当前人数 `{ "type": "peers", "count": 2 }`。
- **只有同一房间内的连接**才会收到对方后续发的 `signal`，因此房间号必须一致。

### 2. 主叫发起连接（仅一端点击「发起连接」）

主叫端依次执行：

1. **getUserMedia({ audio: true })**  
   获取本地麦克风，得到 `MediaStream`，用于发送语音。

2. **new RTCPeerConnection(config)**  
   创建对等连接对象，`config` 中至少包含 STUN：`{ iceServers: [{ urls: 'stun:stun.l.google.com:19302' }] }`，用于 NAT 穿透。

3. **pc.addTrack(track, stream)**  
   把本地音频轨加入连接，对端在 `pc.ontrack` 里会收到远端流并播放。

4. **pc.createDataChannel('msg', { ordered: true })**  
   主叫创建名为 `msg` 的 DataChannel，用于发文本消息。**只有主叫创建**，被叫通过 **pc.ondatachannel** 收到该通道。

5. **pc.createOffer()**  
   生成 SDP 描述（Offer），包含本端支持的编解码、已有轨、DataChannel 等。

6. **pc.setLocalDescription(offer)**  
   把该 Offer 设为本地描述。

7. **通过信令发送 Offer**  
   发送：
   ```json
   { "type": "signal", "payload": { "type": "offer", "sdp": "<整段 SDP 字符串>" } }
   ```
   服务器把 `payload` 原样转发给同房间**除自己外**的所有连接，即被叫会收到。

### 3. 被叫收到 Offer 并回复 Answer

被叫端在 WebSocket 的 `onmessage` 里收到 `type: 'signal'`，且 `payload.type === 'offer'` 时：

1. **getUserMedia({ audio: true })**  
   若尚未获取，先要麦克风权限。

2. **new RTCPeerConnection(config)**  
   创建自己的对等连接（和主叫配置一致，如同一 STUN）。

3. **pc.ondatachannel = (e) => { ... }**  
   **必须先设置**，再执行 setRemoteDescription。这样当远端 SDP 里带有 DataChannel 时，会触发 `ondatachannel`，在回调里拿到 `e.channel`，并给该 channel 绑定 `onmessage` 等，用于收消息。

4. **pc.addTrack(track, stream)**  
   把自己的音频轨加入连接。

5. **pc.setRemoteDescription(new RTCSessionDescription({ type: 'offer', sdp: payload.sdp }))**  
   把主叫的 Offer 设为「远端描述」，PeerConnection 据此知对端能力与 DataChannel 信息。

6. **pc.createAnswer()**  
   根据本地能力 + 远端 Offer 生成 Answer（SDP）。

7. **pc.setLocalDescription(answer)**  
   把 Answer 设为本地描述。

8. **通过信令发送 Answer**  
   发送：
   ```json
   { "type": "signal", "payload": { "type": "answer", "sdp": "<整段 SDP 字符串>" } }
   ```
   服务器转发给主叫。

### 4. 主叫收到 Answer

主叫在信令里收到 `payload.type === 'answer'` 后：

- **pc.setRemoteDescription(new RTCSessionDescription({ type: 'answer', sdp: payload.sdp }))**  
  把被叫的 Answer 设为远端描述。  
  至此，**SDP 协商完成**，两端对「有哪些轨、有没有 DataChannel」达成一致。

### 5. ICE 候选交换（可能多次）

- 两端在**设置本地/远端描述后**会陆续产生 **ICE 候选**（本机网卡、局域网地址、STUN 反射地址等）。
- 每次产生时触发 **pc.onicecandidate**，把候选通过信令发给对端：
  ```json
  {
    "type": "signal",
    "payload": {
      "type": "ice",
      "candidate": {
        "candidate": "...",
        "sdpMLineIndex": 0,
        "sdpMid": "..."
      }
    }
  }
  ```
- 对端收到后执行 **pc.addIceCandidate(new RTCIceCandidate(payload.candidate))**。
- 双方不断补充候选，直到 **pc.iceConnectionState** 变为 **connected**（或 failed/closed），此时 P2P 通道建立完成。

### 6. DataChannel 与音轨就绪

- **主叫**：自己创建的 DataChannel 在连接成功后触发 **channel.onopen**，可在此后 **channel.send(data)** 发消息。
- **被叫**：在 **pc.ondatachannel** 回调里拿到 **channel**，同样设置 **channel.onopen / onmessage**，即可收发消息。
- **音频**：两端通过 **pc.ontrack** 收到对端音轨，把 `event.streams[0]` 赋给 `<audio>.srcObject` 并播放。

此后，**消息和语音都走 P2P**，不再经过信令服务器。

### 7. 应用层消息协议（msg / ack）

为区分「我发的」和「对方发的」，并显示「已送达」，本 demo 使用简单应用协议：

- **发送消息**：DataChannel 发送 JSON 字符串：
  ```json
  { "type": "msg", "id": "唯一id", "text": "内容" }
  ```
- **接收方**：解析后展示「对方: 内容」，并立刻回复：
  ```json
  { "type": "ack", "id": "上文的id" }
  ```
- **发送方**：收到 ack 后，根据 id 把对应条目标记为「✓已送达」。

信令服务器不参与 msg/ack，它们只通过已建立的 DataChannel 在两端之间传输。

---

## 四、关键点小结

| 要点 | 说明 |
|------|------|
| **信令与媒体分离** | 信令（SDP、ICE）走 WebSocket + 服务器转发；媒体和 DataChannel 走 P2P。 |
| **Offer / Answer 方向固定** | 主叫发 Offer，被叫回 Answer；SDP 必须成对（setLocalDescription + setRemoteDescription）。 |
| **DataChannel 谁建谁收** | 主叫 createDataChannel，被叫只能通过 ondatachannel 拿到同一通道。 |
| **ICE 必须双向交换** | 两端都要把 onicecandidate 得到的候选发给对端，并由对端 addIceCandidate。 |
| **序列化格式** | 信令里 SDP 用 `{ type: 'offer'|'answer', sdp: 字符串 }`，ICE 用 `{ type: 'ice', candidate: { candidate, sdpMLineIndex, sdpMid } }`，避免直接传对象导致字段丢失。 |

---

## 五、与 Mac 互通时的对照

Mac 端要实现同一逻辑，需要：

1. **信令**：连同一 WebSocket（如 `ws://localhost:8080/ws`），加入同一 `roomId`，收发相同格式的 `signal`（offer / answer / ice）。
2. **WebRTC**：使用同一 STUN、同一 DataChannel 名称（`msg`）、先设置 **ondatachannel** 再 setRemoteDescription（若 Mac 为被叫）。
3. **消息协议**：DataChannel 发送的 JSON 与 Web 一致（msg + ack），便于两端都显示「我发送 / 对方 / ✓已送达」。

按上述顺序对照 Mac 端实现，即可在 web2web 调通的基础上排查 Mac 无法互通的原因。

### 为何 Mac 收不到 Web 发来的消息？（房间内多端时）

当前信令是**按房间广播**的：同一房间内任何人发 `signal`，**其他所有人**都会收到。但每一端（Mac / Web）通常只维护**一个** RTCPeerConnection，所以：

- 房间里有 **3 端**（例如 1 个 Mac + 2 个 Web 标签页）时，**只有其中 2 端会真正配对成功**（谁先完成 Offer/Answer，谁就建立连接）。
- 例如：Web1 点「发起连接」发 Offer → Mac 和 Web2 **都**收到 Offer，都会回复 Answer；Web1 只会把**第一个收到的 Answer** 设上去，和那一端建立连接，第二个 Answer 会因状态不对被忽略。
- 结果是：**发消息的 Web 可能和另一个 Web 连上了，而和 Mac 并没有建立对等连接**，所以 Mac 收不到该 Web 发的消息。

**正确用法（让 Mac 一定能收到 Web 的消息）：**

- **房间内只留 2 端**：1 个 Mac + 1 个 Web 标签页（不要同时开两个 Web 标签页进同一房间和 Mac 测）。
- 任一端先点「发起连接」，另一端会收到 Offer 并自动回复 Answer，连接建立后即可互相发消息。
- Mac 端日志里若出现「收到 signal: offer (来自 web_xxx)」「收到远端 Offer，正在创建连接并回复 Answer…」「DataChannel 状态: 1」，说明 Mac 与对方已建连；若只有「已加入房间」「WebSocket 已连接」且没有「收到 signal: offer」，说明对方还没发 Offer 或 Mac 未收到，需要由 Mac 或 Web 点一次「发起连接」。
