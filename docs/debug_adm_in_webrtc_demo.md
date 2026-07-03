# 在 webrtc-demo（SwiftUI + Web 互通）里 Debug Mac ADM

目标：保持现有 `webrtc-demo` ↔ `webrtc-web` 互通的开发流程不变，但在 Mac 端调用 WebRTC 时，能在 `audio_device_mac.cc` 等 Native ADM 源文件下断点单步。

> 相比路线 A 用 `AppRTCMobile`，这条路线的好处是直接复用你已经写好的 SwiftUI 客户端 + WebSocket 信令 + DataChannel，调试场景就是你日常开发时的真实场景。

---

## 0. 先确认前置条件

✅ webrtc-demo Xcode 工程现在引用的 framework：

```
path = /Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/out/mac_framework_debug/WebRTC.framework
```

✅ 这个 framework 是 debug 配置（`out/mac_framework_debug/args.gn`）：

```
is_debug = true
enable_stripping = false
use_rtti = true
rtc_enable_objc_api = true
```

✅ 已验证 framework 内嵌 DWARF 调试符号，行号对得上：

```
$ lldb /…/out/mac_framework_debug/WebRTC.framework/Versions/A/WebRTC
(lldb) image lookup -rn AudioDeviceMac::InitPlayout
  Summary: WebRTC`webrtc::AudioDeviceMac::InitPlayout() at audio_device_mac.cc:940
```

✅ Xcode 工程 Debug 配置是 `COPY_PHASE_STRIP=NO`、`DEBUG_INFORMATION_FORMAT=dwarf`，拷贝时不会 strip。

也就是说**断点能力已经天然就绪**，只剩 Xcode 怎么找到源码 + 怎么打断点。

---

## 1. 同步 framework（保险一步）

源码动了之后要重 build framework，否则断点会和实际执行错位。

```bash
export VPYTHON_BYPASS="manually managed python not supported by chrome operations"

/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/third_party/ninja/ninja \
  -C /Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/out/mac_framework_debug \
  sdk:mac_framework_objc
```

如果输出 `ninja: no work to do.`，说明 framework 已是最新，跳过即可。

---

## 2. 让 Xcode 能找到源码（关键）

WebRTC 源码不在 webrtc-demo 工程里，但 framework 的 DWARF 里记录的源文件路径都是绝对路径（`/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/modules/audio_device/mac/audio_device_mac.cc`）。Xcode/lldb 默认就能打开。

如果你想在 Xcode Project Navigator 里方便浏览源码，做一次性配置：

**方式 A（推荐，零侵入）**：用 Xcode 的 `File → Open Quickly`（⇧⌘O）按文件名打开
- 输入 `audio_device_mac.cc` → Xcode 会通过 lldb 解析 DWARF 找到文件

**方式 B（持久化）**：把 webrtc 源码目录拖进工程（不勾选 "Copy items"，不勾选 "Add to targets"）
- 拖 `webrtc/src/modules/audio_device/mac` 进 webrtc-demo 工程
- 仅作为 Source Group 引用，不参与编译

---

## 3. 启动调试

### 第一步：启动 web 端（你已经在用的）

```bash
cd /path/to/webrtc-web
npm start  # 或者你信令服务器的启动方式，监听 :8080/ws
```

### 第二步：用 Xcode 跑 webrtc-demo

1. Xcode 打开 `webrtc-demo.xcodeproj`
2. ⇧⌘O 打开 `audio_device_mac.cc`
3. 在你想观察的行打断点（推荐位置见下文）
4. ⌘R Run

> ⚠️ 第一次运行 macOS 会弹麦克风权限，必须允许，否则 ADM 初始化会走异常分支。

### 第三步：在 webrtc-demo UI 里触发音频路径

1. 输入房间号（默认 `demo`）→ "加入房间"
2. 浏览器打开同样的 web 端，加入同一房间
3. 在 Mac 端点 "发起连接（Offer）" → 这一步就会触发 ADM：
   - `AudioDeviceMac` ctor → `Init` → `InitMicrophone` / `InitSpeaker`
   - SDP 协商完成后 → `InitRecording` / `InitPlayout`
   - ICE 连通后 → `StartRecording` / `StartPlayout` → IO 回调开始流转

---

## 4. 推荐断点（在 Xcode 中）

文件：`/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/modules/audio_device/mac/audio_device_mac.cc`

**生命周期断点（普通断点即可，命中频率低）**

| 行 | 函数 | 看什么 |
|---|---|---|
| 940 | `InitPlayout` | AU 初始化，AudioConverter 配置 |
| 1077 | `InitRecording` | 输入端初始化，硬件 buffer |
| 1273 | `StartRecording` | 启动 IOProc / CaptureWorkerThread |
| 1415 | `StartPlayout` | 启动渲染（注意 default vs 普通设备） |
| 1886 | `objectListenerProc` | 设备热插拔回调 |

**IO 回调断点（实时线程，必须改成 log 断点，否则会卡死音频）**

| 行 | 函数 | 备注 |
|---|---|---|
| 2162 | `implDeviceIOProc` | Default 设备 IO 回调（核心） |
| 2237 | `implOutConverterProc` | 拉取播放数据 |
| 2261 | `implInDeviceIOProc` | 非 default 输入回调 |
| 2358 | `RenderWorkerThread` | 播放线程主循环 |
| 2423 | `CaptureWorkerThread` | 采集线程主循环 |

**改 log 断点的方法（Xcode）**：

1. 右键断点 → "Edit Breakpoint..."
2. 点 "Add Action" → 选 "Log Message"
3. 输入想打印的内容，例如：
   ```
   IOProc tick: numFrames=@inNumberFrames@ ts=@inOutputTime->mHostTime@
   ```
4. **勾选** "Automatically continue after evaluating actions"

---

## 5. 跨文件追线（理解 ADM 数据流向）

录音方向（话筒 → 编码器）：

```
implInDeviceIOProc / CaptureWorkerThread
  └→ AudioDeviceBuffer::DeliverRecordedData    (modules/audio_device/audio_device_buffer.cc)
       └→ AudioTransportImpl::RecordedDataIsAvailable  (audio/audio_transport_impl.cc)
            └→ APM (AEC/NS/AGC)
                 └→ Encoder（Opus 等）
