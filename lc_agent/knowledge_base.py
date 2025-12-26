#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库检索（RAG）机制实现
从DB-GPT迁移，适配HDFS集群诊断场景
"""

import os
import json
from typing import List, Dict, Optional, Tuple
from langchain.docstore.document import Document
# LangChain 1.0.7: 使用 langchain_community 而不是 langchain
from langchain_community.vectorstores import FAISS
# LangChain 1.0.7: Embeddings 接口位置可能有变化，尝试兼容导入
try:
    from langchain.embeddings.base import Embeddings
except ImportError:
    # LangChain 1.0+ 可能使用新的接口
    try:
        from langchain_core.embeddings import Embeddings
    except ImportError:
        from langchain.schema.embeddings import Embeddings
import numpy as np
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


class SimpleEmbeddings(Embeddings):
    """简化的嵌入模型封装"""
    
    def __init__(self, model_name: str = "sentence-transformer"):
        self.model_name = model_name
        if SENTENCE_TRANSFORMER_AVAILABLE:
            try:
                model_path = os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "models/sentence-transformer"
                )
                if os.path.exists(model_path):
                    self.embedder = SentenceTransformer(model_path)
                else:
                    # 使用在线模型，指定缓存目录
                    self.embedder = SentenceTransformer(
                        'sentence-transformers/all-mpnet-base-v2',
                        cache_folder=MODEL_CACHE_DIR
                    )
            except Exception as e:
                logging.warning(f"加载sentence-transformer失败: {e}，使用简化版")
                self.embedder = None
        else:
            self.embedder = None
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档列表"""
        if self.embedder:
            embeddings = self.embedder.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        else:
            # 简化版：使用简单的词频向量（实际应用中应使用真实嵌入模型）
            logging.warning("使用简化版嵌入，建议安装sentence-transformers")
            return [[0.0] * 384 for _ in texts]
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入查询文本"""
        if self.embedder:
            embedding = self.embedder.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        else:
            logging.warning("使用简化版嵌入，建议安装sentence-transformers")
            return [0.0] * 384


class KnowledgeBase:
    """知识库管理类"""
    
    def __init__(self, kb_name: str, kb_path: Optional[str] = None):
        """
        初始化知识库
        
        Args:
            kb_name: 知识库名称（如：NameNodeExpert, DataNodeExpert）
            kb_path: 知识库存储路径（可选）
        """
        self.kb_name = kb_name
        self.kb_path = kb_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "knowledge_base",
            kb_name
        )
        os.makedirs(self.kb_path, exist_ok=True)
        
        # 初始化嵌入模型
        self.embeddings = SimpleEmbeddings()
        
        # 向量存储
        self.vector_store = None
        self._load_or_create_vector_store()
    
    def _load_or_create_vector_store(self):
        """加载或创建向量存储"""
        vector_store_path = os.path.join(self.kb_path, "vector_store")
        
        if os.path.exists(vector_store_path) and os.listdir(vector_store_path):
            try:
                self.vector_store = FAISS.load_local(
                    vector_store_path,
                    self.embeddings
                )
                logging.info(f"成功加载知识库: {self.kb_name}")
            except Exception as e:
                logging.warning(f"加载向量存储失败: {e}，将创建新的")
                self.vector_store = None
        
        if self.vector_store is None:
            # 创建空的向量存储
            self.vector_store = FAISS.from_texts(
                ["初始化"],
                self.embeddings
            )
            # 删除初始化文档
            self.vector_store.delete([self.vector_store.index_to_docstore_id[0]])
    
    def add_documents(self, documents: List[Document]):
        """
        添加文档到知识库
        
        Args:
            documents: Document列表
        """
        if not documents:
            return
        
        # 添加到向量存储
        self.vector_store.add_documents(documents)
        
        # 保存向量存储
        self.save()
    
    def add_texts(self, texts: List[str], metadatas: Optional[List[Dict]] = None):
        """
        添加文本到知识库
        
        Args:
            texts: 文本列表
            metadatas: 元数据列表（可选）
        """
        if not texts:
            return
        
        if metadatas is None:
            metadatas = [{}] * len(texts)
        
        # 创建Document对象
        documents = [
            Document(page_content=text, metadata=metadata)
            for text, metadata in zip(texts, metadatas)
        ]
        
        self.add_documents(documents)
    
    def search(self, query: str, top_k: int = 3, score_threshold: float = 0.4) -> List[Tuple[Document, float]]:
        """
        搜索相关知识
        
        Args:
            query: 查询字符串
            top_k: 返回top_k个结果
            score_threshold: 相似度阈值（FAISS使用L2距离，越小越相似）
        
        Returns:
            (Document, score) 元组列表
        """
        try:
            # FAISS使用similarity_search_with_score
            results = self.vector_store.similarity_search_with_score(query, k=top_k)
            
            # 过滤低分结果（注意：FAISS返回的是距离，不是相似度）
            # 距离越小越相似，所以需要反转阈值判断
            filtered_results = [
                (doc, score) for doc, score in results
                if score <= (1.0 - score_threshold) * 10  # 简单的阈值转换
            ]
            
            return filtered_results
        except Exception as e:
            logging.error(f"搜索知识库失败: {e}")
            return []
    
    def save(self):
        """保存向量存储"""
        vector_store_path = os.path.join(self.kb_path, "vector_store")
        os.makedirs(vector_store_path, exist_ok=True)
        self.vector_store.save_local(vector_store_path)
        logging.info(f"知识库已保存: {self.kb_name}")


class KnowledgeBaseManager:
    """知识库管理器"""
    
    def __init__(self):
        self.knowledge_bases: Dict[str, KnowledgeBase] = {}
        self._init_default_knowledge_bases()
    
    def _init_default_knowledge_bases(self):
        """初始化默认知识库"""
        # HDFS集群诊断相关的知识库
        default_kbs = [
            "NameNodeExpert",
            "DataNodeExpert",
            "YARNExpert",
            "HistoryCases",  # 历史故障案例
            "HadoopDocs",    # Hadoop官方文档
        ]
        
        for kb_name in default_kbs:
            self.get_or_create_kb(kb_name)
    
    def get_or_create_kb(self, kb_name: str) -> KnowledgeBase:
        """获取或创建知识库"""
        if kb_name not in self.knowledge_bases:
            self.knowledge_bases[kb_name] = KnowledgeBase(kb_name)
        return self.knowledge_bases[kb_name]
    
    def search_knowledge(
        self,
        query: str,
        kb_name: Optional[str] = None,
        top_k: int = 3,
        score_threshold: float = 0.4
    ) -> List[Tuple[Document, float]]:
        """
        搜索知识库
        
        Args:
            query: 查询字符串
            kb_name: 知识库名称（None表示搜索所有知识库）
            top_k: 返回top_k个结果
            score_threshold: 相似度阈值
        
        Returns:
            (Document, score) 元组列表
        """
        if kb_name:
            # 搜索指定知识库
            if kb_name in self.knowledge_bases:
                return self.knowledge_bases[kb_name].search(query, top_k, score_threshold)
            else:
                logging.warning(f"知识库不存在: {kb_name}")
                return []
        else:
            # 搜索所有知识库
            all_results = []
            for kb in self.knowledge_bases.values():
                results = kb.search(query, top_k, score_threshold)
                all_results.extend(results)
            
            # 按分数排序并返回top_k
            all_results.sort(key=lambda x: x[1])
            return all_results[:top_k]
    
    def match_knowledge_base(self, expert_type: str) -> str:
        """
        根据专家类型匹配知识库名称
        
        Args:
            expert_type: 专家类型（如："namenode", "datanode"）
        
        Returns:
            知识库名称
        """
        expert_type_lower = expert_type.lower()
        
        # 匹配规则
        if "namenode" in expert_type_lower or "nn" in expert_type_lower:
            return "NameNodeExpert"
        elif "datanode" in expert_type_lower or "dn" in expert_type_lower:
            return "DataNodeExpert"
        elif "yarn" in expert_type_lower:
            return "YARNExpert"
        else:
            # 默认返回历史案例库
            return "HistoryCases"


# 全局知识库管理器实例
_kb_manager = None


def get_kb_manager() -> KnowledgeBaseManager:
    """获取全局知识库管理器"""
    global _kb_manager
    if _kb_manager is None:
        _kb_manager = KnowledgeBaseManager()
    return _kb_manager


def search_diagnosis_knowledge(
    query: str,
    expert_type: str = "all",
    top_k: int = 3,
    score_threshold: float = 0.4
) -> str:
    """
    从知识库检索诊断相关知识（工具函数，供Agent调用）
    
    Args:
        query: 查询字符串（例如："NameNode无法启动"）
        expert_type: 专家类型（"namenode", "datanode", "all"）
        top_k: 返回top_k个结果
        score_threshold: 相似度阈值
    
    Returns:
        检索到的相关知识字符串
    """
    kb_manager = get_kb_manager()
    
    # 匹配知识库
    if expert_type.lower() == "all":
        kb_name = None  # 搜索所有知识库
    else:
        kb_name = kb_manager.match_knowledge_base(expert_type)
    
    # 执行搜索
    results = kb_manager.search_knowledge(
        query=query,
        kb_name=kb_name,
        top_k=top_k,
        score_threshold=score_threshold
    )
    
    # 格式化返回
    if not results:
        return f"未找到与 '{query}' 相关的知识"
    
    knowledge_str = f"找到 {len(results)} 条相关知识：\n\n"
    for idx, (doc, score) in enumerate(results, 1):
        knowledge_str += f"[知识 {idx}] (相似度: {1-score:.2f})\n"
        if doc.metadata:
            if 'source' in doc.metadata:
                knowledge_str += f"来源: {doc.metadata['source']}\n"
            if 'desc' in doc.metadata:
                knowledge_str += f"描述: {doc.metadata['desc']}\n"
        knowledge_str += f"内容: {doc.page_content}\n\n"
    
    return knowledge_str


# 示例：初始化知识库数据
def init_sample_knowledge():
    """初始化示例知识库数据（用于测试）"""
    kb_manager = get_kb_manager()
    
    # NameNode专家知识库
    namenode_kb = kb_manager.get_or_create_kb("NameNodeExpert")
    namenode_kb.add_texts(
        texts=[
            "NameNode无法启动的常见原因：1) 配置文件错误 2) 端口被占用 3) 磁盘空间不足",
            "NameNode启动失败时，检查hdfs-site.xml和core-site.xml配置是否正确",
            "NameNode内存溢出时，需要增加JVM堆内存大小，修改hadoop-env.sh中的HADOOP_HEAPSIZE",
        ],
        metadatas=[
            {"source": "Hadoop官方文档", "desc": "NameNode启动问题"},
            {"source": "故障案例", "desc": "配置检查"},
            {"source": "故障案例", "desc": "内存问题"},
        ]
    )
    
    # DataNode专家知识库
    datanode_kb = kb_manager.get_or_create_kb("DataNodeExpert")
    datanode_kb.add_texts(
        texts=[
            "DataNode无法连接NameNode时，检查网络连接和防火墙设置",
            "DataNode磁盘空间不足会导致数据块复制失败",
            "DataNode心跳超时可能是网络延迟或NameNode负载过高",
        ],
        metadatas=[
            {"source": "故障案例", "desc": "连接问题"},
            {"source": "故障案例", "desc": "存储问题"},
            {"source": "故障案例", "desc": "心跳问题"},
        ]
    )
    
    # 保存所有知识库
    for kb in kb_manager.knowledge_bases.values():
        kb.save()
    
    logging.info("示例知识库数据初始化完成")


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    # 初始化示例数据
    init_sample_knowledge()
    
    # 测试搜索
    result = search_diagnosis_knowledge("NameNode无法启动", expert_type="namenode")
    print(result)

