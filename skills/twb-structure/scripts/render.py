"""
render.py — 用 LLM 生成 wiki/ 下的所有页面

输入：KnowledgeBase + AnalysisResult
输出：写入 wiki/ 目录下的 markdown 文件
"""

import os
from pathlib import Path
from anthropic import Anthropic
from models import KnowledgeBase, DaoNode
from analyze import AnalysisResult, Topic


def _get_client() -> Anthropic:
    return Anthropic()


def _call_llm(system: str, user: str, model: str = "claude-sonnet-4-20250514") -> str:
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


# ── 页面生成器 ──────────────────────────────────────────


def render_dao_page(dao: DaoNode, kb: KnowledgeBase, analysis: AnalysisResult) -> str:
    """生成 wiki/dao/道N-标题.md"""

    # 收集该道下的所有法/术/器
    related_fa = []
    related_shu = []
    related_qi = []
    for book_name, book in kb.books.items():
        for fa in book.fa:
            if dao.id in fa.parent_dao:
                related_fa.append(fa)
        for shu in book.shu:
            for fa_id in shu.parent_fa:
                matching_fa = [f for f in book.fa if f.id == fa_id and dao.id in f.parent_dao]
                if matching_fa:
                    related_shu.append(shu)
                    break

    # 构建 prompt 数据
    fa_lines = []
    for fa in related_fa:
        fa_lines.append(f"- [{fa.book}] {fa.id}：{fa.title}\n  因果机制：{fa.causal_mechanism[:200]}\n  适用边界：{fa.boundary[:150]}")

    shu_lines = []
    for shu in related_shu:
        shu_lines.append(f"- [{shu.book}] {shu.id}：{shu.title}\n  方法：{shu.method[:150]}")

    # 找到相关主题
    related_topics = [t for t in analysis.topics if dao.id in t.related_dao]

    system = """你是 **读后无书 (talk without book)** 知识库的 Wiki 编译器。你的任务是围绕一条"道"（永恒真相），综合所有书的视角，写一篇完整的、可独立阅读的知识文章。

写作要求：
1. 文章是给想深度理解这个主题的知识工作者看的，不是学术论文
2. 用第二人称"你"来写，有对话感
3. 综合多本书的观点，不要逐本罗列——而是按逻辑组织
4. 每个关键论断要标注来源书籍
5. 用 [[页面名]] 语法标注跨页面链接
6. 中文写作，专有名词保留英文"""

    user = f"""请为以下道写一篇 Wiki 文章。

# 道的基本信息
- ID: {dao.id}
- 标题: {dao.title}
- 类别: {dao.category}
- 表述: {dao.description}
- 触碰书籍: {', '.join(f'{b}({a[:30]})' for b, a in dao.books.items())}
- 与其他道的关系: {dao.relations}

# 该道下的法（跨书）
{chr(10).join(fa_lines) if fa_lines else '（无）'}

# 相关术（可操作方法）
{chr(10).join(shu_lines) if shu_lines else '（无）'}

# 相关主题
{', '.join(t.name for t in related_topics) if related_topics else '（无）'}

请按以下结构输出 markdown：

# {dao.id}：{dao.title}

## 这条道在说什么
（融合所有书的视角，用一段话完整阐述）

## 各本书如何触碰这条道
### [书名1] — [角度]
（综合该书在这条道上的法/术/器，写成连贯段落）
### [书名2] — [角度]
...

## 核心法则
| 法 | 来源 | 一句话 | 关键洞察 |
|---|---|---|---|

## 可以做什么
（基于术和器，写成实用的操作建议段落）

## 与其他道的关系
（该道如何与其他道相互作用）

## 相关主题
（链接到相关 topics/ 页面）"""

    return _call_llm(system, user)


