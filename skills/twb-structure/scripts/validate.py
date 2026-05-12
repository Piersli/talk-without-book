"""
validate.py — Wiki 完整性检查

检查项：
1. 所有道都有对应的 wiki 页面
2. 所有 [[链接]] 指向存在的页面
3. 每条法都有上位道
4. 每条术都有上位法（新格式）
5. 统计覆盖度
"""

from pathlib import Path
import re
from models import KnowledgeBase


def validate_wiki(kb: KnowledgeBase, wiki_dir: Path) -> list[str]:
    """运行所有检查，返回问题列表"""
    issues = []

    # 1. 检查道页面覆盖
    dao_dir = wiki_dir / "dao"
    if dao_dir.exists():
        existing_dao_files = {f.stem for f in dao_dir.glob("*.md")}
        for dao in kb.dao:
            matched = any(dao.id in fname for fname in existing_dao_files)
            if not matched:
                issues.append(f"[缺失页面] {dao.id} 没有对应的 wiki/dao/ 页面")
    else:
        issues.append("[缺失目录] wiki/dao/ 不存在")

    # 2. 检查 wiki 链接完整性
    all_pages = set()
    if wiki_dir.exists():
        for md_file in wiki_dir.rglob("*.md"):
            # 页面名 = 文件名（不含 .md）
            all_pages.add(md_file.stem)

        for md_file in wiki_dir.rglob("*.md"):
            content = md_file.read_text(encoding="utf-8")
            links = re.findall(r'\[\[(.+?)\]\]', content)
            for link in links:
                # 清理链接（去掉可能的路径前缀）
                link_name = link.split("/")[-1]
                if link_name not in all_pages:
                    issues.append(f"[断裂链接] {md_file.relative_to(wiki_dir)} 中的 [[{link}]] 指向不存在的页面")

    # 3. 检查法→道关系完整性
    dao_ids = {d.id for d in kb.dao}
    for book_name, book in kb.books.items():
        for fa in book.fa:
            if not fa.parent_dao:
                issues.append(f"[缺失关系] {book_name}/{fa.id} 没有上位道")
            else:
                for dao_ref in fa.parent_dao:
                    if dao_ref not in dao_ids:
                        issues.append(f"[无效引用] {book_name}/{fa.id} 引用了不存在的 {dao_ref}")

    # 4. 检查术→法关系（仅新格式有）
    for book_name, book in kb.books.items():
        fa_ids = {fa.id for fa in book.fa}
        for shu in book.shu:
            if shu.parent_fa:
                for fa_ref in shu.parent_fa:
                    if fa_ref not in fa_ids:
                        issues.append(f"[无效引用] {book_name}/{shu.id} 引用了不存在的 {fa_ref}")

    # 5. 统计覆盖度
    total_fa = sum(len(b.fa) for b in kb.books.values())
    fa_with_dao = sum(1 for b in kb.books.values() for fa in b.fa if fa.parent_dao)
    total_shu = sum(len(b.shu) for b in kb.books.values())
    shu_with_fa = sum(1 for b in kb.books.values() for shu in b.shu if shu.parent_fa)

    coverage_report = (
        f"\n=== 覆盖度报告 ===\n"
        f"道: {len(kb.dao)} 条\n"
        f"法→道关系: {fa_with_dao}/{total_fa} ({fa_with_dao/total_fa*100:.0f}%)\n"
        f"术→法关系: {shu_with_fa}/{total_shu} ({shu_with_fa/total_shu*100:.0f}%)" if total_shu > 0 else ""
    )

    return issues, coverage_report


if __name__ == "__main__":
    import sys
    from parse import parse_knowledge_base

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent.parent
    wiki_dir = root / "wiki"

    kb = parse_knowledge_base(root)
    issues, coverage = validate_wiki(kb, wiki_dir)

    if issues:
        print(f"发现 {len(issues)} 个问题：")
        for issue in issues:
            print(f"  {issue}")
    else:
        print("✓ 无问题")

    print(coverage)
