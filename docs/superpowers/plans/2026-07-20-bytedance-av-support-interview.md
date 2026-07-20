# 字节音视频技术支持专家面试手册 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于仓库现有 WebRTC 实验材料，创建一份偏理解型、可用于简历表达、知识复习和模拟面试的音视频技术支持面试手册。

**Architecture:** 使用单一主文档 `docs/bytedance_av_support_interview.md`，按“项目表达 → 实验主线问题 → 生产排障迁移 → 岗位扩展 → 模拟面试”组织。项目事实必须链接到仓库证据；未实际做过的 CDN、HLS、RTMP 和线上排障内容必须标为理论扩展，不冒充生产经验。

**Tech Stack:** Markdown、WebRTC、Wireshark/tshark、Python、FFmpeg、Git。

---

### Task 1: 建立手册骨架与项目证据索引

**Files:**
- Create: `docs/bytedance_av_support_interview.md`
- Reference: `docs/project_for_resume.md`
- Reference: `docs/native2web-pcap-analysis.md`
- Reference: `docs/web2web-pcap-analysis.md`
- Reference: `docs/sdp_information_analysis.md`
- Reference: `share.md`
- Reference: `src/README.md`

- [ ] **Step 1: 创建固定章节骨架**

文档必须按以下一级章节排列：

```markdown
# 字节音视频技术支持专家面试准备手册

## 1. 使用说明与项目边界
## 2. 简历中的项目描述
## 3. 面试项目讲稿
## 4. 项目证据索引
## 5. WebRTC 建联与信令
## 6. SDP 与媒体协商
## 7. ICE、STUN、TURN 与 NAT
## 8. DTLS、SRTP、RTP 与 RTCP
## 9. DataChannel 与 SCTP
## 10. 编解码、RTP 负载与 FFmpeg
## 11. 实验工具与自动化分析
## 12. 技术支持场景题
## 13. CDN、HTTP、DNS 与流媒体协议
## 14. Linux 与日志排障
## 15. 模拟面试
## 16. 一周复习计划
## 17. 面试表达边界
```

- [ ] **Step 2: 写清项目边界**

开篇必须明确以下事实：

```text
这是个人 WebRTC 原理学习实验，不是生产项目；DTLS/SRTP 解密依赖本地可控环境和主动导出的 key；真实客户网络包通常无法直接解密，生产定位应依赖日志、指标、信令、连接状态、网络质量和可观察字段。
```

- [ ] **Step 3: 建立证据索引表**

证据表至少包含以下映射：

| 面试主题 | 仓库证据 |
| --- | --- |
| Offer/Answer、ICE、DTLS 角色 | `docs/native2web-pcap-analysis.md` |
| Web-Web 候选与信令 | `docs/web2web-pcap-analysis.md` |
| SDP 字段 | `docs/sdp_information_analysis.md` |
| DTLS/SRTP key 与完整链路 | `share.md`、`src/README.md` |
| SCTP/DataChannel | `src/export_sctp_plaintext.py` |
| H264 RTP 解析 | `src/webrtc_h264_extractor.py` |
| RED + VP8 | `src/red_vp8_extract.py` |
| 一键实验分析 | `src/decrypt_session_pipeline.py` |

- [ ] **Step 4: 验证骨架和证据链接**

Run:

```bash
rg -n '^## ' docs/bytedance_av_support_interview.md
for f in docs/project_for_resume.md docs/native2web-pcap-analysis.md docs/web2web-pcap-analysis.md docs/sdp_information_analysis.md share.md src/README.md src/export_sctp_plaintext.py src/webrtc_h264_extractor.py src/red_vp8_extract.py src/decrypt_session_pipeline.py; do test -f "$f" || exit 1; done
```

Expected: 显示 17 个一级章节，所有引用文件存在，退出码为 0。

- [ ] **Step 5: 提交骨架**

```bash
git add docs/bytedance_av_support_interview.md
git commit -m "docs: outline av support interview guide"
```

### Task 2: 完成项目描述与实验主线问题库

**Files:**
- Modify: `docs/bytedance_av_support_interview.md`
- Reference: `docs/native2web-pcap-analysis.md`
- Reference: `docs/sdp_information_analysis.md`
- Reference: `share.md`

- [ ] **Step 1: 写项目表达材料**

必须包含：

- 一句话定位：为系统理解 WebRTC 原理而搭建的 Native-Web 互通与协议分析实验。
- 简历三条：互通环境、可控实验抓包分析、FFmpeg/编解码与文档沉淀。
- 一分钟讲稿：背景、做法、典型案例、能力边界。
- 三分钟讲稿：按 Signaling → ICE → DTLS/SRTP → SCTP/RTP → RED+VP8 展开。

- [ ] **Step 2: 按统一模板写核心问题**

每个核心问题使用以下格式：

