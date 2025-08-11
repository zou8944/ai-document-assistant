"""
不同意图对应的检索策略配置
为不同类型的查询提供优化的检索参数和处理策略
"""

from dataclasses import dataclass
from typing import Optional

from .intent_analyzer import QueryIntent


@dataclass
class RetrievalConfig:
    """检索配置类"""
    top_k: int                          # 检索结果数量
    score_threshold: float              # 相似度阈值
    enable_mmr: bool = False           # 是否启用最大边际相关性
    mmr_diversity_threshold: float = 0.5  # MMR多样性阈值
    context_expansion: bool = False     # 是否进行上下文扩展
    prefer_structured: bool = False     # 是否优先结构化内容
    summary_first: bool = False         # 是否优先使用摘要检索

    def __post_init__(self):
        """验证配置参数"""
        if self.top_k <= 0:
            raise ValueError("top_k must be positive")
        if not 0 <= self.score_threshold <= 1:
            raise ValueError("score_threshold must be between 0 and 1")
        if not 0 <= self.mmr_diversity_threshold <= 1:
            raise ValueError("mmr_diversity_threshold must be between 0 and 1")


# 不同意图的检索策略配置
INTENT_RETRIEVAL_CONFIGS: dict[QueryIntent, RetrievalConfig] = {

    # 概述类查询：需要获得全面的信息覆盖
    QueryIntent.OVERVIEW: RetrievalConfig(
        top_k=15,                       # 增加检索数量以获得更全面的信息
        score_threshold=0.2,            # 降低阈值以包含更多相关内容
        enable_mmr=True,                # 启用MMR以获得多样化的结果
        mmr_diversity_threshold=0.6,    # 较高多样性，避免重复信息
        context_expansion=True,         # 启用上下文扩展
        prefer_structured=True,         # 优先结构化内容（标题、章节等）
        summary_first=True              # 优先使用文档摘要进行检索
    ),

    # 操作指南类查询：重点关注步骤性和连贯性
    QueryIntent.HOW_TO: RetrievalConfig(
        top_k=10,                       # 适中数量，重点关注相关步骤
        score_threshold=0.25,           # 中等阈值
        enable_mmr=True,                # 启用MMR保持步骤多样性
        mmr_diversity_threshold=0.4,    # 较低多样性，保持步骤连贯性
        context_expansion=True,         # 扩展上下文获取完整步骤
        prefer_structured=True,         # 优先步骤性结构化内容
        summary_first=False             # 使用原始内容，保持步骤细节
    ),

    # 比较类查询：需要涵盖比较对象的不同方面
    QueryIntent.COMPARISON: RetrievalConfig(
        top_k=12,                       # 中等数量
        score_threshold=0.2,            # 较低阈值涵盖更多方面
        enable_mmr=True,                # 启用MMR获得多样化比较内容
        mmr_diversity_threshold=0.7,    # 高多样性以涵盖不同比较对象
        context_expansion=False,        # 不需要额外扩展
        prefer_structured=False,        # 不特别偏向结构化内容
        summary_first=False             # 使用原始内容保持比较细节
    ),

    # 事实查询类：精准检索相关信息
    QueryIntent.FACTUAL: RetrievalConfig(
        top_k=5,                        # 保持原有配置，精准检索
        score_threshold=0.3,            # 较高阈值确保相关性
        enable_mmr=False,               # 不需要多样性，注重相关性
        mmr_diversity_threshold=0.5,    # 默认值
        context_expansion=False,        # 不需要扩展
        prefer_structured=False,        # 不特别偏向
        summary_first=False             # 使用原始内容获得细节
    )
}


