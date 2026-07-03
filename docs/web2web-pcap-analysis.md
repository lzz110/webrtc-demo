# web2web.pcapng 请求流程与消息分析

## 概述

本文档基于 **重新抓取的** `web2web.pcapng`，使用 tshark 解析 **Web → 信令服务器(8080) → Web** 的 WebSocket 信令流程，并给出每条传输消息的解析结果（join/joined/peers/signal 的 Offer/Answer/ICE），以及 SDP/ICE/DTLS 关键字段说明。

**抓包文件**: `web2web.pcapng`（重新抓取）  
**分析工具**: Wireshark/tshark  
**信令方式**: WebSocket (`GET /ws`，路径 `/ws`)  
**信令服务**: `[::1]:8080`（本地 IPv6 loopback）

---

## 抓包文件帧号索引

### 信令流程帧号对照表

| 阶段 | 帧号 | 时间戳 | 方向 | 描述 |
|------|------|--------|------|------|
| **WebSocket 建连（客户端 A）** | | | | |
| 客户端 A 发起 TCP | 449 | 4.381106s | 61339 → 8080 | SYN |
| 服务器 SYN+ACK | 450 | 4.381233s | 8080 → 61339 | SYN, ACK |
| HTTP 升级请求 | 453 | 4.381443s | 61339 → 8080 | GET /ws HTTP/1.1 |
| HTTP 升级响应 | 459 | 4.389822s | 8080 → 61339 | HTTP/1.1 101 Switching Protocols |
| **加入房间（客户端 A）** | | | | |
| 客户端 A 加入 | 461 | 4.390233s | 61339 → 8080 | WebSocket: join (peerId: web_1773643063124) |
| 服务器确认加入 | 463 | 4.390918s | 8080 → 61339 | WebSocket: joined |
| **WebSocket 建连（客户端 B）** | | | | |
| 客户端 B 发起 TCP | 609 | 6.275555s | 61352 → 8080 | SYN |
| HTTP 升级请求 | 613 | 6.276068s | 61352 → 8080 | GET /ws HTTP/1.1 |
| HTTP 升级响应 | 615 | 6.277587s | 8080 → 61352 | HTTP/1.1 101 Switching Protocols |
| **加入房间（客户端 B）** | | | | |
| 客户端 B 加入 | 617 | 6.280826s | 61352 → 8080 | WebSocket: join (peerId: web_1773643065013) |
| 服务器确认加入 | 619 | 6.285107s | 8080 → 61352 | WebSocket: joined |
| 服务器广播人数 | 620 | 6.285161s | 8080 → 61339 | WebSocket: peers (count:2) |
| **Offer / ICE（主叫→被叫）** | | | | |
| 客户端 A 发送 Offer | 835 | 9.026450s | 61339 → 8080 | WebSocket: signal (type:offer) |
| 服务器转发 Offer | 837 | 9.026843s | 8080 → 61352 | WebSocket: signal (offer, from: web_1773643063124) |
| 客户端 A 发送 ICE | 839, 843, 883, 885, 905, 913 | 9.045s–9.212s | 61339 → 8080 | 多条 signal (type:ice) |
| 服务器转发 ICE | 841, 845, 887, 889, 907, 915 | 9.046s–9.212s | 8080 → 61352 | signal (ice, from: web_1773643063124) |
| **Answer / ICE（被叫→主叫）** | | | | |
| 客户端 B 发送 Answer | 927 | 9.303749s | 61352 → 8080 | WebSocket: signal (type:answer) |
| 服务器转发 Answer | 929 | 9.304121s | 8080 → 61339 | WebSocket: signal (answer, from: web_1773643065013) |
| 客户端 B 发送 ICE | 931 | 9.323783s | 61352 → 8080 | WebSocket: signal (type:ice) |
| 服务器转发 ICE | 933 | 9.323991s | 8080 → 61339 | WebSocket: signal (ice, from: web_1773643065013) |
| **连接关闭** | | | | |
| 客户端 B 关闭 WebSocket | 15772 | 69.603286s | 61352 → 8080 | WebSocket Connection Close |
| 服务器广播人数 | 15784 | 69.612475s | 8080 → 61339 | WebSocket: peers (count:1) |
| 客户端 A 关闭 WebSocket | 15992 | 72.033395s | 61339 → 8080 | WebSocket Connection Close |

**角色与端口对应（本抓包）**:

