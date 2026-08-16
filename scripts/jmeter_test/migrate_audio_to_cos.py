"""历史音频迁移到 COS。

扫描所有 audio_url 以 /audio/ 开头的 episode：
1. 读取本地音频文件
2. 上传到 COS（key = episodes/YYYYMMDD/xxx.mp3）
3. 更新数据库 audio_url 为完整 COS URL

幂等：已经是 http 开头的 episode 跳过。
"""
import asyncio
import os
import sqlite3
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from app.config import get_settings
from app.paths import resolve_data_dir
from app.workflow.tts.uploader import is_cos_configured, upload_to_cos


async def migrate():
    print("=" * 60)
    print("历史音频迁移到 COS")
    print("=" * 60)

    if not is_cos_configured():
        print("[FAIL] COS 未配置，请先在 .env 配置 COS 凭证")
        return 1

    settings = get_settings()
    db_path = BACKEND_DIR / "data" / "news.db"
    audio_dir = resolve_data_dir() / "audio_cache"

    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT id, audio_url FROM episode "
            "WHERE audio_url LIKE '/audio/%' ORDER BY id"
        )
        rows = cur.fetchall()
        print(f"\n待迁移: {len(rows)} 条")

        success = 0
        skipped = 0
        failed = 0

        for eid, audio_url in rows:
            # /audio/episodes/20260727/xxx.mp3 → episodes/20260727/xxx.mp3
            cos_key = audio_url.replace("/audio/", "", 1)
            local_path = audio_dir / cos_key

            if not local_path.exists():
                print(f"  [{eid}] SKIP 文件不存在: {local_path.name}")
                skipped += 1
                continue

            try:
                file_size = local_path.stat().st_size
                with open(local_path, "rb") as f:
                    data = f.read()

                new_url = await upload_to_cos(data, cos_key)
                conn.execute(
                    "UPDATE episode SET audio_url = ? WHERE id = ?",
                    (new_url, eid),
                )
                conn.commit()
                success += 1
                print(f"  [{eid}] OK {file_size//1024}KB → {new_url[:80]}...")
            except Exception as e:
                failed += 1
                print(f"  [{eid}] FAIL {e}")

        print(f"\n{'=' * 60}")
        print(f"迁移完成: 成功 {success}, 跳过 {skipped}, 失败 {failed}")
        print(f"{'=' * 60}")
        return 0 if failed == 0 else 1
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(migrate()))
