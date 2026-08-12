"""小程序多频道适配（FR-MC-07 跨类型搜索 + FR-MC-04/05 课程进度）端到端冒烟。

安全模式（沿用既定 DB 隔离）：
- 拷贝真实 news.db → 临时文件，monkeypatch app.paths.resolve_db_path 指向它，原库零污染。
- FastAPI TestClient（带 lifespan，启动时跑 FTS5 迁移 + 触发器）进程内跑真实 app。
- dependency_overrides[get_current_user] 免真实 JWT，固定 user_id=1。
- /episodes/search 为公开接口（无鉴权依赖），直接打。
- 种子数据在 lifespan 之后写入：episode_fts 触发器已就绪，插入即被 FTS5 索引，
  使 FTS5 路径而非 LIKE 降级路径命中，验证更接近真实路径。

验证点：
1. GET /api/v1/courses/{cid}/progress → total/learned/percent/last_chapter_id/last_position 正确
2. GET /api/v1/episodes/search?keyword=...&channel_type=course → 仅返回 course/audiobook 类 + 带 channel_type/channel_id/channel_name
3. GET ...&channel_type=news（同一课程关键词）→ 被类型过滤排除，total=0
4. GET ...（不带 channel_type）→ 返回课程结果（全类型）
5. GET ...&channel_type=news（资讯关键词）→ 返回 news 类结果
6. GET /api/v1/courses/{不存在id}/progress → 业务错（code!=0），不 500
7. R1 修正：audiobook 频道在 channel_type=course 筛选下应被命中（聚合组含 audiobook）
8. R2 修正：GET /api/v1/courses/{news频道id}/progress → 404（非课程类频道被拒）
"""
import os
import shutil
import sys
import tempfile
import asyncio
import os as _os
from datetime import date
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import app.paths as paths  # noqa: E402

BACKEND = Path(__file__).resolve().parent.parent
REAL_DB = BACKEND / "data" / "news.db"
# 每进程唯一临时库，避免并发运行/残留进程复用同一路径导致 SQLite 锁竞争（曾致 17min 挂死）
TMP_DB = Path(tempfile.gettempdir()) / f"smoke_mc_news_{_os.getpid()}.db"

for suf in ("", "-wal", "-shm"):
    src = Path(str(REAL_DB) + suf)
    dst = Path(str(TMP_DB) + suf)
    if dst.exists():
        dst.unlink()
    if src.exists():
        shutil.copy(src, dst)

paths.resolve_db_path = lambda: TMP_DB  # type: ignore[assignment]

from app.main import app  # noqa: E402
from app.core.auth import UserPayload, get_current_user  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.models import Channel, Episode, PlayProgress  # noqa: E402
from app.models.episode import EpisodeStatus  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402


async def _user():
    return UserPayload(user_id=1, jti="x", token_type="user", exp=0)


app.dependency_overrides[get_current_user] = _user

results = []


def check(name, cond, extra=""):
    results.append((name, bool(cond)))
    print(("PASS " if cond else "FAIL ") + name + (f"  >> {extra}" if extra else ""))


async def seed():
    async with AsyncSessionLocal() as s:
        # 课程频道（course）
        ch = Channel(
            name="冒烟课程频道MC", channel_type="course", type_label="课程",
            is_active=1, enable_ad=0,
        )
        s.add(ch)
        await s.flush()
        cid = ch.id

        ep_ids = []
        for i in range(3):
            ep = Episode(
                date=date(2026, 8, 11), channel_id=cid,
                title=f"SMOKECOURSE2026 章节{i + 1}", duration=300,
                audio_url="x.mp3", status=EpisodeStatus.published.value,
            )
            s.add(ep)
            await s.flush()
            ep_ids.append(ep.id)

        # 用户 1 在 ep_ids[0] 已完播（completed=1，position=duration）
        pp = PlayProgress(
            user_id=1, episode_id=ep_ids[0], position=300, duration=300, completed=1,
        )
        s.add(pp)

        # 资讯频道（news）+ 一条可搜到的资讯节目
        nc = Channel(name="冒烟资讯频道MC", channel_type="news", type_label="资讯", is_active=1)
        s.add(nc)
        await s.flush()
        ncid = nc.id
        nep = Episode(
            date=date(2026, 8, 11), channel_id=ncid,
            title="SMOKENEWS2026 早间头条", duration=200,
            audio_url="y.mp3", status=EpisodeStatus.published.value,
        )
        s.add(nep)
        await s.flush()
        nep_id = nep.id

        # 有声书频道（audiobook）+ 一条可搜节目，验证 R1 聚合组
        ac = Channel(name="冒烟有声书MC", channel_type="audiobook", type_label="有声读物", is_active=1)
        s.add(ac)
        await s.flush()
        acid = ac.id
        aep = Episode(
            date=date(2026, 8, 11), channel_id=acid,
            title="SMOKEAUDIO2026 书名第一章", duration=400,
            audio_url="z.mp3", status=EpisodeStatus.published.value,
        )
        s.add(aep)
        await s.flush()
        aep_id = aep.id

        await s.commit()
        return cid, ncid, ep_ids, nep_id, acid, aep_id


