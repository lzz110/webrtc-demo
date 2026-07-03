#!/usr/bin/env python3
"""
webrtc_h264_extractor.py - WebRTC H.264 Video Stream Extractor
从 WebRTC pcapng 抓包中提取 H.264 视频流（支持 SRTP 解密）

完整处理流程:
    1. 读取原始 pcapng (可能包含 SRTP)
    2. 自动检测/解密 SRTP → RTP (如果提供 keylog)
    3. 解析 RTP + H.264
    4. 重组 FU-A 分片
    5. 生成 MP4 视频

用法:
    # 从解密后的抓包提取
    python3 webrtc_h264_extractor.py extract decrypted.pcapng

    # 从原始加密抓包提取（需要提供 keylog）
    python3 webrtc_h264_extractor.py extract capture.pcapng -k webrtc_keys.log

    # 查看所有 SSRC
    python3 webrtc_h264_extractor.py extract capture.pcapng -l

依赖:
    pip install scapy pylibsrtp
    ffmpeg

作者: AI Assistant
日期: 2026-03-19
"""

import struct
import subprocess
import tempfile
import os
import sys
import re
import argparse
import wave
import audioop
from pathlib import Path
from typing import List, Tuple, Optional, Dict, NamedTuple, Any
from dataclasses import dataclass

try:
    from scapy.all import rdpcap, UDP, wrpcap, Raw
except ImportError:
    print("错误: 请先安装 scapy")
    print("  pip install scapy")
    sys.exit(1)

# 可选的 pylibsrtp
try:
    import pylibsrtp

    HAS_PYLIBSRTP = True
except ImportError:
    HAS_PYLIBSRTP = False
    print("警告: 未安装 pylibsrtp，无法解密 SRTP")
    print("  pip install pylibsrtp")


@dataclass
class RTPHeader:
    """RTP 头部解析结果"""

    version: int
    padding: bool
    extension: bool
    csrc_count: int
    marker: bool
    payload_type: int
    sequence_number: int
    timestamp: int
    ssrc: int
    header_len: int

    @classmethod
    def parse(cls, data: bytes) -> Optional["RTPHeader"]:
        """从字节解析 RTP 头部"""
        if len(data) < 12:
            return None

        version = (data[0] >> 6) & 0x03
        if version != 2:
            return None

        padding = bool((data[0] >> 5) & 0x01)
        extension = bool((data[0] >> 4) & 0x01)
        csrc_count = data[0] & 0x0F

        marker = bool((data[1] >> 7) & 0x01)
        payload_type = data[1] & 0x7F
        sequence_number = struct.unpack(">H", data[2:4])[0]
        timestamp = struct.unpack(">I", data[4:8])[0]
        ssrc = struct.unpack(">I", data[8:12])[0]

        header_len = 12 + csrc_count * 4

        if extension and len(data) >= header_len + 4:
            ext_len = struct.unpack(">H", data[header_len + 2 : header_len + 4])[0]
            header_len += 4 + ext_len * 4

        return cls(
            version=version,
            padding=padding,
            extension=extension,
            csrc_count=csrc_count,
            marker=marker,
            payload_type=payload_type,
            sequence_number=sequence_number,
            timestamp=timestamp,
            ssrc=ssrc,
            header_len=header_len,
        )


@dataclass
class NALUnit:
    """H.264 NAL 单元"""

    data: bytes
    nal_type: int
    f_bit: int
    nri: int
    source: str


