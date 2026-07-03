# WebRTC 解密工具集

从 WebRTC 抓包中解密 DTLS/SCTP/SRTP, 导出 DataChannel 明文和音视频流。

## 前置条件

### 系统依赖

```bash
# Python 依赖
pip install scapy pylibsrtp

# Wireshark (需要 tshark)
# macOS: brew install --cask wireshark
# Linux: apt install tshark

# ffmpeg
# macOS: brew install ffmpeg
# Linux: apt install ffmpeg
```

### WebRTC 源码改动 (必须)

默认 WebRTC 不会导出 DTLS/SRTP 会话密钥, 必须修改两处源码才能离线解密。

源码根目录假设为 `$WEBRTC_SRC`(即 `src/` 所在路径)。

---

#### 改动 1: 导出 DTLS 密钥 — `rtc_base/openssl_stream_adapter.cc`

目的: 让 Wireshark/tshark 能稳定解密 DTLS ApplicationData, 从而解析 SCTP/DataChannel。

在文件顶部添加头文件:

```cpp
#include <cstdlib>
#include <fstream>
```

新增回调函数(放在匿名 namespace 或文件作用域):

```cpp
static void DtlsKeyLogCallback(const SSL* ssl, const char* line) {
  const char* path = std::getenv("SSLKEYLOGFILE");
  if (!path || !line) return;
  std::ofstream ofs(path, std::ios::app);
  if (ofs.is_open()) {
    ofs << line << "\n";
  }
}
```

在 `OpenSSLStreamAdapter::SetupSSLContext()` 中, 创建 `SSL_CTX` 之后调用:

```cpp
SSL_CTX_set_keylog_callback(ctx, DtlsKeyLogCallback);
```

运行时设置环境变量即可落盘:

```bash
export SSLKEYLOGFILE=/tmp/webrtc_dtls_keys.log
```

---

#### 改动 2: 导出 SRTP 双向密钥 — `pc/dtls_srtp_transport.cc`

目的: 显式导出 SRTP client/server write key, 让离线脚本能按 SSRC 双向解密媒体。

新增辅助函数:

```cpp
#include <cstdlib>
#include <fstream>
#include <sstream>
#include <iomanip>

static std::string BytesToHex(const uint8_t* data, size_t len) {
  std::ostringstream oss;
  for (size_t i = 0; i < len; ++i)
    oss << std::hex << std::setw(2) << std::setfill('0') << (int)data[i];
  return oss.str();
}

static void MaybeExportSrtpKeys(const std::string& role,
                                 const uint8_t* send_key, size_t send_len,
                                 const uint8_t* recv_key, size_t recv_len) {
  const char* path = std::getenv("SRTPKEYLOGFILE");
  if (!path) path = std::getenv("WEBRTC_SRTPKEYLOGFILE");
  if (!path) return;
  std::ofstream ofs(path, std::ios::app);
  if (!ofs.is_open()) return;
  ofs << "SRTP_KEYS role=" << role
      << " send_key=" << BytesToHex(send_key, send_len)
      << " recv_key=" << BytesToHex(recv_key, recv_len)
      << "\n";
}
```

在 `DtlsSrtpTransport::ExtractParams(...)` 中, 拿到 `send_key` / `recv_key` 之后调用:

```cpp
// send_key, recv_key 各 30 字节 = 16(key) + 14(salt)
MaybeExportSrtpKeys(
    is_client ? "client" : "server",
    send_key.data(), send_key.size(),
    recv_key.data(), recv_key.size());
```

运行时:

```bash
export SRTPKEYLOGFILE=/tmp/webrtc_srtp_keys.log
```

---

#### 编译

```bash
cd $WEBRTC_SRC

# 生成构建文件 (Debug)
gn gen out/Debug --args='is_debug=true rtc_include_tests=false'

# 编译
ninja -C out/Debug

# 或 Release
gn gen out/Release --args='is_debug=false rtc_include_tests=false'
ninja -C out/Release
```

iOS 交叉编译:

