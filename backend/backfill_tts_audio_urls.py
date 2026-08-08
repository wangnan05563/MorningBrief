"""回填重建历史 script.segments[].audio_url（COS / 本地两种来源）。

背景：
- 旧版 TTS 流程（_persist_segment_audio_urls 合入前）未把每段 COS audio_url 写回
  script.segments，导致 COS 模式下「语音合成 · TTS 片段」详情面板恒为空
  （本地模式靠目录列表兜底，不受影响）。
- 已合入修复（synthesizer._persist_segment_audio_urls）只覆盖后续运行；
  历史已 success 的工作流分段无 audio_url，需一次性按存储前缀重建。

重建策略：
- 仅处理 status='success' 的工作流（TTS 已完成的才有音频落盘）。
- 优先本地：data/audio_cache/tts/{workflow_id}/ 若存在且有 .mp3 → 按
  {seq}_{uuid}.mp3 文件名解析 seq 重建 /audio/... 静态 URL。
- 否则若 COS 已配置 → list_objects 前缀 tts/{workflow_id}/，按文件名解析 seq 重建 CDN URL。
- 仅填充缺失/空的 audio_url，已存在的保留不动（非破坏性）。
- 先 --dry-run 统计，再实际执行；实际执行前自动备份 news.db。

使用：
  python backfill_tts_audio_urls.py --dry-run    # 仅预览
  python backfill_tts_audio_urls.py              # 实际执行（先自动备份）
"""
import argparse
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# 添加 backend 目录到 sys.path 以便导入 app 模块
sys.path.insert(0, str(Path(__file__).parent))

from app.config import get_settings
from app.workflow.tts.uploader import is_cos_configured


def _local_audio_root() -> Path:
    """本地音频缓存根目录，与 uploader._local_root 保持一致。"""
    try:
        from app.paths import resolve_data_dir
        return Path(resolve_data_dir()) / "audio_cache"
    except Exception:
        return Path("data/audio_cache")


def _build_cos_url(settings, key: str) -> str:
    """拼 COS 对象完整 URL（与 uploader._upload_sync 一致）。"""
    if settings.COS_CDN_DOMAIN:
        base = settings.COS_CDN_DOMAIN.rstrip("/")
    else:
        base = (
            f"https://{settings.COS_BUCKET}.cos.{settings.COS_REGION}.myqcloud.com"
        )
    return f"{base}/{key}"


def _parse_seq_from_filename(fname: str):
    """从 {seq}_{uuid}.mp3 文件名解析 seq（int）。失败返回 None。"""
    stem = fname.rsplit(".", 1)[0]  # 去掉扩展名
    seq_part = stem.split("_", 1)[0]  # 取首段
    try:
        return int(seq_part)
    except (ValueError, TypeError):
        return None


def _local_seq_to_url(workflow_id: str) -> dict:
    """扫描本地 tts 目录，返回 {seq: '/audio/tts/{wf}/{file}'}。无文件返回 {}。"""
    local_dir = _local_audio_root() / "tts" / workflow_id
    if not local_dir.is_dir():
        return {}
    mapping = {}
    for f in local_dir.iterdir():
        if not f.is_file() or not f.name.lower().endswith(".mp3"):
            continue
        seq = _parse_seq_from_filename(f.name)
        if seq is None:
            continue
        key = f"tts/{workflow_id}/{f.name}"
        mapping[seq] = f"/audio/{key}"
    return mapping


def _cos_seq_to_url(settings, workflow_id: str) -> dict:
    """列出 COS 前缀 tts/{workflow_id}/ 下对象，返回 {seq: cos_url}。"""
    try:
        from qcloud_cos import CosConfig, CosS3Client
    except ImportError:
        print("[WARN] qcloud_cos 未安装，跳过 COS 来源重建")
        return {}

    config = CosConfig(
        Region=settings.COS_REGION,
        SecretId=settings.COS_SECRET_ID,
        SecretKey=settings.COS_SECRET_KEY,
    )
    client = CosS3Client(config)
    prefix = f"tts/{workflow_id}/"
    mapping = {}
    marker = ""
    while True:
        try:
            resp = client.list_objects(
                Bucket=settings.COS_BUCKET,
                Prefix=prefix,
                Marker=marker,
                MaxKeys=1000,
            )
        except Exception as e:  # COS 列举失败（网络/鉴权/限流）不应中断整批回填
            print(f"[WARN] COS 列举 tts/{workflow_id}/ 失败，跳过该工作流: {e}")
            return {}
        for item in resp.get("Contents", []):
            key = item.get("Key", "")
            fname = key[len(prefix):]  # 去掉前缀后的文件名
            if not fname or not fname.lower().endswith(".mp3"):
                continue
            seq = _parse_seq_from_filename(fname)
            if seq is None:
                continue
            mapping[seq] = _build_cos_url(settings, key)
        if resp.get("IsTruncated") == "true":
            # list_objects v1 无 Delimiter 时不返回 NextMarker，回退到末位 Key 续传
            contents = resp.get("Contents", [])
            marker = resp.get("NextMarker") or (contents[-1]["Key"] if contents else "")
            if not marker:
                break
        else:
            break
    return mapping


