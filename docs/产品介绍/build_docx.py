# -*- coding: utf-8 -*-
"""T03641：把同名 Markdown 源稿编译成 Word（.docx）。

源稿是唯一事实面，本脚本只做排版映射：标题层级、正文、列表、表格、
以及「【此处插入功能截图…】」占位段落（灰底居中，便于出图后整段替换）。
"""
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

HERE = Path(__file__).resolve().parent
SRC = HERE / "MorningBrief-产品介绍.md"
DST = HERE / "MorningBrief-产品介绍.docx"
PLACEHOLDER = "【此处插入功能截图"


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
    i = tables = placeholders = bodies = 0
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
    sys.stdout.write("docx saved placeholders=%d tables=%d body_paras=%d\n"
                     % (placeholders, tables, bodies))
    return 0


if __name__ == "__main__":
    sys.exit(main())
