# WebRTC SDP 交互信息分析

## 概述

本文档详细分析 `过滤过的_lan_test.pcapng` 中 SDP Offer/Answer 交换所包含的所有信息，展示 WebRTC 连接建立过程中双方协商的关键参数。

**抓包文件**: `过滤过的_lan_test.pcapng`  
**分析工具**: Wireshark/tshark  
**捕获时间**: 2026-03-14  

---

## 抓包文件帧号索引

### 信令流程帧号对照表

| 阶段 | 帧号 | 时间戳 | 描述 |
|------|------|--------|------|
| **注册阶段** | | | |
| peer1 注册请求 | 6 | 38.781781s | POST /register (192.168.50.117 → 192.168.50.20:28080) |
| peer1 注册响应 | 8 | 38.782348s | HTTP 200 OK |
| peer2 注册请求 | - | - | (在捕获前已完成) |
| peer2 注册响应 | - | - | (在捕获前已完成) |
| **轮询阶段** | | | |
| peer2 轮询请求 | 17 | 39.790774s | GET /poll?peerId=peer2 |
| peer2 轮询响应 | 20 | 39.791655s | HTTP 200 OK (包含 Offer + candidates) |
| **Candidate 交换** | | | |
| peer2 发送 candidate | 24 | 39.809315s | POST /signal (192.168.50.117:54917) |
| 服务器确认 | 26 | 39.809973s | HTTP 200 OK |
| peer2 发送 candidate | 113 | 39.818942s | POST /signal |
| 服务器确认 | 122 | 39.819463s | HTTP 200 OK |
| peer2 发送 candidate | 161 | 39.826260s | POST /signal |
| 服务器确认 | 164 | 39.826429s | HTTP 200 OK |
| ... | ... | ... | 共 22 个 candidate 消息 |
| peer2 发送 Answer | - | ~39.93s | POST /signal (包含完整 Answer SDP) |
| **ICE 连通性检查** | | | |
| STUN 请求 | 22 | 39.809312s | peer2 → peer1 (54917 → 51467) |
| STUN 请求 | 23 | 39.809313s | peer2 → peer1 (54543 → 49308) |
| ... | ... | ... | 大量 STUN Binding Request/Response |
| **DTLS 握手** | | | |
| DTLS ClientHello | 778 | 41.000366s | DTLS 握手开始 |
| DTLS ServerHello | 799 | 41.001106s | DTLS 握手响应 |
| DTLS 证书交换 | 958 | 41.018808s | Certificate, KeyExchange |
| DTLS 完成 | 960-962 | 41.024s | ChangeCipherSpec, Finished |
| **数据传输** | | | |
| DTLS 应用数据 | 961+ | 41.024s+ | 加密数据传输 |

---

## 1. 基础会话信息

### 1.1 SDP 标准字段

| 字段 | Offer (peer1) | Answer (peer2) | 含义 |
|------|---------------|----------------|------|
| **v=0** | ✓ | ✓ | SDP 版本，当前为 0 |
| **o=-** `<sess-id>` `<sess-version>` | `5950554900919706858` `1773461645` | `1436474565721902609` `1773461685` | 会话ID和版本号 |
| **s=-** | ✓ | ✓ | 会话名称为空（-） |
| **t=0 0** | ✓ | ✓ | 会话时间：0 0 表示永久 |

### 1.2 会话发起者解析

```
o=- 5950554900919706858 1773461645 IN IP4 0.0.0.0
  │  │                      │          │  │   │
  │  │                      │          │  │   └── 地址：0.0.0.0（占位符）
  │  │                      │          │  └────── 地址类型：IPv4
  │  │                      │          └───────── 网络类型：Internet
  │  │                      └──────────────────── 会话版本号
  │  └─────────────────────────────────────────── 会话ID（64位随机数）
  └────────────────────────────────────────────── 用户名（- 表示无）
```

**关键观察**：
- 会话ID是64位随机数，确保全局唯一
- 地址使用 `0.0.0.0` 占位，实际地址由 ICE 候选者决定
- 版本号递增，用于检测 SDP 更新

