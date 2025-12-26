#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自然语言到Hadoop集群操作执行器
理解自然语言并自动执行对应的Hadoop集群操作
"""

import re
import json
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

# 导入知识库和工具匹配
try:
    from .knowledge_base import get_kb_manager, search_diagnosis_knowledge
    from .tool_matcher import get_tool_registry, match_tools_for_query
except ImportError:
    from lc_agent.knowledge_base import get_kb_manager, search_diagnosis_knowledge
    from lc_agent.tool_matcher import get_tool_registry, match_tools_for_query


@dataclass
class OperationIntent:
    """操作意图"""
    operation_type: str  # start, stop, restart, query, diagnose
    target: Optional[str] = None  # namenode, datanode1, datanode2, cluster
    parameters: Dict[str, Any] = None
    confidence: float = 0.0  # 置信度 0-1
    requires_confirmation: bool = False  # 是否需要确认


class OperationMapper:
    """操作映射器：自然语言 -> 操作参数"""
    
    def __init__(self):
        # 操作类型映射（中文和英文）
        self.command_map = {
            # 启动
            "启动": "start", "start": "start", "开启": "start", 
            "打开": "start", "开启": "start", "运行": "start",
            # 停止
            "停止": "stop", "stop": "stop", "关闭": "stop", 
            "关机": "stop", "关闭": "stop", "停止": "stop",
            # 重启
            "重启": "restart", "restart": "restart", 
            "重新启动": "restart", "重启": "restart",
            # 查询
            "查看": "query", "查看": "query", "显示": "query",
            "获取": "query", "查询": "query", "检查": "query",
            # 诊断
            "诊断": "diagnose", "分析": "diagnose", "排查": "diagnose",
        }
        
        # 节点映射
        self.node_map = {
            # NameNode
            "namenode": "namenode", "nn": "namenode", 
            "name node": "namenode", "名称节点": "namenode",
            # DataNode1
            "datanode1": "datanode1", "dn1": "datanode1", 
            "data node 1": "datanode1", "数据节点1": "datanode1",
            # DataNode2
            "datanode2": "datanode2", "dn2": "datanode2", 
            "data node 2": "datanode2", "数据节点2": "datanode2",
            # 集群
            "集群": "cluster", "cluster": "cluster",
            "整个集群": "cluster", "全部": "cluster", "所有": "cluster",
        }
        
        # 操作知识库（常见操作模板）
        self.operation_kb = self._init_operation_kb()
    
    def _init_operation_kb(self) -> Dict[str, Dict]:
        """初始化操作知识库"""
        return {
            "重启NameNode": {
                "operation_type": "restart",
                "target": "namenode",
                "command": "restart",
                "container": "namenode",
                "description": "重启NameNode节点"
            },
            "启动NameNode": {
                "operation_type": "start",
                "target": "namenode",
                "command": "start",
                "container": "namenode",
                "description": "启动NameNode节点"
            },
            "停止NameNode": {
                "operation_type": "stop",
                "target": "namenode",
                "command": "stop",
                "container": "namenode",
                "description": "停止NameNode节点"
            },
            "查看NameNode日志": {
                "operation_type": "query",
                "target": "namenode",
                "tool": "get_node_log",
                "parameters": {"node_name": "NameNode"},
                "description": "查看NameNode日志"
            },
            "查看集群状态": {
                "operation_type": "query",
                "target": "cluster",
                "tool": "get_monitoring_metrics",
                "description": "查看集群监控指标"
            },
            "查看集群日志": {
                "operation_type": "query",
                "target": "cluster",
                "tool": "get_cluster_logs",
                "description": "查看所有节点日志"
            },
        }
    
    def parse_intent(self, user_input: str) -> OperationIntent:
        """
        解析用户意图
        
        Args:
            user_input: 用户输入的自然语言
        
        Returns:
            OperationIntent对象
        """
        user_input_lower = user_input.lower().strip()
        
        # 1. 先尝试从知识库匹配
        matched_template = self._match_from_kb(user_input_lower)
        if matched_template:
            return self._create_intent_from_template(matched_template, user_input)
        
        # 2. 使用规则解析
        return self._parse_with_rules(user_input_lower, user_input)
    
    def _match_from_kb(self, user_input: str) -> Optional[Dict]:
        """从知识库匹配操作模板"""
        # 简单的关键词匹配
        for template_key, template_value in self.operation_kb.items():
            if template_key.lower() in user_input:
                return template_value
        
        # 使用向量检索（如果可用）
        try:
            kb_manager = get_kb_manager()
            # 创建操作知识库（如果不存在）
            if "OperationKB" not in [kb.kb_name for kb in kb_manager.knowledge_bases.values()]:
                self._create_operation_kb()
            
            # 搜索操作知识库
            results = kb_manager.search_knowledge(
                query=user_input,
                kb_name="OperationKB",
                top_k=1,
                score_threshold=0.6
            )
            
            if results:
                # 从检索结果中提取操作信息
                doc = results[0][0]
                if 'operation_type' in doc.metadata:
                    return {
                        "operation_type": doc.metadata.get('operation_type'),
                        "target": doc.metadata.get('target'),
                        "command": doc.metadata.get('command'),
                        "container": doc.metadata.get('container'),
                        "tool": doc.metadata.get('tool'),
                        "parameters": json.loads(doc.metadata.get('parameters', '{}')),
                    }
        except Exception as e:
            logging.warning(f"知识库检索失败: {e}，使用规则解析")
        
        return None
    
    def _create_operation_kb(self):
        """创建操作知识库"""
        try:
            kb_manager = get_kb_manager()
            operation_kb = kb_manager.get_or_create_kb("OperationKB")
            
            # 添加操作模板到知识库
            for template_key, template_value in self.operation_kb.items():
                metadata = {
                    "template_key": template_key,
                    "operation_type": template_value.get("operation_type", ""),
                    "target": template_value.get("target", ""),
                    "command": template_value.get("command", ""),
                    "container": template_value.get("container", ""),
                    "tool": template_value.get("tool", ""),
                    "parameters": json.dumps(template_value.get("parameters", {})),
                }
                
                operation_kb.add_texts(
                    texts=[f"{template_key}: {template_value.get('description', '')}"],
                    metadatas=[metadata]
                )
            
            operation_kb.save()
        except Exception as e:
            logging.warning(f"创建操作知识库失败: {e}")
    
    def _create_intent_from_template(self, template: Dict, original_input: str) -> OperationIntent:
        """从模板创建意图"""
        return OperationIntent(
            operation_type=template.get("operation_type", "query"),
            target=template.get("target"),
            parameters={
                "command": template.get("command"),
                "container": template.get("container"),
                "tool": template.get("tool"),
                **template.get("parameters", {})
            },
            confidence=0.9,  # 模板匹配置信度高
            requires_confirmation=template.get("operation_type") in ["stop", "restart"]
        )
    
    def _parse_with_rules(self, user_input_lower: str, original_input: str) -> OperationIntent:
        """使用规则解析意图"""
        # 提取操作类型
        operation_type = None
        for keyword, op_type in self.command_map.items():
            if keyword in user_input_lower:
                operation_type = op_type
                break
        
        if not operation_type:
            operation_type = "query"  # 默认查询
        
        # 提取目标节点
        target = None
        for keyword, node in self.node_map.items():
            if keyword in user_input_lower:
                target = node
                break
        
        # 构建参数
        parameters = {}
        
        # 如果是集群操作
        if operation_type in ["start", "stop", "restart"]:
            parameters["command"] = operation_type
            if target and target != "cluster":
                parameters["container"] = target
        elif operation_type == "query":
            # 查询操作，需要确定使用哪个工具
            if "日志" in user_input_lower or "log" in user_input_lower:
                if target and target != "cluster":
                    parameters["tool"] = "get_node_log"
                    parameters["node_name"] = target.capitalize()
                else:
                    parameters["tool"] = "get_cluster_logs"
            elif "状态" in user_input_lower or "监控" in user_input_lower or "metrics" in user_input_lower:
                parameters["tool"] = "get_monitoring_metrics"
        
        # 计算置信度
        confidence = 0.7  # 规则解析默认置信度
        if operation_type and target:
            confidence = 0.8
        if operation_type in ["start", "stop", "restart"]:
            confidence = 0.85
        
        # 判断是否需要确认
        requires_confirmation = operation_type in ["stop", "restart"]
        
        return OperationIntent(
            operation_type=operation_type,
            target=target or "cluster",
            parameters=parameters,
            confidence=confidence,
            requires_confirmation=requires_confirmation
        )


class NaturalLanguageExecutor:
    """自然语言执行器"""
    
    def __init__(self):
        self.mapper = OperationMapper()
        self.tool_registry = get_tool_registry()
    
    def execute(self, user_input: str, auto_confirm: bool = False) -> Dict[str, Any]:
        """
        执行自然语言指令
        
        Args:
            user_input: 用户输入的自然语言
            auto_confirm: 是否自动确认危险操作
        
        Returns:
            执行结果字典
        """
        # 1. 解析意图
        intent = self.mapper.parse_intent(user_input)
        
        # 2. 安全验证
        if intent.requires_confirmation and not auto_confirm:
            return {
                "status": "requires_confirmation",
                "intent": intent,
                "message": f"检测到{intent.operation_type}操作，需要确认。请回复'确认'继续。"
            }
        
        # 3. 执行操作
        try:
            if intent.operation_type in ["start", "stop", "restart"]:
                return self._execute_cluster_operation(intent)
            elif intent.operation_type == "query":
                return self._execute_query_operation(intent)
            elif intent.operation_type == "diagnose":
                return self._execute_diagnose_operation(intent, user_input)
            else:
                return {
                    "status": "error",
                    "message": f"不支持的操作类型: {intent.operation_type}"
                }
        except Exception as e:
            logging.error(f"执行操作失败: {e}")
            return {
                "status": "error",
                "message": f"执行失败: {str(e)}"
            }
    
    def _execute_cluster_operation(self, intent: OperationIntent) -> Dict[str, Any]:
        """执行集群操作"""
        from .agent import hadoop_cluster_operation
        
        command = intent.parameters.get("command")
        container = intent.parameters.get("container")
        
        result = hadoop_cluster_operation(command, container)
        
        return {
            "status": "success",
            "operation": f"{command} {container or 'cluster'}",
            "result": result
        }
    
    def _execute_query_operation(self, intent: OperationIntent) -> Dict[str, Any]:
        """执行查询操作"""
        tool_name = intent.parameters.get("tool")
        
        if tool_name == "get_node_log":
            from .agent import get_node_log
            node_name = intent.parameters.get("node_name")
            result = get_node_log(node_name)
        elif tool_name == "get_cluster_logs":
            from .agent import get_cluster_logs
            result = get_cluster_logs()
        elif tool_name == "get_monitoring_metrics":
            from .agent import get_monitoring_metrics
            result = get_monitoring_metrics()
        else:
            return {
                "status": "error",
                "message": f"未知的查询工具: {tool_name}"
            }
        
        return {
            "status": "success",
            "operation": f"query {tool_name}",
            "result": result
        }
    
    def _execute_diagnose_operation(self, intent: OperationIntent, user_input: str) -> Dict[str, Any]:
        """执行诊断操作"""
        # 使用知识库检索相关知识
        knowledge = search_diagnosis_knowledge(
            query=user_input,
            expert_type=intent.target if intent.target != "cluster" else "all"
        )
        
        return {
            "status": "success",
            "operation": "diagnose",
            "knowledge": knowledge,
            "message": "已检索相关知识，请结合日志和监控指标进行诊断"
        }


# 全局执行器实例
_executor = None


def get_executor() -> NaturalLanguageExecutor:
    """获取全局执行器"""
    global _executor
    if _executor is None:
        _executor = NaturalLanguageExecutor()
    return _executor


def execute_natural_language_command(user_input: str, auto_confirm: bool = False) -> Dict[str, Any]:
    """
    执行自然语言命令（便捷函数）
    
    Args:
        user_input: 用户输入的自然语言
        auto_confirm: 是否自动确认危险操作
    
    Returns:
        执行结果
    """
    executor = get_executor()
    return executor.execute(user_input, auto_confirm)


if __name__ == "__main__":
    # 测试代码
    logging.basicConfig(level=logging.INFO)
    
    executor = NaturalLanguageExecutor()
    
    # 测试用例
    test_cases = [
        "重启NameNode",
        "启动整个集群",
        "查看NameNode日志",
        "查看集群状态",
        "停止DataNode1",
    ]
    
    for test_input in test_cases:
        print(f"\n{'='*60}")
        print(f"输入: {test_input}")
        print('='*60)
        
        intent = executor.mapper.parse_intent(test_input)
        print(f"解析结果:")
        print(f"  操作类型: {intent.operation_type}")
        print(f"  目标: {intent.target}")
        print(f"  参数: {intent.parameters}")
        print(f"  置信度: {intent.confidence}")
        print(f"  需要确认: {intent.requires_confirmation}")

