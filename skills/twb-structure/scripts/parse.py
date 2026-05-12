"""
parse.py — 将 books/ 和 dao/ 下的 markdown 文件解析为结构化数据

输入：项目根目录路径
输出：KnowledgeBase 对象（包含所有道和所有书的法/术/器/势）
"""

import re
from pathlib import Path
from models import (
    KnowledgeBase, BookData, DaoNode, FaNode, ShuNode, QiNode, ShiNode
)


def parse_dao(dao_path: Path) -> list[DaoNode]:
    """解析 dao/道.md → DaoNode 列表"""
    if not dao_path.exists():
        return []

    text = dao_path.read_text(encoding="utf-8")
    nodes = []

    # 按 ## 道N 分割
    sections = re.split(r'\n(?=## 道\d+)', text)

    for section in sections:
        m = re.match(r'## (道\d+)：(.+)', section)
        if not m:
            continue

        dao_id = m.group(1)
        title = m.group(2).strip()

        category = _extract_field(section, "类别")
        description = _extract_field(section, "表述")
        child_fa = _extract_field(section, "下位法")
        relations = _extract_field(section, "与其他道的关系")

        # 解析触碰书籍
        books = {}
        books_section = _extract_block(section, "触碰此道的书籍")
        if books_section:
            for line in books_section.split("\n"):
                # 格式：- Author《Book》— angle 或 - Brooks《...》— ...
                bm = re.match(r'\s*-\s+\w+[《](.+?)[》].*?[—–-]\s*(.+)', line)
                if bm:
                    books[bm.group(1).strip()] = bm.group(2).strip()

        nodes.append(DaoNode(
            id=dao_id,
            title=title,
            category=category,
            description=description,
            books=books,
            child_fa=_parse_id_list(child_fa),
            relations=relations,
        ))

    return nodes


def parse_book(book_dir: Path) -> BookData:
    """解析一本书的所有维度文件 → BookData"""
    book_name = book_dir.name
    book = BookData(name=book_name)

    fa_path = book_dir / "法.md"
    if fa_path.exists():
        book.fa = _parse_fa(fa_path, book_name)

    shu_path = book_dir / "术.md"
    if shu_path.exists():
        book.shu = _parse_shu(shu_path, book_name)

    qi_path = book_dir / "器.md"
    if qi_path.exists():
        book.qi = _parse_qi(qi_path, book_name)

    shi_path = book_dir / "势.md"
    if shi_path.exists():
        book.shi = _parse_shi(shi_path, book_name)

    meta_path = book_dir / "meta.md"
    if meta_path.exists():
        book.meta = {"raw": meta_path.read_text(encoding="utf-8")}

    return book


def parse_knowledge_base(root: Path) -> KnowledgeBase:
    """解析整个知识库 → KnowledgeBase"""
    kb = KnowledgeBase()

    # 解析全局道
    dao_path = root / "dao" / "道.md"
    kb.dao = parse_dao(dao_path)

    # 解析每本书
    books_dir = root / "books"
    if books_dir.exists():
        for book_dir in sorted(books_dir.iterdir()):
            if book_dir.is_dir() and not book_dir.name.startswith("."):
                kb.books[book_dir.name] = parse_book(book_dir)

    return kb


# ── 内部解析函数 ──────────────────────────────────────────


def _parse_fa(path: Path, book_name: str) -> list[FaNode]:
    """解析法.md（法都是编号格式）"""
    text = path.read_text(encoding="utf-8")
    nodes = []
    sections = re.split(r'\n(?=## 法\d+)', text)

    for section in sections:
        m = re.match(r'## (法\d+)：(.+?)(?:\s*[—–-]\s*(.+))?$', section, re.MULTILINE)
        if not m:
            continue

        full_title = m.group(2).strip()
        if m.group(3):
            full_title += " — " + m.group(3).strip()

        mechanism = _extract_field(section, "因果机制")
        evidence = _extract_field(section, "原文依据")
        boundary = _extract_field(section, "适用边界")
        parent_dao_raw = _extract_field(section, "上位道")

        nodes.append(FaNode(
            id=m.group(1),
            book=book_name,
            title=full_title,
            causal_mechanism=mechanism,
            evidence=evidence,
            boundary=boundary,
            parent_dao=_parse_dao_refs(parent_dao_raw),
            keywords=_extract_keywords(full_title + " " + mechanism),
        ))

    return nodes


