"""B 端稿件查询路由测试。

覆盖 GET /admin/api/v1/scripts?workflow_id= 的取数规则：
- rewrite 重跑会追加新 script 行且旧行保留（追加式历史），
  接口必须返回 id 最大的一条，否则 LIMIT 1 无 ORDER BY 按 rowid
  升序返回最旧稿件，新稿与质量审核报告在前端不可见（T01712 回归）。
- 无稿件时 404。
"""
from datetime import date

from app.models.script import Script


async def _add_script(session, workflow_id: str, script_id: int, quality_report=None):
    # AsyncSession 的 add/commit 均为异步 API，同步调用只会创建未 await 的 coroutine，
    # 数据实际不落库（本文件首个版本即栽在这里，表现为接口 404）
    script = Script(
        id=script_id,
        workflow_id=workflow_id,
        episode_date=date(2026, 10, 9),
        full_text="正文",
        segments=[{"seq": 1, "content": "正文"}],
        total_words=2,
        status="draft",
        quality_report=quality_report,
    )
    session.add(script)
    await session.commit()
    return script


async def test_get_script_by_workflow_returns_latest_row(client, db_session, admin_token):
    """同 workflow 存在多份稿件时必须返回 id 最大的一条。"""
    await _add_script(db_session, "wf-multi", 1)
    new = await _add_script(
        db_session, "wf-multi", 2,
        quality_report={"passed": False, "issue_count": 1, "alert_count": 1,
                        "issues": [{"seq": 1, "issue_type": "fact_anchor",
                                     "severity": "high", "evidence": "x",
                                     "suggestion": "y"}]},
    )

    resp = client.get(
        "/admin/api/v1/scripts",
        params={"workflow_id": "wf-multi"},
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    if resp.status_code != 200:
        print("DEBUG resp:", resp.text)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == new.id
    # 质量审核报告必须随新稿返回（旧稿无报告）
    assert data["quality_report"]["passed"] is False
    assert data["quality_report"]["issue_count"] == 1


async def test_get_script_by_workflow_404_when_missing(client, db_session, admin_token):
    """workflow 无稿件时返回 404。"""
    resp = client.get(
        "/admin/api/v1/scripts",
        params={"workflow_id": "wf-empty"},
        headers={"Authorization": f"Bearer {admin_token['token']}"},
    )
    assert resp.status_code == 404
