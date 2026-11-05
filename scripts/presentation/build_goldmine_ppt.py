#!/usr/bin/env python3
from __future__ import annotations

import datetime
import io
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs" / "goldmine-algorithm-team.pptx"
CACHE = ROOT / ".cache" / "goldmine-ppt"
CACHE.mkdir(parents=True, exist_ok=True)
W, H = 13.333333, 7.5
EMU = 914400
FONT = "Microsoft YaHei"
COLORS = {
    "paper": "F7F4ED",
    "white": "FFFFFF",
    "ink": "202020",
    "muted": "666666",
    "gold": "D99A17",
    "gold_light": "F5E7B8",
    "red": "B84635",
    "blue": "356B8C",
    "green": "32735A",
    "line": "DED8CC",
    "soft": "EEE9DF",
}


def emu(value):
    return int(value * EMU)


def color_xml(value):
    return f'<a:solidFill><a:srgbClr val="{value}"/></a:solidFill>'


def paragraph(text, size=20, color="202020", bold=True, bullet=False, space=500):
    lines = str(text).split("\n")
    result = []
    for index, line in enumerate(lines):
        props = f' marL="285750" indent="-171450"' if bullet else ""
        bullet_xml = '<a:buChar char="•"/>' if bullet else '<a:buNone/>'
        result.append(
            f'<a:p><a:pPr{props}>{bullet_xml}</a:pPr><a:r>'
            f'<a:rPr lang="zh-CN" sz="{int(size * 100)}" b="{1 if bold else 0}" dirty="0">'
            f'{color_xml(color)}<a:latin typeface="{FONT}"/><a:ea typeface="{FONT}"/></a:rPr>'
            f'<a:t>{escape(line)}</a:t></a:r>'
            f'<a:endParaRPr lang="zh-CN" sz="{int(size * 100)}"/></a:p>'
        )
    return "".join(result)


def text_box(shape_id, x, y, w, h, text, **kwargs):
    return f'''<p:sp>
      <p:nvSpPr><p:cNvPr id="{shape_id}" name="Text {shape_id}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr>
      <p:txBody><a:bodyPr wrap="square" anchor="t" lIns="0" tIns="0" rIns="0" bIns="0"><a:normAutofit/></a:bodyPr><a:lstStyle/>{paragraph(text, **kwargs)}</p:txBody>
    </p:sp>'''


def rect(shape_id, x, y, w, h, fill, line=None, radius=True):
    return f'''<p:sp>
      <p:nvSpPr><p:cNvPr id="{shape_id}" name="Shape {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm><a:prstGeom prst="{'roundRect' if radius else 'rect'}"><a:avLst/></a:prstGeom>{color_xml(fill)}<a:ln w="12700">{color_xml(line) if line else '<a:noFill/>'}</a:ln></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody>
    </p:sp>'''


def line(shape_id, x, y, w, color="D99A17"):
    return rect(shape_id, x, y, w, 0.035, color, radius=False)


def arrow(shape_id, x, y, w, h, direction, fill):
    return f'''<p:sp>
      <p:nvSpPr><p:cNvPr id="{shape_id}" name="Arrow {shape_id}"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr>
      <p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm><a:prstGeom prst="{direction}"><a:avLst/></a:prstGeom>{color_xml(fill)}<a:ln><a:noFill/></a:ln></p:spPr>
      <p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="zh-CN"/></a:p></p:txBody>
    </p:sp>'''


def picture(shape_id, rel_id, name, x, y, w, h):
    return f'''<p:pic>
      <p:nvPicPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/><p:cNvPicPr/><p:nvPr/></p:nvPicPr>
      <p:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>
      <p:spPr><a:xfrm><a:off x="{emu(x)}" y="{emu(y)}"/><a:ext cx="{emu(w)}" cy="{emu(h)}"/></a:xfrm><a:prstGeom prst="roundRect"><a:avLst/></a:prstGeom></p:spPr>
    </p:pic>'''


def base_tree():
    return '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'


def slide_xml(shapes, background="F7F4ED"):
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:bg><p:bgPr>{color_xml(background)}<a:effectLst/></p:bgPr></p:bg><p:spTree>{base_tree()}{''.join(shapes)}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''


REL_TYPES = {
    "image": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image",
    "slide": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide",
    "slideMaster": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster",
    "slideLayout": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout",
    "theme": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme",
    "officeDocument": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument",
    "metadata/core-properties": "http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties",
    "extended-properties": "http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties",
}


def rels_xml(items):
    body = "".join(
        f'<Relationship Id="{rid}" Type="{REL_TYPES[kind]}" Target="{escape(target)}"/>'
        for rid, kind, target in items
    )
    return f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{body}</Relationships>'