---

## 2. ICE (Interactive Connectivity Establishment) 信息

### 2.1 ICE 凭证

ICE 凭证用于 STUN/TURN 消息的认证和完整性校验。

#### Offer (peer1) 的 ICE 凭证

**来源帧**: 帧 20 (HTTP 响应体中包含 Offer SDP)  
**发送方**: peer1 (192.168.50.20)  
**接收方**: peer2 (192.168.50.117)

```sdp
a=ice-ufrag:bPahAMSGWLoWrceI
a=ice-pwd:IiInJBjURljFzErWzkAYjXZxRyHKkrkf
```

| 属性 | 值 | 说明 |
|------|-----|------|
| **ice-ufrag** | `bPahAMSGWLoWrceI` | 用户名片段，16字符随机字符串 |
| **ice-pwd** | `IiInJBjURljFzErWzkAYjXZxRyHKkrkf` | 密码，24字符随机字符串 |

#### Answer (peer2) 的 ICE 凭证

**来源帧**: 帧 24 HTTP 请求体中包含 Answer SDP（在导出数据中可见）  
**发送方**: peer2 (192.168.50.117)  
**接收方**: peer1 (192.168.50.20)

```sdp
a=ice-ufrag:IKtZGDWSgVWahSSe
a=ice-pwd:flYBUyWRztIggJopdUFXvRxerFwZhNKj
```

| 属性 | 值 | 说明 |
|------|-----|------|
| **ice-ufrag** | `IKtZGDWSgVWahSSe` | 用户名片段，16字符随机字符串 |
| **ice-pwd** | `flYBUyWRztIggJopdUFXvRxerFwZhNKj` | 密码，24字符随机字符串 |

#### ICE 凭证的使用方式

```
STUN Binding Request:
├── USERNAME: bPahAMSGWLoWrceI:IKtZGDWSgVWahSSe
│              │                │
│              │                └── 对端的 ufrag
│              └── 本地的 ufrag
│
└── MESSAGE-INTEGRITY: HMAC-SHA1(ice-pwd, message)
                       │
                       └── 使用本地 ice-pwd 计算签名
```

**安全特性**：
- 双方使用各自的 ice-pwd 计算和验证 HMAC
- 只有知道对方 ice-pwd 才能生成有效的 STUN 响应
- 防止中间人攻击和消息篡改

---

### 2.2 ICE 候选者

#### peer1 的候选者（Offer 中包含）

**来源帧**: 帧 20 (HTTP 响应体)  
**发送方**: peer1 (192.168.50.20)  
**收集方式**: 通过 STUN 服务器 (74.125.250.129:19302) 获取 srflx 候选者

```sdp
; IPv6 主机候选者
a=candidate:1454950769 1 udp 2130706431 fdc7:60ad:2e14:498f:1037:9e8f:aaa2:a04c 49308 typ host ufrag bPahAMSGWLoWrceI
a=candidate:1454950769 2 udp 2130706431 fdc7:60ad:2e14:498f:1037:9e8f:aaa2:a04c 49308 typ host ufrag bPahAMSGWLoWrceI

; IPv4 主机候选者（内网）
a=candidate:3573374140 1 udp 2130706431 192.168.50.20 51467 typ host ufrag bPahAMSGWLoWrceI
a=candidate:3573374140 2 udp 2130706431 192.168.50.20 51467 typ host ufrag bPahAMSGWLoWrceI

; 另一个内网接口
a=candidate:31838006 1 udp 2130706431 10.251.1.1 63603 typ host ufrag bPahAMSGWLoWrceI
a=candidate:31838006 2 udp 2130706431 10.251.1.1 63603 typ host ufrag bPahAMSGWLoWrceI

; 服务器反射候选者（公网地址）
a=candidate:728573177 1 udp 1694498815 124.77.234.173 58571 typ srflx raddr 0.0.0.0 rport 58571 ufrag bPahAMSGWLoWrceI
a=candidate:728573177 2 udp 1694498815 124.77.234.173 58571 typ srflx raddr 0.0.0.0 rport 58571 ufrag bPahAMSGWLoWrceI

; 候选者结束标记
a=end-of-candidates
```

