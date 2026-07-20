# 字节音视频技术支持专家面试准备手册

## 1. 使用说明与项目边界

这份手册围绕当前仓库的 WebRTC 学习实验整理，目标不是背概念，而是建立一条可以口述、可以被追问、也能回到实验材料验证的技术主线。

项目的真实边界必须始终说清楚：

- 这是个人 WebRTC 原理学习实验，不是生产项目。
- DTLS/SRTP 解密依赖本地可控环境和主动导出的 key，用于观察加密后的协议层次和媒体数据；该能力不对应真实生产环境中的通用解密能力。
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

### 通用排障框架

回答任何客户问题时，先使用同一条主线：

```text
确认影响范围和复现条件
→ 收集客户端、服务端和网络证据
→ 按信令、网络、传输、媒体、渲染分层
→ 提出可以被验证的假设
→ 给出临时止损方案
→ 明确根因和长期改进
```

生产环境不能假设能够解密抓包。优先证据包括：SDK 与应用日志、信令日志、PeerConnection 状态、ICE candidate pair、DTLS 状态、`getStats`、RTT、丢包率、jitter、码率、帧率、NACK/PLI、音频能量、设备状态和服务端指标。加密抓包仍可观察五元组、包长、时序、STUN/DTLS 握手、RTP/RTCP 流量形态、重传和网络异常。

### 场景 1：WebRTC 一直连接不上，怎么排查？

**先问什么**

- 是全部用户、某地区、某运营商，还是单设备失败？
- 失败稳定发生还是偶发？Wi-Fi、4G/5G、企业网结果是否不同？
- 卡在哪个状态：没有 Offer/Answer、ICE failed、DTLS failed，还是 connected 后又断开？

**需要的证据**

- 双端信令日志和完整 SDP，确认 Offer/Answer 是否成功设置。
- `iceGatheringState`、`iceConnectionState`、`connectionState`、候选列表和选中 candidate pair。
- TURN allocation 日志、鉴权错误、DNS/TLS 结果。
- 加密抓包中的 STUN Binding、DTLS Client Hello/Server Hello 和 UDP/TCP 可达性。

**分层定位**

1. 信令：检查房间路由、消息顺序、SDP 是否被截断、candidate 是否在 remote description 前丢失。
2. ICE：检查是否只有不可达 host、是否获得 srflx/relay、候选检查是否有响应。
3. DTLS：ICE connected 但没有 Client Hello，检查状态机；有握手但失败，检查 fingerprint、角色和 MTU/网络拦截。
4. 媒体：连接状态成功但无流量，不应继续当成建联失败，应转媒体排障。

**常见根因**

信令时序错误、TURN 不可用、对称 NAT、企业防火墙禁 UDP、IPv4/IPv6 不兼容、DTLS fingerprint 不一致或证书时间问题。

**临时止损与长期改进**

临时可强制 relay、切换 TURN/TLS 443、降级网络或重建 PeerConnection。长期应增加分阶段成功率、ICE 错误码、选中候选类型和 TURN 地域监控。

### 场景 2：连接成功但没有声音，怎么排查？

**先确定链路哪一段没有数据**

按“采集 → 编码发送 → 网络接收 → 解码 → 播放”逐段检查。不要只问用户是否听见声音。

**需要的证据**

- 本地 track 是否 enabled、muted，麦克风权限和 Audio Device Module 状态。
- 发送端 `outbound-rtp` 的 packetsSent、bytesSent、audioLevel。
- 接收端 `inbound-rtp` 的 packetsReceived、bytesReceived、packetsLost、jitter、audioLevel。
- codec 协商、操作系统输出设备、音量、路由和播放器状态。

**判断方法**

- bytesSent 不增长：采集、track、sender 或编码问题。
- 发送增长、接收不增长：网络、SFU 转发、订阅或 SSRC 映射问题。
- 接收增长、audioLevel 长期为 0：发送静音、采集无数据或解码前内容为空。
- audioLevel 正常但听不到：播放设备、系统路由、音量或渲染问题。

**加密抓包怎么用**

不能看音频内容，但能确认是否存在稳定的媒体包、包速率和方向；再与 `getStats` 对齐。实验中可以解密 Opus 用于理解链路，生产不能依赖这一步。

**临时止损与长期改进**

切换输入/输出设备、重建音频 track、重新订阅或重建连接。长期应在 SDK 日志中增加设备、track、codec、首包、首帧和音频能量埋点。

### 场景 3：单向音频怎么排查？

**核心方法**

把两个方向当成两条独立链路，分别记录 A outbound → B inbound 和 B outbound → A inbound，不能用“通话已连接”代替方向验证。

**排查步骤**

