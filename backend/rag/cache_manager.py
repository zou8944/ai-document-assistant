"""
智能缓存管理器
提供多层缓存机制，优化RAG系统的响应速度和成本效益
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SmartCacheManager:
    """
    智能缓存管理器

    功能特点：
    1. 多层缓存架构：查询结果缓存、意图分类缓存、集合概述缓存
    2. 智能相似查询匹配
    3. 可配置的过期策略
    4. 内存缓存和可选的持久化存储
    """

    def __init__(self,
                 cache_backend: str = "memory",
                 cache_dir: str = "./cache",
                 enable_persistent: bool = False):
        """
        初始化缓存管理器

        Args:
            cache_backend: 缓存后端类型 ("memory" 或 "file")
            cache_dir: 文件缓存目录（仅在启用持久化时使用）
            enable_persistent: 是否启用持久化存储
        """
        self.cache_backend = cache_backend
        self.cache_dir = Path(cache_dir)
        self.enable_persistent = enable_persistent

        # 内存缓存
        self.memory_cache: dict[str, dict[str, Any]] = {}

        # 缓存配置
        self.cache_ttl = {
            "collection_summary": 7 * 24 * 3600,    # 7天 - 集合概述缓存
            "query_result": 1 * 24 * 3600,          # 1天 - 查询结果缓存
            "intent_classification": 3 * 24 * 3600,  # 3天 - 意图分类缓存
            "document_summary": 30 * 24 * 3600      # 30天 - 文档摘要缓存
        }

        # 相似查询匹配配置
        self.similarity_threshold = 0.85  # Jaccard相似度阈值
        self.max_cache_size = 1000        # 最大缓存项数

        # 初始化持久化存储
        if self.enable_persistent:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._load_persistent_cache()

        logger.info(f"缓存管理器初始化完成 - 后端: {cache_backend}, 持久化: {enable_persistent}")

    def generate_query_cache_key(self, query: str, collection_name: str, intent: Optional[str] = None) -> str:
        """
        生成查询缓存键

        Args:
            query: 查询文本
            collection_name: 集合名称
            intent: 可选的查询意图

        Returns:
            标准化的缓存键
        """
        # 标准化查询（去除标点、统一大小写、去重复空格）
        normalized_query = re.sub(r'[^\w\s]', '', query.lower().strip())
        normalized_query = re.sub(r'\s+', ' ', normalized_query)

        # 生成hash
        content = f"{collection_name}:{normalized_query}:{intent or 'any'}"
        query_hash = hashlib.md5(content.encode()).hexdigest()[:16]

        return f"query:{collection_name}:{query_hash}"

    def generate_intent_cache_key(self, query: str) -> str:
        """
        生成意图分类缓存键

        Args:
            query: 查询文本

        Returns:
            意图缓存键
        """
        normalized_query = re.sub(r'[^\w\s]', '', query.lower().strip())
        normalized_query = re.sub(r'\s+', ' ', normalized_query)
        query_hash = hashlib.md5(normalized_query.encode()).hexdigest()[:16]

        return f"intent:{query_hash}"

    def _is_cache_valid(self, cache_item: dict[str, Any], cache_type: str) -> bool:
        """
        检查缓存项是否有效

        Args:
            cache_item: 缓存项
            cache_type: 缓存类型

        Returns:
            是否有效
        """
        if not cache_item or "timestamp" not in cache_item:
            return False

        ttl = self.cache_ttl.get(cache_type, 3600)  # 默认1小时
        expires_at = cache_item["timestamp"] + ttl

        return time.time() < expires_at

    def set_query_result_cache(self,
                              query: str,
                              collection_name: str,
                              result: dict[str, Any],
                              intent: Optional[str] = None) -> None:
        """
        设置查询结果缓存

        Args:
            query: 查询文本
            collection_name: 集合名称
            result: 查询结果
            intent: 查询意图
        """
        cache_key = self.generate_query_cache_key(query, collection_name, intent)

        cache_item = {
            "result": result,
            "original_query": query,
            "collection_name": collection_name,
            "intent": intent,
            "timestamp": time.time(),
            "access_count": 1
        }

        self._set_cache_item(cache_key, cache_item, "query_result")
        logger.debug(f"查询结果已缓存 - key: {cache_key[:20]}...")

    def get_query_result_cache(self,
                             query: str,
                             collection_name: str,
                             intent: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        获取查询结果缓存

        Args:
            query: 查询文本
            collection_name: 集合名称
            intent: 查询意图

        Returns:
            缓存的查询结果或None
        """
        # 首先尝试精确匹配
        cache_key = self.generate_query_cache_key(query, collection_name, intent)
        cache_item = self._get_cache_item(cache_key, "query_result")

        if cache_item:
            # 更新访问统计
            cache_item["access_count"] = cache_item.get("access_count", 0) + 1
            logger.info(f"查询缓存命中（精确匹配）- 访问次数: {cache_item['access_count']}")
            return cache_item["result"]

        # 如果精确匹配失败，尝试相似查询匹配
        similar_result = self.get_similar_query_result(query, collection_name)
        if similar_result:
            logger.info("查询缓存命中（相似匹配）")
            return similar_result

        return None

    def get_similar_query_result(self,
                               query: str,
                               collection_name: str,
                               similarity_threshold: Optional[float] = None) -> Optional[dict[str, Any]]:
        """
        获取相似查询的缓存结果

        Args:
            query: 查询文本
            collection_name: 集合名称
            similarity_threshold: 相似度阈值

        Returns:
            相似查询的结果或None
        """
        threshold = similarity_threshold or self.similarity_threshold
        query_words = set(query.lower().split())

        if len(query_words) == 0:
            return None

        best_match = None
        best_similarity = 0.0

        # 在内存缓存中搜索
        for cache_key, cache_item in self.memory_cache.items():
            if not cache_key.startswith(f"query:{collection_name}:"):
                continue

            if not self._is_cache_valid(cache_item, "query_result"):
                continue

            cached_query = cache_item.get("original_query", "")
            cached_words = set(cached_query.lower().split())

            if len(cached_words) == 0:
                continue

            # 计算Jaccard相似度
            intersection = query_words.intersection(cached_words)
            union = query_words.union(cached_words)
            similarity = len(intersection) / len(union)

            if similarity >= threshold and similarity > best_similarity:
                best_similarity = similarity
                best_match = cache_item

        if best_match:
            logger.info(f"找到相似查询缓存，相似度: {best_similarity:.3f}")
            # 更新访问统计
            best_match["access_count"] = best_match.get("access_count", 0) + 1
            return best_match["result"]

        return None

    def set_intent_cache(self, query: str, intent_info: dict[str, Any]) -> None:
        """
        设置意图分类缓存

        Args:
            query: 查询文本
            intent_info: 意图分析信息
        """
        cache_key = self.generate_intent_cache_key(query)

        cache_item = {
            "intent_info": intent_info,
            "original_query": query,
            "timestamp": time.time(),
            "access_count": 1
        }

        self._set_cache_item(cache_key, cache_item, "intent_classification")
        logger.debug(f"意图分类已缓存 - intent: {intent_info.get('intent', {}).get('value', 'unknown')}")

    def get_intent_cache(self, query: str) -> Optional[dict[str, Any]]:
        """
        获取意图分类缓存

        Args:
            query: 查询文本

        Returs:
            缓存的意图信息或None
        """
        cache_key = self.generate_intent_cache_key(query)
        cache_item = self._get_cache_item(cache_key, "intent_classification")

        if cache_item:
            cache_item["access_count"] = cache_item.get("access_count", 0) + 1
            logger.debug("意图分类缓存命中")
            return cache_item["intent_info"]

        return None

    def set_collection_overview_cache(self,
                                    collection_name: str,
                                    doc_count: int,
                                    overview: str) -> None:
        """
        设置集合概述缓存

        Args:
            collection_name: 集合名称
            doc_count: 文档数量（用于缓存失效判断）
            overview: 概述内容
        """
        cache_key = f"overview:{collection_name}:{doc_count}"

        cache_item = {
            "overview": overview,
            "collection_name": collection_name,
            "doc_count": doc_count,
            "timestamp": time.time(),
            "access_count": 1
        }

        self._set_cache_item(cache_key, cache_item, "collection_summary")
        logger.info(f"集合概述已缓存 - collection: {collection_name}")

    def get_collection_overview_cache(self,
                                    collection_name: str,
                                    doc_count: int) -> Optional[str]:
        """
        获取集合概述缓存

        Args:
            collection_name: 集合名称
            doc_count: 当前文档数量

        Returns:
            缓存的概述或None
        """
        cache_key = f"overview:{collection_name}:{doc_count}"
        cache_item = self._get_cache_item(cache_key, "collection_summary")

        if cache_item:
            cache_item["access_count"] = cache_item.get("access_count", 0) + 1
            logger.info("集合概述缓存命中")
            return cache_item["overview"]

        return None

    def _set_cache_item(self, cache_key: str, cache_item: dict[str, Any], cache_type: str) -> None:
        """
        设置缓存项（内部方法）

        Args:
            cache_key: 缓存键
            cache_item: 缓存项
            cache_type: 缓存类型
        """
        # 检查缓存大小限制
        if len(self.memory_cache) >= self.max_cache_size:
            self._evict_old_cache_items()

        # 设置内存缓存
        self.memory_cache[cache_key] = cache_item

        # 设置持久化缓存（如果启用）
        if self.enable_persistent:
            self._save_to_persistent_cache(cache_key, cache_item)

    def _get_cache_item(self, cache_key: str, cache_type: str) -> Optional[dict[str, Any]]:
        """
        获取缓存项（内部方法）

        Args:
            cache_key: 缓存键
            cache_type: 缓存类型

        Returns:
            缓存项或None
        """
        # 首先检查内存缓存
        cache_item = self.memory_cache.get(cache_key)

        if cache_item and self._is_cache_valid(cache_item, cache_type):
            return cache_item

        # 如果内存中没有或已过期，检查持久化缓存
        if self.enable_persistent:
            persistent_item = self._load_from_persistent_cache(cache_key)
            if persistent_item and self._is_cache_valid(persistent_item, cache_type):
                # 重新加载到内存缓存
                self.memory_cache[cache_key] = persistent_item
                return persistent_item

        # 清理无效缓存
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]

        return None

    def _evict_old_cache_items(self, evict_count: int = 100) -> None:
        """
        清理旧的缓存项

        Args:
            evict_count: 要清理的项数
        """
        if len(self.memory_cache) <= evict_count:
            return

        # 按时间戳排序，清理最旧的项目
        items_by_time = sorted(
            self.memory_cache.items(),
            key=lambda x: x[1].get("timestamp", 0)
        )

        for i in range(min(evict_count, len(items_by_time))):
            cache_key = items_by_time[i][0]
            del self.memory_cache[cache_key]

        logger.info(f"清理了 {evict_count} 个旧缓存项")

    def _save_to_persistent_cache(self, cache_key: str, cache_item: dict[str, Any]) -> None:
        """
        保存到持久化缓存

        Args:
            cache_key: 缓存键
            cache_item: 缓存项
        """
        try:
            cache_file = self.cache_dir / f"{cache_key.replace(':', '_')}.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_item, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"持久化缓存保存失败: {e}")

    def _load_from_persistent_cache(self, cache_key: str) -> Optional[dict[str, Any]]:
        """
        从持久化缓存加载

        Args:
            cache_key: 缓存键

        Returns:
            缓存项或None
        """
        try:
            cache_file = self.cache_dir / f"{cache_key.replace(':', '_')}.json"
            if cache_file.exists():
                with open(cache_file, encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"持久化缓存加载失败: {e}")

        return None

    def _load_persistent_cache(self) -> None:
        """加载所有持久化缓存到内存"""
        if not self.cache_dir.exists():
            return

        loaded_count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, encoding='utf-8') as f:
                    cache_item = json.load(f)

                # 重建缓存键
                cache_key = cache_file.stem.replace('_', ':')

                # 检查是否仍然有效
                if self._is_cache_valid(cache_item, "query_result"):  # 使用默认类型检查
                    self.memory_cache[cache_key] = cache_item
                    loaded_count += 1
                else:
                    # 删除过期的文件
                    cache_file.unlink()

            except Exception as e:
                logger.warning(f"加载缓存文件失败 {cache_file}: {e}")

        if loaded_count > 0:
            logger.info(f"从持久化存储加载了 {loaded_count} 个缓存项")

    def clear_cache(self, cache_type: Optional[str] = None) -> int:
        """
        清理缓存

        Args:
            cache_type: 要清理的缓存类型，None表示清理全部

        Returns:
            清理的项目数量
        """
        if cache_type is None:
            # 清理全部缓存
            cleared_count = len(self.memory_cache)
            self.memory_cache.clear()

            if self.enable_persistent and self.cache_dir.exists():
                for cache_file in self.cache_dir.glob("*.json"):
                    cache_file.unlink()

            logger.info(f"清理了全部缓存，共 {cleared_count} 项")
            return cleared_count

        # 清理特定类型的缓存
        keys_to_remove = []
        for cache_key in self.memory_cache:
            if cache_key.startswith(cache_type + ":"):
                keys_to_remove.append(cache_key)

        for key in keys_to_remove:
            del self.memory_cache[key]

            # 删除持久化文件
            if self.enable_persistent:
                cache_file = self.cache_dir / f"{key.replace(':', '_')}.json"
                if cache_file.exists():
                    cache_file.unlink()

        logger.info(f"清理了 {cache_type} 类型缓存，共 {len(keys_to_remove)} 项")
        return len(keys_to_remove)

    def get_cache_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            缓存统计信息
        """
        stats = {
            "total_items": len(self.memory_cache),
            "cache_types": {},
            "memory_usage_mb": 0,  # 简化计算
            "hit_rate": 0,  # 需要在实际使用中统计
            "oldest_item": None,
            "newest_item": None
        }

        # 按类型统计
        for cache_key in self.memory_cache:
            cache_type = cache_key.split(':')[0]
            stats["cache_types"][cache_type] = stats["cache_types"].get(cache_type, 0) + 1

        # 时间统计
        timestamps = [item.get("timestamp", 0) for item in self.memory_cache.values()]
        if timestamps:
            stats["oldest_item"] = datetime.fromtimestamp(min(timestamps)).isoformat()
            stats["newest_item"] = datetime.fromtimestamp(max(timestamps)).isoformat()

        return stats


# 便捷函数
def create_smart_cache_manager(cache_backend: str = "memory",
                             cache_dir: str = "./cache",
                             enable_persistent: bool = False) -> SmartCacheManager:
    """创建智能缓存管理器实例"""
    return SmartCacheManager(cache_backend, cache_dir, enable_persistent)