| 角色 | 端口 | peerId | 说明 |
|------|------|--------|------|
| 客户端 A（主叫/Offerer） | 61339 | web_1773643063124 | 先加入房间，点击「发起连接」发 Offer |
| 客户端 B（被叫/Answerer） | 61352 | web_1773643065013 | 后加入，收到 Offer 后回 Answer |
| 信令服务器 | 8080 | — | [::1]:8080 |

抓包中 8080 对应两条 TCP 流：**Stream 41**（服务器 ↔ 61339）、**Stream 54**（服务器 ↔ 61352）。

---

## 传输的消息内容（从 pcap 解析）

以下为从 **当前** `web2web.pcapng` 中解析出的 WebSocket 文本消息内容（JSON 及关键 SDP/ICE 字段）。

### 1. join（客户端 A 加入房间）

**来源帧**: 461  
**方向**: 61339 → 8080（客户端 A → 信令服务器）

**消息内容（JSON）**:

```json
{
  "type": "join",
  "roomId": "demo",
  "peerId": "web_1773643063124"
}
```

| 字段 | 值 | 说明 |
|------|-----|------|
| type | join | 加入房间 |
| roomId | demo | 房间 ID |
| peerId | web_1773643063124 | 客户端 A 的 peer 标识（主叫） |

---

### 2. joined（服务器确认加入 — 客户端 A）

**来源帧**: 463  
**方向**: 8080 → 61339

**消息内容（JSON）**:

```json
{
  "type": "joined",
  "roomId": "demo",
  "peerId": "web_1773643063124"
}
```

---

### 3. join / joined（客户端 B）

**来源帧**: 617（join）、619（joined）  
**方向**: 61352 → 8080（join）、8080 → 61352（joined）

**join 消息（JSON）**:

```json
{
  "type": "join",
  "roomId": "demo",
  "peerId": "web_1773643065013"
}
```

| 字段 | 值 | 说明 |
|------|-----|------|
| peerId | web_1773643065013 | 客户端 B 的 peer 标识（被叫） |

---

### 4. peers（服务器广播房间人数）

**来源帧**: 620（8080 → 61339）；离开时 15784（8080 → 61339，count:1）

**消息内容（JSON）**:

```json
{
  "type": "peers",
  "count": 2
}
```

| 字段 | 值 | 说明 |
|------|-----|------|
| type | peers | 房间内人数通知 |
| count | 2 | 当前房间内 2 个 peer |

---

### 5. signal — Offer（主叫 SDP Offer）

**来源帧**: 835（61339 → 8080 发送）；837（8080 → 61352 转发）  
**发送方**: web_1773643063124（客户端 A，主叫）  
**接收方**: web_1773643065013（客户端 B，被叫）

**消息内容（JSON 结构）**:

```json
{
  "type": "signal",
  "from": "web_1773643063124",
  "payload": {
    "type": "offer",
    "sdp": "v=0\r\no=- 3950946023744069191 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n..."
  }
}
```

**SDP 摘要（Offer）**:

| 项目 | 值 | 说明 |
|------|-----|------|
| 会话 ID (o=) | 3950946023744069191 | 64 位随机数 |
| 会话版本 (o=) | 2 | 版本号 |
| BUNDLE | 0 1 | 音频 + DataChannel 复用 |
| ice-ufrag | l9ws | ICE 用户名片段 |
| ice-pwd | w2kHP4+dfViZHvSQUzWJ79jA | ICE 密码 |
| setup | actpass | DTLS 角色待协商 |
| fingerprint | sha-256 9B:DB:8B:40:AB:38:07:4A:8D:AF:ED:5E:03:CD:86:E9:40:94:D9:12:01:D6:3D:B6:64:A9:7C:33:33:EC:74:E1 | DTLS 证书指纹 |
| m=audio | 9 UDP/TLS/RTP/SAVPF 111 63 9 0 8 13 110 126 | 音频媒体，opus 等 |
| m=application | 9 UDP/DTLS/SCTP webrtc-datachannel | DataChannel |
| sctp-port | 5000 | SCTP 端口 |
| max-message-size | 262144 | 最大消息 256KB |

---

### 6. signal — ICE（主叫的 ICE 候选，多条）

**来源帧**: 839, 843, 883, 885, 905, 913（61339 → 8080）；841, 845, 887, 889, 907, 915（8080 → 61352 转发）  
**from**: web_1773643063124