```markdown
### 问题：<问题>

**完整回答**

<原理、因果关系和关键术语>

**结合本项目**

<具体抓包帧号、SDP 字段或脚本行为>

**可能追问**

- <追问 1>
- <追问 2>

**30 秒回答**

<可口述的压缩答案>
```

- [ ] **Step 3: 覆盖 WebRTC 主线问题**

至少完成以下问题：

1. WebRTC 为什么需要独立信令，Offer/Answer 做了什么？
2. `setLocalDescription`、`setRemoteDescription` 和 Trickle ICE 的顺序是什么？
3. SDP 中 `m=`、`a=rtpmap`、`a=fmtp`、`mid`、`BUNDLE` 分别有什么作用？
4. Payload Type、SSRC、MID、RID 的区别是什么？
5. ICE candidate 的 host、srflx、relay 是什么，如何选出 candidate pair？
6. STUN 和 TURN 的区别，什么情况下必须使用 TURN？
7. `setup:actpass` 和 `setup:active` 如何决定 DTLS Client/Server？
8. SDP fingerprint 如何防止 DTLS 中间人攻击？
9. DTLS、SRTP、RTP、RTCP 之间是什么关系？
10. SRTP 为什么需要区分发送和接收方向的 key？
11. RTP 序列号、时间戳、SSRC 各自解决什么问题？
12. RTCP 的 SR、RR、NACK、PLI、FIR、TWCC 分别有什么作用？
13. DataChannel 为什么使用 SCTP over DTLS，可靠性如何配置？
14. DataChannel 的 ordered、maxRetransmits、maxPacketLifeTime 如何取舍？
15. 为什么把 RED + VP8 误当 H264 会导致提取失败？
16. H264 的 Single NAL、STAP-A、FU-A 如何封装进 RTP？
17. Opus 为什么适合实时音频，丢包时如何处理？
18. FFmpeg 在实验中承担什么角色，转码和转封装有什么区别？

- [ ] **Step 4: 验证核心问题数量与实验术语**

Run:

```bash
test "$(rg -c '^### 问题：' docs/bytedance_av_support_interview.md)" -ge 18
rg -n '3383|setup:actpass|setup:active|BUNDLE|RED|VP8|STAP-A|FU-A|PPID' docs/bytedance_av_support_interview.md
```

Expected: 核心问题不少于 18 个，实验关键术语均有命中。

- [ ] **Step 5: 提交实验主线题库**

```bash
git add docs/bytedance_av_support_interview.md
git commit -m "docs: add webrtc interview question bank"
```

### Task 3: 完成技术支持场景题与生产迁移边界

**Files:**
- Modify: `docs/bytedance_av_support_interview.md`

- [ ] **Step 1: 定义统一排障方法**

场景回答必须按以下顺序展开：

```text
确认影响范围和复现条件 → 收集客户端/服务端/网络证据 → 按信令、网络、传输、媒体、渲染分层 → 提出验证假设 → 临时止损 → 根因与长期改进
```

- [ ] **Step 2: 完成核心场景题**

每题必须包含“需要什么证据、如何缩小范围、常见根因、不能直接解密抓包时怎么办”，至少覆盖：

1. WebRTC 一直连接不上。
2. 能建联但没有声音。
3. 单向音频。
4. 视频卡顿、花屏或频繁冻结。
5. 首帧慢或加入房间慢。
6. 仅部分网络或地区失败。
7. TURN 使用率突然升高。
8. DataChannel 能建立但消息丢失或乱序。
9. 客户只提供加密抓包，如何继续定位。
10. 如何把一次客户问题沉淀为知识库和自动化工具。

- [ ] **Step 3: 明确生产迁移边界**

场景章节必须包含以下结论：

```text
实验解密用于理解协议；生产排障优先看 getStats、SDK 日志、信令日志、ICE/DTLS 状态、选中候选对、RTT、丢包率、抖动、码率、帧率、NACK/PLI、音频能量和服务端指标。
```

- [ ] **Step 4: 验证场景覆盖**

Run:

```bash
rg -n '连接不上|单向音频|首帧|TURN 使用率|加密抓包|getStats|临时止损|长期改进' docs/bytedance_av_support_interview.md
```

Expected: 每个指定场景和生产排障关键字至少命中一次。

- [ ] **Step 5: 提交场景题**

```bash
git add docs/bytedance_av_support_interview.md
git commit -m "docs: add av support troubleshooting scenarios"
```

### Task 4: 补齐岗位扩展知识与模拟面试

**Files:**
- Modify: `docs/bytedance_av_support_interview.md`

- [ ] **Step 1: 写 CDN、HTTP、DNS 和流媒体协议问题**

至少包含：

- DNS 解析异常如何导致拉流失败。
- HTTP 缓存、Range 请求、状态码和回源。
- CDN 调度、缓存命中、回源、边缘节点故障。
- RTMP、HTTP-FLV、HLS、WebRTC 的时延与适用场景对比。
- HLS 首帧慢、卡顿和 404 的排查方法。

