# webrtc-web

Web 端与 webrtc-demo Mac 端互通：信令 + 音频 + DataChannel 消息。

## 运行

```bash
cd webrtc-web
npm install
npm start
```

浏览器打开 **http://localhost:8080**：

1. 输入房间号（与 Mac 端一致，默认 `demo`），点击「加入房间」
2. 点击「发起连接（创建 Offer）」：本端作为 Offer，等待 Mac 端 Answer；或等 Mac 端先发 Offer，本页会自动回复 Answer
3. 连接成功后即可收发消息、听/说语音；页面有本地/远端音频电平条

## Mac 端对接

Mac 端需连接**同一信令**才能与 Web 互通：

- **WebSocket 地址**：`ws://localhost:8080/ws`
- **协议**：连接后发 `{ "type": "join", "roomId": "demo" }` 加入房间；之后与同房间对端通过 `{ "type": "signal", "payload": { type, sdp? | candidate? } }` 交换 SDP/ICE
- Mac 端可先发 Offer（并创建 DataChannel），或等 Web 发 Offer 后回 Answer；音频轨与 DataChannel 消息格式与 Web 一致即可互通

## 技术说明

- **信令**：同一端口 `/ws` WebSocket，按 `roomId` 转发 signal
- **音频**：仅音频（无视频），STUN `stun.l.google.com:19302`
- **消息**：DataChannel 名 `msg`，ordered，文本 UTF-8