#### peer1 候选者汇总

| Foundation | Component | Transport | Priority | Address | Port | Type | 说明 |
|------------|-----------|-----------|----------|---------|------|------|------|
| 1454950769 | 1 | udp | 2130706431 | fdc7:60ad:2e14:498f:1037:9e8f:aaa2:a04c | 49308 | host | IPv6 主机地址 |
| 1454950769 | 2 | udp | 2130706431 | fdc7:60ad:2e14:498f:1037:9e8f:aaa2:a04c | 49308 | host | IPv6 主机地址（RTCP） |
| 3573374140 | 1 | udp | 2130706431 | 192.168.50.20 | 51467 | host | IPv4 内网地址 |
| 3573374140 | 2 | udp | 2130706431 | 192.168.50.20 | 51467 | host | IPv4 内网地址（RTCP） |
| 31838006 | 1 | udp | 2130706431 | 10.251.1.1 | 63603 | host | 另一个内网接口 |
| 31838006 | 2 | udp | 2130706431 | 10.251.1.1 | 63603 | host | 另一个内网接口（RTCP） |
| 728573177 | 1 | udp | 1694498815 | 124.77.234.173 | 58571 | srflx | 公网反射地址 |
| 728573177 | 2 | udp | 1694498815 | 124.77.234.173 | 58571 | srflx | 公网反射地址（RTCP） |

#### peer2 的候选者（通过单独 candidate 消息发送）

**来源帧**: 帧 24, 113, 122, 161, 188, 213, 241, 252, 263, 275, 286, 297, 308, 319, 330, 341, 352, 364, 376... (共 22 个 HTTP POST /signal 请求)
**发送方**: peer2 (192.168.50.117)
**接收方**: peer1 (192.168.50.20)
**传输方式**: 逐个通过 HTTP POST 发送

```sdp
; 主 IPv4 地址
a=candidate:2393729669 1 udp 2130706431 192.168.50.117 54917 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:2393729669 2 udp 2130706431 192.168.50.117 54917 typ host ufrag IKtZGDWSgVWahSSe

; 多个 IPv6 地址（Docker 容器网络）
a=candidate:1946485821 1 udp 2130706431 fdc7:60ad:2e14:498f:87e:569e:b945:c980 45034 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:2708684109 1 udp 2130706431 fdc7:60ad:2e14:498f:d19f:f776:ef54:f051 36369 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:3129754946 1 udp 2130706431 fdc7:60ad:2e14:498f:1abc:5213:69b5:b44a 58343 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:1404487895 1 udp 2130706431 fdc7:60ad:2e14:498f:56b2:3ff:fe04:78a9 46147 typ host ufrag IKtZGDWSgVWahSSe

; 多个 Docker 网桥接口
a=candidate:3114607224 1 udp 2130706431 192.168.49.1 57192 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:233762139 1 udp 2130706431 172.17.0.1 37470 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:3308009161 1 udp 2130706431 172.19.0.1 44757 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:3528925834 1 udp 2130706431 172.18.0.1 48139 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:2193111953 1 udp 2130706431 172.20.0.1 36197 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:2890797847 1 udp 2130706431 172.22.0.1 39059 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:4053942811 1 udp 2130706431 172.26.0.1 42930 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:3140814676 1 udp 2130706431 172.23.0.1 50737 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:3746851485 1 udp 2130706431 172.24.0.1 55410 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:3358555870 1 udp 2130706431 172.25.0.1 41199 typ host ufrag IKtZGDWSgVWahSSe
a=candidate:2512596946 1 udp 2130706431 172.21.0.1 52966 typ host ufrag IKtZGDWSgVWahSSe

; 公网反射地址
a=candidate:728573177 1 udp 1694498815 124.77.234.173 45427 typ srflx raddr 0.0.0.0 rport 45427 ufrag IKtZGDWSgVWahSSe
a=candidate:728573177 2 udp 1694498815 124.77.234.173 45427 typ srflx raddr 0.0.0.0 rport 45427 ufrag IKtZGDWSgVWahSSe

a=end-of-candidates
```

