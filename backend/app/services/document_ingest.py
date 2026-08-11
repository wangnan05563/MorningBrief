"""文档解析服务（MVP 输入适配器，T1）。

把专业资料（PDF/Word/Markdown/网页/纯文本）解析为有序章节列表，供后续
rewrite → tts → stitch 流水线消费。

MVP 范围（零依赖、可独立验证）：
- 支持 .txt / .md / .markdown：用标准库 + 正则切分章节，无需第三方库。
- 超长章节按句/段自动切块，保持顺序。
- 重型格式（.pdf / .docx / .html）预留扩展点：检测缺失依赖时抛出
  UnsupportedFormatError 并提示安装对应库，避免静默失败。

后续扩展：在 _PARSERS 注册表里补充 PyMuPDF / python-docx / BeautifulSoup 适配器，
parse_document 的调度逻辑无需改动（开闭原则）。
"""
from dataclasses import dataclass
import hashlib
import os
import re
from typing import Callable

from loguru import logger


class DocumentIngestError(Exception):
    """文档解析基类异常。"""


class UnsupportedFormatError(DocumentIngestError):
    """格式不支持或依赖库缺失。"""


@dataclass
class Chapter:
    """解析后的单章/节。seq 为大纲顺序（从 1 递增）。"""
    seq: int
    title: str
    content: str


# 零依赖即可解析的格式
_TEXT_EXT = {".txt", ".text"}
_MD_EXT = {".md", ".markdown", ".mdown", ".mkd"}
# 需第三方库的重型格式（MVP 暂不支持，给出明确提示）
_HEAVY_EXT = {".pdf", ".doc", ".docx", ".html", ".htm"}

# 单章节内容上限：超过则按句/段切块，避免单段 TTS 超时或超长
_MAX_CHAPTER_CHARS = 1200
# 过短章节合并阈值：小于此值且与上一篇合并（避免碎片）
_MIN_MERGE_CHARS = 30

# 重型格式 → 所需依赖与安装提示（扩展点，MVP 仅用于报错）
_HEAVY_HINTS = {
    ".pdf": "PyMuPDF (pip install pymupdf)",
    ".doc": "python-docx (pip install python-docx)",
    ".docx": "python-docx (pip install python-docx)",
    ".html": "beautifulsoup4 (pip install beautifulsoup4)",
}


def compute_content_hash(content: str) -> str:
    """计算正文内容哈希（去重键）。

    用于 list 类型素材的 (source_type, dedup_key) 去重，避免与 rss 的 url 唯一键耦合。
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _decode(raw: bytes) -> str:
    """尽力解码为 UTF-8 文本，失败降级忽略错误字符。"""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="ignore")


def _chunk_long(chapters: list[Chapter], max_chars: int = _MAX_CHAPTER_CHARS) -> list[Chapter]:
    """将超长章节按句/段边界切块，保持顺序并重新编号。"""
    out: list[Chapter] = []
    for ch in chapters:
        if len(ch.content) <= max_chars:
            out.append(ch)
            continue
        # 以句号/感叹/问号/换行作为切分锚点，尽量不在句中切断
        parts = re.split(r"(?<=[。！？\.\n])", ch.content)
        buf = ""
        sub = 0
        for p in parts:
            if buf and len(buf) + len(p) > max_chars:
                sub += 1
                title = f"{ch.title}（{sub}）" if sub > 1 else ch.title
                out.append(Chapter(seq=0, title=title, content=buf.strip()))
                buf = p
            else:
                buf += p
        if buf.strip():
            sub += 1
            title = f"{ch.title}（{sub}）" if sub > 1 else ch.title
            out.append(Chapter(seq=0, title=title, content=buf.strip()))
    # 统一重编号
    for i, c in enumerate(out, 1):
        c.seq = i
    return out


def _split_text_to_chapters(text: str, default_title: str = "正文") -> list[Chapter]:
    """通用文本切分：优先按 Markdown 标题分章；无标题则按空行分段。

    短段（< _MIN_MERGE_CHARS）合并到前一段，减少碎片。
    """
    lines = text.splitlines()
    chapters: list[Chapter] = []
    cur_title: str | None = None
    cur_buf: list[str] = []
    order = 0

    def flush() -> None:
        nonlocal cur_title, cur_buf, order
        body = "\n".join(cur_buf).strip()
        if not body:
            cur_title = None
            cur_buf.clear()
            return
        order += 1
        chapters.append(Chapter(seq=order, title=cur_title or f"第{order}节", content=body))
        cur_title = None
        cur_buf.clear()

    for line in lines:
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            flush()
            cur_title = m.group(2).strip()
        else:
            cur_buf.append(line)
    flush()

    if not chapters:
        body = text.strip()
        if body:
            chapters.append(Chapter(seq=1, title=default_title, content=body))

    # 合并过短片段到前一篇
    merged: list[Chapter] = []
    for ch in chapters:
        if merged and len(ch.content) < _MIN_MERGE_CHARS:
            prev = merged[-1]
            prev.content = (prev.content + "\n" + ch.content).strip()
            prev.title = prev.title  # 保留较长章节标题
        else:
            merged.append(ch)
    merged = _chunk_long(merged)
    return merged


def parse_document(filename: str, raw: bytes) -> list[Chapter]:
    """解析文档为有序章节列表。

    Args:
        filename: 原始文件名（用于识别扩展名）。
        raw: 文件二进制内容。

    Returns:
        章节列表（按大纲顺序，seq 从 1 递增）。

    Raises:
        UnsupportedFormatError: 格式不支持或缺失依赖库。
    """
    ext = os.path.splitext(filename)[1].lower()
    text = _decode(raw)

    if ext in _MD_EXT or ext in _TEXT_EXT:
        chapters = _split_text_to_chapters(text)
        logger.info("[document_ingest] 解析 %s → %d 章节", filename, len(chapters))
        return chapters

    if ext in _HEAVY_EXT:
        hint = _HEAVY_HINTS.get(ext, "对应解析库")
        raise UnsupportedFormatError(
            f"暂不支持 {ext} 格式（MVP 仅支持 .txt/.md）。"
            f"如需解析该格式请安装 {hint}，并在 document_ingest 注册适配器。"
        )

    raise UnsupportedFormatError(f"不支持的文件格式: {ext or '无扩展名'}")