class SRTPKey:
    """SRTP 密钥解析"""

    @staticmethod
    def parse_keylog(keylog_path: str) -> Dict[str, bytes]:
        """解析 SSLKEYLOGFILE 格式的 SRTP 密钥（支持双向）"""
        keys = {}

        with open(keylog_path, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                # 格式: SRTP <client_random_hex> <key><salt>
                # 格式: SRTP_SERVER <client_random_hex> <key><salt>
                if line.startswith("SRTP ") or line.startswith("SRTP_SERVER "):
                    parts = line.split()
                    if len(parts) >= 2:
                        key_type = "server" if parts[0] == "SRTP_SERVER" else "client"
                        
                        # 尝试不同的格式
                        if len(parts) == 2:
                            # SRTP <hex_key_salt>
                            hex_data = parts[1]
                        else:
                            # SRTP <random> <hex_key_salt>
                            hex_data = parts[2] if len(parts) > 2 else parts[1]

                        try:
                            key_material = bytes.fromhex(hex_data)
                            # 30 bytes = 16 (key) + 14 (salt)
                            if len(key_material) == 30:
                                keys[key_type] = key_material
                                print(f"  找到 {parts[0]} 密钥: {hex_data[:16]}...")
                        except ValueError:
                            pass
                # 格式: SRTP_KEYS ... role=server ... send_key=<hex> recv_key=<hex>
                elif line.startswith("SRTP_KEYS "):
                    m_role = re.search(r"\brole=(client|server)\b", line)
                    m_send = re.search(r"\bsend_key=([0-9a-fA-F]+)\b", line)
                    m_recv = re.search(r"\brecv_key=([0-9a-fA-F]+)\b", line)
                    if not m_role or not m_send or not m_recv:
                        continue

                    role = m_role.group(1)
                    send_hex = m_send.group(1)
                    recv_hex = m_recv.group(1)

                    # 按 DTLS role 映射到「client/server write key」
                    # role=server: send=server_write, recv=client_write
                    # role=client: send=client_write, recv=server_write
                    if role == "server":
                        client_hex = recv_hex
                        server_hex = send_hex
                    else:
                        client_hex = send_hex
                        server_hex = recv_hex

                    try:
                        client_key = bytes.fromhex(client_hex)
                        server_key = bytes.fromhex(server_hex)
                        if len(client_key) == 30:
                            keys["client"] = client_key
                            print(f"  找到 SRTP_KEYS(client) 密钥: {client_hex[:16]}...")
                        if len(server_key) == 30:
                            keys["server"] = server_key
                            print(f"  找到 SRTP_KEYS(server) 密钥: {server_hex[:16]}...")
                    except ValueError:
                        pass

        return keys


class SRTPDecryptor:
    """SRTP 解密器"""

    def __init__(self, key_material: bytes):
        """初始化 SRTP Session"""
        if not HAS_PYLIBSRTP:
            raise RuntimeError("pylibsrtp 未安装")

        if not key_material:
            raise ValueError("密钥材料不能为空")

        # 创建 SRTP Policy
        policy = pylibsrtp.Policy(
            key=key_material,
            srtp_profile=pylibsrtp.Policy.SRTP_PROFILE_AES128_CM_SHA1_80,
            ssrc_type=pylibsrtp.Policy.SSRC_ANY_INBOUND,
        )
        self.session = pylibsrtp.Session(policy)
        self.decrypt_errors = {
            "total": 0,
            "auth_fail": 0,
            "replay_fail": 0,
            "other": 0,
        }

    def decrypt(self, srtp_data: bytes) -> Optional[bytes]:
        """解密 SRTP 包，记录详细错误信息"""
        try:
            return self.session.unprotect(srtp_data)
        except pylibsrtp.Error as e:
            self.decrypt_errors["total"] += 1
            error_msg = str(e).lower()
            if "auth" in error_msg or "tag" in error_msg:
                self.decrypt_errors["auth_fail"] += 1
                # print(f"[SRTP] 认证失败: {e}")
            elif "replay" in error_msg or "order" in error_msg:
                self.decrypt_errors["replay_fail"] += 1
                # print(f"[SRTP] 重放保护失败: {e}")
            else:
                self.decrypt_errors["other"] += 1
                # print(f"[SRTP] 解密失败: {e}")
            return None
        except Exception as e:
            self.decrypt_errors["total"] += 1
            self.decrypt_errors["other"] += 1
            # print(f"[SRTP] 未知错误: {e}")
            return None

    def get_error_stats(self) -> Dict[str, int]:
        """获取解密错误统计"""
        return self.decrypt_errors.copy()


class PacketInfo(NamedTuple):
    """解析后的包信息"""

    packet: Any  # scapy packet
    udp_payload: bytes
    rtp: Optional[RTPHeader]
    decrypted: bool


class H264Extractor:
    """H.264 视频流提取器"""

    NAL_TYPE_NAMES = {
        0: "Unspecified",
        1: "Non-IDR",
        2: "Part-A",
        3: "Part-B",
        4: "Part-C",
        5: "IDR",
        6: "SEI",
        7: "SPS",
        8: "PPS",
        9: "AUD",
        10: "End-Seq",
        11: "End-Str",
        12: "Filler",
        24: "STAP-A",
        28: "FU-A",
    }

    def __init__(self):
        self.stats = {
            "total_packets": 0,
            "rtp_packets": 0,
            "h264_packets": 0,
            "nal_units": 0,
            "frames": 0,
            "decrypted": 0,
            "decrypt_attempts": 0,
            "decrypted_client": 0,
            "decrypted_server": 0,
        }
        self.decryptors: List[SRTPDecryptor] = []

    def set_decryptor(self, decryptor: SRTPDecryptor):
        """设置解密器（单个，兼容旧接口）"""
        self.decryptors = [decryptor]
    
    def set_decryptors(self, decryptors: List[SRTPDecryptor]):
        """设置多个解密器（双向支持）"""
        self.decryptors = decryptors

    def iter_packets(
        self, packets: List, target_ssrc: Optional[int] = None
    ):
        """迭代处理包，自动解密并解析 RTP

        Yields:
            PacketInfo: 包含原始包、UDP payload、RTP 头部和解密状态的元组
        """
        total = len(packets)
        processed = 0
        
        for i, pkt in enumerate(packets):
            if not pkt.haslayer(UDP):
                continue

            udp_payload = bytes(pkt[UDP].payload)
            decrypted = False

            # 尝试用所有解密器解密（支持双向）
            if self.decryptors:
                self.stats["decrypt_attempts"] += 1
                for idx, decryptor in enumerate(self.decryptors):
                    decrypted_data = decryptor.decrypt(udp_payload)
                    if decrypted_data:
                        udp_payload = decrypted_data
                        decrypted = True
                        self.stats["decrypted"] += 1
                        # 记录是哪个密钥解密成功的
                        if idx == 0:
                            self.stats["decrypted_client"] += 1
                        else:
                            self.stats["decrypted_server"] += 1
                        break  # 解密成功就停止尝试

            # 解析 RTP 头部
            rtp = RTPHeader.parse(udp_payload)

            # 过滤 SSRC
            if target_ssrc and rtp and rtp.ssrc != target_ssrc:
                continue

            processed += 1
            
            # 每500个包显示一次进度
            if (i + 1) % 500 == 0:
                progress = (i + 1) / total * 100
                print(f"  处理进度: {i + 1}/{total} ({progress:.1f}%)", end="\r")

            yield PacketInfo(packet=pkt, udp_payload=udp_payload, rtp=rtp, decrypted=decrypted)
        
        if processed > 0:
            print(f"  处理完成: {processed} 个 RTP 包")

    def parse_nal_header(self, byte: int) -> Tuple[int, int, int]:
        """解析 NAL 头部"""
        return ((byte >> 7) & 0x01, (byte >> 5) & 0x03, byte & 0x1F)

    def is_likely_srtp(self, payload: bytes) -> bool:
        """检测是否为 SRTP（而非 RTP）"""
        if len(payload) < 12:
            return False

        # 检查版本号
        version = (payload[0] >> 6) & 0x03
        if version != 2:
            return False

        # 检查 payload type
        pt = payload[1] & 0x7F

        # WebRTC 视频通常在 96-127 之间
        if 96 <= pt <= 127:
            # 可能是 RTP 或 SRTP
            # 检查 NAL 类型来区分
            # RTP header 长度最小 12 字节
            cc = payload[0] & 0x0F
            header_len = 12 + cc * 4

            # 检查是否有 extension
            if (payload[0] >> 4) & 0x01:
                if len(payload) >= header_len + 4:
                    ext_len = struct.unpack(
                        ">H", payload[header_len + 2 : header_len + 4]
                    )[0]
                    header_len += 4 + ext_len * 4

            if len(payload) > header_len:
                first_byte = payload[header_len]
                nal_type = first_byte & 0x1F

                # 如果 NAL 类型不在 0-28 范围内，可能是加密的 SRTP
                if nal_type > 28:
                    return True

        return False

    def parse_stap_a(self, payload: bytes) -> List[NALUnit]:
        """解析 STAP-A 聚合包"""
        nals = []
        offset = 1

        while offset + 2 < len(payload):
            nal_size = struct.unpack(">H", payload[offset : offset + 2])[0]
            offset += 2
            if offset + nal_size > len(payload):
                break

            nal_data = payload[offset : offset + nal_size]
            f_bit, nri, nal_type = self.parse_nal_header(nal_data[0])
            nals.append(NALUnit(nal_data, nal_type, f_bit, nri, "STAP"))
            offset += nal_size

        return nals

    def parse_fu_a(
        self, payload: bytes, fu_buffer: Dict, ssrc: int, timestamp: int
    ) -> List[NALUnit]:
        """解析 FU-A 分片包"""
        if len(payload) < 2:
            return []

        nal_byte = payload[0]
        fu_header = payload[1]

        start_bit = (fu_header >> 7) & 1
        end_bit = (fu_header >> 6) & 1
        orig_nal_type = fu_header & 0x1F

        orig_nal_header = bytes([(nal_byte & 0xE0) | orig_nal_type])
        fu_payload = payload[2:]

        # 使用 (ssrc, timestamp, nal_type) 作为 key，避免并发冲突
        key = (ssrc, timestamp, orig_nal_type)

        if start_bit:
            fu_buffer[key] = orig_nal_header + fu_payload
            return []

        if key in fu_buffer:
            fu_buffer[key] += fu_payload
            if end_bit:
                complete = fu_buffer.pop(key)
                f_bit, nri, nal_type = self.parse_nal_header(complete[0])
                return [NALUnit(complete, nal_type, f_bit, nri, "FUA")]

        return []

    def extract_from_pcap(
        self,
        pcap_path: str,
        target_ssrc: Optional[int] = None,
        keylog_path: Optional[str] = None,
    ) -> Tuple[List[List[NALUnit]], Dict]:
        """从 pcapng 提取 H.264 帧（自动处理 SRTP 解密）"""
        print(f"读取: {pcap_path}")
        packets = rdpcap(pcap_path)
        self.stats["total_packets"] = len(packets)
        print(f"  共 {len(packets):,} 个包")

        # 初始化解密器（如果提供 keylog）
        if keylog_path and HAS_PYLIBSRTP:
            print(f"加载密钥: {keylog_path}")
            keys = SRTPKey.parse_keylog(keylog_path)
            decryptors = []
            
            # 加载客户端密钥
            if keys.get("client"):
                print(f"  找到客户端密钥，长度: {len(keys['client'])} bytes")
                decryptors.append(SRTPDecryptor(keys["client"]))
            
            # 加载服务端密钥
            if keys.get("server"):
                print(f"  找到服务端密钥，长度: {len(keys['server'])} bytes")
                decryptors.append(SRTPDecryptor(keys["server"]))
            
            if decryptors:
                self.decryptors = decryptors
                print(f"  已初始化 {len(decryptors)} 个 SRTP 解密器（双向支持）")
                print(f"  解密状态: 激活 - 将尝试解密 SRTP 包")
            else:
                print("  警告: 未找到有效密钥")

        # 检测是否为加密流
        sample_encrypted = 0
        sample_total = 0
        for pkt in packets[:50]:  # 采样前50个包
            if pkt.haslayer(UDP):
                payload = bytes(pkt[UDP].payload)
                if len(payload) >= 12:
                    sample_total += 1
                    if self.is_likely_srtp(payload):
                        sample_encrypted += 1

        if sample_total > 0 and sample_encrypted / sample_total > 0.5:
            print(f"\n检测到加密流 ({sample_encrypted}/{sample_total} 包可能是 SRTP)")
            if not self.decryptor:
                print("警告: 未提供密钥，可能无法正确解析")
                print("  使用 -k 参数指定 keylog 文件")

        # 处理包
        fu_buffers: Dict[Tuple[int, int], Dict[int, bytes]] = {}
        frames: List[List[NALUnit]] = []
        current_frame_nals: List[NALUnit] = []
        last_timestamp: Optional[int] = None
        last_ssrc: Optional[int] = None

        for pkt_info in self.iter_packets(packets, target_ssrc):
            rtp = pkt_info.rtp
            if not rtp:
                continue

            self.stats["rtp_packets"] += 1
            udp_payload = pkt_info.udp_payload

            if len(udp_payload) <= rtp.header_len:
                continue

            payload = udp_payload[rtp.header_len :]
            if len(payload) < 1:
                continue

            buffer_key = (rtp.ssrc, rtp.timestamp)
            if buffer_key not in fu_buffers:
                fu_buffers[buffer_key] = {}

            # 解析 H.264 NAL
            f_bit, nri, nal_type = self.parse_nal_header(payload[0])
            nals: List[NALUnit] = []

            if nal_type == 24:
                nals = self.parse_stap_a(payload)
            elif nal_type == 28:
                nals = self.parse_fu_a(payload, fu_buffers[buffer_key], rtp.ssrc, rtp.timestamp)
            elif nal_type < 24:
                nals = [NALUnit(payload, nal_type, f_bit, nri, "SINGLE")]
            else:
                # 未知类型，可能是解密失败或损坏
                continue

            if not nals:
                continue

            self.stats["h264_packets"] += 1
            self.stats["nal_units"] += len(nals)

            # 帧边界检测
            timestamp_changed = (
                last_timestamp is not None and rtp.timestamp != last_timestamp
            )
            ssrc_changed = last_ssrc is not None and rtp.ssrc != last_ssrc

            if timestamp_changed or ssrc_changed:
                if current_frame_nals:
                    frames.append(current_frame_nals)
                    self.stats["frames"] += 1
                current_frame_nals = []

            current_frame_nals.extend(nals)

            if rtp.marker and current_frame_nals:
                frames.append(current_frame_nals)
                self.stats["frames"] += 1
                current_frame_nals = []

            last_timestamp = rtp.timestamp
            last_ssrc = rtp.ssrc

        if current_frame_nals:
            frames.append(current_frame_nals)
            self.stats["frames"] += 1

        # 输出解密过程统计
        if self.decryptors:
            decrypt_attempts = self.stats.get("decrypt_attempts", 0)
            decrypted_success = self.stats.get("decrypted", 0)
            if decrypt_attempts > 0:
                failed = decrypt_attempts - decrypted_success
                success_rate = decrypted_success / decrypt_attempts * 100
                print(f"\nSRTP 解密统计:")
                print(f"  尝试解密: {decrypt_attempts:,} 个包")
                print(f"  成功解密: {decrypted_success:,} 个包 ({success_rate:.1f}%)")
                
                # 显示双向解密统计
                if len(self.decryptors) > 1:
                    client_count = self.stats.get("decrypted_client", 0)
                    server_count = self.stats.get("decrypted_server", 0)
                    print(f"    ├─ 客户端密钥: {client_count:,} 个包")
                    print(f"    └─ 服务端密钥: {server_count:,} 个包")
                
                if failed > 0:
                    print(f"  解密失败: {failed:,} 个包")
                    # 合并所有解密器的错误统计
                    total_errors = {
                        "auth_fail": 0,
                        "replay_fail": 0,
                        "other": 0,
                    }
                    for decryptor in self.decryptors:
                        err_stats = decryptor.get_error_stats()
                        total_errors["auth_fail"] += err_stats["auth_fail"]
                        total_errors["replay_fail"] += err_stats["replay_fail"]
                        total_errors["other"] += err_stats["other"]
                    
                    if total_errors["auth_fail"] > 0:
                        print(f"    ├─ 认证失败: {total_errors['auth_fail']:,}")
                    if total_errors["replay_fail"] > 0:
                        print(f"    ├─ 重放保护失败: {total_errors['replay_fail']:,}")
                    if total_errors["other"] > 0:
                        print(f"    └─ 其他错误: {total_errors['other']:,}")
        else:
            print(f"\nSRTP 解密: 未激活 (未提供密钥文件)")

        return frames, self.stats

    def analyze_frames(self, frames: List[List[NALUnit]]) -> None:
        """分析帧结构"""
        print(f"\n{'=' * 60}")
        print("帧结构分析 (前10帧)")
        print(f"{'=' * 60}")

        for i, frame in enumerate(frames[:10]):
            nal_types = [nal.nal_type for nal in frame]
            type_names = [self.NAL_TYPE_NAMES.get(t, f"NAL-{t}") for t in nal_types]
            total_size = sum(len(nal.data) for nal in frame)

            frame_type = "P"
            if 5 in nal_types:
                frame_type = "IDR"
            elif 7 in nal_types or 8 in nal_types:
                frame_type = "CFG"

            print(
                f"帧 {i:3d}: [{frame_type:4s}] {len(frame)} NALs "
                f"({', '.join(type_names)}), {total_size:6,} bytes"
            )

        if len(frames) > 10:
            print(f"... 还有 {len(frames) - 10} 帧")

        print(f"\n{'=' * 60}")
        print("NAL 类型统计")
        print(f"{'=' * 60}")

        all_nals = [nal for frame in frames for nal in frame]
        type_counts = {}
        for nal in all_nals:
            type_counts[nal.nal_type] = type_counts.get(nal.nal_type, 0) + 1

        for nal_type, count in sorted(type_counts.items()):
            name = self.NAL_TYPE_NAMES.get(nal_type, f"NAL-{nal_type}")
            pct = count / len(all_nals) * 100 if all_nals else 0
            print(f"  {name:12s}: {count:5,} ({pct:5.1f}%)")

    def frames_to_annexb(self, frames: List[List[NALUnit]]) -> bytes:
        """转换为 Annex B 格式"""
        data = bytearray()
        for frame in frames:
            for nal in frame:
                data.extend(b"\x00\x00\x00\x01")
                data.extend(nal.data)
        return bytes(data)

    def save_to_mp4(
        self, frames: List[List[NALUnit]], output_path: str, framerate: int = 30
    ) -> bool:
        """保存为 MP4"""
        annexb_data = self.frames_to_annexb(frames)

        with tempfile.NamedTemporaryFile(suffix=".264", delete=False) as f:
            f.write(annexb_data)
            temp_264 = f.name

        try:
            # 使用重新编码确保时间戳正确
            cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "h264",
                "-i",
                temp_264,
                "-r",
                str(framerate),
                "-vsync",
                "cfr",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "23",
                "-movflags",
                "+faststart",
                output_path,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                size = os.path.getsize(output_path)
                print(f"✅ 已保存: {output_path} ({size:,} bytes)")
                return True
            else:
                print(f"❌ ffmpeg 失败: {result.stderr[:500]}")
                return False
        finally:
            os.unlink(temp_264)


def list_ssrcs(pcap_path: str, keylog_path: Optional[str] = None) -> Dict[int, Dict]:
    """列出所有 SSRC"""
    print(f"扫描: {pcap_path}")
    packets = rdpcap(pcap_path)

    # 使用 H264Extractor 来处理包
    extractor = H264Extractor()
    if keylog_path and HAS_PYLIBSRTP:
        keys = SRTPKey.parse_keylog(keylog_path)
        decryptors = []
        if keys.get("client"):
            decryptors.append(SRTPDecryptor(keys["client"]))
        if keys.get("server"):
            decryptors.append(SRTPDecryptor(keys["server"]))
        if decryptors:
            extractor.set_decryptors(decryptors)

    ssrc_info = {}
    for pkt_info in extractor.iter_packets(packets):
        rtp = pkt_info.rtp
        if not rtp:
            continue

        if rtp.ssrc not in ssrc_info:
            ssrc_info[rtp.ssrc] = {
                "count": 0,
                "payload_types": set(),
                "seq_range": [rtp.sequence_number, rtp.sequence_number],
            }

        info = ssrc_info[rtp.ssrc]
        info["count"] += 1
        info["payload_types"].add(rtp.payload_type)
        info["seq_range"][0] = min(info["seq_range"][0], rtp.sequence_number)
        info["seq_range"][1] = max(info["seq_range"][1], rtp.sequence_number)

    return ssrc_info


def auto_extract_streams(
    pcap_path: str,
    keylog_path: Optional[str] = None,
    framerate: int = 30,
    output_dir: str = ".",
) -> List[Tuple[int, str]]:
    """自动提取所有 H.264 视频流

    返回: [(ssrc, packet_count), ...]
    """
    print(f"\n{'=' * 60}")
    print("自动检测视频流...")
    print(f"{'=' * 60}")

    # 使用 H264Extractor 来处理包
    packets = rdpcap(pcap_path)
    extractor = H264Extractor()
    if keylog_path and HAS_PYLIBSRTP:
        keys = SRTPKey.parse_keylog(keylog_path)
        decryptors = []
        if keys.get("client"):
            decryptors.append(SRTPDecryptor(keys["client"]))
        if keys.get("server"):
            decryptors.append(SRTPDecryptor(keys["server"]))
        if decryptors:
            extractor.set_decryptors(decryptors)

    # 收集每个 SSRC 的信息
    ssrc_info: Dict[int, Dict] = {}

    for pkt_info in extractor.iter_packets(packets):
        rtp = pkt_info.rtp
        if not rtp:
            continue

        ssrc = rtp.ssrc

        if ssrc not in ssrc_info:
            ssrc_info[ssrc] = {
                "count": 0,
                "payload_types": set(),
                "h264_candidates": 0,
                "packets": [],
            }

        ssrc_info[ssrc]["count"] += 1
        ssrc_info[ssrc]["payload_types"].add(rtp.payload_type)
        ssrc_info[ssrc]["packets"].append(pkt_info.packet)

        # 检测 H.264 NAL 类型
        udp_payload = pkt_info.udp_payload
        if len(udp_payload) > rtp.header_len:
            payload = udp_payload[rtp.header_len :]
            if len(payload) > 0:
                nal_type = payload[0] & 0x1F
                # 标准 H.264 视频 NAL 类型
                # 1=Non-IDR, 5=IDR, 24=STAP-A, 28=FU-A
                if nal_type in [1, 5, 24, 28]:
                    ssrc_info[ssrc]["h264_candidates"] += 1

    # 筛选真正的视频流：
    # 1. Payload Type 在 96-127 之间（WebRTC 动态类型）
    # 2. 至少有一些 H.264 NAL 类型
    # 3. 包数足够多（> 50）
    video_streams = []

    for ssrc, info in ssrc_info.items():
        # 检查 payload type
        has_video_pt = any(96 <= pt <= 127 for pt in info["payload_types"])

        # 检查 H.264 特征
        h264_ratio = info["h264_candidates"] / info["count"] if info["count"] > 0 else 0

        # 标准：
        # - Payload Type 是动态类型 (96-127)
        # - 至少 30% 的包是标准 H.264 NAL 类型
        # - 包数 > 100（排除短时控制流）
        if has_video_pt and h264_ratio > 0.3 and info["count"] > 100:
            video_streams.append((ssrc, info["count"]))

    # 按包数排序
    video_streams.sort(key=lambda x: -x[1])

    if not video_streams:
        print("\n未检测到视频流，放宽条件重试...")
        # 放宽条件：只要有 H.264 候选且包数 > 50
        for ssrc, info in ssrc_info.items():
            h264_ratio = (
                info["h264_candidates"] / info["count"] if info["count"] > 0 else 0
            )
            if info["h264_candidates"] > 10 and info["count"] > 50:
                video_streams.append((ssrc, info["count"]))
        video_streams.sort(key=lambda x: -x[1])

    print(f"\n检测到 {len(video_streams)} 个视频流:\n")
    print(f"{'序号':>4s} {'SSRC':>12s} {'包数':>8s} {'输出文件':>25s}")
    print("-" * 55)

    for i, (ssrc, count) in enumerate(video_streams):
        output_name = f"video_0x{ssrc:08X}.mp4"
        print(f"{i + 1:>4d} 0x{ssrc:08X} {count:>8,} {output_name:>25s}")

    return video_streams


def decrypt_pcapng(
    input_path: str,
    output_path: str,
    keylog_path: str,
    filter_rtp_only: bool = False,
    target_ssrc: Optional[int] = None,
) -> Dict:
    """将 SRTP pcapng 解密为 RTP 明文 pcapng

    Args:
        filter_rtp_only: 只保留 RTP 包（过滤掉 TCP、STUN、DTLS 等）
        target_ssrc: 只保留指定 SSRC 的包

    返回统计信息
    """
    from scapy.all import rdpcap, wrpcap, Raw

    print(f"读取: {input_path}")
    packets = rdpcap(input_path)

    # 加载密钥（支持双向）
    keys = SRTPKey.parse_keylog(keylog_path)
    decryptors = []
    
    if keys.get("client"):
        decryptors.append(SRTPDecryptor(keys["client"]))
        print(f"  已加载客户端密钥")
    
    if keys.get("server"):
        decryptors.append(SRTPDecryptor(keys["server"]))
        print(f"  已加载服务端密钥")
    
    if not decryptors:
        raise ValueError("未找到有效 SRTP 密钥")
    
    print(f"  开始解密（{len(decryptors)} 个密钥）...")
    if filter_rtp_only:
        print(f"  模式: 只保留 RTP 视频流")
    if target_ssrc:
        print(f"  过滤: 只保留 SSRC 0x{target_ssrc:08X}")

    stats = {"total": 0, "udp": 0, "decrypted": 0, "skipped": 0, "filtered": 0, "decrypted_client": 0, "decrypted_server": 0}
    decrypted_packets = []

    for i, pkt in enumerate(packets):
        stats["total"] += 1

        if not pkt.haslayer(UDP):
            # 非 UDP 包
            if filter_rtp_only:
                stats["filtered"] += 1
                continue  # 过滤掉非 UDP 包
            decrypted_packets.append(pkt)
            continue

        stats["udp"] += 1
        udp_payload = bytes(pkt[UDP].payload)

        # 尝试用所有解密器解密（支持双向）
        decrypted = None
        decrypted_by = -1
        for idx, decryptor in enumerate(decryptors):
            decrypted = decryptor.decrypt(udp_payload)
            if decrypted:
                decrypted_by = idx
                break

        if decrypted:
            # 解析 RTP 头部检查 SSRC
            rtp = RTPHeader.parse(decrypted)
            if rtp:
                # 检查 SSRC 过滤
                if target_ssrc and rtp.ssrc != target_ssrc:
                    stats["filtered"] += 1
                    continue

                # 检查 Payload Type（只保留视频流 PT 96-127）
                if filter_rtp_only and not (96 <= rtp.payload_type <= 127):
                    stats["filtered"] += 1
                    continue

            # 解密成功，替换 payload
            pkt[UDP].payload = Raw(load=decrypted)
            stats["decrypted"] += 1
            
            # 记录是哪个密钥解密的
            if decrypted_by == 0:
                stats["decrypted_client"] += 1
            else:
                stats["decrypted_server"] += 1
        else:
            # 解密失败
            if filter_rtp_only:
                stats["filtered"] += 1
                continue  # 过滤掉非 SRTP 包
            stats["skipped"] += 1

        decrypted_packets.append(pkt)

        # 进度显示
        if (i + 1) % 500 == 0:
            print(f"  已处理 {i + 1}/{len(packets)} 个包...")

    # 保存
    print(f"\n保存到: {output_path}")
    print(
        f"  保留 {len(decrypted_packets)}/{len(packets)} 个包 "
        f"(过滤 {stats['filtered']} 个)"
    )
    wrpcap(output_path, decrypted_packets)

    return stats


def parse_ssrc(value: str) -> int:
    """解析 SSRC 参数，支持十进制、十六进制（0x前缀）"""
    try:
        return int(value, 0)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"无效的 SSRC 值: {value}。支持格式: 123456789 或 0x075BCD15"
        )


