"""
analyze.py — LLM 驱动的跨书智能分析

输入：KnowledgeBase（parse 产出）
输出：AnalysisResult（主题归纳、跨书关联、语义去重、空白区域）

使用 Claude API 进行分析。
"""

import json
import os
from dataclasses import dataclass, field
from anthropic import Anthropic
from models import KnowledgeBase


@dataclass
class SemanticDuplicate:
    """语义重复的节点对"""
    node_a: str        # "Same_as_Ever:法27"
    node_b: str        # "The_Social_Animal:法1"
    title_a: str
    title_b: str
    similarity: str    # LLM 判断的相似程度描述
    recommendation: str  # 合并建议


@dataclass
class CrossBookConnection:
    """跨书隐含关联"""
    node_a: str
    node_b: str
    title_a: str
    title_b: str
    relationship: str  # LLM 发现的关联描述


@dataclass
class Topic:
    """LLM 归纳的主题"""
    name: str
    description: str
    related_dao: list[str]        # 涉及的道
    related_nodes: list[str]      # 涉及的节点 ID 列表 (book:dim:id)
    cross_book_summary: str       # LLM 写的跨书综合


@dataclass
class KnowledgeGap:
    """知识库空白区域"""
    area: str
    description: str
    severity: str   # high / medium / low


@dataclass
class BookDivergence:
    """作者之间的分歧"""
    topic: str
    authors: list[str]
    description: str


@dataclass
class AnalysisResult:
    """分析结果"""
    topics: list[Topic] = field(default_factory=list)
    duplicates: list[SemanticDuplicate] = field(default_factory=list)
    connections: list[CrossBookConnection] = field(default_factory=list)
    gaps: list[KnowledgeGap] = field(default_factory=list)
    divergences: list[BookDivergence] = field(default_factory=list)


def _get_client() -> Anthropic:
    """获取 Anthropic 客户端"""
    return Anthropic()


def _kb_summary(kb: KnowledgeBase) -> str:
    """生成知识库的紧凑摘要，供 LLM prompt 使用"""
    lines = []

    lines.append("# 知识库当前状态\n")

    # 道
    lines.append("## 道（全局永恒真相）")
    for d in kb.dao:
        books_str = ", ".join(f"{b}({a[:20]})" for b, a in d.books.items())
        lines.append(f"- {d.id}：{d.title} [{d.category}] 触碰书籍: {books_str}")

    # 每本书的节点
    for book_name, book in kb.books.items():
        lines.append(f"\n## {book_name}")

        if book.fa:
            lines.append("### 法")
            for n in book.fa:
                dao_str = ",".join(n.parent_dao)
                lines.append(f"- {n.id}：{n.title[:60]} [上位道:{dao_str}]")

        if book.shu:
            lines.append("### 术")
            for n in book.shu:
                fa_str = ",".join(n.parent_fa) if n.parent_fa else "无上位法"
                lines.append(f"- {n.id}：{n.title[:60]} [上位法:{fa_str}]")

        if book.qi:
            lines.append("### 器")
            for n in book.qi:
                shu_str = ",".join(n.parent_shu) if n.parent_shu else "无上位术"
                lines.append(f"- {n.id}：{n.title[:60]} [上位术:{shu_str}]")

        if book.shi:
            lines.append("### 势")
            for n in book.shi:
                lines.append(f"- {n.id}：{n.title[:60]}")

    return "\n".join(lines)


def _call_llm(system: str, user: str, model: str = "claude-sonnet-4-20250514") -> str:
    """调用 Claude API"""
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=8192,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return response.content[0].text


def analyze_topics(kb: KnowledgeBase) -> list[Topic]:
    """LLM 归纳主题"""
    summary = _kb_summary(kb)

    system = """你是一个知识库分析师。你的任务是从知识库的所有节点中归纳出用户会用来思考的"主题"。
主题不是道法术器的维度，而是用户在真实场景中会用的思考词汇，如"决策"、"风险"、"学习"、"情绪"、"领导力"等。

要求：
1. 从节点内容中归纳，不要预设
2. 每个主题必须有至少2本书的节点覆盖（如果只有1本书，不足以成为跨书主题）
3. 每个主题写一段跨书综合描述
4. 输出 JSON 数组"""

    user = f"""{summary}

请归纳出所有跨书主题。输出严格 JSON 格式：

```json
[
  {{
    "name": "主题名",
    "description": "一句话描述这个主题覆盖什么",
    "related_dao": ["道1", "道3"],
    "related_nodes": ["Same_as_Ever:法1", "The_Social_Animal:法8"],
    "cross_book_summary": "150字左右的跨书综合描述"
  }}
]
```"""

    result = _call_llm(system, user)
    return _parse_topics(result)