**示例消息（JSON，帧 841）**:

```json
{
  "type": "signal",
  "from": "web_1773643063124",
  "payload": {
    "type": "ice",
    "candidate": {
      "candidate": "candidate:3312508696 1 udp 2122260223 10.83.0.142 53330 typ host generation 0 ufrag l9ws network-id 1 network-cost 10",
      "sdpMLineIndex": 0,
      "sdpMid": "0"
    }
  }
}
```

**主叫 ICE 候选汇总（从抓包解析）**:

| 帧号 | typ | 地址:端口 | sdpMid | 说明 |
|------|-----|-----------|--------|------|
| 839, 841 | host | 10.83.0.142:53330 | 0 | UDP, component 1 |
| 843, 845 | host | 10.83.0.142:54594 | 1 | UDP, component 2 |
| 883, 887 | host | (TCP 或重复) | — | 主叫 ICE |
| 885, 889 | host | (同上) | — | 主叫 ICE |
| 905, 907 | srflx | 222.71.59.2:53330 raddr 10.83.0.142 rport 53330 | 0 | 服务器反射候选 |
| 913, 915 | srflx | 222.71.59.2:54594 raddr 10.83.0.142 rport 54594 | 1 | 服务器反射候选 |

---

### 7. signal — Answer（被叫 SDP Answer）

**来源帧**: 927（61352 → 8080 发送）；929（8080 → 61339 转发）  
**发送方**: web_1773643065013（客户端 B，被叫）  
**接收方**: web_1773643063124（客户端 A，主叫）

**消息内容（JSON 结构）**:

```json
{
  "type": "signal",
  "from": "web_1773643065013",
  "payload": {
    "type": "answer",
    "sdp": "v=0\r\no=- 72210315080066850808 2 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n..."
  }
}
```

**SDP 摘要（Answer）**:

| 项目 | 值 | 说明 |
|------|-----|------|
| 会话 ID (o=) | 72210315080066850808 | 64 位随机数 |
| 会话版本 (o=) | 2 | 版本号 |
| BUNDLE | 0 1 | 与 Offer 一致 |
| ice-ufrag | MWGl | 被叫 ICE 用户名片段 |
| ice-pwd | GnXEOj4vFltV1Xcko0r+B7Ij | 被叫 ICE 密码 |
| setup | active | 被叫为 DTLS Client |
| fingerprint | sha-256 FB:85:01:57:1A:44:3B:6D:42:3E:EC:4B:74:4F:10:90:5E:7E:A0:95:80:0C:B5:A2:3A:21:28:21:E2:F3:D7:74 | 被叫 DTLS 证书指纹 |
| m=audio / m=application | 同 Offer | 与 Offer 一致 |
| sctp-port | 5000 | SCTP 端口 |
| max-message-size | 262144 | 256KB |

---

### 8. signal — ICE（被叫的 ICE 候选）

**来源帧**: 931（61352 → 8080）；933（8080 → 61339 转发）  
**from**: web_1773643065013

**消息内容（JSON）**:

```json
{
  "type": "signal",
  "from": "web_1773643065013",
  "payload": {
    "type": "ice",
    "candidate": {
      "candidate": "candidate:2946458416 1 udp 2122260223 10.83.0.142 61329 typ host generation 0 ufrag MWGl network-id 1 network-cost 10",
      "sdpMLineIndex": 0,
      "sdpMid": "0"
    }
  }
}
```

| 属性 | 值 | 说明 |
|------|-----|------|
| typ | host | 主机候选 |
| 地址:端口 | 10.83.0.142:61329 | 被叫本地地址 |
| ufrag | MWGl | 与 Answer SDP 一致 |
| sdpMid | 0 | 对应 m=audio |

---

## 1. 基础会话信息

### 1.1 SDP 标准字段（本抓包）

| 字段 | Offer (web_1773643063124) | Answer (web_1773643065013) | 含义 |
|------|----------------------------|----------------------------|------|
| **v=0** | ✓ | ✓ | SDP 版本 |
| **o=-** `<sess-id>` `<sess-version>` | 3950946023744069191, 2 | 72210315080066850808, 2 | 会话 ID 与版本号 |
| **s=-** | ✓ | ✓ | 会话名为空 |
| **t=0 0** | ✓ | ✓ | 会话时间永久 |

