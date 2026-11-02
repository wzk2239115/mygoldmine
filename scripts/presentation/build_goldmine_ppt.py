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
FONT = "Noto Sans CJK SC"
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


def paragraph(text, size=20, color="202020", bold=False, bullet=False, space=500):
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

    def cards(self, number, title, cards, columns=3, footer=None):
        shapes, rels = [], []
        self.header(shapes, title, number)
        rows = (len(cards) + columns - 1) // columns
        card_w = (12.23 - (columns - 1) * 0.22) / columns
        card_h = 4.95 / rows - (rows - 1) * 0.2
        for index, (head, body, accent) in enumerate(cards):
            row, col = divmod(index, columns)
            x = 0.55 + col * (card_w + 0.22)
            y = 1.65 + row * (card_h + 0.2)
            shapes.append(rect(20 + index * 4, x, y, card_w, card_h, COLORS["white"], COLORS["line"]))
            shapes.append(rect(21 + index * 4, x, y, 0.06, card_h, accent, radius=False))
            shapes.append(text_box(22 + index * 4, x + 0.25, y + 0.25, card_w - 0.48, 0.5, head, size=18, color=accent, bold=True))
            shapes.append(text_box(23 + index * 4, x + 0.25, y + 0.88, card_w - 0.48, card_h - 1.08, body, size=15, color=COLORS["ink"]))
        if footer:
            shapes.append(text_box(90, 0.62, 6.75, 12.0, 0.35, footer, size=13, color=COLORS["muted"], bold=True))
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

    def flow(self, number, title, steps, footer):
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
        shapes.append(text_box(90, 0.62, 6.35, 12.0, 0.5, footer, size=14, color=COLORS["muted"], bold=True))
        return slide_xml(shapes), rels


