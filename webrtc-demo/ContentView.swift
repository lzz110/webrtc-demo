//
//  ContentView.swift
//  webrtc-demo
//
//  Created by lizhengze on 2026/2/25.
//

import SwiftUI
import Combine
import AVFoundation

// MARK: - 主视图

struct ContentView: View {
    var body: some View {
        TabView {
            ModuleTestView()
                .tabItem {
                    Label("模块测试", systemImage: "checkmark.shield")
                }
            CaptureView()
                .tabItem {
                    Label("音视频采集", systemImage: "camera.fill")
                }
            WebBridgeView()
                .tabItem {
                    Label("Web 互通", systemImage: "network")
                }
        }
        .frame(minWidth: 700, minHeight: 560)
    }
}

// MARK: - Tab 1: 模块测试

struct TestResult: Identifiable {
    let id = UUID()
    let name: String
    let passed: Bool
    let detail: String
}

class ModuleTestRunner: ObservableObject {
    @Published var results: [TestResult] = []
    @Published var isRunning = false
    @Published var summary = ""

    func runAll() {
        isRunning = true
        results = []
        summary = ""

        Task.detached(priority: .userInitiated) {
            var list: [TestResult] = []
            list.append(self.testFactory())
            list.append(self.testIceCandidate())
            list.append(self.testSessionDescription())
            list.append(self.testConfiguration())
            list.append(self.testPeerConnection())
            list.append(self.testDataChannel())
            list.append(self.testMediaConstraints())
            list.append(self.testVideoEncoderFactory())
            list.append(self.testVideoDecoderFactory())
            list.append(self.testAudioTrack())
            list.append(self.testVideoTrack())
            list.append(self.testCameraDevices())

            let passed = list.filter { $0.passed }.count
            let text = "测试完成：\(passed) / \(list.count) 通过"
            await MainActor.run {
                self.results = list
                self.summary = text
                self.isRunning = false
            }
        }
    }

    // MARK: 各测试用例

    private func testFactory() -> TestResult {
        let factory = RTCPeerConnectionFactory()
        return .init(name: "RTCPeerConnectionFactory 创建", passed: true,
                     detail: "类型: \(type(of: factory))")
    }

    private func testIceCandidate() -> TestResult {
        let sdp = "candidate:1 1 UDP 2130706431 192.168.1.1 54321 typ host"
        let c = RTCIceCandidate(sdp: sdp, sdpMLineIndex: 0, sdpMid: "audio")
        let ok = c.sdp == sdp
        return .init(name: "RTCIceCandidate 创建", passed: ok,
                     detail: ok ? "sdpMid=\(c.sdpMid ?? "-")" : "sdp 不匹配")
    }

    private func testSessionDescription() -> TestResult {
        let sdp = RTCSessionDescription(type: .offer, sdp: "v=0\r\n")
        let ok = sdp.type == .offer
        return .init(name: "RTCSessionDescription 创建", passed: ok,
                     detail: ok ? "type=offer" : "type 不匹配")
    }

    private func testConfiguration() -> TestResult {
        let config = RTCConfiguration()
        config.iceServers = [RTCIceServer(urlStrings: ["stun:stun.l.google.com:19302"])]
        let ok = config.iceServers.count == 1
        return .init(name: "RTCConfiguration + ICE Server", passed: ok,
                     detail: ok ? "ICE 服务器数=\(config.iceServers.count)" : "配置失败")
    }