def _opus_packet_duration_samples(packet: bytes, sample_rate: int = 48000) -> int:
    """根据 Opus TOC 估算一个 packet 的采样点数。"""
    if not packet:
        return int(sample_rate * 0.02)  # fallback 20ms

    toc = packet[0]
    config = toc >> 3
    frame_count_code = toc & 0x03
    if frame_count_code == 0:
        frame_count = 1
    elif frame_count_code in (1, 2):
        frame_count = 2
    else:
        # code 3: VBR/CBR with count in 2nd byte (6 bits)
        frame_count = (packet[1] & 0x3F) if len(packet) > 1 else 1
        if frame_count <= 0:
            frame_count = 1

    if config < 12:
        frame_dur_ms = [10, 20, 40, 60][config & 0x03]
    elif config < 16:
        frame_dur_ms = [10, 20][config & 0x01]
    else:
        frame_dur_ms = [2.5, 5, 10, 20][config & 0x03]

    return int(sample_rate * (frame_dur_ms / 1000.0) * frame_count)


def _build_ogg_page(
    packets: List[bytes],
    serial: int,
    seq: int,
    granule_pos: int,
    header_type: int,
) -> bytes:
    """构建单个 Ogg page（每个 packet 需 <= 255 字节，适合本场景）。"""
    lacing_vals = []
    payload = bytearray()
    for p in packets:
        remain = len(p)
        idx = 0
        while remain >= 255:
            lacing_vals.append(255)
            payload.extend(p[idx : idx + 255])
            idx += 255
            remain -= 255
        lacing_vals.append(remain)
        payload.extend(p[idx:])

    header = bytearray()
    header.extend(b"OggS")                       # capture pattern
    header.append(0)                             # version
    header.append(header_type & 0xFF)            # header type
    header.extend(struct.pack("<Q", granule_pos))
    header.extend(struct.pack("<I", serial))
    header.extend(struct.pack("<I", seq))
    header.extend(struct.pack("<I", 0))          # CRC placeholder
    header.append(len(lacing_vals))
    header.extend(bytes(lacing_vals))

    page = header + payload
    crc = _ogg_crc32(page)
    page[22:26] = struct.pack("<I", crc)
    return bytes(page)


