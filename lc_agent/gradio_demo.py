#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HDFS 集群监控 Agent - Gradio Web 界面版本（LangChain + vLLM）
基于 LangChain 和 vLLM 实现自主工具调用的 Agent

使用方法：

       python lc_agent/agentt_gradio.py
    
     在浏览器中打开显示的 URL（通常是 http://127.0.0.1:7860）
"""

import gradio as gr
import sys
import os

# 添加父目录到路径，以便导入现有模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入 LangChain Agent
from lc_agent.agent import create_agent_instance, export_to_word, export_to_pdf
from lc_agent.monitor_collector import collect_all_metrics, format_metrics_for_display

# 全局 Agent 实例和当前模型
agent = None
current_model = "qwen-8b"  # 当前使用的模型
# 存储最后一次的Agent回复（用于文档导出）
last_agent_response = ""

# 模型名称映射（前端显示名称 -> 内部模型名称）
MODEL_NAME_MAP = {
    "Qwen-8B (vLLM)": "qwen-8b",
    "GPT-4o (OpenAI)": "gpt-4o",
    "DeepSeek-R1 (DeepSeek)": "deepseek-r1"
}


def init_agent(model_name: str = "qwen-8b"):
    """
    初始化 LangChain Agent（支持模型切换）
    
    Args:
        model_name: 模型名称，可选值：qwen-8b, gpt-4o, deepseek-r1
    """
    global agent, current_model
    
    model_display_name = {v: k for k, v in MODEL_NAME_MAP.items()}.get(model_name, model_name)
    
    # 如果模型改变或Agent未初始化，重新创建Agent
    if agent is None:
        print(f"[INFO] Agent未初始化，正在创建新Agent（模型: {model_display_name}）...")
        try:
            agent = create_agent_instance(model_name)
            if agent is None:
                raise RuntimeError("LangChain Agent 初始化失败")
            current_model = model_name
            print(f"[INFO] ✅ LangChain Agent 初始化完成（模型: {model_display_name}）")
            print(f"[DEBUG] 当前模型状态: current_model = '{current_model}'")
        except Exception as e:
            error_msg = f"LangChain Agent 初始化失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print("[提示] 请检查：")
            if model_name == "qwen-8b":
                print("[提示]   1. vLLM 服务是否已启动")
                print("[提示]   2. 服务地址是否正确")
                print("[提示]   3. 模型路径是否正确")
            else:
                print(f"[提示]   1. 第三方API配置是否正确（API_BASE_URL, API_KEY）")
                print(f"[提示]   2. 模型名称是否正确")
                print(f"[提示]   3. 网络连接是否正常")
            raise RuntimeError(error_msg)
    elif current_model != model_name:
        print(f"[INFO] 检测到模型切换请求:")
        print(f"[INFO]   当前模型: {current_model} ({MODEL_NAME_MAP.get(current_model, current_model)})")
        print(f"[INFO]   目标模型: {model_name} ({model_display_name})")
        print(f"[INFO] 正在重新创建Agent...")
        try:
            agent = create_agent_instance(model_name)
            if agent is None:
                raise RuntimeError("LangChain Agent 初始化失败")
            old_model = current_model
            current_model = model_name
            print(f"[INFO] ✅ 模型切换成功:")
            print(f"[INFO]   从: {old_model} ({MODEL_NAME_MAP.get(old_model, old_model)})")
            print(f"[INFO]   到: {current_model} ({model_display_name})")
            print(f"[DEBUG] 当前模型状态: current_model = '{current_model}'")
        except Exception as e:
            error_msg = f"模型切换失败: {str(e)}"
            print(f"[ERROR] {error_msg}")
            print(f"[ERROR] 保持使用原模型: {current_model}")
            print("[提示] 请检查：")
            if model_name == "qwen-8b":
                print("[提示]   1. vLLM 服务是否已启动")
                print("[提示]   2. 服务地址是否正确")
                print("[提示]   3. 模型路径是否正确")
            else:
                print(f"[提示]   1. 第三方API配置是否正确（API_BASE_URL, API_KEY）")
                print(f"[提示]   2. 模型名称是否正确")
                print(f"[提示]   3. 网络连接是否正常")
            raise RuntimeError(error_msg)
    else:
        print(f"[DEBUG] 使用现有Agent（模型: {model_display_name}，current_model = '{current_model}'）")
    
    return agent


def update_monitoring_display():
    """更新监控数据显示"""
    try:
        metrics_data = collect_all_metrics()
        html_content = format_metrics_for_display(metrics_data)
        return html_content
    except Exception as e:
        error_html = f"<div style='color: red; padding: 20px;'>❌ 获取监控数据失败: {str(e)}</div>"
        return error_html


def create_gradio_interface():
    """创建 Gradio 界面"""
    
    # 自定义 CSS 样式（可选，让界面更美观）
    custom_css = """
    .gradio-container {
        font-family: 'Microsoft YaHei', 'PingFang SC', Arial, sans-serif;
    }
    .chat-message {
        padding: 10px;
    }
    """
    
    # 使用 Blocks 创建更灵活的布局
    with gr.Blocks(title="HDFS 集群监控 Agent (LangChain + vLLM)", theme=gr.themes.Soft(), css=custom_css) as demo:
        # 使用两列布局：左侧（标题+监控），右侧（聊天）
        with gr.Row():
            # 左侧列：标题+功能说明 + 监控数据
            with gr.Column(scale=1, min_width=300):
                # 标题和功能说明（放在左侧列内部）
                gr.Markdown("""
                #  HDFS 集群监控智能助手
                
                **功能说明**：
                - 📊 **实时监控**：显示集群关键指标
                - 💬 **智能对话**：可以回答关于 HDFS 集群的问题
                - 🔍 **自主工具调用**：智能理解用户意图，自主调用工具分析集群日志
                - 🤖 **多模型支持**：支持切换 Qwen-8B、GPT-4o、DeepSeek-R1
                
                **可用工具**：
                - 检查集群状态
                - 获取监控指标
                - 分析指定节点日志
                """)
                
                gr.Markdown("### 📊 集群监控指标")
                monitoring_html = gr.HTML(
                    value="<div style='padding: 20px; text-align: center;'>正在加载监控数据...</div>",
                    label="监控数据",
                    elem_id="monitoring-display"
                )
                
                # 刷新按钮
                refresh_btn = gr.Button("🔄 手动刷新", variant="primary", size="sm")
                
                def refresh_monitoring():
                    """手动刷新监控数据""" 
                    return update_monitoring_display()
                
                refresh_btn.click(
                    fn=refresh_monitoring,
                    inputs=None,
                    outputs=monitoring_html
                )
                
                # 导出按钮（两个按钮同行，宽度加起来等于刷新按钮）
                with gr.Row():
                    export_word_btn = gr.Button("📄 导出Word", variant="secondary", size="sm", scale=1)
                    export_pdf_btn = gr.Button("📄 导出PDF", variant="secondary", size="sm", scale=1)
                
                # 导出状态（放在按钮下方）
                export_status = gr.Textbox(
                    label="导出状态",
                    visible=True,
                    interactive=False,
                    lines=2
                )
                
                # 文件下载组件（用于触发浏览器下载）
                # 设置为可见但样式最小化，用户可以看到下载链接
                export_file = gr.File(
                    label="下载文件",
                    visible=True,
                    interactive=False,
                    height=50  # 设置较小的高度
                )
                
                # 添加自定义JavaScript，实现自动下载
                download_js = """
                function(file) {
                    if (file) {
                        // 创建隐藏的下载链接并自动点击
                        const link = document.createElement('a');
                        link.href = file;
                        link.download = file.split('/').pop() || 'download';
                        link.style.display = 'none';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    }
                    return file;
                }
                """
            
            # 右侧列：聊天对话（更多空间）
            with gr.Column(scale=2, min_width=400):
                gr.Markdown("### 💬 智能对话（自主工具调用）")
                
                # 模型选择下拉框
                model_selector = gr.Dropdown(
                    choices=list(MODEL_NAME_MAP.keys()),
                    value="Qwen-8B (vLLM)",
                    label="选择大模型",
                    info="切换不同的大模型进行对话",
                    interactive=True
                )
                
                # 使用新格式（messages），兼容 Gradio 4.0+
                # 注意：如果使用 type='messages'，需要修改消息格式处理
                # 为了兼容性，暂时保持 tuples 格式，但添加 type 参数以消除警告
                chatbot = gr.Chatbot(
                    label="对话历史",
                    height=500,
                    show_copy_button=True
                    # 注意：保持tuples格式以兼容现有代码，Gradio警告可以忽略
                )
                msg = gr.Textbox(
                    label="输入消息",
                    placeholder="输入您的问题，例如：查看集群状态、检查 s2 节点、获取监控指标、HDFS 是什么？",
                    lines=2
                )
                
                with gr.Row():
                    submit_btn = gr.Button("📤 发送", variant="primary")
                    clear_btn = gr.Button("🗑️ 清空", variant="secondary")
                
                # 示例问题（展示自主工具调用能力）
                gr.Examples(
                    examples=[
                        "关闭节点datanode1",
                        "启动节点datanode1",
                        "查看集群状态",
                        "关闭整个hadoop集群",
                        "启动整个hadoop集群",
                        "NameNode 的作用是什么？",
                    ],
                    inputs=msg
                )
        
        # 模型切换功能
        def switch_model(selected_model, chat_history):
            """切换模型并清空对话历史"""
            global agent, current_model
            
            model_name = MODEL_NAME_MAP.get(selected_model, "qwen-8b")
            
            print(f"[DEBUG] ========== 模型切换请求 ==========")
            print(f"[DEBUG] 用户选择: {selected_model}")
            print(f"[DEBUG] 映射到内部模型名: {model_name}")
            print(f"[DEBUG] 当前模型: {current_model}")
            
            if current_model != model_name:
                print(f"[INFO] 🔄 开始切换模型: {current_model} -> {model_name}")
                try:
                    # 重置 Agent，强制重新创建
                    print(f"[DEBUG] 重置Agent实例（agent = None）")
                    agent = None
                    # 尝试初始化新模型（验证配置是否正确）
                    print(f"[DEBUG] 调用 init_agent('{model_name}') 初始化新模型...")
                    init_agent(model_name)
                    print(f"[DEBUG] ✅ 模型切换完成，清空对话历史")
                    # 清空对话历史
                    return []
                except Exception as e:
                    error_msg = f"❌ 切换模型失败: {str(e)}\n请检查 .env 文件中的 API_BASE_URL 和 API_KEY 配置"
                    print(f"[ERROR] {error_msg}")
                    print(f"[ERROR] 模型切换失败，保持使用原模型: {current_model}")
                    # 保持当前对话历史，在对话中显示错误消息
                    if chat_history:
                        chat_history.append(["", error_msg])
                    else:
                        chat_history = [["", error_msg]]
                    return chat_history
            else:
                print(f"[DEBUG] 模型未改变，无需切换（当前: {current_model}）")
                return chat_history
        
        # 绑定模型切换事件
        model_selector.change(
            fn=switch_model,
            inputs=[model_selector, chatbot],
            outputs=[chatbot]  # 只更新对话历史
        )
        
        # 聊天功能（使用兼容的 tuples 格式）
        def respond(message, chat_history, selected_model):
            """处理用户消息"""
            global last_agent_response
            
            if not message.strip():
                return chat_history, ""
            
            # 第一步：立即显示用户消息，并显示"正在处理..."提示
            chat_history.append([message, "⏳ 正在处理中，请稍候..."])
            yield chat_history, ""  # 立即返回，让界面显示用户消息和处理提示
            
            # 第二步：获取 Agent 回复（此时用户消息和处理提示已经显示）
            try:
                # 根据选择的模型获取或创建 Agent
                model_name = MODEL_NAME_MAP.get(selected_model, "qwen-8b")
                print(f"[DEBUG] ========== 处理用户消息 ==========")
                print(f"[DEBUG] 用户选择的模型: {selected_model} -> {model_name}")
                print(f"[DEBUG] 调用 init_agent('{model_name}') 获取Agent...")
                current_agent = init_agent(model_name)
                print(f"[DEBUG] ✅ Agent获取成功，开始处理消息...")
                
                # 使用新的invoke方式调用Agent
                config = {"configurable": {"thread_id": "gradio_chat"}}
                result = current_agent.invoke(
                    {"messages": [{"role": "user", "content": message}]},
                    config=config
                )
                
                # 提取回复内容
                # 需要找到最后一条AI消息（不是工具调用消息）
                response = ""
                
                # 添加调试信息
                if "messages" in result:
                    for i, msg in enumerate(result["messages"]):
                        msg_type = None
                        if hasattr(msg, "type"):
                            msg_type = msg.type
                        elif isinstance(msg, dict):
                            msg_type = msg.get("type")
                
                if "messages" in result and len(result["messages"]) > 0:
                    # 从后往前查找最后一条AI消息
                    for msg in reversed(result["messages"]):
                        # 检查消息类型
                        msg_type = None
                        msg_content = None
                        
                        if hasattr(msg, "type"):
                            msg_type = msg.type
                            msg_content = getattr(msg, "content", None)
                        elif isinstance(msg, dict):
                            msg_type = msg.get("type")
                            msg_content = msg.get("content")
                        else:
                            # 尝试转换为字符串
                            msg_content = str(msg)
                        
                        # 跳过工具调用消息和工具返回消息
                        if msg_type in ["tool", "tool_call", "ToolMessage"]:
                            continue
                        
                        # 如果是AI消息且有内容，使用它
                        if msg_type in ["ai", "AIMessage"] or (msg_type is None and msg_content):
                            if msg_content:
                                response = msg_content if isinstance(msg_content, str) else str(msg_content)
                                break
                    
                    # 如果没找到，尝试使用最后一条非工具消息
                    if not response:
                        for msg in reversed(result["messages"]):
                            msg_type = None
                            if hasattr(msg, "type"):
                                msg_type = msg.type
                            elif isinstance(msg, dict):
                                msg_type = msg.get("type")
                            
                            # 跳过工具相关消息
                            if msg_type in ["tool", "tool_call", "ToolMessage"]:
                                continue
                            
                            # 尝试提取内容
                            if hasattr(msg, "content"):
                                response = msg.content if isinstance(msg.content, str) else str(msg.content)
                            elif isinstance(msg, dict):
                                response = msg.get("content", str(msg))
                            else:
                                response = str(msg)
                            
                            if response:
                                break
                    
                    # 如果还是没找到，使用最后一条消息（即使可能是工具消息）
                    if not response and len(result["messages"]) > 0:
                        last_msg = result["messages"][-1]
                        if hasattr(last_msg, "content"):
                            response = last_msg.content
                        elif isinstance(last_msg, dict):
                            response = last_msg.get("content", str(last_msg))
                        else:
                            response = str(last_msg)
                else:
                    response = str(result)
                
                # 如果响应为空或只包含工具调用格式，说明可能有问题
                if not response or (isinstance(response, str) and response.strip().startswith("{") and "name" in response and "arguments" in response):
                    error_msg = "⚠️ Agent返回了工具调用格式，但未生成最终回复。可能原因：\n1. Agent仍在处理中（需要多次思考）\n2. vLLM配置问题\n3. 模型输出格式错误"
                    print(f"[ERROR] {error_msg}")
                    response = error_msg
                
                
                # 确保response是字符串
                if not isinstance(response, str):
                    response = str(response)
                
                # 清理vLLM推理标记（如<think>、<think>等）
                import re
                # 移除常见的推理标记
                response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
                response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
                response = re.sub(r'<reasoning>.*?</reasoning>', '', response, flags=re.DOTALL)
                # 移除其他可能的XML标签（但保留内容）
                response = re.sub(r'<[^>]+>', '', response)
                
                # 清理多余的空白字符
                response = response.strip()
                
                # 检查响应是否为空
                if not response or not response.strip():
                    response = "⚠️ Agent返回了空响应，请检查日志。"
                    print("[ERROR] Agent返回了空响应")
                else:
                    print(f"[DEBUG] 清理后响应长度: {len(response)}")
                

                last_agent_response = response  # 保存最后一次回复
                
                # 确保chat_history格式正确
                if len(chat_history) > 0:
                    # 更新最后一条消息的AI回复部分
                    if isinstance(chat_history[-1], list) and len(chat_history[-1]) >= 2:
                        chat_history[-1][1] = response
                    elif isinstance(chat_history[-1], tuple) and len(chat_history[-1]) >= 2:
                        # 如果是元组，需要转换为列表
                        chat_history[-1] = [chat_history[-1][0], response]
                    else:
                        # 如果格式不对，重新设置
                        chat_history[-1] = [message, response]
                    
                    print(f"[DEBUG] 更新后chat_history[-1]: {chat_history[-1][0][:50] if len(chat_history[-1][0]) > 50 else chat_history[-1][0]}... -> {chat_history[-1][1][:50] if len(chat_history[-1][1]) > 50 else chat_history[-1][1]}...")
                else:
                    print("[ERROR] chat_history为空，无法更新")
                    chat_history.append([message, response])
                
            except Exception as e:
                error_msg = f"❌ 发生错误: {str(e)}"
                last_agent_response = error_msg
                print(f"[ERROR] {error_msg}")
                import traceback
                traceback.print_exc()
                
                # 确保错误信息也能显示
                if len(chat_history) > 0:
                    if isinstance(chat_history[-1], list) and len(chat_history[-1]) >= 2:
                        chat_history[-1][1] = error_msg
                    else:
                        chat_history[-1] = [message, error_msg]
                else:
                    chat_history.append([message, error_msg])
            
            # 第三步：返回完整的对话历史（包含 AI 回复）

            yield chat_history, ""
        
        # 文档导出功能
        def export_document(format_type: str):
            """导出文档并返回文件路径（用于浏览器下载）"""
            global last_agent_response
            
            if not last_agent_response or last_agent_response.startswith("❌"):
                return None, "❌ 没有可导出的内容，请先与Agent对话获取分析结果"
            
            try:
                from datetime import datetime
                import os
                
                # 使用当前工作目录（Gradio启动时的工作目录），确保Gradio可以访问
                # 使用os.getcwd()获取Gradio的实际工作目录
                current_work_dir = os.getcwd()
                # 在当前工作目录下创建exports子目录用于临时导出文件
                exports_dir = os.path.join(current_work_dir, "exports")
                os.makedirs(exports_dir, exist_ok=True)
                
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                
                if format_type == "word":
                    filename = f"cluster_report_{timestamp}.docx"
                    output_path = os.path.join(exports_dir, filename)
                    export_to_word(last_agent_response, output_path)
                    status_msg = f"✅ Word文档已生成，请点击下方下载链接"
                    # 返回相对路径（相对于工作目录），Gradio更容易处理
                    abs_path = os.path.abspath(output_path)
                    rel_path = os.path.relpath(output_path, current_work_dir)
                    print(f"[DEBUG] 导出Word文件 - 绝对路径: {abs_path}")
                    print(f"[DEBUG] 导出Word文件 - 相对路径: {rel_path}")
                    print(f"[DEBUG] 文件是否存在: {os.path.exists(abs_path)}")
                    print(f"[DEBUG] 文件大小: {os.path.getsize(abs_path) if os.path.exists(abs_path) else 'N/A'} bytes")
                    # 使用相对路径，Gradio可以更好地处理
                    return rel_path, status_msg
                else:  # pdf
                    filename = f"cluster_report_{timestamp}.pdf"
                    output_path = os.path.join(exports_dir, filename)
                    export_to_pdf(last_agent_response, output_path)
                    status_msg = f"✅ PDF文档已生成，请点击下方下载链接"
                    # 返回相对路径（相对于工作目录），Gradio更容易处理
                    abs_path = os.path.abspath(output_path)
                    rel_path = os.path.relpath(output_path, current_work_dir)
                    print(f"[DEBUG] 导出PDF文件 - 绝对路径: {abs_path}")
                    print(f"[DEBUG] 导出PDF文件 - 相对路径: {rel_path}")
                    print(f"[DEBUG] 文件是否存在: {os.path.exists(abs_path)}")
                    print(f"[DEBUG] 文件大小: {os.path.getsize(abs_path) if os.path.exists(abs_path) else 'N/A'} bytes")
                    # 使用相对路径，Gradio可以更好地处理
                    return rel_path, status_msg
            except ImportError as e:
                if "docx" in str(e) or "python-docx" in str(e):
                    return None, "❌ 导出Word失败: 需要安装 python-docx (pip install python-docx)"
                elif "reportlab" in str(e):
                    return None, "❌ 导出PDF失败: 需要安装 reportlab (pip install reportlab)"
                else:
                    return None, f"❌ 导出失败: {str(e)}"
            except Exception as e:
                return None, f"❌ 导出失败: {str(e)}"
        
        msg.submit(respond, [msg, chatbot, model_selector], [chatbot, msg])
        submit_btn.click(respond, [msg, chatbot, model_selector], [chatbot, msg])
        clear_btn.click(lambda: ([], ""), None, [chatbot, msg])
        
        # 绑定导出按钮（同时更新文件下载和状态消息）
        # 使用JavaScript实现自动下载
        export_word_btn.click(
            fn=lambda: export_document("word"),
            inputs=None,
            outputs=[export_file, export_status],
            js="""
            (file, status) => {
                if (file) {
                    setTimeout(() => {
                        // 查找文件下载链接并自动点击
                        const fileLinks = document.querySelectorAll('a[href*="cluster_report"]');
                        if (fileLinks.length > 0) {
                            fileLinks[fileLinks.length - 1].click();
                        } else {
                            // 备用方案：直接创建下载链接
                            const link = document.createElement('a');
                            link.href = file;
                            link.download = file.split('/').pop() || 'cluster_report.docx';
                            link.style.display = 'none';
                            document.body.appendChild(link);
                            link.click();
                            setTimeout(() => document.body.removeChild(link), 100);
                        }
                    }, 500);
                }
                return [file, status];
            }
            """
        )
        export_pdf_btn.click(
            fn=lambda: export_document("pdf"),
            inputs=None,
            outputs=[export_file, export_status],
            js="""
            (file, status) => {
                if (file) {
                    setTimeout(() => {
                        // 查找文件下载链接并自动点击
                        const fileLinks = document.querySelectorAll('a[href*="cluster_report"]');
                        if (fileLinks.length > 0) {
                            fileLinks[fileLinks.length - 1].click();
                        } else {
                            // 备用方案：直接创建下载链接
                            const link = document.createElement('a');
                            link.href = file;
                            link.download = file.split('/').pop() || 'cluster_report.pdf';
                            link.style.display = 'none';
                            document.body.appendChild(link);
                            link.click();
                            setTimeout(() => document.body.removeChild(link), 100);
                        }
                    }, 500);
                }
                return [file, status];
            }
            """
        )
        
        # 页面加载时立即更新一次
        demo.load(
            fn=update_monitoring_display,
            inputs=None,
            outputs=monitoring_html
        )
        
        # 注意：某些 Gradio 版本不支持定时自动更新
        # 如果需要定时更新，可以：
        # 1. 使用手动刷新按钮（已实现）
        # 2. 或者升级 Gradio 到支持定时更新的版本
        # 3. 或者使用 JavaScript 在前端实现定时刷新
    
    return demo


def main():
    """主函数"""
    print("=" * 60)
    print("HDFS 集群监控 Agent - Gradio Web 界面 (LangChain)")
    print("=" * 60)
    print()
    print("[INFO] 使用 LangChain Agent（自主工具调用）")
    print("[INFO] 模式: vLLM（Qwen3-8B）")
    print()
    print("[提示] vLLM 配置：")
    print("[提示]   - 服务地址: http://localhost:8000/v1")
    print("[提示]   - 模型路径: /media/hnu/LLM/hnu/LLM/Qwen3-8B")
    print()
    print("[提示] 请确保 vLLM 服务已启动")
    print("-" * 60)
    print()
    print("[INFO] 正在预加载 Agent...")
    print("[提示] 这可能需要一些时间，请耐心等待...")
    print("-" * 60)
    
    # 在启动时预加载 Agent（使用默认模型 qwen-8b）
    try:
        init_agent("qwen-8b")
        print("[INFO] Agent 预加载完成（默认模型: Qwen-8B）！")
    except Exception as e:
        print(f"[ERROR] Agent 预加载失败: {e}")
        print()
        print("[错误] 无法启动 Agent，请检查：")
        print("  1. vLLM 服务是否已启动")
        print("  2. 服务地址是否正确")
        print("  3. 模型路径是否正确")
        print()
        print("[提示] 可以运行以下命令检查 vLLM 服务：")
        print("  curl http://10.157.197.76:8001/health")
        print()
        print("[提示] 如果 vLLM 服务不可用，可以在界面中切换到其他模型（GPT-4o 或 DeepSeek-R1）")
        print()
        # 不退出，允许用户切换到其他模型
        # sys.exit(1)
    
    print()
    print("[INFO] 正在启动 Gradio 界面...")
    print("[INFO] 界面启动后，请在浏览器中打开显示的 URL")
    print("-" * 60)
    print()
    
    try:
        # 创建界面
        demo = create_gradio_interface()
        
        # 启动界面
        # share=False: 不创建公共链接（仅本地访问）
        # server_name="0.0.0.0": 允许局域网访问（可选）
        # server_port=7860: 指定端口（可选）
        # 获取exports目录的绝对路径，添加到allowed_paths
        import os
        current_work_dir = os.getcwd()
        exports_dir = os.path.join(current_work_dir, "exports")
        exports_dir_abs = os.path.abspath(exports_dir)
        os.makedirs(exports_dir_abs, exist_ok=True)
        
        print(f"[DEBUG] Gradio工作目录: {current_work_dir}")
        print(f"[DEBUG] Exports目录: {exports_dir_abs}")
        
        demo.launch(
            share=False,  # 设置为 True 可以创建公共链接
            server_name="127.0.0.1",  # 改为127.0.0.1避免网络问题
            server_port=7860,  # 端口号
            show_error=True,  # 显示错误信息
            allowed_paths=[exports_dir_abs, current_work_dir]  # 允许访问exports目录和工作目录
        )
    except KeyboardInterrupt:
        print("\n[INFO] 收到中断信号，正在关闭...")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERROR] 启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

