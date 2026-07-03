# WebRTC H.264 视频流提取器

## 概述

这是一个专业的 WebRTC 抓包分析工具，能够从 pcapng 格式的网络抓包文件中提取 H.264 视频流，支持 SRTP 加密流的解密，并自动将视频保存为 MP4 格式。

## 核心能力

### 1. SRTP 解密支持
- **自动检测加密流**: 通过采样分析自动识别 SRTP 加密的数据包
- **SSLKEYLOGFILE 解析**: 支持从标准密钥日志文件提取 SRTP 密钥
- **实时解密**: 使用 pylibsrtp 库对加密包进行实时解密处理
- **pcapng 解密导出**: 可将 SRTP 解密为 RTP 明文 pcapng，供 Wireshark 分析

### 2. RTP 协议解析
- **完整 RTP 头部解析**: 支持版本、填充、扩展、CSRC、Marker、Payload Type、序列号、时间戳、SSRC 等字段
- **扩展头部处理**: 自动计算并跳过 RTP 扩展头部
- **多 SSRC 支持**: 可同时处理多个同步源标识符

### 3. H.264 NAL 单元处理
- **NAL 类型识别**: 支持所有标准 H.264 NAL 类型（0-28）
- **STAP-A 聚合包解析**: 处理单时间聚合包，提取多个 NAL 单元
- **FU-A 分片重组**: 自动重组被分片的 NAL 单元，确保视频完整性
- **Annex B 格式转换**: 将 NAL 单元转换为标准 Annex B 格式（添加起始码）

### 4. 智能视频流检测
- **自动 SSRC 发现**: 扫描并列出所有 RTP 流的 SSRC
- **视频流识别**: 基于 Payload Type（96-127）和 H.264 NAL 特征自动识别视频流
- **多流批量提取**: 支持一次性提取多个视频流到独立文件

### 5. 视频导出
- **MP4 格式输出**: 使用 ffmpeg 将 H.264 流封装为 MP4
- **帧率控制**: 可自定义输出视频的帧率
- **时间戳校正**: 使用 CFR（恒定帧率）模式确保播放流畅

### 6. pcapng 解密与过滤（新增）
- **SRTP 转 RTP**: 将加密的 SRTP 抓包解密为明文的 RTP 抓包
- **智能过滤**: 可只保留 RTP 视频流，过滤 TCP、STUN、DTLS 等控制包
- **SSRC 过滤**: 支持只保留特定 SSRC 的数据包
- **Wireshark 兼容**: 输出的 pcapng 可直接用 Wireshark 分析

## 技术架构

```
┌─────────────────────────────────────────────────────────────┐
│                     输入层 (Input Layer)                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │  pcapng文件  │  │  keylog文件  │  │  命令行参数          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   解密层 (Decryption Layer)                  │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │ SRTP检测        │  │ SRTP解密 (pylibsrtp)            │   │
│  │ - 版本检查      │  │ - AES128_CM_SHA1_80             │   │
│  │ - NAL类型分析   │  │ - 自动密钥匹配                  │   │
│  └─────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    解析层 (Parsing Layer)                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ RTP解析器    │  │ H.264解析器  │  │ NAL单元管理器        │  │
│  │ - 头部解析   │  │ - NAL类型识别│  │ - STAP-A处理        │  │
│  │ - SSRC过滤   │  │ - 分片重组   │  │ - FU-A重组          │  │
│  └─────────────┘  └─────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    输出层 (Output Layer)                     │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │ 帧重组          │  │ MP4导出 (ffmpeg)                │   │
│  │ - 时间戳边界    │  │ - H.264 → MP4                   │   │
│  │ - Marker检测    │  │ - 元数据注入                    │   │
│  └─────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## 关键类与数据结构

### RTPHeader (RTP 头部)
```python
@dataclass
class RTPHeader:
    version: int          # RTP 版本 (应为 2)
    padding: bool         # 填充标志
    extension: bool       # 扩展标志
    csrc_count: int       # CSRC 计数
    marker: bool          # 帧结束标记
    payload_type: int     # 负载类型
    sequence_number: int  # 序列号
    timestamp: int        # 时间戳
    ssrc: int             # 同步源标识
    header_len: int       # 头部总长度
