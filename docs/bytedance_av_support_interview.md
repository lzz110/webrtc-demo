# 字节音视频技术支持专家面试准备手册

## 1. 使用说明与项目边界

这份手册围绕当前仓库的 WebRTC 学习实验整理，目标不是背概念，而是建立一条可以口述、可以被追问、也能回到实验材料验证的技术主线。

项目的真实边界必须始终说清楚：

- 这是个人 WebRTC 原理学习实验，不是生产项目。
- DTLS/SRTP 解密依赖本地可控环境和主动导出的 key，用于观察加密后的协议层次和媒体数据。
- 真实客户网络包通常无法直接解密。生产排障更依赖 SDK 日志、信令日志、`getStats`、连接状态、选中候选对、丢包率、RTT、抖动、码率、帧率、关键帧请求和服务端指标。
- FFmpeg Android 经历属于系统学习与实践，不应描述成独立开发了完整播放器内核。
- CDN、HLS、RTMP 和 Linux 线上排障属于岗位理论扩展。没有真实生产经历时，要说“理解原理和掌握排查方法”，不要虚构线上成果。

推荐使用方式：

1. 先熟练项目的一分钟和三分钟讲稿。
2. 沿 WebRTC 建联顺序学习第 5～11 章。
3. 使用第 12 章练习把实验理解迁移到生产排障。
4. 用第 15 章进行完整模拟面试。

## 2. 简历中的项目描述

### 一句话定位

为系统理解 WebRTC 原理，自主搭建 Native 与 Web 端互通实验环境，并结合 Wireshark、tshark、Python 和 FFmpeg 对信令、ICE、DTLS/SRTP、DataChannel 与媒体流进行协议分析。

### 简历三条版

- 搭建 Mac Native 与 Web 端 WebRTC 互通实验环境，覆盖 WebSocket 信令、Offer/Answer、Trickle ICE、音频链路与 DataChannel 通信。
- 在可控实验环境中主动导出 DTLS/SRTP key，结合 Wireshark、tshark 与 Python 分析 Signaling、ICE/STUN、DTLS、SRTP/RTP、SCTP/DataChannel 的完整链路；相关解密仅用于协议学习。
- 结合 FFmpeg 与编解码知识定位 RED 外层封装、VP8 主编码被误判为 H264 的问题，沉淀抓包案例、协议文档和可复用实验脚本。

### 面向技术支持岗位的价值

这个项目不能证明生产支持年限，但可以证明三种底层能力：能够主动搭环境复现问题，能够按协议层次拆解复杂链路，能够把一次实验沉淀成工具和知识文档。面试时要主动承认生产环境与实验环境的差异，再说明如何用日志、指标和状态数据替代明文解密。

## 3. 面试项目讲稿

### 一分钟版本

我为了系统学习 WebRTC 原理，搭建了一个 Mac Native 和 Web 端互通的实验项目，覆盖信令、音频和 DataChannel。项目重点不是界面，而是把连接过程拆开验证：先从 WebSocket 中观察 Offer、Answer 和 Trickle ICE，再通过 SDP 判断 BUNDLE、codec、ICE 凭证和 DTLS 角色。在本地可控环境里，我修改 WebRTC 源码主动导出 DTLS/SRTP key，用 Wireshark、tshark 和 Python 观察加密后的 SCTP 与媒体链路。一个典型案例是视频最初按 H264 提取一直失败，最后结合 SDP 和 RTP 负载确认 PT 123 是 RED 外层、内部主编码是 VP8。这个过程让我形成了按信令、网络、安全传输、媒体和播放分层定位问题的思路。解密只用于实验，真实支持场景我会依赖 SDK 日志、`getStats`、信令和服务端指标。

### 三分钟版本

这个项目的出发点是：我不想只会调用 WebRTC API，而是想理解一次连接到底经历了什么，所以搭建了 Mac Native、浏览器和 Node.js 信令服务器组成的互通环境。

第一层是信令。两个端通过 WebSocket 加入同一房间，信令服务器只负责转发 Offer、Answer 和 ICE candidate。以 `native2web.pcapng` 为例，Web 端发 Offer，Native 返回 Answer；ICE candidate 采用 Trickle ICE 逐条发送。

