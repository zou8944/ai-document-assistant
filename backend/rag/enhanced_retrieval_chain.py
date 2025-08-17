"""
增强的RAG检索链实现
集成智能查询路由、意图分析和基于摘要的概述生成
"""

import logging
from typing import Any, Optional

from langchain_core.output_parsers import StrOutputParser

from vector_store.chroma_client import ChromaManager

from .cache_manager import SmartCacheManager
from .intent_analyzer import IntentAnalyzer, QueryIntent
from .prompt_templates import format_sources, get_prompt_by_intent
from .retrieval_chain import DocumentRetriever, QueryResponse, RetrievalChain
from .retrieval_strategies import RetrievalEnhancer, RetrievalStrategyManager
from .summary_based_overview import SummaryBasedOverviewGenerator
from .summary_manager import SummaryManager

logger = logging.getLogger(__name__)


class EnhancedDocumentRetriever(DocumentRetriever):
    """增强的文档检索器，支持动态配置和检索策略"""

    def __init__(self, chroma_manager: ChromaManager, collection_name: str,
                 embeddings, top_k: int = 5, score_threshold: float = 0.3):
        super().__init__(chroma_manager, collection_name, embeddings, top_k)
        self.score_threshold = score_threshold

    async def retrieve_documents(self, query: str, score_threshold: Optional[float] = None) -> list[dict[str, Any]]:
        """
        检索相关文档，支持动态阈值

        Args:
            query: 查询文本
            score_threshold: 可选的相似度阈值

        Returns:
            检索到的文档列表
        """
        try:
            # 使用传入的阈值或默认阈值
            threshold = score_threshold if score_threshold is not None else self.score_threshold

            # 生成查询向量
            query_embedding = await self.embeddings.aembed_query(query)

            # 搜索相似文档
            results = await self.chroma_manager.search_similar(
                collection_name=self.collection_name,
                query_embedding=query_embedding,
                limit=self.top_k,
                score_threshold=threshold
            )

            return results

        except Exception as e:
            logger.error(f"增强文档检索失败: {e}")
            return []