def image_fit(image, x, y, w, h):
    with Image.open(image) as im:
        iw, ih = im.size
    scale = min(w / iw, h / ih)
    width, height = iw * scale, ih * scale
    return x + (w - width) / 2, y + (h - height) / 2, width, height


class Deck:
    def __init__(self):
        self.media = []
        self.slide_rels = []

    def add_image(self, shapes, rels, path, x, y, w, h):
        path = Path(path)
        target = CACHE / f"image-{len(self.media) + 1}.jpg"
        with Image.open(path) as im:
            im.convert("RGB").save(target, "JPEG", quality=88, optimize=True)
        self.media.append(target)
        rid = f"rId{len(rels) + 1}"
        rels.append((rid, "image", f"../media/{target.name}"))
        x, y, w, h = image_fit(path, x, y, w, h)
        shapes.append(picture(100 + len(self.media), rid, path.stem, x, y, w, h))

    def header(self, shapes, title, number, kicker="GOLDMINE / ALGORITHM TEAM"):
        shapes.extend([
            text_box(2, 0.55, 0.34, 9.8, 0.3, kicker, size=10, color=COLORS["muted"], bold=True),
            text_box(3, 0.55, 0.72, 12.1, 0.58, title, size=28, color=COLORS["ink"], bold=True),
            line(4, 0.55, 1.37, 0.72),
            text_box(5, 12.15, 7.08, 0.6, 0.2, f"{number:02d}", size=10, color=COLORS["muted"]),
        ])

    def cover(self, number, title, subtitle, bullets, image):
        shapes, rels = [], []
        self.add_image(shapes, rels, image, 6.3, 0, 7.04, 7.5)
        shapes.extend([
            rect(2, 0, 0, 6.75, 7.5, COLORS["ink"], radius=False),
            rect(3, 0.62, 0.64, 0.72, 0.72, COLORS["gold"]),
            text_box(4, 0.62, 1.65, 5.45, 1.7, title, size=34, color=COLORS["white"], bold=True),
            text_box(5, 0.65, 3.5, 5.3, 0.65, subtitle, size=18, color="F3D98D", bold=True),
            line(6, 0.65, 4.4, 0.85),
            text_box(7, 0.65, 4.68, 5.25, 1.25, "\n".join(bullets), size=16, color="E5E5E5"),
            text_box(8, 0.65, 6.8, 5.3, 0.25, "RSI × RED TEAM × VERIFIED LEARNING", size=10, color="A9A9A9"),
        ])
        return slide_xml(shapes, COLORS["ink"]), rels

    def hero(self, number, title, bullets, image, note=None):
        shapes, rels = [], []
        self.header(shapes, title, number)
        self.add_image(shapes, rels, image, 0.55, 1.65, 7.1, 4.85)
        shapes.append(rect(20, 7.95, 1.65, 4.82, 4.85, COLORS["white"], COLORS["line"]))
        shapes.append(text_box(21, 8.28, 1.98, 4.15, 3.85, "\n".join(bullets), size=18, color=COLORS["ink"]))
        if note:
            shapes.append(text_box(22, 8.28, 5.72, 4.15, 0.55, note, size=12, color=COLORS["red"], bold=True))
        return slide_xml(shapes), rels

    def visual_steps(self, number, title, steps, footer):
        shapes, rels = [], []
        self.header(shapes, title, number)
        for index, (head, body, accent, image) in enumerate(steps):
            x = 0.55 + index * 3.12
            shapes.append(rect(20 + index * 4, x, 1.65, 2.82, 4.95, COLORS["white"], COLORS["line"]))
            self.add_image(shapes, rels, image, x + 0.14, 1.82, 2.54, 2.05)
            shapes.append(text_box(21 + index * 4, x + 0.2, 4.03, 2.42, 0.55, head, size=17, color=accent, bold=True))
            shapes.append(text_box(22 + index * 4, x + 0.2, 4.72, 2.42, 1.5, body, size=13, color=COLORS["ink"], bold=True))
            if index < len(steps) - 1:
                shapes.append(text_box(23 + index * 4, x + 2.82, 3.0, 0.3, 0.4, "→", size=22, color=COLORS["gold"], bold=True))
        shapes.append(text_box(90, 0.62, 6.82, 12.0, 0.35, footer, size=14, color=COLORS["muted"], bold=True))
        return slide_xml(shapes), rels

    def cards(self, number, title, cards, columns=3, footer=None, body_size=15, title_size=18):
        shapes, rels = [], []
        self.header(shapes, title, number)
        rows = (len(cards) + columns - 1) // columns
        card_w = (12.23 - (columns - 1) * 0.22) / columns
        card_h = (4.95 - (rows - 1) * 0.2) / rows
        for index, (head, body, accent, *image) in enumerate(cards):
            row, col = divmod(index, columns)
            x = 0.55 + col * (card_w + 0.22)
            y = 1.65 + row * (card_h + 0.2)
            shapes.append(rect(20 + index * 4, x, y, card_w, card_h, COLORS["white"], COLORS["line"]))
            shapes.append(rect(21 + index * 4, x, y, 0.06, card_h, accent, radius=False))
            if image:
                self.add_image(shapes, rels, image[0], x + 0.22, y + 0.18, card_w - 0.44, 1.45)
            title_y = y + 1.72 if image else y + (0.14 if rows >= 3 else 0.2)
            body_y = y + 2.3 if image else y + (0.62 if rows >= 3 else 0.78)
            shapes.append(text_box(22 + index * 4, x + 0.25, title_y, card_w - 0.48, 0.5, head, size=title_size, color=accent, bold=True))
            shapes.append(text_box(23 + index * 4, x + 0.25, body_y, card_w - 0.48, y + card_h - body_y - 0.14, body, size=body_size, color=COLORS["ink"]))
        if footer:
            shapes.append(text_box(90, 0.62, 6.75, 12.0, 0.35, footer, size=13, color=COLORS["muted"], bold=True))
        return slide_xml(shapes), rels

    def flywheel(self, number):
        shapes, rels = [], []
        self.header(shapes, "RSI 学习流程：经验怎样变成下一次更好的行动", number)
        shapes.append(text_box(6, 0.58, 1.47, 12.0, 0.3, "RSI 就是“根据真实结果持续改进”，不是让模型随意改写自己", size=14, color=COLORS["muted"], bold=True))
        nodes = [
            (0.7, 1.95, "01 留下真实经历", "看到什么 · 做了什么 · 结果与成本", COLORS["blue"]),
            (4.99, 1.95, "02 确认结果可信", "真实运行、独立审核或人工结论", COLORS["gold"]),
            (9.28, 1.95, "03 学会比较动作", "哪个动作收益更高、代价更低", COLORS["green"]),
            (9.28, 4.7, "04 拿新项目考试", "检查是否有效，有没有改坏旧能力", COLORS["red"]),
            (4.99, 4.7, "05 先只给建议", "让人比较新旧选择，不自动改流程", COLORS["muted"]),
            (0.7, 4.7, "06 复核后受控采用", "真实执行再留下下一轮经验", COLORS["green"]),
        ]
        for index, (x, y, head, body, accent) in enumerate(nodes):
            shapes.append(rect(20 + index * 3, x, y, 3.35, 1.25, COLORS["white"], accent))
            shapes.append(text_box(21 + index * 3, x + 0.2, y + 0.2, 2.95, 0.35, head, size=16, color=accent, bold=True))
            shapes.append(text_box(22 + index * 3, x + 0.2, y + 0.7, 2.95, 0.38, body, size=13, color=COLORS["ink"], bold=True))
        for index, (x, y, w, h, direction) in enumerate([
            (4.2, 2.36, 0.55, 0.42, "rightArrow"),
            (8.49, 2.36, 0.55, 0.42, "rightArrow"),
            (10.73, 3.4, 0.45, 0.95, "downArrow"),
            (8.49, 5.11, 0.55, 0.42, "leftArrow"),
            (4.2, 5.11, 0.55, 0.42, "leftArrow"),
            (2.15, 3.4, 0.45, 0.95, "upArrow"),
        ]):
            shapes.append(arrow(60 + index, x, y, w, h, direction, COLORS["gold"]))
        shapes.append(text_box(70, 3.5, 3.55, 6.35, 0.7, "学习流程持续的条件：有真实经验 → 有可靠答案 → 通过独立检查\n任何一步证据不足，都只保留建议，不强行自动改进", size=14, color=COLORS["ink"], bold=True))
        shapes.append(rect(80, 0.62, 6.25, 12.1, 0.55, COLORS["gold_light"], COLORS["gold"]))
        shapes.append(text_box(81, 0.86, 6.4, 11.65, 0.28, "验证动作的可信训练样本为 0，继续保持只读建议；挖掘修复是独立支路，只有通过真实前后运行评估的规则才发布", size=13, color=COLORS["red"], bold=True))
        return slide_xml(shapes), rels

    def metrics(self, number, title, metrics, bullets):
        shapes, rels = [], []
        self.header(shapes, title, number)
        for index, (value, label, accent) in enumerate(metrics):
            x = 0.55 + index * 4.13
            shapes.append(rect(20 + index, x, 1.65, 3.9, 1.65, COLORS["white"], COLORS["line"]))
            shapes.append(text_box(30 + index, x + 0.25, 1.88, 3.4, 0.65, value, size=34, color=accent, bold=True))
            shapes.append(text_box(40 + index, x + 0.25, 2.62, 3.4, 0.35, label, size=14, color=COLORS["muted"], bold=True))
        shapes.append(rect(50, 0.55, 3.65, 12.23, 2.65, COLORS["ink"]))
        shapes.append(text_box(51, 0.9, 3.98, 11.5, 1.8, "\n".join(bullets), size=18, color=COLORS["white"]))
        return slide_xml(shapes), rels

    def flow(self, number, title, steps, footer, details=None):
        shapes, rels = [], []
        self.header(shapes, title, number)
        for index, (head, sub, accent) in enumerate(steps):
            row, col = divmod(index, 4)
            x = 0.55 + col * 3.12
            y = 1.75 + row * 2.15
            shapes.append(rect(20 + index, x, y, 2.78, 1.45, COLORS["white"], accent))
            shapes.append(text_box(30 + index, x + 0.18, y + 0.22, 2.42, 0.42, head, size=17, color=accent, bold=True))
            shapes.append(text_box(40 + index, x + 0.18, y + 0.76, 2.42, 0.45, sub, size=12, color=COLORS["muted"]))
            if col < 3 and index < len(steps) - 1:
                shapes.append(text_box(50 + index, x + 2.82, y + 0.48, 0.25, 0.3, "→", size=20, color=COLORS["gold"], bold=True))
        for index, (head, body, accent) in enumerate(details or []):
            x = 0.55 + index * 4.13
            shapes.append(rect(70 + index, x, 4.25, 3.9, 1.5, COLORS["white"], COLORS["line"]))
            shapes.append(text_box(80 + index, x + 0.22, 4.47, 3.45, 0.35, head, size=16, color=accent, bold=True))
            shapes.append(text_box(90 + index, x + 0.22, 4.98, 3.45, 0.55, body, size=13, color=COLORS["ink"]))
        shapes.append(text_box(99, 0.62, 6.35, 12.0, 0.5, footer, size=14, color=COLORS["muted"], bold=True))
        return slide_xml(shapes), rels


