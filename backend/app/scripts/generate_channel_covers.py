"""为各频道生成移动端适配的预制封面图（T00731）。

用 agnes-image-2.5-flash 按频道主题逐一生成 3:4 封面，Pillow 压缩至 ≤200KB 的 JPG，
命名 `channel_{频道id}.jpg` 存入 /channel-assets 静态目录；`--assign` 时自动把
`cover_url` 设为对应静态 URL（仅当频道当前无封面，避免覆盖人工配置）。

前置：backend/.env 配置 IMAGE_API_KEY / IMAGE_API_BASE_URL / IMAGE_API_MODEL；
      apihub.agnes-ai.com 需网络可达（2026-09-17 实测该域名 DNS 不通，需换网络/代理后执行）。

用法（backend 目录）：
    python -m app.scripts.generate_channel_covers            # 预览频道清单
    python -m app.scripts.generate_channel_covers --run      # 生成全部缺封面的频道
    python -m app.scripts.generate_channel_covers --run --only 11,12
    python -m app.scripts.generate_channel_covers --run --assign
"""
from __future__ import annotations

import argparse
import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import select  # noqa: E402

from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Channel  # noqa: E402
from app.paths import resolve_channel_asset_dir  # noqa: E402
from app.services.image_gen_service import ImageGenError, generate_image  # noqa: E402

MAX_KB = 200


def compress_to_jpg(raw: bytes, max_kb: int = MAX_KB) -> bytes:
    """缩放到 768 宽并按质量递减压缩至 ≤max_kb（Pillow）。"""
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if img.width > 768:
        img = img.resize((768, int(img.height * 768 / img.width)))
    for quality in (88, 80, 72, 64, 55, 45):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        if buf.tell() <= max_kb * 1024:
            return buf.getvalue()
    return buf.getvalue()


def build_prompt(name: str, description: str, channel_type: str) -> str:
    type_scene = {
        "news": "daily news and current affairs atmosphere",
        "audiobook": "cozy storytelling and audiobook listening atmosphere",
        "course": "structured learning and knowledge course atmosphere",
    }
    scene = type_scene.get(channel_type, "podcast atmosphere")
    desc = (description or "")[:120]
    return (
        f"Vertical 3:4 mobile cover art for an audio channel named '{name}'. "
        f"Theme: {desc or name}. {scene}. "
        "Soft gradient background in mint blue and deep navy palette, subtle abstract shapes, "
        "clean modern composition, no text, no watermark, no logo."
    )


def _ensure_icon_column() -> None:
    """幂等确保 channel.icon_url 列存在（脚本直连库，服务未启动过时迁移尚未跑）。"""
    import sqlite3

    from app.paths import resolve_db_path

    conn = sqlite3.connect(str(resolve_db_path()))
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(channel)")}
        if "icon_url" not in cols:
            conn.execute("ALTER TABLE channel ADD COLUMN icon_url TEXT")
            conn.commit()
            print("[covers] channel 表已补 icon_url 列")
    finally:
        conn.close()


async def main_async(run: bool, assign: bool, only: list[int] | None) -> int:
    _ensure_icon_column()
    async with AsyncSessionLocal() as db:
        stmt = select(Channel).order_by(Channel.id.asc())
        if only:
            stmt = stmt.where(Channel.id.in_(only))
        channels = (await db.execute(stmt)).scalars().all()
        if not channels:
            print("[covers] 无频道")
            return 0

        out_dir = resolve_channel_asset_dir()
        print(f"[covers] 输出目录：{out_dir}")
        failed: list[str] = []
        for ch in channels:
            filename = f"channel_{ch.id}.jpg"
            dest = out_dir / filename
            if dest.exists():
                print(f"  跳过 频道 {ch.id}《{ch.name}》：{filename} 已存在")
                continue
            if not run:
                print(f"  [dry-run] 频道 {ch.id}《{ch.name}》：将生成主题封面（{ch.channel_type}）")
                continue
            prompt = build_prompt(ch.name, ch.description, ch.channel_type or "")
            try:
                raw = generate_image(prompt, size="1K", ratio="3:4")
            except ImageGenError as e:
                print(f"  [fail] 频道 {ch.id}《{ch.name}》：{e}")
                failed.append(ch.name)
                continue
            jpg = compress_to_jpg(raw)
            dest.write_bytes(jpg)
            print(f"  [ok] 频道 {ch.id}《{ch.name}》→ {filename}（{len(jpg) // 1024}KB）")

            if assign and not ch.cover_url:
                ch.cover_url = f"/channel-assets/{filename}"
                print("    已自动设为频道封面（原 cover_url 为空）")
        if assign:
            await db.commit()
        if failed:
            print(f"[covers] {len(failed)} 个频道生成失败：{failed}")
            return 1
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="为频道生成预制封面图（T00731）")
    parser.add_argument("--run", action="store_true", help="实际生成（默认 dry-run）")
    parser.add_argument("--assign", action="store_true", help="生成后自动设为频道 cover_url（仅空封面）")
    parser.add_argument("--only", type=str, default="", help="仅处理指定频道 id，逗号分隔")
    args = parser.parse_args()
    only = [int(x) for x in args.only.split(",") if x.strip()] or None
    return asyncio.run(main_async(args.run, args.assign, only))


if __name__ == "__main__":
    raise SystemExit(main())
