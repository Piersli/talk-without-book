"""
generate.py — 读后无书 浸泡页（静态 HTML 生成器）

设计原则：
- markdown 是源，HTML 只是派生视图（Agent 和人类共用同一 markdown）
- 浸泡页不是文档站——主角是"今日之道 + 问题 + 你的联想"
- 零外部依赖，只用 Python stdlib
- 单页输出，可直接 `open site/index.html`

用法：
    python generate.py              # 在 读后无书/site/index.html 输出
    python generate.py --out <path> # 自定义输出

如果 `~/.claude/bin/cc` 的 banner 已经选过今日之道，会读取同一个状态文件，
确保网页和终端显示的是同一条道 + 同一个问题（配对体验）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ── 数据模型 ────────────────────────────────────────────────


@dataclass
class Dao:
    id: int
    title: str           # 不含编号的标题部分
    category: str
    description: str
    questions: list[str] = field(default_factory=list)
    books: list[str] = field(default_factory=list)  # 原始 markdown 片段行
    laws_line: str = ""                              # "- **下位法**：..." 整行
    relations: str = ""
    journal_entries: list[tuple[str, str, str]] = field(default_factory=list)
    # (timestamp, question_or_None, body)


# ── 解析器 ──────────────────────────────────────────────────


def parse_dao_md(path: Path) -> list[Dao]:
    text = path.read_text(encoding="utf-8")
    # 用 "## 道N：" 切段
    sections = re.split(r'(?m)^## 道(\d+)：', text)
    # sections[0] 是标题前的内容，忽略；后面是 id, body, id, body, ...
    daos = []
    for i in range(1, len(sections), 2):
        dao_id = int(sections[i])
        body = sections[i + 1] if i + 1 < len(sections) else ""
        daos.append(_parse_section(dao_id, body))
    daos.sort(key=lambda d: d.id)
    return daos


def _parse_section(dao_id: int, body: str) -> Dao:
    """body 从 '标题\n\n- **类别**：...' 开始"""
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
    """抽取 `- **name**：内容` 单行字段"""
    m = re.search(rf'^- \*\*{re.escape(name)}\*\*：\s*(.+?)(?=\n- |\n---|\Z)',
                  text, re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    return m.group(1).strip()


def _extract_list_field(text: str, name: str) -> list[str]:
    """抽取 `- **name**：\n  - 项1\n  - 项2\n` 列表字段"""
    m = re.search(rf'^- \*\*{re.escape(name)}\*\*：\s*\n((?:  - .*\n?)+)',
                  text, re.MULTILINE)
    if not m:
        return []
    items = re.findall(r'^  - (.+)', m.group(1), re.MULTILINE)
    return [x.strip() for x in items]


# ── 读 journal ──────────────────────────────────────────────


def load_journal(journal_dir: Path, dao: Dao) -> None:
    f = journal_dir / f"道{dao.id}.md"
    if not f.exists():
        return
    text = f.read_text(encoding="utf-8")
    # 按 ## 时间戳 切
    entries = re.split(r'(?m)^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s*\n', text)
    # entries[0] 是文件头；后面成对 (ts, body)
    for i in range(1, len(entries), 2):
        ts = entries[i].strip()
        body = entries[i + 1] if i + 1 < len(entries) else ""
        # 看是否 Q-A 格式
        q_match = re.search(r'\*\*问：\*\*\s*(.+?)(?=\n\n\*\*答：\*\*)',
                            body, re.DOTALL)
        a_match = re.search(r'\*\*答：\*\*\s*(.+?)(?=\n\n|\Z)', body, re.DOTALL)
        if q_match and a_match:
            dao.journal_entries.append(
                (ts, q_match.group(1).strip(), a_match.group(1).strip())
            )
        else:
            # 普通笔记
            dao.journal_entries.append((ts, "", body.strip()))
    # 最新在前
    dao.journal_entries.sort(key=lambda e: e[0], reverse=True)


# ── 今日之道 & 问题选择 ─────────────────────────────────────


def pick_today(daos: list[Dao]) -> tuple[Dao, str]:
    """与 cc banner 同一套算法：day-of-year mod count"""
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
    """读 $TWB_ROOT/.state/today.tsv，保证今天选哪条道、哪个问题在终端和浏览器之间稳定"""
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


# ── HTML 渲染 ───────────────────────────────────────────────


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
  font-family: "Songti SC", "Noto Serif CJK SC", "Source Han Serif SC", "PingFang SC", Georgia, "Times New Roman", serif;
  line-height: 1.9;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.page {
  max-width: 620px;
  margin: 0 auto;
  padding: 88px 32px 120px;
}

/* 日期头：像日历页的边角 */
.dateline {
  text-align: center;
  margin-bottom: 80px;
  color: var(--fg-dim);
}
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

/* 分隔线 */
.rule {
  border: none;
  border-top: 1px solid var(--rule);
  margin: 64px auto;
  width: 120px;
}

/* 道的编号 */
.dao-id {
  text-align: center;
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 4px;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 24px;
}

/* 道的标题 */
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
  margin-bottom: 56px;
}

/* 表述——主体阅读区 */
.dao-desc {
  font-size: 18px;
  line-height: 2.0;
  color: var(--fg);
  margin: 48px 0;
  text-align: justify;
  text-justify: inter-ideograph;
}
.dao-desc p {
  margin: 0 0 20px;
  text-indent: 2em;
}

/* 今日提问——最突出 */
.question-block {
  margin: 72px 0;
  padding: 36px 32px;
  background: var(--quote-bg);
  border-left: 3px solid var(--accent);
  position: relative;
}
.question-block .label {
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 3px;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 16px;
}
.question-block .q {
  font-size: 20px;
  line-height: 1.8;
  color: var(--fg);
  margin: 0 0 24px;
  font-weight: 400;
}
.question-block .cta {
  font-family: "SF Mono", ui-monospace, monospace;
  font-size: 13px;
  color: var(--fg-dim);
  padding-top: 16px;
  border-top: 1px solid var(--rule);
}
.question-block .cta code {
  color: var(--accent);
  font-weight: 500;
}

/* 你的回响（journal）*/
.journal {
  margin: 72px 0;
}
.journal .label {
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 3px;
  color: var(--fg-dim);
  text-transform: uppercase;
  margin-bottom: 24px;
  text-align: center;
}
.entry {
  margin: 32px 0;
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
  margin-bottom: 8px;
}
.entry .a-line {
  font-size: 16px;
  line-height: 1.9;
  color: var(--fg);
}

.empty-journal {
  text-align: center;
  font-family: -apple-system, sans-serif;
  font-size: 13px;
  color: var(--fg-dim);
  padding: 24px 0;
  font-style: italic;
}

/* 底部书源 */
.sources {
  margin: 72px 0 48px;
  font-size: 14px;
  color: var(--fg-dim);
  line-height: 1.8;
}
.sources .label {
  font-family: -apple-system, sans-serif;
  font-size: 11px; letter-spacing: 3px;
  color: var(--fg-dim);
  text-transform: uppercase;
  margin-bottom: 16px;
  text-align: center;
}
.sources ul {
  list-style: none; padding: 0; margin: 0;
}
.sources li {
  margin: 8px 0;
  padding-left: 20px;
  position: relative;
}
.sources li::before {
  content: "·";
  position: absolute; left: 8px; color: var(--fg-faint);
}

/* 最底脚标 */
.footer {
  text-align: center;
  margin-top: 96px;
  font-family: -apple-system, sans-serif;
  font-size: 11px;
  color: var(--fg-faint);
  letter-spacing: 1px;
  line-height: 1.8;
}
.footer code {
  background: var(--quote-bg);
  padding: 2px 8px; border-radius: 2px;
  color: var(--fg-dim);
}

/* 选中文字的颜色也换一下 */
::selection { background: var(--accent); color: var(--bg); }

/* 小屏 */
@media (max-width: 600px) {
  .page { padding: 56px 24px 80px; }
  .dateline .date-main { font-size: 36px; }
  .dao-title { font-size: 26px; }
  .dao-desc { font-size: 16px; }
  .question-block { padding: 28px 24px; }
  .question-block .q { font-size: 18px; }
}
"""