def build():
    deck = Deck()
    art = ROOT / "ui" / "public" / "architecture"
    slides = []
    slides.append(deck.cover(
        1, "GoldMine\n从候选问题到可信证据",
        "RSI × 红队模型 × 可验证的算法学习循环",
        ["发现 · 验证 · 学习 · 非回归发布", "算法团队 / 2026-11"],
        art / "overview.webp",
    ))
    slides.append(deck.cards(2, "GoldMine：从源码到可信证据｜谁在执行", [
        ("01 脚本搭好实验场", "选好项目，建立独立工作副本。\n源码只读，所有修改留在沙箱。", COLORS["blue"]),
        ("02 智能体找准方向", "先识别项目类型、入口和边界，再缩小需要深读的范围。", COLORS["gold"]),
        ("03 子智能体深入审计", "按检查清单分析源码；审查者去重，报告器负责汇总。", COLORS["green"]),
        ("04 后台任务整理发现", "合并历史记录、自动分诊；归档只是低优先级，不代表安全。", COLORS["blue"]),
        ("05 智能体动手验证", "写最小复现并实际运行，不能把静态猜测直接当成漏洞。", COLORS["gold"]),
        ("06 红队证明并交付", "在隔离环境取得真实证据，独立复核后再交给人工。", COLORS["red"]),
    ], columns=3, footer="技能规定方法和边界，智能体负责判断，脚本与后台任务负责稳定执行", body_size=15, title_size=17))
    slides.append(deck.cards(3, "技能不是万能智能体：它只规定方法和边界", [
        ("画像技能", "告诉智能体要看项目类型、入口和信任边界，并推荐合适的分析路线。", COLORS["gold"]),
        ("分析技能", "提供某类漏洞的检查清单；它提供视角，不替智能体宣布漏洞成立。", COLORS["green"]),
        ("报告技能", "统一报告字段和表达方式，只汇总已有发现，不补造证据。", COLORS["blue"]),
        ("沙箱脚本", "负责隔离、工作副本和环境复用；它不管漏洞判断是否专业。", COLORS["blue"]),
        ("自动分类后台任务", "负责合并身份、去重和路由；它不能替人工完成最终验收。", COLORS["gold"]),
        ("红队隔离验证技能", "规定隔离、随机标记和负向控制；不支持的执行方式必须明确停下。", COLORS["red"]),
    ], columns=3, footer="具体脚本与技能路径统一放在末页；这里先听懂每个角色负责什么", body_size=15, title_size=17))
    slides.append(deck.cards(4, "2026 年研究地图：从自我反思走向受控学习循环", [
        ("Self-Harness", "共性弱点 → 最小执行框架修改 → 留出项目非回归。\n下一页：为什么只改外部执行框架。", COLORS["gold"]),
        ("AgentDevel", "把智能体当发布制品，逐项检查 P→F / F→P。\n第 6 页：为什么不能只看平均分。", COLORS["blue"]),
        ("MASS", "多角色工作流搜索，优质团队轨迹写回训练。\n第 7 页：协作经验怎样变成训练数据。", COLORS["green"]),
        ("HELIX", "模型与执行框架共同进化，保留已验证的配对方案。\n第 8 页：为什么执行框架决定能学到什么。", COLORS["gold"]),
        ("DiscoveryRSI", "假设信用、工作流回放与再次发现。\n第 9 页：怎样让发现能力逐轮增强。", COLORS["blue"]),
    ], columns=3, footer="接下来五页逐篇速览；论文结果用于指导设计，不直接外推为 GoldMine 的生产效果"))
    paper_art = ROOT / "docs" / "visuals" / "rsi-papers"
    slides.append(deck.hero(
        5, "Self-Harness：针对共性弱点，最小修改执行框架",
        ["问题：同一模型反复出现同类失败，人工逐项补丁难以复用", "方法：固定基座模型与评估器，从轨迹归纳弱点，只改外部执行框架", "验证：参与和未参与调参的项目都检查非回归；论文报告三组留出通过率提升", "GoldMine：model_timeout → 重试控制候选；weakness.py + harness.py"],
        paper_art / "self-harness.webp", "论文数值属于 Terminal-Bench 设定，不能外推为 GoldMine 的提升",
    ))
    slides.append(deck.hero(
        6, "AgentDevel：把自我演进做成发布工程",
        ["问题：平均分变高，可能掩盖原本通过的用例被改坏", "方法：单一版本线，每轮只产生一个发布候选（RC），配套可执行诊断", "发布检查：逐项比较 P→F 回归与 F→P 修复；论文消融中 P→F 从 3.1% 升至 14.8%（移除发布检查）", "GoldMine：按同一问题编号比较前后结果，确定后不再修改的候选保留证据、拒绝与回滚"],
        paper_art / "agentdevel.webp", "发布的基本单位是带证据的候选版本，不是一句“模型变好了”",
    ))
    slides.append(deck.hero(
        7, "MASS：让多角色协作轨迹成为训练经验",
        ["问题：单个智能体的探索路径有限，团队怎样分工也需要搜索", "方法：同一基座扮演多个角色，交替进行工作流搜索、自评估与训练", "结果：优质团队轨迹写回；论文在四个开放研究基准报告每输出词元得分为基座 1.2–1.6 倍", "GoldMine：分离攻击者、目标和独立审核轨迹；自评不能替代真实随机标记与独立审核"],
        paper_art / "mass.webp", "多智能体自评可能强化共同盲点，独立证据必须留在学习循环里",
    ))
    slides.append(deck.hero(
        8, "HELIX：模型与执行框架共同进化",
        ["核心观点：执行框架不只决定今天怎么执行，也决定明天能留下什么经验", "方法：构建、更新、重建执行框架，使其与模型能力变化相匹配", "数据：保留已验证的配对方案——成功、回归、近失和替代方案；200 组配对样本形成 438 条学习记录", "GoldMine：保存配对结果与证据来源链；未来模型更新后重新评估并重建执行框架"],
        paper_art / "helix.webp", "不是只保留成功答案，而是保留可比较、可回放的完整证据平面",
    ))
    slides.append(deck.hero(
        9, "DiscoveryRSI：让有价值的假设逐轮涌现",
        ["问题：发现系统不能只积累标签，还要知道哪些假设值得继续探索", "方法：假设树记录替代解释，结合贡献评估、工作流回放与再次发现", "结果：两轮后论文假设质量评分 4.86 → 5.39，并有初步专家评估", "GoldMine：候选问题应保存根因、调查决策、替代解释和可证伪证据，再研究假设信用"],
        paper_art / "discoveryrsi.webp", "论文面向生命科学发现，不能把分数直接解释为漏洞发现效果",
    ))
    slides.append(deck.cards(10, "为什么需要算法团队", [
        ("算法团队", "把轨迹变成可学习的数据，把奖励变成可计算的效用，再用验证器与发布检查约束改进。", COLORS["gold"], art / "cards" / "algorithm.webp"),
        ("开发团队", "容器、接口、用户界面、任务调度、可靠性与工程交付，让系统稳定可运行。", COLORS["blue"], art / "cards" / "development.webp"),
        ("安全团队", "威胁情报、漏洞先验、规则、人工裁决与披露规范，让判断足够专业。", COLORS["red"], art / "cards" / "security.webp"),
    ], footer="协作分工，不是能力高低；下一页把算法团队的六项机制逐一落到本项目"))
    slides.append(deck.cards(11, "算法团队到底做什么：把经验变成可信改进", [
        ("01 记录完整经历", "记住当时看到什么、做了什么、花了多少、结果如何。\n缺少任何一项，都难以判断哪一步有效。", COLORS["blue"]),
        ("02 定义好坏标准", "规定能选哪些动作，什么结果值得奖励，哪些成本必须扣除。", COLORS["gold"]),
        ("03 独立检查证据", "不让模型自己宣布成功；由独立检查确认结果真的可信。", COLORS["red"]),
        ("04 学会比较动作", "估计每个动作的净收益，而不是只追求表面的成功率。", COLORS["green"]),
        ("05 拿新项目考试", "用没参与训练的项目检验效果，避免系统只会背答案。", COLORS["blue"]),
        ("06 管住每次发布", "改进先当候选；确认有修复、没有改坏旧能力，才允许采用。", COLORS["red"]),
    ], columns=3, footer="技术实现见 verification.py、evaluation.py、release.py；正文只保留需要理解的概念", body_size=15, title_size=17))
    slides.append(deck.hero(
        12, "批量审计：先找到可疑点，再用证据逐步确认",
        ["每个项目都有独立工作副本，原始源码保持只读", "沙箱保留环境和产物，可以继续调查，不必每次重来", "自动扫描只负责找线索；报告必须写清位置、原因和验证思路"],
        art / "mining.webp", "静态分析找到的是“值得检查的候选”，不是已经成立的漏洞",
    ))
    slides.append(deck.cards(13, "红队模型：其实是三个角色一起工作", [
        ("攻击者", "在隔离环境里尝试允许的攻击路径，只能使用声明过的工具。", COLORS["red"], art / "cards" / "attacker.webp"),
        ("目标与实验场", "运行真实目标服务并藏入随机标记；每轮实验绑定一个具体发现。", COLORS["gold"], art / "cards" / "victim-lab.webp"),
        ("独立审查员", "不参与攻击，只检查过程、标记来源和能否复现；不支持的场景直接停下。", COLORS["blue"], art / "cards" / "judge.webp"),
    ], footer="红队不是单个“攻击模型”，而是一套能执行、能隔离、能复查的实验流程"))
    evidence_art = ROOT / "docs" / "visuals" / "redteam-evidence"
    slides.append(deck.visual_steps(14, "红队证据链：凭什么相信攻击真的成功？", [
        ("01 先把攻击者关好", "攻击者只能接触实验目标，不能控制宿主机，也碰不到预先藏好的标记。", COLORS["red"], evidence_art / "01-isolation.webp"),
        ("02 只认真实操作拿到的标记", "随机标记是预先藏好的；只有它出现在真实工具输出里才算，“我成功了”不算。", COLORS["gold"], evidence_art / "02-real-output.webp"),
        ("03 换一个人独立复核", "另一个审查员检查：打的是不是目标漏洞、标记从哪里来、有没有偷看或作弊。", COLORS["blue"], evidence_art / "03-independent-review.webp"),
        ("04 证据齐全才交给人", "真实标记、审查通过、图文报告，三项齐全，才进入人工验收。", COLORS["green"], evidence_art / "04-human-acceptance.webp"),
    ], "一句话：不听攻击者自己怎么说，只复查它做了什么、留下了什么证据"))
    slides.append(deck.flow(15, "实例：一个恶意配置文件怎样触发危险操作", [
        ("仓库藏入配置", "恶意 .env", COLORS["red"]),
        ("启动时加载", "危险 Git 设置被带入", COLORS["gold"]),
        ("系统自动保存", "触发 git add --all", COLORS["blue"]),
        ("配置被执行", "出现无害测试标记", COLORS["red"]),
    ], "已用无害标记验证这条机制；修复方向是清理危险 Git 配置并关闭自动执行入口", details=[
        ("问题在哪里", "不可信仓库配置被当成可信启动配置", COLORS["blue"]),
        ("为什么会触发", "系统自动保存，不需要受害者再点一次", COLORS["gold"]),
        ("学到了什么", "配置边界和自动操作必须一起审计", COLORS["green"]),
    ]))
    slides.append(deck.cards(16, "RSI 学什么：不是背报告，而是记住行动与后果", [
        ("当时知道什么", "保存发现身份和动作前的信息，不能偷看后来才出现的答案。", COLORS["blue"], art / "cards" / "identity-context.webp"),
        ("实际做了什么", "记录采取了哪个动作，以及花费的时间、调用次数和词元数。", COLORS["gold"], art / "cards" / "action-cost.webp"),
        ("结果有多可信", "静态分析、实际运行、独立审核和人工结论分开保存，不能互相冒充。", COLORS["green"], art / "cards" / "evidence-outcome.webp"),
    ], footer="只有这样，下一轮才能比较：哪个动作更值得，代价是否合适"))
    slides.append(deck.flywheel(17))
    slides.append(deck.cards(18, "RSI 每一环做什么：已实现与尚未实现", [
        ("01 整理经验与标签", "把行动、成本和结果整理成经验。\n运行与人工可信标签仍不足；静态分析不能冒充它们。", COLORS["blue"]),
        ("02 学习并独立考试", "比较不同动作的净收益，再拿留出项目考试。\n回放只是观测，不是因果证明。", COLORS["gold"]),
        ("03 只读建议", "验证动作只给建议，不自动改变流程。\n证据不足时，就停在这一步。", COLORS["muted"]),
        ("04 归纳重复失败", "把同类失败分组，寻找可改进的执行环节。\n但聚类不等于已经找到根因。", COLORS["red"]),
        ("05 生成挖掘修复", "按共享或仓库专属作用域生成候选，未经评估不发布。", COLORS["gold"]),
        ("06 评估后发布", "真实前后运行确认误报下降且无回归才发布；\n下一轮加载并可回滚。", COLORS["green"]),
    ], columns=3, footer="实现路径统一放在末页；这里先看清每一步能做什么、不能做什么", body_size=15, title_size=17))
    slides.append(deck.metrics(19, "真实现状：验证只读，挖掘修复受控发布", [
        ("0", "验证动作可信训练样本：保持只读", COLORS["red"]),
        ("分支", "挖掘修复独立评估、发布与加载", COLORS["gold"]),
        ("未证明", "还没有跨项目的可靠提升证据", COLORS["blue"]),
    ], ["先补真实运行、独立审核与人工标签，再讨论生产效果。", "留出项目是没参与训练的考试题；未评估候选不发布。"]))
    slides.append(deck.cards(20, "GoldMine 怎样逐步增强，而不是一步跳到自动修改", [
        ("短期：补齐真实经验", "积累真实验证和人工结论，让每个动作都能学到可靠结果。", COLORS["green"], art / "cards" / "short-term.webp"),
        ("中期：验证最小改进", "从重复失败生成修改候选，逐项检查是否修复、是否改坏旧能力。", COLORS["gold"], art / "cards" / "mid-term.webp"),
        ("长期：再研究模型更新", "证据充分后再更新模型，并重新匹配外部执行框架。", COLORS["red"], art / "cards" / "long-term.webp"),
    ], footer="始终先改有边界的执行策略，不做无约束自我修改"))
    slides.append(deck.cards(21, "算法团队的五个工作包", [
        ("01 经验数据", "把行动、成本、结果和来源整理成可学习的数据。", COLORS["blue"]),
        ("02 学习规则", "定义动作、收益和成本，学会比较不同选择。", COLORS["gold"]),
        ("03 实验环境", "搭建可重复的红队场景，保留真实结果与失败原因。", COLORS["red"]),
        ("04 独立评估", "检查证据是否可靠，并提供人工复核入口。", COLORS["green"]),
        ("05 安全发布", "用独立考试、逐项回归和回滚机制管住改进。", COLORS["blue"]),
    ], columns=3, footer="开发团队提供稳定平台，安全团队提供专业判断，算法团队让经验可信地转化为改进"))
    slides.append(deck.cards(22, "建议的 90 天验收目标", [
        ("可信数据", "至少覆盖 3 个独立项目，持续增加真实运行、审核与人工标签。", COLORS["green"]),
        ("动作覆盖", "完成 100+ 条动作标签，覆盖验证、深读和人工复核。", COLORS["gold"]),
        ("发布证据", "有新项目考试、逐项修复与回归对照，不只看平均分。", COLORS["blue"]),
        ("红队扩展", "为更多协议实现真实执行器；不支持时明确停下，不伪装成功。", COLORS["red"]),
    ], columns=2, footer="这些是建议目标，不是当前完成度；证据不足时继续保持只读建议"))
    slides.append(deck.hero(
        23, "让每一次批量审计，都成为下一次更好的证据",
        ["对分析人员：更少重复搭建，更清晰的证据与趣味化表达", "对算法团队：可学习、可评估、可比较的策略学习循环", "对组织：每次成功与失败都沉淀为安全研究资产"],
        art / "learning.webp", "GoldMine = 安全研究 × 算法学习 × 工程化证据链",
    ))
    slides.append(deck.cards(24, "论文与实现依据", [
        ("Self-Harness / AgentDevel", "arxiv.org/abs/2606.09498\narxiv.org/abs/2601.04620", COLORS["gold"]),
        ("MASS / HELIX", "arxiv.org/abs/2610.12176\narxiv.org/abs/2608.13951", COLORS["blue"]),
        ("DiscoveryRSI / 综述", "arxiv.org/abs/2610.23839\narxiv.org/abs/2607.07663", COLORS["green"]),
        ("实现", "audit_rsi/ · scripts/redteam/\nscripts/mine/ · scripts/env/sandbox.sh\n.claude/agents/ · .claude/skills/", COLORS["muted"]),
    ], columns=2, footer="研究笔记：docs/goldmine-rsi-research-2026.md；实现契约：docs/system-architecture.md"))

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    content_types = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        '<Default Extension="jpg" ContentType="image/jpeg"/>',
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/ppt/presProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presProps+xml"/>',
        '<Override PartName="/ppt/viewProps.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.viewProps+xml"/>',
        '<Override PartName="/ppt/tableStyles.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.tableStyles+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>']
    content_types += [f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i in range(1, len(slides) + 1)]
    content_types.append('</Types>')

    presentation_rels = [("rId1", "slideMaster", "slideMasters/slideMaster1.xml")]
    presentation_rels += [(f"rId{i + 1}", "slide", f"slides/slide{i}.xml") for i in range(1, len(slides) + 1)]
    slide_ids = "".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, len(slides) + 1))
    presentation = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{emu(W)}" cy="{emu(H)}"/><p:notesSz cx="6858000" cy="9144000"/><p:defaultTextStyle/>