def analyze_duplicates(kb: KnowledgeBase) -> list[SemanticDuplicate]:
    """LLM 发现语义重复的节点"""
    summary = _kb_summary(kb)

    system = """你是一个知识库去重专家。你的任务是找出跨书之间语义高度相似的节点对。
不是标题相似，而是因果机制或方法描述在本质上说的是同一件事。

注意：
- 同一本书内的节点不算重复（那是提取时已处理的）
- 只找跨书的重复
- 相似但角度不同的不算重复（如同一现象的不同解释机制）"""

    user = f"""{summary}

找出跨书语义重复的节点对。如果没有发现则返回空数组。输出严格 JSON：

```json
[
  {{
    "node_a": "Same_as_Ever:法27",
    "node_b": "The_Social_Animal:法19",
    "title_a": "节点A标题",
    "title_b": "节点B标题",
    "similarity": "描述相似之处",
    "recommendation": "建议如何处理（保留两者但标注关联 / 合并 / 其他）"
  }}
]
```"""

    result = _call_llm(system, user)
    return _parse_duplicates(result)


def analyze_connections(kb: KnowledgeBase) -> list[CrossBookConnection]:
    """LLM 发现跨书隐含关联"""
    summary = _kb_summary(kb)

    system = """你是一个知识网络分析师。你的任务是找出跨书之间有隐含关联但未被显式标注的节点对。

隐含关联的类型：
1. A书的术是B书的法的具体实现
2. A书的法和B书的法描述同一现象的不同层面
3. A书的器可以用来验证B书的法
4. A书的势影响了B书的法的适用边界

只关注有实质意义的关联，不要为了数量而凑。"""

    user = f"""{summary}

找出最有价值的跨书隐含关联（最多15条）。输出严格 JSON：

```json
[
  {{
    "node_a": "Same_as_Ever:法6",
    "node_b": "The_Social_Animal:法20",
    "title_a": "节点A标题",
    "title_b": "节点B标题",
    "relationship": "描述这个关联的实质"
  }}
]
```"""

    result = _call_llm(system, user)
    return _parse_connections(result)


def analyze_gaps(kb: KnowledgeBase) -> list[KnowledgeGap]:
    """LLM 识别知识库空白区域"""
    summary = _kb_summary(kb)

    system = """你是一个知识库诊断师。你的任务是识别当前知识库的空白区域——
哪些重要的知识领域目前覆盖不足或完全缺失。

考虑：
1. 道的类别分布是否均衡
2. 某些道下面的法是否过少
3. 哪些重要的人生/决策主题没有被覆盖
4. 术和器是否有孤立节点（缺少上位关系）"""

    user = f"""{summary}

诊断知识库的空白区域。输出严格 JSON：

```json
[
  {{
    "area": "空白领域名称",
    "description": "缺什么、为什么这个空白重要",
    "severity": "high/medium/low"
  }}
]
```"""

    result = _call_llm(system, user)
    return _parse_gaps(result)


def analyze_divergences(kb: KnowledgeBase) -> list[BookDivergence]:
    """LLM 发现作者之间的分歧"""
    summary = _kb_summary(kb)

    system = """你是一个学术辩论分析师。你的任务是找出不同作者之间的观点分歧——
同一主题上不同作者的立场差异、解释差异或方法论差异。

分歧是高价值信息：它们揭示了知识的边界和争议区域。"""

    user = f"""{summary}

找出作者之间的分歧（如果存在）。如果没有明显分歧则返回空数组。输出严格 JSON：

```json
[
  {{
    "topic": "分歧主题",
    "authors": ["Housel", "Brooks"],
    "description": "描述分歧的具体内容和背后的原因"
  }}
]
```"""

    result = _call_llm(system, user)
    return _parse_divergences(result)


