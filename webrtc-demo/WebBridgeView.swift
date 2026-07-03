//
//  WebBridgeView.swift
//  webrtc-demo
//
//  与 webrtc-web 互通：信令(WebSocket) + 音频 + DataChannel 消息
//

import SwiftUI
import Combine
import AppKit
import AVFoundation

// MARK: - 消息模型（与 Web 端一致：msg + ack 已送达）

struct ChatMessage: Identifiable {
    let id: UUID
    let msgId: String?
    let text: String
    let isRemote: Bool
    let delivered: Bool
}

// MARK: - WebBridgeManager：信令 + WebRTC

class WebBridgeManager: NSObject, ObservableObject {
    @Published var wsStatus: String = "未连接"
    @Published var currentRoomId: String? = nil
    @Published var connectionState: String = "—"
    @Published var messages: [ChatMessage] = []
    @Published var messageDraft: String = ""
    @Published var logContent: String = ""

    private var wsSession: URLSession?
    private var wsTask: URLSessionWebSocketTask?
    private var pendingJoinRoomId: String?
    private var pc: RTCPeerConnection?
    private var factory: RTCPeerConnectionFactory?
    private var audioTrack: RTCAudioTrack?
    private var audioSource: RTCAudioSource?
    private var videoTrack: RTCVideoTrack?
    private var videoSource: RTCVideoSource?
    private var videoCapturer: RTCCameraVideoCapturer?
    private var dataChannel: RTCDataChannel?
    private let config: RTCConfiguration
    private let encoderFactory = RTCDefaultVideoEncoderFactory()
    private let decoderFactory = RTCDefaultVideoDecoderFactory()

    override init() {
        config = RTCConfiguration()
        config.iceServers = [RTCIceServer(urlStrings: ["stun:stun.l.google.com:19302"])]
        super.init()
        factory = RTCPeerConnectionFactory(encoderFactory: encoderFactory, decoderFactory: decoderFactory)
    }

    // MARK: - WebSocket

    private var wsBaseURL: String { "ws://localhost:8080/ws" }

    func joinRoom(roomId: String) {
        guard let url = URL(string: wsBaseURL) else {
            log("❌ 无效 WebSocket 地址")
            return
        }
        pendingJoinRoomId = roomId
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 10
        wsSession = URLSession(configuration: config, delegate: self, delegateQueue: nil)
        wsTask = wsSession?.webSocketTask(with: url)
        wsTask?.resume()
        wsStatus = "连接中…"
        // 不再在此处打「正在连接」日志，避免加入成功后仍看到该行造成误解；连接结果在 didOpenWithProtocol / didCompleteWithError 中打
    }

    func leaveRoom() {
        let room = currentRoomId ?? "demo"
        pendingJoinRoomId = nil
        wsTask?.cancel(with: .goingAway, reason: nil)
        wsTask = nil
        wsSession?.invalidateAndCancel()
        wsSession = nil
        currentRoomId = nil
        wsStatus = "已离开房间 \(room)"
        connectionState = "—"
        closePeerConnection()
        log("已离开房间 \(room)")
    }

