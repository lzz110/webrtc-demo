# webrtc-demo

一个用于系统学习 WebRTC 原理的实验项目。

项目围绕 Native 端与 Web 端的互通实验展开，覆盖信令交换、ICE/STUN、DTLS、SRTP、SCTP/DataChannel、音视频媒体流分析，以及相关实验脚本、抓包样本和分析文档沉淀。

## 项目目标

这个仓库的重点不是业务功能，而是通过可控实验环境理解 WebRTC 的关键链路：

- 搭建 Native 与 Web 端互通实验环境
- 观察和验证 Signaling、ICE、DTLS、SRTP、DataChannel 的工作过程
- 使用 Wireshark、tshark、Python 辅助做抓包分析和实验复盘
- 结合 FFmpeg 与编解码基础，理解媒体封装、RTP 负载格式和码流提取过程

## 重要说明

本仓库中的抓包解密、明文验证和媒体导出能力，仅用于本地可控实验环境下的协议学习与原理验证。

它不代表真实生产环境中的通用解密能力。真实工作中的音视频问题定位，通常更多依赖日志、指标、信令信息、抓包特征和环境信息，而不是直接获取可解密明文。

## 仓库结构

```text
.
├── docs/              项目分析文档、实验总结、简历项目包装材料
├── pcapng-all/        抓包样本
├── src/               Python / Lua 实验分析工具
├── test-parse/        样例输出、兼容入口、参考资料
├── webrtc-demo/       Mac Native 端实验工程
├── webrtc-demo.xcodeproj
├── webrtc-keys/       实验用 keylog 样本
├── webrtc-web/        Web 端互通与信令服务
└── share.md           项目复盘与分享材料
```

补充说明：

- `src/` 是当前主工具目录
- `test-parse/` 保留了旧入口和样例资料，里面的同名 Python 脚本是转发到 `src/` 的兼容包装
- `webrtc-web/` 是独立的 Node.js 小项目
- `pego_homework/` 是独立嵌套仓库，不属于当前主项目的一部分

## 快速开始

### 1. Web 端互通实验

启动 Web 信令与前端页面：

```bash
cd webrtc-web
npm install
npm start
```

默认访问：

- [http://localhost:8080](http://localhost:8080)

更多说明见：

- [webrtc-web/README.md](/Users/lizhengze/Desktop/demo/webrtc-demo/webrtc-web/README.md:1)

### 2. Mac Native 端实验

使用 Xcode 打开：

- [webrtc-demo.xcodeproj](/Users/lizhengze/Desktop/demo/webrtc-demo/webrtc-demo.xcodeproj/project.pbxproj:1)

Native 端用于和 Web 端做互通实验，验证：

- Offer / Answer
- ICE 候选交换
- 音频链路
- DataChannel 消息通信

### 3. Python 抓包分析工具

安装依赖：

```bash
pip install scapy pylibsrtp
```

另需：

- `tshark`
- `ffmpeg`

查看工具完整说明：

- [src/README.md](/Users/lizhengze/Desktop/demo/webrtc-demo/src/README.md:1)

常见入口：

```bash
python3 src/decrypt_session_pipeline.py capture.pcapng -k combined_keys.log --out-dir output/
python3 src/export_sctp_plaintext.py capture.pcapng -k combined_keys.log
python3 src/red_vp8_extract.py capture.pcapng -k combined_keys.log -s 0xAABBCCDD
python3 src/webrtc_h264_extractor.py extract capture.pcapng -k combined_keys.log
```

## 关键文档

- 项目/简历包装：
  [docs/project_for_resume.md](/Users/lizhengze/Desktop/demo/webrtc-demo/docs/project_for_resume.md:1)
- WebRTC 复盘分享：
  [share.md](/Users/lizhengze/Desktop/demo/webrtc-demo/share.md:1)
- Web 端说明：
  [webrtc-web/README.md](/Users/lizhengze/Desktop/demo/webrtc-demo/webrtc-web/README.md:1)
- 工具说明：
  [src/README.md](/Users/lizhengze/Desktop/demo/webrtc-demo/src/README.md:1)
- 典型抓包分析：
  [docs/native2web-pcap-analysis.md](/Users/lizhengze/Desktop/demo/webrtc-demo/docs/native2web-pcap-analysis.md:1)
  [docs/web2web-pcap-analysis.md](/Users/lizhengze/Desktop/demo/webrtc-demo/docs/web2web-pcap-analysis.md:1)
  [docs/sdp_information_analysis.md](/Users/lizhengze/Desktop/demo/webrtc-demo/docs/sdp_information_analysis.md:1)

## 这个项目适合怎么理解

如果你是来读这个仓库的，最合适的理解方式是：

- 它是一个 WebRTC 学习实验项目
- 它包含互通 Demo、抓包样本、分析工具和文档
- 它适合用来理解 WebRTC 协议链路、媒体封装和问题分析方法
- 它不应被理解为真实线上环境中的通用解密平台

## 后续可继续整理的方向

- 为 `pcapng-all/` 和 `webrtc-keys/` 增加样本说明索引
- 为 `docs/` 补一份总览目录
- 为 `webrtc-demo/` 增加 Native 端运行说明
- 为 Python 工具补一组最小可复现实验样例
