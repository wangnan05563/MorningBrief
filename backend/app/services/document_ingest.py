"""文档解析服务（MVP 输入适配器，T1；T00585 扩展电子书格式）。

把专业资料（书籍/文档/网页/纯文本）解析为有序章节列表，供后续
rewrite → tts → stitch 流水线消费。

支持范围（TXT/MD/EPUB/DOCX/HTML 为标准库**零第三方依赖**；PDF 需 PyMuPDF 可选依赖）：
- .txt / .text：纯文本切分章节。
- .md / .markdown / .mdown / .mkd：Markdown 标题分章。
- .epub：EPUB 本质是 ZIP 容器（META-INF/container.xml → OPF → spine 阅读顺序），
  内页为 XHTML——用 zipfile + ElementTree 解析容器结构，html.parser 提取正文，
  按 spine 顺序每篇文档一章。
- .docx：同为 ZIP 容器（word/document.xml），按 <w:p> 段落与 Heading 样式分章。
- .html / .htm：标准库 html.parser 提取文本，标题（h1-h6）转为 Markdown 井号复用分章逻辑。
- .pdf：PyMuPDF(fitz) 懒加载可选依赖，逐页提取文本层（扫描版无文本层给出 OCR 提示）。

超长章节按句/段自动切块，保持顺序。
仍不支持的格式（.doc/.mobi/.azw3 为专有二进制，标准库无法解析）抛出
UnsupportedFormatError 并给出「转存为 EPUB/TXT 后上传」的明确提示，避免静默失败。
"""
from dataclasses import dataclass
import hashlib
import io
import os
import re
import zipfile
import posixpath
from html.parser import HTMLParser
from typing import Callable
import xml.etree.ElementTree as ET

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
# 电子书 / 容器格式（T00585）：EPUB 与 DOCX 本质是 ZIP+XML，标准库即可解析
_ZIP_BOOK_EXT = {".epub", ".docx"}
_HTML_EXT = {".html", ".htm"}
_PDF_EXT = {".pdf"}
# 仍不支持的标准库无法可靠解析格式（MOBI 专有二进制；.doc 旧版二进制）
_UNSUPPORTED_EXT = {".doc", ".mobi", ".azw3", ".azw", ".prc"}

# 单章节内容上限：超过则按句/段切块，避免单段 TTS 超时或超长
_MAX_CHAPTER_CHARS = 1200
# 过短章节合并阈值：小于此值且与上一篇合并（避免碎片）
_MIN_MERGE_CHARS = 30

# 仍不支持格式 → 用户侧动作提示（零依赖前提下无法解析，引导转格式而非装库）
_KINDLE_HINT = "Kindle 专有格式；建议用 Calibre 等工具转存为 EPUB 后上传"
_UNSUPPORTED_HINTS = {
    ".pdf": "PDF 需文本层提取库；建议用阅读器「另存为 TXT」或转存 EPUB 后上传",
    ".doc": "旧版 Word 二进制格式；建议用 Word/WPS「另存为 .docx」后上传",
    ".mobi": _KINDLE_HINT,
    ".azw3": _KINDLE_HINT,
    ".azw": _KINDLE_HINT,
    ".prc": _KINDLE_HINT,
}