    private func testPeerConnection() -> TestResult {
        let factory = RTCPeerConnectionFactory()
        let config = RTCConfiguration()
        config.iceServers = [RTCIceServer(urlStrings: ["stun:stun.l.google.com:19302"])]
        let constraints = RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: nil)
        let pc = factory.peerConnection(with: config, constraints: constraints, delegate: nil)
        let ok = pc != nil
        return .init(name: "RTCPeerConnection 创建", passed: ok,
                     detail: ok ? "signalingState=\(pc!.signalingState.rawValue)" : "创建失败")
    }

    private func testDataChannel() -> TestResult {
        let factory = RTCPeerConnectionFactory()
        let config = RTCConfiguration()
        config.iceServers = []
        let constraints = RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: nil)
        guard let pc = factory.peerConnection(with: config, constraints: constraints, delegate: nil) else {
            return .init(name: "RTCDataChannel 创建", passed: false, detail: "PeerConnection 创建失败")
        }
        let dcConfig = RTCDataChannelConfiguration()
        dcConfig.isOrdered = true
        let dc = pc.dataChannel(forLabel: "test", configuration: dcConfig)
        let ok = dc != nil
        return .init(name: "RTCDataChannel 创建", passed: ok,
                     detail: ok ? "label=\(dc!.label)" : "创建失败")
    }

    private func testMediaConstraints() -> TestResult {
        let mandatory: [String: String] = [
            kRTCMediaConstraintsOfferToReceiveAudio: kRTCMediaConstraintsValueTrue,
            kRTCMediaConstraintsOfferToReceiveVideo: kRTCMediaConstraintsValueTrue
        ]
        let c = RTCMediaConstraints(mandatoryConstraints: mandatory, optionalConstraints: nil)
        return .init(name: "RTCMediaConstraints 创建", passed: true,
                     detail: "类型: \(type(of: c))")
    }

    private func testVideoEncoderFactory() -> TestResult {
        let f = RTCDefaultVideoEncoderFactory()
        let codecs = f.supportedCodecs()
        let ok = codecs.count > 0
        return .init(name: "视频编码器工厂", passed: ok,
                     detail: ok ? codecs.map { $0.name }.joined(separator: " / ") : "无编码器")
    }

    private func testVideoDecoderFactory() -> TestResult {
        let f = RTCDefaultVideoDecoderFactory()
        let codecs = f.supportedCodecs()
        let ok = codecs.count > 0
        return .init(name: "视频解码器工厂", passed: ok,
                     detail: ok ? codecs.map { $0.name }.joined(separator: " / ") : "无解码器")
    }

    private func testAudioTrack() -> TestResult {
        let factory = RTCPeerConnectionFactory()
        let source = factory.audioSource(with: nil)
        let track = factory.audioTrack(with: source, trackId: "audio0")
        let ok = track.trackId == "audio0"
        return .init(name: "RTCAudioTrack 创建", passed: ok,
                     detail: ok ? "trackId=\(track.trackId), enabled=\(track.isEnabled)" : "创建失败")
    }

    private func testVideoTrack() -> TestResult {
        let factory = RTCPeerConnectionFactory()
        let source = factory.videoSource()
        let track = factory.videoTrack(with: source, trackId: "video0")
        let ok = track.trackId == "video0"
        return .init(name: "RTCVideoTrack 创建", passed: ok,
                     detail: ok ? "trackId=\(track.trackId), enabled=\(track.isEnabled)" : "创建失败")
    }

    private func testCameraDevices() -> TestResult {
        let devices = RTCCameraVideoCapturer.captureDevices()
        let ok = devices.count > 0
        let names = devices.map { $0.localizedName }.joined(separator: " / ")
        return .init(name: "摄像头设备枚举", passed: ok,
                     detail: ok ? names : "未找到摄像头设备")
    }
}

struct ModuleTestView: View {
    @StateObject private var runner = ModuleTestRunner()