第二层是媒体与传输协商。我从 SDP 中分析 `m=audio`、`m=application`、codec、Payload Type、BUNDLE、ICE ufrag/pwd、DTLS fingerprint 和 `setup`。实验中 Web Offer 是 `setup:actpass`，Native Answer 是 `setup:active`，所以 Native 成为 DTLS Client，并在抓包 3383 发出 Client Hello。

第三层是安全传输。在可控实验中，我给 WebRTC 增加 keylog 回调，主动导出 DTLS 和 SRTP key。DTLS key 用于观察 SCTP/DataChannel，SRTP 双向 key 用于验证 RTP 媒体。这里最重要的边界是：真实客户抓包通常没有 key，不能靠解密定位；实验的意义是先理解加密流内部是什么，再把认识迁移到日志、状态和质量指标。

第四层是媒体。我编写 Python 脚本解析 RTP 头、SSRC、PT、H264 STAP-A/FU-A，并使用 FFmpeg 做媒体探测和转封装。一次实验中，最初按 H264 提取失败，后来从 SDP 确认外层 PT 123 是 RED，内部是 VP8，于是增加 RED 解包和 VP8 RTP 描述符处理，先生成 IVF 再转 MP4。

最后我把过程整理成抓包索引、分析文档和一键脚本。这个项目主要体现的是原理理解、证据化分析和工具沉淀，而不是生产项目经验。

## 4. 项目证据索引

| 面试主题 | 实验结论 | 仓库证据 |
| --- | --- | --- |
| Native 与 Web 信令 | WebSocket 信令服务器转发 join、Offer、Answer 和 ICE | [`native2web-pcap-analysis.md`](native2web-pcap-analysis.md) |
| Web 与 Web 信令 | 两个浏览器通过本地信令服务完成 Offer/Answer 和 Trickle ICE | [`web2web-pcap-analysis.md`](web2web-pcap-analysis.md) |
| SDP 字段 | 可从 SDP 观察 BUNDLE、codec、ICE 凭证、fingerprint、DTLS setup 和 SCTP | [`sdp_information_analysis.md`](sdp_information_analysis.md) |
| DTLS 角色 | Web Offer 为 `setup:actpass`，Native Answer 为 `setup:active`，Native 发出 Client Hello | [`native2web-pcap-analysis.md`](native2web-pcap-analysis.md) |
| DTLS/SRTP key | 在可控 WebRTC 源码中主动导出 key，用于离线协议验证 | [`share.md`](../share.md)、[`src/README.md`](../src/README.md) |
| SCTP/DataChannel | 使用 tshark 识别 DTLS 端口并导出 PPID、TSN 和用户消息 | [`export_sctp_plaintext.py`](../src/export_sctp_plaintext.py) |
| RTP/H264 | 解析 RTP 头、SSRC、Payload Type，以及 H264 STAP-A、FU-A | [`webrtc_h264_extractor.py`](../src/webrtc_h264_extractor.py) |
| RED + VP8 | SDP 中 PT 123 是 RED 外层，实际主编码为 VP8，不能按裸 H264 解析 | [`red_vp8_extract.py`](../src/red_vp8_extract.py)、[`share.md`](../share.md) |
| 一键实验分析 | 汇总 Signaling、STUN、DTLS、RTP、SCTP 和视频导出 | [`decrypt_session_pipeline.py`](../src/decrypt_session_pipeline.py) |
| Web 互通 Demo | Node.js 信令、浏览器音频和 DataChannel | [`webrtc-web/README.md`](../webrtc-web/README.md) |

面试时，项目事实优先引用上述材料；生产场景回答则要明确说明是从实验原理迁移出的排障方法。

## 5. WebRTC 建联与信令

### 问题：WebRTC 为什么需要独立信令，Offer/Answer 做了什么？

**完整回答**

WebRTC 规范定义了媒体协商、连接建立和传输机制，但没有规定应用必须使用哪种信令协议。应用可以使用 WebSocket、HTTP、MQ 或其他通道交换 SDP 和 ICE candidate。Offer 描述发起方希望建立的媒体和传输能力，Answer 从双方能力交集中选择可接受参数。信令服务器通常只负责鉴权、房间管理和消息转发，不参与最终的媒体加密传输。

