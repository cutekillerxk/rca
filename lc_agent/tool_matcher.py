#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工具嵌入向量匹配实现
从DB-GPT迁移，用于智能选择最相关的工具
"""

import os
import json
import numpy as np
from typing import List, Dict, Callable, Optional, Tuple
import logging

# 设置sentence-transformers模型缓存目录为D:\models
# Windows路径处理：使用 os.path.join("D:\\", "models") 或直接使用 "D:\\models"
MODEL_CACHE_DIR = os.path.join("D:\\", "models")  # Windows正确格式
os.makedirs(MODEL_CACHE_DIR, exist_ok=True)
# 设置环境变量（sentence-transformers会使用这个目录）
os.environ['TRANSFORMERS_CACHE'] = MODEL_CACHE_DIR
os.environ['HF_HOME'] = MODEL_CACHE_DIR

# 如果使用sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMER_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMER_AVAILABLE = False
    logging.warning("sentence-transformers未安装，将使用简化版嵌入模型")


def sentence_embedding(sentence: str, model: str = "sentence-transformer") -> List[float]:
    """
    生成句子嵌入向量
    
    Args:
        sentence: 输入句子
        model: 模型类型
    
    Returns:
        嵌入向量列表
    """
    if model == "sentence-transformer" and SENTENCE_TRANSFORMER_AVAILABLE:
        try:
            model_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "models/sentence-transformer"
            )
            if os.path.exists(model_path):
                embedder = SentenceTransformer(model_path)
            else:
                # 使用在线模型，指定缓存目录为D:\models
                embedder = SentenceTransformer(
                    'sentence-transformers/all-mpnet-base-v2',
                    cache_folder=MODEL_CACHE_DIR
                )
            
            embedding = embedder.encode(sentence, convert_to_numpy=True).tolist()
            return embedding
        except Exception as e:
            logging.warning(f"加载sentence-transformer失败: {e}，使用简化版")
            return _simple_embedding(sentence)
    else:
        return _simple_embedding(sentence)


def _simple_embedding(sentence: str) -> List[float]:
    """简化版嵌入（实际应用中应使用真实嵌入模型）"""
    logging.warning("使用简化版嵌入，建议安装sentence-transformers")
    # 返回固定长度的零向量（实际应用中应使用真实嵌入）
    return [0.0] * 384


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    计算余弦相似度
    
    Args:
        vec1: 向量1
        vec2: 向量2
    
    Returns:
        余弦相似度（0-1之间）
    """
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    similarity = dot_product / (norm1 * norm2)
    # 归一化到0-1
    return (similarity + 1) / 2


class ToolRegistry:
    """工具注册表"""
    
    def __init__(self, embedding_dir: Optional[str] = None):
        """
        初始化工具注册表
        
        Args:
            embedding_dir: 嵌入向量存储目录
        """
        self.tools: Dict[str, Dict] = {}
        self.embedding_dir = embedding_dir or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "tools/embeddings"
        )
        os.makedirs(self.embedding_dir, exist_ok=True)
    
    def register_tool(
        self,
        tool_name: str,
        tool_func: Callable,
        description: str,
        force_regenerate: bool = False
    ):
        """
        注册工具
        
        Args:
            tool_name: 工具名称
            tool_func: 工具函数
            description: 工具描述
            force_regenerate: 是否强制重新生成嵌入向量
        """
        embedding_file = os.path.join(self.embedding_dir, f"{tool_name}.npy")
        
        # 尝试加载已存在的嵌入向量
        if os.path.exists(embedding_file) and not force_regenerate:
            try:
                embedding = np.load(embedding_file).tolist()
                logging.info(f"加载工具 {tool_name} 的嵌入向量")
            except Exception as e:
                logging.warning(f"加载嵌入向量失败: {e}，重新生成")
                embedding = None
        else:
            embedding = None
        
        # 如果没有嵌入向量，生成新的
        if embedding is None:
            # 构建查询字符串：工具名 + 描述
            query = f"{tool_name} {description}"
            embedding = sentence_embedding(query)
            
            # 保存嵌入向量
            np.save(embedding_file, np.array(embedding))
            logging.info(f"为工具 {tool_name} 生成并保存嵌入向量")
        
        # 注册工具
        self.tools[tool_name] = {
            "func": tool_func,
            "description": description,
            "embedding": embedding
        }
    
    def match_tools(
        self,
        user_query: str,
        top_k: int = 3,
        threshold: float = 0.5
    ) -> List[Tuple[str, float]]:
        """
        匹配最相关的工具
        
        Args:
            user_query: 用户查询
            top_k: 返回top_k个工具
            threshold: 相似度阈值
        
        Returns:
            [(工具名, 相似度), ...] 列表，按相似度降序排列
        """
        if not self.tools:
            return []
        
        # 生成查询的嵌入向量
        query_embedding = sentence_embedding(user_query)
        
        # 计算与所有工具的相似度
        similarities = {}
        for tool_name, tool_info in self.tools.items():
            similarity = cosine_similarity(query_embedding, tool_info["embedding"])
            if similarity >= threshold:
                similarities[tool_name] = similarity
        
        # 按相似度排序
        sorted_tools = sorted(
            similarities.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 返回top_k
        return sorted_tools[:top_k]
    
    def get_tool(self, tool_name: str) -> Optional[Callable]:
        """获取工具函数"""
        if tool_name in self.tools:
            return self.tools[tool_name]["func"]
        return None


# 全局工具注册表实例
_tool_registry = None


def get_tool_registry() -> ToolRegistry:
    """获取全局工具注册表"""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def register_tool_for_agent(
    tool_name: str,
    tool_func: Callable,
    description: str
):
    """
    为Agent注册工具（便捷函数）
    
    Args:
        tool_name: 工具名称
        tool_func: 工具函数
        description: 工具描述
    """
    registry = get_tool_registry()
    registry.register_tool(tool_name, tool_func, description)


def match_tools_for_query(
    user_query: str,
    top_k: int = 3,
    threshold: float = 0.5
) -> List[str]:
    """
    为查询匹配最相关的工具（便捷函数）
    
    Args:
        user_query: 用户查询
        top_k: 返回top_k个工具
        threshold: 相似度阈值
    
    Returns:
        工具名称列表
    """
    registry = get_tool_registry()
    matched = registry.match_tools(user_query, top_k, threshold)
    return [tool_name for tool_name, _ in matched]


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 创建工具注册表
    registry = ToolRegistry()
    
    # 模拟注册一些工具
    def get_cluster_logs():
        """获取集群所有节点的最新日志内容"""
        pass
    
    def get_node_log(node_name: str):
        """获取指定节点的日志内容"""
        pass
    
    def get_monitoring_metrics():
        """获取集群的实时监控指标"""
        pass
    
    registry.register_tool(
        "get_cluster_logs",
        get_cluster_logs,
        "获取集群所有节点的最新日志内容，用来分析集群的整体状态"
    )
    
    registry.register_tool(
        "get_node_log",
        get_node_log,
        "获取指定节点的日志内容，用来分析指定节点的状态"
    )
    
    registry.register_tool(
        "get_monitoring_metrics",
        get_monitoring_metrics,
        "获取集群的实时监控指标"
    )
    
    # 测试匹配
    query = "NameNode无法启动，查看日志"
    matched = registry.match_tools(query, top_k=2)
    print(f"查询: {query}")
    print("匹配的工具:")
    for tool_name, similarity in matched:
        print(f"  - {tool_name}: {similarity:.3f}")