```bash
gn gen out/ios_arm64 --args='
  target_os="ios"
  target_cpu="arm64"
  is_debug=false
  rtc_include_tests=false
  ios_enable_code_signing=false
'
ninja -C out/ios_arm64
```

---

## 密钥文件格式

两处改动会分别产出两个 keylog 文件, 合并后供脚本使用:

```bash
cat /tmp/webrtc_dtls_keys.log /tmp/webrtc_srtp_keys.log > combined_keys.log
```

文件内容示例:

```
# DTLS key log (NSS Key Log 格式, Wireshark 原生支持)
CLIENT_RANDOM abcdef0123456789... master_secret_hex...

# SRTP key log (自定义格式, 脚本解析)
SRTP_KEYS role=server send_key=aabbccdd... recv_key=11223344...
```

---

## 工具说明

### 1. `decrypt_session_pipeline.py` — 一键总控

输入 pcap + keylog, 一次性输出:
- 完整解密报告 (Signaling / ICE / DTLS / RTP / SCTP / Video)
- 双端视频 MP4
- DataChannel 明文

```bash
python3 src/decrypt_session_pipeline.py \
  capture.pcapng \
  -k combined_keys.log \
  --out-dir output/ \
  --log output/report.log
```

### 2. `webrtc_h264_extractor.py` — H.264 视频提取 + SRTP 解密

```bash
# 列出所有 SSRC
python3 src/webrtc_h264_extractor.py extract capture.pcapng -k keys.log -l

# 提取指定 SSRC 的 H.264 视频
python3 src/webrtc_h264_extractor.py extract capture.pcapng -k keys.log -s 0x12345678

# 解密 pcapng (供 Wireshark 打开)
python3 src/webrtc_h264_extractor.py decrypt capture.pcapng -k keys.log -o decrypted.pcapng

# 提取音频
python3 src/webrtc_h264_extractor.py extract-audio capture.pcapng -k keys.log -o audio_out
```

### 3. `red_vp8_extract.py` — RED(PT=123) + VP8 视频提取

当 SDP 协商为 `a=rtpmap:123 red/90000` 时, 视频不是裸 H.264, 需要 RED 解包 + VP8 描述符剥离:

```bash
python3 src/red_vp8_extract.py capture.pcapng -k keys.log -s 0xAABBCCDD
```

### 4. `export_sctp_plaintext.py` — SCTP/DataChannel 明文导出

```bash
python3 src/export_sctp_plaintext.py capture.pcapng -k combined_keys.log
```

### 5. `wireshark-datachannel-json.lua` — Wireshark DataChannel 解析插件

将 SCTP PPID=51 的 JSON 载荷解析为树状显示:

```bash
wireshark -X lua_script:src/wireshark-datachannel-json.lua capture.pcapng
```

或在 Wireshark 首选项中添加脚本路径。

---

## 典型工作流

```
1. 编译改动后的 WebRTC, 设置环境变量
   export SSLKEYLOGFILE=/tmp/dtls.log
   export SRTPKEYLOGFILE=/tmp/srtp.log

2. 运行 WebRTC 应用, 同时用 Wireshark/tcpdump 抓包
   tcpdump -i any -w capture.pcapng udp

3. 合并密钥
   cat /tmp/dtls.log /tmp/srtp.log > combined_keys.log

4. 一键解密
   python3 src/decrypt_session_pipeline.py capture.pcapng -k combined_keys.log --out-dir output/
```

## 解密原理简述

```
Signaling (WebSocket/HTTP)
    ↓ SDP Offer/Answer
ICE/STUN (UDP)
    ↓ 连通性检查
DTLS (UDP, 加密)          ← SSLKEYLOGFILE 解密
    ├─ SCTP/DataChannel   ← tshark 解析明文
    └─ SRTP Key 协商      ← SRTPKEYLOGFILE 导出
SRTP (UDP, 加密)          ← pylibsrtp 解密
    ├─ 视频 (H.264 / RED+VP8)
    └─ 音频 (Opus / G.711)
```