    var body: some View {
        VStack(spacing: 0) {
            // 顶部工具栏
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("WebRTC 模块测试")
                        .font(.headline)
                    if !runner.summary.isEmpty {
                        Text(runner.summary)
                            .font(.caption)
                            .foregroundColor(allPassed ? .green : .orange)
                    }
                }
                Spacer()
                Button(action: { runner.runAll() }) {
                    HStack(spacing: 6) {
                        if runner.isRunning {
                            ProgressView().scaleEffect(0.7).frame(width: 14, height: 14)
                        } else {
                            Image(systemName: "play.fill")
                        }
                        Text(runner.isRunning ? "测试中..." : "运行全部")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(runner.isRunning)
            }
            .padding()

            Divider()

            if runner.results.isEmpty {
                Spacer()
                Text("点击「运行全部」开始测试")
                    .foregroundColor(.secondary)
                Spacer()
            } else {
                List(runner.results) { r in
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: r.passed ? "checkmark.circle.fill" : "xmark.circle.fill")
                            .foregroundColor(r.passed ? .green : .red)
                            .font(.title3)
                        VStack(alignment: .leading, spacing: 3) {
                            Text(r.name).font(.subheadline).fontWeight(.medium)
                            Text(r.detail).font(.caption).foregroundColor(.secondary)
                        }
                        Spacer()
                        Text(r.passed ? "通过" : "失败")
                            .font(.caption2).fontWeight(.semibold)
                            .foregroundColor(r.passed ? .green : .red)
                            .padding(.horizontal, 7).padding(.vertical, 3)
                            .background(RoundedRectangle(cornerRadius: 4)
                                .fill(r.passed ? Color.green.opacity(0.12) : Color.red.opacity(0.12)))
                    }
                    .padding(.vertical, 3)
                }
            }
        }
    }

    private var allPassed: Bool { runner.results.allSatisfy { $0.passed } }
}

// MARK: - Tab 2: 音视频采集

// 用于将 NSView 嵌入 SwiftUI
struct VideoPreviewWrapper: NSViewRepresentable {
    let videoView: RTCMTLNSVideoView

    func makeNSView(context: Context) -> RTCMTLNSVideoView { videoView }
    func updateNSView(_ nsView: RTCMTLNSVideoView, context: Context) {}
}

class CaptureManager: NSObject, ObservableObject {
    @Published var isVideoRunning = false
    @Published var isAudioRunning = false
    @Published var statusLog: [String] = []
    @Published var videoSize: String = "-"

    let videoView = RTCMTLNSVideoView()

    private var factory: RTCPeerConnectionFactory?
    private var videoCapturer: RTCCameraVideoCapturer?
    private var videoSource: RTCVideoSource?
    private var videoTrack: RTCVideoTrack?
    private var audioSource: RTCAudioSource?
    private var audioTrack: RTCAudioTrack?

    // 音频电平监测
    private var audioLevelTimer: Timer?
    @Published var audioLevel: Float = 0.0

    override init() {
        super.init()
        setupFactory()
    }

    private func setupFactory() {
        let encoderFactory = RTCDefaultVideoEncoderFactory()
        let decoderFactory = RTCDefaultVideoDecoderFactory()
        factory = RTCPeerConnectionFactory(encoderFactory: encoderFactory,
                                           decoderFactory: decoderFactory)
        log("✅ RTCPeerConnectionFactory 初始化完成")
    }

    // MARK: - 视频采集

    func startVideo() {
        guard let factory else { log("❌ Factory 未初始化"); return }

        let devices = RTCCameraVideoCapturer.captureDevices()
        guard let device = devices.first else {
            log("❌ 未找到摄像头设备")
            return
        }

        // 选择最佳格式（最接近 1280x720）
        let formats = RTCCameraVideoCapturer.supportedFormats(for: device)
        let targetWidth: Int32 = 1280
        let bestFormat = formats.min(by: { a, b in
            let wa = CMVideoFormatDescriptionGetDimensions(a.formatDescription).width
            let wb = CMVideoFormatDescriptionGetDimensions(b.formatDescription).width
            return abs(wa - targetWidth) < abs(wb - targetWidth)
        })

        guard let format = bestFormat else {
            log("❌ 未找到合适的视频格式")
            return
        }

        let dims = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
        let fps = format.videoSupportedFrameRateRanges.first.map { Int($0.maxFrameRate) } ?? 30

        // 创建 VideoSource 和 Track
        videoSource = factory.videoSource()
        videoTrack = factory.videoTrack(with: videoSource!, trackId: "video0")
        videoTrack?.isEnabled = true

        // 将 videoView 作为渲染器
        videoTrack?.add(videoView)

        // 启动采集
        videoCapturer = RTCCameraVideoCapturer(delegate: videoSource!)
        videoCapturer?.startCapture(with: device, format: format, fps: fps) { [weak self] error in
            DispatchQueue.main.async {
                if let error {
                    self?.log("❌ 视频采集启动失败: \(error.localizedDescription)")
                } else {
                    self?.isVideoRunning = true
                    self?.videoSize = "\(dims.width) × \(dims.height) @ \(fps)fps"
                    self?.log("✅ 视频采集启动 — \(device.localizedName) \(dims.width)×\(dims.height) @\(fps)fps")
                }
            }
        }
    }