**结合本项目**

`native2web.pcapng` 中 Native 和 Web 都先通过 `GET /ws` 升级到 WebSocket，再发送 `join`。Web 在帧 3351 发 Offer，服务器在帧 3353 转发；Native 在帧 3371 返回 Answer，帧 3373 转发给 Web。服务端没有修改 SDP，只完成房间内路由。

**可能追问**

- 信令服务器断开后，已经建立的 P2P 媒体是否一定中断？
- SFU 场景中媒体是否仍然是端到端直连？

**30 秒回答**

WebRTC 不规定信令实现，应用用 WebSocket 等方式交换 Offer、Answer 和 ICE。Offer/Answer 协商媒体、编解码和传输参数，信令服务器负责转发和房间管理；媒体链路建立后通常不经过这个信令服务。

### 问题：`setLocalDescription`、`setRemoteDescription` 和 Trickle ICE 的顺序是什么？

**完整回答**

发起方创建 Offer 后调用 `setLocalDescription(offer)`，这会启动本地 ICE gathering，然后通过信令发送 SDP；接收方先 `setRemoteDescription(offer)`，创建 Answer 并 `setLocalDescription(answer)`，再把 Answer 返回；发起方收到后 `setRemoteDescription(answer)`。Trickle ICE 允许 candidate 在收集到时立即发送，不必等 SDP 包含完整候选集合。收到远端 candidate 时通常调用 `addIceCandidate`，但如果 remote description 尚未设置，应用需要缓存 candidate，避免时序错误。

**结合本项目**

Web 发出 Offer 后，帧 3355、3357、3363、3364 继续逐条发送 ICE；Native 返回 Answer 后也在帧 3376 发送 candidate。这说明实验使用了 Trickle ICE，SDP 与 candidate 不是一次性发送完。

**可能追问**

- 为什么 `addIceCandidate` 可能报 remote description 为空？
- ICE gathering complete 与 ICE connection connected 有什么区别？

**30 秒回答**

Offerer 先设置本地 Offer，Answerer 设置远端 Offer、生成并设置本地 Answer，Offerer 再设置远端 Answer。Trickle ICE 让 candidate 边收集边发送；如果 candidate 早于远端 SDP 到达，需要先缓存再调用 `addIceCandidate`。

## 6. SDP 与媒体协商

### 问题：SDP 中 `m=`、`a=rtpmap`、`a=fmtp`、`mid` 和 `BUNDLE` 分别有什么作用？

**完整回答**

`m=` 定义一个媒体段，包括媒体类型、端口、传输协议和 Payload Type 列表；`a=rtpmap` 把动态 PT 映射到 codec、时钟频率和声道；`a=fmtp` 提供 codec 的格式参数，例如 H264 profile-level-id 或 Opus 特性；`a=mid` 为媒体段提供稳定标识；`a=group:BUNDLE` 表示多个媒体段复用同一 ICE/DTLS 传输和 UDP 五元组。BUNDLE 降低端口与握手开销，但接收端需要通过 MID、PT、SSRC 等信息正确分流。

**结合本项目**

Native-Web Offer 中 `BUNDLE 0 1` 把音频 `mid:0` 和 DataChannel `mid:1` 复用到同一传输；`m=audio` 使用 `UDP/TLS/RTP/SAVPF`，`m=application` 使用 `UDP/DTLS/SCTP webrtc-datachannel`，SCTP 端口为 5000。

**可能追问**

- BUNDLE 后为什么 SDP 仍然有多个 `m=` 段？
- Payload Type 在不同媒体段中是否全局唯一？

**30 秒回答**

`m=` 定义媒体段，`rtpmap` 映射 PT 到 codec，`fmtp` 描述 codec 参数，`mid` 标识媒体段，BUNDLE 让多个媒体段复用同一 ICE/DTLS 传输。本项目音频和 DataChannel 就通过 BUNDLE 共用传输。

### 问题：Payload Type、SSRC、MID 和 RID 的区别是什么？

**完整回答**