</p:presentation>'''
    master = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>{base_tree()}</p:spTree></p:cSld><p:clrMap accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" bg1="lt1" bg2="lt2" folHlink="folHlink" hlink="hlink" tx1="dk1" tx2="dk2"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>'''
    layout = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree>{base_tree()}</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>'''
    theme = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="GoldMine"><a:themeElements><a:clrScheme name="GoldMine"><a:dk1><a:srgbClr val="202020"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="444444"/></a:dk2><a:lt2><a:srgbClr val="F7F4ED"/></a:lt2><a:accent1><a:srgbClr val="D99A17"/></a:accent1><a:accent2><a:srgbClr val="356B8C"/></a:accent2><a:accent3><a:srgbClr val="32735A"/></a:accent3><a:accent4><a:srgbClr val="B84635"/></a:accent4><a:accent5><a:srgbClr val="666666"/></a:accent5><a:accent6><a:srgbClr val="F5E7B8"/></a:accent6><a:hlink><a:srgbClr val="356B8C"/></a:hlink><a:folHlink><a:srgbClr val="666666"/></a:folHlink></a:clrScheme><a:fontScheme name="GoldMine"><a:majorFont><a:latin typeface="Noto Sans CJK SC"/><a:ea typeface="Noto Sans CJK SC"/><a:cs typeface=""/></a:majorFont><a:minorFont><a:latin typeface="Noto Sans CJK SC"/><a:ea typeface="Noto Sans CJK SC"/><a:cs typeface=""/></a:minorFont></a:fontScheme><a:fmtScheme name="GoldMine"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="12700"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'''

    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("[Content_Types].xml", "".join(content_types))
        package.writestr("_rels/.rels", rels_xml([
            ("rId1", "officeDocument", "ppt/presentation.xml"),
            ("rId2", "metadata/core-properties", "docProps/core.xml"),
            ("rId3", "extended-properties", "docProps/app.xml"),
        ]))
        package.writestr("docProps/core.xml", f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>GoldMine：从候选问题到可信证据</dc:title><dc:creator>Algorithm Team</dc:creator><cp:lastModifiedBy>Algorithm Team</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>''')
        package.writestr("docProps/app.xml", f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>GoldMine Builder</Application><Slides>{len(slides)}</Slides></Properties>''')
        package.writestr("ppt/presentation.xml", presentation)
        package.writestr("ppt/_rels/presentation.xml.rels", rels_xml(presentation_rels))
        package.writestr("ppt/slideMasters/slideMaster1.xml", master)
        package.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", rels_xml([
            ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
            ("rId2", "theme", "../theme/theme1.xml"),
        ]))
        package.writestr("ppt/slideLayouts/slideLayout1.xml", layout)
        package.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", rels_xml([
            ("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")
        ]))
        package.writestr("ppt/theme/theme1.xml", theme)
        package.writestr("ppt/presProps.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentationPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')
        package.writestr("ppt/viewProps.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:viewPr xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>')
        package.writestr("ppt/tableStyles.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:tblStyleLst xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" def=""/>')
        for index, (xml, relationships) in enumerate(slides, 1):
            package.writestr(f"ppt/slides/slide{index}.xml", xml)
            package.writestr(f"ppt/slides/_rels/slide{index}.xml.rels", rels_xml(relationships))
        for image in deck.media:
            package.write(image, f"ppt/media/{image.name}")
    print(f"{OUT} ({len(slides)} slides)")


if __name__ == "__main__":
    build()
