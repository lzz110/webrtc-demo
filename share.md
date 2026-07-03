# WebRTC 解密历程分享 (share)

## 1. 目标
把 WebRTC 抓包中的关键链路讲清楚, 并尽可能自动化导出:
- 建联过程: Signaling -> ICE/STUN -> DTLS -> SRTP/SCTP
- 媒体导出: 解密后音视频
- DataChannel: SCTP 明文消息

## 2. 抓包归档
已将 `webrtc-demo` 下所有 `.pcapng` 统一归档到:
- `pcapng-all/`

当前包含:
- `native2webvideo.pcapng`
- `native2weblatest.pcapng`
- `web2native.pcapng`
- `web2web.pcapng`
- `native2web.pcapng`
- `native2webSRTP.pcapng`
- `0320_lsa_lzz.pcapng`
- `native2weblatest_decrypted_rtp_only.pcapng`
- `rtp_only.pcapng`
- `loopback_webrtc.pcapng`

## 3. 关键源码改动(重点)

源码路径: `/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/`

### 3.1 `rtc_base/openssl_stream_adapter.cc`
- 改了什么:
  - 新增 `DtlsKeyLogCallback(...)`。
  - 在 `SetupSSLContext()` 中调用 `SSL_CTX_set_keylog_callback(ctx, DtlsKeyLogCallback)`。
  - 通过环境变量 `SSLKEYLOGFILE` 把 BoringSSL key log 行写入文件。
- 为什么要改:
  - 原始流程里 DTLS 会话密钥没有稳定落盘, Wireshark 很难稳定解出 DTLS ApplicationData。
  - 没有 DTLS 明文就无法向上解析 SCTP/DataChannel。
- 结果:
  - 可稳定得到 NSS Key Log 格式内容, 支持 Wireshark/tshark 解密 DTLS->SCTP。

### 3.2 `pc/dtls_srtp_transport.cc`
- 改了什么:
  - 新增 `MaybeExportSrtpKeys(...)` 和 `BytesToHex(...)`。
  - 在 `ExtractParams(...)` 里拿到 `send_key/recv_key` 后导出 `SRTP_KEYS` 行。
  - 支持 `SRTPKEYLOGFILE`(和 `WEBRTC_SRTPKEYLOGFILE` 兜底)写文件。
- 为什么要改:
  - 仅有 `SSLKEYLOGFILE` 仍不足以让离线脚本稳定解 SRTP 双向媒体。
  - 需要显式落盘 SRTP 双向 key, 才能可靠做 SSRC 解密映射。
- 结果:
  - 可在离线脚本中按 client/server write key 双向解密 SRTP。

## 4. 解密历程(按时间顺序, 现象 -> 原因 -> 解决)

### 阶段 1: web2web 场景, DTLS 应用层无法稳定解密
- 对应抓包:
  - `pcapng-all/web2web.pcapng`
- 主要 key 文件尝试:
  - `webrtc-keys/sslkeys.log`
  - `webrtc-keys/sslkeys_new.log`
- 现象:
  - Wireshark 能看到握手阶段, 但 DTLS Application Data 无法稳定下钻到 SCTP/DataChannel 明文。
  - 同一条链路在不同浏览器版本、不同抓包会出现"有时可见, 有时不可见"。
- 原因:
  - web2web 常走浏览器默认路径, 更容易落到 DTLS/TLS1.3 相关行为。
  - keylog 即使有 CLIENT_RANDOM, 对应用层是否可稳定解密还受浏览器实现与 Wireshark 版本兼容性影响。
- 解决:
  - 暂时不把 web2web 当主验证样本。
  - 转向 native 参与的链路做主路径, 先打通"可复现、可自动化"的流程。

### 阶段 2: web2native 初期, 仍无法完整解析业务层
- 对应抓包:
  - `pcapng-all/web2native.pcapng`
  - 以及早期 native 互通抓包 `pcapng-all/native2web.pcapng`
- 主要 key 文件尝试:
  - `webrtc-keys/native_sslkeys.log`
  - `webrtc-keys/native_clientrandom_only.log`
- 现象:
  - 可以看到部分握手和媒体包, 但 DataChannel/SCTP 明文不完整或不可见。
  - SRTP 解密成功率不稳定, 无法稳定建立"会话密钥 -> SSRC"的映射。
- 原因:
  - 原生端导出的 key 信息不完整(只导出到某一层, 或导出时机不对)。
  - 单一 key 文件无法覆盖全部会话分支(重连、重协商、多条路径)。
- 解决:
  - 修改 `rtc_base/openssl_stream_adapter.cc`:
    - 新增 `DtlsKeyLogCallback(...)`。
    - 在 `SetupSSLContext()` 里调用 `SSL_CTX_set_keylog_callback(...)`。
    - 通过 `SSLKEYLOGFILE` 把 DTLS/TLS key log 行落盘。
  - 这样做的直接目的:
    - 让 Wireshark/tshark 能稳定解密 DTLS ApplicationData。
    - 先打通 SCTP/DataChannel 明文可见性。