Payload Type 表示当前 RTP 包负载采用的编码或封装格式，动态 PT 的语义由 SDP 决定；SSRC 标识一个 RTP 同步源，常用于区分发送流和维护序列号、时间戳状态；MID 标识 SDP 中的媒体段，在 BUNDLE 场景帮助将包归属到正确的 m-line；RID 标识同一媒体源中的不同编码层，常用于 simulcast。PT 是格式，SSRC 是流，MID 是媒体段，RID 是编码层，不能互相替代。

**结合本项目**

实验脚本按 SSRC 汇总 RTP 流，再根据 PT 判断负载类型。视频案例中 PT 123 不是 H264，而是 SDP 声明的 RED 外层；仅看 SSRC 或包字节不能替代 SDP 的 PT 映射。

**可能追问**

- 为什么 SSRC 可能在重协商或碰撞后变化？
- RTX 流如何与原始媒体流关联？

**30 秒回答**

PT 表示编码或封装格式，SSRC 标识 RTP 源，MID 标识 SDP 媒体段，RID 标识 simulcast 编码层。项目中先按 SSRC 分流，再根据 SDP 的 PT 映射确认实际负载。

## 7. ICE、STUN、TURN 与 NAT

### 问题：ICE candidate 的 host、srflx、relay 是什么，如何选出 candidate pair？

**完整回答**

host candidate 是本机网卡地址；srflx candidate 是通过 STUN 看到的 NAT 公网映射；relay candidate 是 TURN 服务器分配的中继地址。ICE 把本地和远端候选组成 candidate pair，通过 STUN connectivity check 验证可达性，并按候选类型、本地偏好、组件和协议计算优先级。控制方对成功 pair 发 USE-CANDIDATE 完成提名。理想情况选直连 host/srflx，直连失败才走 relay，但最终取决于连通性和优先级，而不是只看候选类型。

**结合本项目**

`web2web.pcapng` 同时观察到了私网 host candidate 和公网 srflx candidate；`native2web.pcapng` 的同机实验主要使用 host UDP candidate。抓包中的候选地址能解释 DTLS 最终使用的 UDP 端口。

**可能追问**

- ICE controlling 和 controlled 如何确定？
- 为什么有 srflx candidate 仍可能连接失败？

**30 秒回答**

host 是本地地址，srflx 是 STUN 获取的 NAT 映射，relay 是 TURN 中继。ICE 会组成候选对并做 STUN 连通性检查，最终提名一个成功且优先级合适的 pair；有候选不代表一定可达。

### 问题：STUN 和 TURN 的区别，什么情况下必须使用 TURN？

**完整回答**

STUN 主要帮助终端发现公网映射并执行 ICE 连通性检查，它不转发媒体；TURN 在终端之间无法直连时中继数据。对称 NAT、严格企业防火墙、UDP 被封禁、地址族或路由不兼容时，经常需要 TURN。生产系统通常准备 UDP TURN、TCP TURN 和 TLS 443 TURN 作为多级兜底。TURN 能提高连接成功率，但会增加带宽成本、时延和容量压力，因此需要监控分配成功率、relay 使用率和中继质量。

**结合本项目**

当前实验主要在同一网络或本机回环环境完成，没有覆盖完整 TURN 场景。因此面试时应表述为理解 STUN/TURN 原理和排查方法，而不是声称已验证生产 TURN 容量和调度。

**可能追问**

- TURN over TCP 为什么不是首选？
- relay 使用率突然升高可能说明什么？

**30 秒回答**

STUN 用于发现映射和检测直连，TURN 真正中继媒体。对称 NAT、严格防火墙或 UDP 不可用时需要 TURN。TURN 提升成功率但增加成本和时延，所以生产上要监控 relay 使用率和服务容量。

## 8. DTLS、SRTP、RTP 与 RTCP

### 问题：`setup:actpass` 和 `setup:active` 如何决定 DTLS Client/Server？

**完整回答**

SDP 的 `a=setup` 用于协商 DTLS 连接角色。Offer 常用 `actpass`，表示接受对端选择 active 或 passive；Answer 选择 `active` 时，Answerer 主动发起 DTLS Client Hello，Offerer 成为 passive 的 DTLS Server。这里的 DTLS Client/Server 与业务主叫/被叫、ICE controlling/controlled 不是同一个概念，不能凭谁发 Offer 直接推断。

