//
//  webrtc_demoApp.swift
//  webrtc-demo
//
//  Created by lizhengze on 2026/2/25.
//

import SwiftUI
import Foundation

@main
struct webrtc_demoApp: App {
    init() {
        // Set key log paths as early as possible (before WebRTC is initialized).
        // Wireshark reads DTLS keys from SSLKEYLOGFILE (NSS Key Log Format).
        let keysDir = "/Users/lizhengze/Desktop/demo/webrtc-demo/webrtc-keys"
        let unifiedKeyLogPath = "\(keysDir)/native_combined_keys.log"

        // Ensure output directory exists.
        try? FileManager.default.createDirectory(
            atPath: keysDir,
            withIntermediateDirectories: true
        )

        setenv("SSLKEYLOGFILE", unifiedKeyLogPath, 1)
        // Some builds also honor SSLKEYLOG.
        setenv("SSLKEYLOG", unifiedKeyLogPath, 1)

        // Custom env var consumed by patched pc/dtls_srtp_transport.cc.
        setenv("SRTPKEYLOGFILE", unifiedKeyLogPath, 1)
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}
