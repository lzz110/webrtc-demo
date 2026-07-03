# WebRTC H.264 提取器 - 完整使用指南与原理实现

## 📑 目录

1. [功能概述](#功能概述)
2. [安装与依赖](#安装与依赖)
3. [命令详解](#命令详解)
4. [实现原理](#实现原理)
5. [核心算法详解](#核心算法详解)
6. [架构设计](#架构设计)
7. [故障排除](#故障排除)
8. [进阶用法](#进阶用法)

---

## 功能概述

### 主要功能

| 功能 | 说明 |
|------|------|
| **SRTP 解密** | 将加密的 WebRTC 抓包解密为 RTP 明文 |
| **H.264 提取** | 从 RTP 流中提取 H.264 视频帧 |
| **自动检测** | 自动识别所有视频流（SSRC） |
| **智能命名** | 按 `video_0xSSSSSSSS.mp4` 格式自动命名 |
| **单流过滤** | 支持指定 SSRC 提取特定视频流 |
| **pcapng 转换** | 生成供 Wireshark 分析的解密后抓包 |

### 支持的格式

- **输入**: `*.pcapng` (Wireshark 抓包文件)
- **密钥**: SSLKEYLOGFILE 格式
- **输出视频**: `*.mp4` (H.264 编码)
- **输出抓包**: `*.pcapng` (RTP 明文)

---

## 安装与依赖

### 系统要求

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# 下载 ffmpeg 并添加到 PATH
```

### Python 依赖

```bash
pip install scapy pylibsrtp
```

**依赖版本要求：**
- `scapy` >= 2.4.5
- `pylibsrtp` >= 1.0.0
- `ffmpeg` >= 4.0

---

## 命令详解

### 1. 自动提取视频（最简单用法）

```bash
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log
```

**输出：**
- `video_0x67018AED.mp4`
- `video_0x5959B53D.mp4`
- ...

**功能说明：**
- 自动检测所有 H.264 视频流
- 按 SSRC 自动命名输出文件
- 支持 SRTP 自动解密

---

### 2. 查看所有流

```bash
python3 webrtc_h264_extractor.py extract capture.pcapng -l
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -l
```

**输出示例：**
```
======================================================================
        SSRC       包数     PT                序列号范围
======================================================================
0x67018AED    1,572     96        11553 - 13124
0x5959B53D    1,571     96           636 - 2206
0xA4AA2637       14     97        20907 - 20920
...
```

---

### 3. 提取指定 SSRC

```bash
# 自动命名输出
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -s 0x67018AED

# 自定义输出文件名
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -s 0x67018AED -o myvideo.mp4
```

**输出：**
- `video_0x67018AED.mp4` 或 `myvideo.mp4`

---

### 4. 解密为 RTP 明文抓包

#### 4.1 保留所有包

```bash
python3 webrtc_h264_extractor.py decrypt capture.pcapng \
    -k keys.log \
    -o decrypted.pcapng
```

**特点：**
- 保留 TCP、UDP、STUN、DTLS 等所有包
- 只将 SRTP 包替换为 RTP 包
- 文件大小与原始抓包相近

---

#### 4.2 只保留 RTP 视频流

```bash
python3 webrtc_h264_extractor.py decrypt capture.pcapng \
    -k keys.log \
    -o rtp_only.pcapng \
    --rtp-only
```

**特点：**
- 过滤掉 TCP、STUN、DTLS、DNS 等非视频包
- 只保留 Payload Type 96-127 的 RTP 包
- 文件大小减少约 60%

---

#### 4.3 只保留指定 SSRC

```bash
python3 webrtc_h264_extractor.py decrypt capture.pcapng \
    -k keys.log \
    -o single_ssrc.pcapng \
    --rtp-only \
    -s 0x67018AED
```

**特点：**
- 只保留指定 SSRC 的 RTP 包
- 文件最小，Wireshark 加载最快
- 适合分析单一视频流

---

### 5. 高级选项

```bash
# 指定输出目录
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -d ./videos/

# 调整帧率（默认 30fps）
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -f 25

# 只分析不导出
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log --analyze
```

---

## 实现原理

### 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                    webrtc_h264_extractor.py                      │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────┐ │
│  │  SRTP Key   │  │   Scapy     │  │  H.264      │  │  ffmpeg │ │
│  │   Parser    │  │   Packets   │  │  Decoder    │  │ Encoder │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └────┬────┘ │
│         │                │                │              │      │
│         ▼                ▼                ▼              ▼      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              H264Extractor (核心类)                       │  │
│  │  - extract_from_pcap()    - 主提取函数                    │  │
│  │  - parse_fu_a()           - FU-A 分片重组                 │  │
│  │  - parse_stap_a()         - STAP-A 解析                   │  │
│  │  - frames_to_annexb()     - Annex B 转换                  │  │
│  │  - save_to_mp4()          - MP4 生成                      │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

### 核心流程

#### 1. SRTP 解密流程

```python
# 1. 加载密钥
key_material = bytes.fromhex("fe0ef3d6feb580add7677c59636ed13157b5e729de8771498829debf9531")
#     ↑ 16 bytes (Master Key)     ↑ 14 bytes (Master Salt)

# 2. 创建 SRTP Session
policy = pylibsrtp.Policy(
    key=key_material,
    srtp_profile=pylibsrtp.Policy.SRTP_PROFILE_AES128_CM_SHA1_80,
    ssrc_type=pylibsrtp.Policy.SSRC_ANY_INBOUND
)
session = pylibsrtp.Session(policy)

# 3. 解密每个包
for packet in packets:
    srtp_data = bytes(packet[UDP].payload)
    rtp_data = session.unprotect(srtp_data)  # ← 解密
    packet[UDP].payload = Raw(load=rtp_data)  # ← 替换 payload
```

**技术细节：**
- **加密算法**: AES-128-CM (Counter Mode)
- **认证算法**: HMAC-SHA1-80
- **密钥长度**: 30 bytes (16 bytes key + 14 bytes salt)
- **RFC 标准**: RFC 3711 (SRTP), RFC 6184 (RTP H.264)

---

#### 2. RTP 解析流程

```
RTP Header (12+ bytes)
┌─────────────────────────────────────────────────────────────┐
│ V=2 │ P │ X │ CC=0  │ M │      PT=96       │   Sequence    │
│  10 │ 0 │ 1 │  0000 │ 1 │    0 1100 000    │    Number     │
├─────────────────────────────────────────────────────────────┤
│                           Timestamp                         │
├─────────────────────────────────────────────────────────────┤
│                           SSRC                              │
├─────────────────────────────────────────────────────────────┤
│           Extension ID        │       Extension Length      │  ← 可选
├─────────────────────────────────────────────────────────────┤
│                      Extension Data...                      │  ← 可选
└─────────────────────────────────────────────────────────────┘
```

```python
class RTPHeader:
    @classmethod
    def parse(cls, data: bytes) -> 'RTPHeader':
        version = (data[0] >> 6) & 0x03        # 2 bits
        padding = bool((data[0] >> 5) & 0x01)  # 1 bit
        extension = bool((data[0] >> 4) & 0x01) # 1 bit
        csrc_count = data[0] & 0x0F             # 4 bits
        marker = bool((data[1] >> 7) & 0x01)   # 1 bit
        payload_type = data[1] & 0x7F          # 7 bits
        sequence_number = struct.unpack('>H', data[2:4])[0]
        timestamp = struct.unpack('>I', data[4:8])[0]
        ssrc = struct.unpack('>I', data[8:12])[0]
        
        # 计算 header 长度（包含 extension）
        header_len = 12 + csrc_count * 4
        if extension:
            ext_len = struct.unpack('>H', data[header_len+2:header_len+4])[0]
            header_len += 4 + ext_len * 4
```

---

#### 3. H.264 NAL 解析流程

##### 3.1 单 NAL 单元 (NAL Type 1-23)

```
RTP Payload
┌─────────────────────────────────────────┐
│ F │ NRI │ Type │      NAL Data...       │
│ 1 │  0  │ 00001│                        │  ← NAL Type = 1 (Non-IDR)
└─────────────────────────────────────────┘
│←1 byte→│
```

##### 3.2 STAP-A 聚合 (NAL Type 24)

```
RTP Payload
┌─────────────────────────────────────────────────────────────┐
│ F │ NRI │ Type │ Size │ NAL 1 │ Size │ NAL 2 │ ...         │
│ 1 │  0  │ 11000│ 16bit│       │ 16bit│       │             │
└─────────────────────────────────────────────────────────────┘
│←1 byte→│←2 bytes→│
```

**解析代码：**
```python
def parse_stap_a(self, payload: bytes) -> List[NALUnit]:
    nals = []
    offset = 1  # 跳过 STAP-A NAL header
    
    while offset + 2 < len(payload):
        # 读取 NAL 大小（大端序 16-bit）
        nal_size = struct.unpack('>H', payload[offset:offset+2])[0]
        offset += 2
        
        # 提取 NAL 数据
        nal_data = payload[offset:offset+nal_size]
        nals.append(NALUnit(data=nal_data, ...))
        offset += nal_size
    
    return nals
```

##### 3.3 FU-A 分片 (NAL Type 28)

```
RTP Payload
┌─────────────────────────────────────────────────────────────┐
│ F │ NRI │ Type │ S │ E │ R │ Type │      FU Payload...     │
│ 1 │  0  │ 11100│ 1 │ 0 │ 0 │00101 │                        │
└─────────────────────────────────────────────────────────────┘
│←1 byte→│←      FU Header (1 byte)      →│

S (1 bit): Start of fragment
E (1 bit): End of fragment
R (1 bit): Reserved (0)
Type (5 bits): Original NAL type
```

**重组算法：**
```python
def parse_fu_a(self, payload: bytes, fu_buffer: Dict) -> List[NALUnit]:
    nal_byte = payload[0]       # FU-A NAL header (0x7C for FU-A with NRI=3)
    fu_header = payload[1]      # FU header
    
    start_bit = (fu_header >> 7) & 1    # 分片开始
    end_bit = (fu_header >> 6) & 1      # 分片结束
    orig_nal_type = fu_header & 0x1F   # 原始 NAL 类型 (如 5=IDR)
    
    # 重建原始 NAL header
    # 例如: (0x7C & 0xE0) | 5 = 0x65 (IDR with NRI=3)
    orig_nal_header = bytes([(nal_byte & 0xE0) | orig_nal_type])
    
    key = orig_nal_type  # 使用原始 NAL 类型作为重组 key
    
    if start_bit:
        # 开始新分片：创建 NAL buffer
        fu_buffer[key] = orig_nal_header + payload[2:]
        return []
    
    if key in fu_buffer:
        # 中间或结束分片：追加数据
        fu_buffer[key] += payload[2:]
        
        if end_bit:
            # 分片完成：返回完整 NAL
            complete = fu_buffer.pop(key)
            return [NALUnit(data=complete, nal_type=orig_nal_type, ...)]
    
    return []
```

---

#### 4. 帧边界检测

```python
# 方法 1: RTP Marker 位（最可靠）
if rtp.marker:
    # Marker = 1 表示这是帧的最后一个包
    save_current_frame()
    start_new_frame()

# 方法 2: 时间戳变化
if rtp.timestamp != last_timestamp:
    # 时间戳变化 = 新帧开始
    save_current_frame()
    start_new_frame()

# 方法 3: FU-A Start 位（关键帧检测）
if fu_header & 0x80:  # Start bit = 1
    if current_frame:
        save_current_frame()
    start_new_frame()
```

---

#### 5. Annex B 格式转换

```python
def frames_to_annexb(self, frames: List[List[NALUnit]]) -> bytes:
    """
    将帧列表转换为 H.264 Annex B 格式
    
    Annex B 格式:
    [00 00 00 01] [NAL Header] [NAL Payload]
    [00 00 00 01] [NAL Header] [NAL Payload]
    ...
    """
    data = bytearray()
    start_code = b'\x00\x00\x00\x01'  # 4-byte start code
    
    for frame in frames:
        for nal in frame:
            data.extend(start_code)
            data.extend(nal.data)
    
    return bytes(data)
```

**示例：**
```
输入 (RTP payloads):
  Frame 0: [SPS NAL][PPS NAL][IDR NAL]
  Frame 1: [P NAL]
  Frame 2: [P NAL]

输出 (Annex B):
  00 00 00 01 [SPS NAL]
  00 00 00 01 [PPS NAL]
  00 00 00 01 [IDR NAL]
  00 00 00 01 [P NAL]
  00 00 00 01 [P NAL]
```

---

#### 6. MP4 生成

```python
def save_to_mp4(self, frames: List[List[NALUnit]], 
                output_path: str, framerate: int = 30) -> bool:
    # 1. 生成 Annex B 数据
    annexb_data = self.frames_to_annexb(frames)
    
    # 2. 写入临时 .264 文件
    with tempfile.NamedTemporaryFile(suffix='.264', delete=False) as f:
        f.write(annexb_data)
        temp_264 = f.name
    
    # 3. 使用 ffmpeg 转码为 MP4
    cmd = [
        'ffmpeg', '-y',
        '-f', 'h264',              # 输入格式
        '-i', temp_264,            # 输入文件
        '-r', str(framerate),      # 输出帧率
        '-vsync', 'cfr',           # 恒定帧率
        '-c:v', 'libx264',         # 编码器
        '-preset', 'ultrafast',    # 快速编码
        '-crf', '23',              # 质量
        '-movflags', '+faststart', # Web 优化
        output_path
    ]
    
    subprocess.run(cmd, ...)
```

**为什么需要重新编码？**
- 裸 H.264 (Annex B) 没有时间戳信息
- 直接 copy 会导致播放器无法解析帧率
- 重新编码生成正确的时间戳

---

## 架构设计

### 类图

```
┌─────────────────────────────────────────────────────────────────┐
│                         H264Extractor                           │
├─────────────────────────────────────────────────────────────────┤
│ - stats: Dict                    # 统计信息                     │
│ - decryptor: SRTPDecryptor       # SRTP 解密器                  │
├─────────────────────────────────────────────────────────────────┤
│ + extract_from_pcap()            # 主提取函数                   │
│ + parse_fu_a()                   # FU-A 分片重组               │
│ + parse_stap_a()                 # STAP-A 聚合解析             │
│ + frames_to_annexb()             # Annex B 格式转换            │
│ + save_to_mp4()                  # MP4 生成                    │
│ + analyze_frames()               # 帧分析                      │
└─────────────────────────────────────────────────────────────────┘
                              △
                              │
┌─────────────────────────────────────────────────────────────────┐
│                      SRTPDecryptor                              │
├─────────────────────────────────────────────────────────────────┤
│ - session: pylibsrtp.Session                                    │
├─────────────────────────────────────────────────────────────────┤
│ + decrypt(data: bytes) -> bytes                                 │
└─────────────────────────────────────────────────────────────────┘
                              △
                              │
┌─────────────────────────────────────────────────────────────────┐
│                        SRTPKey                                  │
├─────────────────────────────────────────────────────────────────┤
│ + parse_keylog(path: str) -> Dict                               │
└─────────────────────────────────────────────────────────────────┘
```

---

### 数据流

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  pcapng  │────▶│   Scapy  │────▶│   RTP    │────▶│   NAL    │
│   File   │     │  rdpcap  │     │  Parser  │     │  Parser  │
└──────────┘     └──────────┘     └──────────┘     └────┬─────┘
                                                        │
                       ┌────────────────────────────────┘
                       ▼
              ┌─────────────────┐
              │   FU-A Buffer   │  ◄── 分片重组状态机
              │   (per SSRC)    │
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Frame Builder  │  ◄── 按时间戳/Marker 分帧
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  Annex B Encoder│  ◄── 添加 start code
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │  ffmpeg (MP4)   │  ◄── 视频编码
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │   output.mp4    │
              └─────────────────┘
```

---

## 核心算法详解

### 1. FU-A 分片重组状态机

```
                    ┌─────────────┐
         ┌─────────▶│    IDLE     │◀────────┐
         │          └──────┬──────┘         │
         │                 │ Start=1        │
         │                 ▼                │
         │          ┌─────────────┐         │
         │          │  BUFFERING  │         │
         │          │ (积累数据)   │         │
         │          └──────┬──────┘         │
         │                 │                 │
    End=1│            Start=0               │
         │         (中间分片)                │
         │                 │                 │
         │                 ▼                 │
         │          ┌─────────────┐         │
         └──────────│   COMPLETE  │─────────┘
                    │ 返回完整NAL │
                    └─────────────┘
```

### 2. 视频流检测算法

```python
def is_video_stream(packets: List) -> bool:
    """
    检测是否为 H.264 视频流的条件：
    1. Payload Type 在 96-127 之间（WebRTC 动态类型）
    2. NAL 类型包含 1, 5, 24, 28（标准 H.264）
    3. 包数 > 100（排除控制流）
    4. H.264 特征占比 > 30%
    """
    h264_types = {1, 5, 24, 28}  # Non-IDR, IDR, STAP-A, FU-A
    
    h264_count = sum(
        1 for pkt in packets
        if get_nal_type(pkt) in h264_types
    )
    
    ratio = h264_count / len(packets)
    return ratio > 0.3 and len(packets) > 100
```

---

## 故障排除

### 问题 1: "未找到 H.264 视频流"

**原因分析：**
1. 抓包文件损坏或不包含 RTP 流
2. SRTP 未正确解密（密钥错误）
3. 视频编码不是 H.264（可能是 VP8/VP9/AV1）

**排查方法：**
```bash
# 1. 检查原始抓包
tshark -r capture.pcapng -Y "udp" | head

# 2. 检查是否识别为 RTP
tshark -r capture.pcapng -Y "rtp" | head

# 3. 检查 NAL 类型
tshark -r capture.pcapng -Y "rtp" -T fields -e data | \
    xxd -r -p | hexdump -C | head

# 4. 手动指定 SSRC 测试
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -s 0xXXXXXXXX
```

---

### 问题 2: 视频播放花屏/卡顿

**原因分析：**
1. FU-A 分片重组错误（丢包或乱序）
2. 缺少 SPS/PPS（关键帧信息丢失）
3. 时间戳错误导致帧率不正确

**排查方法：**
```python
# 检查帧结构
for i, frame in enumerate(frames[:5]):
    nal_types = [nal.nal_type for nal in frame]
    print(f"Frame {i}: {nal_types}")
    # 第一帧应该包含: [7, 8, 6, 5] 或 [7, 8, 5]
    # 即: SPS, PPS, [SEI], IDR

# 检查是否有 SPS/PPS
has_sps = any(nal.nal_type == 7 for nal in all_nals)
has_pps = any(nal.nal_type == 8 for nal in all_nals)
print(f"Has SPS: {has_sps}, Has PPS: {has_pps}")
```

---

### 问题 3: 解密失败

**原因分析：**
1. 密钥格式不正确
2. pylibsrtp 版本不兼容
3. SRTP profile 不匹配

**排查方法：**
```python
# 检查密钥长度
key = bytes.fromhex("fe0ef3d6feb580add7677c59636ed13157b5e729de8771498829debf9531")
print(f"Key length: {len(key)} bytes")  # 应该是 30

# 检查 pylibsrtp 版本
import pylibsrtp
print(pylibsrtp.__version__)

# 测试解密
policy = pylibsrtp.Policy(
    key=key,
    srtp_profile=pylibsrtp.Policy.SRTP_PROFILE_AES128_CM_SHA1_80,
    ssrc_type=pylibsrtp.Policy.SSRC_ANY_INBOUND
)
session = pylibsrtp.Session(policy)
```

---

## 进阶用法

### 批量处理多个抓包

```bash
#!/bin/bash
# batch_extract.sh

KEYLOG="webrtc_keys.log"
OUTPUT_DIR="./extracted_videos"

mkdir -p "$OUTPUT_DIR"

for pcap in *.pcapng; do
    echo "Processing: $pccap"
    python3 webrtc_h264_extractor.py extract "$pcap" \
        -k "$KEYLOG" \
        -d "$OUTPUT_DIR"
done
```

### 提取关键帧用于缩略图

```python
# 修改脚本，只提取 IDR 帧
for i, frame in enumerate(frames):
    nal_types = [nal.nal_type for nal in frame]
    if 5 in nal_types:  # IDR 帧
        # 保存为单独的图片或视频片段
        save_frame(frame, f"keyframe_{i}.jpg")
```

### 生成报告

```python
# 生成详细的分析报告
report = {
    'file': input_file,
    'total_packets': stats['total_packets'],
    'video_streams': len(video_streams),
    'frames': stats['frames'],
    'duration': frames[-1].timestamp - frames[0].timestamp,
    'bitrate': calculate_bitrate(frames),
    'resolution': detect_resolution(frames),
}
```

---

## 附录

### H.264 NAL 类型参考

| Type | 名称 | 说明 |
|------|------|------|
| 0 | Unspecified | 未指定 |
| 1 | Non-IDR Slice | 非关键帧切片 |
| 5 | IDR Slice | 关键帧（Instantaneous Decoder Refresh） |
| 6 | SEI | 补充增强信息 |
| 7 | SPS | 序列参数集（Sequence Parameter Set） |
| 8 | PPS | 图像参数集（Picture Parameter Set） |
| 24 | STAP-A | 单时间聚合包 A |
| 28 | FU-A | 分片单元 A |

### WebRTC Payload Type

| PT | 用途 |
|----|------|
| 96 | 视频（H.264/VP8/VP9） |
| 97 | 视频（H.264/VP8/VP9） |
| 111 | 音频（Opus） |

---

*文档版本: 2.0*  
*更新日期: 2026-03-19*  
*作者: AI Assistant*
