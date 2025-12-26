#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成知识库检索和工具匹配的Agent示例
展示如何将DB-GPT的技术迁移到RCA项目中
"""

import os
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

# 导入知识库和工具匹配模块
try:
    from .knowledge_base import search_diagnosis_knowledge, get_kb_manager
    from .tool_matcher import get_tool_registry, register_tool_for_agent, match_tools_for_query
    from .agent import (
        get_cluster_logs,
        get_node_log,
        get_monitoring_metrics,
        website_search,
        hadoop_cluster_operation,
        create_llm
    )
except ImportError:
    # 如果相对导入失败，尝试绝对导入
    from lc_agent.knowledge_base import search_diagnosis_knowledge, get_kb_manager
    from lc_agent.tool_matcher import get_tool_registry, register_tool_for_agent, match_tools_for_query
    from lc_agent.agent import (
        get_cluster_logs,
        get_node_log,
        get_monitoring_metrics,
        website_search,
        hadoop_cluster_operation,
        create_llm
    )


# ==================== 新增工具：知识库检索 ====================

@tool("search_diagnosis_knowledge", description="从知识库检索诊断相关知识，包括历史故障案例和Hadoop文档")
def search_diagnosis_knowledge_tool(
    query: str,
    expert_type: str = "all"
) -> str:
    """
    从知识库检索诊断相关知识
    
    Args:
        query: 查询字符串（例如："NameNode无法启动"）
        expert_type: 专家类型（"namenode", "datanode", "yarn", "all"）
    
    Returns:
        检索到的相关知识字符串
    """
    return search_diagnosis_knowledge(query, expert_type)


# ==================== 增强的Agent创建函数 ====================

def create_agent_with_kb(model_name: str = "qwen-8b"):
    """
    创建集成知识库检索的Agent实例
    
    Args:
        model_name: 模型名称
    
    Returns:
        Agent 实例
    """
    print(f"[DEBUG] 开始创建集成知识库的Agent实例 - 模型: {model_name}")
    
    llm = create_llm(model_name)
    
    # 基础工具列表
    base_tools = [
        get_cluster_logs,
        get_node_log,
        get_monitoring_metrics,
        website_search,
        hadoop_cluster_operation,
    ]
    
    # 添加知识库检索工具
    tools = base_tools + [search_diagnosis_knowledge_tool]
    
    # 注册所有工具到工具匹配器（用于智能工具选择）
    tool_registry = get_tool_registry()
    for tool_func in tools:
        # 获取工具的描述
        if hasattr(tool_func, 'description'):
            description = tool_func.description
        elif hasattr(tool_func, '__doc__'):
            description = tool_func.__doc__ or ""
        else:
            description = f"工具: {tool_func.__name__}"
        
        tool_registry.register_tool(
            tool_name=tool_func.name if hasattr(tool_func, 'name') else tool_func.__name__,
            tool_func=tool_func,
            description=description
        )
    
    # 增强的系统提示词
    system_prompt = """你是HDFS集群问题诊断专家，具备以下能力：

1. **知识库检索**：你可以使用 search_diagnosis_knowledge 工具从历史故障案例和Hadoop文档中检索相关知识
2. **日志分析**：你可以获取和分析集群日志
3. **监控指标**：你可以获取实时监控指标
4. **网络搜索**：你可以搜索最新的解决方案

**诊断流程建议**：
1. 首先使用 search_diagnosis_knowledge 检索相关知识，了解类似问题的解决方案
2. 然后获取相关节点的日志和监控指标
3. 结合知识库知识和实际数据进行分析
4. 给出诊断结果和解决方案

请用专业、清晰的语言回答。"""
    
    print(f"[DEBUG] 正在创建Agent（使用 {model_name} 模型）...")
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt
    )
    
    print(f"[DEBUG] ✅ Agent实例创建成功 - 模型: {model_name}")
    
    return agent


# ==================== 智能工具推荐功能 ====================

def recommend_tools(user_query: str, top_k: int = 3) -> list:
    """
    根据用户查询推荐最相关的工具
    
    Args:
        user_query: 用户查询
        top_k: 返回top_k个工具
    
    Returns:
        推荐的工具名称列表
    """
    return match_tools_for_query(user_query, top_k=top_k)


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 初始化知识库（添加示例数据）
    try:
        from .knowledge_base import init_sample_knowledge
    except ImportError:
        from lc_agent.knowledge_base import init_sample_knowledge
    init_sample_knowledge()
    
    # 创建Agent
    agent = create_agent_with_kb()
    
    # 测试工具推荐
    query = "NameNode无法启动，需要查看日志和检索相关知识"
    recommended = recommend_tools(query, top_k=3)
    print(f"查询: {query}")
    print(f"推荐工具: {recommended}")
    
    # 测试Agent调用
    config = {"configurable": {"thread_id": "test_1"}}
    result = agent.invoke(
        {"messages": [{"role": "user", "content": query}]},
        config=config
    )
    
    print("\n[Agent响应]")
    print(result['messages'][-1].content)