**结合本项目**

Web 发出的 Offer 是 `setup:actpass`，Native Answer 是 `setup:active`，所以 Native 是 DTLS Client。`native2web.pcapng` 帧 3383 正是 Native 的 UDP 端口 52125 向 Web 端口 49428 发 Client Hello，和 SDP 一致。

**可能追问**

- Answer 是否可以选择 `passive`？
- DTLS role 和 SRTP key 方向为什么有关？

**30 秒回答**

Offer 的 `actpass` 让 Answerer 选择角色；Answer 为 `active` 时，Answerer 主动发 Client Hello，成为 DTLS Client。本项目 Native Answer 为 active，抓包 3383 也验证了 Native 发 Client Hello。

### 问题：SDP fingerprint 如何防止 DTLS 中间人攻击？

**完整回答**

SDP fingerprint 是对端 DTLS 证书的哈希。收到 DTLS Certificate 后，WebRTC 栈计算证书指纹并与通过信令获得的 SDP fingerprint 比较；不一致就拒绝连接。这样媒体密钥由 DTLS 协商，身份绑定则依赖可信信令传递 fingerprint。若信令本身可被攻击者同时篡改，攻击者也可能替换 SDP fingerprint，所以生产中仍需 HTTPS/WSS、鉴权和信令完整性保护。

**结合本项目**

`native2web-pcap-analysis.md` 记录了 Web Offer 与 Native Answer 各自的 SHA-256 fingerprint。实验可以在 SDP 和 DTLS Certificate 两侧观察这个绑定关系，但没有模拟信令劫持。

**可能追问**

- WebRTC 为什么通常使用自签名证书？
- fingerprint 验证失败应从哪些层排查？

**30 秒回答**

SDP fingerprint 是 DTLS 证书哈希。握手收到证书后必须和信令中的 fingerprint 匹配，否则拒绝连接。它把 DTLS 身份与 SDP 绑定，但前提是信令通道本身可信。

### 问题：DTLS、SRTP、RTP、RTCP 之间是什么关系？

**完整回答**

RTP 负责承载实时音视频，RTCP 负责质量反馈、同步和控制；SRTP/SRTCP 在 RTP/RTCP 外增加加密、完整性校验和重放保护。WebRTC 先在 ICE 选中的 UDP 路径上完成 DTLS 握手，再通过 DTLS-SRTP exporter 派生 SRTP 主密钥，之后媒体走 SRTP，控制反馈走 SRTCP。DTLS 不逐包承载音视频；DataChannel 才是 SCTP 数据封装在 DTLS record 内。

**结合本项目**

抓包中 DTLS 握手完成后出现加密媒体。实验分别导出 DTLS key 观察 SCTP/DataChannel，以及 SRTP key 验证 RTP 媒体，说明两类数据虽共用 ICE/DTLS 建立的安全上下文，但后续承载方式不同。

**可能追问**

- 为什么不能直接用 DTLS 传每个音视频包？
- RTP 与 RTCP 在 BUNDLE/rtcp-mux 后如何复用？

**30 秒回答**

RTP/RTCP 承载媒体和反馈，SRTP/SRTCP负责保护它们。WebRTC 用 DTLS 握手验证身份并派生 SRTP key，媒体随后走 SRTP；DataChannel 则是 SCTP over DTLS。

### 问题：SRTP 为什么需要区分发送和接收方向的 key？

**完整回答**

DTLS-SRTP 会派生 client_write 和 server_write 两个方向的密钥材料。一个端的发送 key 对应另一个端的接收 key，方向映射由 DTLS role 决定，而不是由 Offerer/Answerer 名称决定。如果把方向映射错，SRTP 认证标签校验失败，包不会被接受。多 SSRC 可以共享同一方向的主密钥，但每个 SSRC 具有独立的包索引、rollover counter 和重放窗口状态。

**结合本项目**

`webrtc_h264_extractor.py` 解析 `SRTP_KEYS role=... send_key=... recv_key=...`，按 DTLS role 映射 client/server write key，并在实验脚本中尝试双向 decryptor。早期只能解一侧的现象正是方向映射问题的重要线索。

**可能追问**

- SRTP 的 ROC 是什么？
- 为什么不应长期用“两个 key 都试一下”作为生产实现？

