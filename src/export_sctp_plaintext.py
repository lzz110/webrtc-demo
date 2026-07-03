#!/usr/bin/env python3
"""
使用 tshark + keylog 从 DTLS 中导出 SCTP(DataChannel) 明文消息。

默认使用 macOS Wireshark.app 自带 tshark:
  /Applications/Wireshark.app/Contents/MacOS/tshark
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import List, Tuple


def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True, errors="replace")


def detect_dtls_ports(tshark: str, pcap: str) -> List[int]:
    out = run(
        [
            tshark,
            "-r",
            pcap,
            "-Y",
            "dtls",
            "-T",
            "fields",
            "-e",
            "udp.srcport",
            "-e",
            "udp.dstport",
        ]
    )
    ports = set()
    for line in out.splitlines():
        parts = [x.strip() for x in line.split("\t") if x.strip()]
        for p in parts:
            if p.isdigit():
                ports.add(int(p))
    return sorted(ports)


def fetch_sctp_rows(
    tshark: str, pcap: str, keylog: str, dtls_ports: List[int]
) -> List[Tuple[str, ...]]:
    cmd = [
        tshark,
        "-r",
        pcap,
        "-o",
        f"tls.keylog_file:{keylog}",
    ]
    for p in dtls_ports:
        cmd.extend(["-d", f"udp.port=={p},dtls"])
    cmd.extend(
        [
            "-Y",
            "sctp.data_payload_proto_id==51",
            "-T",
            "fields",
            "-E",
            "separator=\t",
            "-e",
            "frame.number",
            "-e",
            "ip.src",
            "-e",
            "udp.srcport",
            "-e",
            "ip.dst",
            "-e",
            "udp.dstport",
            "-e",
            "sctp.data_tsn",
            "-e",
            "sctp.data_payload_proto_id",
            "-e",
            "data.data",
            "-e",
            "_ws.col.info",
        ]
    )
    out = run(cmd)
    rows: List[Tuple[str, ...]] = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 9:
            continue
        rows.append(tuple(parts[:9]))
    return rows


def decode_hex_payload(hex_text: str) -> str:
    if not hex_text:
        return ""
    try:
        raw = bytes.fromhex(hex_text)
        text = raw.decode("utf-8", errors="replace")
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            # 标准化 JSON，方便日志对齐
            obj = json.loads(text)
            return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        return text
    except Exception:
        return ""


def render_block(rows: List[Tuple[str, ...]]) -> str:
    lines = []
    lines.append("  SCTP plaintext messages (auto via tshark):")
    for r in rows:
        frame, sip, sport, dip, dport, tsn, ppid, hex_payload, info = r
        text = decode_hex_payload(hex_payload)
        lines.append(
            f"    - Frame {frame} | proto=SCTP | PPID={ppid} | TSN={tsn} | {info.strip()}"
        )
        lines.append(f"      {sip}:{sport} -> {dip}:{dport}")
        if text:
            lines.append(f"      JSON/Text: {text}")
        else:
            lines.append("      JSON/Text: <empty or non-UTF8>")
    return "\n".join(lines)


def update_log(log_path: Path, block: str) -> None:
    text = log_path.read_text(encoding="utf-8")
    start_anchor = "  SCTP parse status:"
    end_anchor = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n  ✅ Interop Summary"
    si = text.find(start_anchor)
    ei = text.find(end_anchor)
    if si == -1 or ei == -1 or ei <= si:
        # 找不到结构就直接追加
        text = text.rstrip() + "\n\n" + block + "\n"
        log_path.write_text(text, encoding="utf-8")
        return

    # 保留 parse status 段，替换旧消息块
    # 找 parse status 段尾（连续空行后）
    head = text[:si]
    mid = text[si:ei]
    tail = text[ei:]
    parse_end = mid.find("\n\n")
    if parse_end == -1:
        new_mid = mid.rstrip() + "\n\n" + block + "\n\n"
    else:
        parse_part = mid[:parse_end].rstrip()
        new_mid = parse_part + "\n\n" + block + "\n\n"
    log_path.write_text(head + new_mid + tail, encoding="utf-8")


def normalize_punctuation(text: str) -> str:
    mapping = {
        "，": ",",
        "。": ".",
        "：": ":",
        "；": ";",
        "（": "(",
        "）": ")",
        "【": "[",
        "】": "]",
        "？": "?",
        "！": "!",
        "、": ",",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
    }
    for src, dst in mapping.items():
        text = text.replace(src, dst)
    return text


def main() -> None:
    ap = argparse.ArgumentParser(description="Export DTLS->SCTP plaintext via tshark")
    ap.add_argument("pcap", help="pcap/pcapng file")
    ap.add_argument("-k", "--keylog", required=True, help="(Pre)-Master-Secret keylog")
    ap.add_argument(
        "--tshark",
        default="/Applications/Wireshark.app/Contents/MacOS/tshark",
        help="tshark path",
    )
    ap.add_argument("--log", help="optional: update target log file in place")
    ap.add_argument(
        "--normalize-punctuation",
        action="store_true",
        help="replace Chinese punctuation with ASCII in updated log",
    )
    args = ap.parse_args()

    ports = detect_dtls_ports(args.tshark, args.pcap)
    if not ports:
        raise SystemExit("No DTLS UDP ports detected.")

    rows = fetch_sctp_rows(args.tshark, args.pcap, args.keylog, ports)
    block = render_block(rows)
    print(block)

    if args.log:
        log_path = Path(args.log)
        update_log(log_path, block)
        if args.normalize_punctuation:
            normed = normalize_punctuation(log_path.read_text(encoding="utf-8"))
            log_path.write_text(normed, encoding="utf-8")
        print(f"\n[OK] updated log: {args.log}")


if __name__ == "__main__":
    main()