def _parse_shu(path: Path, book_name: str) -> list[ShuNode]:
    """解析术.md — 兼容编号格式(术1：...)和无编号格式(## 标题)"""
    text = path.read_text(encoding="utf-8")
    nodes = []

    # 按 ## 分割所有 section（跳过文件头部）
    sections = re.split(r'\n(?=## )', text)

    counter = 0
    for section in sections:
        # 跳过头部（# 开头的标题行或无 ## 的 section）
        if not section.strip().startswith("## "):
            continue

        # 尝试编号格式：## 术1：标题 — 副标题
        m = re.match(r'## (术\d+)：(.+?)(?:\s*[—–-]\s*(.+))?$', section, re.MULTILINE)
        if m:
            node_id = m.group(1)
            full_title = m.group(2).strip()
            if m.group(3):
                full_title += " — " + m.group(3).strip()
        else:
            # 无编号格式：## 标题
            m2 = re.match(r'## (.+)', section)
            if not m2:
                continue
            counter += 1
            node_id = f"术{counter}"
            full_title = m2.group(1).strip()

        method = _extract_field(section, "方法描述")
        evidence = _extract_field(section, "原文依据")
        scenario = _extract_field(section, "适用场景")
        parent_fa_raw = _extract_field(section, "上位法")

        nodes.append(ShuNode(
            id=node_id,
            book=book_name,
            title=full_title,
            method=method,
            evidence=evidence,
            scenario=scenario,
            parent_fa=_parse_id_list(parent_fa_raw),
            keywords=_extract_keywords(full_title + " " + method),
        ))

    return nodes


def _parse_qi(path: Path, book_name: str) -> list[QiNode]:
    """解析器.md — 兼容编号和无编号格式，兼容"描述"和"工具描述"字段名"""
    text = path.read_text(encoding="utf-8")
    nodes = []

    sections = re.split(r'\n(?=## )', text)

    counter = 0
    for section in sections:
        if not section.strip().startswith("## "):
            continue

        # 尝试编号格式
        m = re.match(r'## (器\d+)：(.+?)(?:\s*[—–-]\s*(.+))?$', section, re.MULTILINE)
        if m:
            node_id = m.group(1)
            full_title = m.group(2).strip()
            if m.group(3):
                full_title += " — " + m.group(3).strip()
        else:
            m2 = re.match(r'## (.+)', section)
            if not m2:
                continue
            counter += 1
            node_id = f"器{counter}"
            full_title = m2.group(1).strip()

        # 兼容 "描述" 和 "工具描述" 两种字段名
        description = _extract_field(section, "描述") or _extract_field(section, "工具描述")
        source = _extract_field(section, "原文出处")
        usage = _extract_field(section, "使用方式")
        parent_shu_raw = _extract_field(section, "上位术")

        nodes.append(QiNode(
            id=node_id,
            book=book_name,
            title=full_title,
            description=description,
            source=source,
            usage=usage,
            parent_shu=_parse_id_list(parent_shu_raw),
            keywords=_extract_keywords(full_title + " " + description),
        ))

    return nodes


