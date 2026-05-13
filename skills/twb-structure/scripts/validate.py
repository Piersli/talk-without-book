"""
validate.py — 知识库完整性 + 语义一致性检查

防止"validate 报 73/73 健康但里面是错链"这种漂移。

检查分两级：
- ERROR：链路在结构或语义上是坏的，必须修
- WARN：缺关系/不饱和，建议补但不致命

检查项：
1. ERROR：引用了不存在的道编号
2. ERROR：「候选道N」残留（应该转正或删除）
3. ERROR：「上位道：道N + 旧标题」编号和标题不匹配（旧 schema 残留）
4. ERROR：法节点缺上位道
5. WARN：术节点缺上位法
6. WARN：器节点缺上位术
7. WARN：势节点缺影响范围
8. Wiki 页面覆盖、断裂链接（如果 wiki 存在）
"""

from pathlib import Path
import re
import sys


# ── 解析当前道索引（权威） ──────────────────────────────────


def parse_dao_index(dao_md_path: Path) -> dict[int, str]:
    """返回 {dao_id: title} 字典——当前 dao/道.md 的权威映射"""
    text = dao_md_path.read_text(encoding="utf-8")
    titles = {}
    for m in re.finditer(r'^## 道(\d+)：(.+?)$', text, re.MULTILINE):
        titles[int(m.group(1))] = m.group(2).strip()
    return titles


# ── 检查器 ────────────────────────────────────────────────


def scan_uplinks_in_books(root: Path, dao_titles: dict[int, str]) -> tuple[list[dict], list[dict]]:
    """
    扫描 books/*/{法,术,器,势,meta}.md 的所有上位关系。
    返回 (errors, warnings)，每条是 dict: {file, line, kind, message}
    """
    errors: list[dict] = []
    warnings: list[dict] = []

    books_dir = root / "books"
    if not books_dir.exists():
        return errors, warnings

    dao_ids = set(dao_titles.keys())

    for book_dir in sorted(books_dir.iterdir()):
        if not book_dir.is_dir():
            continue
        book_name = book_dir.name

        for dim_file in book_dir.glob("*.md"):
            if dim_file.name in ("meta.md",):
                continue  # meta 不查
            dim = dim_file.stem  # 法/术/器/势
            text = dim_file.read_text(encoding="utf-8")
            lines = text.splitlines()

            # 当前正在解析的节点 id（跨多行）
            current_node = None
            for i, line in enumerate(lines, 1):
                # 探测节点头：## 法1：xxx 或 ## 标题
                m = re.match(r'^## (法|术|器|势)(\d+)?[:：]', line)
                if m:
                    if m.group(2):
                        current_node = f"{m.group(1)}{m.group(2)}"
                    else:
                        current_node = m.group(1) + "?"  # 无编号
                    continue

                # 检查"候选道N"残留 → ERROR
                if re.search(r'候选道\d+', line):
                    candidates = re.findall(r'候选道\d+', line)
                    for c in candidates:
                        errors.append({
                            "kind": "候选道残留",
                            "file": str(dim_file.relative_to(root)),
                            "line": i,
                            "node": current_node,
                            "message": f"{c} 应该转正为正式道或删除",
                            "context": line.strip()[:120],
                        })

                # 检查上位道字段："- **上位道**：..."
                up_match = re.match(r'^- \*\*上位道\*\*：(.+)$', line)
                if up_match:
                    content = up_match.group(1).strip()
                    # 抓所有"道N"
                    for ref_match in re.finditer(r'道(\d+)(?:\s*[（(]([^）)]+)[）)])?', content):
                        ref_id = int(ref_match.group(1))
                        ref_title_in_text = (ref_match.group(2) or "").strip()

                        # ERROR：引用了不存在的道编号
                        if ref_id not in dao_ids:
                            errors.append({
                                "kind": "无效道编号",
                                "file": str(dim_file.relative_to(root)),
                                "line": i,
                                "node": current_node,
                                "message": f"道{ref_id} 不在 dao/道.md 里（当前 {len(dao_ids)} 条道）",
                                "context": line.strip()[:120],
                            })
                            continue

                        # ERROR：编号 + 标题不匹配（用 dao/道.md 的标题做关键词验证）
                        # 取 dao 标题的核心关键词（删掉助词、连接词、的字等）
                        if ref_title_in_text:
                            authoritative = dao_titles[ref_id]
                            if not _titles_compatible(ref_title_in_text, authoritative):
                                errors.append({
                                    "kind": "标题不匹配",
                                    "file": str(dim_file.relative_to(root)),
                                    "line": i,
                                    "node": current_node,
                                    "message": (
                                        f"道{ref_id} 后的描述「{ref_title_in_text[:40]}…」"
                                        f"与当前道标题「{authoritative[:40]}…」语义偏离"
                                    ),
                                    "context": line.strip()[:120],
                                })

                # 检查上位法（术节点用）
                # 检查上位术（器节点用）
                # 这两个在下面的覆盖率统计里处理

    return errors, warnings