```

播放方向（解码器 → 扬声器）：

```
implOutConverterProc / RenderWorkerThread
  └→ AudioDeviceBuffer::RequestPlayoutData     (modules/audio_device/audio_device_buffer.cc)
       └→ AudioDeviceBuffer::GetPlayoutData
            ↑ 上层 AudioTransportImpl::NeedMorePlayData 喂入混音后 PCM
```

在这些跨文件断点上能直观看出 PDF 里讲的"AudioDeviceBuffer 是 ADM 与上层之间的缓冲边界"。

---

## 6. 常用 lldb 命令（Xcode 调试控制台直接输入）

```lldb
# 看当前线程栈
bt 12

# ADM 内部状态
po _outDesiredFormat
po _outStreamFormat
p _renderDelayUs
p _captureDelayUs
p _ioBufferDurationFrames
p _outputDeviceID
p _inputDeviceID
p _initialized
p _playing
p _recording

# 看 AU 回调里的 buffer
p inputData->mNumberBuffers
p inputData->mBuffers[0].mDataByteSize
p inputData->mBuffers[0].mNumberChannels

# 估算每次 IO 回调对应 ms 数（对照 PDF 里的"10ms 帧"概念）
expr (double)inNumberFrames / 48000.0 * 1000

# 看当前进程里 ADM 实例地址
expr (void*)this
```

---

## 7. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| 断点显示空心、命中不了 | Xcode 没找到 framework 里的源码路径 | `image list WebRTC` 看 framework 路径；确认 framework 是 debug build |
| 断点位置代码灰显（"Code is unavailable due to optimization"） | framework 是 release build | 重 build：见第 1 节命令 |
| 加房间后立刻崩溃 / 没声 | 没给麦克风权限 | 系统设置 → 隐私 → 麦克风 → 允许 webrtc-demo |
| IO 回调断点一断就卡死、音频卡顿 | IO 在实时线程，硬断会把流停住 | 改 log 断点（见第 4 节） |
| `image lookup` 找不到 InitPlayout | framework 引用错了路径 / strip 过 | 检查工程 `FRAMEWORK_SEARCH_PATHS` 指向的是 `mac_framework_debug` |
| 改了 webrtc 源码后 Xcode 行号对不上 | framework 没重 build | 跑第 1 节的 ninja 命令再 ⌘R |

---

## 8. 学习路径建议（对照 PDF 的 AudioDeviceMac 章节）

1. 打开 PDF 找到 `AudioDeviceMac` 那一节
2. 在 Xcode 加入断点 `AudioDeviceMac::AudioDeviceMac`、`Init`、`InitPlayout`、`InitRecording` （都是普通断点）
3. 启动 webrtc-demo，加房间，发起连接
4. 让程序停在 `InitPlayout`，单步 (F6) 走完整段，对照 PDF 看：
   - 怎么找 default output device（`kAudioHardwarePropertyDefaultOutputDevice`）
   - 怎么打开 AudioUnit（`kAudioUnitSubType_DefaultOutput`/`HALOutput`）
   - AudioConverter 初始化（`outDesiredFormat → outStreamFormat`）
5. 单步进入 `StartPlayout` 看 IO 回调是怎么注册上去的
6. 把 `implOutConverterProc` 改成 log 断点，启动后看每次回调的 numberDataPackets，结合 PDF 的"10ms 帧"对一对
7. 观察录音方向：在 `implDeviceIOProc` 处 log，看到的就是 PDF 里讲的 mic 数据进入 ADM 的入口

完成后你应该对 Mac ADM 的"如何拿到 hardware buffer / 如何转换格式 / 如何与上层 AudioDeviceBuffer 接口交互"有完整心智模型。

---

## 附：从零重建 Xcode 工程引用（仅当 framework 引用坏掉时用）

如果不慎删掉了工程里的 framework 引用：

1. Xcode → 选中 target webrtc-demo
2. General → Frameworks, Libraries, and Embedded Content → "+"
3. "Add Other" → "Add Files..."
4. 选择：`/Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/out/mac_framework_debug/WebRTC.framework`
5. Embed 模式选 "Embed & Sign"
6. Build Settings → `FRAMEWORK_SEARCH_PATHS` 加：
   ```
   /Users/lizhengze/Desktop/demo/webrtc_src/webrtc/src/out/mac_framework_debug
   ```
