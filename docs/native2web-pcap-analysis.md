# native2web.pcapng 请求流程与消息分析

## 概述

本文档基于 **native2web.pcapng**，使用 tshark 及 **native_sslkeys.log** 解析 **Native（Mac 客户端）↔ Web（浏览器）** 的 WebRTC 信令与媒体流程。本抓包中 **DTLS 1.2** 已通过 Native 端导出的密钥文件成功解密，可看到 DTLS Application Data 及上层 SCTP/DataChannel 流量。

**抓包文件**: `native2web.pcapng`  
**密钥文件**: `webrtc-keys/native_sslkeys.log`（NSS Key Log 格式，CLIENT_RANDOM）  
**分析工具**: Wireshark / tshark（需在 Preferences → TLS 中配置 Pre-Master-Secret log filename 指向上述 keylog）  
**信令方式**: WebSocket `GET /ws`，信令服务 8080

---

## 抓包文件帧号索引

### 信令流程帧号对照表

| 阶段 | 帧号 | 时间戳 | 方向 | 描述 |
|------|------|--------|------|------|
| **WebSocket 建连（Native Mac）** | | | | |
| Native 发起 TCP | 3165 | 24.472s | 50912 → 8080 | SYN |
| HTTP 升级请求 | 3169 | 24.472s | 50912 → 8080 | GET /ws HTTP/1.1 |
| HTTP 升级响应 | 3171 | 24.476s | 8080 → 50912 | HTTP/1.1 101 Switching Protocols |
| **加入房间（Native）** | | | | |
| Native 加入 | 3173 | 24.476s | 50912 → 8080 | WebSocket: join (peerId: mac_1773800721705) |
| 服务器确认加入 | 3175 | 24.476s | 8080 → 50912 | WebSocket: joined |
| **WebSocket 建连（Web）** | | | | |
| Web 发起 TCP/升级 | 3299 等 | 27.032s | 50921 → 8080 | WebSocket 建连 |
| **加入房间（Web）** | | | | |
| Web 加入 | 3299 | 27.032s | 50921 → 8080 | WebSocket: join (peerId: web_1773800724262) |
| 服务器确认加入 | 3301 | 27.033s | 8080 → 50921 | WebSocket: joined |
| 服务器广播人数 | 3303 | 27.033s | 8080 → 50912 | WebSocket: peers (count:2) |
| **Offer / ICE（Web → Native）** | | | | |
| Web 发送 Offer | 3351 | 28.490s | 50921 → 8080 | WebSocket: signal (type:offer) |
| 服务器转发 Offer | 3353 | 28.491s | 8080 → 50912 | WebSocket: signal (offer, from: web_1773800724262) |
| Web 发送 ICE | 3355, 3357, 3363, 3364 | 28.491s–28.613s | 50921 → 8080 | signal (type:ice) host/tcp |
| 服务器转发 ICE | 3359, 3361, 3367, 3369 | 28.491s–28.614s | 8080 → 50912 | signal (ice, from: web_1773800724262) |
| **Answer / ICE（Native → Web）** | | | | |
| Native 发送 Answer | 3371 | 28.634s | 50912 → 8080 | WebSocket: signal (type:answer) |
| 服务器转发 Answer | 3373 | 28.635s | 8080 → 50921 | WebSocket: signal (answer, from: mac_1773800721705) |
| Native 发送 ICE | 3376 | 28.638s | 50912 → 8080 | WebSocket: signal (type:ice) |
| 服务器转发 ICE | 3381 | 28.639s | 8080 → 50921 | WebSocket: signal (ice, from: mac_1773800721705) |
| **DTLS 握手与加密数据** | | | | |
| DTLS Client Hello | 3383 | 28.639s | 52125 → 49428 | Native (Client) → Web (Server) |
| DTLS Server Hello / Cert / … | 3384 | 28.640s | 49428 → 52125 | 握手继续 |
| DTLS Client Key Exchange / … | 3385 | 28.649s | 52125 → 49428 | 握手完成 |
| DTLS Change Cipher Spec / Finished | 3386 | 28.650s | 49428 → 52125 | 切换加密 |
| DTLS Application Data | 3387+ | 28.651s 起 | 双向 | **已解密**（SCTP/DataChannel 等） |

**角色与端口对应（本抓包）**:

| 角色 | WebSocket 端口 | peerId | DTLS 端口 | DTLS 角色 |
|------|----------------|--------|-----------|-----------|
| Native（Mac 客户端） | 50912 | mac_1773800721705 | 52125 | DTLS Client（Answerer，setup:active） |
| Web（浏览器） | 50921 | web_1773800724262 | 49428 | DTLS Server（Offerer，setup:actpass） |
| 信令服务器 | 8080 | — | — | — |