    private func sendWS(_ obj: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: obj),
              let str = String(data: data, encoding: .utf8) else { return }
        wsTask?.send(.string(str)) { [weak self] err in
            if let err { DispatchQueue.main.async { self?.log("WS 发送错误: \(err.localizedDescription)") } }
        }
    }

    private func receiveWSMessage() {
        wsTask?.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let msg):
                switch msg {
                case .string(let s):
                    self.handleWSMessage(s)
                default:
                    break
                }
            case .failure:
                break
            }
            if self.wsTask != nil { self.receiveWSMessage() }
        }
    }

    private func handleWSMessage(_ s: String) {
        guard let data = s.data(using: .utf8),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = json["type"] as? String else { return }

        DispatchQueue.main.async {
            if type == "joined" {
                self.currentRoomId = json["roomId"] as? String
                self.wsStatus = "已加入房间: \(self.currentRoomId ?? "")"
                self.logWithSeparator("✅ \(self.wsStatus)")
            } else if type == "peers" {
                let count = (json["count"] as? Int) ?? 0
                self.log("当前房间人数: \(count)")
            } else if type == "signal", let payload = json["payload"] as? [String: Any] {
                let from = (json["from"] as? String) ?? "?"
                let sigType = (payload["type"] as? String) ?? "?"
                self.log("收到 signal: \(sigType) (来自 \(from))")
                self.handleSignal(payload)
            }
        }
    }

    private func sendSignal(_ payload: [String: Any]) {
        sendWS(["type": "signal", "payload": payload])
    }

    // MARK: - WebRTC

    private func createPeerConnection() -> RTCPeerConnection? {
        guard let factory else { return nil }
        let constraints = RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: nil)
        let pc = factory.peerConnection(with: config, constraints: constraints, delegate: self)
        self.pc = pc
        return pc
    }

    private func closePeerConnection() {
        dataChannel?.close()
        dataChannel = nil
        pc?.close()
        pc = nil
        videoCapturer?.stopCapture {
            // no-op
        }
        videoCapturer = nil
        videoTrack = nil
        videoSource = nil
        audioTrack = nil
        audioSource = nil
    }

    private func ensureLocalMediaAdded(to pc: RTCPeerConnection) {
        guard let factory else { return }

        if audioTrack == nil {
            let constraints = RTCMediaConstraints(
                mandatoryConstraints: nil,
                optionalConstraints: [
                    "googEchoCancellation": kRTCMediaConstraintsValueTrue,
                    "googNoiseSuppression": kRTCMediaConstraintsValueTrue,
                ]
            )
            audioSource = factory.audioSource(with: constraints)
            audioTrack = factory.audioTrack(with: audioSource!, trackId: "audio0")
            audioTrack?.isEnabled = true
            if let audioTrack {
                pc.add(audioTrack, streamIds: ["stream1"])
            }
        }

        if videoTrack == nil {
            let devices = RTCCameraVideoCapturer.captureDevices()
            guard let device = devices.first else {
                log("未找到可用摄像头，仅发送音频")
                return
            }
            let formats = RTCCameraVideoCapturer.supportedFormats(for: device)
            let targetWidth: Int32 = 640
            guard let format = formats.min(by: { a, b in
                let wa = CMVideoFormatDescriptionGetDimensions(a.formatDescription).width
                let wb = CMVideoFormatDescriptionGetDimensions(b.formatDescription).width
                return abs(wa - targetWidth) < abs(wb - targetWidth)
            }) else {
                log("未找到可用视频格式，仅发送音频")
                return
            }
            let fps = min(
                24,
                format.videoSupportedFrameRateRanges.first.map { Int($0.maxFrameRate) } ?? 24
            )
            videoSource = factory.videoSource()
            videoTrack = factory.videoTrack(with: videoSource!, trackId: "video0")
            videoTrack?.isEnabled = true
            if let videoTrack {
                pc.add(videoTrack, streamIds: ["stream1"])
            }
            videoCapturer = RTCCameraVideoCapturer(delegate: videoSource!)
            videoCapturer?.startCapture(with: device, format: format, fps: fps) { [weak self] error in
                DispatchQueue.main.async {
                    if let error {
                        self?.log("视频采集启动失败：\(error.localizedDescription)")
                    } else {
                        let dims = CMVideoFormatDescriptionGetDimensions(format.formatDescription)
                        self?.log("视频采集启动：\(device.localizedName) \(dims.width)x\(dims.height)@\(fps)fps")
                    }
                }
            }
        }
    }

    func startCallAsOfferer(roomId: String) {
        if pc != nil { return }
        guard let pc = createPeerConnection() else { return }

        ensureLocalMediaAdded(to: pc)

        let dcConfig = RTCDataChannelConfiguration()
        dcConfig.isOrdered = true
        dataChannel = pc.dataChannel(forLabel: "msg", configuration: dcConfig)
        dataChannel?.delegate = self

        pc.offer(for: RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: nil)) { [weak self] sdp, err in
            guard let self, let sdp else {
                DispatchQueue.main.async { self?.log("创建 Offer 失败: \(err?.localizedDescription ?? "")") }
                return
            }
            pc.setLocalDescription(sdp) { [weak self] err in
                guard err == nil else { return }
                let payload: [String: Any] = [
                    "type": "offer",
                    "sdp": sdp.sdp
                ]
                self?.sendSignal(payload)
                DispatchQueue.main.async {
                    self?.connectionState = "已发送 Offer"
                    self?.log("已发送 Offer")
                }
            }
        }
    }

    private func handleSignal(_ payload: [String: Any]) {
        guard let type = payload["type"] as? String else { return }

        if type == "offer", let sdpStr = payload["sdp"] as? String {
            handleRemoteOffer(sdp: sdpStr)
        } else if type == "answer", let sdpStr = payload["sdp"] as? String {
            handleRemoteAnswer(sdp: sdpStr)
        } else if type == "ice", let candidateDict = payload["candidate"] as? [String: Any] {
            handleRemoteIce(candidateDict: candidateDict)
        }
    }

    private func handleRemoteOffer(sdp: String) {
        if pc == nil {
            log("收到远端 Offer，正在创建连接并回复 Answer…")
            guard createPeerConnection() != nil else { return }
            if let pc {
                ensureLocalMediaAdded(to: pc)
            }
        } else {
            log("已有连接，忽略新 Offer（建议房间内仅 2 端：1 Mac + 1 Web）")
            return
        }

        let normalizedSdp = sdp.replacingOccurrences(of: "\r\n", with: "\n").replacingOccurrences(of: "\n", with: "\r\n")
        let offer = RTCSessionDescription(type: .offer, sdp: normalizedSdp)
        pc?.setRemoteDescription(offer) { [weak self] err in
            guard let self else { return }
            if let err = err as NSError? {
                DispatchQueue.main.async {
                    self.log("setRemoteDescription(offer) 失败: \(err.localizedDescription)")
                    if let reason = err.localizedFailureReason, !reason.isEmpty { self.log("  原因: \(reason)") }
                }
                return
            }
            self.pc?.answer(for: RTCMediaConstraints(mandatoryConstraints: nil, optionalConstraints: nil)) { [weak self] sdp, err in
                guard let self, let sdp else { return }
                self.pc?.setLocalDescription(sdp) { [weak self] err in
                    guard let self, err == nil else { return }
                    self.sendSignal(["type": "answer", "sdp": sdp.sdp])
                    DispatchQueue.main.async {
                        self.connectionState = "已回复 Answer"
                        self.logWithSeparator("已回复 Answer")
                    }
                }
            }
        }
    }

    private func handleRemoteAnswer(sdp: String) {
        guard let pc = pc else { return }
        guard pc.signalingState == .haveLocalOffer else {
            log("忽略 answer：当前状态 \(pc.signalingState.rawValue)，非 have-local-offer")
            return
        }
        let normalizedSdp = sdp.replacingOccurrences(of: "\r\n", with: "\n").replacingOccurrences(of: "\n", with: "\r\n")
        let answer = RTCSessionDescription(type: .answer, sdp: normalizedSdp)
        pc.setRemoteDescription(answer) { [weak self] err in
            DispatchQueue.main.async {
                if let e = err as NSError? {
                    self?.log("setRemoteDescription(answer) 失败: \(e.localizedDescription)")
                } else {
                    self?.connectionState = "已连接"
                    self?.logWithSeparator("已连接")
                }
            }
        }
    }

    private func handleRemoteIce(candidateDict: [String: Any]) {
        guard let candidate = RTCIceCandidate(from: candidateDict) else { return }
        pc?.add(candidate) { _ in }
    }

    private func mimeType(for url: URL) -> String {
        if #available(macOS 11.0, *) {
            if let values = try? url.resourceValues(forKeys: [.contentTypeKey]),
               let type = values.contentType,
               let mime = type.preferredMIMEType {
                return mime
            }
        }
        return "application/octet-stream"
    }

    func sendFile() {
        guard let dc = dataChannel, dc.readyState == .open else {
            log("当前 DataChannel 未连接，无法发送文件")
            return
        }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = false
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url, let self else { return }
            do {
                let data = try Data(contentsOf: url)
                let attrs = try FileManager.default.attributesOfItem(atPath: url.path)
                let size = (attrs[.size] as? NSNumber)?.intValue ?? data.count
                let name = url.lastPathComponent
                let msgId = "f_" + String(UInt64(Date().timeIntervalSince1970 * 1000)) + "_" + String(UUID().uuidString.prefix(8))
                let base64 = data.base64EncodedString()
                let label = "[文件] \(name) (\(size) 字节)"
                DispatchQueue.main.async {
                    self.messages.append(ChatMessage(id: UUID(), msgId: msgId, text: label, isRemote: false, delivered: false))
                }
                let payload: [String: Any] = [
                    "type": "file",
                    "id": msgId,
                    "name": name,
                    "size": size,
                    "mime": self.mimeType(for: url),
                    "data": base64
                ]
                guard let json = try? JSONSerialization.data(withJSONObject: payload) else { return }
                dc.sendData(RTCDataBuffer(data: json, isBinary: false))
            } catch {
//                self?.log("发送文件失败: \(error.localizedDescription)")
            }
        }
    }

    func sendMessage() {
        let text = messageDraft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, let dc = dataChannel, dc.readyState == .open else { return }
        let msgId = "m_" + String(UInt64(Date().timeIntervalSince1970 * 1000)) + "_" + String(UUID().uuidString.prefix(8))
        let msg = ChatMessage(id: UUID(), msgId: msgId, text: text, isRemote: false, delivered: false)
        DispatchQueue.main.async { self.messages.append(msg); self.messageDraft = "" }
        let payload: [String: Any] = ["type": "msg", "id": msgId, "text": text]
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else { return }
        dc.sendData(RTCDataBuffer(data: data, isBinary: false))
    }

    private func sendAck(msgId: String) {
        guard let dc = dataChannel, dc.readyState == .open else { return }
        let payload: [String: Any] = ["type": "ack", "id": msgId]
        guard let data = try? JSONSerialization.data(withJSONObject: payload) else { return }
        dc.sendData(RTCDataBuffer(data: data, isBinary: false))
    }

    private func setMessageDelivered(msgId: String) {
        DispatchQueue.main.async {
            self.messages = self.messages.map { m in
                m.msgId == msgId ? ChatMessage(id: m.id, msgId: m.msgId, text: m.text, isRemote: m.isRemote, delivered: true) : m
            }
        }
    }

    private static let logTimeFormatter: DateFormatter = {
        let f = DateFormatter()
        f.dateFormat = "HH:mm:ss"
        return f
    }()

    private func log(_ msg: String) {
        DispatchQueue.main.async {
            let timeStr = Self.logTimeFormatter.string(from: Date())
            let line = "[\(timeStr)] \(msg)"
            self.logContent += line + "\n"
            let maxLen = 20_000
            if self.logContent.count > maxLen {
                self.logContent = String(self.logContent.suffix(maxLen))
                if let firstNewline = self.logContent.firstIndex(of: "\n") {
                    self.logContent = String(self.logContent[firstNewline...].dropFirst())
                }
            }
        }
    }

    /// 在关键节点后插入空行，便于阅读
    private func logWithSeparator(_ msg: String) {
        log(msg)
        DispatchQueue.main.async {
            if !self.logContent.isEmpty && !self.logContent.hasSuffix("\n\n") {
                self.logContent += "\n"
            }
        }
    }
}