1. 检查双方 SDP 的 direction 属性是否为 `sendrecv`，transceiver 是否被设为 `sendonly/recvonly/inactive`。
2. 比较两端 outbound/inbound RTP 统计，定位断点在发送前、网络中还是接收后。
3. 检查 SFU publish/subscribe、用户权限、SSRC/MID 映射和转发策略。
4. 检查问题端的麦克风权限、Audio Device、系统路由和静音状态。
5. 若只有特定网络方向失败，检查 NAT 映射、防火墙和选中 candidate pair。

**常见根因**

一侧 track 未加入、协商方向错误、设备权限、SFU 未订阅、SSRC 映射错误、单方向 UDP 被限制。

**临时止损与长期改进**

重新协商或重建 track/订阅；长期在监控中按用户和方向展示 packets/bytes/audioLevel，避免只看房间级成功率。

### 场景 4：视频卡顿、花屏或频繁冻结怎么排查？

**先区分三类现象**

- 卡顿：帧到达不均匀、jitter buffer 增长或解码/渲染跟不上。
- 花屏：参考帧损坏、分片丢失或码流错误。
- 冻结：等待关键帧、解码器停滞或接收码率降到很低。

**需要的证据**

发送/接收码率、帧率、分辨率、QP、packetsLost、jitter、RTT、NACK、PLI/FIR、framesDropped、framesDecoded、freezeCount、解码耗时和 CPU/GPU。

**分层定位**

1. 网络：丢包、抖动和 RTT 是否同步升高，TWCC 估计是否降码率。
2. 发送：编码帧率、关键帧间隔和 CPU 是否异常。
3. 传输：NACK/RTX/FEC 是否生效，PLI 是否频繁。
4. 接收：framesReceived 正常但 framesDecoded 低，检查码流、profile 和解码器。
5. 渲染：decoded 正常但 rendered 低，检查主线程、GPU 和页面可见性。

**结合实验理解**

RED+VP8 被误按 H264 解析会产生“码流异常”，但生产卡顿更常见的是网络、关键帧恢复和设备性能问题，不能看到 FFmpeg 报错就直接断言编码格式错误。

**临时止损与长期改进**

降分辨率/帧率、切低层、请求关键帧、切 relay 或重建解码器。长期建立卡顿指标与网络、编码、解码事件的时间线关联。

### 场景 5：首帧慢或加入房间慢怎么排查？

**拆解耗时阶段**

```text
DNS/TCP/TLS/鉴权 → 加房 → Offer/Answer → ICE → DTLS → 发布/订阅 → 首个 RTP 包 → 首个关键帧 → 解码 → 渲染
```

**需要的证据**

每个阶段的开始/结束时间戳、候选类型、TURN 分配耗时、首包时间、首个可解码关键帧时间、解码和渲染时间。

**常见根因**

DNS 或 TLS 慢、信令排队、ICE 等待超时后才 fallback TURN、跨区域 TURN/SFU、订阅晚、关键帧间隔过长、PLI 未响应、解码器初始化慢。

**临时止损与长期改进**

预连接信令、就近调度 TURN/SFU、优化 ICE candidate pool、订阅时主动请求关键帧、缩短首个 GOP。长期必须把“进房耗时”拆成阶段指标，单一总耗时无法定位。

### 场景 6：只有部分地区、运营商或企业网络失败怎么排查？

**范围判断**

按地区、运营商、网络类型、IP 地址族、客户端版本和 TURN/SFU 节点聚合成功率，先确认是否有共同维度。

**需要的证据**

DNS 解析结果、路由/mtr、候选类型、选中节点、TURN 协议、TLS SNI/证书、端口可达性、丢包/RTT 和错误码。

**常见根因**

DNS 调度错误、跨地域路由、IPv6 黑洞、UDP 或特定端口被禁、企业代理、证书链不兼容、区域 TURN 容量或节点故障。

**加密抓包怎么用**

对比成功和失败样本的 DNS、STUN 响应、DTLS 握手位置、重传和五元组；即使没有明文，也能定位失败发生在哪个协议阶段。

**临时止损与长期改进**

切换备用域名、节点、IPv4、TURN/TLS 443。长期建立按网络维度的 SLI、主动探测和自动摘除异常节点机制。

### 场景 7：TURN 使用率突然升高怎么排查？

**先判断分子还是分母变化**

同时看总连接数、直连成功数、relay 连接数和 TURN allocation 结果。使用率上升可能是直连下降，也可能是某策略主动偏向 relay。

**检查方向**

- 客户端版本是否修改了 ICE transport policy、candidate filter 或超时。
- STUN 是否故障，host/srflx candidate 是否减少。
- 某运营商是否出现 UDP 限制或 NAT 行为变化。
- TURN 凭证、容量、地域调度和端口是否正常。
- 选中 pair 是否从 host/srflx 大量切到 relay，RTT 和质量是否同步变化。

**风险与止损**