这些答案必须标注为“岗位理论扩展”，不得写成项目已验证内容。

- [ ] **Step 2: 写 Linux 和日志排障问题**

覆盖以下命令和用途：

```text
dig/nslookup：DNS；curl：HTTP/TLS/耗时；ss：连接与端口；tcpdump：抓包；ping/mtr：连通性和路径；top/ps：CPU；free/vm_stat：内存；iostat：磁盘；journalctl：服务日志；grep/awk/sed：日志过滤。
```

- [ ] **Step 3: 写模拟面试**

至少包含 15 轮问答，顺序为：

1. 项目介绍。
2. 为什么做这个项目。
3. WebRTC 建联全流程。
4. SDP 关键字段。
5. ICE 与 TURN。
6. DTLS/SRTP。
7. 真实抓包为什么不能解密。
8. 无声音排查。
9. 卡顿排查。
10. RED + VP8 案例。
11. FFmpeg 能力。
12. HLS/RTMP/WebRTC 对比。
13. CDN 问题排查。
14. Python 工具化。
15. 如何服务客户并推动共性问题改进。

- [ ] **Step 4: 验证扩展内容与模拟轮数**

Run:

```bash
rg -n '岗位理论扩展|DNS|Range|回源|HTTP-FLV|HLS|RTMP|dig|curl|tcpdump|mtr|journalctl' docs/bytedance_av_support_interview.md
test "$(rg -c '^### 模拟 [0-9]' docs/bytedance_av_support_interview.md)" -ge 15
```

Expected: 扩展主题和工具均有命中，模拟面试不少于 15 轮。

- [ ] **Step 5: 提交岗位扩展和模拟面试**

```bash
git add docs/bytedance_av_support_interview.md
git commit -m "docs: add av support interview simulations"
```

### Task 5: 完成一周计划、边界审校与最终验证

**Files:**
- Modify: `docs/bytedance_av_support_interview.md`
- Modify: `README.md`

- [ ] **Step 1: 写一周复习计划**

安排如下：

1. Day 1：项目讲稿、证据索引和 WebRTC 全流程。
2. Day 2：SDP、ICE、STUN、TURN、NAT。
3. Day 3：DTLS、SRTP、RTP、RTCP、DataChannel。
4. Day 4：H264、VP8、Opus、RED、FFmpeg。
5. Day 5：无声音、卡顿、建联失败等场景排障。
6. Day 6：CDN、DNS、HTTP、HLS、RTMP、Linux。
7. Day 7：15 轮模拟面试和薄弱项回补。

每一天必须包含“学习内容、口述练习、当天产出”。

- [ ] **Step 2: 写面试边界清单**

必须明确：

- 可以说“在可控环境导出 key 验证协议”，不能说“可以解密客户抓包”。
- 可以说“熟悉 FFmpeg 常用处理流程”，不能说“独立实现 FFmpeg 播放器内核”。
- 可以说“掌握 CDN/HLS/RTMP 排查方法”，除非有真实经历，否则不能说“负责过生产 CDN”。
- 对不会的问题使用“已知事实 → 假设 → 验证方法”的回答结构。

- [ ] **Step 3: 在根 README 增加面试手册入口**

在 `README.md` 的关键文档列表中增加：

```markdown
- 字节音视频技术支持面试手册：
  [docs/bytedance_av_support_interview.md](docs/bytedance_av_support_interview.md)
```

- [ ] **Step 4: 执行最终验证**

Run:

```bash
test -f docs/bytedance_av_support_interview.md
test "$(rg -c '^## ' docs/bytedance_av_support_interview.md)" -eq 17
test "$(rg -c '^### 问题：' docs/bytedance_av_support_interview.md)" -ge 18
test "$(rg -c '^### 模拟 [0-9]' docs/bytedance_av_support_interview.md)" -ge 15
rg -n '可控实验环境|不对应真实生产环境|岗位理论扩展|一周复习计划' docs/bytedance_av_support_interview.md
rg -n 'bytedance_av_support_interview.md' README.md
git diff --check
```

Expected: 所有命令退出码为 0；17 个一级章节、至少 18 个核心问题、至少 15 轮模拟面试；无 Markdown 空白错误。

- [ ] **Step 5: 最终事实审校**

逐项核对：

- `native2web` 实验中 Web 为 Offerer、Native Answer 为 `setup:active`、Native 发起 DTLS Client Hello。
- BUNDLE 包含音频与 DataChannel，SCTP 端口为 5000。
- RED 外层 PT 为 123，主编码识别为 VP8，不写成 H264 成功提取案例。
- 生产场景不依赖解密客户抓包。

- [ ] **Step 6: 提交最终手册**

```bash
git add docs/bytedance_av_support_interview.md README.md
git commit -m "docs: complete bytedance av support interview guide"
```