def render_topic_page(topic: Topic, kb: KnowledgeBase) -> str:
    """生成 wiki/topics/主题.md"""

    # 收集该主题相关的节点详情
    node_details = []
    for ref in topic.related_nodes[:30]:  # 限制数量
        parts = ref.split(":")
        if len(parts) >= 2:
            book_name = parts[0]
            node_ref = parts[1] if len(parts) == 2 else parts[1]
            book = kb.books.get(book_name)
            if book:
                # 搜索节点
                for fa in book.fa:
                    if fa.id == node_ref:
                        node_details.append(f"- [{book_name}] {fa.id}：{fa.title} (因果：{fa.causal_mechanism[:100]})")
                for shu in book.shu:
                    if shu.id == node_ref:
                        node_details.append(f"- [{book_name}] {shu.id}：{shu.title} (方法：{shu.method[:100]})")

    system = """你是 **读后无书 (talk without book)** 知识库的 Wiki 编译器。你的任务是围绕一个"主题"，综合知识库中所有相关节点，写一篇用户可以直接阅读的知识文章。

写作要求：
1. 主题文章是按用户的思考词汇组织的——用户想到"决策"时会来读这页
2. 综合多本书的法/术/器，不要逐本罗列
3. 从"底层原理"写到"怎么做"，形成完整的理解闭环
4. 标注来源书籍
5. 用 [[页面名]] 语法标注跨页面链接"""

    user = f"""请为以下主题写一篇 Wiki 文章。

# 主题信息
- 名称: {topic.name}
- 描述: {topic.description}
- 涉及的道: {', '.join(topic.related_dao)}
- LLM跨书综合: {topic.cross_book_summary}

# 相关节点
{chr(10).join(node_details) if node_details else '（详见上方综合）'}

请按以下结构输出 markdown：

# {topic.name}

## 知识库对"{topic.name}"的理解
（综合所有相关节点，写一篇关于该主题的完整文章）

## 底层原理
（涉及的道，为什么这个主题的规律是这样的）

## 关键法则
（核心的法，用连贯段落而非列表）

## 实用方法
（术和器，可以直接拿来用的）

## 相关主题
（链接到其他相关主题）"""

    return _call_llm(system, user)


def render_book_page(book_name: str, kb: KnowledgeBase) -> str:
    """生成 wiki/books/书名.md"""
    book = kb.books[book_name]

    # 统计该书触碰了哪些道
    dao_touchpoints = {}
    for fa in book.fa:
        for dao_id in fa.parent_dao:
            if dao_id not in dao_touchpoints:
                dao_touchpoints[dao_id] = []
            dao_touchpoints[dao_id].append(fa.title[:40])

    dao_lines = []
    for dao_id, fa_titles in sorted(dao_touchpoints.items()):
        dao_node = next((d for d in kb.dao if d.id == dao_id), None)
        dao_title = dao_node.title if dao_node else dao_id
        dao_lines.append(f"- {dao_id}（{dao_title}）: {len(fa_titles)}条法 — {', '.join(fa_titles[:3])}")

    system = """你是 **读后无书 (talk without book)** 知识库的 Wiki 编译器。写一本书的概览页面——
这本书的核心论点是什么，它在整个知识库中提供了什么独特的视角。"""

    user = f"""请为以下书写一篇概览。

# 书籍信息
- 名称: {book_name}
- 法: {len(book.fa)} 条
- 术: {len(book.shu)} 条
- 器: {len(book.qi)} 条
- 势: {len(book.shi)} 条

# 触碰的道
{chr(10).join(dao_lines)}

# 法的标题列表
{chr(10).join(f'- {fa.id}：{fa.title}' for fa in book.fa)}

请按以下结构输出 markdown：

# {book_name}

## 核心论点
（一段综合）

## 触碰的道
| 道 | 强度 | 角度 |
|---|---|---|

## 独特贡献
（这本书在整个知识库中提供了什么别的书没有的视角）

## 节点统计
法: {len(book.fa)} | 术: {len(book.shu)} | 器: {len(book.qi)} | 势: {len(book.shi)}"""

    return _call_llm(system, user)


def render_cross_pages(analysis: AnalysisResult) -> tuple[str, str]:
    """生成 wiki/cross/分歧.md 和 wiki/cross/空白.md"""

    # 分歧页面
    if analysis.divergences:
        divergence_lines = []
        for d in analysis.divergences:
            divergence_lines.append(f"## {d.topic}\n**作者**: {', '.join(d.authors)}\n\n{d.description}\n")
        divergence_md = f"# 分歧与矛盾\n\n> 不同作者对同一主题的不同看法。分歧是高价值信息——它揭示了知识的边界。\n\n{''.join(divergence_lines)}"
    else:
        divergence_md = "# 分歧与矛盾\n\n> 当前知识库中未发现显著的作者间分歧。随着更多书籍加入，分歧会自然浮现。\n"

    # 空白页面
    if analysis.gaps:
        gap_lines = []
        for g in analysis.gaps:
            icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(g.severity, "⚪")
            gap_lines.append(f"## {icon} {g.area}\n\n{g.description}\n\n**严重度**: {g.severity}\n")
        gaps_md = f"# 知识库空白区域\n\n> 知识库的自我诊断。识别覆盖不足的区域，指导下一步提取方向。\n\n{''.join(gap_lines)}"
    else:
        gaps_md = "# 知识库空白区域\n\n> 当前未识别出显著空白。\n"

    return divergence_md, gaps_md


