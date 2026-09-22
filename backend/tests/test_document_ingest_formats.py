"""T00585 —— 素材录入支持电子书格式（EPUB / DOCX / HTML，零第三方依赖）单元测试。

用标准库 zipfile 在测试内构建合成 EPUB / DOCX 容器，验证：
- EPUB：container.xml → OPF → spine 阅读顺序逐篇成章、标题取自 h1、长章切块；
- DOCX：Heading 样式分章、<w:t> 文本提取；
- HTML：h1-h6 转 Markdown 井号复用分章、GB18030 编码网页正确解码；
- 不支持格式（.pdf/.mobi）的明确报错与转格式提示；
- 既有 .txt 行为回归。

运行：backend 目录下 .venv/Scripts/python -m pytest tests/test_document_ingest_formats.py
"""
import io
import zipfile

import pytest

from app.services.document_ingest import (
    DocumentIngestError,
    UnsupportedFormatError,
    compute_content_hash,
    parse_document,
)


def _make_epub(chapters: list[tuple[str, str]]) -> bytes:
    """构建最小合法 EPUB（container.xml + OPF + spine + 每章一个 XHTML）。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip")
        zf.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            "<rootfiles>"
            '<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>'
            "</rootfiles></container>",
        )
        items = "".join(
            f'<item id="c{i}" href="ch{i}.xhtml" media-type="application/xhtml+xml"/>'
            for i in range(1, len(chapters) + 1)
        )
        refs = "".join(f'<itemref idref="c{i}"/>' for i in range(1, len(chapters) + 1))
        zf.writestr(
            "OEBPS/content.opf",
            '<?xml version="1.0"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0">'
            f"<manifest>{items}</manifest><spine>{refs}</spine></package>",
        )
        for i, (title, body) in enumerate(chapters, 1):
            zf.writestr(
                f"OEBPS/ch{i}.xhtml",
                '<?xml version="1.0" encoding="utf-8"?>'
                '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>x</title></head>'
                f"<body><h1>{title}</h1><p>{body}</p></body></html>",
            )
    return buf.getvalue()


def _make_docx(paragraphs: list[tuple[str, str]]) -> bytes:
    """构建最小 DOCX（paragraphs: [(样式, 文本)]，样式 heading1=标题）。"""
    _W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    body = []
    for style, text in paragraphs:
        pstyle = (
            f'<w:pPr><w:pStyle w:val="{style}"/></w:pPr>' if style else ""
        )
        body.append(f"<w:p>{pstyle}<w:r><w:t>{text}</w:t></w:r></w:p>")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "word/document.xml",
            '<?xml version="1.0"?>'
            f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f"<w:body>{''.join(body)}</w:body></w:document>",
        )
    return buf.getvalue()


class TestEpub:
    def test_spine_order_and_titles(self):
        raw = _make_epub([
            ("第一章 缘起", "这是第一章的内容，讲了一个完整的开头故事。主角在小镇长大，对世界充满好奇，也为后续的冒险埋下了伏笔。"),
            ("第二章 展开", "这是第二章的内容，把主线情节充分展开铺陈。冲突逐步升级，人物关系变得复杂，读者也开始理解故事的真正主题。"),
            ("第三章 收束", "这是第三章的内容，为整个故事画上收束句号。所有伏笔在此回收，主题得到升华，留给读者长久的回味与思考。"),
        ])
        chapters = parse_document("三体.epub", raw)
        assert [c.title for c in chapters] == ["第一章 缘起", "第二章 展开", "第三章 收束"]
        assert [c.seq for c in chapters] == [1, 2, 3]
        assert "第二章的内容" in chapters[1].content

    def test_long_chapter_chunked(self):
        long_body = "这一段讲了一个很长的道理。" * 200  # ~2400 字 > _MAX_CHAPTER_CHARS
        raw = _make_epub([("很长的一章", long_body)])
        chapters = parse_document("长书.epub", raw)
        assert len(chapters) > 1, "超长章节应被切块"
        assert all(len(c.content) <= 1200 + 60 for c in chapters)  # 允许句边界少量超出
        assert all(c.title.startswith("很长的一章") for c in chapters)

    def test_dedup_hash_stable_across_parse(self):
        raw = _make_epub([("第一章", "内容A。这是一段稳定的正文内容，用于校验哈希一致性。")])
        ch1 = parse_document("a.epub", raw)[0]
        ch2 = parse_document("a.epub", raw)[0]
        assert compute_content_hash(ch1.content) == compute_content_hash(ch2.content)

    def test_broken_epub_raises(self):
        with pytest.raises(DocumentIngestError):
            parse_document("bad.epub", b"this is not a zip")


class TestDocx:
    def test_heading_styles_split_chapters(self):
        raw = _make_docx([
            ("heading1", "第一章 导论"),
            ("", "导论正文第一段，交代研究背景与问题意识。该领域近十年的进展与争论，为后续章节的方法选择提供了出发点。"),
            ("heading1", "第二章 方法"),
            ("", "方法正文第一段，说明实验设计与数据来源。样本规模、变量定义与检验方式在此逐一交代，保证结论可复现。"),
        ])
        chapters = parse_document("书稿.docx", raw)
        assert [c.title for c in chapters] == ["第一章 导论", "第二章 方法"]
        assert "导论正文" in chapters[0].content
        assert "方法正文" in chapters[1].content

    def test_text_only_docx_single_chapter(self):
        raw = _make_docx([("", "没有标题样式的一堆文字。")])
        chapters = parse_document("notes.docx", raw)
        assert len(chapters) == 1
        assert "一堆文字" in chapters[0].content


class TestHtml:
    def test_headings_become_chapters(self):
        html = (
            "<html><head><style>body{color:red}</style></head><body>"
            "<h1>上篇</h1><p>上篇内容，篇幅足够长，避免被合并处理。这一节讨论了问题的来龙去脉，并给出三个值得记住的判断。</p>"
            "<h1>下篇</h1><p>下篇内容，篇幅同样足够长。这一节转向解决方案，逐一评述了可行路径，并指出最容易被忽视的陷阱。</p>"
            "</body></html>"
        ).encode("utf-8")
        chapters = parse_document("page.html", html)
        assert [c.title for c in chapters] == ["上篇", "下篇"]
        # style 标签内容不应泄漏进正文
        assert "color:red" not in chapters[0].content

    def test_gb18030_encoding_decoded(self):
        html = "<html><body><h1>中文标题</h1><p>中文内容。</p></body></html>".encode("gb18030")
        chapters = parse_document("gb.html", html)
        assert chapters[0].title == "中文标题"
        assert "中文内容" in chapters[0].content


class TestTxtRegression:
    def test_txt_still_works(self):
        chapters = parse_document("a.txt", "# 第一章\n内容一。".encode("utf-8"))
        assert chapters[0].title == "第一章"


class TestUnsupported:
    @pytest.mark.parametrize("filename", ["book.mobi", "book.azw3", "old.doc"])
    def test_unsupported_formats_hint_conversion(self, filename):
        with pytest.raises(UnsupportedFormatError) as ei:
            parse_document(filename, b"\x00\x01binary")
        assert "转存" in str(ei.value) or "另存为" in str(ei.value)

    def test_unknown_extension(self):
        with pytest.raises(UnsupportedFormatError):
            parse_document("book.xyz", b"data")


# ==========================================================================
# API 级冒烟：/admin/api/v1/materials/upload（multipart → 解析 → 入库）
# 复用 conftest 的 client / admin_token 夹具与 test_workflow_service 的
# stub_blacklist 模式（require_admin → is_in_blacklist 会连生产库，需绕过）。
# ==========================================================================

import pytest as _pytest


@_pytest.fixture
def stub_blacklist(monkeypatch):
    """绕过 is_in_blacklist 的 DB 查询，避免命中生产 SQLite 文件。"""
    import app.core.auth

    async def _always_false(jti: str) -> bool:
        return False

    monkeypatch.setattr(app.core.auth, "is_in_blacklist", _always_false)


def _admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token['token']}"}


def test_upload_epub_api_roundtrip(client, admin_token, stub_blacklist):
    """EPUB 经 multipart 上传 → 解析 2 章 → 入库返回 count=2。"""
    raw = _make_epub([
        ("第一章 缘起", "这是第一章的内容，讲了一个完整的开头故事。主角在小镇长大，对世界充满好奇，也为后续的冒险埋下了伏笔。"),
        ("第二章 展开", "这是第二章的内容，把主线情节充分展开铺陈。冲突逐步升级，人物关系变得复杂，读者也开始理解故事的真正主题。"),
    ])
    resp = client.post(
        "/admin/api/v1/materials/upload",
        files={"file": ("book.epub", raw, "application/epub+zip")},
        data={"channel_id": "10", "source": "文档上传"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0, body
    assert body["data"]["count"] == 2
    titles = [item["title"] for item in body["data"]["list"]]
    assert "第一章 缘起" in titles[0]


def test_upload_unsupported_format_api_returns_biz_error(client, admin_token, stub_blacklist):
    """不支持的格式经 API 上传 → 业务错误（code!=0），消息含转格式提示。"""
    resp = client.post(
        "/admin/api/v1/materials/upload",
        files={"file": ("book.mobi", b"\x00\x01binary", "application/x-mobipocket-ebook")},
        data={"channel_id": "10"},
        headers=_admin_headers(admin_token),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] != 0
    assert "EPUB" in body["message"] or "mobi" in body["message"]

class TestPdf:
    """PDF 文本层提取（PyMuPDF(fitz) 懒加载可选依赖，T00585 下一步）。

    测试内构建**最小合法 PDF**（手算 xref 偏移），不依赖任何 PDF 生成库。
    """

    @staticmethod
    def _build_pdf(lines):
        import io as _io
        nl = chr(10)  # 避免 heredoc/传输层吃掉反斜杠转义
        content = "BT /F1 14 Tf 20 750 Td 16 TL" + nl + "".join(f"({l}) Tj T*{nl}" for l in lines) + "ET"
        objs = [
            b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        ]
        stream = content.encode("latin-1")
        objs.append(("<< /Length %d >>%sstream%s" % (len(stream), nl, nl)).encode() + stream + ("%sendstream" % nl).encode())
        objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        out = _io.BytesIO()
        out.write(b"%PDF-1.4" + nl.encode())
        offsets = []
        for i, body in enumerate(objs, 1):
            offsets.append(out.tell())
            out.write((f"{i} 0 obj" + nl).encode() + body + (nl + "endobj" + nl).encode())
        xref_at = out.tell()
        out.write((f"xref{nl}0 {len(objs) + 1}{nl}").encode())
        out.write(b"0000000000 65535 f " + nl.encode())
        for off in offsets:
            out.write((f"{off:010d} 00000 n " + nl).encode())
        out.write((f"trailer{nl}<< /Size {len(objs) + 1} /Root 1 0 R >>{nl}startxref{nl}{xref_at}{nl}%%EOF{nl}").encode())
        return out.getvalue()

    def test_text_layer_pdf_parsed(self):
        raw = self._build_pdf([
            "Chapter 1 The Beginning",
            "This is the first page of the test book. " * 8,
            "Chapter 2 The Middle",
            "Second page content for chunking. " * 8,
        ])
        chapters = parse_document("book.pdf", raw)
        assert chapters, "有文本层的 PDF 应解析出章节"
        joined = chr(10).join(c.content for c in chapters)
        assert "Chapter 1" in joined

    def test_scan_pdf_no_text_layer_hint(self):
        # 无文本流的页 → 无文本层（扫描版）→ 明确提示 OCR，而非静默失败
        raw = self._build_pdf([""])  # 空内容流
        with pytest.raises(UnsupportedFormatError, match="OCR"):
            parse_document("scan.pdf", raw)

    def test_pymupdf_missing_gives_install_hint(self, monkeypatch):
        import sys
        # 模拟未安装 fitz：让 _parse_pdf 的懒加载 import 触发 ImportError
        monkeypatch.setitem(sys.modules, "fitz", None)
        raw = self._build_pdf(["Chapter 1", "Some text " * 10])
        with pytest.raises(UnsupportedFormatError, match="PyMuPDF"):
            parse_document("book.pdf", raw)