def _parse_shi(path: Path, book_name: str) -> list[ShiNode]:
    """解析势.md — 兼容编号和无编号格式，兼容不同字段名"""
    text = path.read_text(encoding="utf-8")
    nodes = []

    sections = re.split(r'\n(?=## )', text)

    counter = 0
    for section in sections:
        if not section.strip().startswith("## "):
            continue

        # 尝试编号格式
        m = re.match(r'## (势\d+)：(.+?)(?:\s*[—–-]\s*(.+))?$', section, re.MULTILINE)
        if m:
            node_id = m.group(1)
            full_title = m.group(2).strip()
            if m.group(3):
                full_title += " — " + m.group(3).strip()
        else:
            m2 = re.match(r'## (.+)', section)
            if not m2:
                continue
            counter += 1
            node_id = f"势{counter}"
            full_title = m2.group(1).strip()

        # 兼容 "判断内容" 和 "趋势判断" 两种字段名
        content = _extract_field(section, "判断内容") or _extract_field(section, "趋势判断")
        evidence = _extract_field(section, "原文依据")
        # 兼容 "影响范围" 和 "对当下的启示"
        impact = _extract_field(section, "影响范围") or _extract_field(section, "对当下的启示")
        validity = _extract_field(section, "时效性")

        nodes.append(ShiNode(
            id=node_id,
            book=book_name,
            title=full_title,
            content=content,
            evidence=evidence,
            impact=impact,
            validity=validity,
            keywords=_extract_keywords(full_title + " " + content),
        ))

    return nodes


# ── 工具函数 ──────────────────────────────────────────


def _extract_field(section: str, field_name: str) -> str:
    """从 markdown section 中提取 `- **字段名**：内容`"""
    pattern = rf'-\s+\*\*{re.escape(field_name)}\*\*[：:]\s*(.+?)(?=\n-\s+\*\*|\n##|\n---|\Z)'
    m = re.search(pattern, section, re.DOTALL)
    if m:
        return m.group(1).strip()
    return ""


def _extract_block(section: str, field_name: str) -> str:
    """提取字段下方的多行内容块（如触碰此道的书籍）"""
    pattern = rf'-\s+\*\*{re.escape(field_name)}\*\*[：:]\s*\n((?:\s+-.+\n?)*)'
    m = re.search(pattern, section)
    if m:
        return m.group(1).strip()
    # 也尝试同一行有内容的情况
    pattern2 = rf'-\s+\*\*{re.escape(field_name)}\*\*[：:]\s*\n((?:\s+-.+\n?)+)'
    m2 = re.search(pattern2, section)
    if m2:
        return m2.group(1).strip()
    return ""


def _parse_dao_refs(text: str) -> list[str]:
    """从文本中提取道的引用：道1, 道2, ..."""
    return re.findall(r'道\d+', text)


def _parse_id_list(text: str) -> list[str]:
    """从文本中提取法/术/器的 ID 引用"""
    return re.findall(r'[法术器势]\d+', text)


def _extract_keywords(text: str) -> list[str]:
    """从文本中提取中文关键词（简单分词）"""
    # 提取中文词组（2-6字）
    chinese_words = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
    # 提取英文专有名词
    english_terms = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*', text)
    # 去重保序
    seen = set()
    keywords = []
    for w in chinese_words + english_terms:
        if w not in seen and len(w) >= 2:
            seen.add(w)
            keywords.append(w)
    return keywords


# ── CLI 入口 ──────────────────────────────────────────


if __name__ == "__main__":
    import sys
    import json

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent
    kb = parse_knowledge_base(root)

    print(f"=== 知识库解析完成 ===")
    print(f"道: {len(kb.dao)} 条")
    print(f"书: {len(kb.books)} 本")
    for name, book in kb.books.items():
        print(f"  {name}: 法{len(book.fa)} 术{len(book.shu)} 器{len(book.qi)} 势{len(book.shi)}")
    print(f"总节点数: {kb.total_nodes}")

    # 验证：打印每条法的上位道
    print(f"\n=== 法→道 关联检查 ===")
    for fa in kb.all_fa:
        dao_refs = ", ".join(fa.parent_dao) if fa.parent_dao else "⚠ 无上位道"
        print(f"  [{fa.book}] {fa.id}: {fa.title[:30]}... → {dao_refs}")