def render_meta(kb: KnowledgeBase, analysis: AnalysisResult) -> str:
    """生成 wiki/_meta.md — 知识库全景"""
    lines = [
        "# 知识库全景",
        "",
        "## 统计",
        f"- 书籍: {len(kb.books)} 本",
        f"- 道: {len(kb.dao)} 条",
        f"- 总节点: {kb.total_nodes}",
        "",
        "| 书 | 法 | 术 | 器 | 势 |",
        "|---|---|---|---|---|",
    ]

    for name, book in kb.books.items():
        lines.append(f"| {name} | {len(book.fa)} | {len(book.shu)} | {len(book.qi)} | {len(book.shi)} |")

    lines.extend([
        "",
        "## 主题索引",
        "",
    ])
    for t in analysis.topics:
        lines.append(f"- [[{t.name}]] — {t.description}")

    lines.extend([
        "",
        "## 道索引",
        "",
    ])
    for d in kb.dao:
        lines.append(f"- [[{d.id}-{_dao_slug(d.title)}]] — {d.title}")

    lines.extend([
        "",
        "## 书籍索引",
        "",
    ])
    for name in kb.books:
        lines.append(f"- [[{name}]]")

    if analysis.gaps:
        lines.extend([
            "",
            "## 空白区域",
            "",
        ])
        for g in analysis.gaps:
            lines.append(f"- [{g.severity}] {g.area}")

    return "\n".join(lines)


def _dao_slug(title: str) -> str:
    """从道标题生成文件名友好的 slug"""
    # 取前几个中文字作为 slug
    import re
    chinese = re.findall(r'[\u4e00-\u9fff]+', title)
    if chinese:
        return chinese[0][:4]
    return title[:20].replace(" ", "-")


# ── 主入口 ──────────────────────────────────────────


def render_wiki(kb: KnowledgeBase, analysis: AnalysisResult, wiki_dir: Path):
    """生成所有 wiki 页面"""

    # 创建目录
    (wiki_dir / "dao").mkdir(parents=True, exist_ok=True)
    (wiki_dir / "topics").mkdir(parents=True, exist_ok=True)
    (wiki_dir / "books").mkdir(parents=True, exist_ok=True)
    (wiki_dir / "cross").mkdir(parents=True, exist_ok=True)

    # 生成道页面
    for dao in kb.dao:
        slug = _dao_slug(dao.title)
        filename = f"{dao.id}-{slug}.md"
        print(f"  [render] wiki/dao/{filename}")
        content = render_dao_page(dao, kb, analysis)
        (wiki_dir / "dao" / filename).write_text(content, encoding="utf-8")

    # 生成主题页面
    for topic in analysis.topics:
        filename = f"{topic.name}.md"
        print(f"  [render] wiki/topics/{filename}")
        content = render_topic_page(topic, kb)
        (wiki_dir / "topics" / filename).write_text(content, encoding="utf-8")

    # 生成书籍页面
    for book_name in kb.books:
        filename = f"{book_name}.md"
        print(f"  [render] wiki/books/{filename}")
        content = render_book_page(book_name, kb)
        (wiki_dir / "books" / filename).write_text(content, encoding="utf-8")

    # 生成跨书页面
    print(f"  [render] wiki/cross/分歧.md")
    print(f"  [render] wiki/cross/空白.md")
    divergence_md, gaps_md = render_cross_pages(analysis)
    (wiki_dir / "cross" / "分歧.md").write_text(divergence_md, encoding="utf-8")
    (wiki_dir / "cross" / "空白.md").write_text(gaps_md, encoding="utf-8")

    # 生成全景页
    print(f"  [render] wiki/_meta.md")
    meta_md = render_meta(kb, analysis)
    (wiki_dir / "_meta.md").write_text(meta_md, encoding="utf-8")

    print(f"  [render] 完成！共生成 {len(kb.dao) + len(analysis.topics) + len(kb.books) + 3} 个页面")
