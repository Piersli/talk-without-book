"""
render_html.py — 读后无书 · 全产出物 HTML 渲染器

设计原则
- markdown 是源，HTML 只是派生视图（Agent 和人类共用同一 markdown）
- 风格沿用《每日斯多葛》的安静纸质感：奶白底、衬线字、宽白边、窄列
- 零外部依赖，只用 Python stdlib
- 站点结构：

    $TWB_ROOT/site/
    ├── index.html               今日之道 · 浸泡（入口）
    ├── dao/
    │   ├── index.html           所有的道（总览）
    │   └── 道N.html             单条道的深度页
    ├── books/
    │   ├── index.html           书架
    │   └── {BookName}/
    │       └── index.html       一本书的全部节点
    ├── journal/
    │   ├── index.html           浸泡记录总览
    │   └── 道N.html             单条道的浸泡轨迹
    └── _assets/
        └── style.css            共享样式

用法：
    python render_html.py $TWB_ROOT
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ────────────────────────────────────────────────


@dataclass
class Dao:
    id: int
    title: str                                       # 不含编号
    category: str
    description: str
    questions: list[str] = field(default_factory=list)
    books: list[str] = field(default_factory=list)   # 原始 markdown 行
    laws_line: str = ""
    relations: str = ""
    journal_entries: list[tuple[str, str, str]] = field(default_factory=list)
    # (timestamp, question_or_None, body)


@dataclass
class Node:
    """法/术/器/势 的单个节点"""
    dim: str                                          # 法/术/器/势
    id: str                                           # "法1"、"术1" 或派生 "节点1"
    title: str
    subtitle: str = ""                                # "—" 之后的副标题
    fields: list[tuple[str, str]] = field(default_factory=list)  # [(field_name, value), ...]


@dataclass
class Book:
    name: str                                         # Same_as_Ever
    display_name: str = ""                            # 《Same as Ever》— xxx
    author: str = ""
    meta_text: str = ""                               # 原 meta.md 全文
    fa: list[Node] = field(default_factory=list)
    shu: list[Node] = field(default_factory=list)
    qi: list[Node] = field(default_factory=list)
    shi: list[Node] = field(default_factory=list)


# ── 解析器 ──────────────────────────────────────────────────


def parse_dao_md(path: Path) -> list[Dao]:
    text = path.read_text(encoding="utf-8")
    sections = re.split(r'(?m)^## 道(\d+)：', text)
    daos: list[Dao] = []
    for i in range(1, len(sections), 2):
        dao_id = int(sections[i])
        body = sections[i + 1] if i + 1 < len(sections) else ""
        daos.append(_parse_dao_section(dao_id, body))
    daos.sort(key=lambda d: d.id)
    return daos


def _parse_dao_section(dao_id: int, body: str) -> Dao:
    lines = body.split("\n")
    title = lines[0].strip() if lines else f"道{dao_id}"
    rest = "\n".join(lines[1:])

    dao = Dao(id=dao_id, title=title, category="", description="")
    dao.category = _extract_field(rest, "类别")
    dao.description = _extract_field(rest, "表述")
    dao.questions = _extract_list_field(rest, "检索问题")
    dao.books = _extract_list_field(rest, "触碰此道的书籍")
    dao.laws_line = _extract_field(rest, "下位法")
    dao.relations = _extract_field(rest, "与其他道的关系")
    return dao


def _extract_field(text: str, name: str) -> str:
    m = re.search(
        rf'^- \*\*{re.escape(name)}\*\*：\s*(.+?)(?=\n- |\n---|\Z)',
        text, re.MULTILINE | re.DOTALL
    )
    return m.group(1).strip() if m else ""


def _extract_list_field(text: str, name: str) -> list[str]:
    m = re.search(
        rf'^- \*\*{re.escape(name)}\*\*：\s*\n((?:  - .*\n?)+)',
        text, re.MULTILINE
    )
    if not m:
        return []
    return [x.strip() for x in re.findall(r'^  - (.+)', m.group(1), re.MULTILINE)]


# Book / Node parsers ----------------------------------------------------------


def parse_book_dir(book_dir: Path) -> Book:
    name = book_dir.name
    book = Book(name=name)

    meta_path = book_dir / "meta.md"
    if meta_path.exists():
        book.meta_text = meta_path.read_text(encoding="utf-8")
        # 抓 display_name & author（从前两行 quote）
        for line in book.meta_text.splitlines()[:10]:
            if "**书名**" in line:
                book.display_name = re.sub(r'^>?\s*\*\*书名\*\*[:：]\s*', '', line).strip()
            elif "**作者**" in line:
                book.author = re.sub(r'^>?\s*\*\*作者\*\*[:：]\s*', '', line).strip()

    for dim, attr in [("法", "fa"), ("术", "shu"), ("器", "qi"), ("势", "shi")]:
        p = book_dir / f"{dim}.md"
        if p.exists():
            setattr(book, attr, parse_nodes(p, dim))

    return book


def parse_nodes(md_path: Path, dim: str) -> list[Node]:
    """解析法/术/器/势 markdown，返回节点列表"""
    text = md_path.read_text(encoding="utf-8")
    nodes: list[Node] = []

    # 先按 `## ` 切（除去文件头）
    sections = re.split(r'(?m)^## ', text)
    sequential = 1
    for sec in sections[1:]:  # sections[0] 是前置说明
        sec = sec.strip()
        if not sec:
            continue
        # 跳过"上位道索引"等元数据节
        first_line = sec.split('\n', 1)[0].strip()
        if first_line in ("上位道索引", "上位法索引", "上位术索引", "目录"):
            continue

        node = _parse_node_section(sec, dim, sequential)
        if node:
            nodes.append(node)
            sequential += 1
    return nodes


def _parse_node_section(section: str, dim: str, fallback_seq: int) -> Node | None:
    """解析单个节点 section"""
    lines = section.split('\n')
    if not lines:
        return None

    header = lines[0].strip()
    # 编号形式："法1：标题 — 副标题"
    m = re.match(rf'^({dim}\d+)[：:]\s*(.+?)(?:\s*[—–-]\s*(.+))?$', header)
    if m:
        node_id = m.group(1)
        title = m.group(2).strip()
        subtitle = (m.group(3) or "").strip()
    else:
        # 无编号形式：直接是标题
        # 尝试拆 "标题 — 副标题"
        sub_m = re.match(r'^(.+?)\s*[—–-]\s*(.+)$', header)
        if sub_m:
            title = sub_m.group(1).strip()
            subtitle = sub_m.group(2).strip()
        else:
            title = header
            subtitle = ""
        node_id = f"{dim}{fallback_seq}"

    # 抓字段 "- **xxx**：yyy"
    rest = "\n".join(lines[1:])
    field_pairs: list[tuple[str, str]] = []
    for m in re.finditer(
        r'^- \*\*(.+?)\*\*[：:]\s*(.+?)(?=\n- \*\*|\n---|\Z)',
        rest, re.MULTILINE | re.DOTALL
    ):
        field_pairs.append((m.group(1).strip(), m.group(2).strip()))

    return Node(dim=dim, id=node_id, title=title, subtitle=subtitle, fields=field_pairs)


# Journal parser ---------------------------------------------------------------


def load_journal(journal_dir: Path, dao: Dao) -> None:
    f = journal_dir / f"道{dao.id}.md"
    if not f.exists():
        return
    text = f.read_text(encoding="utf-8")
    entries = re.split(r'(?m)^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\n', text)
    for i in range(1, len(entries), 2):
        ts = entries[i].strip()
        body = entries[i + 1] if i + 1 < len(entries) else ""
        q_match = re.search(r'\*\*问：\*\*\s*(.+?)(?=\n\n\*\*答：\*\*)', body, re.DOTALL)
        a_match = re.search(r'\*\*答：\*\*\s*(.+?)(?=\n\n|\Z)', body, re.DOTALL)
        if q_match and a_match:
            dao.journal_entries.append((ts, q_match.group(1).strip(), a_match.group(1).strip()))
        else:
            dao.journal_entries.append((ts, "", body.strip()))
    dao.journal_entries.sort(key=lambda e: e[0], reverse=True)


# 今日选取 ----------------------------------------------------------------------


def pick_today(daos: list[Dao]) -> tuple[Dao, str]:
    today = dt.date.today()
    doy = today.timetuple().tm_yday
    idx = doy % len(daos)
    today_dao = daos[idx]
    question = ""
    if today_dao.questions:
        q_idx = (doy // len(daos)) % len(today_dao.questions)
        question = today_dao.questions[q_idx]
    return today_dao, question


def read_today_state(root: Path) -> tuple[str, int, str] | None:
    f = root / ".state" / "today.tsv"
    if not f.exists():
        return None
    try:
        parts = f.read_text().strip().split("\t")
        if len(parts) == 3:
            return parts[0], int(parts[1]), parts[2]
    except Exception:
        pass
    return None


# ── 共享 CSS ────────────────────────────────────────────────


CSS = """
:root {
  --bg: #fdfaf4;
  --fg: #1a1a1f;
  --fg-dim: #6b6860;
  --fg-faint: #aaa69c;
  --accent: #8b6508;
  --rule: #d9d3c4;
  --quote-bg: #f5efe2;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14120e;
    --fg: #e6e1d5;
    --fg-dim: #9a9489;
    --fg-faint: #5c584f;
    --accent: #d4a44a;
    --rule: #2a2820;
    --quote-bg: #1c1a14;
  }
}

