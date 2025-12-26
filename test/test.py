from pyexpat import model
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from langgraph.checkpoint.memory import InMemorySaver
from langchain.agents.middleware import HumanInTheLoopMiddleware
import os

# 加载 .env 文件
load_dotenv()

# 如果需要使用 Tavily 搜索，取消下面的注释并设置 TAVILY_API_KEY
from langchain_tavily import TavilySearch
website_search = TavilySearch(max_results=2, tavily_api_key=os.getenv("TAVILY_API_KEY"))

# 从环境变量读取第三方 API 配置
API_KEY = os.getenv("API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL", "https://www.dmxapi.com/v1")  # 第三方 API 地址
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")  # 第三方 API 支持的模型名称

checkpointer = InMemorySaver()
# 创建连接到本地vLLM的 LLM 对象
llm = ChatOpenAI(
    base_url="http://10.157.197.76:8001/v1",      # 第三方 API 的地址
    api_key="not-needed",            # 第三方 API 的密钥
    model="/media/hnu/LLM/hnu/LLM/Qwen3-8B",       # 第三方 API 支持的模型名称
    temperature=0,              # 温度参数（0-1，0 更确定性）
    max_tokens=4096,            # 最大生成 token 数
    timeout=300,                # 超时时间（秒）
    max_retries=2,              # 最大重试次数
    # 注意：不要在这里设置 tool_choice
    # create_agent 会自动处理工具调用
)
print("1")
@tool("query_order_status",description="根据订单号查询订单状态")
def query_order_status(order_id:str)->str:
    if order_id == "1024":
        return "订单状态为已发货"
    else:
        return "未找到订单"
print("2")
@tool("refund_policy", description="根据关键词查询退款政策")
def refund_policy(keyword: str) -> str:
    """根据关键词查询退款政策"""
    print(f"keyword: {keyword}")
    return "退款政策为：15天无理由退款"
print("3")
# 定义工具列表
# 注意：LangChain 1.0.7 中，create_agent() 不接受预绑定工具的模型
# 应该直接传递原始模型和工具列表
tools = [query_order_status, refund_policy, website_search]

agent = create_agent(
    model=llm,  # 直接使用 llm，不要 bind_tools
    tools=tools,  
    system_prompt="你是一个智能助手，可以根据用户的问题来调用工具解决问题。",
)
print("4")
config = {
    "configurable": {
        "thread_id": "1"
    }
}
print("5")
result = agent.invoke(
    {"messages":[{"role":"user","content":"你有哪些工具可以调用，它们的功能是什么？"}]},
    config=config  # 传入 config 参数
    )
print("6")
print(result['messages'][-1].content)