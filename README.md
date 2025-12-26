# RCA - HDFS集群故障检测与自动处理系统

## 项目简介

RCA（Root Cause Analysis）是一个基于AI的HDFS集群故障检测与诊断系统，集成了知识库检索、自然语言操作执行等先进功能。

## 主要功能

### 1. 集群监控与诊断
- 实时监控HDFS集群状态
- 日志自动读取和分析
- JMX指标采集
- 智能问题诊断

### 2. 知识库检索（RAG）
- 历史故障案例检索
- Hadoop文档知识库
- 语义相似度搜索
- 多知识库管理

### 3. 自然语言操作执行
- 理解自然语言指令
- 自动执行Hadoop集群操作
- 智能工具选择
- 安全操作确认

## 技术栈

- **LangChain 1.0.7**: Agent框架
- **FAISS**: 向量数据库
- **sentence-transformers**: 文本嵌入
- **vLLM**: 本地LLM部署
- **Gradio**: Web界面

## 快速开始

### 安装依赖

```bash
pip install langchain==1.0.7
pip install langchain-community
pip install faiss-cpu
pip install sentence-transformers
```

### 运行

```bash
cd lc_agent
python gradio_demo.py
```

## 项目结构

```
rca/
├── lc_agent/              # 核心Agent实现
│   ├── agent.py           # 主Agent
│   ├── knowledge_base.py  # 知识库检索
│   ├── tool_matcher.py   # 工具匹配
│   ├── natural_language_executor.py  # 自然语言执行
│   └── gradio_demo.py    # Web界面
├── test/                  # 测试文件
└── docs/                  # 文档
```

## 文档

- [快速开始-知识库集成.md](快速开始-知识库集成.md)
- [自然语言操作执行-使用指南.md](自然语言操作执行-使用指南.md)
- [功能记录.md](功能记录.md)

## 许可证

MIT License