---

## 传输的消息内容（从 pcap 解析）

### 1. join（Native 加入房间）

**来源帧**: 3173  
**方向**: 50912 → 8080（Native → 信令服务器）

**消息内容（JSON）**:

```json
{
  "roomId": "demo",
  "type": "join",
  "peerId": "mac_1773800721705"
}
```

| 字段 | 值 | 说明 |
|------|-----|------|
| type | join | 加入房间 |
| roomId | demo | 房间 ID |
| peerId | mac_1773800721705 | Native 端 peer 标识 |

---

### 2. joined（服务器确认加入 — Native）

**来源帧**: 3175  
**方向**: 8080 → 50912

```json
{
  "type": "joined",
  "roomId": "demo",
  "peerId": "mac_1773800721705"
}
```

---

### 3. join / joined（Web）

**来源帧**: 3299（join）、3301（joined）  
**方向**: 50921 → 8080（join）、8080 → 50921（joined）

**join 消息（JSON）**:

```json
{
  "type": "join",
  "roomId": "demo",
  "peerId": "web_1773800724262"
}
```

---

### 4. peers（服务器广播房间人数）

**来源帧**: 3303（8080 → 50912）

```json
{
  "type": "peers",
  "count": 2
}
```

---

### 5. signal — Offer（Web 主叫 SDP Offer）

**来源帧**: 3351（50921 → 8080 发送）；3353（8080 → 50912 转发）  
**发送方**: web_1773800724262（Web，主叫）  
**接收方**: mac_1773800721705（Native，被叫）

**SDP 摘要（Offer）**:

| 项目 | 值 | 说明 |
|------|-----|------|
| 会话 ID (o=) | 3212275197340149533 | 64 位随机数 |
| BUNDLE | 0 1 | 音频 + DataChannel 复用 |
| ice-ufrag | /U6C | ICE 用户名片段 |
| ice-pwd | VtB9Pwh7rxx2whSePtwB5t4H | ICE 密码 |
| setup | actpass | DTLS 角色待协商 |
| fingerprint | sha-256 36:20:C0:65:0A:1E:D6:88:6A:25:55:77:69:28:CF:DC:80:30:03:D5:18:7A:C2:CC:11:35:C5:93:2D:92:24:7E | DTLS 证书指纹 |
| m=audio | 9 UDP/TLS/RTP/SAVPF 111 63 9 0 8 13 110 126 | 音频媒体 |
| m=application | 9 UDP/DTLS/SCTP webrtc-datachannel | DataChannel |
| sctp-port | 5000 | SCTP 端口 |
| max-message-size | 262144 | 最大消息 256KB |

---

### 6. signal — ICE（Web 的 ICE 候选）

**来源帧**: 3355, 3357, 3363, 3364（50921 → 8080）；3359, 3361, 3367, 3369（8080 → 50912 转发）  
**from**: web_1773800724262

**Web ICE 候选汇总**:

| 类型 | 地址:端口 | 说明 |
|------|-----------|------|
| host udp | 10.83.0.142:49428, 10.83.0.142:61174 | component 0/1 |
| host tcp | 10.83.0.142:9 (active) | TCP 候选 |

---

### 7. signal — Answer（Native 被叫 SDP Answer）

**来源帧**: 3371（50912 → 8080 发送）；3373（8080 → 50921 转发）  
**发送方**: mac_1773800721705（Native，被叫）  
**接收方**: web_1773800724262（Web，主叫）

**SDP 摘要（Answer）**:

| 项目 | 值 | 说明 |
|------|-----|------|
| 会话 ID (o=) | 6064803280354030821 | 64 位随机数 |
| ice-ufrag | Pvhf | Native ICE 用户名片段 |
| ice-pwd | 4R5950QppK4NSPWJl4Nz4Uvs | Native ICE 密码 |
| setup | **active** | Native 为 DTLS Client |
| fingerprint | sha-256 1C:65:AA:BD:3A:E7:3E:B3:46:46:73:DD:68:29:5E:C5:80:F7:04:DB:A3:4F:92:5C:9D:82:6A:46:85:48:D3:42 | Native DTLS 证书指纹 |
| m=audio / m=application | 同 Offer | 与 Offer 一致 |
| sctp-port | 5000 | SCTP 端口 |
| max-message-size | 262144 | 256KB |

---

### 8. signal — ICE（Native 的 ICE 候选）

**来源帧**: 3376（50912 → 8080）；3381（8080 → 50921 转发）  
**from**: mac_1773800721705

**候选示例**:

