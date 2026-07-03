# 调试 AudioDeviceMac 实操指引（路线 A）

目标：用 webrtc 源码自带的 `AppRTCMobile`（Mac 版）作为入口，在 `modules/audio_device/mac/audio_device_mac.cc` 真断点单步，对照 `docs/webrtc_audio.pdf` 中 Mac ADM 的章节进行学习。

---

## 0. 环境前置

| 路径 | 说明 |
|---|---|
| `/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src` | webrtc 源码根 |
| `/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/out/mac_static_debug` | debug 构建目录（is_debug=true, arm64） |
| `/Users/lizhengze/Desktop/demo/webrtc_src/depot_tools` | depot_tools |
| `/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/third_party/ninja/ninja` | 真正的 ninja 二进制（绕开 depot_tools wrapper） |

公司网络无法访问 `chrome-infra-packages.appspot.com`，因此 GN regen 时拉 vpython3 的 venv 会失败。规避方式（已验证）：

```bash
export VPYTHON_BYPASS="manually managed python not supported by chrome operations"
```

设了它之后，`vpython3` 会直接 `exec python3`，跳过 cipd 在线解析。

---

## 1. 编译 AppRTCMobile（mac arm64 debug）✅ 已完成

```bash
export VPYTHON_BYPASS="manually managed python not supported by chrome operations"
export PATH=/Users/lizhengze/Desktop/demo/webrtc_src/depot_tools:$PATH

/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/third_party/ninja/ninja \
  -C /Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/out/mac_static_debug \
  AppRTCMobile
```

注意：
- 不要用 `ninja`/`autoninja` 命令名（depot_tools wrapper 会因为 `out/.siso_deps` 存在而拒绝）；用 `third_party/ninja/ninja` 真二进制
- 第一次会触发 `Regenerating ninja files`，开了 `VPYTHON_BYPASS` 之后能跑通
- 全量编译 ≈ 20-40 分钟（M 系列），后续增量很快

产物（已验证）：

```
out/mac_static_debug/AppRTCMobile.app
├── Contents/MacOS/AppRTCMobile                              ← 75 MB，带 DWARF 调试符号
└── Contents/Frameworks/WebRTC.framework/Versions/A/WebRTC   ← 84 MB framework
```

符号验证（已通过）：

```
$ lldb out/mac_static_debug/AppRTCMobile.app/Contents/MacOS/AppRTCMobile
(lldb) image lookup -rn AudioDeviceMac::InitPlayout
  Summary: AppRTCMobile`webrtc::AudioDeviceMac::InitPlayout() at audio_device_mac.cc:940
(lldb) image lookup -rn AudioDeviceMac::implOutConverterProc
  Summary: AppRTCMobile`webrtc::AudioDeviceMac::implOutConverterProc(...) at audio_device_mac.cc:2238
```

注意符号在 `AppRTCMobile` 主二进制和 `WebRTC.framework` 里**都有一份**（静态链接 + 动态 framework 共存）。lldb 在 `AppRTCMobile` 进程里下断点会自动命中正确的那份。

---

## 2. 启动调试

### 方式 A：lldb 命令行（推荐先这种，离 ADM 内部最近）

```bash
lldb /Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/out/mac_static_debug/AppRTCMobile.app/Contents/MacOS/AppRTCMobile
```

或者直接加载预置的断点脚本：

```bash
lldb -s /Users/lizhengze/Desktop/demo/webrtc-demo/docs/lldb_audio_device_mac.lldb \
  /Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/out/mac_static_debug/AppRTCMobile.app/Contents/MacOS/AppRTCMobile
```

### 方式 B：Xcode Attach

1. Finder 双击 `AppRTCMobile.app` 启动
2. Xcode → File → Open... 选 `webrtc/src` 目录（让 Xcode 能找到源码）
3. Debug → Attach to Process → AppRTCMobile
4. ⇧⌘O 打开 `audio_device_mac.cc`，左侧栏点行号即可下断点

---

## 3. 触发音频路径

最快触发 ADM Init/Start 的方式：

1. 启动 AppRTCMobile，输入任意房间号（例如 `1234`）→ Connect
2. 此时即使没有第二个端，Mac 端也已经走完：
   - `RTCPeerConnectionFactory` 创建
   - `AudioDeviceModule::Create(kPlatformDefaultAudio,…)` → `AudioDeviceMac` ctor
   - `Init()` / `InitMicrophone()` / `InitSpeaker()` / `InitRecording()`
3. 当 ICE 连通 / 出现远端音频流时，会触发 `StartRecording` / `StartPlayout`，IO 回调开始流转