TURN 使用率升高会增加带宽成本和节点压力，严重时形成容量连锁故障。临时扩容、切流和恢复 STUN/直连策略；长期监控 relay 原因、节点容量、分配失败率和每用户带宽。

### 场景 8：DataChannel 能建立但消息丢失或乱序怎么排查？

**需要确认的配置**

ordered、`maxRetransmits`、`maxPacketLifeTime`、消息大小、发送频率、`bufferedAmount`、DataChannel readyState 和双方协议版本。

**判断方法**

- 如果配置了无序或部分可靠，丢失/乱序可能是预期行为，先核对业务假设。
- reliable ordered 仍“丢消息”，检查应用消息 ID、去重、序列化、接收回调和断线重建，不要只看底层 SCTP。
- `bufferedAmount` 持续增长说明发送速度超过网络能力，可能影响延迟和内存。
- 大消息可能发生分片并造成明显队头阻塞，应限制大小或分块。

**结合实验理解**

实验中通过 PPID 和 TSN 观察 SCTP 消息，但真实生产通常无法解密 DTLS，应依赖应用消息 ID、发送/接收日志、buffer 指标和 DataChannel 配置。

**临时止损与长期改进**

降低发送频率、拆分大消息、增加业务 ACK/序号和重连恢复。长期为消息链路增加端到端成功率和延迟监控。

### 场景 9：客户只提供加密抓包，如何继续定位？

**明确不能做什么**

没有终端主动导出的 key 时，不能承诺还原 DTLS/SRTP 明文，也不能尝试从抓包“计算出”会话密钥。WebRTC 的安全设计就是避免旁路解密。

**仍然可以观察什么**

- DNS、TCP/TLS 信令连接和 WebSocket 流量时序，若信令本身也加密则结合服务端日志。
- STUN Binding 请求/响应、candidate 检查、重传和选中五元组。
- DTLS Client Hello、Server Hello、Certificate、Finished 是否完整，角色和握手耗时。
- 加密媒体包的方向、包长、速率、突发、间断、丢包迹象和路径 MTU 问题。
- TURN ChannelData/流量形态、TCP 重传、ICMP 和网络层错误。

**需要补充的证据**

请求同一时间窗口的双端 SDK 日志、`getStats` 周期采样、信令服务日志、房间/用户/trace ID、客户端版本、网络与设备信息。将抓包时间线与日志事件对齐。

**回答亮点**

实验解密的价值是知道密文内部各层在做什么，因此即使生产包不可解密，也能根据握手位置、包流形态和外部状态提出更准确的验证假设。

### 场景 10：如何把一次客户问题沉淀为知识库和自动化工具？

**知识库结构**

记录适用版本、症状、影响范围、前置条件、证据清单、判定步骤、根因、止损方案、长期修复、验证结果和不可公开的敏感信息。结论必须可以由证据复现，而不是只写最终答案。

**抽象工具的条件**

当问题重复出现、输入字段稳定、判断规则可解释且人工操作耗时时，适合自动化。工具输出应包含原始依据、规则版本和失败原因，避免黑盒判定。

**结合本项目**

项目把手工 Wireshark 过程沉淀为 `decrypt_session_pipeline.py` 和专题脚本，这种思路可迁移到生产日志分析；但生产工具还需脱敏、权限、审计、回归样本、性能和误判治理。

**推动共性改进**

向产品和研发提供问题频率、影响面、根因分布和复现条件，推动新增日志、指标、错误码、自诊断和配置保护。技术支持的价值不只是关单，还要减少同类问题再次发生。

## 13. CDN、HTTP、DNS 与流媒体协议

> 本章属于岗位理论扩展，不是当前 WebRTC 项目已经验证的生产经历。面试时应使用“理解原理、掌握排查方法”的口径。

### 扩展问题：DNS 解析异常如何导致拉流失败？

DNS 位于实际 HTTP、WebSocket 或媒体连接之前。错误记录、缓存未更新、地域/运营商调度偏差、AAAA 可解析但 IPv6 不通、TTL 不合理、Local DNS 劫持或 DoH 与系统 DNS 结果不同，都可能造成连接失败或被调度到远端节点。

排查时需要比较：客户端实际 DNS 结果、权威 DNS 结果、不同运营商递归结果、A/AAAA、TTL、CNAME 链、解析耗时和最终连接 IP。使用 `dig +trace` 看委派链，`dig @server` 对比不同 DNS；再用 `curl --resolve` 绕过 DNS 固定到指定 IP。如果固定 IP 成功而域名失败，才能把范围收敛到 DNS/调度，不能看到 `Could not resolve host` 之外的任何错误都归因于 DNS。

### 扩展问题：HTTP 缓存、Range 请求、状态码和回源有什么关系？