* { box-sizing: border-box; }

html, body {
  margin: 0; padding: 0;
  background: var(--bg); color: var(--fg);
  font-family: "Songti SC", "Noto Serif CJK SC", "Source Han Serif SC", "PingFang SC",
               Georgia, "Times New Roman", serif;
  line-height: 1.9;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.page {
  max-width: 620px;
  margin: 0 auto;
  padding: 56px 32px 120px;
}
.page-wide {
  max-width: 760px;
  margin: 0 auto;
  padding: 56px 32px 120px;
}

/* 顶栏 */
.topnav {
  font-family: -apple-system, "PingFang SC", sans-serif;
  font-size: 12px;
  color: var(--fg-faint);
  text-align: center;
  margin-bottom: 64px;
  letter-spacing: 2px;
}
.topnav a {
  color: var(--fg-dim);
  text-decoration: none;
  margin: 0 6px;
}
.topnav a:hover { color: var(--fg); }
.topnav a.active { color: var(--accent); font-weight: 600; }
.topnav .sep { color: var(--rule); margin: 0 2px; }

/* 通用 */
.rule {
  border: none;
  border-top: 1px solid var(--rule);
  margin: 56px auto;
  width: 120px;
}
.label {
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 3px;
  color: var(--fg-dim);
  text-transform: uppercase;
  margin-bottom: 16px;
}
.label-center { text-align: center; }

a { color: var(--accent); }
a:hover { opacity: 0.85; }

/* 日期头（today 页用）*/
.dateline { text-align: center; margin-bottom: 64px; color: var(--fg-dim); }
.dateline .year {
  font-size: 12px; letter-spacing: 6px;
  text-transform: uppercase;
  color: var(--fg-faint);
  margin-bottom: 8px;
  font-family: -apple-system, sans-serif;
}
.dateline .date-main {
  font-size: 44px; font-weight: 300;
  color: var(--fg); line-height: 1;
  letter-spacing: 2px;
}
.dateline .weekday {
  font-size: 13px; letter-spacing: 3px;
  margin-top: 12px; color: var(--fg-dim);
  font-family: -apple-system, sans-serif;
}

/* 道编号、标题、类别 */
.dao-id {
  text-align: center;
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 4px;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 24px;
}
.dao-title {
  font-size: 32px;
  line-height: 1.5;
  font-weight: 400;
  text-align: center;
  margin: 0 0 12px;
  color: var(--fg);
  letter-spacing: 1px;
}
.dao-category {
  text-align: center;
  font-size: 12px; color: var(--fg-dim);
  font-family: -apple-system, sans-serif;
  letter-spacing: 2px;
  margin-bottom: 48px;
}

/* 主体阅读区 */
.dao-desc {
  font-size: 18px;
  line-height: 2.0;
  color: var(--fg);
  margin: 32px 0;
  text-align: justify;
  text-justify: inter-ideograph;
}
.dao-desc p {
  margin: 0 0 20px;
  text-indent: 2em;
}

/* 提问块 */
.question-block {
  margin: 56px 0;
  padding: 32px 28px;
  background: var(--quote-bg);
  border-left: 3px solid var(--accent);
}
.question-block .q {
  font-size: 19px;
  line-height: 1.8;
  color: var(--fg);
  margin: 0 0 20px;
}
.question-block .cta {
  font-family: "SF Mono", ui-monospace, monospace;
  font-size: 12px;
  color: var(--fg-dim);
  padding-top: 14px;
  border-top: 1px solid var(--rule);
}
.question-block .cta code {
  color: var(--accent); font-weight: 500;
}

/* journal */
.journal { margin: 56px 0; }
.entry {
  margin: 28px 0;
  padding: 0 0 24px;
  border-bottom: 1px dashed var(--rule);
}
.entry:last-child { border-bottom: none; }
.entry .ts {
  font-family: -apple-system, sans-serif;
  font-size: 11px; color: var(--fg-faint);
  letter-spacing: 1px;
  margin-bottom: 12px;
}
.entry .q-line {
  font-size: 14px;
  color: var(--fg-dim);
  font-style: italic;
  margin-bottom: 10px;
}
.entry .a-line {
  font-size: 16px;
  line-height: 1.9;
  color: var(--fg);
}

.empty {
  text-align: center;
  font-family: -apple-system, sans-serif;
  font-size: 13px;
  color: var(--fg-dim);
  padding: 24px 0;
  font-style: italic;
}

/* sources */
.sources { margin: 56px 0 32px; font-size: 14px; color: var(--fg-dim); line-height: 1.8; }
.sources ul { list-style: none; padding: 0; margin: 0; }
.sources li {
  margin: 8px 0; padding-left: 20px; position: relative;
}
.sources li::before {
  content: "·"; position: absolute; left: 8px; color: var(--fg-faint);
}

/* 列表/总览页 */
.list-grid { display: flex; flex-direction: column; gap: 0; }
.list-item {
  padding: 24px 0;
  border-bottom: 1px solid var(--rule);
  text-decoration: none;
  color: var(--fg);
  display: block;
}
.list-item:last-child { border-bottom: none; }
.list-item:hover { background: var(--quote-bg); margin: 0 -24px; padding: 24px; }
.list-item .item-id {
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 3px;
  color: var(--accent);
  text-transform: uppercase;
}
.list-item .item-title {
  font-size: 20px; line-height: 1.5; margin: 8px 0 4px;
  font-weight: 400;
}
.list-item .item-meta {
  font-family: -apple-system, sans-serif;
  font-size: 12px; color: var(--fg-dim);
}

/* 节点（法/术/器/势）卡片 */
.node-section {
  margin: 56px 0;
}
.node-section > .label-section {
  font-family: -apple-system, sans-serif;
  font-size: 14px; letter-spacing: 4px;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 32px;
  text-align: center;
}
.node {
  margin: 32px 0;
  padding-bottom: 24px;
  border-bottom: 1px dashed var(--rule);
}
.node:last-child { border-bottom: none; }
.node .node-id {
  font-family: -apple-system, sans-serif;
  font-size: 11px; color: var(--accent);
  letter-spacing: 2px;
}
.node .node-title {
  font-size: 19px; line-height: 1.6;
  margin: 6px 0 4px; font-weight: 500;
}
.node .node-subtitle {
  font-size: 14px; color: var(--fg-dim);
  font-style: italic;
  margin-bottom: 14px;
}
.node .node-field {
  margin: 10px 0;
  font-size: 14px;
  line-height: 1.85;
}
.node .node-field .field-name {
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 2px;
  color: var(--accent);
  text-transform: uppercase;
  display: inline-block;
  min-width: 80px;
  vertical-align: top;
}
.node .node-field .field-value {
  color: var(--fg);
  display: inline;
}

/* meta 表格（书页头部）*/
.book-header {
  margin-bottom: 56px;
  text-align: center;
}
.book-header .book-name {
  font-size: 28px;
  font-weight: 400;
  margin: 0 0 8px;
  letter-spacing: 1px;
}
.book-header .book-author {
  font-size: 14px; color: var(--fg-dim);
  font-family: -apple-system, sans-serif;
  letter-spacing: 2px;
}
.book-meta-content {
  background: var(--quote-bg);
  padding: 24px 28px;
  margin: 32px 0;
  font-size: 14px;
  line-height: 1.9;
}
.book-meta-content table {
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
}
.book-meta-content th, .book-meta-content td {
  padding: 6px 10px;
  text-align: left;
  border-bottom: 1px solid var(--rule);
  font-size: 13px;
}
.book-meta-content th {
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 2px;
  color: var(--accent);
  text-transform: uppercase;
}

/* TOC（书页内的法/术/器/势 锚点导航）*/
.toc {
  font-family: -apple-system, sans-serif;
  font-size: 12px; color: var(--fg-dim);
  text-align: center;
  margin: 0 0 56px;
  letter-spacing: 2px;
}
.toc a { color: var(--accent); text-decoration: none; margin: 0 12px; }

/* 脚注 */
.footer {
  text-align: center;
  margin-top: 96px;
  font-family: -apple-system, sans-serif;
  font-size: 11px;
  color: var(--fg-faint);
  letter-spacing: 1px;
  line-height: 1.8;
}
.footer a { color: var(--fg-dim); }
.footer code {
  background: var(--quote-bg);
  padding: 2px 8px; border-radius: 2px;
  color: var(--fg-dim);
}

::selection { background: var(--accent); color: var(--bg); }

@media (max-width: 600px) {
  .page, .page-wide { padding: 40px 20px 80px; }
  .dateline .date-main { font-size: 36px; }
  .dao-title { font-size: 26px; }
  .dao-desc { font-size: 16px; }
  .question-block { padding: 24px 20px; }
  .question-block .q { font-size: 17px; }
  .node-section > .label-section { font-size: 12px; }
  .node .node-title { font-size: 17px; }
}
"""


# ── HTML 模板 ───────────────────────────────────────────────


def html_shell(title: str, body: str, css_rel_path: str,
               nav_active: str = "", wide: bool = False) -> str:
    """完整 HTML 文档外壳"""
    nav = _topnav(css_rel_path, nav_active)
    page_class = "page-wide" if wide else "page"
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{css_rel_path}">
</head>
<body>
  <div class="{page_class}">
    {nav}
    {body}
  </div>
</body>
</html>
"""


def _topnav(css_rel_path: str, active: str) -> str:
    """根据 CSS 路径推断当前页深度，生成相对链接"""
    # css_rel_path 形如 "_assets/style.css" 或 "../_assets/style.css"
    depth = css_rel_path.count("../")
    prefix = "../" * depth

    items = [
        ("today",   "index.html",         "今日"),
        ("dao",     "dao/index.html",     "道"),
        ("books",   "books/index.html",   "书"),
        ("journal", "journal/index.html", "浸泡"),
    ]
    parts = []
    for key, path, label in items:
        cls = ' class="active"' if key == active else ""
        parts.append(f'<a href="{prefix}{path}"{cls}>{label}</a>')
    sep = '<span class="sep">·</span>'
    return f'<nav class="topnav">{sep.join(parts)}</nav>'


def _auto_link_dao_refs(text: str, current_dao_id: int | None = None,
                        link_prefix: str = "") -> str:
    """把 '道N' 转为链接（指向道页）"""
    def repl(m):
        n = m.group(1)
        if current_dao_id is not None and int(n) == current_dao_id:
            return f"道{n}"  # 自指不链接
        return f'<a href="{link_prefix}道{n}.html">道{n}</a>'
    return re.sub(r'道(\d+)', repl, text)


def _split_desc_paragraphs(desc: str) -> list[str]:
    """按句号自然分段"""
    sentences = [s.strip() for s in re.split(r'(?<=。)', desc) if s.strip()]
    if len(sentences) <= 2:
        return [desc]
    per_para = max(2, len(sentences) // 3 + (1 if len(sentences) % 3 else 0))
    return ["".join(sentences[i:i + per_para]) for i in range(0, len(sentences), per_para)]


# ── 页面渲染 ────────────────────────────────────────────────


def render_today(dao: Dao, question: str, date_info: dict, has_journal: bool) -> str:
    paras = _split_desc_paragraphs(dao.description)
    desc_html = "".join(f'<p>{html.escape(p)}</p>' for p in paras)

    question_block = ""
    if question:
        question_block = f"""
        <div class="question-block">
          <div class="label">今日提问</div>
          <div class="q">{html.escape(question)}</div>
          <div class="cta">一句话回应：<code>cc note {dao.id} "..."</code></div>
        </div>
        """

    journal_block = ""
    if dao.journal_entries:
        parts = []
        for ts, q, body in dao.journal_entries[:3]:
            q_line = f'<div class="q-line">问：{html.escape(q)}</div>' if q else ""
            a_line = f'<div class="a-line">{html.escape(body).replace(chr(10), "<br>")}</div>'
            parts.append(
                f'<div class="entry">'
                f'<div class="ts">{html.escape(ts)}</div>'
                f'{q_line}{a_line}</div>'
            )
        more_link = ""
        if len(dao.journal_entries) > 3:
            more_link = f'<p style="text-align:center;margin-top:16px"><a href="journal/道{dao.id}.html" style="font-size:13px">查看全部 {len(dao.journal_entries)} 条 →</a></p>'
        journal_block = f"""
        <hr class="rule">
        <section class="journal">
          <div class="label label-center">你对这条道的过往回响</div>
          {''.join(parts)}
          {more_link}
        </section>
        """
    else:
        journal_block = """
        <hr class="rule">
        <section class="journal">
          <div class="label label-center">你对这条道的过往回响</div>
          <div class="empty">还没有。今天是第一次。</div>
        </section>
        """

    deep_link = f'<p style="text-align:center;margin-top:24px"><a href="dao/道{dao.id}.html" style="font-size:13px">深入这条道 →</a></p>'

    return f"""
    <div class="dateline">
      <div class="year">{date_info['year']}</div>
      <div class="date-main">{date_info['month']}月 · {date_info['day']}日</div>
      <div class="weekday">{date_info['weekday']}</div>
    </div>

    <div class="dao-id">道 · {dao.id}</div>
    <h1 class="dao-title">{html.escape(dao.title)}</h1>
    <div class="dao-category">{html.escape(dao.category)}</div>

    <div class="dao-desc">{desc_html}</div>

    {question_block}

    {deep_link}

    {journal_block}

    <div class="footer">
      读后无书 · talk without book<br>
      <code>cc dao</code> 终端重看 · <code>cc note</code> 沉淀回响
    </div>
    """


def render_dao_overview(daos: list[Dao]) -> str:
    """所有的道 · 总览页"""
    items = []
    for d in daos:
        journal_n = len(d.journal_entries)
        meta_bits = [d.category]
        if journal_n:
            meta_bits.append(f"{journal_n} 条浸泡")
        meta = " · ".join(meta_bits)
        items.append(f"""
        <a class="list-item" href="道{d.id}.html">
          <div class="item-id">道 · {d.id}</div>
          <div class="item-title">{html.escape(d.title)}</div>
          <div class="item-meta">{html.escape(meta)}</div>
        </a>
        """)

    return f"""
    <div class="dao-id">总览</div>
    <h1 class="dao-title">所有的道</h1>
    <div class="dao-category">{len(daos)} 条 · 永恒不变的底层真相</div>

    <div class="list-grid">
      {''.join(items)}
    </div>

    <div class="footer">读后无书 · talk without book</div>
    """


def render_dao_page(dao: Dao, link_prefix: str = "") -> str:
    """单条道的深度页"""
    paras = _split_desc_paragraphs(dao.description)
    desc_html = "".join(f'<p>{html.escape(p)}</p>' for p in paras)

    # 检索问题
    q_html = ""
    if dao.questions:
        q_items = "".join(f'<li>{html.escape(q)}</li>' for q in dao.questions)
        q_html = f"""
        <hr class="rule">
        <section>
          <div class="label label-center">检索问题</div>
          <ul style="list-style:none;padding:0;margin:0;font-size:15px;line-height:1.9">
            {q_items}
          </ul>
        </section>
        """

    # 触碰书籍
    books_html = ""
    if dao.books:
        book_items = "".join(
            f'<li>{html.escape(b)}</li>' for b in dao.books
        )
        books_html = f"""
        <hr class="rule">
        <section class="sources">
          <div class="label label-center">触碰此道的书籍</div>
          <ul>{book_items}</ul>
        </section>
        """

    # 与其他道的关系
    rel_html = ""
    if dao.relations:
        rel_linked = _auto_link_dao_refs(html.escape(dao.relations),
                                          current_dao_id=dao.id,
                                          link_prefix=link_prefix)
        rel_html = f"""
        <hr class="rule">
        <section>
          <div class="label label-center">与其他道的关系</div>
          <p style="font-size:15px;line-height:1.9;color:var(--fg);text-align:justify">
            {rel_linked}
          </p>
        </section>
        """

    # 下位法
    laws_html = ""
    if dao.laws_line:
        laws_html = f"""
        <hr class="rule">
        <section>
          <div class="label label-center">下位法</div>
          <p style="font-size:14px;line-height:1.9;color:var(--fg-dim);text-align:center">
            {html.escape(dao.laws_line)}
          </p>
        </section>
        """

    # journal 入口
    journal_link = ""
    if dao.journal_entries:
        journal_link = f"""
        <hr class="rule">
        <p style="text-align:center"><a href="../journal/道{dao.id}.html" style="font-size:13px">浸泡记录 {len(dao.journal_entries)} 条 →</a></p>
        """

    return f"""
    <div class="dao-id">道 · {dao.id}</div>
    <h1 class="dao-title">{html.escape(dao.title)}</h1>
    <div class="dao-category">{html.escape(dao.category)}</div>

    <div class="dao-desc">{desc_html}</div>

    {q_html}
    {books_html}
    {rel_html}
    {laws_html}
    {journal_link}

    <div class="footer">读后无书 · talk without book</div>
    """


def render_book_overview(books: list[Book]) -> str:
    """书架（总览）"""
    if not books:
        body = '<div class="empty">还没有拆解过的书。<br>用 <code>twb:extract</code> 拆第一本。</div>'
    else:
        items = []
        for b in books:
            display = b.display_name or b.name
            total = len(b.fa) + len(b.shu) + len(b.qi) + len(b.shi)
            meta_bits = [f"法 {len(b.fa)}", f"术 {len(b.shu)}", f"器 {len(b.qi)}", f"势 {len(b.shi)}"]
            if b.author:
                items.append(f"""
                <a class="list-item" href="{b.name}/index.html">
                  <div class="item-id">{html.escape(b.author)}</div>
                  <div class="item-title">《{html.escape(display)}》</div>
                  <div class="item-meta">{' · '.join(meta_bits)} · 共 {total} 节点</div>
                </a>
                """)
            else:
                items.append(f"""
                <a class="list-item" href="{b.name}/index.html">
                  <div class="item-id">书</div>
                  <div class="item-title">《{html.escape(display)}》</div>
                  <div class="item-meta">{' · '.join(meta_bits)} · 共 {total} 节点</div>
                </a>
                """)
        body = f'<div class="list-grid">{"".join(items)}</div>'

    return f"""
    <div class="dao-id">总览</div>
    <h1 class="dao-title">书架</h1>
    <div class="dao-category">{len(books)} 本 · 拆解过的书</div>
    {body}
    <div class="footer">读后无书 · talk without book</div>
    """


def _render_nodes_section(dim_label: str, nodes: list[Node], anchor: str) -> str:
    if not nodes:
        return ""
    items = []
    for n in nodes:
        # 字段
        field_items = []
        for fname, fval in n.fields:
            # 道N 链接化
            fval_linked = _auto_link_dao_refs(html.escape(fval), link_prefix="../../dao/")
            field_items.append(
                f'<div class="node-field">'
                f'<span class="field-name">{html.escape(fname)}</span>'
                f'<span class="field-value">{fval_linked}</span>'
                f'</div>'
            )
        sub = f'<div class="node-subtitle">{html.escape(n.subtitle)}</div>' if n.subtitle else ""
        items.append(f"""
        <div class="node" id="{anchor}-{n.id}">
          <div class="node-id">{n.id}</div>
          <div class="node-title">{html.escape(n.title)}</div>
          {sub}
          {''.join(field_items)}
        </div>
        """)

    return f"""
    <section class="node-section" id="{anchor}">
      <div class="label-section">{dim_label} · {len(nodes)} 节点</div>
      {''.join(items)}
    </section>
    """


def render_book_page(book: Book) -> str:
    """一本书的全部节点"""
    display = book.display_name or book.name

    # meta
    meta_html = ""
    if book.meta_text:
        # 简单把 meta.md 转成 HTML：先去掉一级标题，做 markdown 表格转 HTML
        meta_body = re.sub(r'^# .+?\n', '', book.meta_text, count=1)
        # 简易 markdown 表格转 HTML
        meta_html = _simple_markdown_to_html(meta_body)
        meta_html = f'<div class="book-meta-content">{meta_html}</div>'

    # TOC
    toc_items = []
    for dim_label, nodes, anchor in [
        ("法", book.fa, "fa"),
        ("术", book.shu, "shu"),
        ("器", book.qi, "qi"),
        ("势", book.shi, "shi"),
    ]:
        if nodes:
            toc_items.append(f'<a href="#{anchor}">{dim_label} ({len(nodes)})</a>')
    toc = f'<nav class="toc">{" · ".join(toc_items)}</nav>' if toc_items else ""

    # 节点
    sections = ""
    sections += _render_nodes_section("法", book.fa, "fa")
    sections += _render_nodes_section("术", book.shu, "shu")
    sections += _render_nodes_section("器", book.qi, "qi")
    sections += _render_nodes_section("势", book.shi, "shi")

    return f"""
    <div class="book-header">
      <h1 class="book-name">《{html.escape(display)}》</h1>
      {f'<div class="book-author">{html.escape(book.author)}</div>' if book.author else ''}
    </div>

    {meta_html}

    {toc}

    {sections}

    <div class="footer">读后无书 · talk without book</div>
    """


def _simple_markdown_to_html(md: str) -> str:
    """非常基础的 markdown→HTML：>引用、表格、段落"""
    lines = md.split('\n')
    html_parts = []
    in_table = False
    table_rows = []

    for line in lines:
        line = line.rstrip()
        # 表格行
        if line.startswith('|') and line.endswith('|'):
            if not in_table:
                in_table = True
                table_rows = []
            # 跳过分隔行（|---|---|）
            if re.match(r'^\|[\s\-:|]+\|$', line):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            table_rows.append(cells)
            continue
        else:
            if in_table:
                # 输出表格
                if table_rows:
                    parts = ['<table>']
                    parts.append('<tr>' + ''.join(f'<th>{html.escape(c)}</th>' for c in table_rows[0]) + '</tr>')
                    for row in table_rows[1:]:
                        parts.append('<tr>' + ''.join(f'<td>{html.escape(c)}</td>' for c in row) + '</tr>')
                    parts.append('</table>')
                    html_parts.append(''.join(parts))
                in_table = False

        # > 引用
        if line.startswith('> '):
            content = line[2:].strip()
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html.escape(content))
            html_parts.append(f'<p style="color:var(--fg-dim);font-size:13px;margin:4px 0">{content}</p>')
        elif line.startswith('## '):
            html_parts.append(f'<h3 style="font-family:-apple-system,sans-serif;font-size:14px;letter-spacing:2px;color:var(--accent);margin-top:24px;text-transform:uppercase">{html.escape(line[3:])}</h3>')
        elif line.strip():
            content = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html.escape(line))
            html_parts.append(f'<p>{content}</p>')

    if in_table and table_rows:
        parts = ['<table>']
        parts.append('<tr>' + ''.join(f'<th>{html.escape(c)}</th>' for c in table_rows[0]) + '</tr>')
        for row in table_rows[1:]:
            parts.append('<tr>' + ''.join(f'<td>{html.escape(c)}</td>' for c in row) + '</tr>')
        parts.append('</table>')
        html_parts.append(''.join(parts))

    return '\n'.join(html_parts)