#### peer2 候选者汇总（共 22 个）

| 类型 | 数量 | 地址范围 | 说明 | 对应帧号 |
|------|------|----------|------|----------|
| **host IPv4** | 2 | 192.168.50.117, 192.168.49.1 | 主机地址 | 24, 113, 122, 161... |
| **host IPv6** | 7 | fdc7:60ad:2e14:498f:* | Docker 容器 IPv6 | 24, 188, 213... |
| **host Docker** | 11 | 172.17.x.x - 172.26.x.x | Docker 网桥接口 | 241, 252, 263... |
| **srflx** | 2 | 124.77.234.173:45427 | 公网反射地址 | 376... |

#### 候选者格式详解

```
candidate:<foundation> <component-id> <transport> <priority> <connection-address> <port> typ <cand-type> [raddr <rel-addr>] [rport <rel-port>] ufrag <username>

示例：
candidate:3573374140 1 udp 2130706431 192.168.50.20 51467 typ host ufrag bPahAMSGWLoWrceI
          │            │ │   │          │             │      │    │     │
          │            │ │   │          │             │      │    │     └── ufrag
          │            │ │   │          │             │      │    └── 候选者类型
          │            │ │   │          │             │      └── typ 关键字
          │            │ │   │          │             └── 端口
          │            │ │   │          └── IP 地址
          │            │ │   └── 优先级
          │            │ └── 传输协议
          │            └── 组件ID (1=RTP, 2=RTCP)
          └── foundation (唯一标识符)
```

#### 候选者优先级计算

```
priority = (2^24) * (type preference) + (2^8) * (local preference) + (256 - component ID)

类型优先级：
- host:    126 (最高)
- srflx:   100
- prflx:   110
- relay:   0   (最低)

示例计算（host 候选者）：
priority = (2^24) * 126 + (2^8) * 65535 + (256 - 1)
         = 2113929216 + 16776960 + 255
         = 2130706431
```

---

## 3. DTLS (Datagram Transport Layer Security) 信息

### 3.1 证书指纹

证书指纹用于验证对端 DTLS 证书的真实性，防止中间人攻击。

#### Offer (peer1) 的指纹

```sdp
a=fingerprint:sha-256 15:66:65:AB:01:DD:2B:9E:27:A3:7E:A4:7E:CC:8F:82:CF:27:74:9F:E8:5C:42:6C:8A:D1:88:ED:3C:88:B4:87
```

**指纹值**：`15:66:65:AB:01:DD:2B:9E:27:A3:7E:A4:7E:CC:8F:82:CF:27:74:9F:E8:5C:42:6C:8A:D1:88:ED:3C:88:B4:87`

#### Answer (peer2) 的指纹

```sdp
a=fingerprint:sha-256 BB:AB:25:87:64:1A:E4:C8:7B:FD:A2:05:AB:11:ED:B2:43:53:94:72:4D:A9:B1:C5:06:4C:11:E9:AF:D2:79:1F
```

**指纹值**：`BB:AB:25:87:64:1A:E4:C8:7B:FD:A2:05:AB:11:ED:B2:43:53:94:72:4D:A9:B1:C5:06:4C:11:E9:AF:D2:79:1F`

#### 指纹验证过程

```
DTLS 握手时：
1. peer1 发送 Certificate 消息，包含 X.509 证书
2. peer2 计算证书的 SHA-256 哈希
3. peer2 比对哈希值与 SDP 中的 fingerprint
4. 如果匹配，确认对端身份；如果不匹配，终止连接
```

### 3.2 DTLS 角色协商

#### setup 属性

```sdp
; Offer
a=setup:actpass     ; 可以是主动或被动

; Answer
a=setup:active      ; 选择主动
```