def run_analysis(kb: KnowledgeBase) -> AnalysisResult:
    """运行完整分析流程"""
    print("  [analyze] 归纳主题...")
    topics = analyze_topics(kb)
    print(f"    → {len(topics)} 个主题")

    print("  [analyze] 检测语义重复...")
    duplicates = analyze_duplicates(kb)
    print(f"    → {len(duplicates)} 对重复")

    print("  [analyze] 发现跨书关联...")
    connections = analyze_connections(kb)
    print(f"    → {len(connections)} 条关联")

    print("  [analyze] 识别知识空白...")
    gaps = analyze_gaps(kb)
    print(f"    → {len(gaps)} 个空白")

    print("  [analyze] 发现作者分歧...")
    divergences = analyze_divergences(kb)
    print(f"    → {len(divergences)} 处分歧")

    return AnalysisResult(
        topics=topics,
        duplicates=duplicates,
        connections=connections,
        gaps=gaps,
        divergences=divergences,
    )


# ── JSON 解析工具 ──────────────────────────────────────────


def _extract_json(text: str) -> str:
    """从 LLM 输出中提取 JSON 块"""
    # 尝试 ```json ... ``` 格式
    import re
    m = re.search(r'```json\s*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # 尝试直接 [ ... ] 格式
    m = re.search(r'(\[.*\])', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text.strip()


def _parse_topics(text: str) -> list[Topic]:
    data = json.loads(_extract_json(text))
    return [
        Topic(
            name=t["name"],
            description=t["description"],
            related_dao=t.get("related_dao", []),
            related_nodes=t.get("related_nodes", []),
            cross_book_summary=t.get("cross_book_summary", ""),
        )
        for t in data
    ]


def _parse_duplicates(text: str) -> list[SemanticDuplicate]:
    data = json.loads(_extract_json(text))
    return [
        SemanticDuplicate(
            node_a=d["node_a"],
            node_b=d["node_b"],
            title_a=d.get("title_a", ""),
            title_b=d.get("title_b", ""),
            similarity=d.get("similarity", ""),
            recommendation=d.get("recommendation", ""),
        )
        for d in data
    ]


def _parse_connections(text: str) -> list[CrossBookConnection]:
    data = json.loads(_extract_json(text))
    return [
        CrossBookConnection(
            node_a=c["node_a"],
            node_b=c["node_b"],
            title_a=c.get("title_a", ""),
            title_b=c.get("title_b", ""),
            relationship=c.get("relationship", ""),
        )
        for c in data
    ]


def _parse_gaps(text: str) -> list[KnowledgeGap]:
    data = json.loads(_extract_json(text))
    return [
        KnowledgeGap(
            area=g["area"],
            description=g["description"],
            severity=g.get("severity", "medium"),
        )
        for g in data
    ]


def _parse_divergences(text: str) -> list[BookDivergence]:
    data = json.loads(_extract_json(text))
    return [
        BookDivergence(
            topic=d["topic"],
            authors=d.get("authors", []),
            description=d["description"],
        )
        for d in data
    ]


# ── CLI 入口 ──────────────────────────────────────────


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from parse import parse_knowledge_base

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent
    print(f"解析知识库: {root}")
    kb = parse_knowledge_base(root)
    print(f"解析完成: {kb.total_nodes} 节点\n")

    print("开始 LLM 分析...")
    result = run_analysis(kb)

    print(f"\n=== 分析结果 ===")
    print(f"主题: {len(result.topics)}")
    for t in result.topics:
        print(f"  - {t.name}: {t.description}")

    print(f"\n语义重复: {len(result.duplicates)}")
    for d in result.duplicates:
        print(f"  - {d.node_a} ≈ {d.node_b}: {d.similarity[:50]}")

    print(f"\n跨书关联: {len(result.connections)}")
    for c in result.connections:
        print(f"  - {c.node_a} ↔ {c.node_b}: {c.relationship[:50]}")

    print(f"\n知识空白: {len(result.gaps)}")
    for g in result.gaps:
        print(f"  - [{g.severity}] {g.area}: {g.description[:50]}")

    print(f"\n作者分歧: {len(result.divergences)}")
    for d in result.divergences:
        print(f"  - {d.topic}: {d.description[:50]}")
