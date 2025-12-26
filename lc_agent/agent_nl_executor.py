#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
集成自然语言执行能力的Agent
增强版Agent，能够理解自然语言并自动执行Hadoop集群操作
"""

import os
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI

# 导入原有模块
try:
    from .agent import (
        get_cluster_logs,
        get_node_log,
        get_monitoring_metrics,
        website_search,
        hadoop_cluster_operation,
        create_llm
    )
    from .natural_language_executor import (
        get_executor,
        execute_natural_language_command,
        OperationIntent
    )
except ImportError:
    from lc_agent.agent import (
        get_cluster_logs,
        get_node_log,
        get_monitoring_metrics,
        website_search,
        hadoop_cluster_operation,
        create_llm
    )
    from lc_agent.natural_language_executor import (
        get_executor,
        execute_natural_language_command,
        OperationIntent
    )


# ==================== 增强的工具描述 ====================

# 增强hadoop_cluster_operation工具的描述
ENHANCED_HADOOP_OPERATION_DESCRIPTION = """
执行Hadoop集群操作。支持自然语言指令，自动理解操作类型和目标节点。

**操作类型**（支持中英文）：
- 启动/start/开启/打开 → start
- 停止/stop/关闭/关机 → stop  
- 重启/restart/重新启动 → restart

**目标节点**（支持中英文和缩写）：
- NameNode/namenode/nn/名称节点 → namenode
- DataNode1/datanode1/dn1/数据节点1 → datanode1
- DataNode2/datanode2/dn2/数据节点2 → datanode2
- 整个集群/全部/所有/cluster → 不指定container（操作整个集群）

**使用示例**：
- "重启NameNode" → command="restart", container="namenode"
- "启动整个集群" → command="start", container=None
- "停止DataNode1" → command="stop", container="datanode1"
- "关闭NameNode" → command="stop", container="namenode"

**参数说明**：
- command: 操作类型（"start"/"stop"/"restart"）
- container: 节点名称（可选，不指定则操作整个集群）
"""


# ==================== 自然语言执行工具 ====================

@tool("execute_natural_language_command", description="""
执行自然语言Hadoop集群操作指令。能够理解用户的自然语言并自动执行对应的操作。

**支持的指令类型**：
1. **集群操作**：
   - "重启NameNode"
   - "启动整个集群"
   - "停止DataNode1"

2. **查询操作**：
   - "查看NameNode日志"
   - "查看集群状态"
   - "获取集群监控指标"

3. **诊断操作**：
   - "NameNode无法启动，帮我诊断"
   - "分析集群性能问题"

**参数**：
- user_input: 用户的自然语言指令
- auto_confirm: 是否自动确认危险操作（默认False，危险操作需要用户确认）

**返回**：
执行结果，包括操作状态、结果信息等
""")
def execute_nl_command_tool(user_input: str, auto_confirm: bool = False) -> str:
    """
    执行自然语言命令工具
    
    Args:
        user_input: 用户输入的自然语言
        auto_confirm: 是否自动确认危险操作
    
    Returns:
        执行结果字符串
    """
    try:
        executor = get_executor()
        result = executor.execute(user_input, auto_confirm)
        
        if result["status"] == "requires_confirmation":
            return f"⚠️ {result['message']}\n\n解析的操作意图：\n- 操作类型: {result['intent'].operation_type}\n- 目标: {result['intent'].target}\n- 参数: {result['intent'].parameters}"
        elif result["status"] == "success":
            return f"✅ 操作执行成功：{result.get('operation', '')}\n\n结果：\n{result.get('result', '')}"
        else:
            return f"❌ 操作失败：{result.get('message', '未知错误')}"
    except Exception as e:
        return f"❌ 执行失败：{str(e)}"


# ==================== 增强的Agent创建函数 ====================

def create_agent_with_nl_executor(model_name: str = "qwen-8b"):
    """
    创建集成自然语言执行能力的Agent实例
    
    Args:
        model_name: 模型名称
    
    Returns:
        Agent 实例
    """
    print(f"[DEBUG] 开始创建集成自然语言执行能力的Agent - 模型: {model_name}")
    
    llm = create_llm(model_name)
    
    # 基础工具列表
    tools = [
        get_cluster_logs,
        get_node_log,
        get_monitoring_metrics,
        website_search,
        hadoop_cluster_operation,
    ]
    
    # 添加自然语言执行工具
    tools.append(execute_nl_command_tool)
    
    # 增强的系统提示词
    system_prompt = """你是HDFS集群智能操作助手，具备以下能力：

**核心能力**：
1. **自然语言理解**：能够理解用户的自然语言指令并自动执行
2. **集群操作**：可以执行启动、停止、重启等集群操作
3. **日志分析**：可以获取和分析集群日志
4. **监控查询**：可以查询集群监控指标
5. **问题诊断**：可以诊断集群问题并提供解决方案

**操作指令示例**：

**集群操作**：
- "重启NameNode" → 使用 execute_natural_language_command 或 hadoop_cluster_operation
- "启动整个集群" → 执行集群启动操作
- "停止DataNode1" → 停止指定节点

**查询操作**：
- "查看NameNode日志" → 使用 get_node_log(node_name="NameNode")
- "查看集群状态" → 使用 get_monitoring_metrics()
- "获取所有节点日志" → 使用 get_cluster_logs()

**诊断操作**：
- "NameNode无法启动，帮我诊断" → 
  1. 先使用 search_diagnosis_knowledge 检索相关知识
  2. 然后获取NameNode日志
  3. 查看监控指标
  4. 综合分析给出诊断结果

**智能执行策略**：
1. **简单指令**：直接使用 execute_natural_language_command 工具，它能自动理解并执行
2. **复杂指令**：分解为多个步骤，逐步执行
3. **危险操作**：执行前会要求用户确认（如停止、重启操作）
4. **组合操作**：支持"先查看日志，如果有错误就重启"这样的组合指令

**重要原则**：
1. 理解用户意图，不要逐字翻译
2. 自动提取操作类型和目标节点
3. 危险操作（停止、重启）需要用户确认
4. 返回清晰的操作结果和状态信息
5. 如果操作失败，提供错误信息和解决建议

请用专业、友好、清晰的语言与用户交互。"""
    
    print(f"[DEBUG] 正在创建Agent（使用 {model_name} 模型）...")
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt
    )
    
    print(f"[DEBUG] ✅ Agent实例创建成功 - 模型: {model_name}")
    
    return agent


# ==================== 便捷函数 ====================

def create_enhanced_agent(model_name: str = "qwen-8b"):
    """
    创建增强版Agent（便捷函数）
    
    Args:
        model_name: 模型名称
    
    Returns:
        Agent 实例
    """
    return create_agent_with_nl_executor(model_name)


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 测试代码
    print("=" * 60)
    print("测试自然语言执行能力")
    print("=" * 60)
    
    # 创建Agent
    agent = create_agent_with_nl_executor()
    
    # 测试用例
    test_cases = [
        "重启NameNode",
        "查看NameNode日志",
        "查看集群状态",
        "NameNode无法启动，帮我诊断",
    ]
    
    config = {"configurable": {"thread_id": "test_nl_executor"}}
    
    for query in test_cases:
        print(f"\n{'='*60}")
        print(f"用户输入: {query}")
        print('='*60)
        
        try:
            result = agent.invoke(
                {"messages": [{"role": "user", "content": query}]},
                config=config
            )
            
            print("\nAgent响应:")
            print(result['messages'][-1].content)
        except Exception as e:
            print(f"❌ 执行失败: {e}")
            import traceback
            traceback.print_exc()