#### 角色确定规则

| Offer | Answer | 结果 |
|-------|--------|------|
| actpass | active | Offerer = Server, Answerer = Client |
| actpass | passive | Offerer = Client, Answerer = Server |
| active | passive | Offerer = Client, Answerer = Server |
| passive | active | Offerer = Server, Answerer = Client |

**本例结果**：
- peer1 (Offer, actpass) → **DTLS Server**（等待连接）
- peer2 (Answer, active) → **DTLS Client**（发起连接）

#### DTLS 握手流程（对应抓包帧号）

```
peer1 (Server)                       peer2 (Client)
    │                                    │
    │  1. ClientHello                    │
    │     帧 778 (41.000366s)            │
    │ ◄───────────────────────────────── │
    │                                    │
    │  2. ServerHello                    │
    │     帧 799 (41.001106s)            │
    │  3. Certificate (peer1 的证书)      │
    │  4. ServerKeyExchange              │
    │  5. CertificateRequest             │
    │  6. ServerHelloDone                │
    │ ─────────────────────────────────► │
    │                                    │
    │  7. Certificate (peer2 的证书)      │
    │     帧 957-959 (41.018s)           │
    │  8. ClientKeyExchange              │
    │  9. CertificateVerify              │
    │ 10. ChangeCipherSpec               │
    │ 11. Finished                       │
    │ ◄───────────────────────────────── │
    │                                    │
    │ 12. ChangeCipherSpec               │
    │     帧 960 (41.024412s)            │
    │ 13. Finished                       │
    │ ─────────────────────────────────► │
    │                                    │
    │  [加密通道建立完成]                  │
    │  帧 961+ 开始传输应用数据            │
```

**DTLS 帧号详情**:
| 帧号 | 时间戳 | 内容类型 | 握手类型 | 描述 |
|------|--------|----------|----------|------|
| 778 | 41.000366s | 22 (Handshake) | 1 (ClientHello) | DTLS 握手开始 |
| 799 | 41.001106s | 22 (Handshake) | 3 (HelloVerifyRequest) | Cookie 验证 |
| 957 | 41.018559s | 22 (Handshake) | 1 (ClientHello) | 重传 ClientHello |
| 958 | 41.018808s | 22 (Handshake) | 2,11,12,13,14 | ServerHello, Certificate, ServerKeyExchange, CertificateRequest, ServerHelloDone |
| 959 | 41.023086s | 22 (Handshake) | 11,16,15,20 | Certificate, ClientKeyExchange, CertificateVerify, Finished |
| 960 | 41.024412s | 20 (ChangeCipherSpec), 22 | 20 | ChangeCipherSpec, Finished |
| 961+ | 41.024706s+ | 23 (Application Data) | - | 加密数据传输 |

---

## 4. 媒体信息

### 4.1 媒体描述行

```sdp
m=application 9 UDP/DTLS/SCTP webrtc-datachannel
```

| 字段 | 值 | 说明 |
|------|-----|------|
| **媒体类型** | `application` | 应用数据（非音频/视频） |
| **端口** | `9` | 占位符（实际端口由 ICE 决定） |
| **传输协议** | `UDP/DTLS/SCTP` | UDP 传输 + DTLS 加密 + SCTP 协议 |
| **格式列表** | `webrtc-datachannel` | WebRTC DataChannel |

### 4.2 连接信息

```sdp
c=IN IP4 0.0.0.0
```

- **网络类型**: IN (Internet)
- **地址类型**: IP4
- **地址**: `0.0.0.0`（占位符，实际地址由 ICE 候选者决定）

### 4.3 SCTP 配置

```sdp
a=sctp-port:5000              ; SCTP 端口号
a=max-message-size:1073741823 ; 最大消息大小（约 1GB）
```

| 属性 | 值 | 说明 |
|------|-----|------|
| **sctp-port** | 5000 | SCTP 使用的端口 |
| **max-message-size** | 1073741823 | 单个消息的最大字节数 |

---

## 5. 扩展和特性