```
candidate:2867388794 1 udp 2122260223 10.83.0.142 52125 typ host generation 0 ufrag Pvhf ...
```

| 属性 | 值 | 说明 |
|------|-----|------|
| typ | host | 主机候选 |
| 地址:端口 | 10.83.0.142:52125 | Native 本地地址（与 DTLS Client 端口一致） |
| ufrag | Pvhf | 与 Answer SDP 一致 |

---

## DTLS 信息（已解密）

本抓包使用 **native_sslkeys.log**（Native 端通过 WebRTC 源码中的 `SSL_CTX_set_keylog_callback` 导出）进行解密。密钥格式为 NSS Key Log：`CLIENT_RANDOM <client_random_hex> <master_secret_hex>`。

### 密钥与 pcap 对应关系

- 抓包中 **DTLS Client Hello**（帧 3383）的 **Random** 为：  
  `b96aaff39b1751d4c8848c4362115bc725f38e2bda1f7037f2902d0c52fa5360`
- **native_sslkeys.log** 中第二条即为此会话的 `CLIENT_RANDOM`，Wireshark/tshark 配置该 keylog 后可成功解密 DTLS Application Data。

### 握手端口与角色

| 方向 | 端口 | 角色 |
|------|------|------|
| 52125 → 49428 | Native → Web | DTLS Client（发 Client Hello） |
| 49428 → 52125 | Web → Native | DTLS Server（发 Server Hello） |

与 SDP 一致：Web Offer 为 `setup:actpass`，Native Answer 为 `setup:active`，故 Native 为 DTLS Client，Web 为 DTLS Server。

### DTLS 版本

握手中协商为 **DTLS 1.2**（版本 0xfefd）。解密后可见：

- DTLS 握手：Client Hello、Server Hello、Certificate、Server Key Exchange、Certificate Request、Server Hello Done、Certificate、Client Key Exchange、Certificate Verify、Change Cipher Spec、Finished 等；
- DTLS Application Data（content type 23）：承载 SCTP/DataChannel 等，在 Wireshark 中显示为 **Decrypted DTLS**，可进一步解析 SCTP 与 WebRTC Data Channel 协议。

---

## ICE 与媒体信息

### ICE 凭证

| 端 | ice-ufrag | ice-pwd |
|----|-----------|---------|
| Web（Offer） | /U6C | VtB9Pwh7rxx2whSePtwB5t4H |
| Native（Answer） | Pvhf | 4R5950QppK4NSPWJl4Nz4Uvs |

### 媒体与 SCTP

- **BUNDLE**: 音频（mid:0）与 DataChannel（mid:1）复用同一传输。
- **m=audio**: UDP/TLS/RTP/SAVPF，opus 等。
- **m=application**: UDP/DTLS/SCTP webrtc-datachannel，sctp-port 5000，max-message-size 262144。

---

## 完整帧号速查表（信令 + DTLS）

| 帧号 | 时间戳 | 方向 | 消息类型 | 内容摘要 |
|------|--------|------|----------|----------|
| 3165 | 24.472s | 50912 → 8080 | TCP | SYN（Native WebSocket 建连） |
| 3169 | 24.472s | 50912 → 8080 | HTTP | GET /ws |
| 3171 | 24.476s | 8080 → 50912 | HTTP | 101 Switching Protocols |
| 3173 | 24.476s | 50912 → 8080 | WebSocket | join (peerId: mac_1773800721705) |
| 3175 | 24.476s | 8080 → 50912 | WebSocket | joined |
| 3299 | 27.032s | 50921 → 8080 | WebSocket | join (peerId: web_1773800724262) |
| 3301 | 27.033s | 8080 → 50921 | WebSocket | joined |
| 3303 | 27.033s | 8080 → 50912 | WebSocket | peers (count:2) |
| 3351 | 28.490s | 50921 → 8080 | WebSocket | signal offer |
| 3353 | 28.491s | 8080 → 50912 | WebSocket | signal offer (from: web_1773800724262) |
| 3355–3369 | 28.491s–28.614s | 双向 | WebSocket | signal ice（Web → Native 转发） |
| 3371 | 28.634s | 50912 → 8080 | WebSocket | signal answer |
| 3373 | 28.635s | 8080 → 50921 | WebSocket | signal answer (from: mac_1773800721705) |
| 3376 | 28.638s | 50912 → 8080 | WebSocket | signal ice（Native） |
| 3381 | 28.639s | 8080 → 50921 | WebSocket | signal ice (from: mac_1773800721705) |
| 3383 | 28.639s | 52125 → 49428 | DTLS | Client Hello |
| 3384 | 28.640s | 49428 → 52125 | DTLS | Server Hello, Certificate, … |
| 3385–3386 | 28.649s–28.650s | 双向 | DTLS | 握手完成（Change Cipher Spec, Finished） |
| 3387+ | 28.651s 起 | 双向 | DTLS | Application Data（已解密） |