### 1.2 会话发起者解析（Offer）

```
o=- 3950946023744069191 2 IN IP4 127.0.0.1
  │  │                      │  │  │   │
  │  │                      │  │  │   └── 地址占位符
  │  │                      │  │  └────── IPv4
  │  │                      │  └───────── Internet
  │  │                      └──────────── 会话版本号
  │  └─────────────────────────────────── 会话 ID（64 位随机数）
  └────────────────────────────────────── 用户名（-）
```

---

## 2. ICE 信息

### 2.1 ICE 凭证

#### Offer（主叫 web_1773643063124）

**来源帧**: 835 / 837（signal offer 的 SDP 内）

```sdp
a=ice-ufrag:l9ws
a=ice-pwd:w2kHP4+dfViZHvSQUzWJ79jA
```

| 属性 | 值 | 说明 |
|------|-----|------|
| ice-ufrag | l9ws | 用户名片段 |
| ice-pwd | w2kHP4+dfViZHvSQUzWJ79jA | 密码 |

#### Answer（被叫 web_1773643065013）

**来源帧**: 927 / 929（signal answer 的 SDP 内）

```sdp
a=ice-ufrag:MWGl
a=ice-pwd:GnXEOj4vFltV1Xcko0r+B7Ij
```

| 属性 | 值 | 说明 |
|------|-----|------|
| ice-ufrag | MWGl | 用户名片段 |
| ice-pwd | GnXEOj4vFltV1Xcko0r+B7Ij | 密码 |

### 2.2 ICE 候选者汇总

#### 主叫（web_1773643063124）候选者

| 类型 | 地址:端口 | 帧号（转发至 61352） |
|------|-----------|----------------------|
| host udp | 10.83.0.142:53330, 10.83.0.142:54594 | 841, 845 |
| srflx | 222.71.59.2:53330, 222.71.59.2:54594 | 907, 915 |

#### 被叫（web_1773643065013）候选者

| 类型 | 地址:端口 | 帧号（转发至 61339） |
|------|-----------|----------------------|
| host | 10.83.0.142:61329 | 933 |

---

## 3. DTLS 信息

本次抓包中可以完整解析 **DTLS 1.3 的握手阶段**（ClientHello / ServerHello 等），但由于当前 `sslkeys.log` 中没有与这些 DTLS 会话匹配的应用流量密钥，\n所有 DTLS Application Data 在 Wireshark / tshark 中仍显示为 **Encrypted Data**，不会出现 `Decrypted DTLS` 或上层 SCTP/DataChannel 明文。

### 3.1 握手端口与角色

从 `web2web.pcapng` 中可以看到 DTLS 握手的两个端口：

- **ClientHello**（帧 1519）: `10.83.0.142:62184 → 10.83.0.142:51156`  
- **ServerHello**（帧 1520）: `10.83.0.142:51156 → 10.83.0.142:62184`

结合 SDP：

- `62184` 所在一侧为 **DTLS Client**（被叫 Answerer，`setup:active`）\n- `51156` 所在一侧为 **DTLS Server**（主叫 Offerer，`setup:actpass`）

### 3.2 证书指纹

#### Offer（主叫）

```sdp
a=fingerprint:sha-256 9B:DB:8B:40:AB:38:07:4A:8D:AF:ED:5E:03:CD:86:E9:40:94:D9:12:01:D6:3D:B6:64:A9:7C:33:33:EC:74:E1
```

#### Answer（被叫）

```sdp
a=fingerprint:sha-256 FB:85:01:57:1A:44:3B:6D:42:3E:EC:4B:74:4F:10:90:5E:7E:A0:95:80:0C:B5:A2:3A:21:28:21:E2:F3:D7:74
```

### 3.3 DTLS 角色协商

| Offer | Answer | 结果 |
|-------|--------|------|
| actpass | active | 主叫 = DTLS Server，被叫 = DTLS Client |

---

## 4. 媒体信息

### 4.1 媒体描述行（Offer/Answer 一致）

```sdp
m=audio 9 UDP/TLS/RTP/SAVPF 111 63 9 0 8 13 110 126
m=application 9 UDP/DTLS/SCTP webrtc-datachannel
```

| 媒体 | 端口 | 协议 | 说明 |
|------|------|------|------|
| audio | 9 | UDP/TLS/RTP/SAVPF | 音频（opus 等），端口为占位符 |
| application | 9 | UDP/DTLS/SCTP | WebRTC DataChannel |

