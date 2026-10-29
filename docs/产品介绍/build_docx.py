# -*- coding: utf-8 -*-
"""T03641 / T03643：把同名 Markdown 源稿编译成 Word（.docx）。

源稿是唯一事实面，本脚本只做排版映射：标题层级、正文、列表、表格、
`![说明](assets/x.png)` 配图（按长宽比定宽 + 居中图注），以及
「【此处插入功能截图…】」占位段落（灰底居中，便于出图后整段替换）。
配图文件缺失即报错退出，不允许静默产出一份「看起来完整、其实少图」的文档。
"""
import re
import struct
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

HERE = Path(__file__).resolve().parent
SRC = HERE / "MorningBrief-产品介绍.md"
DST = HERE / "MorningBrief-产品介绍.docx"
PLACEHOLDER = "【此处插入功能截图"
IMAGE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)$")


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    if head[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit("配图不是 PNG：%s" % path)
    return struct.unpack(">II", head[16:24])


def pic_width(w, h):
    ratio = w / h
    if ratio >= 1.6:
        return Inches(6.2)
    if ratio >= 0.8:
        return Inches(4.2)
    return Inches(2.5)


def set_font(style, size, bold=False, color=None, name="微软雅黑"):
    style.font.name = name
    style.font.size = Pt(size)
    style.font.bold = bold
    if color is not None:
        style.font.color.rgb = RGBColor(*color)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), name)


def shade(paragraph, hex_fill):
    el = paragraph._p.get_or_add_pPr()
    sh = el.makeelement(qn("w:shd"), {qn("w:val"): "clear", qn("w:fill"): hex_fill})
    el.append(sh)


def bold_runs(paragraph, text):
    """把 **粗体** 片段渲染成真正的加粗 run，其余按正文。"""
    for i, part in enumerate(re.split(r"\*\*(.+?)\*\*", text)):
        if not part:
            continue
        run = paragraph.add_run(part)
        run.bold = (i % 2 == 1)
    return paragraph


def main():
    doc = Document()
    for name, size, bold, color in (("Normal", 11, False, None), ("Title", 26, True, (31, 56, 88)),
                                    ("Heading 1", 16, True, (31, 56, 88)),
                                    ("Heading 2", 13, True, (53, 94, 133)),
                                    ("Heading 3", 11.5, True, (89, 89, 89))):
        set_font(doc.styles[name], size, bold, color)
    doc.styles["Normal"].paragraph_format.space_after = Pt(6)
    doc.styles["Normal"].paragraph_format.line_spacing = 1.4

    lines = SRC.read_text(encoding="utf-8").splitlines()
    i = tables = placeholders = bodies = images = 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip() or ln.strip() == "---":
            i += 1
            continue
        if ln.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+$", lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not set("".join(cells)) <= set("-: "):
                    rows.append(cells)
                i += 1
            t = doc.add_table(rows=0, cols=len(rows[0]))
            t.style = "Light Grid Accent 1"
            for r, cells in enumerate(rows):
                target = t.add_row().cells
                for c, val in enumerate(cells):
                    target[c].text = ""
                    p = target[c].paragraphs[0]
                    p.add_run(val).bold = (r == 0)
            tables += 1
            continue
        if ln.startswith("# "):
            p = doc.add_paragraph(ln[2:], style="Title")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        elif ln.startswith("## "):
            doc.add_paragraph(ln[3:], style="Heading 1")
        elif ln.startswith("### "):
            doc.add_paragraph(ln[4:], style="Heading 2")
        elif ln.startswith("- "):
            bold_runs(doc.add_paragraph(style="List Bullet"), ln[2:])
            bodies += 1
        elif re.match(r"^\d+\. ", ln):
            bold_runs(doc.add_paragraph(style="List Number"), re.sub(r"^\d+\. ", "", ln))
            bodies += 1
        elif (m := IMAGE.match(ln.strip())):
            rel = m.group(2)
            asset = HERE / rel
            if not asset.exists():
                raise SystemExit("配图缺失：%s（源稿第 %d 行）" % (rel, i + 1))
            w, h = png_size(asset)
            doc.add_picture(str(asset), width=pic_width(w, h))
            pic = doc.paragraphs[-1]
            pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap = doc.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = cap.add_run(m.group(1))
            run.font.size = Pt(9)
            run.font.color.rgb = RGBColor(0x60, 0x69, 0x73)
            images += 1
        elif ln.startswith(PLACEHOLDER):
            p = doc.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            run = p.add_run(ln)
            run.font.color.rgb = RGBColor(0x99, 0x55, 0x00)
            run.italic = True
            shade(p, "F2F2F2")
            placeholders += 1
        else:
            bold_runs(doc.add_paragraph(), ln)
            bodies += 1
        i += 1

    doc.core_properties.title = "MorningBrief 产品介绍"
    doc.core_properties.author = "MorningBrief"
    doc.core_properties.comments = "由 docs/产品介绍/MorningBrief-产品介绍.md 编译生成"
    doc.save(DST)
    sys.stdout.write("docx saved placeholders=%d images=%d tables=%d body_paras=%d\n"
                     % (placeholders, images, tables, bodies))
    return 0


if __name__ == "__main__":
    sys.exit(main())