CDN 边缘节点先根据 cache key、缓存规则和有效期判断是否命中；未命中、过期或配置 bypass 时向源站回源。Range 请求让客户端按字节区间获取大文件，正确响应通常是 `206 Partial Content`，并带 `Content-Range`。如果源站或 CDN 不支持 Range，播放器 seek、分片并发和断点续传可能异常。

排查重点包括：状态码、`Age`、`Cache-Control`、`ETag`、`Last-Modified`、`Via/X-Cache`、`Content-Length/Content-Range`、首字节时间和回源日志。常见状态码：301/302 调度跳转，403 鉴权，404 资源或路径，416 Range 越界，5xx 源站/边缘错误。需要区分边缘返回还是源站返回，避免只看最终 HTTP code。

### 扩展问题：CDN 调度、缓存命中、回源和边缘节点故障怎么排查？

先按域名、资源、地区、运营商、节点 IP、状态码和时间窗口确定影响范围。然后比较成功与失败请求的 DNS/CDN 调度结果、边缘响应头、缓存命中状态、回源耗时与源站负载。

典型路径：

1. DNS 是否把用户调到合理的边缘节点。
2. 边缘节点是否健康、证书和端口是否正常。
3. cache key 是否错误导致低命中或串内容。
4. 未命中时回源网络、鉴权、Host、Range 和源站容量是否正常。
5. 故障是否只发生在某资源、某节点或所有节点。

临时止损可以摘除节点、切备用域名/源站、预热热点资源或回滚缓存规则。长期改进包括节点 SLI、回源保护、缓存命中率监控、变更审计和主动探测。

### 扩展问题：RTMP、HTTP-FLV、HLS 和 WebRTC 怎么比较？

| 协议 | 常见传输 | 典型时延 | 主要特点 | 适用场景 |
| --- | --- | --- | --- | --- |
| RTMP | TCP 长连接 | 约 1～3 秒 | 推流生态成熟，浏览器原生支持弱 | 直播推流、服务间传输 |
| HTTP-FLV | HTTP/TCP 长连接 | 约 1～3 秒 | 实现简单、延迟较低、弱网下有 TCP 队头阻塞 | Web 直播播放（需播放器） |
| HLS | HTTP 分片 | 通常数秒到十几秒；LL-HLS 更低 | CDN 友好、兼容性好、易缓存 | 大规模直播和点播 |
| WebRTC | ICE + UDP/TCP，SRTP | 通常数百毫秒 | 双向、拥塞控制、NAT 穿透，系统复杂 | 实时互动、会议、连麦 |

选择不是只看低延迟。互动性强时选 WebRTC；大规模单向分发更看重 CDN 成本和兼容性时选 HLS；RTMP 常用于采集推流。技术支持需要根据业务目标、终端、网络和成本判断，而不是认为 WebRTC 可以替代所有流媒体协议。

### 扩展问题：HLS 首帧慢、卡顿或 404 怎么排查？

先拆成播放地址获取、Master Playlist、Media Playlist、首个分片下载、解复用、解码和渲染。首帧慢常见于 DNS/TLS、播放列表层级、等待新分片、GOP 过长、首分片大、跨区调度和播放器缓冲策略。卡顿要看分片下载时间是否超过分片时长、带宽估计、码率切换、buffer level 和解码性能。404 要区分播放列表不存在、分片已从滑动窗口移除、发布/缓存时序、路径或鉴权参数错误。

需要收集每个 URL、状态码、DNS/connect/TLS/TTFB/download 耗时、响应头、playlist 内容、media sequence、target duration、分片大小、播放器 buffer 和 CDN 节点。使用 `curl -v`、`curl -w` 和 `ffprobe` 分别验证网络与媒体层。

## 14. Linux 与日志排障

> 本章属于岗位理论扩展。重点不是背命令参数，而是知道每条命令验证哪个假设。

### 网络与协议工具

| 工具 | 验证的问题 | 常用示例 |
| --- | --- | --- |
| `dig` / `nslookup` | 域名解析、A/AAAA、CNAME、TTL、指定 DNS 差异 | `dig example.com A`、`dig @8.8.8.8 example.com` |
| `curl` | DNS、TCP、TLS、HTTP 状态、响应头和阶段耗时 | `curl -v -o /dev/null -w '%{time_connect} %{time_starttransfer}\n' URL` |
| `ss` | 监听端口、TCP/UDP socket、连接状态与队列 | `ss -lntup`、`ss -s` |
| `tcpdump` | 抓取指定主机、端口和协议的网络包 | `sudo tcpdump -i any host 1.2.3.4 and udp -w issue.pcap` |
| `ping` | 基础 ICMP 连通性与 RTT；被禁时不能据此判死 | `ping -c 10 host` |
| `mtr` | 路径上的时延和丢包趋势 | `mtr -rwzc 100 host` |