### 阶段 3: 修改源码后, SCTP/DataChannel 可解密, 但 SRTP 仍有问题
- 对应抓包:
  - `pcapng-all/native2weblatest.pcapng`
  - `pcapng-all/native2webSRTP.pcapng`
- 主要 key 文件尝试:
  - `webrtc-keys/native_srtp_for_pathB.log`
  - `webrtc-keys/native_combined_keys.log`(逐步完善)
- 现象:
  - Wireshark 中可见 DTLS->SCTP 明文消息, msg/ack 可以读到。
  - 但媒体侧仍存在"只能解一侧/解密失败率高/视频帧异常"的问题。
- 原因:
  - SCTP 能解密不等于 SRTP 一定可解密, 二者依赖的会话匹配和方向映射不同。
  - SRTP 需要准确处理 client/server write key 与发送方向映射, 否则会出现认证失败。
- 解决:
  - 修改 `pc/dtls_srtp_transport.cc`:
    - 新增 `MaybeExportSrtpKeys(...)` 和 `BytesToHex(...)`。
    - 在 `ExtractParams(...)` 里导出 `SRTP_KEYS`(send_key/recv_key)。
    - 使用 `SRTPKEYLOGFILE`(兼容 `WEBRTC_SRTPKEYLOGFILE`) 输出会话 key。
  - 明确双向 key 映射规则(client_write/server_write)。
  - 在脚本中同时尝试 client/server 两组 SRTP key。
  - 逐个 SSRC 校验解密效果, 固定可用映射后再批量导出。

### 阶段 4: SRTP 可解密后, 遇到视频编码识别错误
- 对应抓包:
  - `pcapng-all/native2webvideo.pcapng`
- 主要 key 文件:
  - `webrtc-keys/native_combined_keys.log`
- 现象:
  - SRTP 解开后, 按 H264 路径提取视频仍失败, ffmpeg 报错。
  - NAL 统计出现大量异常类型, 与标准 H264 特征不匹配。
- 原因:
  - 该会话视频不是裸 H264 RTP。
  - SDP 明确协商了 `a=rtpmap:123 red/90000`, 实际负载为 RED 封装, 主编码是 VP8(PT=96)。
- 解决:
  - 增加 RED 解包(RFC2198) + VP8 RTP 描述符剥离(RFC7741)流程。
  - 输出 IVF 后再转 MP4, 不再强行按 H264 NAL 路径处理。

### 阶段 5: 全链路打通并自动化
- 对应抓包:
  - `pcapng-all/native2webvideo.pcapng`
- 使用 key 文件:
  - `webrtc-keys/native_combined_keys.log`
- 最终结果:
  - 建联链路可完整讲清楚: Signaling -> ICE/STUN -> DTLS -> SRTP/SCTP。
  - SCTP/DataChannel 明文可自动导出(msg/ack)。
  - 双端视频可稳定导出。
- 固化产物:
  - `test-parse/decrypt_session_pipeline.py`(一键总控)
  - `test-parse/export_sctp_plaintext.py`(SCTP 明文导出)
  - `test-parse/native2webvideo-test-decrypt.log`(模板化日志)

## 5. 自动化脚本沉淀

### 5.1 一键总控
- 脚本: `test-parse/decrypt_session_pipeline.py`
- 输入: `pcap + keylog`
- 输出:
  - 解密日志: `*-test-decrypt.log`
  - 双端视频: `*.mp4` + 中间 `*.ivf`
  - 日志内含: Signaling, ICE/STUN, DTLS, RTP Streams, SCTP 明文, Summary

示例:
```bash
python3 test-parse/decrypt_session_pipeline.py   pcapng-all/native2webvideo.pcapng   -k webrtc-keys/native_combined_keys.log   --out-dir test-parse   --log test-parse/native2webvideo-test-decrypt.log
```

### 5.2 SCTP 明文导出(独立)
- 脚本: `test-parse/export_sctp_plaintext.py`
- 说明: 自动调用 tshark 解析 DTLS->SCTP(PPID=51) 明文 JSON。
- 已支持: 更新日志时自动规范标点(中文标点 -> 英文半角)。

## 6. 对外讲解建议(5 分钟版本)
1. 先讲“为什么必须改源码”: 默认没有稳定导出可复现的 key 材料。
2. 再讲两处核心改动: `openssl_stream_adapter.cc` 和 `dtls_srtp_transport.cc`。
3. 然后按时间线讲 5 个阶段, 每阶段固定三句话(现象/原因/解决)。
4. 最后展示一键命令和最终日志, 让听众可复跑验证。