def _split_desc_into_paragraphs(desc: str) -> list[str]:
    """把单段表述按句号切分为 2-3 个可阅读的段落"""
    sentences = re.split(r'(?<=。)', desc)
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 2:
        return [desc]
    # 平均分成约 2-3 段，每段 2-3 句
    per_para = max(2, len(sentences) // 3 + (1 if len(sentences) % 3 else 0))
    paras = []
    for i in range(0, len(sentences), per_para):
        paras.append("".join(sentences[i:i + per_para]))
    return paras


def render_today_page(
    dao: Dao,
    today_question: str,
    date_info: dict,
) -> str:
    """渲染"一天一页"的浸泡页——只有今日之道，没有索引"""

    # 表述分段
    paras = _split_desc_into_paragraphs(dao.description)
    desc_html = "".join(f'<p>{html.escape(p)}</p>' for p in paras)

    # 问题块
    if today_question:
        question_html = f"""
        <div class="question-block">
          <div class="label">今日提问</div>
          <div class="q">{html.escape(today_question)}</div>
          <div class="cta">一句话回应：<code>cc note {dao.id} "..."</code></div>
        </div>
        """
    else:
        question_html = ""

    # 你的回响
    journal_html = ""
    if dao.journal_entries:
        parts = []
        # 只显示最近的 5 条，避免淹没今日内容
        for ts, q, body in dao.journal_entries[:5]:
            q_line = (f'<div class="q-line">问：{html.escape(q)}</div>' if q else "")
            a_line = f'<div class="a-line">{html.escape(body).replace(chr(10), "<br>")}</div>'
            parts.append(
                f'<div class="entry">'
                f'<div class="ts">{html.escape(ts)}</div>'
                f'{q_line}{a_line}'
                f'</div>'
            )
        label = f"你对这条道的过往回响"
        if len(dao.journal_entries) > 5:
            label += f"（显示最近 5 / 共 {len(dao.journal_entries)} 条）"
        journal_html = f"""
        <hr class="rule">
        <section class="journal">
          <div class="label">{label}</div>
          {"".join(parts)}
        </section>
        """
    else:
        # 没有记录时，用温柔的提示
        journal_html = f"""
        <hr class="rule">
        <section class="journal">
          <div class="label">你对这条道的过往回响</div>
          <div class="empty-journal">还没有。今天是第一次。</div>
        </section>
        """

    # 书源
    sources_html = ""
    if dao.books:
        items = "".join(f'<li>{html.escape(b)}</li>' for b in dao.books)
        sources_html = f"""
        <hr class="rule">
        <section class="sources">
          <div class="label">这条道的书源</div>
          <ul>{items}</ul>
        </section>
        """

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

    {question_html}

    {journal_html}

    {sources_html}

    <div class="footer">
      读后无书 · 浸泡层 · 第二表面<br>
      <code>python tools/view/generate.py</code> · 次日再开
    </div>
    """


def render_html(dao: Dao, today_question: str, date_info: dict) -> str:
    body = render_today_page(dao, today_question, date_info)
    return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{date_info['month']}月{date_info['day']}日 · 道{dao.id}</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="page">
    {body}
  </div>
</body>
</html>
"""


# ── 主入口 ──────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate 读后无书 daily immersion page (one 道 per day, Daily-Stoic style)"
    )
    parser.add_argument("root", type=Path,
                        help="知识库根目录（$TWB_ROOT）—— 应包含 dao/道.md")
    parser.add_argument("--out", type=Path, default=None,
                        help="输出路径（默认为 <root>/site/index.html）")
    args = parser.parse_args()

    root: Path = args.root.resolve()
    dao_file = root / "dao" / "道.md"
    journal_dir = root / "dao" / "journal"

    if not dao_file.exists():
        print(f"✗ 找不到 {dao_file}", file=sys.stderr)
        return 1

    print(f"解析 {dao_file}...")
    daos = parse_dao_md(dao_file)
    print(f"  → {len(daos)} 条道")

    # 加载 journal
    if journal_dir.exists():
        for d in daos:
            load_journal(journal_dir, d)
        total = sum(len(d.journal_entries) for d in daos)
        print(f"  → {total} 条 journal 记录")

    # 选今日之道：如果 $TWB_ROOT/.state/today.tsv 存在且是今天，用它（保证多通道一致）
    state = read_today_state(root)
    today_date = dt.date.today().isoformat()
    if state and state[0] == today_date:
        _, sync_id, sync_q = state
        today_dao = next((d for d in daos if d.id == sync_id), None)
        today_question = sync_q
        if today_dao:
            print(f"  → 从 .state/today.tsv 同步：今日 道{today_dao.id}")
        else:
            today_dao, today_question = pick_today(daos)
    else:
        today_dao, today_question = pick_today(daos)
        print(f"  → 独立选取：今日 道{today_dao.id}")

    # 渲染：把日期拆成 year/month/day/weekday
    today_obj = dt.date.today()
    weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][today_obj.weekday()]
    date_info = {
        "year": str(today_obj.year),
        "month": str(today_obj.month),
        "day": str(today_obj.day),
        "weekday": weekday_cn,
    }

    html_content = render_html(today_dao, today_question, date_info)

    # 输出
    out = args.out or (root / "site" / "index.html")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_content, encoding="utf-8")
    print(f"✓ 已写入 {out}")
    print(f"  打开：open {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