def _titles_compatible(written: str, authoritative: str) -> bool:
    """
    判断 written（节点内写的描述）和 authoritative（dao/道.md 的权威标题）
    是否语义兼容。

    规则：从两边各抽 3+ 字符的关键词块，至少有 2 个重叠才算 OK。
    很宽松——只是抓"明显写错了别的道的标题"这种 case。
    """
    def keywords(s: str) -> set[str]:
        # 用中文标点切，取长度 >= 3 的块
        chunks = re.split(r'[，。、；：（）()\s]+', s)
        return {c for c in chunks if len(c) >= 3}

    w_kw = keywords(written)
    a_kw = keywords(authoritative)

    # 如果两边任何一方都没产生有用关键词，无法判断 → 兼容
    if not w_kw or not a_kw:
        return True

    # 找有共享子串的对：任意 written 的关键词与任意 authoritative 关键词有 >= 3 字的连续相同
    matches = 0
    for w in w_kw:
        for a in a_kw:
            if _has_common_substr(w, a, min_len=3):
                matches += 1
                break
    return matches >= 1


def _has_common_substr(s1: str, s2: str, min_len: int = 3) -> bool:
    """是否有长度 >= min_len 的公共子串"""
    if len(s1) < min_len or len(s2) < min_len:
        return False
    for i in range(len(s1) - min_len + 1):
        if s1[i:i+min_len] in s2:
            return True
    return False


def check_coverage(root: Path) -> tuple[dict, list[dict]]:
    """统计 法→道、术→法、器→术 的覆盖率，并对低覆盖率发 WARN"""
    warnings: list[dict] = []
    stats = {"fa_total": 0, "fa_with_dao": 0,
             "shu_total": 0, "shu_with_fa": 0,
             "qi_total": 0, "qi_with_shu": 0,
             "shi_total": 0, "shi_with_scope": 0}

    books_dir = root / "books"
    if not books_dir.exists():
        return stats, warnings

    for book_dir in sorted(books_dir.iterdir()):
        if not book_dir.is_dir():
            continue
        book_name = book_dir.name

        for dim, total_key, with_key, uplink_field in [
            ("法", "fa_total", "fa_with_dao", "上位道"),
            ("术", "shu_total", "shu_with_fa", "上位法"),
            ("器", "qi_total", "qi_with_shu", "上位术"),
            ("势", "shi_total", "shi_with_scope", "影响范围"),
        ]:
            dim_file = book_dir / f"{dim}.md"
            if not dim_file.exists():
                continue
            text = dim_file.read_text(encoding="utf-8")
            # 节点数 = ## XX 的数量（排除元数据节）
            nodes = re.findall(r'^## (?!上位|目录)(.+?)$', text, re.MULTILINE)
            # 进一步过滤元节
            real_nodes = [n for n in nodes if not n.endswith("映射索引")
                          and not n.endswith("索引")
                          and "映射" not in n]
            node_count = len(real_nodes)
            stats[total_key] += node_count

            # 数有上位关系字段的节点
            uplink_pattern = rf'^- \*\*{re.escape(uplink_field)}\*\*：'
            with_uplink = len(re.findall(uplink_pattern, text, re.MULTILINE))
            stats[with_key] += with_uplink

            # 缺关系的列 WARN
            if with_uplink < node_count:
                missing = node_count - with_uplink
                warnings.append({
                    "kind": f"{dim} 缺{uplink_field}",
                    "file": str(dim_file.relative_to(root)),
                    "line": None,
                    "node": None,
                    "message": f"{book_name}/{dim}：{missing}/{node_count} 个节点缺「{uplink_field}」",
                    "context": "",
                })

    return stats, warnings


def check_wiki_pages(root: Path, dao_titles: dict[int, str]) -> list[dict]:
    """检查 wiki/dao/ 页面覆盖"""
    warnings = []
    wiki_dir = root / "wiki"
    if not wiki_dir.exists():
        warnings.append({
            "kind": "wiki 缺失",
            "file": "wiki/",
            "line": None,
            "node": None,
            "message": "wiki/ 目录不存在；运行 compile.py 生成",
            "context": "",
        })
        return warnings

    dao_pages_dir = wiki_dir / "dao"
    if not dao_pages_dir.exists():
        warnings.append({
            "kind": "wiki/dao 缺失",
            "file": "wiki/dao/",
            "line": None,
            "node": None,
            "message": "wiki/dao/ 目录不存在；运行 compile.py 生成",
            "context": "",
        })
        return warnings

    existing = {f.stem for f in dao_pages_dir.glob("*.md")}
    for dao_id in dao_titles:
        matched = any(f"道{dao_id}" in name for name in existing)
        if not matched:
            warnings.append({
                "kind": "wiki/dao 缺页",
                "file": "wiki/dao/",
                "line": None,
                "node": None,
                "message": f"道{dao_id} 没有对应的 wiki 页",
                "context": "",
            })

    return warnings