### 5.1 BUNDLE 策略

```sdp
a=group:BUNDLE 0
```

**作用**：将所有媒体流（音频、视频、数据）复用到单一传输连接上。

**优势**：
- 减少连接数（只需要一个 ICE + DTLS 连接）
- 降低 NAT 穿透难度
- 减少资源消耗

### 5.2 Media Stream ID 语义

```sdp
a=msid-semantic:WMS *
```

**作用**：声明使用 WebRTC Media Stream (WMS) 语义，`*` 表示通配符。

### 5.3 RTP 扩展头

```sdp
a=extmap-allow-mixed
```

**作用**：允许在一个 RTP 包中混合使用 one-byte 和 two-byte 扩展头格式。

### 5.4 媒体流标识

```sdp
a=mid:0
```

**作用**：标识媒体流 ID，用于 BUNDLE 分组。

### 5.5 传输方向

```sdp
a=sendrecv
```

**作用**：声明双向通信（既可发送也可接收）。

其他选项：
- `sendonly`：仅发送
- `recvonly`：仅接收
- `inactive`：不传输

---

## 6. 网络环境分析

### 6.1 peer1 网络特征

```
┌─────────────────────────────────────┐
│           peer1 (192.168.50.20)      │
│                                     │
│  接口：                              │
│  ├─ eth0: 192.168.50.20             │
│  ├─ eth1: 10.251.1.1                │
│  └─ IPv6: fdc7:60ad:2e14:498f::     │
│                                     │
│  NAT：                               │
│  └─ 公网 IP: 124.77.234.173         │
│                                     │
│  候选者数量：8 个                     │
│  - host: 6 个（3 地址 × 2 组件）      │
│  - srflx: 2 个                       │
└─────────────────────────────────────┘
```

### 6.2 peer2 网络特征

```
┌─────────────────────────────────────┐
│          peer2 (192.168.50.117)      │
│                                     │
│  接口：                              │
│  ├─ eth0: 192.168.50.117            │
│  ├─ eth1: 192.168.49.1              │
│  ├─ docker0: 172.17.0.1             │
│  ├─ docker1: 172.18.0.1             │
│  ├─ docker2: 172.19.0.1             │
│  ├─ ... (共 10 个 Docker 网桥)       │
│  └─ 多个 IPv6 地址（Docker 容器）     │
│                                     │
│  NAT：                               │
│  └─ 公网 IP: 124.77.234.173         │
│                                     │
│  候选者数量：22 个                    │
│  - host: 20 个                       │
│  - srflx: 2 个                       │
└─────────────────────────────────────┘
```

### 6.3 连接路径选择

```
最终使用的路径（host 候选者）：
┌────────────────────────────────────────────────────────────┐
│                                                            │
│   peer1: 192.168.50.20:51467  ◄────────────►  192.168.50.117:54917 :peer2
│                                                            │
│   类型：host ↔ host（内网直连）                             │
│   优先级：2130706431（最高）                                │
│   延迟：极低（局域网内）                                    │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 7. 安全机制总结

### 7.1 多层安全架构

```
┌─────────────────────────────────────────────────────────────┐
│                      应用层 (DataChannel)                    │
│                    （应用自定义加密）                         │
├─────────────────────────────────────────────────────────────┤
│                      SCTP 层                                 │
│              （流控制、多路复用、可靠性）                      │
├─────────────────────────────────────────────────────────────┤
│                      DTLS 层                                 │
│         （证书验证、密钥交换、记录加密）                       │
│         - fingerprint 验证对端证书                           │
│         - 完美前向保密 (PFS)                                 │
├─────────────────────────────────────────────────────────────┤
│                      ICE/STUN 层                             │
│         - ice-ufrag/ice-pwd 认证                             │
│         - MESSAGE-INTEGRITY 完整性校验                       │
├─────────────────────────────────────────────────────────────┤
│                      UDP 层                                  │
│              （无连接传输）                                  │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 密钥和凭证汇总（含帧号）