排障时先记录时间、时区、机器、网络接口和命令，确保可以和服务端日志对齐。抓包必须控制范围和时长，并遵守用户隐私、密钥和业务数据的合规要求。

### 系统资源与服务日志

| 工具 | 观察内容 | 判断注意点 |
| --- | --- | --- |
| `top` / `ps` | CPU、线程、进程状态 | 总 CPU 正常不代表单核或单线程正常 |
| `free`（Linux）/ `vm_stat`（macOS） | 内存、缓存和 swap | 不要把 page cache 简单当内存泄漏 |
| `iostat` | 磁盘吞吐、延迟和利用率 | 音视频录制、日志暴涨可能造成 I/O 抖动 |
| `journalctl` | systemd 服务日志和启动失败 | 用时间窗口、unit、trace ID 缩小范围 |
| `grep` / `awk` / `sed` | 筛选、聚合和规范化日志 | 保留原始日志，脚本输出要可回溯 |

示例排障顺序：服务不可达时先用 `ss` 确认是否监听，再用 `curl` 从本机和远端验证，随后看 `journalctl -u service --since ...`，最后根据需要抓 `tcpdump`。CPU 高时先定位进程和线程，再关联请求量、编码参数、日志与版本变更，不能直接重启后结束分析。

### 日志分析应该具备哪些字段？

音视频技术支持最需要的是可关联性。日志至少应包含时间戳与时区、客户端/SDK 版本、设备/系统、用户/房间/会话/trace ID、信令阶段、ICE/DTLS 状态、选中候选对、codec、SSRC/MID、错误码和关键质量统计。敏感字段需要脱敏，日志级别和采样率应可动态调整。

好的日志回答“谁在什么时候、哪个版本、哪个阶段、发生了什么、上下文是什么”；好的指标回答“影响面多大、从什么时候开始、集中在哪个维度”。两者结合才能从个案走向共性问题。

## 15. 模拟面试

### 模拟 1：请介绍一下这个项目

**候选人回答**

这是我为了系统理解 WebRTC 原理做的个人实验项目。我搭建了 Mac Native、浏览器和 Node.js 信令服务，走通音频与 DataChannel，再从抓包中分析 Offer/Answer、Trickle ICE、DTLS、SRTP/RTP 和 SCTP。在可控环境里我主动导出 key 验证加密后的协议层次，并用 Python、tshark 和 FFmpeg 做自动分析。典型案例是从 SDP 和 RTP 负载定位到视频不是 H264，而是 RED 外层封装的 VP8。这个项目体现的是原理理解和工具沉淀，不是生产解密平台。

**面试官可能追问**

- 你具体写了哪些代码？
- 哪个问题最难，怎么证明根因？

**回答重点**

指向 `webrtc-web`、Native 工程、Python 脚本和 RED+VP8 案例，不要只列协议名。

### 模拟 2：为什么做这个项目，而不是直接看文档？

**候选人回答**

文档能说明协议定义，但很难建立时序和因果关系。我通过实际互通把信令消息、SDP 字段、ICE candidate、DTLS role 和最终 UDP 端口对应起来。例如 SDP 中 Native Answer 是 `setup:active`，抓包 3383 确实由 Native 发 Client Hello。实验让我能从证据验证理解，也暴露了 RED+VP8 这类只看概念不容易遇到的问题。

**面试官可能追问**

- 如果重新做一次，你会增加什么？

**回答重点**

补 TURN、多网络弱网、`getStats` 时间线、RTCP/TWCC、自动化回归样本和敏感数据治理。

### 模拟 3：请完整描述一次 WebRTC 建联

**候选人回答**

双方先通过业务信令交换 Offer/Answer，协商媒体、codec、ICE 参数、DTLS fingerprint 和角色；同时 Trickle ICE 收集并交换 host/srflx/relay candidate。ICE 组成候选对并执行 STUN connectivity check，提名可用 pair。随后在选中路径上完成 DTLS 握手、校验证书 fingerprint，并派生 SRTP key。媒体通过 SRTP/SRTCP 传输，DataChannel 通过 SCTP over DTLS 传输。之后拥塞控制、RTCP 反馈、NACK/PLI 等持续参与质量调节。

**面试官可能追问**

- 哪些步骤可以并行？
- ICE connected 和 PeerConnection connected 为什么可能时间不同？

**回答重点**

说明信令、ICE gathering 可交错，Trickle ICE 减少等待；连接状态是多个 transport 状态的聚合。

### 模拟 4：你看 SDP 时最关注哪些字段？

**候选人回答**

先看每个 `m=` 段和 direction，确认媒体类型是否被拒绝；再看 `rtpmap/fmtp/rtcp-fb` 确认 codec 与反馈；看 MID/BUNDLE 判断复用；看 ICE ufrag/pwd 和 candidate；看 fingerprint/setup 判断 DTLS 身份与角色；DataChannel 还要看 `sctp-port` 和 max-message-size。不能只看 codec，因为建联失败常发生在 ICE 或 DTLS。

