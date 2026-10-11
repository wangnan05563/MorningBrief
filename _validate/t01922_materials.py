"""T01922 真机测试物料生成 + 码流级取证（全程离线，不触发付费链路）。

为什么这脚本存在：本环境无 Android/iOS 设备通道（adb 不存在），真机起播无法自证；
但「档位到底产出了什么码流」是可以客观取证的——24kHz MP3 究竟是不是 MPEG-2 Layer III(LSF)、
容器时长与帧算时长是否一致、有没有 Xing/ID3v2 这类影响起播与进度条的结构。
把这些先钉死，真机同学只需按包播放并对照预期值。

素材源：_validate/t01845_samples/ep100.mp3（本项目已发布成品，128kbps@44100，只读 GET 拉取）。
输出：_validate/t01922_pack/  —— 6 个待播文件 + 1 个 HLS 分片包 + facts.json

用法：backend/.venv/Scripts/python.exe _validate/t01922_materials.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FFMPEG = os.path.join(ROOT, "backend", "ffmpeg", "bin", "ffmpeg.exe")
FFPROBE = os.path.join(ROOT, "backend", "ffmpeg", "bin", "ffprobe.exe")
SRC = os.path.join(HERE, "t01845_samples", "ep100.mp3")
PACK = os.path.join(HERE, "t01922_pack")
SLICE_START, SLICE_SEC = 30.0, 60.0

# (文件名, 编码器, 码率, 采样率, 说明)
TARGETS = [
    ("A_baseline_128k_44100.mp3", "libmp3lame", "128k", 44100, "线上已发布口径（基线）"),
    ("B_standard_64k_32000.mp3", "libmp3lame", "64k", 32000, "当前默认档 standard"),
    ("C_quality_96k_44100.mp3", "libmp3lame", "96k", 44100, "高音质档 quality"),
    ("D_lean_48k_32000.mp3", "libmp3lame", "48k", 32000, "省流档 lean（音质存疑，见 T01871 A 段）"),
    ("E_lsf_64k_24000.mp3", "libmp3lame", "64k", 24000, "24kHz 候选：预期为 MPEG-2 Layer III(LSF)"),
    ("F_aac_64k_32000.m4a", "aac", "64k", 32000, "AAC 档（HLS 同编码器，容器 m4a）"),
]

SR_TABLE = {
    "mpeg1": {0: 44100, 1: 48000, 2: 32000},
    "mpeg2": {0: 22050, 1: 24000, 2: 16000},
}
SPF = {  # samples per frame
    ("mpeg1", "layer3"): 1152,
    ("mpeg2", "layer3"): 576,
}


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, errors="replace")


def decode_slice():
    """基线文件用「直接切片不重编」保留线上原码流（-c copy 会按帧对齐，够准）。"""
    os.makedirs(PACK, exist_ok=True)
    wav = os.path.join(PACK, "_slice_src.wav")
    r = run([FFMPEG, "-y", "-ss", str(SLICE_START), "-t", str(SLICE_SEC), "-i", SRC,
             "-c:a", "pcm_s16le", "-ac", "1", wav])
    assert r.returncode == 0, r.stderr[-400:]
    return wav


def encode(wav, name, codec, bitrate, sr, out):
    cmd = [FFMPEG, "-y", "-i", wav, "-c:a", codec, "-b:a", bitrate, "-ar", str(sr), "-ac", "1"]
    if codec == "aac":
        cmd += ["-movflags", "+faststart"]
    cmd.append(out)
    r = run(cmd)
    assert r.returncode == 0, f"{name}: {r.stderr[-400:]}"


def build_hls(wav, sr, bitrate):
    """镜像生产 build_hls_cmd 的口径：PCM → AAC + HLS 分片（-f hls）。"""
    d = os.path.join(PACK, "G_hls_aac_64k_32000")
    os.makedirs(d, exist_ok=True)
    cmd = [FFMPEG, "-y", "-i", wav, "-c:a", "aac", "-b:a", bitrate, "-ar", str(sr), "-ac", "1",
           "-f", "hls", "-hls_time", "10", "-hls_list_size", "0",
           "-hls_segment_type", "mpegts",
           os.path.join(d, "playlist.m3u8")]
    r = run(cmd)
    assert r.returncode == 0, r.stderr[-400:]
    return d


def parse_mp3_frames(path):
    """手写帧头解析：不依赖 ffprobe 的推测口径，直接读第一帧与总帧数。"""
    data = open(path, "rb").read()
    i = 0
    id3v2 = 0
    if data[:3] == b"ID3":
        size = ((data[6] & 0x7F) << 21 | (data[7] & 0x7F) << 14
                | (data[8] & 0x7F) << 7 | (data[9] & 0x7F))
        id3v2 = size + 10
        i = id3v2
    first = None
    frames = 0
    xing = False
    total_bytes = len(data)
    while i + 4 <= total_bytes:
        if data[i] == 0xFF and (data[i + 1] & 0xE0) == 0xE0:
            ver_bits = (data[i + 1] >> 3) & 0x03      # 3=MPEG1, 2=MPEG2, 0=MPEG2.5
            layer_bits = (data[i + 1] >> 1) & 0x03    # 1=Layer III
            if ver_bits in (3, 2) and layer_bits == 1:
                ver = "mpeg1" if ver_bits == 3 else "mpeg2"
                sr_idx = (data[i + 2] >> 2) & 0x03
                br_idx = (data[i + 2] >> 4) & 0x0F
                ch_mode = (data[i + 3] >> 6) & 0x03
                padding = (data[i + 2] >> 1) & 0x01
                sr = SR_TABLE[ver].get(sr_idx)
                if sr is None:
                    i += 1
                    continue
                if first is None:
                    first = {
                        "mpeg_version": ver,
                        "layer": "III",
                        "lsf": ver == "mpeg2",
                        "bitrate_index": br_idx,
                        "sample_rate_index": sr_idx,
                        "sample_rate": sr,
                        "channel_mode": ["stereo", "joint", "dual", "mono"][ch_mode],
                    }
                    tag = data[i + 4: i + 20]
                    xing = b"Xing" in tag or b"Info" in tag
                frames += 1
                spf = SPF[(ver, "layer3")]
                bitrate_map = {
                    "mpeg1": [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0],
                    "mpeg2": [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0],
                }
                br = bitrate_map[ver][br_idx]
                frame_len = int(spf / 8 * br * 1000 / sr) + padding
                if frame_len <= 0:
                    break
                i += frame_len
                continue
        i += 1
    spf0 = SPF[(first["mpeg_version"], "layer3")] if first else 0
    frame_dur = frames * spf0 / first["sample_rate"] if first and spf0 else 0
    return {
        "id3v2_bytes": id3v2,
        "frame_count": frames,
        "frame_header": first,
        "xing_or_info_tag": xing,
        "duration_by_frames_sec": round(frame_dur, 3),
    }


def probe(path):
    r = run([FFPROBE, "-v", "quiet", "-print_format", "json",
             "-show_format", "-show_streams", path])
    j = json.loads(r.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    fmt = j.get("format") or {}
    return {
        "codec": st.get("codec_name"),
        "profile": st.get("profile"),
        "sample_rate": st.get("sample_rate"),
        "channels": st.get("channels"),
        "bit_rate_fmt": fmt.get("bit_rate"),
        "duration_fmt": fmt.get("duration"),
        "format_name": fmt.get("format_name"),
        "size_bytes": int(fmt.get("size") or 0),
        "tags": {k: v for k, v in (fmt.get("tags") or {}).items()},
    }


def main():
    facts = {"source": SRC, "slice": {"start": SLICE_START, "sec": SLICE_SEC}, "files": []}
    wav = decode_slice()
    # A0：线上原码流的逐帧拷贝（-c copy，不重编）——A 档是从解码 PCM 再编 128k，属第二代，
    # 真机要对照的「线上现状」必须用这份原码流。
    a0 = os.path.join(PACK, "A0_published_copy.mp3")
    r = run([FFMPEG, "-y", "-ss", str(SLICE_START), "-t", str(SLICE_SEC), "-i", SRC,
             "-c", "copy", a0])
    assert r.returncode == 0, r.stderr[-400:]
    rec = {"file": os.path.basename(a0), "note": "线上已发布成品原码流逐帧拷贝（-c copy，零重编）",
           "requested": "copy from published ep100.mp3"}
    rec["ffprobe"] = probe(a0)
    rec["mp3_frames"] = parse_mp3_frames(a0)
    facts["files"].insert(0, rec)
    for name, codec, bitrate, sr, note in TARGETS:
        out = os.path.join(PACK, name)
        encode(wav, name, codec, bitrate, sr, out)
        rec = {"file": name, "note": note, "requested": f"{codec} {bitrate} @{sr}"}
        rec["ffprobe"] = probe(out)
        if name.endswith(".mp3"):
            rec["mp3_frames"] = parse_mp3_frames(out)
        facts["files"].append(rec)
        print(f"[生成] {name}")

    hls_dir = build_hls(wav, 32000, "64k")
    segs = sorted(f for f in os.listdir(hls_dir) if f.endswith(".ts"))
    m3u8 = open(os.path.join(hls_dir, "playlist.m3u8"), encoding="utf-8").read()
    facts["hls"] = {
        "dir": os.path.relpath(hls_dir, HERE).replace("\\", "/"),
        "segments": len(segs),
        "playlist_head": m3u8.splitlines()[:6],
        "targetduration_line": next((l for l in m3u8.splitlines() if "TARGETDURATION" in l), ""),
        "first_ts_probe": probe(os.path.join(hls_dir, segs[0])),
        "note": "生产口径：build_hls_cmd 由 PCM 时间线直接编 AAC（T01870），本包按同参数复现",
    }
    os.remove(wav)
    out_path = os.path.join(HERE, "t01922_pack_facts.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)
    print(f"[取证落盘] {out_path}")


if __name__ == "__main__":
    main()