// MARK: - URLSessionWebSocketDelegate（连接成功后再发 join）

extension WebBridgeManager: URLSessionWebSocketDelegate, URLSessionDelegate {
    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        DispatchQueue.main.async { [weak self] in
            guard let self, let roomId = self.pendingJoinRoomId else { return }
            self.log("WebSocket 已连接 \(self.wsBaseURL)，已发送 join(roomId=\(roomId))")
            let join: [String: Any] = [
                "type": "join",
                "roomId": roomId,
                "peerId": "mac_" + String(UInt64(Date().timeIntervalSince1970 * 1000))
            ]
            self.sendWS(join)
            self.receiveWSMessage()
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        DispatchQueue.main.async { [weak self] in
            self?.log("WebSocket 已关闭: \(closeCode.rawValue)")
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: Error?) {
        if let error {
            DispatchQueue.main.async { [weak self] in
                self?.log("WS 连接失败: \(error.localizedDescription)")
                self?.wsStatus = "连接失败（请先启动 webrtc-web: npm start）"
            }
        }
    }
}

// MARK: - RTCPeerConnectionDelegate

extension WebBridgeManager: RTCPeerConnectionDelegate {
    func peerConnection(_ peerConnection: RTCPeerConnection, didChange stateChanged: RTCSignalingState) {}
    func peerConnection(_ peerConnection: RTCPeerConnection, didAdd stream: RTCMediaStream) {
        let a = stream.audioTracks.count
        let v = stream.videoTracks.count
        DispatchQueue.main.async {
            self.log("收到远端媒体流：audioTracks=\(a), videoTracks=\(v)")
        }
    }
    func peerConnection(_ peerConnection: RTCPeerConnection, didRemove stream: RTCMediaStream) {}
    func peerConnectionShouldNegotiate(_ peerConnection: RTCPeerConnection) {}
    func peerConnection(_ peerConnection: RTCPeerConnection, didChange newState: RTCIceConnectionState) {
        DispatchQueue.main.async {
            self.connectionState = "\(newState.rawValue)"
        }
    }
    func peerConnection(_ peerConnection: RTCPeerConnection, didChange newState: RTCIceGatheringState) {}
    func peerConnection(_ peerConnection: RTCPeerConnection, didGenerate candidate: RTCIceCandidate) {
        let dict: [String: Any] = [
            "type": "ice",
            "candidate": [
                "candidate": candidate.sdp,
                "sdpMLineIndex": candidate.sdpMLineIndex,
                "sdpMid": candidate.sdpMid ?? ""
            ]
        ]
        sendSignal(dict)
    }
    func peerConnection(_ peerConnection: RTCPeerConnection, didRemove candidates: [RTCIceCandidate]) {}
    func peerConnection(_ peerConnection: RTCPeerConnection, didOpen dataChannel: RTCDataChannel) {
        DispatchQueue.main.async { [weak self] in
            self?.dataChannel = dataChannel
            self?.dataChannel?.delegate = self
            self?.logWithSeparator("收到对端 DataChannel，label=\(dataChannel.label)")
        }
    }
}

// MARK: - RTCDataChannelDelegate

extension WebBridgeManager: RTCDataChannelDelegate {
    func dataChannelDidChangeState(_ dataChannel: RTCDataChannel) {
        DispatchQueue.main.async { [weak self] in
            let stateStr: String
            switch dataChannel.readyState {
            case .connecting: stateStr = "connecting"
            case .open: stateStr = "open"
            case .closing: stateStr = "closing"
            case .closed: stateStr = "closed"
            @unknown default: stateStr = "\(dataChannel.readyState.rawValue)"
            }
            self?.log("DataChannel 状态: \(stateStr)")
        }
    }