**面试官可能追问**

- PT 96 为什么不能直接认为是 VP8？

**回答重点**

动态 PT 的语义由当前 SDP 映射决定，会话之间可以不同。

### 模拟 5：ICE 和 TURN 你怎么理解？

**候选人回答**

ICE 是候选收集、连通性检查和路径提名框架；STUN 帮助发现 NAT 映射并做检查；TURN 在直连失败时中继。排障时我会看 candidate 是否完整、check 是否有响应、最终选中 host/srflx/relay 哪一类，以及 TURN allocation、鉴权、地域和协议。TURN 不是越多越好，它提升成功率但增加成本和时延。

**面试官可能追问**

- 有 srflx 为什么仍然连接不上？

**回答重点**

候选存在不等于对端可达，对称 NAT、防火墙、地址族和路由仍可能失败。

### 模拟 6：DTLS 和 SRTP 是什么关系？

**候选人回答**

DTLS 在 ICE 选中的路径上完成身份验证和密钥协商，并通过 DTLS-SRTP exporter 派生 client/server 两个方向的 SRTP key。音视频不会逐包封装在 DTLS 中，而是走 SRTP；DataChannel 才是 SCTP over DTLS。SDP fingerprint 用来校验握手证书，setup 决定谁发 Client Hello。

**面试官可能追问**

- 为什么方向 key 映射错误会只解出一侧？

**回答重点**

一个端的发送 key 对应对端接收 key，映射由 DTLS role 决定，错误会导致 SRTP 认证失败。

### 模拟 7：为什么真实工作中的网络包通常无法解密？

**候选人回答**

WebRTC 使用 DTLS 协商密钥，再保护 SRTP 和 DataChannel。旁路抓包没有终端内存中的密钥材料，不能从流量逆推出会话 key，这正是安全目标。我的实验通过修改可控客户端主动导出 key，只用于理解协议。生产排障会结合 SDK 日志、`getStats`、信令、状态、服务端指标和加密包的时序/流量形态，而不会承诺解密客户抓包。

**面试官可能追问**

- 加密抓包还有什么价值？

**回答重点**

可观察 DNS、STUN、DTLS 握手、五元组、包速率、方向、重传、MTU 和网络错误，并与日志时间线对齐。

### 模拟 8：用户反馈没有声音，你会怎么处理？

**候选人回答**

先确认范围和方向，再按采集、发送、网络接收、解码、播放逐段检查。看 track/权限/设备状态，看 outbound bytes 和 audioLevel 是否增长，再看对端 inbound bytes、loss、jitter 和 audioLevel。发送不增长查采集和 sender；发送增长接收不增长查网络/SFU/订阅；接收和 audioLevel 正常但听不到查播放路由。临时可切设备、重建 track 或连接，长期补首包、音频能量和设备埋点。

**面试官可能追问**

- 单向音频与完全无声音有什么不同？

**回答重点**

单向音频必须把 A→B 和 B→A 两条链路分别比较，特别检查 direction、权限、订阅和方向性网络问题。

### 模拟 9：视频卡顿你会看哪些指标？

**候选人回答**

我会把卡顿拆成网络、发送编码、传输恢复、接收解码和渲染。网络看 RTT、loss、jitter、available bitrate；传输看 NACK、RTX、PLI/FIR；发送看码率、帧率、分辨率和 CPU；接收看 framesReceived/Decoded/Dropped、freezeCount 和解码耗时。要把这些指标放在同一时间线，避免看到丢包就直接下结论。

**面试官可能追问**

- 丢包低但卡顿高是什么原因？

**回答重点**

检查 jitter、突发延迟、码率过高、关键帧、解码性能、主线程/GPU 和渲染调度。

### 模拟 10：讲一下 RED + VP8 的案例

**候选人回答**

SRTP 解密后，我最初把视频按 H264 解析，但 NAL type 异常且 FFmpeg 无法解码。我没有继续猜 key，而是回到 SDP，看到 PT 123 映射为 RED/90000，内部主编码是 VP8。RED 有自己的 block header，VP8 还有 RTP payload descriptor，直接按 H264 NAL header 解析必然错误。我增加 RED 解包和 VP8 描述符剥离，按 timestamp/marker 组帧，写 IVF 后再用 FFmpeg 转 MP4。这个案例说明排障要先确认协议和负载语义，再检查实现。

**面试官可能追问**

- 如何证明不是 SRTP key 错误？

**回答重点**

SRTP 认证成功、RTP 头和序列连续；错误集中在 payload 解释，且 SDP 映射与正确解析结果相互验证。

### 模拟 11：你对 FFmpeg 熟悉到什么程度？

