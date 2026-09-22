"""为各频道生成 1:1 正方形图标（T00731 遗留处理）。

用 agnes-image-2.5-flash 按频道主题生成方形图标，Pillow 缩放为 512×512 PNG，
命名 `channel_{频道id}_icon.png` 存入 /channel-assets 静态目录；
--assign 时自动把 icon_url 设为对应静态 URL（仅当频道当前无 icon，避免覆盖人工配置）。

为什么主题用英文常量而非常读 description：T00731 复盘确认，提示词若直接带中文
频道名/描述，模型会照排成中文文字（视觉水印）。这里为每个频道提供独立英文主题词，
并在提示词前置强否定（Absolutely textless, no Chinese characters/kanji/letters）。

用法（backend 目录）：
    python -m app.scripts.generate_channel_icons              # 预览
    python -m app.scripts.generate_channel_icons --run        # 生成全部缺 icon 的频道
    python -m app.scripts.generate_channel_icons --run --only 1,2
    python -m app.scripts.generate_channel_icons --run --assign
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

# 频道 id → 英文主题词（离线生成用；与 T00731 封面主题一一对应）
ICON_THEMES: dict[int, str] = {
    1: "microchip and circuit board, technology news",
    2: "bar chart and golden coin, financial news",
    3: "running track and ball, sports news",
    4: "clapperboard and sound wave, entertainment news",
    5: "globe with linked dots, world news",
    6: "city skyline, livelihood news",
    7: "green leaf and heartbeat pulse, health news",
    8: "open book and graduation cap, education news",
    9: "game controller, gaming news",
    10: "hourglass and stone pillars, history",
    11: "headphones and open book, audiobook",
    12: "neural network and brain, AI general knowledge",
}


def build_icon_prompt(channel_id: int, themes: str) -> str:
    """构造方形图标的生成提示词：扁平无文字、低饱和商务蓝、主题可识别。"""
    return (
        f"Flat minimalist 1:1 app icon for an audio platform, central symbolic: {themes}. "
        "Low-saturation business blue palette (#2F5674 #3F6C8F #6C93AF #EDF3F7), "
        "clean flat vector, large negative space, rounded friendly feel, no gradient noise. "
        "Absolutely textless: no Chinese characters, no kanji, no letters, "
        "no watermark, no logo, no border, no badge."
    )


def compress_to_png(raw: bytes, size: int = 512) -> bytes:
    """缩放到方形 size×size 并编码为 PNG（图标宜用 PNG 保留简洁边缘）。"""
    from PIL import Image

    img = Image.open(io.BytesIO(raw)).convert("RGB")
    img = img.resize((size, size), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


async def main_async(run: bool, assign: bool, only: list[int] | None) -> int:
    async with AsyncSessionLocal() as db:
        stmt = select(Channel).order_by(Channel.id.asc())
        if only:
            stmt = stmt.where(Channel.id.in_(only))
        channels = (await db.execute(stmt)).scalars().all()
        if not channels:
            print("[icons] 无频道")
            return 0

        out_dir = resolve_channel_asset_dir()
        failed: list[str] = []
        done = 0
        for ch in channels:
            filename = f"channel_{ch.id}_icon.png"
            dest = out_dir / filename
            if dest.exists():
                print(f"  跳过 频道 {ch.id}《{ch.name}》：{filename} 已存在")
                continue
            theme = ICON_THEMES.get(ch.id) or (ch.description or ch.name)[:60]
            if not run:
                print(f"  [dry-run] 频道 {ch.id}《{ch.name}》→ {filename}")
                continue
            try:
                raw = generate_image(build_icon_prompt(ch.id, theme), size="1K", ratio="1:1")
            except ImageGenError as e:
                print(f"  [fail] 频道 {ch.id}《{ch.name}》：{e}")
                failed.append(ch.name)
                continue
            png = compress_to_png(raw)
            dest.write_bytes(png)
            print(f"  [ok] 频道 {ch.id}《{ch.name}》→ {filename}（{len(png) // 1024}KB）")
            done += 1

            if assign and not ch.icon_url:
                ch.icon_url = f"/channel-assets/{filename}"
                print(f"    已设为频道图标（原 icon_url 为空）")
        if assign:
            await db.commit()
        print(f"[icons] 完成 {done} 张；{len(failed)} 个失败：{failed}")
        return 0 if not failed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="为频道生成 1:1 预制图标（T00731 遗留）")
    parser.add_argument("--run", action="store_true", help="实际生成（默认 dry-run）")
    parser.add_argument("--assign", action="store_true", help="生成后自动设为频道 icon_url（仅空 icon）")
    parser.add_argument("--only", type=str, default="", help="仅处理指定频道 id，逗号分隔")
    args = parser.parse_args()
    only = [int(x) for x in args.only.split(",") if x.strip()] or None
    return asyncio.run(main_async(args.run, args.assign, only))


if __name__ == "__main__":
    raise SystemExit(main())