def compute_content_hash(content: str) -> str:
    """计算正文内容哈希（去重键）。

    用于 list 类型素材的 (source_type, dedup_key) 去重，避免与 rss 的 url 唯一键耦合。
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _decode(raw: bytes) -> str:
    """尽力解码为文本：UTF-8 优先，其次 GB18030（中文网页/文档常见），失败降级忽略。

    注意顺序：UTF-8 严格解码失败才尝试 GB18030（GB18030 几乎能解码任意字节，
    放在最前会把合法 UTF-8 解成乱码）。
    """
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        pass
    try:
        return raw.decode("gb18030")
    except UnicodeDecodeError:
        return raw.decode("utf-8", errors="ignore")


def _chunk_long(chapters: list[Chapter], max_chars: int = _MAX_CHAPTER_CHARS) -> list[Chapter]:  # NOSONAR
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


def _split_text_to_chapters(text: str, default_title: str = "正文") -> list[Chapter]:  # NOSONAR
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
            if len(ch.title) > len(prev.title):
                prev.title = ch.title
        else:
            merged.append(ch)
    merged = _chunk_long(merged)
    return merged


# ---------------------------------------------------------------------------
# T00585：HTML / EPUB / DOCX 解析（零第三方依赖，全部标准库）
# ---------------------------------------------------------------------------

_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_BLOCK_TAGS = {
    "p", "div", "section", "article", "aside", "li", "tr", "br", "hr",
    "ul", "ol", "table", "blockquote", "pre", "figure", "figcaption",
    "header", "footer", "main",
}
_SKIP_TAGS = {"script", "style", "head", "noscript"}


class _HTMLTextExtractor(HTMLParser):
    """把 HTML/XHTML 提取为纯文本：块级标签转换行，标题转 Markdown 井号。

    输出文本可直接交给 _split_text_to_chapters（h1-h6 → `# 标题` 复用现有分章）；
    首个标题文本另存 `first_heading`，供容器格式（EPUB）作为章节题名兜底。
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0
        self.first_heading: str | None = None
        self._heading_capture = False
        self._heading_buf: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        elif tag in _HEADING_TAGS:
            # 第一个标题用一级井号（作章节题名），其余用二级
            self._heading_capture = True
            self._heading_buf = []
            self.parts.append("\n# " if self.first_heading is None else "\n## ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif tag in _HEADING_TAGS:
            if self.first_heading is None:
                self.first_heading = "".join(self._heading_buf).strip() or None
            self._heading_capture = False
            self._heading_buf = []
            self.parts.append("\n")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._skip_depth:
            return
        if self._heading_capture:
            self._heading_buf.append(data)
        self.parts.append(data)

    def get_text(self) -> str:
        # 压缩 3+ 连续换行为 2 个（保留段落分隔语义）
        text = "".join(self.parts)
        return re.sub(r"\n{3,}", "\n\n", text).strip()


def _html_to_text(raw: bytes) -> tuple[str, str | None]:
    """HTML/XHTML → (纯文本, 文档首个标题文本或 None)。"""
    parser = _HTMLTextExtractor()
    parser.feed(_decode(raw))
    parser.close()
    return parser.get_text(), parser.first_heading


def _extract_epub_spine_lines(zf, manifest: dict, spine_ids: list, opf_dir: str) -> list[str]:
    """按 spine 顺序逐篇提取正文行（每篇 XHTML = 一章）。

    篇内已有标题（h1-h3）则直接用；无标题的篇（封面/版权页等）用序号兜底。
    """
    lines: list[str] = []
    order = 0
    for idref in spine_ids:
        href = manifest.get(idref)
        if not href:
            continue
        path = posixpath.normpath(posixpath.join(opf_dir, href)) if opf_dir else href
        try:
            doc_raw = zf.read(path)
        except KeyError:
            logger.warning("[document_ingest] EPUB spine 条目缺失，跳过: {}", path)
            continue
        text, doc_title = _html_to_text(doc_raw)
        if not text:
            continue
        order += 1
        if not (text.startswith("# ") or "\n# " in text):
            lines.append(f"# {doc_title or f'第{order}节'}")
        lines.append(text)
    return lines


def _parse_epub(raw: bytes, filename: str) -> list[Chapter]:
    """解析 EPUB：ZIP 容器 → container.xml → OPF → spine 阅读顺序逐篇提取。

    EPUB 结构：
      META-INF/container.xml       指向 OPF 路径
      *.opf                        清单(manifest id→href) + 顺序(spine idref 序列)
      *.xhtml                      各章节内容
    """
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as e:
        raise DocumentIngestError(f"EPUB 文件损坏（不是有效的 ZIP 容器）: {filename}") from e

    # 1. container.xml → OPF 路径
    try:
        container = ET.fromstring(zf.read("META-INF/container.xml"))
    except KeyError as e:
        raise DocumentIngestError("EPUB 缺少 META-INF/container.xml，不是有效的 EPUB") from e
    _NS_CONTAINER = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = container.find(".//c:rootfiles/c:rootfile", _NS_CONTAINER)
    opf_path = rootfile.get("full-path") if rootfile is not None else None
    if not opf_path:
        raise DocumentIngestError("EPUB container.xml 未声明 rootfile，无法定位书目信息")

    # 2. OPF → manifest(id→href) + spine(阅读顺序)
    try:
        opf = ET.fromstring(zf.read(opf_path))
    except KeyError as e:
        raise DocumentIngestError(f"EPUB 清单文件缺失: {opf_path}") from e
    _NS_OPF = {"o": "http://www.idpf.org/2007/opf"}
    manifest = {
        item.get("id"): item.get("href")
        for item in opf.findall(".//o:manifest/o:item", _NS_OPF)
    }
    spine_ids = [ref.get("idref") for ref in opf.findall(".//o:spine/o:itemref", _NS_OPF)]
    opf_dir = posixpath.dirname(opf_path)

    # 3. 按 spine 顺序逐篇提取（每篇 XHTML = 一章）
    lines = _extract_epub_spine_lines(zf, manifest, spine_ids, opf_dir)
    if not lines:
        raise DocumentIngestError(f"EPUB 未提取到任何正文内容: {filename}")

    chapters = _split_text_to_chapters("\n".join(lines), default_title="正文")
    logger.info("[document_ingest] 解析 EPUB {}（spine {} 篇）→ {} 章节",
                filename, len(spine_ids), len(chapters))
    return chapters


def _parse_docx(raw: bytes, filename: str) -> list[Chapter]:
    """解析 DOCX：ZIP 容器 → word/document.xml，按 Heading 样式分章。"""
    _W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        doc = zf.read("word/document.xml")
    except zipfile.BadZipFile as e:
        raise DocumentIngestError(f"DOCX 文件损坏（不是有效的 ZIP 容器）: {filename}") from e
    except KeyError as e:
        raise DocumentIngestError("DOCX 缺少 word/document.xml，不是有效的 Word 文档") from e

    root = ET.fromstring(doc)
    lines: list[str] = []
    for p in root.iter(f"{_W}p"):
        style_el = p.find(f"{_W}pPr/{_W}pStyle")
        style = (style_el.get(f"{_W}val", "") if style_el is not None else "").lower()
        text = "".join(t.text or "" for t in p.iter(f"{_W}t")).strip()
        if not text:
            continue
        # Heading1-6 / 标题 样式视为章节标题
        if style.startswith("heading") or style in ("title", "标题"):
            lines.append(f"# {text}")
        else:
            lines.append(text)
    if not lines:
        raise DocumentIngestError(f"DOCX 未提取到任何正文内容: {filename}")

    chapters = _split_text_to_chapters("\n".join(lines), default_title="正文")
    logger.info("[document_ingest] 解析 DOCX {} → {} 章节", filename, len(chapters))
    return chapters


def split_text(text: str, default_title: str = "正文") -> list[dict]:
    """公开的纯文本切分入口（T00603：全文源爬虫复用）。

    把长文本按标题/段落切成有序章节并做超长切块与碎片合并，
    返回 [{"title": str, "content": str}]，供 crawler 把整本书拆成多条素材。
    """
    chapters = _split_text_to_chapters(text, default_title=default_title)
    return [{"title": c.title, "content": c.content} for c in chapters]


def _parse_pdf(raw: bytes, filename: str) -> list[Chapter]:
    """解析 PDF：PyMuPDF(fitz) 逐页提取文本层 → 合并 → 统一分章（懒加载可选依赖）。

    PyMuPDF 文本层提取对复杂版面/中文字体更稳（评分高于 pypdf）。
    依赖**懒加载**：未安装时抛 UnsupportedFormatError 并给出安装指引，
    保证 document_ingest 的其余格式零依赖可用。
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise UnsupportedFormatError(
            "PDF 解析需要 PyMuPDF 库（backend/.venv 执行 pip install PyMuPDF），"
            "或把 PDF 转存为 EPUB/TXT 后上传"
        ) from e

    try:
        doc = fitz.open(stream=raw, filetype="pdf")
        try:
            page_texts = [(page.get_text() or "").strip() for page in doc]
        finally:
            doc.close()
    except fitz.FileDataError as e:
        raise DocumentIngestError(f"PDF 解析失败: {filename}（非 PDF 或文件损坏）") from e
    except Exception as e:
        raise DocumentIngestError(f"PDF 解析失败: {filename}（{e}）。扫描版 PDF 无文本层，请先 OCR") from e

    # 按页拼接（页与页之间空行分隔，供分章器识别段落边界）
    text = "\n\n".join(t for t in page_texts if t)
    if not text.strip():
        raise UnsupportedFormatError(
            f"PDF 无文本层（扫描版图片）: {filename}。请先 OCR，或转存为 EPUB/TXT 后上传"
        )

    chapters = _split_text_to_chapters(text, default_title=filename.rsplit(".", 1)[0] or "正文")
    logger.info("[document_ingest] 解析 PDF {}（{} 页）→ {} 章节", filename, len(page_texts), len(chapters))
    return chapters


def parse_document(filename: str, raw: bytes) -> list[Chapter]:
    """解析文档为有序章节列表。

    支持格式（零第三方依赖）：
    - 纯文本/Markdown：.txt/.text/.md/.markdown/.mdown/.mkd
    - 电子书/容器：.epub（ZIP+OPF+XHTML）、.docx（ZIP+document.xml）
    - 网页：.html/.htm
    不支持：.pdf/.doc/.mobi/.azw3 等（标准库无法可靠提取），抛错并提示转格式。

    Args:
        filename: 原始文件名（用于识别扩展名）。
        raw: 文件二进制内容。

    Returns:
        章节列表（按大纲顺序，seq 从 1 递增）。

    Raises:
        UnsupportedFormatError: 格式不支持或文件损坏。
        DocumentIngestError: 容器损坏 / 无有效内容。
    """
    ext = os.path.splitext(filename)[1].lower()

    if ext in _MD_EXT or ext in _TEXT_EXT:
        chapters = _split_text_to_chapters(_decode(raw))
        logger.info("[document_ingest] 解析 {} → {} 章节", filename, len(chapters))
        return chapters

    if ext == ".epub":
        return _parse_epub(raw, filename)

    if ext == ".docx":
        return _parse_docx(raw, filename)

    if ext in _PDF_EXT:
        return _parse_pdf(raw, filename)

    if ext in _HTML_EXT:
        text, _ = _html_to_text(raw)
        chapters = _split_text_to_chapters(text)
        logger.info("[document_ingest] 解析 HTML {} → {} 章节", filename, len(chapters))
        return chapters

    if ext in _UNSUPPORTED_EXT:
        hint = _UNSUPPORTED_HINTS.get(ext, "请转存为 EPUB/TXT 后上传")
        raise UnsupportedFormatError(f"暂不支持 {ext} 格式：{hint}")

    raise UnsupportedFormatError(f"不支持的文件格式: {ext or '无扩展名'}")
