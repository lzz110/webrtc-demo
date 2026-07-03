# WebRTC H.264 提取器 - 快速参考

## 🚀 常用命令

```bash
# 自动提取所有视频（最简单）
python3 webrtc_h264_extractor.py extract loopback_webrtc.pcapng -k webrtc_dtls_keys.log

# 查看所有流
python3 webrtc_h264_extractor.py extract loopback_webrtc.pcapng -l

# 提取指定流
python3 webrtc_h264_extractor.py extract loopback_webrtc.pcapng -k webrtc_dtls_keys.log -s 0x67018AED

# 解密为 RTP 明文（供 Wireshark）
python3 webrtc_h264_extractor.py decrypt loopback_webrtc.pcapng -k webrtc_dtls_keys.log -o out.pcapng --rtp-only
```

---

## 📊 输出文件命名规则

| 场景 | 命令 | 输出文件名 |
|------|------|------------|
| 自动提取 | `-k keys.log` | `video_0x67018AED.mp4` |
| 指定 SSRC | `-s 0x67018AED` | `video_0x67018AED.mp4` |
| 自定义名 | `-s 0x67018AED -o out.mp4` | `out.mp4` |
| 指定目录 | `-d ./videos/` | `./videos/video_0x67018AED.mp4` |

---

## 🔧 解密模式对比

| 模式 | 命令 | 保留内容 | 文件大小 |
|------|------|----------|----------|
| 完整解密 | `decrypt ... -o out.pcapng` | 所有包（TCP/UDP/STUN/DTLS/RTP） | ~4.0M |
| 仅 RTP | `decrypt ... --rtp-only` | 仅 RTP 视频流 | ~1.7M |
| 单流 | `decrypt ... --rtp-only -s 0xSSSSSSSS` | 仅指定 SSRC | ~1.7M |

---

## 🐛 故障速查

| 问题 | 解决方案 |
|------|----------|
| "未找到 H.264" | 使用 `-l` 查看 SSRC，确认密钥正确 |
| 视频花屏 | 检查是否有 SPS/PPS（NAL type 7/8） |
| 解密失败 | 确认密钥长度 30 bytes，pylibsrtp 已安装 |
| 播放卡顿 | 尝试调整帧率 `-f 25` 或 `-f 30` |

---

## 📐 H.264 NAL 类型速查

```
Type 1: Non-IDR (P帧)
Type 5: IDR (关键帧)
Type 6: SEI (补充信息)
Type 7: SPS (序列参数集)
Type 8: PPS (图像参数集)
Type 24: STAP-A (聚合包)
Type 28: FU-A (分片包)
```

---

## 🔗 依赖安装

```bash
# macOS
brew install ffmpeg
pip install scapy pylibsrtp

# Ubuntu
sudo apt-get install ffmpeg
pip install scapy pylibsrtp
```

---

## 💡 提示

1. **密钥文件格式**: `SRTP <hex_key>` (60 hex chars = 30 bytes)
2. **WebRTC 时钟**: 90 kHz (timestamp 差 3000 ≈ 33ms = 30fps)
3. **视频 PT 范围**: 96-127 (动态 payload type)
4. **Annex B start code**: `00 00 00 01`

---

*快速参考 v1.0 | 2026-03-19*