| 层级 | 凭证 | 用途 | 来源 | 抓包帧号 |
|------|------|------|------|----------|
| **ICE** | ice-ufrag, ice-pwd | STUN 认证 | SDP 交换 | 帧 20 (Offer), 帧 24+ (Answer) |
| **DTLS** | 证书指纹 | 证书验证 | SDP 交换 | 帧 20 (Offer), 帧 24+ (Answer) |
| **DTLS** | 会话密钥 | 记录加密 | DTLS 握手协商 | 帧 778-961 |
| **SCTP** | 关联密钥 | 从 DTLS 导出 | DTLS 导出 | 帧 961+ |

---

## 8. 关键洞察

### 8.1 网络复杂度差异

| 指标 | peer1 | peer2 |
|------|-------|-------|
| **候选者数量** | 8 个 | 22 个 |
| **网络接口** | 3 个 | 13+ 个 |
| **Docker 环境** | 否 | 是（大量容器） |
| **公网地址** | 相同 NAT (124.77.234.173) | 相同 NAT (124.77.234.173) |

**结论**：peer2 运行在复杂的容器化环境中，peer1 相对简单。

### 8.2 连接优化（含帧号验证）

- 成功使用 **host 候选者** 直连，避免经过 STUN/TURN 服务器
  - 实际使用路径：`192.168.50.20:51467` ↔ `192.168.50.117:54917`
  - 验证帧：帧 22-53 (STUN 连通性检查)
  
- 使用 **BUNDLE** 策略，单一连接传输所有数据
  - SDP 中声明：`a=group:BUNDLE 0` (帧 20)
  
- 启用 **DataChannel** 传输应用数据（非音视频）
  - SDP 媒体行：`m=application 9 UDP/DTLS/SCTP webrtc-datachannel` (帧 20)
  - 实际传输：帧 961+ (DTLS Application Data)

### 8.3 安全强度

- ICE 凭证：16字符 ufrag + 24字符 pwd，随机生成
- DTLS：SHA-256 指纹，256位证书
- 完美前向保密：即使长期密钥泄露，历史会话也不会被解密

---

## 9. 完整帧号速查表

### 9.1 HTTP 信令帧