**30 秒回答**

SRTP 从 DTLS 派生 client_write 和 server_write 两套方向密钥，一个端发送对应对端接收。方向由 DTLS role 决定，映射错会导致认证失败。本项目的双向 key 实验帮助验证了这一点。

### 问题：RTP 序列号、时间戳和 SSRC 各自解决什么问题？

**完整回答**

序列号每个 RTP 包递增，用于发现丢包、重排和驱动 NACK；时间戳表示媒体采样时刻，增量由 codec clock rate 决定，用于播放节奏、抖动缓冲和音视频同步，它不是墙上时钟；SSRC 标识同步源，使接收端能够为每条流维护独立的序列号、时间戳、统计和解码状态。跨媒体同步还需要 RTCP Sender Report 把 RTP timestamp 映射到 NTP 时间。

**结合本项目**

`webrtc_h264_extractor.py` 解析 RTP header 的 sequence、timestamp、Payload Type 和 SSRC，脚本按 SSRC 汇总包数与序列号范围。它能观察包级连续性，但不等价于完整的播放质量评估。

**可能追问**

- 序列号回绕如何处理？
- 视频 90 kHz 时钟与帧率是什么关系？

**30 秒回答**

序列号用于丢包和重排，时间戳表示媒体采样时间，SSRC 标识一条同步源。接收端按 SSRC 维护状态，并用 RTCP SR 把 RTP 时间映射到 NTP 做跨流同步。

### 问题：RTCP 的 SR、RR、NACK、PLI、FIR 和 TWCC 分别有什么作用？

**完整回答**

SR 由发送端报告 NTP/RTP 时间映射和发送统计；RR 由接收端报告丢包、最高序列号、jitter 和往返时延相关字段。NACK 请求重传具体丢失序列号，通常配合 RTX；PLI 请求发送新的图像内刷新帧，常用于解码参考丢失；FIR 也是全帧刷新请求，但语义更强且使用应更克制；TWCC 基于 transport-wide sequence number 反馈每个包的到达时间，用于带宽估计和拥塞控制。它们解决的问题不同，不能把卡顿简单等价为“多发 PLI”。

**结合本项目**

当前脚本重点处理 RTP 和媒体导出，没有完整实现 RTCP/TWCC 分析。因此这部分属于基于 WebRTC 原理的岗位扩展，面试时可以说明下一步会将 RTCP 统计纳入自动化报告。

**可能追问**

- NACK、RTX 和 FEC 如何取舍？
- jitter 高但 packet loss 低可能是什么原因？

**30 秒回答**

SR/RR 提供同步和质量统计，NACK 请求具体包重传，PLI/FIR 请求刷新解码参考，TWCC 反馈包到达时间用于带宽估计。排障时要把这些反馈与丢包、RTT、码率和帧率结合看。

## 9. DataChannel 与 SCTP

### 问题：DataChannel 为什么使用 SCTP over DTLS，可靠性如何配置？

**完整回答**

SCTP 提供面向消息的传输、多 stream 复用、有序/无序交付和部分可靠性，比直接使用 TCP 更适合在同一 PeerConnection 中承载多种消息。WebRTC 将 SCTP 封装在 DTLS 中获得加密和身份验证，再运行在 ICE 选中的传输上。DataChannel 可以按 channel 配置 ordered、最大重传次数或最大存活时间，从而在可靠性和实时性之间取舍。多个 SCTP stream 可减少不同 DataChannel 之间的队头阻塞，但底层丢包和拥塞仍会影响整体连接。

**结合本项目**

SDP 的 `m=application` 为 `UDP/DTLS/SCTP webrtc-datachannel`，`sctp-port:5000`。`export_sctp_plaintext.py` 在可控 keylog 环境中让 tshark 解出 SCTP，并读取 PPID、TSN 和用户 JSON。

**可能追问**

- SCTP stream 和 WebRTC DataChannel ID 有什么关系？
- DataChannel 是否与媒体共享拥塞控制？

**30 秒回答**

DataChannel 使用 SCTP 获得消息边界、多 stream、有序/无序和部分可靠性，再通过 DTLS 加密。项目 SDP 中 SCTP 端口是 5000，实验脚本能观察 PPID 和 TSN。