class EnhancedRetrievalChain(RetrievalChain):
    """
    增强的RAG检索链，支持智能查询路由和意图感知处理

    主要功能：
    1. 智能查询意图分析
    2. 基于意图的检索策略选择
    3. 概述查询的摘要优先处理
    4. 意图特定的提示词模板
    5. 结果增强和优化
    """

    def __init__(self, collection_name: str, chroma_persist_directory: str = "./chroma_db",
                 openai_api_key: Optional[str] = None,
                 enable_summary_overview: bool = True, enable_cache: bool = True):
        """
        初始化增强检索链

        Args:
            collection_name: ChromaDB集合名称
            chroma_persist_directory: ChromaDB持久化目录
            openai_api_key: OpenAI API密钥
            enable_summary_overview: 是否启用摘要概述功能
            enable_cache: 是否启用智能缓存
        """
        # 调用父类初始化
        super().__init__(collection_name, chroma_persist_directory, openai_api_key)

        self.enable_summary_overview = enable_summary_overview
        self.enable_cache = enable_cache

        try:
            # 初始化智能组件
            self.intent_analyzer = IntentAnalyzer(llm=self.llm)
            self.strategy_manager = RetrievalStrategyManager()

            # 初始化缓存管理器
            if self.enable_cache:
                self.cache_manager = SmartCacheManager(
                    cache_backend="memory",
                    enable_persistent=False  # 可以根据需要启用
                )
                logger.info("智能缓存已启用")
            else:
                self.cache_manager = None

            # 替换为增强的文档检索器
            self.retriever = EnhancedDocumentRetriever(
                chroma_manager=self.chroma_manager,
                collection_name=collection_name,
                embeddings=self.embeddings,
                top_k=5  # 默认值，会根据策略动态调整
            )

            # 初始化摘要相关组件
            if self.enable_summary_overview:
                self.summary_manager = SummaryManager(self.chroma_manager, self.embeddings)
                self.overview_generator = SummaryBasedOverviewGenerator(
                    self.summary_manager, self.llm
                )
                logger.info("摘要概述功能已启用")
            else:
                self.summary_manager = None
                self.overview_generator = None

            logger.info(f"增强检索链初始化完成 - 集合: '{collection_name}'")

        except Exception as e:
            logger.error(f"增强检索链初始化失败: {e}")
            raise

    async def query(self, question: str, include_sources: bool = True) -> QueryResponse:
        """
        增强的查询处理，支持意图分析和智能路由

        Args:
            question: 用户问题
            include_sources: 是否包含来源引用

        Returns:
            查询响应对象
        """
        try:
            logger.info(f"开始处理增强查询: {question[:100]}...")

            # 1. 检查查询结果缓存
            if self.cache_manager:
                cached_result = self.cache_manager.get_query_result_cache(question, self.collection_name)
                if cached_result:
                    logger.info("查询结果缓存命中，直接返回缓存结果")
                    return QueryResponse(
                        answer=cached_result["answer"],
                        sources=cached_result["sources"],
                        confidence=cached_result["confidence"],
                        query=question
                    )

            # 2. 分析用户意图（检查意图缓存）
            if self.cache_manager:
                cached_intent = self.cache_manager.get_intent_cache(question)
                if cached_intent:
                    intent_info = cached_intent
                    logger.debug("意图分析缓存命中")
                else:
                    intent_info = self.intent_analyzer.analyze_with_confidence(question)
                    # 缓存意图分析结果
                    self.cache_manager.set_intent_cache(question, intent_info)
            else:
                intent_info = self.intent_analyzer.analyze_with_confidence(question)

            intent = intent_info["intent"]
            confidence = intent_info["confidence"]

            logger.info(f"检测到查询意图: {intent.value} (置信度: {confidence}, 方法: {intent_info['analysis_method']})")

            # 2. 处理概述类查询（如果启用了摘要功能）
            if intent == QueryIntent.OVERVIEW and self.enable_summary_overview and self.overview_generator:
                try:
                    overview_response = await self.overview_generator.generate_overview(
                        question, self.collection_name
                    )

                    # 如果摘要概述成功，直接返回
                    if overview_response.summary_count > 0:
                        logger.info(f"使用摘要生成概述 - 摘要数量: {overview_response.summary_count}")
                        return QueryResponse(
                            answer=overview_response.answer,
                            sources=overview_response.sources,
                            confidence=overview_response.confidence,
                            query=question
                        )
                    else:
                        logger.info("摘要概述生成失败，回退到常规检索")
                except Exception as e:
                    logger.warning(f"摘要概述生成失败，回退到常规检索: {e}")

            # 3. 使用意图特定的检索策略
            config = self.strategy_manager.get_config(intent)

            # 更新检索器参数
            self.retriever.top_k = config.top_k

            logger.debug(f"使用检索策略 - top_k: {config.top_k}, threshold: {config.score_threshold}")

            # 4. 执行文档检索
            relevant_docs = await self.retriever.retrieve_documents(
                question, score_threshold=config.score_threshold
            )

            # 5. 如果是概述查询且检索结果不足，尝试扩展检索
            if intent == QueryIntent.OVERVIEW and len(relevant_docs) < 10:
                logger.info("概述查询结果不足，尝试扩展检索...")
                expanded_docs = await self._expand_overview_retrieval(question)
                if len(expanded_docs) > len(relevant_docs):
                    relevant_docs = expanded_docs
                    logger.info(f"扩展检索完成，文档数量: {len(relevant_docs)}")

            if not relevant_docs:
                return self._generate_no_results_response(question, intent)

            # 6. 应用检索增强策略
            if config.enable_mmr:
                relevant_docs = RetrievalEnhancer.apply_mmr_filter(
                    relevant_docs, config.mmr_diversity_threshold
                )
                logger.debug(f"MMR过滤后文档数量: {len(relevant_docs)}")

            if config.prefer_structured:
                relevant_docs = RetrievalEnhancer.prioritize_structured_content(relevant_docs)
                logger.debug("已优先排序结构化内容")

            if config.context_expansion:
                relevant_docs = RetrievalEnhancer.enhance_with_context(relevant_docs)

            # 7. 根据意图选择提示词模板
            prompt_template = get_prompt_by_intent(intent)

            # 8. 格式化上下文（根据意图优化）
            context = self._format_context_by_intent(relevant_docs, intent)

            # 9. 生成回答
            chain = prompt_template | self.llm | StrOutputParser()
            answer = await chain.ainvoke({
                "context": context,
                "question": question
            })

            # 10. 计算置信度
            confidence_score = self._calculate_confidence(relevant_docs, intent, intent_info["confidence_score"])

            # 11. 格式化来源信息
            sources = self._format_sources_by_intent(relevant_docs, intent, include_sources)
            if sources and include_sources:
                answer += format_sources(sources)

            logger.info(f"增强查询处理完成 - 意图: {intent.value}, 文档数: {len(relevant_docs)}, 置信度: {confidence_score:.3f}")

            # 创建查询响应
            query_response = QueryResponse(
                answer=answer,
                sources=sources,
                confidence=confidence_score,
                query=question
            )

            # 12. 缓存查询结果
            if self.cache_manager:
                result_to_cache = {
                    "answer": answer,
                    "sources": sources,
                    "confidence": confidence_score,
                    "query": question
                }
                self.cache_manager.set_query_result_cache(
                    question, self.collection_name, result_to_cache, intent.value
                )
                logger.debug("查询结果已缓存")

            return query_response

        except Exception as e:
            logger.error(f"增强查询处理失败: {e}")
            return self._generate_error_response(str(e), question)

    async def _expand_overview_retrieval(self, question: str) -> list[dict[str, Any]]:
        """
        针对概述查询的扩展检索策略

        Args:
            question: 查询问题

        Returns:
            扩展后的文档列表
        """
        try:
            # 使用更宽松的检索条件
            expanded_docs = await self.retriever.retrieve_documents(
                question, score_threshold=0.1
            )

            if not expanded_docs:
                return []

            # 按section分组，确保各部分都有覆盖
            section_groups = {}
            for doc in expanded_docs:
                section = doc.get('metadata', {}).get('section_title', 'unknown')
                if section not in section_groups:
                    section_groups[section] = []
                section_groups[section].append(doc)

            # 从每个section选择最相关的文档
            balanced_docs = []
            for section_docs in section_groups.values():
                # 按score排序，选择前2个
                sorted_docs = sorted(section_docs, key=lambda x: x.get('score', 0), reverse=True)
                balanced_docs.extend(sorted_docs[:2])

            # 总数限制在20个以内
            return balanced_docs[:20]

        except Exception as e:
            logger.error(f"概述查询扩展检索失败: {e}")
            return []

    def _format_context_by_intent(self, documents: list[dict[str, Any]], intent: QueryIntent) -> str:
        """
        根据意图格式化上下文

        Args:
            documents: 文档列表
            intent: 查询意图

        Returns:
            格式化的上下文文本
        """
        if not documents:
            return "未找到相关文档。"

        if intent == QueryIntent.OVERVIEW:
            return self._format_overview_context(documents)
        elif intent == QueryIntent.HOW_TO:
            return self._format_procedural_context(documents)
        else:
            return self._format_context(documents)  # 使用父类方法

    def _format_overview_context(self, documents: list[dict[str, Any]]) -> str:
        """
        格式化概述上下文，按主题分组

        Args:
            documents: 文档列表

        Returns:
            格式化的概述上下文
        """
        sections = {}
        ungrouped = []

        for doc in documents:
            section_title = doc.get('metadata', {}).get('section_title')
            if section_title:
                if section_title not in sections:
                    sections[section_title] = []
                sections[section_title].append(doc)
            else:
                ungrouped.append(doc)

        context_parts = []

        # 按section组织内容
        for section_title, docs in sections.items():
            context_parts.append(f"## {section_title}")
            for i, doc in enumerate(docs):
                source = doc.get('source', 'Unknown')
                content = doc.get('content', '')
                score = doc.get('score', 0)
                context_parts.append(f"[片段 {len(context_parts)}] 来源: {source} (相关度: {score:.3f})\n{content}")

        # 添加未分组内容
        if ungrouped:
            context_parts.append("## 其他相关内容")
            for doc in ungrouped:
                source = doc.get('source', 'Unknown')
                content = doc.get('content', '')
                score = doc.get('score', 0)
                context_parts.append(f"[片段 {len(context_parts)}] 来源: {source} (相关度: {score:.3f})\n{content}")

        return "\n\n".join(context_parts)

    def _format_procedural_context(self, documents: list[dict[str, Any]]) -> str:
        """
        格式化操作指南上下文，优先显示步骤性内容

        Args:
            documents: 文档列表

        Returns:
            格式化的步骤上下文
        """
        procedural_docs = []
        regular_docs = []

        for doc in documents:
            metadata = doc.get('metadata', {})
            content = doc.get('content', '').lower()

            # 检测步骤性内容
            is_procedural = (
                metadata.get('is_procedural', False) or
                any(indicator in content for indicator in ['步骤', '第一步', '第二步', 'step 1', 'step 2', '首先', '然后', '最后'])
            )

            if is_procedural:
                procedural_docs.append(doc)
            else:
                regular_docs.append(doc)

        context_parts = []

        # 优先显示步骤性内容
        if procedural_docs:
            context_parts.append("## 操作步骤相关内容")
            for i, doc in enumerate(procedural_docs):
                source = doc.get('source', 'Unknown')
                content = doc.get('content', '')
                score = doc.get('score', 0)
                step_indicators = []

                # 提取步骤指示器
                for indicator in ['第一步', '第二步', '第三步', 'step 1', 'step 2', '首先', '然后', '最后']:
                    if indicator in content.lower():
                        step_indicators.append(indicator)

                step_info = f" (包含步骤: {', '.join(step_indicators)})" if step_indicators else ""
                context_parts.append(f"[步骤文档 {i+1}] 来源: {source} (相关度: {score:.3f}){step_info}\n{content}")

        # 添加其他相关内容
        if regular_docs:
            context_parts.append("## 其他相关信息")
            for i, doc in enumerate(regular_docs):
                source = doc.get('source', 'Unknown')
                content = doc.get('content', '')
                score = doc.get('score', 0)
                context_parts.append(f"[参考文档 {i+1}] 来源: {source} (相关度: {score:.3f})\n{content}")

        return "\n\n".join(context_parts)

    def _calculate_confidence(self, documents: list[dict[str, Any]], intent: QueryIntent, intent_confidence: float) -> float:
        """
        根据意图和检索结果计算置信度

        Args:
            documents: 检索到的文档
            intent: 查询意图
            intent_confidence: 意图识别置信度

        Returns:
            综合置信度分数
        """
        if not documents:
            return 0.0

        # 基础置信度：基于文档相关性分数
        avg_score = sum(doc.get('score', 0) for doc in documents) / len(documents)
        base_confidence = min(avg_score * 2, 0.9)

        # 根据意图调整置信度计算
        if intent == QueryIntent.OVERVIEW:
            # 概述类查询：文档数量多样性也影响置信度
            diversity_bonus = min(len(documents) / 15, 0.2)
            final_confidence = min(base_confidence + diversity_bonus, 0.95)
        elif intent == QueryIntent.HOW_TO:
            # 操作指南：步骤完整性影响置信度
            procedural_count = sum(1 for doc in documents
                                 if any(keyword in doc.get('content', '').lower()
                                       for keyword in ['步骤', 'step', '首先', '然后', '最后']))
            procedural_bonus = min(procedural_count / 3, 0.15)
            final_confidence = min(base_confidence + procedural_bonus, 0.95)
        else:
            final_confidence = min(base_confidence, 0.9)

        # 考虑意图识别的置信度
        intent_weight = {"high": 1.0, "medium": 0.9, "low": 0.8}.get(intent_confidence, 0.8)
        final_confidence *= intent_weight

        return final_confidence

    def _format_sources_by_intent(self, documents: list[dict[str, Any]], intent: QueryIntent, include_sources: bool) -> list[dict[str, Any]]:
        """
        根据意图格式化来源信息

        Args:
            documents: 文档列表
            intent: 查询意图
            include_sources: 是否包含来源

        Returns:
            格式化的来源信息列表
        """
        if not include_sources or not documents:
            return []

        sources = []
        for i, doc in enumerate(documents, 1):
            source_info = {
                "id": f"doc_{i}",
                "source": doc.get('source', 'Unknown'),
                "content_preview": doc.get('content', '')[:200] + "..." if len(doc.get('content', '')) > 200 else doc.get('content', ''),
                "score": doc.get('score', 0),
                "start_index": doc.get('start_index', 0),
                "intent": intent.value
            }

            # 为不同意图添加特定信息
            if intent == QueryIntent.HOW_TO:
                # 标记是否包含步骤信息
                content = doc.get('content', '').lower()
                source_info["has_steps"] = any(keyword in content for keyword in ['步骤', 'step', '首先', '然后', '最后'])

            sources.append(source_info)

        return sources

    def _generate_no_results_response(self, question: str, intent: QueryIntent) -> QueryResponse:
        """
        生成无结果响应

        Args:
            question: 用户问题
            intent: 查询意图

        Returns:
            无结果响应
        """
        intent_messages = {
            QueryIntent.OVERVIEW: "抱歉，我没有找到能够提供全面概述的相关文档。建议您检查文档是否已正确处理，或尝试使用更具体的关键词。",
            QueryIntent.HOW_TO: "抱歉，我没有找到相关的操作指南或步骤说明。建议您确认文档中是否包含相关的操作步骤，或尝试用不同的方式描述您的需求。",
            QueryIntent.COMPARISON: "抱歉，我没有找到可以进行比较分析的相关信息。建议您确认文档中是否包含您想比较的对象或概念。",
            QueryIntent.FACTUAL: "抱歉，我在提供的文档中没有找到与您的问题相关的信息。请确认您的问题是否在文档范围内，或者尝试用不同的方式提问。"
        }

        message = intent_messages.get(intent, intent_messages[QueryIntent.FACTUAL])

        return QueryResponse(
            answer=message,
            sources=[],
            confidence=0.0,
            query=question
        )

    def _generate_error_response(self, error_message: str, question: str) -> QueryResponse:
        """
        生成错误响应

        Args:
            error_message: 错误消息
            question: 用户问题

        Returns:
            错误响应
        """
        return QueryResponse(
            answer=f"抱歉，处理您的问题时出现错误：{error_message}。请稍后重试。",
            sources=[],
            confidence=0.0,
            query=question
        )

    async def get_intent_analysis(self, question: str) -> dict[str, Any]:
        """
        获取查询的意图分析结果（用于调试和分析）

        Args:
            question: 查询问题

        Returns:
            意图分析结果
        """
        return self.intent_analyzer.analyze_with_confidence(question)

    def get_cache_stats(self) -> Optional[dict[str, Any]]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息或None（如果缓存未启用）
        """
        if self.cache_manager:
            return self.cache_manager.get_cache_stats()
        return None

    def clear_cache(self, cache_type: Optional[str] = None) -> int:
        """
        清理缓存

        Args:
            cache_type: 要清理的缓存类型，None表示清理全部

        Returns:
            清理的项目数量
        """
        if self.cache_manager:
            return self.cache_manager.clear_cache(cache_type)
        return 0


# 便捷函数
def create_enhanced_retrieval_chain(collection_name: str,
                                   config=None,
                                   openai_api_key: Optional[str] = None,
                                   enable_summary_overview: bool = True,
                                   enable_cache: bool = True) -> EnhancedRetrievalChain:
    """创建增强检索链实例"""
    if config:
        return EnhancedRetrievalChain(
            collection_name=collection_name,
            chroma_persist_directory=config.chroma_persist_directory,
            openai_api_key=openai_api_key or config.openai_api_key,
            enable_summary_overview=enable_summary_overview,
            enable_cache=enable_cache
        )
    else:
        return EnhancedRetrievalChain(
            collection_name=collection_name,
            chroma_persist_directory="./chroma_db",
            openai_api_key=openai_api_key,
            enable_summary_overview=enable_summary_overview,
            enable_cache=enable_cache
        )