**候选人回答**

我熟悉常用命令和音视频处理流程，理解 demux/decode/filter/encode/mux，能用 ffprobe 检查 codec、time base、码率和错误，用 FFmpeg 做抽流、转封装、转码和 WAV/MP4 输出。我还学习过 Android NDK/JNI 集成相关项目。但我不会把这描述成独立实现了 FFmpeg 内核或完整播放器，当前强项是利用 FFmpeg 辅助定位媒体格式和码流问题。

**面试官可能追问**

- 转码和转封装有什么区别？

**回答重点**

转封装不重新编码，主要改变容器；转码经过解码/编码，会改变 codec 或参数并增加成本和质量损失。

### 模拟 12：HLS、RTMP 和 WebRTC 如何选？

**候选人回答**

互动会议、连麦需要亚秒级双向通信和拥塞控制，优先 WebRTC；大规模单向分发看重 CDN、终端兼容和成本，常用 HLS；RTMP 常用于主播到平台的推流链路；HTTP-FLV 可用于较低延迟播放但浏览器需播放器支持。选择需要平衡时延、互动性、规模、网络、终端和成本，不是协议越新越好。

**面试官可能追问**

- HLS 为什么通常延迟高？

**回答重点**

分片生成、playlist 更新、下载和播放器 buffer 共同产生延迟；LL-HLS 通过 partial segment 等机制降低延迟。

### 模拟 13：客户说某地区播放失败，你怎么判断是不是 CDN？

**候选人回答**

先按地区、运营商、域名、资源、节点 IP 和状态码确认聚集性。对比 DNS 调度、边缘响应头、缓存命中、回源耗时和源站结果；用 `curl --resolve` 固定节点，区分 DNS、边缘和源站。若固定某节点失败、其他节点成功，且同节点错误率升高，才有证据指向边缘节点。临时摘除节点或切备用域名，长期补主动探测和分维度 SLI。

**面试官可能追问**

- 404 一定是源站没有文件吗？

**回答重点**

不一定，可能是边缘负缓存、HLS 滑动窗口、路径/鉴权、发布与缓存时序或错误回源 Host。

### 模拟 14：为什么用 Python 做分析工具？

**候选人回答**

Python 适合快速编排 tshark、Scapy、pylibsrtp 和 FFmpeg，把重复的端口识别、流统计、媒体导出和日志生成固定下来。工具输出必须保留帧号、SSRC/PT、命令和失败原因，让结论可回到原始证据验证。生产化时还要补回归样本、性能、超时、错误码、脱敏和审计，不能把实验脚本直接当线上工具。

**面试官可能追问**

- 如何测试抓包分析工具？

**回答重点**

维护小型已知样本和期望摘要，覆盖正常、缺 key、错 key、乱序、丢包、多 SSRC、不同 codec，并对 tshark/FFmpeg 版本做兼容验证。

### 模拟 15：技术支持如何推动共性问题改进？

**候选人回答**

先把单次问题记录成可复现证据链，再按错误码、版本、地区、设备和网络聚合，确认它是个案还是共性问题。向产品和研发提供影响面、频率、根因分布、复现条件和建议优先级；短期提供止损，长期推动新增日志、指标、自诊断、配置保护和自动化检查。发布后用相同指标验证问题率是否下降。支持专家的价值不只是解决当前客户问题，而是降低同类问题的重复成本。

**面试官可能追问**

- 研发认为无法复现时怎么办？

**回答重点**

补齐最小复现环境、时间线、原始证据、版本和对照组；把争论从观点变成可以验证的假设。

## 16. 一周复习计划

### Day 1：项目讲稿与 WebRTC 全流程

**学习内容**

- 熟悉第 1～5 章，能不看文档描述 Signaling → ICE → DTLS/SRTP → RTP/SCTP。
- 对照 `native2web-pcap-analysis.md` 记住 Offer/Answer 方向、3383 帧和最终 UDP 端口。

**口述练习**

- 分别讲一遍一分钟和三分钟项目介绍。
- 回答模拟 1～3，不允许只堆协议名。

**当天产出**

- 录制一份三分钟项目讲解。
- 写出一张 WebRTC 建联时序图和项目证据索引。

### Day 2：SDP、ICE、STUN、TURN 与 NAT

**学习内容**

- 复习 `m=`、rtpmap/fmtp、MID、BUNDLE、PT、SSRC、fingerprint、setup。
- 理解 host/srflx/relay、candidate pair、STUN check 和 TURN fallback。

**口述练习**

- 拿项目 SDP 逐行解释关键字段。
- 回答“有 srflx 为什么仍连不上”和“TURN 使用率为何升高”。

**当天产出**

- 一张 SDP 字段速查表。
- 一张 ICE 建联失败排障树。