with TestClient(app) as c:
    cid, ncid, ep_ids, nep_id, acid, aep_id = asyncio.run(seed())

    # --- 1. 课程进度聚合 ---
    r = c.get(f"/api/v1/courses/{cid}/progress")
    check("C1 course progress 200", r.status_code == 200, f"code={r.status_code} {r.text[:160]}")
    d = (r.json().get("data") or {}) if r.status_code == 200 else {}
    check("C2 total=3(已发布章节数)", d.get("total") == 3, f"total={d.get('total')}")
    check("C3 learned=1(完播1章)", d.get("learned") == 1, f"learned={d.get('learned')}")
    check("C4 percent=33", d.get("percent") == 33, f"percent={d.get('percent')}")
    check("C5 last_chapter_id=首章", d.get("last_chapter_id") == ep_ids[0], f"last={d.get('last_chapter_id')}")
    check("C6 last_position=300", d.get("last_position") == 300, f"pos={d.get('last_position')}")

    # --- 2. 跨类型搜索：course ---
    r = c.get("/api/v1/episodes/search?keyword=SMOKECOURSE2026&channel_type=course")
    check("S1 course search 200", r.status_code == 200, f"code={r.status_code} {r.text[:160]}")
    d = (r.json().get("data") or {}) if r.status_code == 200 else {}
    lst = d.get("list") or []
    check("S2 course 命中>=1", d.get("total", 0) >= 1, f"total={d.get('total')}")
    check("S3 全部为 course 且本频道",
          all(it.get("channel_type") == "course" and it.get("channel_id") == cid for it in lst),
          str([(it.get("channel_type"), it.get("channel_id")) for it in lst]))
    check("S4 带 channel_name", all(it.get("channel_name") for it in lst),
          str([it.get("channel_name") for it in lst]))

    # --- 3. 同关键词按 news 过滤应被排除 ---
    r = c.get("/api/v1/episodes/search?keyword=SMOKECOURSE2026&channel_type=news")
    d = (r.json().get("data") or {}) if r.status_code == 200 else {}
    check("S5 news 过滤课程关键词→total=0", d.get("total", -1) == 0, f"total={d.get('total')}")

    # --- 4. 不带 channel_type 返回课程结果（全类型）---
    r = c.get("/api/v1/episodes/search?keyword=SMOKECOURSE2026")
    d = (r.json().get("data") or {}) if r.status_code == 200 else {}
    lst = d.get("list") or []
    check("S6 无类型约束命中>=1", d.get("total", 0) >= 1, f"total={d.get('total')}")
    check("S7 无约束结果为 course 类", all(it.get("channel_type") == "course" for it in lst),
          str([it.get("channel_type") for it in lst]))

    # --- 5. news 关键词 + news 类型 ---
    r = c.get("/api/v1/episodes/search?keyword=SMOKENEWS2026&channel_type=news")
    d = (r.json().get("data") or {}) if r.status_code == 200 else {}
    lst = d.get("list") or []
    check("S8 news 命中>=1", d.get("total", 0) >= 1, f"total={d.get('total')}")
    check("S9 结果 channel_type=news", all(it.get("channel_type") == "news" for it in lst),
          str([it.get("channel_type") for it in lst]))

    # --- 6. 不存在频道 → 业务错非 500 ---
    # NotFoundError 约定映射 HTTP 404 + body.code=404（见 app.core.exceptions），
    # 与 BizError 默认 200 不同，这里只要「非 500、明确业务错」即符合预期。
    r = c.get("/api/v1/courses/999999/progress")
    ok = r.status_code in (200, 404) and r.json().get("code") not in (0, None) and r.status_code != 500
    check("N1 不存在频道→业务错(非500)", ok, f"code={r.status_code} body={r.text[:120]}")

    # --- 7. R1 修正：audiobook 在 course 筛选下应被命中（聚合组）---
    r = c.get("/api/v1/episodes/search?keyword=SMOKEAUDIO2026&channel_type=course")
    check("R1A audio-by-course search 200", r.status_code == 200, f"code={r.status_code} {r.text[:160]}")
    d = (r.json().get("data") or {}) if r.status_code == 200 else {}
    lst = d.get("list") or []
    check("R1B audiobook 命中>=1", d.get("total", 0) >= 1, f"total={d.get('total')}")
    check("R1C 命中项 type=audiobook 且本有声书频道",
          all(it.get("channel_type") == "audiobook" and it.get("channel_id") == acid for it in lst),
          str([(it.get("channel_type"), it.get("channel_id")) for it in lst]))
    check("R1D 命中项带 channel_name", all(it.get("channel_name") for it in lst),
          str([it.get("channel_name") for it in lst]))

    # 反向：audiobook 关键词按 news 过滤应被排除
    r = c.get("/api/v1/episodes/search?keyword=SMOKEAUDIO2026&channel_type=news")
    d = (r.json().get("data") or {}) if r.status_code == 200 else {}
    check("R1E news 过滤有声书关键词→total=0", d.get("total", -1) == 0, f"total={d.get('total')}")

    # --- 8. R2 修正：news 频道调用课程进度接口应 404（非课程类被拒）---
    r = c.get(f"/api/v1/courses/{ncid}/progress")
    ok = r.status_code in (200, 404) and r.json().get("code") not in (0, None)
    check("R2 news 频道→404(非课程类被拒)", ok, f"code={r.status_code} body={r.text[:120]}")

print("\n=== MC SEARCH/COURSES SMOKE SUMMARY ===")
fails = [n for n, ok in results if not ok]
for n, ok in results:
    print(("  [OK] " if ok else "  [XX] ") + n)
print(f"total={len(results)} pass={len(results)-len(fails)} fail={len(fails)}")
sys.exit(1 if fails else 0)