    func stopVideo() {
        videoCapturer?.stopCapture { [weak self] in
            DispatchQueue.main.async {
                self?.videoTrack?.remove(self!.videoView)
                self?.videoCapturer = nil
                self?.videoTrack = nil
                self?.videoSource = nil
                self?.isVideoRunning = false
                self?.videoSize = "-"
                self?.log("⏹ 视频采集已停止")
            }
        }
    }

    // MARK: - 音频采集

    func startAudio() {
        guard let factory else { log("❌ Factory 未初始化"); return }

        let constraints = RTCMediaConstraints(
            mandatoryConstraints: nil,
            optionalConstraints: [
                "googEchoCancellation": kRTCMediaConstraintsValueTrue,
                "googNoiseSuppression": kRTCMediaConstraintsValueTrue,
                "googAutoGainControl":  kRTCMediaConstraintsValueTrue,
            ]
        )
        audioSource = factory.audioSource(with: constraints)
        audioTrack = factory.audioTrack(with: audioSource!, trackId: "audio0")
        audioTrack?.isEnabled = true

        isAudioRunning = true
        log("✅ 音频采集启动 — trackId=audio0，回声消除+降噪已开启")

        // 用 AVAudioEngine 监测麦克风电平
        startAudioLevelMonitor()
    }

    func stopAudio() {
        stopAudioLevelMonitor()
        audioTrack?.isEnabled = false
        audioTrack = nil
        audioSource = nil
        isAudioRunning = false
        audioLevel = 0
        log("⏹ 音频采集已停止")
    }

    // MARK: - 音频电平监测（AVAudioEngine）

    private var audioEngine: AVAudioEngine?

    private func startAudioLevelMonitor() {
        let engine = AVAudioEngine()
        let inputNode = engine.inputNode
        let format = inputNode.outputFormat(forBus: 0)

        inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            guard let channelData = buffer.floatChannelData?[0] else { return }
            let frameCount = Int(buffer.frameLength)
            var sum: Float = 0
            for i in 0..<frameCount { sum += channelData[i] * channelData[i] }
            let rms = sqrt(sum / Float(frameCount))
            let db = 20 * log10(max(rms, 1e-7))
            // 映射 -60dB ~ 0dB 到 0.0 ~ 1.0
            let level = max(0, min(1, (db + 60) / 60))
            DispatchQueue.main.async { self?.audioLevel = level }
        }

        do {
            try engine.start()
            audioEngine = engine
        } catch {
            log("⚠️ 音频电平监测启动失败: \(error.localizedDescription)")
        }
    }

    private func stopAudioLevelMonitor() {
        audioEngine?.inputNode.removeTap(onBus: 0)
        audioEngine?.stop()
        audioEngine = nil
    }

    // MARK: - 日志

    private func log(_ msg: String) {
        DispatchQueue.main.async {
            self.statusLog.insert(msg, at: 0)
            if self.statusLog.count > 20 { self.statusLog.removeLast() }
        }
    }
}

struct CaptureView: View {
    @StateObject private var manager = CaptureManager()