如果想脱离信令服务器、纯本地触发：用浏览器打开 `https://appr.tc/r/<room>`，再用 AppRTCMobile 输入同一个房间号。

---

## 4. 关键断点清单（对照 PDF 看效果最好）

文件：`/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/modules/audio_device/mac/audio_device_mac.cc`

| 行号 | 函数 | 看什么 |
|---|---|---|
| ~ 940 | `InitPlayout` | 输出端 AudioUnit 初始化，AudioConverter 配置（采样率/帧大小） |
| ~1077 | `InitRecording` | 输入端 AU 初始化，硬件 buffer 大小协商 |
| ~1273 | `StartRecording` | 启动 IOProc / CaptureWorkerThread |
| ~1415 | `StartPlayout` | 启动渲染（**注意 default device vs 普通 device 路径分叉**） |
| ~1886 | `objectListenerProc` | Core Audio 设备热插拔 / 默认设备切换回调 |
| ~2162 | `implDeviceIOProc` | **Default 设备的 IO 回调（核心）** |
| ~2237 | `implOutConverterProc` | AudioConverter 拉取播放数据 → `AudioDeviceBuffer` |
| ~2261 | `implInDeviceIOProc` | 非 default 输入设备的 IO 回调 |
| ~2358 | `RenderWorkerThread` | 播放线程主循环（消费环形缓冲，喂给 AU） |
| ~2423 | `CaptureWorkerThread` | 采集线程主循环（从环形缓冲拿录音帧，送 ADM Buffer） |

跨文件追线：

- `AudioDeviceBuffer::DeliverRecordedData` (`modules/audio_device/audio_device_buffer.cc`) — 录音数据离开 ADM 进 APM
- `AudioDeviceBuffer::RequestPlayoutData` — 播放线程向上层要 10ms PCM
- `AudioTransportImpl::RecordedDataIsAvailable` (`audio/audio_transport_impl.cc`) — APM/混音/编码入口

---

## 5. IO 回调断点的正确姿势

`implDeviceIOProc` / `implInDeviceIOProc` / `implOutConverterProc` 跑在 Core Audio 实时线程上，硬停会立刻让音频卡死或断流。建议：

### 用 log breakpoint（不停下，仅打印）

lldb 命令：

```lldb
breakpoint set -n AudioDeviceMac::implOutConverterProc \
  -C "po (UInt32)$arg1[0]" -C "frame $arg2 numChannels $arg3" \
  --auto-continue true
```

Xcode 里：右键断点 → Edit Breakpoint → Action: Log Message + 勾选 "Automatically continue after evaluating actions"。

### 真断的话，先放行 N 次

```lldb
breakpoint set -n AudioDeviceMac::implDeviceIOProc -i 200
```

`-i 200` 表示前 200 次忽略，避免一启动就卡死。

---

## 6. 常用 lldb 命令片段

```lldb
# 看当前线程在哪个 ADM 函数
bt 8

# ADM 内部状态
p _outDesiredFormat
p _outStreamFormat
p _renderDelayUs
p _captureDelayUs
p _ioBufferDurationFrames
p _outputDeviceID

# 看 AudioBuffer
p inputData->mNumberBuffers
p inputData->mBuffers[0].mDataByteSize

# 计算每次回调对应多少 ms 音频
expr (double)inNumberFrames / 48000.0 * 1000
```

---

## 7. 故障排查

| 现象 | 可能原因 | 处理 |
|---|---|---|
| `ninja: error: rebuilding 'build.ninja': subcommand failed` 且日志里有 `chrome-infra-packages` | 公司网络挡 cipd | `export VPYTHON_BYPASS=...`（见上） |
| `depot_tools/ninja.py: contains Siso state file` | wrapper 拒绝 ninja | 改用 `third_party/ninja/ninja` 真二进制 |
| 编译完跑起来听不到 mic 声 | 没给 AppRTCMobile 麦克风权限 | 系统设置 → 隐私 → 麦克风 → 勾选 AppRTCMobile |
| 断点不命中 | Xcode 用了别的源码副本 | `image lookup -n AudioDeviceMac::InitPlayout` 看符号路径 |

---

## 8. 学习路径建议

1. 先 `breakpoint set -n AudioDeviceMac::AudioDeviceMac`（构造）+ `Init` + `InitPlayout` + `InitRecording`，搞清楚启动顺序
2. 再下 `StartPlayout` / `StartRecording`，观察线程切换
3. 最后看 IO 回调（用 log 断点），结合 PDF 的"AudioDeviceMac 缓冲与时延"章节对照
4. 想看上游怎么把 PCM 喂下来：跟 `RequestPlayoutData` → `AudioDeviceBuffer::GetPlayoutData` → 上层 `AudioTransport`
