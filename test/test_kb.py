from lc_agent.knowledge_base import init_sample_knowledge, search_diagnosis_knowledge

# 初始化示例知识库
init_sample_knowledge()

# 测试搜索
result = search_diagnosis_knowledge(
    query="NameNode无法启动",
    expert_type="namenode",
    top_k=3
)
print(result)