def _build_ogg_crc_table() -> List[int]:
    poly = 0x04C11DB7
    table = []
    for i in range(256):
        r = i << 24
        for _ in range(8):
            if r & 0x80000000:
                r = ((r << 1) ^ poly) & 0xFFFFFFFF
            else:
                r = (r << 1) & 0xFFFFFFFF
        table.append(r)
    return table


_OGG_CRC_TABLE = _build_ogg_crc_table()


def _ogg_crc32(data: bytes) -> int:
    crc = 0
    for b in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ _OGG_CRC_TABLE[((crc >> 24) & 0xFF) ^ b]
    return crc


def _write_opus_ogg(opus_packets: List[bytes], out_ogg: str, channels: int = 2) -> None:
    """把 Opus RTP payload 序列写成 Ogg Opus 文件。"""
    serial = 0x13572468
    seq = 0
    granule = 0
    pages = []

    opus_head = bytearray()
    opus_head.extend(b"OpusHead")
    opus_head.append(1)                          # version
    opus_head.append(channels)                   # channel count
    opus_head.extend(struct.pack("<H", 0))       # pre-skip
    opus_head.extend(struct.pack("<I", 48000))   # input sample rate
    opus_head.extend(struct.pack("<H", 0))       # output gain
    opus_head.append(0)                          # channel mapping family
    pages.append(_build_ogg_page([bytes(opus_head)], serial, seq, 0, 0x02))  # BOS
    seq += 1

    opus_tags = b"OpusTags" + struct.pack("<I", 0) + struct.pack("<I", 0)
    pages.append(_build_ogg_page([opus_tags], serial, seq, 0, 0x00))
    seq += 1

    for pkt in opus_packets:
        granule += _opus_packet_duration_samples(pkt)
        pages.append(_build_ogg_page([pkt], serial, seq, granule, 0x00))
        seq += 1

    if pages:
        last = bytearray(pages[-1])
        last[5] = last[5] | 0x04                 # EOS
        last[22:26] = b"\x00\x00\x00\x00"
        crc = _ogg_crc32(last)
        last[22:26] = struct.pack("<I", crc)
        pages[-1] = bytes(last)

    with open(out_ogg, "wb") as f:
        for p in pages:
            f.write(p)