### Day 3：DTLS、SRTP、RTP、RTCP 与 DataChannel

**学习内容**

- 复习 DTLS role、fingerprint、DTLS-SRTP key 派生和双向 key 映射。
- 理解 RTP sequence/timestamp/SSRC、RTCP SR/RR/NACK/PLI/FIR/TWCC。
- 理解 SCTP over DTLS、ordered 和部分可靠性。

**口述练习**

- 解释为什么真实抓包不能解密，但仍然有分析价值。
- 用项目的 active/actpass 和 PPID/TSN 作为证据回答。

**当天产出**

- 一张 DTLS/SRTP/RTP/DataChannel 分层图。
- 完成模拟 6、7、8。

### Day 4：H264、VP8、Opus、RED 与 FFmpeg

**学习内容**

- 复习 Single NAL、STAP-A、FU-A、VP8 descriptor、RED header。
- 复习 Opus PLC/FEC、转码和转封装、IVF/Annex-B/Ogg/MP4 的角色。

**口述练习**

- 完整讲 RED + VP8 案例，说明如何排除错 key。
- 回答“你对 FFmpeg 熟悉到什么程度”，守住能力边界。

**当天产出**

- 用 `ffprobe` 分析一个视频和一个音频样本并记录字段。
- 完成模拟 10、11。

### Day 5：技术支持场景排障

**学习内容**

- 复习建联失败、无声音、单向音频、卡顿、首帧慢和区域网络问题。
- 熟悉 `getStats` 中 candidate pair、inbound/outbound RTP 和质量字段。

**口述练习**

- 每个场景严格按“范围 → 证据 → 分层 → 假设 → 止损 → 改进”回答。
- 练习在没有明文抓包时向客户索取最小证据集。

**当天产出**

- 画一张无声音排障表和一张卡顿指标时间线。
- 完成模拟 8、9、15。

### Day 6：CDN、DNS、HTTP、HLS、RTMP 与 Linux

**学习内容**

- 复习 DNS 调度、CDN 缓存/回源、Range、HLS playlist/segment。
- 复习 HLS、HTTP-FLV、RTMP、WebRTC 的取舍。
- 熟悉 `dig`、`curl`、`ss`、`tcpdump`、`mtr`、`journalctl` 的验证目标。

**口述练习**

- 回答某地区播放失败和 HLS 首帧慢。
- 明确这些是岗位理论扩展，不虚构生产经历。

**当天产出**

- 一张流媒体协议对比表。
- 一份拉流失败的 Linux 命令检查清单。

### Day 7：完整模拟与薄弱项回补

**学习内容**

- 复盘所有标记不熟的题，只补影响主线的问题。
- 检查简历、项目讲稿和口头回答是否一致。

**口述练习**

- 连续完成 15 轮模拟面试并计时。
- 每个问题先给 30 秒结论，再接受两层追问。

**当天产出**

- 一次完整录音和自评表。
- 最终版项目三条描述、三分钟讲稿和不会问题的回答模板。

## 17. 面试表达边界

### 可以明确表达

- 在可控实验环境中修改 WebRTC、主动导出 key，用于验证 DTLS/SRTP 和上层协议。
- 能用 Wireshark、tshark、Python 和 FFmpeg 分析实验抓包、RTP 负载和媒体格式。
- 理解 WebRTC 建联、音视频质量指标和按层排障方法。
- 学习过 FFmpeg Android、NDK/JNI、编解码和封装处理流程。
- 理解 CDN、DNS、HTTP、HLS、RTMP 和 Linux 的基础排查方法。

### 不应夸大的内容

- 不说“可以解密客户或真实线上 WebRTC 抓包”。
- 不说“做过生产 WebRTC 解密平台”或“负责过大规模 RTC/CDN 稳定性”。
- 不说“独立实现 FFmpeg 播放器内核”或“精通编解码优化”。
- 没有实际生产案例时，不编造客户规模、故障率、性能提升百分比或收入影响。

### 不会的问题怎么回答

使用“已知事实 → 当前判断 → 验证方法”的结构：

> 这个场景我没有直接的生产实践。基于我对协议的理解，已知现象更可能落在 A 或 B 两层。我会先收集 X、Y、Z 证据验证；如果 X 成立则继续检查……，如果不成立则转向……。我不会在缺少数据时直接判断根因。

这样的回答比猜一个名词更符合技术支持岗位：承认边界，同时展示分层思考、证据意识和推进问题的能力。

### 面试前最终检查

- 项目介绍中是否主动说清“个人学习实验”。
- 是否能解释为什么生产抓包不能解密。
- 每个项目结论能否指出文档、帧号、SDP 字段或脚本作为证据。
- 是否能把实验知识迁移成日志、指标和状态驱动的生产排障方法。
- 是否区分“做过”“理解”“熟悉工具”和“计划验证”。
