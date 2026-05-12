"""数据模型：知识库的结构化表示"""

from dataclasses import dataclass, field
from enum import Enum


class Dimension(Enum):
    DAO = "道"
    FA = "法"
    SHU = "术"
    QI = "器"
    SHI = "势"


@dataclass
class DaoNode:
    """全局道节点"""
    id: str                     # 道1, 道2, ...
    title: str                  # 一句断言
    category: str               # 人性类 / 世界类 / 关系类
    description: str            # 展开表述
    books: dict[str, str]       # {book_name: angle}
    child_fa: list[str]         # 下位法 ID 列表
    relations: str              # 与其他道的关系


@dataclass
class FaNode:
    """法节点（per-book）"""
    id: str                     # 法1, 法2, ...
    book: str                   # 所属书名
    title: str                  # 一句因果表述
    causal_mechanism: str       # 因果机制
    evidence: str               # 原文依据
    boundary: str               # 适用边界
    parent_dao: list[str]       # 上位道 ID
    keywords: list[str] = field(default_factory=list)


@dataclass
class ShuNode:
    """术节点（per-book）"""
    id: str
    book: str
    title: str
    method: str                 # 方法描述
    evidence: str               # 原文依据
    scenario: str               # 适用场景
    parent_fa: list[str]        # 上位法 ID
    keywords: list[str] = field(default_factory=list)


@dataclass
class QiNode:
    """器节点（per-book）"""
    id: str
    book: str
    title: str
    description: str            # 描述
    source: str                 # 原文出处
    usage: str                  # 使用方式
    parent_shu: list[str]       # 上位术 ID
    keywords: list[str] = field(default_factory=list)


@dataclass
class ShiNode:
    """势节点（per-book）"""
    id: str
    book: str
    title: str
    content: str                # 判断内容
    evidence: str               # 原文依据
    impact: str                 # 影响范围
    validity: str               # 时效性
    keywords: list[str] = field(default_factory=list)


@dataclass
class BookData:
    """一本书的全部结构化数据"""
    name: str
    fa: list[FaNode] = field(default_factory=list)
    shu: list[ShuNode] = field(default_factory=list)
    qi: list[QiNode] = field(default_factory=list)
    shi: list[ShiNode] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


@dataclass
class KnowledgeBase:
    """整个知识库"""
    dao: list[DaoNode] = field(default_factory=list)
    books: dict[str, BookData] = field(default_factory=dict)

    @property
    def total_nodes(self) -> int:
        total = len(self.dao)
        for book in self.books.values():
            total += len(book.fa) + len(book.shu) + len(book.qi) + len(book.shi)
        return total

    @property
    def all_fa(self) -> list[FaNode]:
        return [fa for book in self.books.values() for fa in book.fa]

    @property
    def all_shu(self) -> list[ShuNode]:
        return [shu for book in self.books.values() for shu in book.shu]

    @property
    def all_qi(self) -> list[QiNode]:
        return [qi for book in self.books.values() for qi in book.qi]

    @property
    def all_shi(self) -> list[ShiNode]:
        return [shi for book in self.books.values() for shi in book.shi]