---

## 在 Wireshark 中直接显示 DataChannel JSON 解析结果

DTLS 解密成功后，**包字节流**里已经能看到明文 JSON（如 `{"type":"msg","id":"...","text":"testlz z"}`）。若要在**包详细信息**里以树状结构展示解析后的字段（Type、Message ID、Text 等），可加载本项目提供的 Lua 解析器。

### 前置条件

- 已按前文配置 **TLS Pre-Master-Secret log**（如 `native_sslkeys.log`），DTLS 应用数据能解密。
- 抓包中 SCTP 使用 PPID 51（WebRTC String），载荷为本 demo 的 JSON（`type` 为 `msg` / `file` / `ack` 等）。

### 使用步骤

1. **获取 Lua 脚本**  
   脚本路径：`docs/wireshark-datachannel-json.lua`。

2. **在 Wireshark 中加载**（任选其一）：
   - **方式 A（推荐）**：**编辑 → 首选项 → Lua** → 在「脚本路径」中加入 `docs` 所在目录（如本项目根目录），在「启用」下的「Default」中填入脚本完整路径，例如：  
     `/Users/你的用户名/Desktop/demo/webrtc-demo/docs/wireshark-datachannel-json.lua`  
     确定后重启 Wireshark 或重新打开 pcap。
   - **方式 B**：启动时指定脚本  
     `wireshark -X lua_script:/绝对路径/webrtc-demo/docs/wireshark-datachannel-json.lua native2web.pcapng`

3. **查看效果**  
   打开已解密的 pcap，选中 SCTP DATA（如 DATA TSN=1、TSN=2 等应用数据包），在**包详细信息**中会多出子树 **「WebRTC DataChannel JSON」**，其中展示解析出的：
   - **Type**：`msg` / `file` / `ack`
   - **Message ID**：消息或文件的 id
   - **Text**：`type=msg` 时的文本内容
   - **File Name / File Size**：`type=file` 时的文件名与大小
   - **Raw JSON**：原始 JSON 字符串

无需额外过滤，只要该包是 PPID 51 的 SCTP DATA 且内容为上述 JSON 格式，就会自动被解析并显示在树中。

---

## 参考文档

