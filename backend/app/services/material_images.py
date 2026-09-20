"""素材图片聚合助手（T00766 采集图片 → T00809 审核详情展示）。

采集器把文章全量图片 URL 存进 `material.images_json`（JSON 数组，封面在前、正文顺序）。
节目脚本接口与审核详情都需要「按素材顺序聚合、去重、保序」的同一套规则，抽为共享助手，
避免两处实现各自演化后口径漂移（谁排前面、要不要去重、脏数据怎么处理）。

用法：
    imgs = aggregate_material_images(materials)   # materials 需按期望展示顺序传入
    page_imgs = imgs[:9]                          # 截断由调用方决定（各处上限可能不同）
"""
import json
from typing import Iterable, Optional


def parse_material_images(raw: Optional[str]) -> list[str]:
    """解析 `material.images_json`。

    脏数据（非法 JSON、非数组、空串）一律按「无图片」处理，不抛异常——
    详情页不能因为一条坏数据整页打不开。
    """
    if not raw or not isinstance(raw, str):
        return []
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(data, list):
        return []
    return [u.strip() for u in data if isinstance(u, str) and u.strip()]


def aggregate_material_images(materials: Iterable) -> list[str]:
    """按素材给定顺序聚合图片：去重且保持首次出现顺序。

    调用方负责素材顺序（分段顺序 → 段内 material_ids 顺序），本函数只做解析与去重。
    """
    images: list[str] = []
    seen: set[str] = set()
    for mat in materials:
        if mat is None:
            continue
        for url in parse_material_images(getattr(mat, "images_json", None)):
            if url not in seen:
                seen.add(url)
                images.append(url)
    return images