def _resolve_audio_map(settings, workflow_id: str) -> tuple[dict, str]:
    """返回 (seq->url 映射, 来源说明)。优先本地，否则 COS。"""
    local_map = _local_seq_to_url(workflow_id)
    if local_map:
        return local_map, f"本地 {len(local_map)} 段"
    if is_cos_configured():
        cos_map = _cos_seq_to_url(settings, workflow_id)
        if cos_map:
            return cos_map, f"COS {len(cos_map)} 段"
        return {}, "COS 已配置但无对象"
    return {}, "无本地文件且 COS 未配置"


def main():
    parser = argparse.ArgumentParser(description="回填重建历史 script.segments[].audio_url")
    parser.add_argument("--dry-run", action="store_true", help="仅预览影响范围，不执行更新")
    parser.add_argument("--db", default="data/news.db", help="SQLite 数据库路径")
    args = parser.parse_args()

    db_path = Path(__file__).parent / args.db
    if not db_path.exists():
        print(f"[ERROR] 数据库不存在: {db_path}")
        sys.exit(1)

    settings = get_settings()

    print(f"数据库: {db_path}")
    print(f"模式: {'dry-run（仅预览）' if args.dry_run else '实际执行'}")
    print("=" * 60)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # 1. 取出所有 success 工作流 id 集合（只有这些才有完整音频落盘）
    success_ids = {
        r["id"]
        for r in cur.execute(
            "SELECT id FROM workflow WHERE status='success'"
        ).fetchall()
    }
    print(f"status=success 工作流数: {len(success_ids)}")

    # 2. 取出这些工作流关联的 script（按 workflow_id 匹配）
    rows = cur.execute(
        "SELECT id, workflow_id, segments FROM script ORDER BY id"
    ).fetchall()

    affected = []  # [{"script_id","workflow_id","segments_after","filled"}]
    scanned_scripts = 0
    total_filled = 0
    source_counts = {}

    for r in rows:
        wf_id = r["workflow_id"]
        if wf_id not in success_ids:
            continue  # 非 success 工作流的音频不一定完整，跳过
        segments = r["segments"] or "[]"
        try:
            segs = json.loads(segments)
        except json.JSONDecodeError:
            continue
        if not isinstance(segs, list) or not segs:
            continue

        # 是否已有缺失 audio_url 的分段（先判断，避免无谓打 COS）
        has_missing = any(
            isinstance(seg, dict)
            and (not seg.get("audio_url"))
            and isinstance(seg.get("seq"), int)
            for seg in segs
        )
        if not has_missing:
            continue

        scanned_scripts += 1
        seq_map, source = _resolve_audio_map(settings, wf_id)
        if source not in source_counts:
            source_counts[source] = 0
        source_counts[source] += 1

        if not seq_map:
            # 该工作流无可用音频来源，跳过（不报错，避免噪音）
            continue

        filled = 0
        changed = False
        for seg in segs:
            if not isinstance(seg, dict):
                continue
            seq = seg.get("seq")
            if not seg.get("audio_url") and isinstance(seq, int) and seq in seq_map:
                seg["audio_url"] = seq_map[seq]
                filled += 1
                changed = True

        if changed:
            affected.append({
                "script_id": r["id"],
                "workflow_id": wf_id,
                "segments_after": json.dumps(segs, ensure_ascii=False),
                "filled": filled,
                "source": source,
            })
            total_filled += filled

    print(f"含缺失 audio_url 的 success-script 扫描数: {scanned_scripts}")
    print(f"音频来源分布: {source_counts}")
    print(f"可回填 script 数: {len(affected)}")
    print(f"可回填分段总数: {total_filled}")
    print()

    if not affected:
        print("[OK] 无需回填，所有 success 分段均已含 audio_url 或有对应音频来源")
        conn.close()
        return

    print("===== 待回填样本（前 8 个）=====")
    for a in affected[:8]:
        print(f"  script_id={a['script_id']:<5} wf={a['workflow_id']:<16} "
              f"填充 {a['filled']} 段 来源={a['source']}")

    if args.dry_run:
        print("\n[dry-run] 未实际更新数据库。去掉 --dry-run 参数以执行回填。")
        conn.close()
        return

    # 实际执行前自动备份
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_suffix("").with_name(
        f"news.db.bak_{ts}"
    )
    shutil.copy2(str(db_path), str(backup_path))
    print(f"\n[备份] 已备份数据库到: {backup_path}")

    print("===== 开始执行回填 =====")
    updated = 0
    for a in affected:
        cur.execute(
            "UPDATE script SET segments=? WHERE id=?",
            (a["segments_after"], a["script_id"]),
        )
        updated += 1
    conn.commit()
    conn.close()
    print(f"\n[完成] 共回填 {updated} 份文稿，填充 {total_filled} 个分段 audio_url")


if __name__ == "__main__":
    main()
