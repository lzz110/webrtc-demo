# SRTP 解密与 RTP 解析技术指南

## 目录

1. [整体流程概览](#整体流程概览)
2. [DTLS-SRTP 密钥协商](#dtls-srtp-密钥协商)
3. [SRTP 密钥派生](#srtp-密钥派生)
4. [SRTP 包结构](#srtp-包结构)
5. [SRTP 解密过程](#srtp-解密过程)
6. [RTP 解析](#rtp-解析)
7. [Wireshark 密钥格式详解](#wireshark-密钥格式详解)
8. [常见问题排查](#常见问题排查)

---

## 整体流程概览

```
┌─────────────────────────────────────────────────────────────────┐
│                      WebRTC 通信流程                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. DTLS 握手                                                    │
│     ├── ClientHello (Client Random)                             │
│     ├── ServerHello (Server Random)                             │
│     ├── Certificate Exchange                                     │
│     └── Finished                                                 │
│                           ↓                                     │
│  2. SRTP 密钥导出 (RFC 5764)                                     │
│     └── export_keying_material("EXTRACTOR-dtls_srtp")           │
│                           ↓                                     │
│  3. SRTP 会话密钥派生                                            │
│     ├── Session Encryption Key                                  │
│     ├── Session Authentication Key                              │
│     └── Session Salt                                            │
│                           ↓                                     │
│  4. SRTP 加密传输                                                │
│     ├── RTP Header (12+ bytes)                                  │
│     ├── Encrypted Payload                                        │
│     └── Authentication Tag                                       │
│                           ↓                                     │
│  5. SRTP 接收解密                                                │
│     ├── 验证 Authentication Tag                                  │
│     ├── 解密 Payload                                             │
│     └── 重放保护检查                                              │
│                           ↓                                     │
│  6. RTP 解析                                                     │
│     ├── Version (2 bits)                                         │
│     ├── Padding (1 bit)                                          │
│     ├── Extension (1 bit)                                        │
│     ├── CSRC Count (4 bits)                                      │
│     ├── Marker (1 bit)                                           │
│     ├── Payload Type (7 bits)                                    │
│     ├── Sequence Number (16 bits)                                │
│     ├── Timestamp (32 bits)                                      │
│     ├── SSRC (32 bits)                                           │
│     ├── CSRC List (optional)                                     │
│     ├── Extension Header (optional)                              │
│     └── Payload (decrypted)                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## DTLS-SRTP 密钥协商

### 1. DTLS 握手流程

```
Client                                           Server
  |                                                |
  |--- ClientHello ------------------------------->|
  |    - Client Random (32 bytes)                  |
  |    - Supported Cipher Suites                   |
  |    - Use SRTP Extension                        |
  |                                                |
  |<-- ServerHello --------------------------------|
  |    - Server Random (32 bytes)                  |
  |    - Selected Cipher Suite                     |
  |    - Selected SRTP Profile                     |
  |                                                |
  |<-- Certificate --------------------------------|
  |    - Server Certificate                        |
  |                                                |
  |<-- ServerHelloDone ----------------------------|
  |                                                |
  |--- ClientKeyExchange ------------------------->|
  |    - Pre-Master Secret (encrypted)             |
  |                                                |
  |--- ChangeCipherSpec --------------------------->|
  |--- Finished (encrypted) ---------------------->|
  |                                                |
  |<-- ChangeCipherSpec ----------------------------|
  |<-- Finished (encrypted) ------------------------|
  |                                                |
```

### 2. 导出 SRTP 密钥材料

DTLS 握手完成后，双方使用 `export_keying_material` 导出 SRTP 密钥：

```c
// RFC 5764 定义的导出标签
const char* label = "EXTRACTOR-dtls_srtp";

// 导出的材料总长度 (SRTP_AES128_CM_HMAC_SHA1_80)
// client_key (16) + server_key (16) + client_salt (14) + server_salt (14) = 60 bytes
uint8_t key_material[60];

SSL_export_keying_material(
    ssl,
    key_material, sizeof(key_material),
    label, strlen(label),
    NULL, 0, 0  // no context
);
```

### 3. 密钥材料布局

```
导出材料布局 (60 bytes for AES128_CM_HMAC_SHA1_80):
┌────────────────────────────────────────────────────────────────────┐
│  0-15   │ 16-31   │ 32-45   │ 46-59   │                           │
├────────────────────────────────────────────────────────────────────┤
│ Client  │ Server  │ Client  │ Server  │                           │
│  Key    │  Key    │  Salt   │  Salt   │                           │
│ 16 bytes│ 16 bytes│ 14 bytes│ 14 bytes│                           │
└────────────────────────────────────────────────────────────────────┘
```

---

## SRTP 密钥派生

### 1. 会话密钥派生公式

SRTP 使用基于 AES-CM 的密钥派生：

```
SRTP Session Key = PRF(master_key, 0x00 || master_salt || index)
SRTCP Session Key = PRF(master_key, 0x01 || master_salt || index)
```

其中：
- `PRF` 是伪随机函数（AES-CM）
- `||` 表示连接
- `index` 是 RTP 包序号

### 2. 密钥派生过程

```
Master Key (16 bytes) ──┐
                        ├──[Key Derivation]──> Session Encryption Key (16 bytes)
Master Salt (14 bytes) ─┘                         Session Auth Key (20 bytes)
                                                  Session Salt (14 bytes)
```

### 3. 每个 SRTP 会话需要的关键参数

```c
typedef struct {
    // Master keys (from DTLS export)
    uint8_t client_master_key[16];
    uint8_t server_master_key[16];
    uint8_t client_master_salt[14];
    uint8_t server_master_salt[14];
    
    // Derived session keys (per direction)
    uint8_t client_session_enc_key[16];
    uint8_t client_session_auth_key[20];
    uint8_t client_session_salt[14];
    
    uint8_t server_session_enc_key[16];
    uint8_t server_session_auth_key[20];
    uint8_t server_session_salt[14];
    
    // Replay protection window
    uint64_t replay_window[REPLAY_WINDOW_SIZE];
} srtp_session_t;
```

---

## SRTP 包结构

### 1. 原始 RTP 包（加密前）

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|V=2|P|X|  CC   |M|     PT      |       Sequence Number         |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                           Timestamp                           |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|           Synchronization Source (SSRC) identifier            |
+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
|            Contributing Source (CSRC) identifiers             |
|                             ....                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                   RTP Extension (if X=1)                      |
|                             ....                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                           Payload                             |
|                             ....                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### 2. SRTP 包（加密后）

```
 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|V=2|P|X|  CC   |M|     PT      |       Sequence Number         |  <- 不加密
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                           Timestamp                           |  <- 不加密
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|           Synchronization Source (SSRC) identifier            |  <- 不加密
+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+=+
|            Contributing Source (CSRC) identifiers             |  <- 不加密
|                             ....                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                   RTP Extension (if X=1)                      |  <- 加密
|                             ....                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    Encrypted Payload                          |  <- 加密
|                             ....                              |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                   Authentication Tag                          |  <- 附加
|                             ....                              |     (10 bytes for auth)
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                    ROC (if EKT enabled)                       |  <- 可选
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
```

### 3. 字段说明

| 字段 | 大小 | 加密? | 说明 |
|------|------|-------|------|
| V (Version) | 2 bits | 否 | RTP 版本，始终为 2 |
| P (Padding) | 1 bit | 否 | 末尾是否有填充 |
| X (Extension) | 1 bit | 否 | 是否有扩展头 |
| CC (CSRC Count) | 4 bits | 否 | CSRC 数量 |
| M (Marker) | 1 bit | 否 | 标记位 |
| PT (Payload Type) | 7 bits | 否 | 负载类型 |
| Sequence Number | 16 bits | 否 | 包序号 |
| Timestamp | 32 bits | 否 | 时间戳 |
| SSRC | 32 bits | 否 | 同步源标识 |
| CSRC | 32×CC bits | 否 | 贡献源列表 |
| Extension | 可变 | 是 | RTP 扩展头 |
| Payload | 可变 | 是 | 实际负载数据 |
| Auth Tag | 10 bytes | N/A | 认证标签 |

---

## SRTP 解密过程

### 1. 解密流程图

```
收到 SRTP 包
    │
    ▼
┌──────────────────┐
│ 1. 提取 RTP Header│
│    - Seq Num      │
│    - SSRC         │
│    - Timestamp    │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 2. 计算 Packet   │
│    Index (ROC)   │
│    index =       │
│    ROC << 16 +   │
│    seq_num       │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 3. 派生 Session  │
│    Keys          │
│    - enc_key     │
│    - auth_key    │
│    - salt        │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ 4. 验证 Auth Tag │
│    (HMAC-SHA1)   │
│    比对计算值     │
│    和接收值       │
└────────┬─────────┘
         │
         ▼
    ┌────────┐
    │ 验证   │
    │ 失败?  │
    └────┬───┘
       │ │
   是  │ │  否
       │ │
       ▼ ▼
    丢弃包  ┌──────────────────┐
            │ 5. 解密 Payload  │
            │    (AES-ICM)     │
            │                  │
            │    plaintext =   │
            │    ciphertext ⊕  │
            │    keystream     │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ 6. 重放保护检查   │
            │    - 检查 index  │
            │      是否在窗口内 │
            └────────┬─────────┘
                     │
                     ▼
            ┌──────────────────┐
            │ 7. 输出 RTP Packet│
            │    - Header       │
            │    - Payload      │
            └──────────────────┘
```

### 2. 密钥流生成 (AES-ICM)

```
IV Construction:
┌──────────────┬──────────────┬──────────────┬──────────────┐
│   salt (14)  │   SSRC (4)   │  index (6)   │  padding (2) │
│              │              │  ROC(4)+Seq  │              │
└──────────────┴──────────────┴──────────────┴──────────────┘
      112 bits      32 bits        48 bits        16 bits
      
Total IV: 128 bits (16 bytes)

keystream = AES(master_key, IV) || AES(master_key, IV+1) || ...
```

### 3. 解密公式

```
# 分段加密（AES-ICM 模式）
for i in range(0, payload_len, 16):
    counter = IV + (i // 16)
    keystream_block = AES_ENCRYPT(session_enc_key, counter)
    plaintext[i:i+16] = ciphertext[i:i+16] ⊕ keystream_block
```

### 4. 认证计算 (HMAC-SHA1)

```
Authenticated Data:
- RTP Header (12 bytes minimum)
- ROC (4 bytes, implicit)

Auth Tag = HMAC-SHA1(auth_key, authenticated_data + ciphertext)[0:10]
```

---

## RTP 解析

### 1. RTP Header 解析

```c
typedef struct {
    // Byte 0
    uint8_t version:2;      // 2 bits
    uint8_t padding:1;      // 1 bit
    uint8_t extension:1;    // 1 bit
    uint8_t csrc_count:4;   // 4 bits
    
    // Byte 1
    uint8_t marker:1;       // 1 bit
    uint8_t payload_type:7; // 7 bits
    
    // Bytes 2-3
    uint16_t sequence_number;
    
    // Bytes 4-7
    uint32_t timestamp;
    
    // Bytes 8-11
    uint32_t ssrc;
    
    // Optional: CSRC list (0-15 × 4 bytes)
    uint32_t csrc_list[15];
    
    // Optional: Extension header
    rtp_extension_t extension;
} rtp_header_t;
```

### 2. 常见 Payload Type

| PT | 编码格式 | 说明 |
|----|---------|------|
| 0 | PCMU | G.711 μ-law |
| 8 | PCMA | G.711 A-law |
| 96 | H.264 | 动态分配 |
| 97 | H.264-SVC | 动态分配 |
| 98 | VP8 | 动态分配 |
| 99 | VP9 | 动态分配 |
| 100 | AV1 | 动态分配 |
| 111 | Opus | 动态分配 |

### 3. WebRTC 视频 RTP 结构

```
RTP Header (12+ bytes)
│
├── Video Codec Specific Header (optional)
│   ├── H.264: 1-3 bytes (FU-A indicator + header)
│   ├── VP8: 1-3 bytes (VP8 payload descriptor)
│   └── VP9: 1-3 bytes (VP9 payload descriptor)
│
└── Actual Codec Data
    ├── H.264 NAL Units
    ├── VP8 Frame Data
    └── VP9 Frame Data
```

#### H.264 特殊处理

```
RTP Payload for H.264 (Fragmentation Unit A - FU-A):

 0                   1                   2                   3
 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
| FU indicator  |   FU header   |                               |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+                               |
|                                                               |
|                         FU payload                            |
|                                                               |
|                             +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
|                             :...OPTIONAL RTP padding          |
+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

FU Indicator:
  - F (1 bit): Forbidden zero bit
  - NRI (2 bits): NAL reference indicator
  - Type (5 bits): NAL unit type (28 for FU-A)

FU Header:
  - S (1 bit): Start bit
  - E (1 bit): End bit
  - R (1 bit): Reserved
  - Type (5 bits): Original NAL unit type
```

---

## Wireshark 密钥格式详解

### 1. NSS Key Log 格式

Wireshark 使用 NSS Key Log 格式来解密 SSL/TLS/DTLS/SRTP：

```
# 格式: <Label> <ClientRandom> <Secret>
CLIENT_RANDOM <64_hex_chars> <96_hex_chars_for_TLS12>
SRTP <64_hex_chars> <60_hex_chars_for_AES128>
```

### 2. 正确的密钥文件格式

```
# DTLS 1.2 主密钥 (用于解密 DTLS 层)
CLIENT_RANDOM 3b8f2c1d4e5a607b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2 7d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8

# SRTP 密钥 (用于解密 SRTP 层)
# 格式: SRTP <client_random> <master_key><master_salt>
# 注意: 对于解密，只需要 client_random 作为索引
SRTP 3b8f2c1d4e5a607b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2 a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5

# Wireshark 可能也接受这种格式
SRTP_SERVER 3b8f2c1d4e5a607b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2 d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a
```

### 3. Wireshark 如何匹配密钥

```
Wireshark 解密流程:

1. 捕获 DTLS 包
   └── 提取 Client Random (从 ClientHello)
   
2. 查找密钥文件
   └── 搜索 "CLIENT_RANDOM <client_random>"
   └── 找到对应的主密钥
   
3. 派生 SRTP 密钥
   └── 使用主密钥 + "EXTRACTOR-dtls_srtp" 导出
   └── 或者直接使用文件中的 SRTP 行
   
4. 解密 SRTP 包
   └── 使用导出的密钥解密
   
注意: Wireshark 3.0+ 可以直接使用 CLIENT_RANDOM 
      自动派生 SRTP 密钥，不需要单独的 SRTP 行！
```

### 4. 关键发现

**对于 DTLS 1.2 + SRTP，Wireshark 实际上只需要 `CLIENT_RANDOM`！**

当 Wireshark 看到：
```
CLIENT_RANDOM <random> <master_secret>
```

它会自动：
1. 使用 master_secret 派生 SRTP 密钥
2. 使用 `EXTRACTOR-dtls_srtp` 标签导出
3. 解密 SRTP 包

**这意味着我们的 `SRTP` 行可能是多余的！**

---

## 常见问题排查

### Q1: Wireshark 显示 "Could not decrypt SRTP packet"

排查步骤：
1. 确认密钥文件路径正确
2. 确认 Client Random 匹配
3. 确认使用的是正确的 DTLS 版本
4. 检查 Wireshark 版本 (需要 3.0+)
5. 确认捕获到了完整的 DTLS 握手

### Q2: 密钥文件格式正确但仍无法解密

可能原因：
1. **DTLS 1.3 使用不同的密钥导出机制**
   - DTLS 1.3 使用 `EXPORTER_SECRET` 而不是 `CLIENT_RANDOM`
   - Wireshark 3.4+ 才支持 DTLS 1.3

2. **SRTP 加密套件不匹配**
   - 确认使用 AES128_CM_HMAC_SHA1_80
   - 其他套件需要不同的密钥长度

3. **密钥文件在连接建立后才创建**
   - Wireshark 需要看到完整的握手过程
   - 必须在握手前设置密钥文件

### Q3: 如何验证密钥正确性

```bash
# 1. 检查密钥文件格式
head -5 ~/Downloads/webrtc_dtls_keys.log

# 2. 验证 Client Random 长度
echo "3b8f2c1d4e5a607b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2" | wc -c
# 应该输出 65 (64 hex chars + newline)

# 3. 在 Wireshark 中检查
# Edit -> Preferences -> Protocols -> DTLS
# 确认 "(Pre)-Master-Secret log filename" 已设置

# 4. 使用 tshark 命令行解密
tshark -r capture.pcapng -o "ssl.keylog_file:$HOME/Downloads/webrtc_dtls_keys.log" -V
```

---

## 总结

### 关键点

1. **对于 DTLS 1.2 + SRTP，只需要 `CLIENT_RANDOM` 行**
   - Wireshark 会自动派生 SRTP 密钥
   - 单独的 `SRTP` 行是可选的（用于旧版本 Wireshark）

2. **密钥必须在 DTLS 握手前设置**
   - 错过握手就无法解密

3. **SRTP 解密需要**
   - RTP Header (12 bytes) - 明文
   - Encrypted Payload - 使用 AES-ICM 解密
   - Auth Tag - 验证完整性

4. **WebRTC 视频流**
   - 通常是 H.264 或 VP8/VP9
   - RTP payload 需要特殊解析（FU-A for H.264）

### 我们的实现问题

当前代码导出了：
```
CLIENT_RANDOM ...
SRTP ...
SRTP_SERVER ...
```

实际上，**对于 Wireshark 3.0+，只需要 `CLIENT_RANDOM`**！

但如果你想支持：
- 旧版本 Wireshark
- 直接提供 SRTP 密钥给其他工具
- 手动验证密钥

那么 `SRTP` 行还是有用的。
