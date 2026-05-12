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
import http.server
import json
import os
import re
import socketserver
import sys
import urllib.parse
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

/* 回应区域（草稿台）*/
.response-area {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid var(--rule);
}
.response-area-standalone {
  /* 独立草稿台（用在道页面，不在 question-block 里）*/
  margin: 56px 0;
  padding: 32px 28px;
  background: var(--quote-bg);
  border-left: 3px solid var(--accent);
  border-top: none;
}
.response-area-standalone > .label {
  margin-bottom: 16px;
}
.response-area textarea {
  width: 100%;
  min-height: 100px;
  border: 1px solid var(--rule);
  background: var(--bg);
  color: var(--fg);
  font-family: inherit;
  font-size: 16px;
  line-height: 1.85;
  padding: 14px 16px;
  border-radius: 2px;
  resize: vertical;
  margin-bottom: 14px;
  -webkit-font-smoothing: antialiased;
}
.response-area textarea:focus {
  outline: none;
  border-color: var(--accent);
}
.response-area textarea::placeholder {
  color: var(--fg-faint);
  font-style: italic;
}
.response-actions {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  font-family: -apple-system, "PingFang SC", sans-serif;
}
.response-area button {
  background: var(--accent);
  color: var(--bg);
  border: none;
  padding: 10px 18px;
  font-size: 12px;
  letter-spacing: 1px;
  cursor: pointer;
  font-family: -apple-system, "PingFang SC", sans-serif;
  font-weight: 500;
  border-radius: 2px;
  transition: opacity 0.15s;
}
.response-area button:hover {
  opacity: 0.85;
}
.response-area button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.response-area .hint {
  font-size: 11px;
  color: var(--fg-dim);
  letter-spacing: 0.5px;
}
.response-area .hint code {
  background: var(--bg);
  border: 1px solid var(--rule);
  padding: 1px 6px;
  font-size: 11px;
  color: var(--fg-dim);
  border-radius: 2px;
}
.response-area .copy-status {
  margin-top: 12px;
  font-size: 12px;
  color: var(--accent);
  font-family: -apple-system, "PingFang SC", sans-serif;
  font-weight: 500;
  display: none;
  letter-spacing: 0.5px;
}
.response-area .copy-status.visible {
  display: block;
}
.response-area .response-help {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px dashed var(--rule);
  font-size: 12px;
  color: var(--fg-dim);
  line-height: 1.8;
  font-family: -apple-system, "PingFang SC", sans-serif;
  letter-spacing: 0.3px;
}
.response-area .response-help em {
  color: var(--accent);
  font-style: normal;
  background: var(--bg);
  border: 1px solid var(--rule);
  padding: 1px 6px;
  border-radius: 2px;
  font-size: 11px;
  font-family: "SF Mono", monospace;
}
.response-area .response-help code {
  background: var(--bg);
  border: 1px solid var(--rule);
  padding: 1px 6px;
  font-size: 11px;
  border-radius: 2px;
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

/* 静态模式提示 banner */
.static-mode-banner {
  font-family: -apple-system, "PingFang SC", sans-serif;
  font-size: 12px;
  line-height: 1.8;
  color: var(--fg-dim);
  background: var(--quote-bg);
  border-left: 2px solid var(--fg-faint);
  padding: 12px 16px;
  margin: -32px -32px 56px;
  border-radius: 2px;
}
.static-mode-banner strong {
  color: var(--fg);
  font-weight: 600;
}
.static-mode-banner code {
  background: var(--bg);
  border: 1px solid var(--rule);
  padding: 1px 6px;
  font-size: 11px;
  border-radius: 2px;
  color: var(--fg);
}

@keyframes pulse-success {
  0% { transform: scale(1); }
  50% { transform: scale(1.04); }
  100% { transform: scale(1); }
}
.copy-status.success {
  color: var(--accent);
  animation: pulse-success 0.4s ease-out;
}
.copy-status.error { color: #c62828; }
@media (prefers-color-scheme: dark) {
  .copy-status.error { color: #ef9a9a; }
}

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


# ── 客户端 JavaScript ─────────────────────────────────────


SCRIPT_JS = r"""
// 读后无书 · 交互逻辑
// 优先 POST /api/note；server 未运行则 fallback 复制触发词到剪贴板
(function() {
  // 检测运行模式
  const isServerMode = location.protocol === 'http:' || location.protocol === 'https:';

  function setup() {
    const cfg = window.TWB;
    if (!cfg) return;

    const btn = document.getElementById('copy-btn');
    const ta = document.getElementById('response-input');
    const status = document.getElementById('copy-status');
    if (!btn || !ta) return;

    // 按模式调整按钮文案
    if (!isServerMode) {
      btn.textContent = '复制给 Agent →';
    }
    btn.dataset.originalLabel = btn.textContent;

    // 静态模式：插入一个温和的提示 banner
    if (!isServerMode && !document.getElementById('static-mode-banner')) {
      const banner = document.createElement('div');
      banner.id = 'static-mode-banner';
      banner.className = 'static-mode-banner';
      banner.innerHTML =
        '<strong>静态模式</strong>（file://）—— 写入将通过"复制 + 粘贴到 Agent"完成。<br>' +
        '想要点一下就直接保存？跑 <code>python render_html.py $TWB_HOME --serve</code>，从 ' +
        '<a href="http://127.0.0.1:8080" style="color:inherit;text-decoration:underline">http://127.0.0.1:8080</a> 打开。';
      // 插入到 nav 之后
      const nav = document.querySelector('.topnav');
      if (nav && nav.parentNode) {
        nav.parentNode.insertBefore(banner, nav.nextSibling);
      } else {
        document.body.insertBefore(banner, document.body.firstChild);
      }
    }

    function showStatus(msg, kind) {
      if (!status) return;
      status.classList.add('visible');
      status.classList.remove('success', 'error');
      if (kind) status.classList.add(kind);
      status.textContent = msg;
    }

    function resetButton(delay) {
      setTimeout(() => {
        btn.textContent = btn.dataset.originalLabel;
        btn.disabled = false;
      }, delay || 4000);
    }

    async function submit() {
      const text = (ta.value || '').trim();
      if (!text) {
        ta.focus();
        ta.style.borderColor = 'var(--accent)';
        setTimeout(() => { ta.style.borderColor = ''; }, 600);
        return;
      }

      btn.disabled = true;
      btn.textContent = '写入中...';

      // 优先：POST 到本地 server，直接写 markdown
      try {
        const res = await fetch('/api/note', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dao_id: cfg.dao_id,
            text: text,
            question: cfg.today_question || null
          })
        });
        if (res.ok) {
          const data = await res.json();
          showStatus(`✓ 已沉淀到道${cfg.dao_id} 的家页（${data.entries_count} 条）。正在刷新...`, 'success');
          btn.textContent = '✓ 已保存';
          ta.value = '';
          setTimeout(() => location.reload(), 1200);
          return;
        }
        // 4xx / 5xx：把错误显示出来，不 fallback
        const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }));
        showStatus('✗ 写入失败：' + (err.error || res.status), 'error');
        btn.textContent = btn.dataset.originalLabel;
        btn.disabled = false;
        return;
      } catch (e) {
        // 网络错误（没起 server，比如 file:// 打开）→ fallback 复制
      }

      // Fallback：复制触发词到剪贴板
      const trigger = cfg.page_type === 'today'
        ? '我想到了：' + text
        : '道' + cfg.dao_id + ' 让我想到 ' + text;
      try {
        await navigator.clipboard.writeText(trigger);
        showStatus('（没检测到本地 server）✓ 已复制触发词，粘贴到任意 Agent 会话。', 'success');
        btn.textContent = '已复制 ✓';
        resetButton(4000);
      } catch (e) {
        showStatus('✗ 写入和复制都失败：' + e, 'error');
        btn.textContent = btn.dataset.originalLabel;
        btn.disabled = false;
      }
    }

    btn.addEventListener('click', submit);
    ta.addEventListener('keydown', (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        submit();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setup);
  } else {
    setup();
  }
})();
""".strip()


# ── HTML 模板 ───────────────────────────────────────────────


def html_shell(title: str, body: str, css_rel_path: str,
               nav_active: str = "", wide: bool = False,
               with_script: bool = False) -> str:
    """完整 HTML 文档外壳"""
    nav = _topnav(css_rel_path, nav_active)
    page_class = "page-wide" if wide else "page"
    # script.js 与 css 在同一目录
    script_rel_path = css_rel_path.rsplit('/', 1)[0] + '/script.js' if '/' in css_rel_path else 'script.js'
    script_tag = f'<script src="{script_rel_path}"></script>' if with_script else ''
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
  {script_tag}
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
          <div class="response-area">
            <textarea id="response-input" placeholder="一句话也可以——把脑子里浮现的写下来"></textarea>
            <div class="response-actions">
              <button id="copy-btn">记一笔 →</button>
              <span class="hint">或在终端：<code>cc note {dao.id} "..."</code></span>
            </div>
            <div class="copy-status" id="copy-status"></div>
            <div class="response-help">
              <strong>有 server 在跑</strong>（通过 <code>render_html.py --serve</code> 启动）→ 直接写入
              <code>dao/journal/道{dao.id}.md</code>，下方"过往回响"立即出现。
              <br>
              <strong>没 server</strong>（直接打开 file://）→ 自动 fallback 为"复制 <em>我想到了：xxx</em> 到剪贴板"，
              粘贴给任意装了 <code>twb:daily</code> 的 Agent（Claude Code / Hermes / OpenClaw 等）由 skill 接住。
            </div>
          </div>
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
            more_link = f'<p style="text-align:center;margin-top:16px"><a href="dao/道{dao.id}.html" style="font-size:13px">查看全部 {len(dao.journal_entries)} 条（道{dao.id} 的家页）→</a></p>'
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

    <script>
      window.TWB = {{
        dao_id: {dao.id},
        today_question: {json.dumps(question)},
        page_type: "today"
      }};
    </script>
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
    """单条道的 canonical 积累页——所有关于这条道的内容都在这里"""
    paras = _split_desc_paragraphs(dao.description)
    desc_html = "".join(f'<p>{html.escape(p)}</p>' for p in paras)

    # ── 草稿台（每条道页都有）──
    response_area = f"""
    <div class="response-area response-area-standalone">
      <div class="label label-center">记一笔</div>
      <textarea id="response-input" placeholder="读到这条道时想到了什么？一句话也可以。"></textarea>
      <div class="response-actions">
        <button id="copy-btn">记一笔 →</button>
        <span class="hint">或在终端：<code>cc note {dao.id} "..."</code></span>
      </div>
      <div class="copy-status" id="copy-status"></div>
      <div class="response-help">
        <strong>有 server 在跑</strong>（通过 <code>render_html.py --serve</code> 启动）→ 直接写入下方的「过往回响」。
        <br>
        <strong>没 server</strong>（file:// 打开）→ 自动 fallback 为"复制 <em>道{dao.id} 让我想到 xxx</em> 到剪贴板"，
        粘贴给任意装了 <code>twb:daily</code> 的 Agent。
      </div>
    </div>
    """

    # ── 过往回响（journal 内联）──
    journal_html = ""
    if dao.journal_entries:
        parts = []
        for ts, q, body in dao.journal_entries:
            q_line = f'<div class="q-line">问：{html.escape(q)}</div>' if q else ""
            a_line = f'<div class="a-line">{html.escape(body).replace(chr(10), "<br>")}</div>'
            parts.append(
                f'<div class="entry">'
                f'<div class="ts">{html.escape(ts)}</div>'
                f'{q_line}{a_line}</div>'
            )
        journal_html = f"""
        <hr class="rule">
        <section class="journal">
          <div class="label label-center">你过往的回响（{len(dao.journal_entries)} 条 · 最新在前）</div>
          {''.join(parts)}
        </section>
        """
    else:
        journal_html = f"""
        <hr class="rule">
        <section class="journal">
          <div class="label label-center">你过往的回响</div>
          <div class="empty">还没有。上面那个草稿台是入口。</div>
        </section>
        """

    # ── 关于这条道（参考信息，放后面）──
    q_html = ""
    if dao.questions:
        q_items = "".join(f'<li>{html.escape(q)}</li>' for q in dao.questions)
        q_html = f"""
        <section>
          <div class="label label-center">检索问题</div>
          <ul style="list-style:none;padding:0;margin:0;font-size:14px;line-height:1.9;color:var(--fg-dim)">
            {q_items}
          </ul>
        </section>
        """

    books_html = ""
    if dao.books:
        book_items = "".join(
            f'<li>{html.escape(b)}</li>' for b in dao.books
        )
        books_html = f"""
        <section class="sources">
          <div class="label label-center">触碰此道的书籍</div>
          <ul>{book_items}</ul>
        </section>
        """

    rel_html = ""
    if dao.relations:
        rel_linked = _auto_link_dao_refs(html.escape(dao.relations),
                                          current_dao_id=dao.id,
                                          link_prefix=link_prefix)
        rel_html = f"""
        <section>
          <div class="label label-center">与其他道的关系</div>
          <p style="font-size:14px;line-height:1.9;color:var(--fg-dim);text-align:justify">
            {rel_linked}
          </p>
        </section>
        """

    laws_html = ""
    if dao.laws_line:
        laws_html = f"""
        <section>
          <div class="label label-center">下位法</div>
          <p style="font-size:13px;line-height:1.9;color:var(--fg-dim);text-align:center">
            {html.escape(dao.laws_line)}
          </p>
        </section>
        """

    reference_block = ""
    parts = [q_html, books_html, rel_html, laws_html]
    if any(parts):
        reference_block = f"""
        <hr class="rule">
        <div class="label label-center" style="margin-bottom:32px">关于这条道</div>
        {''.join(p for p in parts if p)}
        """

    return f"""
    <div class="dao-id">道 · {dao.id}</div>
    <h1 class="dao-title">{html.escape(dao.title)}</h1>
    <div class="dao-category">{html.escape(dao.category)}</div>

    <div class="dao-desc">{desc_html}</div>

    {response_area}

    {journal_html}

    {reference_block}

    <div class="footer">读后无书 · talk without book</div>

    <script>
      window.TWB = {{
        dao_id: {dao.id},
        today_question: null,
        page_type: "dao"
      }};
    </script>
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
        body = '<div class="empty">还没有任何浸泡记录。<br>打开任一条道的家页，下方的草稿台是入口。</div>'
    else:
        items = []
        for d in daos_with:
            latest = d.journal_entries[0][0] if d.journal_entries else ""
            items.append(f"""
            <a class="list-item" href="../dao/道{d.id}.html">
              <div class="item-id">道 · {d.id}</div>
              <div class="item-title">{html.escape(d.title)}</div>
              <div class="item-meta">{len(d.journal_entries)} 条 · 最近 {html.escape(latest)}</div>
            </a>
            """)
        body = f'<div class="list-grid">{"".join(items)}</div>'

    return f"""
    <div class="dao-id">总览</div>
    <h1 class="dao-title">浸泡记录</h1>
    <div class="dao-category">{len([d for d in daos if d.journal_entries])} 条道有回响 · 每条道的完整回响在它的家页内</div>
    {body}
    <div class="footer">读后无书 · talk without book</div>
    """


# （render_journal_page 已删除——单条道的 journal 现在内联在 dao/道N.html 里）


# ── journal 写入 ────────────────────────────────────────────


def append_journal_entry(root: Path, dao_id: int, text: str,
                         question: str | None = None) -> tuple[Path, int]:
    """
    追加一条 journal 记录到 $TWB_ROOT/dao/journal/道N.md
    返回 (journal_file_path, total_entries_count)
    """
    journal_dir = root / "dao" / "journal"
    journal_dir.mkdir(parents=True, exist_ok=True)
    journal_file = journal_dir / f"道{dao_id}.md"

    # 文件不存在则建文件头
    if not journal_file.exists():
        journal_file.write_text(
            f"# 道{dao_id} · 联想记录\n\n"
            f"> 浸泡过程中临场产生的联想、质疑、应用场景。\n",
            encoding="utf-8"
        )

    ts = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    if question:
        entry = f"\n## {ts}\n\n**问：** {question}\n\n**答：** {text}\n"
    else:
        entry = f"\n## {ts}\n\n{text}\n"

    with journal_file.open("a", encoding="utf-8") as f:
        f.write(entry)

    # 数一下现在有多少条
    count = 0
    try:
        existing = journal_file.read_text(encoding="utf-8")
        count = len(re.findall(r'(?m)^## \d{4}-\d{2}-\d{2} \d{2}:\d{2}', existing))
    except Exception:
        pass

    return journal_file, count


# ── 全量渲染（提取出来供 main 和 server 共用）──────────────


def render_all(root: Path, quiet: bool = False) -> None:
    """把 $TWB_ROOT 里的全部 markdown 产出物渲染成 site/ 下的 HTML"""
    def log(msg):
        if not quiet:
            print(msg)

    site = root / "site"
    site.mkdir(parents=True, exist_ok=True)

    dao_file = root / "dao" / "道.md"
    if not dao_file.exists():
        raise FileNotFoundError(f"找不到 {dao_file}")

    # 共享资源
    assets = site / "_assets"
    assets.mkdir(exist_ok=True)
    (assets / "style.css").write_text(CSS, encoding="utf-8")
    (assets / "script.js").write_text(SCRIPT_JS, encoding="utf-8")
    log(f"  ✓ {assets}/style.css + script.js")

    # 解析所有道 + journal
    log(f"  解析 {dao_file}...")
    daos = parse_dao_md(dao_file)
    log(f"    → {len(daos)} 条道")

    journals_dir = root / "dao" / "journal"
    journal_count = 0
    if journals_dir.exists():
        for d in daos:
            load_journal(journals_dir, d)
            journal_count += len(d.journal_entries)
        log(f"    → {journal_count} 条 journal 记录")

    # 解析所有书
    books: list[Book] = []
    books_dir = root / "books"
    if books_dir.exists():
        for bd in sorted(books_dir.iterdir()):
            if bd.is_dir() and not bd.name.startswith("."):
                try:
                    book = parse_book_dir(bd)
                    books.append(book)
                    log(f"    → 书：{book.name} (法{len(book.fa)} 术{len(book.shu)} 器{len(book.qi)} 势{len(book.shi)})")
                except Exception as e:
                    log(f"    ⚠️ 解析 {bd.name} 失败：{e}")

    # 今日选取
    state = read_today_state(root)
    today_date = dt.date.today().isoformat()
    if state and state[0] == today_date:
        _, sync_id, sync_q = state
        today_dao = next((d for d in daos if d.id == sync_id), daos[0])
        today_question = sync_q
        log(f"    → 同步 today.tsv：道{today_dao.id}")
    else:
        today_dao, today_question = pick_today(daos)
        log(f"    → 独立选取：道{today_dao.id}")

    today_obj = dt.date.today()
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today_obj.weekday()]
    date_info = {
        "year": today_obj.year,
        "month": today_obj.month,
        "day": today_obj.day,
        "weekday": weekday_cn,
    }

    # 渲染
    body = render_today(today_dao, today_question, date_info, bool(today_dao.journal_entries))
    (site / "index.html").write_text(
        html_shell(f"{today_obj.month}月{today_obj.day}日 · 道{today_dao.id}",
                   body, "_assets/style.css", "today", with_script=True),
        encoding="utf-8"
    )

    (site / "dao").mkdir(exist_ok=True)
    (site / "dao" / "index.html").write_text(
        html_shell("所有的道", render_dao_overview(daos),
                   "../_assets/style.css", "dao"),
        encoding="utf-8"
    )
    for dao in daos:
        (site / "dao" / f"道{dao.id}.html").write_text(
            html_shell(f"道{dao.id}：{dao.title[:25]}", render_dao_page(dao),
                       "../_assets/style.css", "dao", with_script=True),
            encoding="utf-8"
        )

    (site / "books").mkdir(exist_ok=True)
    (site / "books" / "index.html").write_text(
        html_shell("书架", render_book_overview(books),
                   "../_assets/style.css", "books"),
        encoding="utf-8"
    )
    for book in books:
        bdir = site / "books" / book.name
        bdir.mkdir(exist_ok=True)
        (bdir / "index.html").write_text(
            html_shell(f"《{book.display_name or book.name}》", render_book_page(book),
                       "../../_assets/style.css", "books", wide=True),
            encoding="utf-8"
        )

    (site / "journal").mkdir(exist_ok=True)
    (site / "journal" / "index.html").write_text(
        html_shell("浸泡记录总览", render_journal_index(daos),
                   "../_assets/style.css", "journal"),
        encoding="utf-8"
    )
    for old in (site / "journal").glob("道*.html"):
        old.unlink()

    log(f"  ✓ site/ 全部页面已写入")


# ── 本地服务器 ──────────────────────────────────────────────


def make_server_handler(root: Path):
    """工厂：返回一个绑定了 root 的 HTTP handler 类"""
    site_dir = root / "site"

    class TwbHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(site_dir), **kwargs)

        def do_POST(self):
            if self.path == '/api/note':
                self._handle_note()
            else:
                self.send_error(404, "Not Found")

        def _handle_note(self):
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length == 0:
                    self._send_error(400, "Empty body")
                    return
                data = json.loads(self.rfile.read(length))

                dao_id = int(data.get('dao_id', 0))
                text = (data.get('text') or '').strip()
                question = (data.get('question') or '').strip() or None

                if dao_id <= 0:
                    self._send_error(400, "missing dao_id")
                    return
                if not text:
                    self._send_error(400, "empty text")
                    return

                journal_file, count = append_journal_entry(root, dao_id, text, question)

                # 重新渲染
                try:
                    render_all(root, quiet=True)
                except Exception as e:
                    print(f"  ⚠️ render_all 失败但 journal 已写：{e}", file=sys.stderr)

                self._send_json(200, {
                    "ok": True,
                    "dao_id": dao_id,
                    "entries_count": count,
                    "journal_path": str(journal_file),
                    "timestamp": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
                })

            except json.JSONDecodeError as e:
                self._send_error(400, f"bad json: {e}")
            except Exception as e:
                self._send_error(500, f"{type(e).__name__}: {e}")

        def _send_json(self, code: int, body: dict):
            payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def _send_error(self, code: int, msg: str):
            self._send_json(code, {"ok": False, "error": msg})

        def log_message(self, fmt, *args):
            # 安静一些——只 log POST 和错误
            if 'POST' in (args[0] if args else '') or any('error' in str(a).lower() for a in args):
                print(f"  [server] {fmt % args}")

    return TwbHandler


def start_server(root: Path, port: int = 8080) -> None:
    """启动本地 HTTP 服务器（静态站点 + /api/note 写入）"""
    # 首次启动先渲染一遍
    print(f"\n首次渲染...")
    render_all(root, quiet=True)
    print(f"  ✓ site/ 就绪")

    Handler = make_server_handler(root)

    # 找空闲端口
    while port < port + 20:
        try:
            with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
                url = f"http://127.0.0.1:{port}"
                print(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                print(f"  读后无书 · talk without book")
                print(f"  本地服务运行中：{url}")
                print(f"  按 Ctrl+C 停止")
                print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                # 自动打开浏览器（仅 macOS / Linux 有 open / xdg-open）
                try:
                    if sys.platform == "darwin":
                        os.system(f"open {url}")
                    elif sys.platform.startswith("linux"):
                        os.system(f"xdg-open {url} 2>/dev/null &")
                except Exception:
                    pass

                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    print("\n  ✓ 已停止")
                    return
        except OSError as e:
            if "Address already in use" in str(e):
                print(f"  端口 {port} 被占用，尝试 {port + 1}...")
                port += 1
                continue
            raise


# ── 主入口 ──────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="读后无书 · 全产出物 HTML 渲染器"
    )
    parser.add_argument("root", type=Path,
                        help="知识库根目录（$TWB_ROOT），必须包含 dao/道.md")
    parser.add_argument("--serve", action="store_true",
                        help="启动本地 HTTP 服务器（含写入 API）而不是只生成静态文件")
    parser.add_argument("--port", type=int, default=8080,
                        help="服务器端口（默认 8080，被占用则自动 +1）")
    args = parser.parse_args()

    root: Path = args.root.resolve()

    if args.serve:
        try:
            start_server(root, args.port)
        except FileNotFoundError as e:
            print(f"✗ {e}", file=sys.stderr)
            return 1
        return 0

    try:
        render_all(root, quiet=False)
    except FileNotFoundError as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    site = root / "site"
    print(f"\n✓ 全部渲染完成 → {site}")
    print(f"  打开：open {site / 'index.html'}")
    print(f"  或启动交互模式：python {sys.argv[0]} {root} --serve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