### 问题：ordered、`maxRetransmits`、`maxPacketLifeTime` 如何取舍？

**完整回答**

`ordered:true` 保证按发送顺序交付，但前面的消息丢失会阻塞后续消息；`ordered:false` 允许后到消息先交付，适合位置、状态等只关心新值的数据。默认不设置重传限制时是可靠传输；`maxRetransmits` 限制重传次数；`maxPacketLifeTime` 限制消息可重传的时间，两者不能同时设置。聊天、控制命令通常需要可靠有序；高频状态或实时遥测可以选择无序和部分可靠，避免旧消息拖累新消息。

**结合本项目**

Web Demo 的 `msg` DataChannel 使用 ordered 文本消息，更接近聊天语义。实验没有覆盖不可靠模式，面试时应说明这是设计取舍的理论扩展。

**可能追问**

- `bufferedAmount` 为什么需要监控？
- 大消息对 DataChannel 和媒体有什么影响？

**30 秒回答**

可靠有序适合聊天和关键命令；无序、限制重传次数或生命周期适合只关心最新状态的数据。选择依据是业务能否容忍丢失、乱序和旧消息。

## 10. 编解码、RTP 负载与 FFmpeg

### 问题：为什么把 RED + VP8 误当 H264 会导致提取失败？

**完整回答**

RTP payload 的解释必须以 SDP 的 PT 映射为准。RED（RFC 2198）是冗余封装，外层 payload 先包含一个或多个 RED block header，再包含主编码数据；VP8 RTP payload 还带有自己的 payload descriptor。若把 RED 包的首字节直接当作 H264 NAL header，NAL type、分片边界和帧边界都会错误，最终得到无法解码的 Annex-B 数据。正确流程是：根据外层 PT 识别 RED，解析 block，取出主 VP8 payload，去掉 VP8 descriptor，按 marker/timestamp 组帧，写 IVF 或交给解码器。

**结合本项目**

实验 SDP 显示 `a=rtpmap:123 red/90000`，内部主编码 PT 为 VP8。最初 H264 脚本看到大量异常 NAL type，FFmpeg 也无法解码；增加 `red_vp8_extract.py` 后，先输出 IVF 再转 MP4，验证了根因不是 SRTP 解密失败，而是负载格式识别错误。

**可能追问**

- RED 与 ULPFEC、RTX 有什么区别？
- 如何从 SDP 找到 RED 保护的主 PT？

**30 秒回答**

PT 123 在 SDP 中映射为 RED，不是 H264。RED 外层和 VP8 descriptor 都需要先剥离，直接把首字节当 NAL header 会破坏帧结构。本项目正是通过 SDP 和异常 NAL 统计定位到 RED + VP8。

### 问题：H264 的 Single NAL、STAP-A、FU-A 如何封装进 RTP？

**完整回答**

较小的 NAL unit 可以作为 Single NAL Unit Packet 直接放进一个 RTP payload；STAP-A 将多个较小 NAL 聚合到一个 RTP 包，每个 NAL 前有 16 位长度，常用于 SPS/PPS；FU-A 将过大的 NAL 拆成多个 RTP 包，使用 FU indicator 和 FU header 保存原始 NAL type，并通过 Start/End 位标识重组边界。接收端要按序列号、时间戳和 marker 处理丢包与帧边界，再恢复 Annex-B 起始码。FU-A 中间片丢失时，整个 NAL 往往不可用。

**结合本项目**

`webrtc_h264_extractor.py` 实现了 RTP header、STAP-A 和 FU-A 解析，并将恢复的 NAL 写成 Annex-B，再调用 FFmpeg 封装为 MP4。这个逻辑只适用于 SDP 确认是 H264 的流。

**可能追问**

- SPS/PPS 丢失会有什么表现？
- marker bit 是否一定等价于关键帧结束？

**30 秒回答**

小 NAL 直接单包发送，STAP-A 聚合多个小 NAL，FU-A 拆分大 NAL。接收端必须按序列号和 FU Start/End 重组；丢一个 FU 分片通常会破坏整个 NAL。

### 问题：Opus 为什么适合实时音频，丢包时如何处理？