    func dataChannel(_ dataChannel: RTCDataChannel, didReceiveMessageWith buffer: RTCDataBuffer) {
        let byteCount = buffer.data.count
        guard !buffer.isBinary, let str = String(data: buffer.data, encoding: .utf8) else {
            DispatchQueue.main.async {
                self.log("收到 DataChannel 二进制: \(byteCount) 字节（已忽略）")
            }
            return
        }
        DispatchQueue.main.async {
            self.log("收到 DataChannel 消息: \(byteCount) 字节")
            self.log("  → \(str.prefix(60))\(str.count > 60 ? "…" : "")")
            if str.count > 60 { self.log("  → 完整: \(String(str.prefix(200)))\(str.count > 200 ? "…" : "")") }
        }

        if let data = str.data(using: .utf8),
           let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
           let type = obj["type"] as? String {
            if type == "file",
               let msgId = obj["id"] as? String,
               let name = obj["name"] as? String,
               let sizeAny = obj["size"],
               let b64 = obj["data"] as? String {
                let size: Int
                if let n = sizeAny as? NSNumber { size = n.intValue }
                else { size = Int("\(sizeAny)") ?? 0 }
                if let fileData = Data(base64Encoded: b64) {
                    let downloads = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
                    let folder = downloads?.appendingPathComponent("webrtc-demo-files", isDirectory: true)
                    if let folder {
                        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
                        let dest = folder.appendingPathComponent(name)
                        do {
                            try fileData.write(to: dest)
                            DispatchQueue.main.async {
                                let label = "[文件] \(name) (\(size) 字节) 已保存到 \(dest.path)"
                                self.messages.append(ChatMessage(id: UUID(), msgId: nil, text: label, isRemote: true, delivered: false))
                                self.log(label)
                            }
                        } catch {
                            DispatchQueue.main.async {
                                self.log("保存文件失败: \(error.localizedDescription)")
                            }
                        }
                    }
                }
                sendAck(msgId: msgId)
                return
            }
            if type == "msg", let msgId = obj["id"] as? String, let text = obj["text"] as? String {
                DispatchQueue.main.async {
                    self.messages.append(ChatMessage(id: UUID(), msgId: nil, text: text, isRemote: true, delivered: false))
                }
                sendAck(msgId: msgId)
                return
            }
            if type == "ack", let msgId = obj["id"] as? String {
                setMessageDelivered(msgId: msgId)
                return
            }
        }
        DispatchQueue.main.async {
            self.messages.append(ChatMessage(id: UUID(), msgId: nil, text: str, isRemote: true, delivered: false))
        }
    }

}

// MARK: - RTCIceCandidate 从字典构造（Web 端格式）

extension RTCIceCandidate {
    convenience init?(from dict: [String: Any]) {
        guard let cand = dict["candidate"] as? String else { return nil }
        let lineIndex: Int32
        if let n = dict["sdpMLineIndex"] as? NSNumber { lineIndex = n.int32Value }
        else if let i = dict["sdpMLineIndex"] as? Int { lineIndex = Int32(i) }
        else { lineIndex = 0 }
        let mid = dict["sdpMid"] as? String
        self.init(sdp: cand, sdpMLineIndex: lineIndex, sdpMid: mid)
    }
}

// MARK: - View

struct WebBridgeView: View {
    @StateObject private var manager = WebBridgeManager()
    @State private var roomId: String = "demo"