class RetrievalStrategyManager:
    """检索策略管理器"""

    def __init__(self, custom_configs: Optional[dict[QueryIntent, RetrievalConfig]] = None):
        """
        初始化策略管理器
        
        Args:
            custom_configs: 自定义配置，会覆盖默认配置
        """
        self.configs = INTENT_RETRIEVAL_CONFIGS.copy()

        if custom_configs:
            self.configs.update(custom_configs)

    def get_config(self, intent: QueryIntent) -> RetrievalConfig:
        """
        获取指定意图的检索配置
        
        Args:
            intent: 查询意图
            
        Returns:
            对应的检索配置
        """
        return self.configs.get(intent, self.configs[QueryIntent.FACTUAL])

    def update_config(self, intent: QueryIntent, config: RetrievalConfig) -> None:
        """
        更新指定意图的检索配置
        
        Args:
            intent: 查询意图
            config: 新的检索配置
        """
        config.__post_init__()  # 验证配置
        self.configs[intent] = config

    def get_all_configs(self) -> dict[QueryIntent, RetrievalConfig]:
        """获取所有配置"""
        return self.configs.copy()

    def reset_to_default(self) -> None:
        """重置为默认配置"""
        self.configs = INTENT_RETRIEVAL_CONFIGS.copy()


# 检索增强策略
class RetrievalEnhancer:
    """检索结果增强器"""

    @staticmethod
    def apply_mmr_filter(documents: list, diversity_threshold: float = 0.5) -> list:
        """
        应用最大边际相关性过滤
        
        Args:
            documents: 原始检索文档列表
            diversity_threshold: 多样性阈值
            
        Returns:
            经过MMR过滤的文档列表
        """
        # 简化的MMR实现 - 基于内容相似度去重
        if not documents:
            return documents

        filtered_docs = [documents[0]]  # 保留第一个（最相关的）

        for doc in documents[1:]:
            # 检查与已选择文档的相似度
            is_diverse = True
            doc_content = doc.get('content', '').lower()

            for selected_doc in filtered_docs:
                selected_content = selected_doc.get('content', '').lower()

                # 简单的内容重叠检查
                doc_words = set(doc_content.split())
                selected_words = set(selected_content.split())

                if len(doc_words) == 0 or len(selected_words) == 0:
                    continue

                # 计算Jaccard相似度
                intersection = doc_words.intersection(selected_words)
                union = doc_words.union(selected_words)
                similarity = len(intersection) / len(union) if union else 0

                if similarity > (1 - diversity_threshold):
                    is_diverse = False
                    break

            if is_diverse:
                filtered_docs.append(doc)

        return filtered_docs

    @staticmethod
    def enhance_with_context(documents: list, context_window: int = 2) -> list:
        """
        通过上下文信息增强检索结果
        
        Args:
            documents: 原始检索文档列表
            context_window: 上下文窗口大小
            
        Returns:
            增强后的文档列表
        """
        # 这里可以实现上下文扩展逻辑
        # 例如：查找相邻的文档chunks，获取更完整的上下文
        return documents

    @staticmethod
    def prioritize_structured_content(documents: list) -> list:
        """
        优先排序结构化内容（标题、列表等）
        
        Args:
            documents: 原始检索文档列表
            
        Returns:
            重新排序的文档列表
        """
        structured_docs = []
        regular_docs = []

        for doc in documents:
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})

            # 检查是否为结构化内容
            is_structured = (
                content.startswith('#') or          # Markdown标题
                content.startswith('- ') or         # 列表项
                content.startswith('1. ') or        # 数字列表
                '第' in content and '步' in content or  # 步骤
                metadata.get('content_type') in ['heading', 'list', 'procedural']
            )

            if is_structured:
                structured_docs.append(doc)
            else:
                regular_docs.append(doc)

        # 结构化内容优先，但保持原有相关性顺序
        return structured_docs + regular_docs


# 便捷函数
def create_retrieval_strategy_manager(custom_configs: Optional[dict[QueryIntent, RetrievalConfig]] = None) -> RetrievalStrategyManager:
    """创建检索策略管理器实例"""
    return RetrievalStrategyManager(custom_configs)


def get_default_config(intent: QueryIntent) -> RetrievalConfig:
    """获取指定意图的默认配置"""
    return INTENT_RETRIEVAL_CONFIGS.get(intent, INTENT_RETRIEVAL_CONFIGS[QueryIntent.FACTUAL])
