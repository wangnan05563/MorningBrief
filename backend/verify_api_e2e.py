"""端到端验证脚本：playlogs/progress + users/stats 接口。

为什么写这个脚本：
- 单元测试已验证 PlayService 层逻辑，但未覆盖 HTTP 路由层 + Pydantic 校验层
- 需要端到端确认：duration=0 + listened_seconds 组合能通过 Field(ge=0) 校验
- 需要确认 stats 接口返回的累计值确实随上报累加

执行方式：
    cd backend
    python verify_api_e2e.py
"""
import asyncio
import sys
from pathlib import Path

# 确保能 import app.*
sys.path.insert(0, str(Path(__file__).parent))

import httpx
from sqlalchemy import select, text

from app.config import get_settings
from app.core.security import create_access_token
from app.database import AsyncSessionLocal
from app.models import User, Episode, EpisodeStatus


BASE_URL = "http://127.0.0.1:8000"


async def find_test_user_and_episode() -> tuple[int, int]:
    """从数据库找一个已存在的用户和一个已发布的 episode。

    为什么不用固定 ID：开发环境数据可能被清空，硬编码 ID 会失败；
    动态查询保证脚本可在任何数据状态下运行。
    """
    async with AsyncSessionLocal() as db:
        # 找一个有 openid 的用户（C 端用户）
        user_result = await db.execute(
            select(User.id).where(User.openid.is_not(None)).limit(1)
        )
        user_id = user_result.scalar_one_or_none()
        if user_id is None:
            # 没有真实用户时取任意一个 user
            user_result = await db.execute(select(User.id).limit(1))
            user_id = user_result.scalar_one_or_none()
        if user_id is None:
            raise RuntimeError("数据库无 user 记录，无法测试")

        # 找一个已发布的 episode
        ep_result = await db.execute(
            select(Episode.id)
            .where(Episode.status == EpisodeStatus.published.value)
            .limit(1)
        )
        episode_id = ep_result.scalar_one_or_none()
        if episode_id is None:
            raise RuntimeError("数据库无 published episode，无法测试")

        return user_id, episode_id


async def get_user_total_listen_duration(user_id: int) -> int:
    """直接从数据库读取 User.total_listen_duration（用于交叉验证 stats 接口）。"""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User.total_listen_duration).where(User.id == user_id)
        )
        return int(result.scalar_one_or_none() or 0)


async def main():
    print("=" * 70)
    print("端到端验证：playlogs/progress + users/stats")
    print("=" * 70)

    # 1. 找测试数据
    user_id, episode_id = await find_test_user_and_episode()
    print(f"\n[1] 测试数据: user_id={user_id}, episode_id={episode_id}")

    # 2. 生成测试 token（直接用项目内部函数，绕过微信 wx.login）
    token, jti, expires_in = create_access_token(str(user_id), token_type="user")
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[2] 生成 token: jti={jti}, expires_in={expires_in}s")

    # 3. 调用 stats 接口获取基线值
    async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=10) as client:
        resp = await client.get("/api/v1/users/stats")
        assert resp.status_code == 200, f"stats 接口异常: {resp.status_code} {resp.text}"
        before_data = resp.json()["data"]
        before_total = before_data["total_listen_seconds"]
        print(f"[3] 上报前 stats: total_listen_seconds={before_total}, "
              f"episodes={before_data['total_listen_episodes']}, "
              f"completed={before_data['completed_episodes']}")

        # 数据库交叉验证
        db_before = await get_user_total_listen_duration(user_id)
        assert db_before == before_total, (
            f"stats 接口与数据库不一致: stats={before_total}, db={db_before}"
        )
        print(f"    数据库交叉验证通过: User.total_listen_duration={db_before}")

        # 4. 调用 progress 接口，上报 duration=0 + listened_seconds=30
        # 为什么 duration=0：模拟 BackgroundAudioManager HLS 流式加载下 duration 延迟填充场景
        # 为什么 listened_seconds=30：模拟前端 onTimeUpdate 增量计算
        payload = {
            "episode_id": episode_id,
            "position": 30,
            "duration": 0,
            "completed": False,
            "listened_seconds": 30,
        }
        resp = await client.post("/api/v1/playlogs/progress", json=payload)
        assert resp.status_code == 200, (
            f"progress 接口拒绝 duration=0 + listened_seconds: "
            f"{resp.status_code} {resp.text}"
        )
        print(f"[4] progress 上报成功: duration=0, listened_seconds=30 → 200 OK")

        # 5. 再次调用 stats 接口，验证累计值增加 30
        resp = await client.get("/api/v1/users/stats")
        after_data = resp.json()["data"]
        after_total = after_data["total_listen_seconds"]
        print(f"[5] 上报后 stats: total_listen_seconds={after_total}")

        delta = after_total - before_total
        assert delta == 30, (
            f"累计值增量异常: expected=30, actual={delta} "
            f"(before={before_total}, after={after_total})"
        )
        print(f"    验证通过：累计时长正确增加 {delta} 秒")

        # 6. 再次上报 listened_seconds=45，验证连续累加
        payload2 = {
            "episode_id": episode_id,
            "position": 75,
            "duration": 600,
            "completed": False,
            "listened_seconds": 45,
        }
        resp = await client.post("/api/v1/playlogs/progress", json=payload2)
        assert resp.status_code == 200, f"progress 接口第二次上报失败: {resp.text}"

        resp = await client.get("/api/v1/users/stats")
        final_total = resp.json()["data"]["total_listen_seconds"]
        delta2 = final_total - after_total
        assert delta2 == 45, (
            f"第二次累计增量异常: expected=45, actual={delta2}"
        )
        print(f"[6] 第二次上报验证通过：累计时长再次增加 {delta2} 秒")

        # 7. 数据库最终交叉验证
        db_final = await get_user_total_listen_duration(user_id)
        assert db_final == final_total, (
            f"最终数据库与接口不一致: stats={final_total}, db={db_final}"
        )
        print(f"[7] 最终数据库交叉验证通过: User.total_listen_duration={db_final}")

    print("\n" + "=" * 70)
    print("全部验证通过 ✓")
    print("=" * 70)
    print("\n验证摘要：")
    print(f"  - /api/v1/playlogs/progress 接受 duration=0 + listened_seconds 组合")
    print(f"  - /api/v1/users/stats 返回累计收听时长正确")
    print(f"  - 前后端字段契约一致：listened_seconds → User.total_listen_duration 累加")
    print(f"  - 测试用户 ID: {user_id}（累计时长 {before_total} → {final_total} 秒）")


if __name__ == "__main__":
    asyncio.run(main())
