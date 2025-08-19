"""
摘要存储和检索管理器
管理文档摘要的向量化存储和智能检索
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel

from rag.document_summarizer import DocumentSummary
from vector_store.chroma_client import ChromaManager

logger = logging.getLogger(__name__)


class SummaryPoint(BaseModel):
    """摘要向量点数据模型"""
    id: str
    summary: str
    source: str
    doc_type: str
    original_length: int
    generated_at: str
    score: Optional[float] = None  # 检索时的相似度分数


class SummaryManager:
    """摘要存储和检索管理器"""

    def __init__(self, chroma_manager: ChromaManager, embeddings):
        """
        初始化摘要管理器

        Args:
            chroma_manager: ChromaDB数据库管理器实例
            embeddings: 嵌入模型实例（用于向量化）
        """
        self.chroma_manager = chroma_manager
        self.embeddings = embeddings

    def _get_summary_collection_name(self, base_collection: str) -> str:
        """获取摘要集合名称"""
        return f"{base_collection}_summaries"

    async def store_document_summaries(self,
                                     collection_name: str,
                                     summaries: list[DocumentSummary]) -> dict[str, Any]:
        """
        存储文档摘要到专门的摘要集合

        Args:
            collection_name: 基础集合名称
            summaries: 文档摘要列表

        Returns:
            存储结果字典
        """
        summary_collection = self._get_summary_collection_name(collection_name)

        try:
            # 过滤出有效的摘要
            valid_summaries = [s for s in summaries if not s.error and s.summary.strip()]
            if not valid_summaries:
                return {
                    "status": "error",
                    "message": "没有有效的摘要可存储",
                    "stored_count": 0
                }

            logger.info(f"准备存储 {len(valid_summaries)} 个有效摘要到 {summary_collection}")

            # 确保摘要集合存在（获取embedding维度）
            embedding_dim = getattr(self.embeddings, 'dimension', 1536)  # 默认OpenAI维度
            await self.chroma_manager.ensure_collection(summary_collection, embedding_dim)

            # 批量生成摘要的向量表示
            summary_texts = [s.summary for s in valid_summaries]
            try:
                # 检查是否是异步embedding模型
                if hasattr(self.embeddings, 'aembed_documents'):
                    summary_embeddings = await self.embeddings.aembed_documents(summary_texts)
                else:
                    summary_embeddings = self.embeddings.embed_documents(summary_texts)

                logger.info(f"成功生成 {len(summary_embeddings)} 个摘要向量")

            except Exception as e:
                logger.error(f"摘要向量化失败: {e}")
                return {
                    "status": "error",
                    "message": f"向量化失败: {e}",
                    "stored_count": 0
                }

            # 准备摘要数据
            ids = []
            documents = []
            metadatas = []
            embeddings_list = []

            for summary_data, embedding in zip(valid_summaries, summary_embeddings):
                ids.append(summary_data.id)
                documents.append(summary_data.summary)
                metadatas.append({
                    "source": summary_data.source,
                    "doc_type": summary_data.doc_type,
                    "original_length": summary_data.original_length,
                    "generated_at": summary_data.generated_at,
                    "summary_type": "document",  # 标识这是文档级摘要
                    "has_error": summary_data.error,
                    "error_message": summary_data.error_message
                })
                embeddings_list.append(embedding)

            # 批量插入摘要
            result = await self.index_documents(summary_collection, ids, documents, metadatas, embeddings_list)

            if result["status"] == "success":
                logger.info(f"成功存储 {result['indexed_count']} 个文档摘要到 {summary_collection}")
                return {
                    "status": "success",
                    "stored_count": result["indexed_count"],
                    "collection_name": summary_collection
                }
            else:
                return result

        except Exception as e:
            logger.error(f"存储文档摘要失败: {e}")
            return {
                "status": "error",
                "message": f"存储失败: {e}",
                "stored_count": 0
            }

    async def index_documents(self, collection_name: str, ids: list[str],
                             documents: list[str], metadatas: list[dict],
                             embeddings_list: list[list[float]]) -> dict[str, Any]:
        """
        索引文档到集合

        Args:
            collection_name: 集合名称  
            ids: 文档ID列表
            documents: 文档内容列表
            metadatas: 元数据列表
            embeddings_list: 向量列表

        Returns:
            索引结果字典
        """
        try:
            collection = self.chroma_manager.client.get_collection(name=collection_name)

            # 使用ChromaDB的upsert操作
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings_list
            )

            logger.info(f"成功索引 {len(ids)} 个文档到集合 '{collection_name}'")

            return {
                "status": "success",
                "indexed_count": len(ids),
                "collection_name": collection_name
            }

        except Exception as e:
            logger.error(f"索引文档失败: {e}")
            return {
                "status": "error",
                "message": str(e),
                "indexed_count": 0
            }

    async def retrieve_relevant_summaries(self,
                                        collection_name: str,
                                        query: str,
                                        limit: int = 15,
                                        score_threshold: float = 0.1) -> list[SummaryPoint]:
        """
        检索与查询相关的文档摘要

        Args:
            collection_name: 基础集合名称
            query: 查询文本
            limit: 返回结果数量限制
            score_threshold: 相似度阈值

        Returns:
            相关摘要列表
        """
        summary_collection = self._get_summary_collection_name(collection_name)

        try:
            # 生成查询向量
            if hasattr(self.embeddings, 'aembed_query'):
                query_embedding = await self.embeddings.aembed_query(query)
            else:
                query_embedding = self.embeddings.embed_query(query)

            # 检索相似摘要
            results = await self.chroma_manager.search_similar(
                collection_name=summary_collection,
                query_embedding=query_embedding,
                limit=limit,
                score_threshold=score_threshold
            )

            # 转换为SummaryPoint对象
            summary_points = []
            for result in results:
                try:
                    point = SummaryPoint(
                        id=result["id"],
                        summary=result.get("content", result.get("summary", "")),  # 兼容字段名差异
                        source=result.get("source", "unknown"),
                        doc_type=result.get("metadata", {}).get("doc_type", "document"),
                        original_length=result.get("metadata", {}).get("original_length", 0),
                        generated_at=result.get("metadata", {}).get("generated_at", ""),
                        score=result["score"]
                    )
                    summary_points.append(point)
                except Exception as e:
                    logger.warning(f"解析摘要点失败 {result.get('id', 'unknown')}: {e}")
                    continue

            logger.info(f"检索到 {len(summary_points)} 个相关摘要，查询: {query[:50]}...")
            return summary_points

        except Exception as e:
            logger.error(f"检索相关摘要失败: {e}")
            return []

    async def get_collection_summary_stats(self, collection_name: str) -> Optional[dict[str, Any]]:
        """
        获取摘要集合的统计信息

        Args:
            collection_name: 基础集合名称

        Returns:
            统计信息字典
        """
        summary_collection = self._get_summary_collection_name(collection_name)

        try:
            info = await self.chroma_manager.get_collection_info(summary_collection)
            if info:
                return {
                    "collection_name": summary_collection,
                    "summary_count": info["vectors_count"],
                    "status": info["status"],
                    "config": info["config"]
                }
            return None

        except Exception as e:
            logger.error(f"获取摘要集合统计失败: {e}")
            return None

    async def delete_summary_collection(self, collection_name: str) -> bool:
        """
        删除摘要集合

        Args:
            collection_name: 基础集合名称

        Returns:
            删除是否成功
        """
        summary_collection = self._get_summary_collection_name(collection_name)

        try:
            success = await self.chroma_manager.delete_collection(summary_collection)
            if success:
                logger.info(f"成功删除摘要集合: {summary_collection}")
            return success

        except Exception as e:
            logger.error(f"删除摘要集合失败: {e}")
            return False

    def format_summaries_context(self, summaries: list[SummaryPoint], max_length: int = 8000) -> str:
        """
        格式化摘要为上下文文本

        Args:
            summaries: 摘要列表
            max_length: 最大上下文长度

        Returns:
            格式化的上下文文本
        """
        if not summaries:
            return "未找到相关文档摘要。"

        context_parts = []
        current_length = 0

        for i, summary in enumerate(summaries, 1):
            # 格式化单个摘要
            formatted_summary = f"""【文档摘要 {i}】