    var body: some View {
        HStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 16) {
                Text("Web 互通").font(.headline)

                GroupBox {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Text("房间号")
                            TextField("demo", text: $roomId)
                                .textFieldStyle(.roundedBorder)
                                .frame(width: 120)
                                .disabled(manager.currentRoomId != nil)
                            if manager.currentRoomId == nil {
                                Button("加入房间") { manager.joinRoom(roomId: roomId.isEmpty ? "demo" : roomId) }
                                    .buttonStyle(.borderedProminent)
                            } else {
                                Button("离开房间") { manager.leaveRoom() }
                                    .buttonStyle(.bordered)
                            }
                        }
                        Text(manager.wsStatus).font(.caption).foregroundColor(.secondary)
                    }
                    .padding(4)
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Button("发起连接（Offer）") {
                                manager.startCallAsOfferer(roomId: roomId.isEmpty ? "demo" : roomId)
                            }
                            .disabled(manager.currentRoomId == nil)
                            Text(manager.connectionState).font(.caption).foregroundColor(.secondary)
                        }
                    }
                    .padding(4)
                }

                GroupBox {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("消息（DataChannel）").font(.subheadline)
                        HStack {
                            TextField("输入消息", text: $manager.messageDraft)
                                .textFieldStyle(.roundedBorder)
                                .onSubmit { manager.sendMessage() }
                            Button("发送", action: { manager.sendMessage() })
                        }
                        HStack {
                            Button("发送文件…") {
                                manager.sendFile()
                            }
                        }
                        ScrollView {
                            VStack(alignment: .leading, spacing: 4) {
                                ForEach(manager.messages) { m in
                                    let line = m.isRemote ? "对方: \(m.text)" : (m.delivered ? "我发送: \(m.text) ✓已送达" : "我发送: \(m.text)")
                                    Text(line)
                                        .font(.caption)
                                        .foregroundColor(m.isRemote ? .green : .primary)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                        }
                        .frame(height: 140)
                    }
                    .padding(4)
                }

                Spacer()
            }
            .padding()
            .frame(width: 320)

            Divider()

            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("日志").font(.headline)
                    Spacer()
                    Button("复制") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(manager.logContent, forType: .string)
                    }
                    .buttonStyle(.bordered)
                    .disabled(manager.logContent.isEmpty)
                }
                ScrollView {
                    Text(manager.logContent)
                        .font(.system(size: 11, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(6)
                }
                .background(Color(nsColor: .textBackgroundColor).opacity(0.5))
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            .padding()
            .frame(maxWidth: .infinity)
        }
    }
}