def extract_main_audio_payload(
    pcap_path: str,
    output_prefix: str,
    keylog_path: str,
    target_pt: Optional[int] = None,
    target_ssrc: Optional[int] = None,
) -> None:
    """从 SRTP 抓包中解出主流音频 PT 并仅输出 WAV。"""
    print(f"读取: {pcap_path}")
    packets = rdpcap(pcap_path)

    extractor = H264Extractor()
    keys = SRTPKey.parse_keylog(keylog_path)
    decryptors = []
    if keys.get("client"):
        decryptors.append(SRTPDecryptor(keys["client"]))
    if keys.get("server"):
        decryptors.append(SRTPDecryptor(keys["server"]))
    if not decryptors:
        raise RuntimeError("未从 keylog 中解析出 SRTP 密钥")
    extractor.set_decryptors(decryptors)

    stream_count: Dict[Tuple[int, int], int] = {}
    packets_cache: List[Tuple[int, int, int, bytes]] = []

    for pkt_info in extractor.iter_packets(packets):
        rtp = pkt_info.rtp
        if not rtp:
            continue
        udp_payload = pkt_info.udp_payload
        if len(udp_payload) <= rtp.header_len:
            continue
        payload = udp_payload[rtp.header_len:]
        if not payload:
            continue
        key = (rtp.ssrc, rtp.payload_type)
        stream_count[key] = stream_count.get(key, 0) + 1
        packets_cache.append((rtp.ssrc, rtp.payload_type, rtp.sequence_number, payload))

    if not stream_count:
        raise RuntimeError("未检测到可用 RTP/SRTP 音频包")

    if target_ssrc is not None and target_pt is not None:
        chosen_ssrc, chosen_pt = target_ssrc, target_pt
    elif target_ssrc is not None:
        candidates = [(pt, c) for (ssrc, pt), c in stream_count.items() if ssrc == target_ssrc]
        if not candidates:
            raise RuntimeError(f"未找到指定 SSRC: 0x{target_ssrc:08X}")
        chosen_pt = sorted(candidates, key=lambda x: -x[1])[0][0]
        chosen_ssrc = target_ssrc
    elif target_pt is not None:
        candidates = [(ssrc, c) for (ssrc, pt), c in stream_count.items() if pt == target_pt]
        if not candidates:
            raise RuntimeError(f"未找到指定 PT: {target_pt}")
        chosen_ssrc = sorted(candidates, key=lambda x: -x[1])[0][0]
        chosen_pt = target_pt
    else:
        chosen_ssrc, chosen_pt = sorted(stream_count.items(), key=lambda x: -x[1])[0][0]

    selected = [
        (seq, payload)
        for ssrc, pt, seq, payload in packets_cache
        if ssrc == chosen_ssrc and pt == chosen_pt
    ]
    selected.sort(key=lambda x: x[0])
    if not selected:
        raise RuntimeError("未匹配到目标流包")

    codec_hint = {111: "opus", 0: "pcmu", 8: "pcma"}.get(chosen_pt, "unknown")
    wav_path = f"{output_prefix}.wav"

    print("\n" + "=" * 60)
    print("音频主流提取完成（仅 WAV）")
    print("=" * 60)
    print(f"SSRC: 0x{chosen_ssrc:08X}")
    print(f"PT:   {chosen_pt} ({codec_hint})")
    print(f"包数: {len(selected):,}")

    # 对 G.711 额外输出可直接播放的 WAV
    if chosen_pt in (0, 8):
        pcm_data = bytearray()
        for _, payload in selected:
            if chosen_pt == 0:
                pcm_data.extend(audioop.ulaw2lin(payload, 2))
            else:
                pcm_data.extend(audioop.alaw2lin(payload, 2))
        wav_path = f"{output_prefix}.wav"
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(8000)
            wf.writeframes(bytes(pcm_data))
        print(f"输出: {wav_path} (可直接播放)")
    elif chosen_pt == 111:
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tf:
            temp_ogg = tf.name
        try:
            _write_opus_ogg([p for _, p in selected], temp_ogg, channels=2)
            cmd = [
                "ffmpeg",
                "-y",
                "-i",
                temp_ogg,
                "-vn",
                "-acodec",
                "pcm_s16le",
                "-ar",
                "48000",
                "-ac",
                "2",
                wav_path,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg 转 WAV 失败: {result.stderr[:400]}")
            print(f"输出: {wav_path} (Opus -> WAV)")
        finally:
            try:
                os.unlink(temp_ogg)
            except OSError:
                pass
    else:
        raise RuntimeError(f"暂不支持 PT={chosen_pt} 直接转 WAV")


def main():
    parser = argparse.ArgumentParser(
        description="WebRTC H.264 提取器（支持 SRTP 解密，自动检测视频流）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # ===== 提取视频 =====
  # 自动提取所有视频流（自动命名: video_0xSSSSSSSS.mp4）
  %(prog)s extract capture.pcapng -k webrtc_keys.log
  
  # 提取到指定目录
  %(prog)s extract capture.pcapng -k keys.log -d ./videos/
  
  # 只提取特定 SSRC
  %(prog)s extract capture.pcapng -k keys.log -s 0x67018aed
  
  # 提取并指定输出文件名
  %(prog)s extract capture.pcapng -k keys.log -s 0x67018aed -o myvideo.mp4
  
  # 先查看所有 SSRC
  %(prog)s extract capture.pcapng -l
  
  # ===== 解密 pcapng（供 Wireshark 分析） =====
  # 将 SRTP 解密为 RTP 明文 pcapng（保留所有包）
  %(prog)s decrypt capture.pcapng -k keys.log -o decrypted.pcapng
  
  # 只保留 RTP 视频流（过滤 TCP、STUN、DTLS 等）
  %(prog)s decrypt capture.pcapng -k keys.log -o rtp_only.pcapng --rtp-only
  
  # 只保留特定 SSRC 的 RTP 流
  %(prog)s decrypt capture.pcapng -k keys.log -o single_ssrc.pcapng --rtp-only -s 0x67018aed

  # ===== 提取主流音频（路径 B） =====
  # 自动选择主流 (SSRC, PT)，只导出 WAV
  %(prog)s extract-audio capture.pcapng -k native_combined_keys.log -o audio_main

  # 指定 PT/SSRC
  %(prog)s extract-audio capture.pcapng -k native_combined_keys.log --pt 111
        """,
    )

    # 添加子命令
    subparsers = parser.add_subparsers(dest="command", help="子命令", required=True)

    # extract 子命令（默认）
    extract_parser = subparsers.add_parser("extract", help="提取 H.264 视频（默认）")
    extract_parser.add_argument("input", help="输入 pcapng 文件")
    extract_parser.add_argument("-o", "--output", help="输出文件（指定 -s 时使用）")
    extract_parser.add_argument(
        "-d", "--output-dir", default=".", help="输出目录（自动提取时使用）"
    )
    extract_parser.add_argument("-k", "--keylog", help="SSLKEYLOGFILE 密钥文件")
    extract_parser.add_argument(
        "-s", "--ssrc", type=parse_ssrc, help="指定 SSRC（可选，支持十进制或十六进制如 0x12345678）"
    )
    extract_parser.add_argument("-f", "--framerate", type=int, default=30, help="帧率")
    extract_parser.add_argument("-l", "--list", action="store_true", help="只列出 SSRC")
    extract_parser.add_argument("-a", "--analyze", action="store_true", help="只分析")

    # decrypt 子命令
    decrypt_parser = subparsers.add_parser(
        "decrypt", help="将 SRTP 解密为 RTP 明文 pcapng"
    )
    decrypt_parser.add_argument("input", help="输入 SRTP pcapng 文件")
    decrypt_parser.add_argument(
        "-o", "--output", required=True, help="输出 RTP pcapng 文件"
    )
    decrypt_parser.add_argument(
        "-k", "--keylog", required=True, help="SSLKEYLOGFILE 密钥文件"
    )
    decrypt_parser.add_argument(
        "--rtp-only",
        action="store_true",
        help="只保留 RTP 视频流（过滤 TCP、STUN、DTLS 等）",
    )
    decrypt_parser.add_argument(
        "-s", "--ssrc", type=parse_ssrc, help="只保留指定 SSRC 的包（可选，支持十进制或十六进制）"
    )

    # extract-audio 子命令（路径 B）
    audio_parser = subparsers.add_parser(
        "extract-audio", help="路径B：从 SRTP 解密后提取主流音频载荷"
    )
    audio_parser.add_argument("input", help="输入 SRTP pcapng 文件")
    audio_parser.add_argument("-k", "--keylog", required=True, help="密钥文件（支持 SRTP/SRTP_SERVER 或 SRTP_KEYS）")
    audio_parser.add_argument("-o", "--output", required=True, help="输出前缀（不带扩展名）")
    audio_parser.add_argument("--pt", type=int, help="指定 payload type（可选）")
    audio_parser.add_argument("--ssrc", type=parse_ssrc, help="指定 SSRC（可选）")

    args = parser.parse_args()

    # 处理命令
    if args.command == "decrypt":
        if not os.path.exists(args.input):
            print(f"错误: 输入文件不存在: {args.input}")
            return

        try:
            stats = decrypt_pcapng(
                args.input,
                args.output,
                args.keylog,
                filter_rtp_only=args.rtp_only,
                target_ssrc=args.ssrc,
            )
            print(f"\n{'=' * 60}")
            print("解密完成")
            print(f"{'=' * 60}")
            print(f"总包数:     {stats['total']:,}")
            print(f"UDP 包:     {stats['udp']:,}")
            print(f"成功解密:   {stats['decrypted']:,}")
            
            # 显示双向解密统计
            if stats.get("decrypted_client", 0) > 0 or stats.get("decrypted_server", 0) > 0:
                print(f"  ├─ 客户端密钥: {stats.get('decrypted_client', 0):,}")
                print(f"  └─ 服务端密钥: {stats.get('decrypted_server', 0):,}")
            
            print(f"跳过(非SRTP): {stats['skipped']:,}")
            if stats["filtered"] > 0:
                print(f"过滤(非RTP): {stats['filtered']:,}")
            print(f"\n现在可以用 Wireshark 打开: {args.output}")
        except Exception as e:
            print(f"❌ 解密失败: {e}")
            import traceback

            traceback.print_exc()
        return

    if args.command == "extract-audio":
        if not os.path.exists(args.input):
            print(f"错误: 输入文件不存在: {args.input}")
            return
        try:
            extract_main_audio_payload(
                pcap_path=args.input,
                output_prefix=args.output,
                keylog_path=args.keylog,
                target_pt=args.pt,
                target_ssrc=args.ssrc,
            )
        except Exception as e:
            print(f"❌ 提取音频失败: {e}")
            import traceback
            traceback.print_exc()
        return

    # extract 命令
    if not os.path.exists(args.input):
        print(f"错误: 文件不存在: {args.input}")
        return

    if args.list:
        ssrcs = list_ssrcs(args.input, args.keylog)
        print(f"\n{'=' * 70}")
        print(f"{'SSRC':>12s} {'包数':>8s} {'PT':>6s} {'序列号范围':>20s}")
        print(f"{'=' * 70}")
        for ssrc, info in sorted(ssrcs.items(), key=lambda x: -x[1]["count"]):
            pt_str = ",".join(map(str, info["payload_types"]))
            seq_range = f"{info['seq_range'][0]} - {info['seq_range'][1]}"
            print(f"0x{ssrc:08X} {info['count']:>8,} {pt_str:>6s} {seq_range:>20s}")
        return

    # 如果指定了 SSRC，使用单流模式
    if args.ssrc:
        output = args.output or f"video_0x{args.ssrc:08X}.mp4"

        extractor = H264Extractor()
        frames, stats = extractor.extract_from_pcap(args.input, args.ssrc, args.keylog)

        print(f"\n{'=' * 60}")
        print("处理统计")
        print(f"{'=' * 60}")
        print(f"总包数:      {stats['total_packets']:>8,}")
        print(f"RTP 包:      {stats['rtp_packets']:>8,}")
        if stats["decrypted"] > 0:
            print(f"解密包:      {stats['decrypted']:>8,}")
            
            # 显示双向解密统计
            if stats.get("decrypted_client", 0) > 0 or stats.get("decrypted_server", 0) > 0:
                print(f"  ├─ 客户端密钥: {stats.get('decrypted_client', 0):,}")
                print(f"  └─ 服务端密钥: {stats.get('decrypted_server', 0):,}")
            
            # 显示解密错误统计
            if extractor.decryptors:
                # 合并所有解密器的错误统计
                total_errors = {
                    "total": 0,
                    "auth_fail": 0,
                    "replay_fail": 0,
                    "other": 0,
                }
                for decryptor in extractor.decryptors:
                    err_stats = decryptor.get_error_stats()
                    total_errors["total"] += err_stats["total"]
                    total_errors["auth_fail"] += err_stats["auth_fail"]
                    total_errors["replay_fail"] += err_stats["replay_fail"]
                    total_errors["other"] += err_stats["other"]
                
                if total_errors["total"] > 0:
                    print(f"  ├─ 解密失败: {total_errors['total']:,}")
                    if total_errors["auth_fail"] > 0:
                        print(f"  │  ├─ 认证失败: {total_errors['auth_fail']:,}")
                    if total_errors["replay_fail"] > 0:
                        print(f"  │  ├─ 重放保护失败: {total_errors['replay_fail']:,}")
                    if total_errors["other"] > 0:
                        print(f"  │  └─ 其他错误: {total_errors['other']:,}")
        print(f"H.264 包:    {stats['h264_packets']:>8,}")
        print(f"NAL 单元:    {stats['nal_units']:>8,}")
        print(f"提取帧数:    {stats['frames']:>8,}")

        if not frames:
            print("\n❌ 未找到 H.264 视频流")
            return

        extractor.analyze_frames(frames)

        if args.analyze:
            return

        print(f"\n{'=' * 60}")
        print("导出视频")
        print(f"{'=' * 60}")

        success = extractor.save_to_mp4(frames, output, args.framerate)

        if success:
            print(f"\n播放: ffplay {output}")

    else:
        # 自动模式：提取所有视频流
        video_streams = auto_extract_streams(
            args.input, args.keylog, args.framerate, args.output_dir
        )

        if not video_streams:
            print("\n❌ 未检测到 H.264 视频流")
            print("提示:")
            print("  1. 使用 -l 参数查看所有 SSRC")
            print("  2. 如果是加密流，使用 -k 指定密钥文件")
            return

        # 创建输出目录
        os.makedirs(args.output_dir, exist_ok=True)

        print(f"\n{'=' * 60}")
        print("开始提取视频流...")
        print(f"{'=' * 60}")

        extracted = []
        for i, (ssrc, count) in enumerate(video_streams):
            output_path = os.path.join(args.output_dir, f"video_0x{ssrc:08X}.mp4")

            print(f"\n[{i + 1}/{len(video_streams)}] 提取 SSRC 0x{ssrc:08X}...")

            extractor = H264Extractor()
            frames, stats = extractor.extract_from_pcap(args.input, ssrc, args.keylog)

            if frames:
                extractor.analyze_frames(frames)
                success = extractor.save_to_mp4(frames, output_path, args.framerate)
                if success:
                    extracted.append(output_path)
            else:
                print(f"  ⚠️ 未找到有效帧")

        print(f"\n{'=' * 60}")
        print(f"提取完成！共 {len(extracted)} 个视频")
        print(f"{'=' * 60}")
        for path in extracted:
            print(f"  {path}")


if __name__ == "__main__":
    main()