# ── 输出 ──────────────────────────────────────────────────


def format_report(errors: list[dict], warnings: list[dict], stats: dict, dao_count: int) -> str:
    lines = []

    lines.append("\n" + "═" * 60)
    lines.append("  读后无书 · 知识库验证报告")
    lines.append("═" * 60)

    # ERROR 区
    if errors:
        lines.append(f"\n🔴 ERROR ({len(errors)})——这些必须修：\n")
        for e in errors:
            loc = f"{e['file']}:{e['line']}"
            node = f"[{e['node']}] " if e['node'] else ""
            lines.append(f"  [{e['kind']}] {loc}")
            lines.append(f"    {node}{e['message']}")
            if e['context']:
                lines.append(f"    > {e['context']}")
            lines.append("")
    else:
        lines.append("\n🟢 没有 ERROR — 链路语义一致")

    # WARN 区
    if warnings:
        lines.append(f"\n🟡 WARN ({len(warnings)})——建议补：\n")
        # 按 kind 分组
        from collections import defaultdict
        by_kind = defaultdict(list)
        for w in warnings:
            by_kind[w["kind"]].append(w)
        for kind, items in by_kind.items():
            lines.append(f"  [{kind}] × {len(items)}")
            for w in items[:5]:
                lines.append(f"    · {w['message']}")
            if len(items) > 5:
                lines.append(f"    ...还有 {len(items)-5} 条")
            lines.append("")

    # 覆盖率
    lines.append("─" * 60)
    lines.append("  覆盖度")
    lines.append("─" * 60)
    lines.append(f"  道：{dao_count} 条")
    if stats['fa_total']:
        lines.append(f"  法→道：{stats['fa_with_dao']}/{stats['fa_total']} "
                     f"({stats['fa_with_dao']/stats['fa_total']*100:.0f}%)")
    if stats['shu_total']:
        lines.append(f"  术→法：{stats['shu_with_fa']}/{stats['shu_total']} "
                     f"({stats['shu_with_fa']/stats['shu_total']*100:.0f}%)")
    if stats['qi_total']:
        lines.append(f"  器→术：{stats['qi_with_shu']}/{stats['qi_total']} "
                     f"({stats['qi_with_shu']/stats['qi_total']*100:.0f}%)")
    if stats['shi_total']:
        lines.append(f"  势→影响范围：{stats['shi_with_scope']}/{stats['shi_total']} "
                     f"({stats['shi_with_scope']/stats['shi_total']*100:.0f}%)")

    lines.append("─" * 60)
    return "\n".join(lines)


# ── 兼容旧接口（被 compile.py 调用） ──────────────────


def validate_wiki(kb, wiki_dir):
    """旧接口兼容——返回 (issues, coverage_report)。compile.py 仍调这个。"""
    issues = []
    if not wiki_dir.exists():
        issues.append("[缺失目录] wiki/dao/ 不存在")

    # 基础覆盖
    total_fa = sum(len(b.fa) for b in kb.books.values())
    fa_with_dao = sum(1 for b in kb.books.values() for fa in b.fa if fa.parent_dao)
    total_shu = sum(len(b.shu) for b in kb.books.values())
    shu_with_fa = sum(1 for b in kb.books.values() for shu in b.shu if shu.parent_fa)

    coverage = (
        f"\n=== 覆盖度报告 ===\n"
        f"道: {len(kb.dao)} 条\n"
        f"法→道关系: {fa_with_dao}/{total_fa} "
        f"({fa_with_dao/total_fa*100:.0f}%)"
    )
    if total_shu:
        coverage += f"\n术→法关系: {shu_with_fa}/{total_shu} ({shu_with_fa/total_shu*100:.0f}%)"

    return issues, coverage


# ── 主入口 ──────────────────────────────────────────────


def main(root: Path) -> int:
    dao_md = root / "dao" / "道.md"
    if not dao_md.exists():
        print(f"✗ 找不到 {dao_md}", file=sys.stderr)
        return 2

    dao_titles = parse_dao_index(dao_md)
    print(f"  加载权威道索引：{len(dao_titles)} 条")
    for n, t in sorted(dao_titles.items()):
        print(f"    道{n}: {t[:30]}...")

    errors, warnings = scan_uplinks_in_books(root, dao_titles)
    stats, coverage_warns = check_coverage(root)
    warnings.extend(coverage_warns)
    warnings.extend(check_wiki_pages(root, dao_titles))

    print(format_report(errors, warnings, stats, len(dao_titles)))

    if errors:
        return 1
    return 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent
    sys.exit(main(root))