- [RFC 4566](https://tools.ietf.org/html/rfc4566) - SDP
- [RFC 5245](https://tools.ietf.org/html/rfc5245) - ICE
- [RFC 5763](https://tools.ietf.org/html/rfc5763) - DTLS-SRTP
- [RFC 6347](https://tools.ietf.org/html/rfc6347) - DTLS 1.2
- [RFC 8832](https://tools.ietf.org/html/rfc8832) - WebRTC Data Channels
- 同项目: `docs/web2web-pcap-analysis.md`（Web↔Web 信令与 DTLS 分析）
- 同项目: `docs/SSLKEYLOGFILE_IMPLEMENTATION.md`（Native 端 keylog 实现说明）

---

# 附录：WebRTC 抓包解密 — 问题与解决方案总结

## 一、遇到的问题

### 1. Web ↔ Web 使用 DTLS 1.3，无法用 Wireshark 解密

- **现象**：浏览器与浏览器之间建立 WebRTC 时，Chrome/Edge 默认使用 **DTLS 1.3**。即便设置 `SSLKEYLOGFILE`，Wireshark 能解析 DTLS 握手，但 **Application Data 仍显示为 Encrypted Data**，无法看到 SCTP/DataChannel 明文。
- **原因**：Wireshark 对 DTLS 1.3 的 keylog 解密支持不完整（尤其是应用层流量密钥的匹配与解密逻辑），且浏览器导出的是 TLS 1.3 风格的 `CLIENT_TRAFFIC_SECRET_0` / `SERVER_TRAFFIC_SECRET_0` 等，与 DTLS 1.2 的 `CLIENT_RANDOM` + `master_secret` 不同，难以直接用于当前 Wireshark 的 DTLS 解密。

### 2. Web ↔ Native 使用 DTLS 1.2

- **现象**：当一端为 **浏览器**、另一端为 **Native（如 Mac 客户端，使用自编译 WebRTC.framework）** 时，协商出的 DTLS 版本为 **DTLS 1.2**。
- **原因**：Native 端使用的 BoringSSL/WebRTC 默认或当前配置为 DTLS 1.2，浏览器在与 Native 互通时会降级到 DTLS 1.2，因此从协议上具备用 NSS Key Log（CLIENT_RANDOM + master_secret）在 Wireshark 中解密的可能。

### 3. 浏览器端 SSLKEYLOGFILE 输出因浏览器而异

- **Chrome**：对 WebRTC DTLS 会话，keylog 中多为 **SERVER_HANDSHAKE_TRAFFIC_SECRET**、**CLIENT_HANDSHAKE_TRAFFIC_SECRET** 等 TLS 1.3 风格条目，而 **缺少** Wireshark 解密 DTLS 1.2 应用数据所需的 **CLIENT_RANDOM** + **master_secret**。因此即使 Web↔Native 使用 DTLS 1.2，仅靠 Chrome 的 keylog 仍无法在 Wireshark 中解密 DTLS Application Data。
- **Edge**：部分场景下会导出 **CLIENT_RANDOM**，但实测中与 pcap 里 DTLS Client Hello 的 Random 对不上，或仅覆盖部分连接（如页面其他 TLS 连接），**WebRTC DTLS 1.2 会话的 CLIENT_RANDOM 仍可能未写入**，导致解密失败。
- **结论**：依赖浏览器导出、且与 Wireshark 兼容的 DTLS 1.2 密钥并不可靠，且 Web↔Web 多为 DTLS 1.3，解密难度更大。

## 二、解决方案

### 1. 使用 Native 端导出 NSS Key Log（推荐）

- **思路**：在 **Native 端**（如 Mac 客户端）的 WebRTC 库中启用 BoringSSL 的 **keylog 回调**，将密钥写入文件，格式为 NSS Key Log（`CLIENT_RANDOM` + `master_secret`），供 Wireshark 使用。
- **实现要点**：
  - 在 WebRTC 源码（如 `rtc_base/openssl_stream_adapter.cc`）中，为 DTLS 使用的 `SSL_CTX` 注册 `SSL_CTX_set_keylog_callback`，在回调里读取环境变量 `SSLKEYLOGFILE`，将 BoringSSL 传入的 `line`（已是 NSS 格式）追加写入该文件。
  - 在 Native 应用启动最早阶段（如 `main` 或 App 的 `init`）通过 `setenv("SSLKEYLOGFILE", "/path/to/native_sslkeys.log", 1)` 指定 keylog 路径。
  - 重新编译 WebRTC.framework 和 Native 应用，抓包时先启动 Native、再建立 WebRTC 连接，即可在 `native_sslkeys.log` 中得到与当前 DTLS 1.2 会话对应的 `CLIENT_RANDOM`。
- **效果**：在 **Native ↔ Web** 场景下，将 Wireshark 的 Pre-Master-Secret log 指向 `native_sslkeys.log`，即可完整解密 DTLS 1.2 的 Application Data，查看 SCTP 与 DataChannel 内容（如本抓包 native2web.pcapng）。

A. 修改 WebRTC 源码：注册 keylog callback
已改：
/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/rtc_base/openssl_stream_adapter.cc

增加 DtlsKeyLogCallback()：读取环境变量 SSLKEYLOGFILE，append 写入每条 keylog line。
在 OpenSSLStreamAdapter::SetupSSLContext() 创建 SSL_CTX 后立刻调用：
SSL_CTX_set_keylog_callback(ctx, DtlsKeyLogCallback);
这一步的效果是：只要 App 设置了 SSLKEYLOGFILE，DTLS/TLS 的 keylog 行就会被写到文件里。

### 2. 区分场景选择抓包与解密方式

| 场景 | DTLS 版本 | 推荐做法 |
|------|-----------|----------|
| Web ↔ Web | 多为 DTLS 1.3 | 目前 Wireshark 对 DTLS 1.3 keylog 解密支持有限，可主要分析信令与握手；若必须看应用层，可考虑 Native 中继或等 Wireshark 增强支持。 |
| Web ↔ Native | DTLS 1.2 | 使用 **Native 端 keylog**（如上），配合 Wireshark 解密；浏览器端 SSLKEYLOGFILE 不作为主要依赖。 |

### 3. macOS Framework 编译与引用

- 若在修改 WebRTC 源码（如增加 keylog、或为 macOS 排除 RTCAudioSession 等 iOS 专用 API）后重新编译出 `WebRTC.framework`，需在 Xcode 工程中更新该 framework 的引用路径（如改为新产物路径或使用绝对路径），并确保 Clean Build 后重新链接，避免仍使用旧库导致无 keylog 或编译错误。

---

以上总结基于本项目在 web2web、web2native 抓包与 native keylog 实现过程中的实测结果，供后续排查 DTLS 解密与协议分析时参考。
