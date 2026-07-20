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

待 Task 2 补充。

## 3. 面试项目讲稿

待 Task 2 补充。

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

待 Task 2 补充。

## 6. SDP 与媒体协商

待 Task 2 补充。

## 7. ICE、STUN、TURN 与 NAT

待 Task 2 补充。

## 8. DTLS、SRTP、RTP 与 RTCP

待 Task 2 补充。

## 9. DataChannel 与 SCTP

待 Task 2 补充。

## 10. 编解码、RTP 负载与 FFmpeg

待 Task 2 补充。

## 11. 实验工具与自动化分析

待 Task 2 补充。

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