### 4.2 SCTP 配置

```sdp
a=sctp-port:5000
a=max-message-size:262144
```

---

## 5. 扩展和特性

### 5.1 BUNDLE

```sdp
a=group:BUNDLE 0 1
```

音频(mid:0) 与 DataChannel(mid:1) 复用同一传输连接。

### 5.2 传输方向

```sdp
a=sendrecv
```

双向音视频与数据。

---

## 6. 与 server.js 的对应关系

- 建连: `GET /ws` → `wss.on('connection')`
- `type: 'join'` → 回 `joined`，并 `broadcastToRoom(..., { type: 'peers', count })`
- `type: 'signal'` → `broadcastToRoom(roomId, excludeWs, { type: 'signal', from: peerId, payload })`  
  Offer/Answer/ICE 均以 `signal` 在房间内广播（排除发送者），对端在 8080 流上收到 `signal(from: ...)`。

---

## 7. 完整帧号速查表（8080 信令）

### 7.1 WebSocket 信令帧（本抓包）

| 帧号 | 时间戳 | 方向 | 消息类型 | 内容摘要 |
|------|--------|------|----------|----------|
| 453 | 4.381443s | 61339 → 8080 | HTTP | GET /ws |
| 459 | 4.389822s | 8080 → 61339 | HTTP | 101 Switching Protocols |
| 461 | 4.390233s | 61339 → 8080 | WebSocket | join (roomId:demo, peerId:web_1773643063124) |
| 463 | 4.390918s | 8080 → 61339 | WebSocket | joined |
| 613 | 6.276068s | 61352 → 8080 | HTTP | GET /ws |
| 615 | 6.277587s | 8080 → 61352 | HTTP | 101 Switching Protocols |
| 617 | 6.280826s | 61352 → 8080 | WebSocket | join (peerId:web_1773643065013) |
| 619 | 6.285107s | 8080 → 61352 | WebSocket | joined |
| 620 | 6.285161s | 8080 → 61339 | WebSocket | peers (count:2) |
| 835 | 9.026450s | 61339 → 8080 | WebSocket | signal offer |
| 837 | 9.026843s | 8080 → 61352 | WebSocket | signal offer (from: web_1773643063124) |
| 839–915 | 9.045s–9.212s | 双向 | WebSocket | signal ice（主叫 host/srflx） |
| 927 | 9.303749s | 61352 → 8080 | WebSocket | signal answer |
| 929 | 9.304121s | 8080 → 61339 | WebSocket | signal answer (from: web_1773643065013) |
| 931 | 9.323783s | 61352 → 8080 | WebSocket | signal ice（被叫 host） |
| 933 | 9.323991s | 8080 → 61339 | WebSocket | signal ice (from: web_1773643065013) |
| 15772 | 69.603286s | 61352 → 8080 | WebSocket | Connection Close |
| 15784 | 69.612475s | 8080 → 61339 | WebSocket | peers (count:1) |
| 15992 | 72.033395s | 61339 → 8080 | WebSocket | Connection Close |

### 7.2 小结

- 本版 **web2web.pcapng** 中 8080 端口展示了两端（61339 / 61352）通过同一信令服务器建立 1v1 WebRTC 的完整过程。
- 客户端 A（61339，web_1773643063124）先加入并作为主叫发 Offer，客户端 B（61352，web_1773643065013）后加入并回 Answer；服务器仅做房间内广播，不修改 SDP/ICE。
- 信令均在 8080 的 WebSocket 上完成；P2P 媒体与 DataChannel 在 ICE 成功后走直连。抓包末尾包含 WebSocket 关闭与 peers 人数更新（count:1）。

---

## 8. 参考文档

- [RFC 4566](https://tools.ietf.org/html/rfc4566) - SDP: Session Description Protocol
- [RFC 5245](https://tools.ietf.org/html/rfc5245) - ICE
- [RFC 5763](https://tools.ietf.org/html/rfc5763) - DTLS-SRTP
- [RFC 6347](https://tools.ietf.org/html/rfc6347) - DTLS 1.2
- [RFC 8832](https://tools.ietf.org/html/rfc8832) - WebRTC Data Channels
- 同项目: `docs/sdp_information_analysis.md`（过滤过的_lan_test.pcapng 的 SDP/ICE/DTLS 分析）