```

### NALUnit (NAL 单元)
```python
@dataclass
class NALUnit:
    data: bytes      # NAL 数据
    nal_type: int    # NAL 类型 (0-31)
    f_bit: int       # 禁止位
    nri: int         # 参考重要性
    source: str      # 来源 (SINGLE/STAP/FUA)
```

### H.264 NAL 类型映射
| 类型 | 名称 | 说明 |
|------|------|------|
| 0 | Unspecified | 未指定 |
| 1 | Non-IDR | 非关键帧切片 |
| 5 | IDR | 关键帧（Instantaneous Decoder Refresh）|
| 6 | SEI | 补充增强信息 |
| 7 | SPS | 序列参数集 |
| 8 | PPS | 图像参数集 |
| 9 | AUD | 访问单元分隔符 |
| 24 | STAP-A | 单时间聚合包 A |
| 28 | FU-A | 分片单元 A |

## 处理流程

### 1. 单流提取流程
```
读取 pcapng → 检测/解密 SRTP → 解析 RTP → 提取 H.264 NAL
     ↓
重组 FU-A 分片 → 按时间戳分帧 → 转换为 Annex B → ffmpeg 导出 MP4
```

### 2. 自动批量提取流程
```
扫描所有 SSRC → 识别视频流特征 → 筛选候选流
     ↓
按包数排序 → 逐个提取 → 生成独立 MP4 文件
```

### 3. pcapng 解密流程
```
读取 SRTP pcapng → 加载密钥 → 逐包解密 → 可选过滤
     ↓
替换 UDP payload → 保存为 RTP pcapng → Wireshark 分析
```

## 命令行用法

### 子命令结构
```
webrtc_h264_extractor.py [extract|decrypt] [options]
```

### extract 子命令（默认）- 提取视频

#### 自动提取所有视频流
```bash
# 自动提取所有视频流（自动命名: video_0xSSSSSSSS.mp4）
python3 webrtc_h264_extractor.py extract capture.pcapng -k webrtc_keys.log

# 提取到指定目录
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -d ./videos/
```

#### 提取特定 SSRC
```bash
# 只提取特定 SSRC
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -s 0x67018aed

# 提取并指定输出文件名
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -s 0x67018aed -o myvideo.mp4
```

#### 查看和分析
```bash
# 查看所有 SSRC
python3 webrtc_h264_extractor.py extract capture.pcapng -l

# 仅分析不导出
python3 webrtc_h264_extractor.py extract capture.pcapng -k keys.log -a
```

### decrypt 子命令 - 解密 pcapng（供 Wireshark 分析）

#### 解密保留所有包（文件较大）
```bash
python3 webrtc_h264_extractor.py decrypt \
    capture.pcapng -k keys.log -o decrypted.pcapng
```

#### 只保留 RTP 视频流（推荐，文件较小）
```bash
python3 webrtc_h264_extractor.py decrypt \
    capture.pcapng -k keys.log -o rtp_only.pcapng --rtp-only
```

#### 只保留特定 SSRC（最小文件，Wireshark 加载最快）
```bash
python3 webrtc_h264_extractor.py decrypt \
    capture.pcapng -k keys.log -o single_ssrc.pcapng \
    --rtp-only -s 0x67018aed
```

### 参数说明

#### extract 子命令参数
| 参数 | 说明 | 示例 |
|------|------|------|
| `input` | 输入 pcapng 文件 | `capture.pcapng` |
| `-k, --keylog` | SSLKEYLOGFILE 密钥文件 | `webrtc_keys.log` |
| `-s, --ssrc` | 指定 SSRC（十六进制） | `0x67018aed` |
| `-o, --output` | 输出文件（单流模式） | `output.mp4` |
| `-d, --output-dir` | 输出目录（自动模式） | `./videos/` |
| `-f, --framerate` | 输出帧率 | `30` |
| `-l, --list` | 只列出 SSRC | - |
| `-a, --analyze` | 只分析不导出 | - |

#### decrypt 子命令参数
| 参数 | 说明 | 示例 |
|------|------|------|
| `input` | 输入 SRTP pcapng 文件 | `capture.pcapng` |
| `-o, --output` | 输出 RTP pcapng 文件（必需） | `decrypted.pcapng` |
| `-k, --keylog` | SSLKEYLOGFILE 密钥文件（必需） | `keys.log` |
| `--rtp-only` | 只保留 RTP 视频流 | - |
| `-s, --ssrc` | 只保留指定 SSRC | `0x67018aed` |

## 依赖要求

### Python 包
```bash
pip install scapy pylibsrtp
```

### 系统工具
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Windows
# 下载并安装 ffmpeg，添加到 PATH
```

