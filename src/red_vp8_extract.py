#!/usr/bin/env python3
"""
从 WebRTC pcapng 中提取 RED(PT=123) 封装的 VP8(内层常见 PT=96)，重组为 IVF，再用 ffmpeg 转 MP4/WebM。

SDP 示例: a=rtpmap:123 red/90000 — 外层 RED，主编码常为 VP8。

依赖: scapy pylibsrtp ffmpeg；与 webrtc_h264_extractor 共用密钥格式。
"""

from __future__ import annotations

import argparse
import struct
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 同目录导入
_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))  # noqa: ensure same-directory imports work

from scapy.all import UDP, rdpcap  # noqa: E402

from webrtc_h264_extractor import (  # noqa: E402
    HAS_PYLIBSRTP,
    RTPHeader,
    SRTPDecryptor,
    SRTPKey,
)


def unwrap_red_primary(rtp_payload: bytes) -> Tuple[int, bytes]:
    """
    RFC 2198: F=1 表示后面还有头部（冗余块，4 字节头）；F=0 为最后一头（主编码，仅 1 字节 PT）。
    数据区顺序：与头部顺序一致，先各冗余块数据，最后是主数据。
    """
    if not rtp_payload:
        return (-1, b"")

    pos = 0
    redundant_lens: List[int] = []

    while pos < len(rtp_payload):
        b0 = rtp_payload[pos]
        if b0 & 0x80:
            # 冗余块头 4 字节
            if pos + 4 > len(rtp_payload):
                return (-1, rtp_payload)
            # 14-bit TS offset, 10-bit length (RFC 2198)
            b1, b2, b3 = rtp_payload[pos + 1], rtp_payload[pos + 2], rtp_payload[pos + 3]
            ts_off = (b1 << 6) | (b2 >> 2)
            block_len = ((b2 & 0x03) << 8) | b3
            redundant_lens.append(block_len)
            pos += 4
            _ = ts_off  # 提取即可，重组主轨不需要
        else:
            primary_pt = b0 & 0x7F
            pos += 1
            break

    data_pos = pos
    for blen in redundant_lens:
        data_pos += blen
    if data_pos > len(rtp_payload):
        return (-1, rtp_payload)

    return primary_pt, rtp_payload[data_pos:]


def vp8_descriptor_length(buf: bytes) -> int:
    """RFC 7741：返回 VP8 描述符占用字节数（不含压缩 VP8 数据）。"""
    if not buf:
        return 0
    pos = 1
    b0 = buf[0]
    if b0 & 0x80:  # X
        if len(buf) < 2:
            return len(buf)
        ext = buf[1]
        pos = 2
        if ext & 0x80:  # I — PictureID
            if pos >= len(buf):
                return pos
            pid0 = buf[pos]
            pos += 1
            if pid0 & 0x80:
                if pos < len(buf):
                    pos += 1
        if ext & 0x40:  # L
            pos += 1
        if (ext & 0x20) or (ext & 0x10):  # T or K
            pos += 1
    return min(pos, len(buf))


def strip_vp8_descriptor(inner_payload: bytes) -> Optional[Tuple[bytes, bool, int]]:
    """
    返回 (压缩 VP8 片段, S 位, PID)。
    S=1 且 PID=0 时，片段含 RFC7741 的 VP8 payload header（3 或 10 字节）。
    """
    if len(inner_payload) < 1:
        return None
    dlen = vp8_descriptor_length(inner_payload)
    if dlen > len(inner_payload):
        return None
    desc = inner_payload[:dlen]
    b0 = desc[0]
    s = bool(b0 & 0x10)  # bit 4
    pid = b0 & 0x07  # 低 3 位 Part ID
    vp8_chunk = inner_payload[dlen:]
    return vp8_chunk, s, pid


def guess_vp8_dimensions(bitstream: bytes) -> Tuple[int, int]:
    """从关键帧中找 0x9d01002a 同步字，读取 14-bit 宽高。"""
    sig = b"\x9d\x01\x2a"
    i = 0
    while True:
        j = bitstream.find(sig, i)
        if j < 0 or j + 10 > len(bitstream):
            return 640, 480
        # 同步字后 4 字节: 2 字节宽、2 字节高（各 14 位有效，小端）
        w = struct.unpack("<H", bitstream[j + 3 : j + 5])[0] & 0x3FFF
        h = struct.unpack("<H", bitstream[j + 5 : j + 7])[0] & 0x3FFF
        if w > 0 and h > 0 and w <= 8192 and h <= 8192:
            return w, h
        i = j + 1