    var body: some View {
        HStack(spacing: 0) {
            // 左侧：视频预览
            VStack(spacing: 0) {
                ZStack {
                    Color.black
                    if manager.isVideoRunning {
                        VideoPreviewWrapper(videoView: manager.videoView)
                    } else {
                        VStack(spacing: 8) {
                            Image(systemName: "camera.slash")
                                .font(.system(size: 40))
                                .foregroundColor(.gray)
                            Text("摄像头未启动")
                                .foregroundColor(.gray)
                                .font(.caption)
                        }
                    }
                }
                .frame(maxWidth: .infinity)
                .aspectRatio(16/9, contentMode: .fit)

                // 视频信息栏
                HStack {
                    Label(manager.videoSize, systemImage: "video")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Spacer()
                    Circle()
                        .fill(manager.isVideoRunning ? Color.green : Color.gray)
                        .frame(width: 8, height: 8)
                    Text(manager.isVideoRunning ? "采集中" : "已停止")
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(Color(NSColor.windowBackgroundColor))
            }

            Divider()

            // 右侧：控制面板
            VStack(alignment: .leading, spacing: 16) {
                Text("采集控制").font(.headline)

                // 视频控制
                GroupBox {
                    VStack(alignment: .leading, spacing: 10) {
                        Label("视频采集", systemImage: "camera.fill")
                            .font(.subheadline).fontWeight(.medium)
                        HStack {
                            Button(action: { manager.startVideo() }) {
                                Label("启动", systemImage: "play.fill")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent)
                            .disabled(manager.isVideoRunning)

                            Button(action: { manager.stopVideo() }) {
                                Label("停止", systemImage: "stop.fill")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.bordered)
                            .disabled(!manager.isVideoRunning)
                        }
                    }
                    .padding(4)
                }

                // 音频控制
                GroupBox {
                    VStack(alignment: .leading, spacing: 10) {
                        Label("音频采集", systemImage: "mic.fill")
                            .font(.subheadline).fontWeight(.medium)
                        HStack {
                            Button(action: { manager.startAudio() }) {
                                Label("启动", systemImage: "play.fill")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.borderedProminent)
                            .tint(.orange)
                            .disabled(manager.isAudioRunning)

                            Button(action: { manager.stopAudio() }) {
                                Label("停止", systemImage: "stop.fill")
                                    .frame(maxWidth: .infinity)
                            }
                            .buttonStyle(.bordered)
                            .disabled(!manager.isAudioRunning)
                        }

                        // 音频电平
                        VStack(alignment: .leading, spacing: 4) {
                            Text("麦克风电平").font(.caption).foregroundColor(.secondary)
                            GeometryReader { geo in
                                ZStack(alignment: .leading) {
                                    RoundedRectangle(cornerRadius: 3)
                                        .fill(Color.gray.opacity(0.2))
                                    RoundedRectangle(cornerRadius: 3)
                                        .fill(levelColor)
                                        .frame(width: geo.size.width * CGFloat(manager.audioLevel))
                                        .animation(.linear(duration: 0.05), value: manager.audioLevel)
                                }
                            }
                            .frame(height: 10)
                        }
                    }
                    .padding(4)
                }

                Divider()

                // 日志
                VStack(alignment: .leading, spacing: 6) {
                    Text("运行日志").font(.caption).foregroundColor(.secondary)
                    ScrollView {
                        VStack(alignment: .leading, spacing: 3) {
                            ForEach(manager.statusLog, id: \.self) { line in
                                Text(line)
                                    .font(.system(size: 11, design: .monospaced))
                                    .foregroundColor(.primary)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                            }
                        }
                        .padding(6)
                    }
                    .frame(maxHeight: .infinity)
                    .background(Color(NSColor.textBackgroundColor))
                    .cornerRadius(6)
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color.gray.opacity(0.3)))
                }

                Spacer()
            }
            .padding()
            .frame(width: 260)
        }
    }

    private var levelColor: Color {
        switch manager.audioLevel {
        case 0..<0.5:  return .green
        case 0.5..<0.8: return .yellow
        default:        return .red
        }
    }
}

#Preview {
    ContentView()
}
