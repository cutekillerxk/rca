# DB-GPT 技术迁移实施指南

## 一、概述

本文档提供从 DB-GPT 项目迁移关键技术到 RCA 项目的详细实施步骤和代码示例。

## 二、已创建的文件

### 2.1 知识库检索模块
- **文件**: `lc_agent/knowledge_base.py`
- **功能**: 实现 RAG（检索增强生成）机制，从知识库检索诊断相关知识
- **核心类**:
  - `KnowledgeBase`: 单个知识库管理
  - `KnowledgeBaseManager`: 知识库管理器
  - `search_diagnosis_knowledge()`: 工具函数，供Agent调用

### 2.2 工具匹配模块
- **文件**: `lc_agent/tool_matcher.py`
- **功能**: 使用嵌入向量匹配最相关的工具
- **核心类**:
  - `ToolRegistry`: 工具注册表
  - `match_tools_for_query()`: 匹配工具函数

### 2.3 集成示例
- **文件**: `lc_agent/agent_with_kb.py`
- **功能**: 展示如何将知识库检索集成到现有Agent中

## 三、实施步骤

### 步骤1: 安装依赖

```bash
# 安装向量数据库和嵌入模型
pip install faiss-cpu  # 或 faiss-gpu（如果有GPU）
pip install sentence-transformers
pip install langchain
```

### 步骤2: 初始化知识库

```python
from lc_agent.knowledge_base import init_sample_knowledge, get_kb_manager

# 初始化示例知识库数据
init_sample_knowledge()

# 或者手动添加知识
kb_manager = get_kb_manager()
namenode_kb = kb_manager.get_or_create_kb("NameNodeExpert")

# 添加知识文档
namenode_kb.add_texts(
    texts=[
        "NameNode无法启动的常见原因：1) 配置文件错误 2) 端口被占用 3) 磁盘空间不足",
        "NameNode启动失败时，检查hdfs-site.xml和core-site.xml配置是否正确",
    ],
    metadatas=[
        {"source": "Hadoop官方文档", "desc": "NameNode启动问题"},
        {"source": "故障案例", "desc": "配置检查"},
    ]
)
namenode_kb.save()
```

### 步骤3: 集成到现有Agent

修改 `agent.py` 中的 `create_agent_instance` 函数：

```python
from lc_agent.knowledge_base import search_diagnosis_knowledge
from lc_agent.tool_matcher import get_tool_registry

# 添加知识库检索工具
@tool("search_diagnosis_knowledge", description="从知识库检索诊断相关知识")
def search_diagnosis_knowledge_tool(query: str, expert_type: str = "all") -> str:
    return search_diagnosis_knowledge(query, expert_type)

def create_agent_instance(model_name: str = "qwen-8b"):
    llm = create_llm(model_name)
    
    # 原有工具
    tools = [
        get_cluster_logs,
        get_node_log,
        get_monitoring_metrics,
        website_search,
        hadoop_cluster_operation,
    ]
    
    # 添加知识库检索工具
    tools.append(search_diagnosis_knowledge_tool)
    
    # 注册工具到工具匹配器（可选）
    tool_registry = get_tool_registry()
    for tool_func in tools:
        tool_registry.register_tool(
            tool_name=tool_func.name,
            tool_func=tool_func,
            description=tool_func.description
        )
    
    # 更新系统提示词
    system_prompt = """你是HDFS集群问题诊断专家。

你可以使用以下工具：
1. search_diagnosis_knowledge: 从知识库检索历史故障案例和文档
2. get_cluster_logs: 获取集群日志
3. get_node_log: 获取指定节点日志
4. get_monitoring_metrics: 获取监控指标
5. website_search: 网络搜索
6. hadoop_cluster_operation: 集群操作

**诊断建议**：
- 遇到问题时，先使用 search_diagnosis_knowledge 检索相关知识
- 然后获取相关日志和监控指标
- 结合知识库知识和实际数据进行分析

请用专业、清晰的语言回答。"""
    
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt
    )
    
    return agent
```

### 步骤4: 构建知识库内容

#### 4.1 从历史故障案例构建

```python
# 读取历史诊断报告
import json
from lc_agent.knowledge_base import get_kb_manager

kb_manager = get_kb_manager()
history_kb = kb_manager.get_or_create_kb("HistoryCases")

# 假设有历史案例文件
with open("history_cases.json", "r", encoding="utf-8") as f:
    cases = json.load(f)

for case in cases:
    history_kb.add_texts(
        texts=[case["description"] + "\n解决方案: " + case["solution"]],
        metadatas=[{
            "source": "历史案例",
            "desc": case["title"],
            "date": case["date"]
        }]
    )

history_kb.save()
```

#### 4.2 从Hadoop文档构建

```python
# 从文档文件提取知识
from langchain.document_loaders import TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

kb_manager = get_kb_manager()
hadoop_kb = kb_manager.get_or_create_kb("HadoopDocs")

# 加载文档
loader = TextLoader("hadoop_troubleshooting.txt", encoding="utf-8")
documents = loader.load()

# 分割文档
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50
)
docs = text_splitter.split_documents(documents)

# 添加到知识库
hadoop_kb.add_documents(docs)
hadoop_kb.save()
```