def render_journal_index(daos: list[Dao]) -> str:
    """浸泡记录总览（每条有 entry 的道）"""
    daos_with = [d for d in daos if d.journal_entries]
    if not daos_with:
        body = '<div class="empty">还没有任何浸泡记录。<br>当 banner 出现今日提问时，用 <code>cc note</code> 写第一笔。</div>'
    else:
        items = []
        for d in daos_with:
            latest = d.journal_entries[0][0] if d.journal_entries else ""
            items.append(f"""
            <a class="list-item" href="道{d.id}.html">
              <div class="item-id">道 · {d.id}</div>
              <div class="item-title">{html.escape(d.title)}</div>
              <div class="item-meta">{len(d.journal_entries)} 条 · 最近 {html.escape(latest)}</div>
            </a>
            """)
        body = f'<div class="list-grid">{"".join(items)}</div>'

    return f"""
    <div class="dao-id">总览</div>
    <h1 class="dao-title">浸泡记录</h1>
    <div class="dao-category">{len([d for d in daos if d.journal_entries])} 条道有回响</div>
    {body}
    <div class="footer">读后无书 · talk without book</div>
    """


def render_journal_page(dao: Dao) -> str:
    """单条道的浸泡轨迹"""
    if not dao.journal_entries:
        body = '<div class="empty">还没有。</div>'
    else:
        parts = []
        for ts, q, body_text in dao.journal_entries:
            q_line = f'<div class="q-line">问：{html.escape(q)}</div>' if q else ""
            a_line = f'<div class="a-line">{html.escape(body_text).replace(chr(10), "<br>")}</div>'
            parts.append(
                f'<div class="entry">'
                f'<div class="ts">{html.escape(ts)}</div>'
                f'{q_line}{a_line}</div>'
            )
        body = ''.join(parts)

    return f"""
    <div class="dao-id">道 · {dao.id}</div>
    <h1 class="dao-title">{html.escape(dao.title)}</h1>
    <div class="dao-category">{len(dao.journal_entries)} 条浸泡记录</div>

    <hr class="rule">

    <section class="journal">
      {body}
    </section>

    <div class="footer">
      <a href="../dao/道{dao.id}.html">← 回到道{dao.id} 深度页</a>
    </div>
    """