**完整回答**

Opus 支持从语音到音乐的宽码率、宽采样率和较低算法时延，并能根据网络动态调整码率、帧长、带宽、DTX 和 in-band FEC。接收端在丢包时可使用 PLC 生成掩蔽音频；开启 in-band FEC 后，下一个包可以携带前一帧的低码率冗余，但需要增加一帧等待；也可通过 RED 或应用侧冗余增强抗丢包。实时语音通常不依赖高 RTT 下的重传，因为迟到的音频价值很低。

**结合本项目**

实验 SDP 的音频优先 codec 包含 Opus，`webrtc_h264_extractor.py` 能把解出的 Opus RTP payload 写成 Ogg Opus，再通过 FFmpeg 转 WAV。当前实验未系统测试不同丢包率下的 PLC/FEC 效果。

**可能追问**

- Opus RTP clock rate 为什么通常是 48000？
- 音频卡顿但 RTP 丢包低时还应检查什么？

**30 秒回答**

Opus 低时延、码率和帧长可调，并支持 PLC、DTX 和 in-band FEC，适合实时语音。丢包时通常优先 PLC/FEC，而不是等待高 RTT 重传。

### 问题：FFmpeg 在实验中承担什么角色，转码和转封装有什么区别？

**完整回答**

FFmpeg 在实验中主要用于探测媒体信息、验证码流是否可解码、把裸码流或 IVF/Ogg 重新封装为常见容器，以及必要时解码输出 WAV。转封装只改变容器，编码数据不重新压缩，速度快且通常无质量损失；转码包含解码和重新编码，会改变 codec、码率、分辨率等，计算成本高并可能损失质量。排障时优先用 `ffprobe` 确认 codec、time base、时长和错误，再判断是码流损坏、时间戳异常、封装不匹配还是解码器问题。

**结合本项目**

RED+VP8 路径先写 IVF，再由 FFmpeg 转封装到 MP4；H264 路径恢复 Annex-B 后再封装；Opus 路径写 Ogg 后转 WAV。FFmpeg 是验证和处理工具，不是本项目自己实现的编解码器。

**可能追问**

- `-c copy` 表示什么？
- 有码流但 FFmpeg 报时间戳错误时如何排查？

**30 秒回答**

FFmpeg 用于探测、解码验证和封装转换。转封装只换容器，转码会重新编码。本项目把 VP8 写入 IVF、H264 恢复为 Annex-B，再用 FFmpeg 验证和封装。

## 11. 实验工具与自动化分析

### 问题：为什么要把 Wireshark 手工分析整理成 Python/tshark 工具？

**完整回答**

手工分析适合探索，但重复性差、容易漏字段，也不利于批量比较问题样本。工具化的价值是固定输入、输出和判定口径：识别 DTLS UDP 端口、统计 STUN/DTLS record、按 SSRC/PT 汇总 RTP、导出 SCTP PPID/TSN、提取媒体并生成统一日志。技术支持场景中，工具还应记录版本、命令、失败原因和原始证据，避免只输出一个“成功/失败”结论。自动化不能替代判断，规则必须允许回到原始包验证。

**结合本项目**

`decrypt_session_pipeline.py` 串联 SCTP 明文、RTP 流统计和视频导出；`export_sctp_plaintext.py` 调用 tshark；媒体脚本使用 Scapy 和 pylibsrtp。当前工具是实验性质，生产化还需要测试样本、错误码、性能和敏感数据治理。

**可能追问**

- 为什么一部分解析交给 tshark，一部分使用 Scapy？
- 如何为抓包分析工具设计回归测试？

**30 秒回答**

工具化能固定分析口径、减少重复劳动并保留证据链。项目中 tshark 负责成熟协议解析，Python 负责编排、统计和媒体处理；生产化还需要测试、错误处理和敏感数据治理。

## 12. 技术支持场景题

待 Task 3 补充。

## 13. CDN、HTTP、DNS 与流媒体协议

待 Task 4 补充。

## 14. Linux 与日志排障

待 Task 4 补充。

## 15. 模拟面试

待 Task 4 补充。

## 16. 一周复习计划

待 Task 5 补充。

## 17. 面试表达边界

待 Task 5 补充。