| 帧号 | 时间戳 | 方向 | 方法/URI | 内容摘要 |
|------|--------|------|----------|----------|
| 6 | 38.781781s | peer2 → Server | POST /register | peer2 注册 |
| 8 | 38.782348s | Server → peer2 | 200 OK | 注册成功 |
| 17 | 39.790774s | peer2 → Server | GET /poll?peerId=peer2 | 轮询消息 |
| **20** | **39.791655s** | **Server → peer2** | **200 OK** | **包含 Offer + 4 candidates** |
| 24 | 39.809315s | peer2 → Server | POST /signal | candidate (192.168.50.117:54917) |
| 26 | 39.809973s | Server → peer2 | 200 OK | 确认接收 |
| 113 | 39.818942s | peer2 → Server | POST /signal | candidate (IPv6) |
| 122 | 39.819463s | Server → peer2 | 200 OK | 确认接收 |
| 161 | 39.826260s | peer2 → Server | POST /signal | candidate (IPv6) |
| 164 | 39.826429s | Server → peer2 | 200 OK | 确认接收 |
| 188 | 39.832745s | peer2 → Server | POST /signal | candidate (IPv6) |
| 190 | 39.832919s | Server → peer2 | 200 OK | 确认接收 |
| 213 | 39.840162s | peer2 → Server | POST /signal | candidate (IPv6) |
| 216 | 39.840448s | Server → peer2 | 200 OK | 确认接收 |
| 241 | 39.847418s | peer2 → Server | POST /signal | candidate (Docker) |
| 243 | 39.847538s | Server → peer2 | 200 OK | 确认接收 |
| 252 | 39.854198s | peer2 → Server | POST /signal | candidate (Docker) |
| 254 | 39.854308s | Server → peer2 | 200 OK | 确认接收 |
| 263 | 39.861198s | peer2 → Server | POST /signal | candidate (Docker) |
| 265 | 39.861361s | Server → peer2 | 200 OK | 确认接收 |
| 275 | 39.867967s | peer2 → Server | POST /signal | candidate (Docker) |
| 277 | 39.868114s | Server → peer2 | 200 OK | 确认接收 |
| 286 | 39.875005s | peer2 → Server | POST /signal | candidate (Docker) |
| 288 | 39.875195s | Server → peer2 | 200 OK | 确认接收 |
| 297 | 39.883119s | peer2 → Server | POST /signal | candidate (Docker) |
| 299 | 39.883294s | Server → peer2 | 200 OK | 确认接收 |
| 308 | 39.890360s | peer2 → Server | POST /signal | candidate (Docker) |
| 310 | 39.890563s | Server → peer2 | 200 OK | 确认接收 |
| 319 | 39.896608s | peer2 → Server | POST /signal | candidate (Docker) |
| 321 | 39.896781s | Server → peer2 | 200 OK | 确认接收 |
| 330 | 39.903351s | peer2 → Server | POST /signal | candidate (Docker) |
| 332 | 39.903490s | Server → peer2 | 200 OK | 确认接收 |
| 341 | 39.910039s | peer2 → Server | POST /signal | candidate (Docker) |
| 343 | 39.910181s | Server → peer2 | 200 OK | 确认接收 |
| 352 | 39.915824s | peer2 → Server | POST /signal | candidate (Docker) |
| 354 | 39.915960s | Server → peer2 | 200 OK | 确认接收 |
| 364 | 39.921868s | peer2 → Server | POST /signal | candidate (Docker) |
| 366 | 39.921971s | Server → peer2 | 200 OK | 确认接收 |
| 376 | 39.930067s | peer2 → Server | POST /signal | candidate (srflx) |
| 378 | 39.930223s | Server → peer2 | 200 OK | 确认接收 |
| ... | ... | ... | ... | 更多 candidate 帧... |

### 9.2 STUN/ICE 帧

| 帧号范围 | 时间戳范围 | 描述 |
|----------|------------|------|
| 1-2 | 0.000000s-0.158541s | peer1 STUN 服务器反射地址获取 |
| 22-53 | 39.809312s-39.814239s | ICE 连通性检查（大量 STUN Binding Request/Response） |

### 9.3 DTLS 握手帧

| 帧号 | 时间戳 | 描述 |
|------|--------|------|
| 778 | 41.000366s | DTLS ClientHello |
| 799 | 41.001106s | DTLS HelloVerifyRequest |
| 957 | 41.018559s | DTLS ClientHello (重传) |
| 958 | 41.018808s | DTLS ServerHello + Certificate + ServerKeyExchange + CertificateRequest + ServerHelloDone |
| 959 | 41.023086s | DTLS Certificate + ClientKeyExchange + CertificateVerify + Finished |
| 960 | 41.024412s | DTLS ChangeCipherSpec + Finished |
| 961+ | 41.024706s+ | DTLS Application Data (加密传输) |

---

## 10. 参考文档

- [RFC 4566](https://tools.ietf.org/html/rfc4566) - SDP: Session Description Protocol
- [RFC 5245](https://tools.ietf.org/html/rfc5245) - Interactive Connectivity Establishment (ICE)
- [RFC 5763](https://tools.ietf.org/html/rfc5763) - Framework for Establishing a Secure Real-time Transport Protocol (SRTP) Security Context Using Datagram Transport Layer Security (DTLS)
- [RFC 6347](https://tools.ietf.org/html/rfc6347) - Datagram Transport Layer Security Version 1.2
- [RFC 8842](https://tools.ietf.org/html/rfc8842) - Session Description Protocol (SDP) Offer/Answer Considerations for Datagram Transport Layer Security (DTLS) and Transport Layer Security (TLS)
- [RFC 8832](https://tools.ietf.org/html/rfc8832) - WebRTC Data Channels
- [WebRTC 1.0: Real-time Communication Between Browsers](https://www.w3.org/TR/webrtc/)