## 四、使用示例

### 4.1 基本使用

```python
from lc_agent.agent_with_kb import create_agent_with_kb

# 创建Agent
agent = create_agent_with_kb()

# 使用Agent诊断问题
config = {"configurable": {"thread_id": "diagnosis_1"}}
result = agent.invoke(
    {"messages": [{"role": "user", "content": "NameNode无法启动，请诊断"}]},
    config=config
)

print(result['messages'][-1].content)
```

### 4.2 工具推荐

```python
from lc_agent.tool_matcher import match_tools_for_query

# 根据查询推荐工具
query = "NameNode无法启动，需要查看日志"
recommended_tools = match_tools_for_query(query, top_k=3)
print(f"推荐工具: {recommended_tools}")
# 输出: ['get_node_log', 'search_diagnosis_knowledge', 'get_cluster_logs']
```

## 五、高级功能

### 5.1 多智能体系统（可选）

如果需要实现多智能体协作，可以参考 `DB-GPT/multiagents/environments/dba.py`：

```python
# 创建多个专家Agent
experts = {
    "NameNodeExpert": create_expert_agent(
        name="NameNodeExpert",
        knowledge_base="NameNodeExpert",
        tools=[get_namenode_logs, search_diagnosis_knowledge, ...]
    ),
    "DataNodeExpert": create_expert_agent(...),
}

# 角色分配器
def assign_experts(alert_description: str) -> List[str]:
    # 使用LLM分析异常，选择专家
    selected_experts = llm.analyze_and_select_experts(alert_description)
    return selected_experts

# 并行诊断
async def parallel_diagnosis(experts: List[str], alert_info: dict):
    results = await asyncio.gather(*[
        experts[name].diagnose(alert_info) 
        for name in experts
    ])
    return results
```

### 5.2 工具嵌入向量匹配集成

在Agent中集成工具匹配，可以动态推荐工具：

```python
def create_agent_with_smart_tool_selection(model_name: str = "qwen-8b"):
    llm = create_llm(model_name)
    
    # 所有可用工具
    all_tools = [get_cluster_logs, get_node_log, ...]
    
    # 注册所有工具
    tool_registry = get_tool_registry()
    for tool_func in all_tools:
        tool_registry.register_tool(
            tool_name=tool_func.name,
            tool_func=tool_func,
            description=tool_func.description
        )
    
    # 创建Agent（可以动态选择工具）
    agent = create_agent(
        model=llm,
        tools=all_tools,  # 或者根据查询动态选择
        system_prompt=system_prompt
    )
    
    return agent
```

## 六、性能优化建议

### 6.1 知识库优化
- 使用合适的chunk_size（建议500-1000字符）
- 定期更新知识库内容
- 使用GPU加速嵌入计算（如果可用）

### 6.2 工具匹配优化
- 缓存工具嵌入向量（已实现）
- 批量处理多个查询
- 使用更快的嵌入模型（如all-MiniLM-L6-v2）

## 七、测试验证

### 7.1 测试知识库检索

```python
from lc_agent.knowledge_base import search_diagnosis_knowledge

# 测试搜索
result = search_diagnosis_knowledge(
    query="NameNode无法启动",
    expert_type="namenode",
    top_k=3
)
print(result)
```

### 7.2 测试工具匹配

```python
from lc_agent.tool_matcher import match_tools_for_query

# 测试工具匹配
recommended = match_tools_for_query(
    "查看NameNode日志",
    top_k=3
)
print(recommended)
```

## 八、常见问题

### Q1: 嵌入模型加载失败
**A**: 确保安装了sentence-transformers，或使用在线模型：
```python
pip install sentence-transformers
```

### Q2: FAISS安装失败
**A**: 使用CPU版本：
```bash
pip install faiss-cpu
```

### Q3: 知识库搜索返回空结果
**A**: 检查：
1. 知识库是否已初始化数据
2. score_threshold是否设置过高
3. 查询字符串是否与知识库内容相关

### Q4: 工具匹配不准确
**A**: 
1. 确保工具描述清晰准确
2. 调整threshold参数
3. 使用更好的嵌入模型

## 九、下一步计划

1. **收集历史故障案例**：整理历史诊断报告，构建案例库
2. **收集Hadoop文档**：从官方文档提取诊断知识
3. **优化嵌入模型**：根据实际效果调整模型参数
4. **实现多智能体系统**：如果需要更复杂的诊断流程
5. **性能测试**：测试大规模知识库的检索性能

## 十、参考资源

- DB-GPT知识库实现: `dbot/DB-GPT/server/knowledge_base/kb_doc_api.py`
- DB-GPT工具匹配: `dbot/DB-GPT/multiagents/tools/api_retrieval.py`
- DB-GPT多智能体: `dbot/DB-GPT/multiagents/environments/dba.py`
- LangChain文档: https://python.langchain.com/
- FAISS文档: https://github.com/facebookresearch/faiss

