# -*- coding: utf-8 -*-
"""T03641 / T03643 校验：回读 .docx，确认结构、无乱码、配图真的嵌进去了，
且规模数字与事实表逐项一致。"""
import re
import sys
import zipfile
from pathlib import Path

from docx import Document

HERE = Path(__file__).resolve().parent
DOCX = HERE / "MorningBrief-产品介绍.docx"
SRC = HERE / "MorningBrief-产品介绍.md"
FACTS = HERE.parent.parent / "_validate" / "news2" / "T03641_facts.md"
OUT = HERE / "verify_report.txt"
WANT_PH = 3

WANT_TABLE = {  # 速览表里每一项：文案里的数字 -> 事实表实测值
    "内容生产工作流节点": "7", "可插拔 TTS 引擎": "5", "素材接入渠道": "7",
    "频道形态": "3", "广告投放位": "3", "小程序页面": "18", "数据模型": "35",
}


def main():
    fails = []
    if not DOCX.exists():
        return print("docx 不存在") or 1
    with zipfile.ZipFile(DOCX) as z:
        bad = z.testzip()
        if bad:
            fails.append("zip 损坏：%s" % bad)
        xml = z.read("word/document.xml").decode("utf-8")
        media = sorted(n for n in z.namelist() if n.startswith("word/media/"))
    if "\ufffd" in xml:
        fails.append("document.xml 含 U+FFFD（编码丢失）")

    md_images = re.findall(r"^!\[[^\]]*\]\(([^)]+)\)$", SRC.read_text(encoding="utf-8"), re.M)
    missing_assets = [p for p in md_images if not (HERE / p).exists()]
    if missing_assets:
        fails.append("源稿引用了不存在的配图：%s" % missing_assets)
    if len(media) != len(md_images):
        fails.append("源稿 %d 张配图，docx 内嵌 %d 个媒体文件" % (len(md_images), len(media)))
    if xml.count("<w:drawing>") != len(md_images):
        fails.append("正文 drawing 数 %d 与配图数 %d 不符" % (xml.count("<w:drawing>"), len(md_images)))

    doc = Document(str(DOCX))
    paras = list(doc.paragraphs)
    styles = [p.style.name for p in paras]
    titles = styles.count("Title")
    h1 = styles.count("Heading 1")
    h2 = styles.count("Heading 2")
    ph = [p.text for p in paras if p.text.startswith("【此处插入功能截图")]
    bullets = styles.count("List Bullet")
    numbers = styles.count("List Number")

    if titles != 1:
        fails.append("封面标题应为 1，实为 %d" % titles)
    if h1 < 6:
        fails.append("一级章节过少：%d" % h1)
    if len(ph) != WANT_PH:
        fails.append("截图占位应为 %d（其余已出图），实为 %d" % (WANT_PH, len(ph)))
    if not doc.tables:
        fails.append("缺少关键数字速览表")

    table = doc.tables[0]
    cells = {r.cells[0].text.strip(): r.cells[1].text.strip() for r in table.rows[1:]}
    for k, want in WANT_TABLE.items():
        got = cells.get(k, "")
        if not got.startswith(want):
            fails.append("速览表「%s」= 「%s」，事实表实测 %s" % (k, got, want))
    facts = FACTS.read_text(encoding="utf-8")
    for k, want in (("后端路由模块 / 注册端点数", "243"), ("管理后台一级模块数", "18"),
                    ("管理后台内置主题数", "6"), ("pytest 全量回归用例数", "1694")):
        if want not in facts:
            fails.append("事实表缺 %s=%s" % (k, want))
    api_cell = cells.get("后端接口", "")
    if not api_cell.startswith("43") or "243" not in api_cell:
        fails.append("速览表「后端接口」与事实表不符：%s" % api_cell)
    stat_cell = cells.get("运营后台模块", "")
    if not stat_cell.startswith("18") or "45" not in stat_cell:
        fails.append("速览表「运营后台模块」与事实表不符：%s" % stat_cell)
    theme_cell = cells.get("质量保障", "")
    if "1694" not in theme_cell:
        fails.append("速览表「质量保障」未引用实测用例数：%s" % theme_cell)
    if "未找到" in xml:
        fails.append("正文残留「未找到」占位口径")
    ver = "1.0.20261029.003"
    if ver not in "\n".join(p.text for p in paras):
        fails.append("封面缺版本号")

    lines = ["## T03641 / T03643 .docx 回读校验", "文件大小 %dB" % DOCX.stat().st_size,
             "段落 %d（Title %d / H1 %d / H2 %d / 项目符号 %d / 编号 %d）"
             % (len(paras), titles, h1, h2, bullets, numbers),
             "表格 %d 个，速览表 %d 行 × %d 列" % (len(doc.tables), len(table.rows), len(table.columns)),
             "配图：源稿 %d 张 / docx 内嵌 %d 个媒体文件" % (len(md_images), len(media)),
             "截图占位 %d 处（应剩 %d 处）" % (len(ph), WANT_PH), ""]
    lines += ["- %s" % p for p in ph]
    lines.append("")
    lines.append("## 结论")
    lines.append("通过" if not fails else "未通过：\n" + "\n".join("- " + f for f in fails))
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    sys.stdout.write("fails=%d -> verify_report.txt\n" % len(fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
