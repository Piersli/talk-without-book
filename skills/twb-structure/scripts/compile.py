"""
compile.py — Wiki 编译入口

用法:
    python compile.py [项目根目录]

    默认项目根目录为 tools/compile/../../（即 talkwithbook/）

流程:
    1. parse  — 读取 books/ 和 dao/ → 结构化数据
    2. analyze — LLM 跨书分析（主题、去重、关联、空白、分歧）
    3. render  — LLM 生成 wiki/ 页面
    4. validate — 检查完整性
"""

import sys
import time
from pathlib import Path

# 确保能 import 同目录的模块
sys.path.insert(0, str(Path(__file__).parent))

from parse import parse_knowledge_base
from analyze import run_analysis
from render import render_wiki
from validate import validate_wiki


def compile_wiki(root: Path | None = None):
    """编译完整 Wiki"""
    if root is None:
        root = Path(__file__).parent.parent.parent

    wiki_dir = root / "wiki"
    start = time.time()

    print("=" * 50)
    print(f"读后无书 (talk without book) Wiki 编译器")
    print(f"项目根目录: {root}")
    print("=" * 50)

    # Phase 1: Parse
    print(f"\n[1/4] 解析知识库...")
    kb = parse_knowledge_base(root)
    print(f"  → 道: {len(kb.dao)} | 书: {len(kb.books)} | 总节点: {kb.total_nodes}")
    for name, book in kb.books.items():
        print(f"    {name}: 法{len(book.fa)} 术{len(book.shu)} 器{len(book.qi)} 势{len(book.shi)}")

    # Phase 2: Analyze
    print(f"\n[2/4] LLM 跨书分析...")
    analysis = run_analysis(kb)

    # Phase 3: Render
    print(f"\n[3/4] 生成 Wiki 页面...")
    render_wiki(kb, analysis, wiki_dir)

    # Phase 4: Validate
    print(f"\n[4/4] 完整性检查...")
    issues, coverage = validate_wiki(kb, wiki_dir)

    elapsed = time.time() - start

    # 输出总结
    print("\n" + "=" * 50)
    print(f"编译完成！耗时 {elapsed:.1f}s")
    print(f"Wiki 目录: {wiki_dir}")
    print(coverage)

    if issues:
        print(f"\n⚠ 发现 {len(issues)} 个问题：")
        for issue in issues[:10]:
            print(f"  {issue}")
        if len(issues) > 10:
            print(f"  ... 还有 {len(issues) - 10} 个问题")
    else:
        print("\n✓ 无完整性问题")

    print("=" * 50)
    return len(issues) == 0


if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    success = compile_wiki(root)
    sys.exit(0 if success else 1)
