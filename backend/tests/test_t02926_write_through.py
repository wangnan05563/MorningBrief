"""T02926 写入贯通探针：模型声明的每个字段，提交后必须真的落到对应的库列上。

判据不是返回码——PUT 返回 200 而列值没变，用户看到的仍是一句「已保存」，
这正是 M16 / C56 那一家族的体质。所以这里逐字段提交、逐字段回读库。

字段清单来自运行时反射（`extract_backend_models.py` 的同一套口径），
不是测试里抄的名单：模型加字段而这里没覆盖 → 参数化数量对不上直接红。
"""
import json
from datetime import date, datetime, time
from pathlib import Path

import pytest
from pydantic import BaseModel
from sqlalchemy import select

from app.models import Channel, Material
from app.models.ad_material import AdMaterial
from app.models.ad_placement import AdPlacement
from app.routers.admin.ads import MaterialCreateRequest, PlacementCreateRequest
from app.routers.admin.channels import ChannelUpdateRequest
from app.routers.admin.materials import MaterialUpdateRequest

REGISTRY = Path(__file__).resolve().parents[2] / "scripts/field_audit/out/field_registry.json"

# 每个字段给一个「和种子值明显不同」的探针值；None 表示该字段由服务端派生，不参与写入贯通
SAMPLE = {
    "name": "贯通探针名", "description": "贯通探针描述", "category": "probe-cat",
    "content": "贯通探针正文", "source": "贯通探针书名", "title": "贯通探针标题",
    "summary": "贯通探针摘要", "status": "selected", "media_type": "audio",
    "media_url": "https://example.com/probe.mp3", "media_thumb_url": "https://example.com/probe.jpg",
    "url": "https://example.com/probe", "file_url": "https://example.com/probe.mp3",
    "duration": 33, "cover_url": "https://example.com/cover.png", "icon_url": "https://example.com/icon.png",
    "keywords": "探针,贯通", "type_label": "探针标签", "channel_type": "audiobook",
    "selection_strategy": "manual", "rewrite_template": "probe_tpl",
    "intro_prompt": "探针片头", "outro_prompt": "探针片尾", "constraint_prompt": "探针约束",
    "bgm_path": "data/bgm/probe.mp3", "bgm_gap_mode": "bridge", "schedule_time": "07:30",
    "bgm_volume": 0.5, "min_duration_sec": 300, "material_lookback_days": 5,
    "segment_gap_sec": 3, "display_order": 9,
    "rss_sources": "https://example.com/rss", "book_rss_sources": "https://example.com/brss",
    "manual_material_ids": "1,2", "auto_generate_prompts": 1,
    "disclaimer_level": "normal",
    "enabled": 0, "is_active": 0, "enable_ad": 0, "enable_thinking_question": 0,
    "inherit_bgm_gap": 0, "inherit_segment_gap": 0,
}
INT_FIELDS = {"display_order", "bgm_volume", "segment_gap_sec", "material_lookback_days",
              "min_duration_sec", "duration", "position", "material_id", "enabled"}
DATE_FIELDS = {"start_date", "end_date"}
TIME_FIELDS = {"schedule_time"}


def sample_value(model: type[BaseModel], field: str):
    info = model.model_fields[field]
    ann = str(info.annotation)
    if field in SAMPLE:
        return SAMPLE[field]
    if "date" in ann.lower() and "datetime" not in ann.lower():
        return date(2026, 1, 2).isoformat()
    if "datetime" in ann.lower():
        return datetime(2026, 1, 2, 3, 4).isoformat()
    if "int" in ann.lower() or "float" in ann.lower():
        return 7
    if "bool" in ann.lower():
        return True
    return f"探针值-{field}"


async def _seed(db_session):
    m = Material(source="原书名", source_type="list", title="原标题", content="原正文",
                 url="https://example.com/orig", category="orig", status="pending", channel_id=77)
    c = Channel(name="原频道", description="原描述", rss_sources="https://example.com/orig-rss")
    am = AdMaterial(name="原素材", description="原描述", file_url="https://example.com/orig.mp3", duration=12)
    db_session.add_all([m, c, am])
    await db_session.commit()
    return m.id, c.id, am.id


async def _read(db_session, model, obj_id):
    res = await db_session.execute(select(model).where(model.id == obj_id))
    return res.scalar_one()


def _put(client, token, url, payload):
    return client.put(url, json=payload, headers={"Authorization": f"Bearer {token['token']}"})


def _declared(model):
    """与登记表同一份事实源：模型字段清单必须和 JSON 里一致"""
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    for row in reg["rows"]:
        if row["model"] == model.__name__:
            return sorted(row["declared"]), row
    return None, None


@pytest.mark.parametrize("model,endpoint,url_tpl,orm", [
    (MaterialUpdateRequest, "PUT /materials/*", "/admin/api/v1/materials/{id}", Material),
    (ChannelUpdateRequest, "PUT /channels/*", "/admin/api/v1/channels/{id}", Channel),
])
async def test_every_declared_field_reaches_the_column(db_session, client, admin_token, model, endpoint, url_tpl, orm):
    obj_id, _, _ = await _seed(db_session)
    fields, row = _declared(model)
    assert row is not None, f"登记表里没有 {model.__name__}，生成器与运行时反射脱节"
    assert fields == sorted(model.model_fields), f"{model.__name__} 字段清单与登记表不一致"

    not_in_column = set(row["diffs"]["modelNotInColumn"])
    broken = []
    rejected = []
    for field in fields:
        if field in not_in_column:
            continue  # 非列字段（控制/派生）由另一条用例负责
        value = sample_value(model, field)
        resp = _put(client, admin_token, url_tpl.format(id=obj_id), {field: value})
        body = resp.json()
        if resp.status_code != 200 or body.get("code") not in (0, 200):
            rejected.append(f"{field}: code={body.get('code')} msg={body.get('message')}")
            continue
        obj = await _read(db_session, orm, obj_id)
        actual = getattr(obj, field, "<无此属性>")
        if not _same(actual, field, value):
            broken.append(f"{field}: 返回成功但库里是 {actual!r}（提交 {value!r}）")
    print(f"\n{endpoint} 被校验拦下的字段（诚实拒绝，不算缺陷）：{rejected}")
    assert not broken, f"{endpoint} 声明字段未写入库：\n" + "\n".join(broken)


def _same(actual, field, value):
    if actual == value:
        return True
    if field in DATE_FIELDS and isinstance(value, str):
        return actual == date.fromisoformat(value)
    if field in TIME_FIELDS and isinstance(value, str):
        # TIME 列把 "07:30" 规范成 "07:30:00"，是同一时刻而不是写丢
        return time.fromisoformat(str(actual)) == time.fromisoformat(value)
    try:
        return float(actual) == float(value)  # 列类型可能是 float/Decimal
    except (TypeError, ValueError):
        return False