来源: {summary.source}
类型: {summary.doc_type}
相似度: {summary.score:.3f}

{summary.summary}
"""

            # 检查长度限制
            if current_length + len(formatted_summary) > max_length:
                context_parts.append(f"\n[... 因长度限制，省略其余 {len(summaries) - i + 1} 个摘要 ...]")
                break

            context_parts.append(formatted_summary)
            current_length += len(formatted_summary)

        return "\n" + "="*50 + "\n".join(context_parts) + "\n" + "="*50

    async def update_document_summary(self,
                                    collection_name: str,
                                    summary_id: str,
                                    new_summary: DocumentSummary) -> bool:
        """
        更新单个文档摘要

        Args:
            collection_name: 基础集合名称
            summary_id: 摘要ID
            new_summary: 新的摘要数据

        Returns:
            更新是否成功
        """
        summary_collection = self._get_summary_collection_name(collection_name)

        try:
            # 生成新摘要的向量
            if hasattr(self.embeddings, 'aembed_documents'):
                embedding = (await self.embeddings.aembed_documents([new_summary.summary]))[0]
            else:
                embedding = self.embeddings.embed_documents([new_summary.summary])[0]

            # 准备更新数据
            metadata = {
                "source": new_summary.source,
                "doc_type": new_summary.doc_type,
                "original_length": new_summary.original_length,
                "generated_at": new_summary.generated_at,
                "summary_type": "document",
                "has_error": new_summary.error,
                "error_message": new_summary.error_message
            }

            # 执行更新
            result = await self.index_documents(summary_collection, [summary_id], [new_summary.summary], [metadata], [embedding])
            return result["status"] == "success"

        except Exception as e:
            logger.error(f"更新文档摘要失败: {e}")
            return False