## 密钥日志格式

脚本支持标准 SSLKEYLOGFILE 格式的 SRTP 密钥：

```
# 格式 1: SRTP <client_random_hex> <key_salt_hex>
SRTP a1b2c3d4e5f6... 0123456789abcdef0123456789abcdef0123456789abcdef0123456789ab

# 格式 2: SRTP <key_salt_hex>
SRTP 0123456789abcdef0123456789abcdef0123456789abcdef0123456789ab
```

密钥材料长度：30 字节（16 字节密钥 + 14 字节盐值）

## 输出示例

### 分析输出
```
============================================================
帧结构分析 (前10帧)
============================================================
帧   0: [IDR ] 3 NALs (SPS, PPS, IDR), 12,345 bytes
帧   1: [P   ] 1 NALs (Non-IDR),  8,234 bytes
帧   2: [P   ] 1 NALs (Non-IDR),  7,891 bytes
...

============================================================
NAL 类型统计
============================================================
  IDR         :   120 (  5.2%)
  Non-IDR     : 2,150 ( 93.1%)
  SPS         :     1 (  0.0%)
  PPS         :     1 (  0.0%)
  SEI         :    38 (  1.6%)
```

### 视频提取输出
```
============================================================
自动检测视频流...
============================================================

检测到 1 个视频流:

  序号         SSRC       包数                  输出文件
-------------------------------------------------------
   1 0x67018AED    3,456      video_0x67018AED.mp4

============================================================
开始提取视频流...
============================================================

[1/1] 提取 SSRC 0x67018AED...
✅ 已保存: ./video_0x67018AED.mp4 (1,234,567 bytes)
```

### pcapng 解密输出
```
读取: capture.pcapng
  找到 SRTP 密钥: 0123456789abcdef...
  已加载密钥，开始解密...
  模式: 只保留 RTP 视频流
  过滤: 只保留 SSRC 0x67018AED
  已处理 500/3456 个包...
  已处理 1000/3456 个包...

保存到: single_ssrc.pcapng
  保留 1234/3456 个包 (过滤 2222 个)

============================================================
解密完成
============================================================
总包数:     3,456
UDP 包:     3,200
成功解密:   1,234
跳过(非SRTP): 1,966
过滤(非RTP): 2222

现在可以用 Wireshark 打开: single_ssrc.pcapng
```

## 使用场景

1. **WebRTC 调试**: 分析视频通话质量问题
2. **安全审计**: 检查加密视频传输内容
3. **性能分析**: 统计帧率、码率、NAL 分布
4. **故障排查**: 验证视频流是否正确传输
5. **取证分析**: 从抓包恢复视频内容
6. **协议分析**: 解密后用 Wireshark 深度分析 RTP 流

## 注意事项

1. **密钥安全**: keylog 文件包含敏感密钥信息，请妥善保管
2. **性能考虑**: 大文件处理可能需要较长时间，建议分批处理
3. **ffmpeg 依赖**: 确保 ffmpeg 已正确安装并在 PATH 中
4. **内存使用**: 大抓包文件可能占用较多内存，建议有足够 RAM
5. **NAL 兼容性**: 仅支持 H.264 编码的视频流，不支持 VP8/VP9/AV1

## 故障排除

### 问题：未找到视频流
- 检查是否提供了正确的 keylog 文件（如果是加密流）
- 使用 `-l` 参数查看所有 SSRC
- 确认抓包确实包含视频数据

### 问题：解密失败
- 验证 keylog 文件格式是否正确
- 确认密钥与抓包匹配（同一 session）
- 检查 pylibsrtp 是否正确安装

### 问题：视频播放异常
- 尝试调整帧率参数 `-f`
- 检查是否有丢包（查看序列号连续性）
- 使用 `-a` 参数分析 NAL 结构

### 问题：Wireshark 无法打开解密后的 pcapng
- 确认输出文件扩展名为 `.pcapng`
- 检查是否有写入权限
- 尝试使用 `--rtp-only` 减少包数量
