"""单本讲书分集编排（T00626 P1）。

背景：得到式「每日听书」要求**一本书一条音频**，大部头拆「上/中/下」且衔接自然
（规范见 `docs/每日听书频道专有流程规范.md` §3.3）。此前讲书模板里的
`{book_title}` `{part_label}` `{part_brief}` `{part_link}` `{next_episode_hint}`
只能人工填写，本模块按**素材（章节）序列 + 改写字数估算**自动编排。

规则（与规范文档一致）：
- 估算改写总字数 ≤ 8000 → 单集；≤ 24000 → 上/下两篇；> 24000 → 上/中/下三篇；
- 分篇采用**均衡贪心切分**（每篇估算字数尽量接近总字数/篇数，边界落在整章上）；
- 衔接语：首篇无衔接；中篇「回顾上一集」；末篇（多篇时）「接着上一集的问题讲完」；
- 篇尾预告：非末篇给下一集提示，末篇给「明天打开下一本书」收束。

设计要点：
- **纯函数、无 IO**：输入素材 dict 列表，输出编排结果，便于单测与复用；
- 不改库、不改素材标题：编排结果由改写阶段按 `material_id` 注入模板槽位，
  避免污染素材数据（下次重跑可重新编排）。
"""
from __future__ import annotations

import re

# 分篇阈值（估算改写字数）：≤t1 单集；≤t2 两篇；否则三篇
DEFAULT_THRESHOLDS: tuple[int, int] = (8000, 24000)
PART_LABELS: dict[int, list[str]] = {1: ["单集"], 2: ["上篇", "下篇"], 3: ["上篇", "中篇", "下篇"]}

# 单章改写字数估算区间（章过短按 600 下限、过长按单段上限的 1.25 倍）
_MIN_CHAPTER_WORDS = 600
_CHAPTER_SCALE = 0.85

# 书名前缀（书源名）与章节分隔符
_SOURCE_PREFIX = re.compile(r"^\s*(维基文库|Gutendex|豆瓣读书|书格|Kindle伴侣|得到|微信读书)\s*[-—·:：]\s*")
_CHAPTER_SEP = re.compile(r"[/·|｜]")

_LINK_MIDDLE = "这一集开头，请先用 30 秒回顾上一集讲到哪里，再接着往下讲。"
_LINK_LAST = "上一集我们留下了一个问题，这一集接着把它讲完。"
_HINT_LAST = "这本书我们就讲完了。明天同一时间，我们打开下一本书。"


def extract_book_title(source: str | None = None, title: str | None = None) -> str:
    """从素材 source / title 提取书名。

    示例：'我只知道人是什么' → 同名；'维基文库-論語' → '論語'；
    '論語/學而第一' → '論語'；'Gutendex-唐詩三百首' → '唐詩三百首'。
    """
    for raw in (source, title):
        if not raw:
            continue
        s = _SOURCE_PREFIX.sub("", str(raw).strip())
        s = _CHAPTER_SEP.split(s)[0].strip()
        if s:
            return s
    return ""


def estimate_chapter_words(content: str | None, words_per_segment: int = 1800) -> int:
    """估算单章改写后字数：原文字数 × 系数，并夹在 [600, words_per_segment×1.25]。"""
    n = len(content or "")
    est = int(n * _CHAPTER_SCALE)
    upper = int(words_per_segment * 1.25) if words_per_segment else 2250
    return max(_MIN_CHAPTER_WORDS, min(est, max(_MIN_CHAPTER_WORDS, upper)))


def plan_book_parts(
    materials: list[dict],
    words_per_segment: int = 1800,
    thresholds: tuple[int, int] = DEFAULT_THRESHOLDS,
) -> dict:
    """编排单本书的分篇方案。

    Args:
        materials: 章节素材列表（顺序即讲述顺序），每项含 id/title/content/source
        words_per_segment: 单段目标字数（用于上限估算）
        thresholds: (t1, t2) 分篇阈值

    Returns:
        {
          "book_title": str,
          "parts": int,
          "total_words_estimate": int,
          "assignments": {material_id: {book_title, part_label, part_index, part_total,
                                        part_brief, part_link, next_episode_hint}},
          "part_chapters": [[material_id, ...], ...],
        }
    """
    chapters = [m for m in (materials or []) if (m.get("content") or "").strip()]
    if not chapters:
        return {"book_title": "", "parts": 0, "total_words_estimate": 0,
                "assignments": {}, "part_chapters": []}

    ests = [estimate_chapter_words(m.get("content"), words_per_segment) for m in chapters]
    total = sum(ests)
    t1, t2 = thresholds
    parts = 1 if total <= t1 else (2 if total <= t2 else 3)
    labels = PART_LABELS[parts]

    # 均衡贪心切分：累计达到 total/parts 且剩余章节足够填满后续篇时切篇
    target = total / parts
    buckets: list[list[int]] = [[] for _ in range(parts)]
    bucket_idx = 0
    acc = 0
    for i, est in enumerate(ests):
        remaining_chapters = len(chapters) - i
        remaining_parts = parts - bucket_idx - 1
        if (
            bucket_idx < parts - 1
            and acc >= target
            and remaining_chapters > remaining_parts  # 至少给后续每篇留一章
        ):
            bucket_idx += 1
            acc = 0
        buckets[bucket_idx].append(i)
        acc += est

    book_title = extract_book_title(chapters[0].get("source"), chapters[0].get("title"))
    assignments: dict = {}
    for pi, bucket in enumerate(buckets):
        if not bucket:
            continue
        label = labels[pi]
        is_last = pi == parts - 1
        titles = [str(chapters[i].get("title") or "").strip() for i in bucket]
        brief = "本篇覆盖：" + "、".join(t for t in titles[:3] if t) + ("等章节。" if len(titles) > 3 else "。")
        # 衔接语：首篇无；三篇的中篇用回顾语；末篇（多篇）用"回应上一集问题"语
        if pi == 0 or parts == 1:
            link = ""
        elif is_last:
            link = _LINK_LAST
        else:
            link = _LINK_MIDDLE
        next_hint = _HINT_LAST if is_last else f"下一集我们接着讲《{book_title}》的{labels[pi + 1]}。"
        for ci, i in enumerate(bucket, 1):
            assignments[chapters[i].get("id")] = {
                "book_title": book_title,
                "part_label": label,
                "part_index": ci,
                "part_total": len(bucket),
                "part_brief": brief,
                "part_link": link,
                "next_episode_hint": next_hint,
            }

    return {
        "book_title": book_title,
        "parts": parts,
        "total_words_estimate": total,
        "assignments": assignments,
        "part_chapters": [[chapters[i].get("id") for i in b] for b in buckets],
    }