# ── 主入口 ──────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="读后无书 · 全产出物 HTML 渲染器"
    )
    parser.add_argument("root", type=Path,
                        help="知识库根目录（$TWB_ROOT），必须包含 dao/道.md")
    args = parser.parse_args()

    root: Path = args.root.resolve()
    site = root / "site"
    site.mkdir(parents=True, exist_ok=True)

    dao_file = root / "dao" / "道.md"
    if not dao_file.exists():
        print(f"✗ 找不到 {dao_file}", file=sys.stderr)
        return 1

    # 写 CSS
    assets = site / "_assets"
    assets.mkdir(exist_ok=True)
    (assets / "style.css").write_text(CSS, encoding="utf-8")
    print(f"  ✓ {assets / 'style.css'}")

    # 解析所有道
    print(f"  解析 {dao_file}...")
    daos = parse_dao_md(dao_file)
    print(f"    → {len(daos)} 条道")

    # 加载 journal
    journals_dir = root / "dao" / "journal"
    journal_count = 0
    if journals_dir.exists():
        for d in daos:
            load_journal(journals_dir, d)
            journal_count += len(d.journal_entries)
        print(f"    → {journal_count} 条 journal 记录")

    # 解析所有书
    books: list[Book] = []
    books_dir = root / "books"
    if books_dir.exists():
        for bd in sorted(books_dir.iterdir()):
            if bd.is_dir() and not bd.name.startswith("."):
                try:
                    book = parse_book_dir(bd)
                    books.append(book)
                    print(f"    → 书：{book.name} (法{len(book.fa)} 术{len(book.shu)} 器{len(book.qi)} 势{len(book.shi)})")
                except Exception as e:
                    print(f"    ⚠️ 解析 {bd.name} 失败：{e}")

    # 今日选取
    state = read_today_state(root)
    today_date = dt.date.today().isoformat()
    today_dao: Dao
    today_question: str
    if state and state[0] == today_date:
        _, sync_id, sync_q = state
        today_dao = next((d for d in daos if d.id == sync_id), daos[0])
        today_question = sync_q
        print(f"    → 同步 today.tsv：道{today_dao.id}")
    else:
        today_dao, today_question = pick_today(daos)
        print(f"    → 独立选取：道{today_dao.id}")

    today_obj = dt.date.today()
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today_obj.weekday()]
    date_info = {
        "year": today_obj.year,
        "month": today_obj.month,
        "day": today_obj.day,
        "weekday": weekday_cn,
    }

    # ── 渲染所有页 ──

    # index.html (today)
    body = render_today(today_dao, today_question, date_info, bool(today_dao.journal_entries))
    (site / "index.html").write_text(
        html_shell(f"{today_obj.month}月{today_obj.day}日 · 道{today_dao.id}",
                   body, "_assets/style.css", "today"),
        encoding="utf-8"
    )
    print(f"  ✓ site/index.html")

    # dao/index.html
    (site / "dao").mkdir(exist_ok=True)
    body = render_dao_overview(daos)
    (site / "dao" / "index.html").write_text(
        html_shell("所有的道", body, "../_assets/style.css", "dao"),
        encoding="utf-8"
    )
    print(f"  ✓ site/dao/index.html")

    # dao/道N.html
    for dao in daos:
        body = render_dao_page(dao)
        (site / "dao" / f"道{dao.id}.html").write_text(
            html_shell(f"道{dao.id}：{dao.title[:25]}", body,
                       "../_assets/style.css", "dao"),
            encoding="utf-8"
        )
    print(f"  ✓ site/dao/道N.html × {len(daos)}")

    # books/
    if books:
        (site / "books").mkdir(exist_ok=True)
        body = render_book_overview(books)
        (site / "books" / "index.html").write_text(
            html_shell("书架", body, "../_assets/style.css", "books"),
            encoding="utf-8"
        )
        for book in books:
            bdir = site / "books" / book.name
            bdir.mkdir(exist_ok=True)
            body = render_book_page(book)
            (bdir / "index.html").write_text(
                html_shell(f"《{book.display_name or book.name}》", body,
                           "../../_assets/style.css", "books", wide=True),
                encoding="utf-8"
            )
        print(f"  ✓ site/books/ × {len(books)} 本")
    else:
        # 空书架页
        (site / "books").mkdir(exist_ok=True)
        body = render_book_overview([])
        (site / "books" / "index.html").write_text(
            html_shell("书架", body, "../_assets/style.css", "books"),
            encoding="utf-8"
        )

    # journal/
    (site / "journal").mkdir(exist_ok=True)
    body = render_journal_index(daos)
    (site / "journal" / "index.html").write_text(
        html_shell("浸泡记录", body, "../_assets/style.css", "journal"),
        encoding="utf-8"
    )
    for dao in daos:
        if dao.journal_entries:
            body = render_journal_page(dao)
            (site / "journal" / f"道{dao.id}.html").write_text(
                html_shell(f"道{dao.id} · 浸泡", body,
                           "../_assets/style.css", "journal"),
                encoding="utf-8"
            )
    n_journal = sum(1 for d in daos if d.journal_entries)
    print(f"  ✓ site/journal/ × {n_journal + 1} 页")

    print(f"\n✓ 全部渲染完成 → {site}")
    print(f"  打开：open {site / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