def write_ivf(frames: List[bytes], path: Path, fps_num: int = 30, fps_den: int = 1) -> Tuple[int, int]:
    w, h = 640, 480
    for fr in frames:
        if len(fr) > 20:
            w, h = guess_vp8_dimensions(fr)
            break

    with open(path, "wb") as f:
        # DKIF header（timebase 用 fps_den / fps_num，时间戳每帧 +1）
        f.write(b"DKIF")
        f.write(struct.pack("<H", 0))  # version
        f.write(struct.pack("<H", 32))  # header size
        f.write(b"VP80")
        f.write(struct.pack("<H", w))
        f.write(struct.pack("<H", h))
        f.write(struct.pack("<I", fps_den))
        f.write(struct.pack("<I", fps_num))
        f.write(struct.pack("<I", len(frames)))
        f.write(struct.pack("<I", 0))
        for fi, fr in enumerate(frames):
            f.write(struct.pack("<I", len(fr)))
            f.write(struct.pack("<Q", fi))
            f.write(fr)
    return w, h


def extract_red_vp8_frames(
    pcap_path: Path,
    keylog_path: Path,
    target_ssrc: int,
    outer_pt: int = 123,
) -> List[bytes]:
    if not HAS_PYLIBSRTP:
        raise RuntimeError("需要 pylibsrtp")

    keys = SRTPKey.parse_keylog(str(keylog_path))
    decryptors: List[SRTPDecryptor] = []
    if keys.get("client"):
        decryptors.append(SRTPDecryptor(keys["client"]))
    if keys.get("server"):
        decryptors.append(SRTPDecryptor(keys["server"]))
    if not decryptors:
        raise ValueError("密钥文件中无有效 SRTP 密钥")

    packets = rdpcap(str(pcap_path))
    # (timestamp, seq) -> list of vp8 fragments in arrival order; we'll sort by seq
    bucket: Dict[Tuple[int, int], List[Tuple[int, bytes]]] = defaultdict(list)

    for pkt in packets:
        if not pkt.haslayer(UDP):
            continue
        udp_payload = bytes(pkt[UDP].payload)
        for dec in decryptors:
            plain = dec.decrypt(udp_payload)
            if plain:
                udp_payload = plain
                break
        else:
            continue

        rtp = RTPHeader.parse(udp_payload)
        if not rtp or rtp.ssrc != target_ssrc:
            continue
        if rtp.payload_type != outer_pt:
            continue

        pl = udp_payload[rtp.header_len :]
        if rtp.padding and pl:
            pad = pl[-1]
            if pad > 0 and len(pl) > pad:
                pl = pl[:-pad]

        inner_pt, inner = unwrap_red_primary(pl)
        if inner_pt < 0 or inner_pt != 96:
            continue

        stripped = strip_vp8_descriptor(inner)
        if not stripped:
            continue
        chunk, _s, _pid = stripped
        if not chunk:
            continue

        bucket[(rtp.timestamp, inner_pt)].append((rtp.sequence_number, chunk))

    frames: List[bytes] = []
    for (_ts, _pt), parts in sorted(bucket.items(), key=lambda x: x[0][0]):
        parts.sort(key=lambda x: x[0])
        frames.append(b"".join(p[1] for p in parts))

    return frames


def ffmpeg_ivf_to_mp4(ivf: Path, mp4: Path, fps: int = 30) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-r",
        str(fps),
        "-i",
        str(ivf),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(mp4),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:] if r.stderr else "ffmpeg failed")


def main() -> None:
    ap = argparse.ArgumentParser(description="RED(123)+VP8 提取为 IVF/MP4")
    ap.add_argument("pcapng", type=Path)
    ap.add_argument("-k", "--keylog", type=Path, required=True)
    ap.add_argument("-s", "--ssrc", type=lambda x: int(x, 0), required=True)
    ap.add_argument("--outer-pt", type=int, default=123, help="RED 外层 PT，默认 123")
    ap.add_argument("-o", "--output", type=Path, default=None, help="输出 .mp4（默认与 pcap 同名）")
    ap.add_argument("--ivf-only", type=Path, default=None, help="仅写 IVF 到此路径")
    args = ap.parse_args()

    out_mp4 = args.output
    if out_mp4 is None and not args.ivf_only:
        out_mp4 = args.pcapng.with_suffix(".red_vp8.mp4")

    print(f"提取 SSRC=0x{args.ssrc:08X} 外层PT={args.outer_pt} …")
    frames = extract_red_vp8_frames(
        args.pcapng, args.keylog, args.ssrc, outer_pt=args.outer_pt
    )
    print(f"  重组帧数: {len(frames)}")
    if not frames:
        print("未得到任何帧，请检查 SSRC / 密钥 / 外层 PT")
        sys.exit(1)

    if args.ivf_only:
        ivf_path = args.ivf_only
    elif out_mp4 is not None:
        ivf_path = out_mp4.with_suffix(".ivf")
    else:
        ivf_path = args.pcapng.with_suffix(".red_vp8.ivf")
    w, h = write_ivf(frames, ivf_path)
    print(f"  IVF: {ivf_path} ({w}x{h}, {ivf_path.stat().st_size} bytes)")

    if args.ivf_only:
        return

    assert out_mp4 is not None
    ffmpeg_ivf_to_mp4(ivf_path, out_mp4)
    print(f"  MP4: {out_mp4} ({out_mp4.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