def build():
    deck = Deck()
    art = ROOT / "ui" / "public" / "architecture"
    slides = []
    slides.append(deck.cover(
        1, "GoldMine\n从漏洞矿藏到可信证据",
        "RSI × 红队模型 × 可验证的算法闭环",
        ["发现 · 验证 · 学习 · 非回归发布", "算法团队 / 2026-11"],
        art / "overview.webp",
    ))
    slides.append(deck.hero(
        2, "不是“更会的扫描器”，而是安全研究闭环",
        ["目标源码 → 静态候选 → 持久沙箱验证", "红队证明 → 经验学习 → 受控发布", "Finding Ledger 保留每次发现与证据血缘"],
        art / "overview.webp", "核心：每次挖掘都能成为下一次更好的依据",
    ))
    slides.append(deck.cards(3, "为什么需要算法团队", [
        ("算法团队", "轨迹建模、策略与奖励、验证器、效用学习、跨项目泛化、RSI 发布门禁。", COLORS["gold"]),
        ("开发团队", "容器、API、UI、任务调度、可靠性与工程交付，让系统稳定可运行。", COLORS["blue"]),
        ("安全团队", "威胁情报、漏洞先验、规则、人工裁决与披露规范，让判断足够专业。", COLORS["red"]),
    ], footer="协作分工，不是能力高低；缺少算法闭环，系统只能重复固定规则。"))
    slides.append(deck.hero(
        4, "挖掘：先得到可追溯候选，而不是直接宣布漏洞",
        ["每个 run 独立，原始源码只读，工作副本可写", "持久沙箱复用依赖、工作区与产物，可继续 shell / verify", "Jev 只做召回；报告增量落盘并过质量门"],
        art / "mining.webp", "静态 finding 是研究假设，不是已成立漏洞",
    ))
    slides.append(deck.cards(5, "红队模型：不是单个“攻击模型”", [
        ("Attacker", "在受限容器中探索允许的攻击路径；模型策略与工具 harness 共同决定行为。", COLORS["red"]),
        ("Victim + Lab", "真实服务、随机 flag、内部网络；scenario 绑定 finding 与源码 hash。", COLORS["gold"]),
        ("Independent judge", "审核目标漏洞、证据、作弊风险与可复现性；HTTP 之外明确 blocked。", COLORS["blue"]),
    ], footer="红队能力 = 模型策略 + 执行 harness + 隔离 lab + 独立 judge + 可回放轨迹"))
    slides.append(deck.hero(
        6, "红队证据链：系统必须证明“确实发生了”",
        ["attacker 无宿主、无 Docker socket、无 flag 直读路径", "flag 只能来自真实工具输出，最终回答不是证据", "judge schema + 确定性 flag provenance 双重校验", "flag + approved + 图文报告，才进入人工验收"],
        art / "redteam.webp", "不是“模型说攻破了”，而是证据链支持这个结论",
    ))
    slides.append(deck.cards(7, "从轨迹到经验：RSI 的数据基础", [
        ("身份与上下文", "occurrence / semantic 双层身份；保存动作前上下文，避免未来信息泄漏。", COLORS["blue"]),
        ("动作与成本", "策略、propensity、agent/token/time 成本；确定性路由不被冒充为探索。", COLORS["gold"]),
        ("结果与证据", "static < runtime < judge < manual；来源 hash 与标签范围可审计。", COLORS["green"]),
    ], footer="verify / auto-state 已接入；redteam-experience 分离 run 结果与 attacker step，并复核 provenance"))
    steps = [
        ("轨迹", "真实动作与成本", COLORS["blue"]),
        ("标签 / 效用", "证据等级隔离", COLORS["gold"]),
        ("训练", "per-action utility", COLORS["green"]),
        ("Holdout", "跨项目验证", COLORS["red"]),
        ("Replay + Flips", "matched + outcome transitions", COLORS["blue"]),
        ("统计门禁", "coverage≥0.8 · fix≥1 · P→F=0", COLORS["gold"]),
        ("Shadow", "只读建议", COLORS["muted"]),
        ("受控发布", "不可变候选与回滚", COLORS["green"]),
    ]
    slides.append(deck.flow(8, "Goldmine 的 RSI 闭环", steps, "replay 与 outcome flips 都不宣称因果；证据不足时保持 shadow"))
    slides.append(deck.metrics(9, "真实现状：闭环已通，可信数据仍是瓶颈", [
        ("986", "occurrence 经验记录", COLORS["blue"]),
        ("6", "真实 static 动作样本（本轮前为 0）", COLORS["gold"]),
        ("0", "trusted support：生产继续拒绝", COLORS["red"]),
    ], ["当前只能叫 shadow RSI，不能宣称生产自我进化。", "下一阶段重点：runtime / judge 标签、动作覆盖与红队 lab 扩展。"]))
    slides.append(deck.cards(10, "2026 年研究地图：从自我反思走向受控闭环", [
        ("Self-Harness", "弱点聚类 → 最小 harness 修改 → held-out 非回归。", COLORS["gold"]),
        ("AgentDevel", "单版本线、可执行诊断、P→F / F→P flip 门禁。", COLORS["blue"]),
        ("MASS", "多智能体工作流搜索，优质团队轨迹回流训练。", COLORS["green"]),
        ("HELIX", "模型–harness 共进化，verified siblings 与证据平面。", COLORS["gold"]),
        ("DiscoveryRSI", "假设信用、workflow replay 与 rediscovery。", COLORS["blue"]),
        ("RSI 综述", "1,250 篇论文：验证层级、闭环程度与崩溃风险。", COLORS["red"]),
    ], columns=3, footer="论文结果用于指导设计，不直接外推为 Goldmine 的生产效果"))
    slides.append(deck.cards(11, "对 Goldmine 的技术选择", [
        ("短期", "真实标签、动作覆盖、逐 finding 非回归、跨项目 holdout；先让 shadow 学到真实经验。", COLORS["green"]),
        ("中期", "redteam-weakness 失败聚类、最小候选 harness、verified siblings 与统计验收。", COLORS["gold"]),
        ("长期", "证据充分后研究模型更新，并针对新能力画像重建匹配的 harness。", COLORS["red"]),
    ], footer="选择有边界的 harness RSI，不做无约束自我修改"))
    slides.append(deck.cards(12, "算法团队的五个工作包", [
        ("01 数据与身份", "轨迹、标签、成本、血缘与语义防泄漏。", COLORS["blue"]),
        ("02 策略与奖励", "动作效用、成本约束、探索与基线。", COLORS["gold"]),
        ("03 红队环境", "场景生成、执行协议、真实 flag 与失败分类。", COLORS["red"]),
        ("04 评估器", "judge、provenance、验证层级与人类复核接口。", COLORS["green"]),
        ("05 发布科学", "holdout、flip gate、bootstrap、版本与回滚。", COLORS["blue"]),
    ], columns=3, footer="开发团队与安全团队是这些工作包的共同交付伙伴"))
    slides.append(deck.cards(13, "建议的 90 天验收指标", [
        ("Trusted 数据", "至少 3 个独立项目；runtime / judge 样本持续增长。", COLORS["green"]),
        ("动作覆盖", "100+ 动作标签，覆盖 verify / deep_read / human_review。", COLORS["gold"]),
        ("发布证据", "跨项目 holdout、逐 finding P→F/F→P、基线对照。", COLORS["blue"]),
        ("红队扩展", "真实新协议执行器，不用 HTTP 包装冒充支持。", COLORS["red"]),
    ], columns=2, footer="这些是建议目标，不是当前完成度；门禁不满足时继续保持 shadow"))
    slides.append(deck.hero(
        14, "让每一次挖掘，都成为下一次更好的证据",
        ["对分析人员：更少重复搭建，更清晰的证据与趣味化表达", "对算法团队：可学习、可评估、可比较的策略闭环", "对组织：每次成功与失败都沉淀为安全研究资产"],
        art / "learning.webp", "GoldMine = 安全研究 × 算法学习 × 工程化证据链",
    ))
    slides.append(deck.cards(15, "论文与实现依据", [
        ("Self-Harness / AgentDevel", "arxiv.org/abs/2606.09498\narxiv.org/abs/2601.04620", COLORS["gold"]),
        ("MASS / HELIX", "arxiv.org/abs/2610.12176\narxiv.org/abs/2608.13951", COLORS["blue"]),
        ("DiscoveryRSI / 综述", "arxiv.org/abs/2610.23839\narxiv.org/abs/2607.07663", COLORS["green"]),
        ("实现", "audit_rsi/ · scripts/redteam/\nscripts/mine/ · scripts/env/sandbox.sh\ndocs/system-architecture.md", COLORS["muted"]),
    ], columns=2, footer="研究笔记：docs/goldmine-rsi-research-2026.md"))

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
        package.writestr("docProps/core.xml", f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>GoldMine：从漏洞矿藏到可信证据</dc:title><dc:creator>Algorithm Team</dc:creator><cp:lastModifiedBy>Algorithm Team</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">{now}</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">{now}</dcterms:modified></cp:coreProperties>''')
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
