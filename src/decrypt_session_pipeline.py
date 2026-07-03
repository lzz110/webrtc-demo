#!/usr/bin/env python3
"""
One-shot pipeline:
1) Decrypt DTLS/SCTP plaintext messages via tshark.
2) Decrypt SRTP RED/VP8 and export top-N videos.
3) Generate a single decrypt log with ASCII punctuation.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scapy.all import UDP, rdpcap

from export_sctp_plaintext import detect_dtls_ports, fetch_sctp_rows, decode_hex_payload, normalize_punctuation
from red_vp8_extract import extract_red_vp8_frames, ffmpeg_ivf_to_mp4, write_ivf
from webrtc_h264_extractor import RTPHeader, SRTPDecryptor, SRTPKey


def run(cmd: List[str]) -> str:
    return subprocess.check_output(cmd, text=True, errors="replace")


def count_packets(pcap: Path) -> Tuple[int, int, int]:
    pkts = rdpcap(str(pcap))
    total = len(pkts)
    udp = sum(1 for p in pkts if p.haslayer(UDP))
    tcp = sum(1 for p in pkts if p.haslayer("TCP"))
    return total, udp, tcp


def top_video_ssrcs(pcap: Path, keylog: Path, outer_pt: int = 123, top_n: int = 2) -> List[Tuple[int, int]]:
    keys = SRTPKey.parse_keylog(str(keylog))
    decs: List[SRTPDecryptor] = []
    if keys.get("client"):
        decs.append(SRTPDecryptor(keys["client"]))
    if keys.get("server"):
        decs.append(SRTPDecryptor(keys["server"]))
    if not decs:
        raise RuntimeError("no valid SRTP keys in keylog")

    counts: Dict[int, int] = defaultdict(int)
    for p in rdpcap(str(pcap)):
        if not p.haslayer(UDP):
            continue
        raw = bytes(p[UDP].payload)
        plain = None
        for d in decs:
            x = d.decrypt(raw)
            if x:
                plain = x
                break
        if not plain:
            continue
        rtp = RTPHeader.parse(plain)
        if not rtp:
            continue
        if rtp.payload_type == outer_pt:
            counts[rtp.ssrc] += 1
    items = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    return items[:top_n]


def signaling_stats_from_strings(pcap: Path) -> Dict[str, Any]:
    import re

    out = run(["strings", str(pcap)])
    stats = {
        "signal": len(re.findall(r'"type":"signal"', out)),
        "offer": len(re.findall(r'"type":"offer"', out)),
        "answer": len(re.findall(r'"type":"answer"', out)),
        "ice_candidate": len(re.findall(r'"type":"ice_candidate"', out)),
        "hello": len(re.findall(r'"type":"hello"', out)),
        "peers": sorted(set(re.findall(r'"from":"([^"]+)"', out))),
        "candidates": len(re.findall(r"candidate:[^\\r\\n\"]+", out)),
    }
    return stats


def stun_stats(tshark: str, pcap: Path) -> Dict[str, Any]:
    out = run(
        [
            tshark,
            "-r",
            str(pcap),
            "-Y",
            "stun",
            "-T",
            "fields",
            "-e",
            "ip.src",
            "-e",
            "udp.srcport",
            "-e",
            "ip.dst",
            "-e",
            "udp.dstport",
            "-e",
            "stun.type",
        ]
    )
    req = 0
    resp = 0
    total = 0
    pairs = defaultdict(int)
    for ln in out.splitlines():
        p = ln.split("\t")
        if len(p) < 5:
            continue
        sip, sp, dip, dp, st = p[:5]
        try:
            t = int(st, 16)
        except ValueError:
            continue
        total += 1
        if t == 0x0001:
            req += 1
        elif t == 0x0101:
            resp += 1
        key = tuple(sorted([(sip, sp), (dip, dp)]))
        pairs[key] += 1
    top_pair = None
    if pairs:
        top_pair = max(pairs.items(), key=lambda kv: kv[1])[0]
    return {"total": total, "request": req, "response": resp, "pair_count": len(pairs), "top_pair": top_pair}


def dtls_record_stats(tshark: str, pcap: Path) -> Dict[int, int]:
    out = run(
        [
            tshark,
            "-r",
            str(pcap),
            "-Y",
            "dtls",
            "-T",
            "fields",
            "-e",
            "dtls.record.content_type",
        ]
    )
    counts: Dict[int, int] = defaultdict(int)
    for ln in out.splitlines():
        for tok in ln.split(","):
            tok = tok.strip()
            if tok.isdigit():
                counts[int(tok)] += 1
    return dict(counts)


def rtp_stream_summary(pcap: Path, keylog: Path) -> Tuple[int, int, List[Dict[str, Any]]]:
    keys = SRTPKey.parse_keylog(str(keylog))
    decs: List[SRTPDecryptor] = []
    if keys.get("client"):
        decs.append(SRTPDecryptor(keys["client"]))
    if keys.get("server"):
        decs.append(SRTPDecryptor(keys["server"]))
    if not decs:
        return 0, 0, []

    stats: Dict[int, Dict[str, Any]] = defaultdict(lambda: {"count": 0, "pt": defaultdict(int), "seq_min": None, "seq_max": None})
    total_rtp = 0
    for p in rdpcap(str(pcap)):
        if not p.haslayer(UDP):
            continue
        raw = bytes(p[UDP].payload)
        plain = None
        for d in decs:
            x = d.decrypt(raw)
            if x:
                plain = x
                break
        if not plain:
            continue
        rtp = RTPHeader.parse(plain)
        if not rtp:
            continue
        total_rtp += 1
        s = stats[rtp.ssrc]
        s["count"] += 1
        s["pt"][rtp.payload_type] += 1
        if s["seq_min"] is None or rtp.sequence_number < s["seq_min"]:
            s["seq_min"] = rtp.sequence_number
        if s["seq_max"] is None or rtp.sequence_number > s["seq_max"]:
            s["seq_max"] = rtp.sequence_number

    rows: List[Dict[str, Any]] = []
    for ssrc, info in sorted(stats.items(), key=lambda kv: kv[1]["count"], reverse=True):
        top_pts = sorted(info["pt"].items(), key=lambda kv: kv[1], reverse=True)
        pt_text = ",".join(str(p[0]) for p in top_pts[:2])
        if 111 in info["pt"]:
            kind = "audio"
        elif 123 in info["pt"]:
            kind = "video"
        else:
            kind = "rtx"
        rows.append(
            {
                "ssrc_hex": f"0x{ssrc:08X}",
                "type": kind,
                "count": info["count"],
                "pt": pt_text,
                "seq": f"{info['seq_min']}-{info['seq_max']}",
            }
        )
    return total_rtp, len(stats), rows


def sdp_lines_from_strings(pcap: Path) -> Tuple[List[str], List[str]]:
    out = run(["strings", str(pcap)])
    offer = []
    answer = []
    import re

    mo = re.search(r'"type":"offer".*?"sdp":"(.*?)"\}\}', out)
    if mo:
        s = mo.group(1).replace("\\r\\n", "\n")
        for pat in [
            r"^m=video .*$",
            r"^a=rtpmap:96 .*$",
            r"^a=rtpmap:98 .*$",
            r"^a=rtpmap:109 .*$",
            r"^a=rtpmap:123 .*$",
            r"^m=application .*$",
            r"^a=sctp-port:.*$",
            r"^a=max-message-size:.*$",
        ]:
            m = re.search(pat, s, re.M)
            if m:
                offer.append(m.group(0))

    ai = out.find('"type":"answer"')
    if ai != -1:
        st = out.rfind('{"type":"signal"', 0, ai)
        ed = out.find("}}", ai)
        blk = out[st : ed + 2]
        ma = re.search(r'"sdp":"(.*?)","type":"answer"', blk)
        if ma:
            s = ma.group(1).replace("\\r\\n", "\n")
            for pat in [
                r"^m=video .*$",
                r"^a=rtpmap:96 .*$",
                r"^a=rtpmap:98 .*$",
                r"^a=rtpmap:109 .*$",
                r"^a=rtpmap:123 .*$",
                r"^m=application .*$",
                r"^a=sctp-port:.*$",
                r"^a=max-message-size:.*$",
            ]:
                m = re.search(pat, s, re.M)
                if m:
                    answer.append(m.group(0))
    return offer, answer


def build_log(
    pcap: Path,
    keylog: Path,
    total: int,
    udp: int,
    tcp: int,
    offer: List[str],
    answer: List[str],
    signaling: Dict[str, Any],
    stun: Dict[str, Any],
    dtls_records: Dict[int, int],
    dtls_ports: List[int],
    sctp_rows: List[Tuple[str, ...]],
    rtp_total: int,
    rtp_ssrcs: int,
    rtp_rows: List[Dict[str, Any]],
    exports: List[Dict[str, str]],
) -> str:
    lines: List[str] = []
    lines.append(f"python3 decrypt_session_pipeline.py {pcap.name} -k {keylog}")
    lines.append("")
    lines.append("======================================================================")
    lines.append(f"  WebRTC Session Decrypt Report: {pcap.name}")
    lines.append("======================================================================")
    lines.append(f"  Capture File : {pcap.name}")
    lines.append(f"  Packet Count : {total} (UDP={udp}, TCP={tcp})")
    lines.append(f"  Generated At : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("----------------------------------------------------------------------")
    lines.append("  [Signaling]")
    lines.append("----------------------------------------------------------------------")
    lines.append(
        "  Messages: "
        f"signal={signaling['signal']}, offer={signaling['offer']}, answer={signaling['answer']}, "
        f"ice_candidate={signaling['ice_candidate']}, hello={signaling['hello']}"
    )
    if signaling["peers"]:
        lines.append("  Peers: " + " <-> ".join(signaling["peers"][:2]))
    lines.append(f"  ICE candidates in signaling: {signaling['candidates']}")
    lines.append("")
    lines.append("  SDP Offer:")
    lines.extend([f"    {x}" for x in offer])
    lines.append("  SDP Answer:")
    lines.extend([f"    {x}" for x in answer])
    lines.append("")
    lines.append("----------------------------------------------------------------------")
    lines.append("  [ICE / STUN]")
    lines.append("----------------------------------------------------------------------")
    lines.append(f"  STUN total={stun['total']}, request={stun['request']}, response={stun['response']}")
    lines.append(f"  Candidate pairs observed={stun['pair_count']}")
    if stun["top_pair"]:
        (a, ap), (b, bp) = stun["top_pair"]
        lines.append(f"  Active pair: {a}:{ap} <-> {b}:{bp}")
    lines.append("")
    lines.append("----------------------------------------------------------------------")
    lines.append("  [DTLS]")
    lines.append("----------------------------------------------------------------------")
    lines.append(f"  DTLS UDP ports: {', '.join(map(str, dtls_ports)) if dtls_ports else 'N/A'}")
    lines.append(
        "  Records: "
        f"Handshake(22)={dtls_records.get(22,0)}, "
        f"ChangeCipherSpec(20)={dtls_records.get(20,0)}, "
        f"ApplicationData(23)={dtls_records.get(23,0)}, "
        f"Alert(21)={dtls_records.get(21,0)}"
    )
    lines.append("")
    lines.append("----------------------------------------------------------------------")
    lines.append("  [RTP Streams (decrypted)]")
    lines.append("----------------------------------------------------------------------")
    lines.append(f"  SSRCs={rtp_ssrcs}, RTP packets={rtp_total}")
    lines.append("  SSRC         Type    Count    PT        Seq Range")
    lines.append("  --------------------------------------------------")
    for row in rtp_rows[:8]:
        lines.append(
            f"  {row['ssrc_hex']:<12} {row['type']:<7} {row['count']:<8} {row['pt']:<9} {row['seq']}"
        )
    lines.append("")
    lines.append("----------------------------------------------------------------------")
    lines.append("  [SCTP / DataChannel Plaintext]")
    lines.append("----------------------------------------------------------------------")
    if not sctp_rows:
        lines.append("  No SCTP plaintext rows found")
    for r in sctp_rows:
        frame, sip, sport, dip, dport, tsn, ppid, hex_payload, info = r
        txt = decode_hex_payload(hex_payload)
        lines.append(f"  Frame {frame} | SCTP | PPID={ppid} | TSN={tsn} | {info.strip()}")
        lines.append(f"    {sip}:{sport} -> {dip}:{dport}")
        lines.append(f"    JSON/Text: {txt if txt else '<empty or non-UTF8>'}")
    lines.append("")
    lines.append("----------------------------------------------------------------------")
    lines.append("  [Decrypted Video Exports]")
    lines.append("----------------------------------------------------------------------")
    for i, e in enumerate(exports, 1):
        lines.append(f"  [{i}] SSRC {e['ssrc_hex']} | packets={e['packet_count']} | frames={e['frames']}")
        lines.append(f"      IVF: {e['ivf']}")
        lines.append(f"      MP4: {e['mp4']} ({e['size']} bytes)")
    lines.append("")
    lines.append("----------------------------------------------------------------------")
    lines.append("  [Protocol Summary]")
    lines.append("----------------------------------------------------------------------")
    lines.append(f"  ICE/STUN: {stun['total']} packets, pairs={stun['pair_count']}")
    lines.append(f"  DTLS: total={sum(dtls_records.values())}, app_data={dtls_records.get(23,0)}")
    lines.append(f"  SRTP/RTP: ssrcs={rtp_ssrcs}, packets={rtp_total}")
    lines.append(f"  SCTP plaintext rows: {len(sctp_rows)}")
    lines.append(f"  Video outputs: {len(exports)}")
    lines.append("======================================================================")
    return normalize_punctuation("\n".join(lines) + "\n")


def main() -> None:
    ap = argparse.ArgumentParser(description="One-shot DTLS/SCTP + AV decrypt pipeline")
    ap.add_argument("pcap", type=Path)
    ap.add_argument("-k", "--keylog", type=Path, required=True)
    ap.add_argument(
        "--tshark",
        default="/Applications/Wireshark.app/Contents/MacOS/tshark",
        help="tshark path",
    )
    ap.add_argument("--top-videos", type=int, default=2, help="export top N video SSRC by PT=123 packets")
    ap.add_argument("--outer-pt", type=int, default=123)
    ap.add_argument("--out-dir", type=Path, default=None)
    ap.add_argument("--log", type=Path, default=None, help="output log path")
    args = ap.parse_args()

    if args.out_dir is None:
        out_dir = args.pcap.parent / "test-parse"
    else:
        out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.log is None:
        log_path = out_dir / f"{args.pcap.stem}-test-decrypt.log"
    else:
        log_path = args.log

    total, udp, tcp = count_packets(args.pcap)
    signaling = signaling_stats_from_strings(args.pcap)
    stun = stun_stats(args.tshark, args.pcap)
    dtls_records = dtls_record_stats(args.tshark, args.pcap)
    offer, answer = sdp_lines_from_strings(args.pcap)
    dtls_ports = detect_dtls_ports(args.tshark, str(args.pcap))
    sctp_rows = fetch_sctp_rows(args.tshark, str(args.pcap), str(args.keylog), dtls_ports)
    rtp_total, rtp_ssrcs, rtp_rows = rtp_stream_summary(args.pcap, args.keylog)

    top_ssrc = top_video_ssrcs(args.pcap, args.keylog, outer_pt=args.outer_pt, top_n=args.top_videos)
    exports: List[Dict[str, str]] = []
    for ssrc, cnt in top_ssrc:
        ssrc_hex = f"0x{ssrc:08X}"
        mp4 = out_dir / f"{args.pcap.stem}_{ssrc_hex}.mp4"
        ivf = out_dir / f"{args.pcap.stem}_{ssrc_hex}.ivf"
        frames = extract_red_vp8_frames(args.pcap, args.keylog, ssrc, outer_pt=args.outer_pt)
        if not frames:
            continue
        write_ivf(frames, ivf)
        ffmpeg_ivf_to_mp4(ivf, mp4)
        exports.append(
            {
                "ssrc_hex": ssrc_hex,
                "packet_count": str(cnt),
                "frames": str(len(frames)),
                "ivf": str(ivf),
                "mp4": str(mp4),
                "size": str(mp4.stat().st_size),
            }
        )

    text = build_log(
        args.pcap,
        args.keylog,
        total,
        udp,
        tcp,
        offer,
        answer,
        signaling,
        stun,
        dtls_records,
        dtls_ports,
        sctp_rows,
        rtp_total,
        rtp_ssrcs,
        rtp_rows,
        exports,
    )
    log_path.write_text(text, encoding="utf-8")
    print(f"[OK] log: {log_path}")
    for e in exports:
        print(f"[OK] video: {e['mp4']}")


if __name__ == "__main__":
    main()

