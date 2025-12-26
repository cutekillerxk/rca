#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化日志读取器状态文件（Docker版本）
读取 Docker 容器中的日志文件，将 last_positions 设置为文件大小（最新位置），
将 last_files 设置为对应的日志文件名
"""

import os
import json
import subprocess
from datetime import datetime
import sys

# 添加 lc_agent 目录到路径，以便导入 DockerLogReader
lc_agent_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lc_agent')
if lc_agent_path not in sys.path:
    sys.path.insert(0, lc_agent_path)

try:
    from agent import DockerLogReader, LOG_FILES_CONFIG
except ImportError as e:
    print(f"错误：无法导入 agent 模块: {e}")
    print(f"请确保 lc_agent/agent.py 文件存在且可访问")
    sys.exit(1)

# 日志状态文件路径（与 agent.py 保持一致）
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
STATE_FILE = os.path.join(LOG_DIR, "log_reader_state.json")


def get_docker_log_file_info(docker_reader: DockerLogReader, node_pattern: str):
    """
    获取 Docker 容器中日志文件信息
    
    Args:
        docker_reader: DockerLogReader 实例
        node_pattern: 节点匹配模式（如 'namenode', 'datanode'）
    
    Returns:
        (文件大小, 文件名) 或 (None, None) 如果未找到
    """
    try:
        # 检查容器是否运行
        check_result = subprocess.run(
            f'docker ps --format "{{{{.Names}}}}" | findstr /C:"{docker_reader.container}"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if check_result.returncode != 0 or docker_reader.container not in check_result.stdout:
            print(f"  [{docker_reader.container}] 容器未运行，无法获取日志文件信息")
            return None, None
        
        # 列出日志文件
        log_files = docker_reader.list_log_files(node_pattern)
        if not log_files:
            print(f"  [{docker_reader.container}] 未找到匹配的日志文件（模式: {node_pattern}）")
            return None, None
        
        # 获取文件修改时间，找到最新的文件
        log_files_with_time = []
        for f in log_files:
            mtime = docker_reader.get_file_mtime(f)
            if mtime:
                log_files_with_time.append((f, mtime))
        
        if not log_files_with_time:
            print(f"  [{docker_reader.container}] 无法读取日志文件的时间信息")
            return None, None
        
        # 按修改时间排序，获取最新的日志文件
        log_files_with_time.sort(key=lambda x: x[1], reverse=True)
        latest_file = log_files_with_time[0][0]
        
        # 获取文件大小（通过 docker exec 执行 stat 命令）
        try:
            if not os.path.isabs(latest_file):
                file_path = os.path.join(docker_reader.log_path, latest_file)
            else:
                file_path = latest_file
            
            # 使用 stat 命令获取文件大小
            result = subprocess.run(
                f'docker exec {docker_reader.container} sh -c "stat -c %s {file_path} 2>&1"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                try:
                    file_size = int(result.stdout.strip())
                    print(f"  [{docker_reader.container}] 找到日志文件: {latest_file}, 大小: {file_size} 字节")
                    return file_size, latest_file
                except ValueError:
                    print(f"  [{docker_reader.container}] 无法解析文件大小: {result.stdout.strip()}")
                    return None, None
            else:
                print(f"  [{docker_reader.container}] 无法获取文件大小: {result.stderr}")
                return None, None
        except Exception as e:
            print(f"  [{docker_reader.container}] 无法获取文件大小: {e}")
            return None, None
        
    except Exception as e:
        print(f"  [{docker_reader.container}] 错误: {e}")
        return None, None


def main():
    """主函数：初始化日志读取器状态"""
    print("=" * 60)
    print("初始化日志读取器状态文件（Docker版本 - 5个容器）")
    print("=" * 60)
    
    num_log_files = len(LOG_FILES_CONFIG)  # 5个日志文件
    last_positions = [0] * num_log_files
    last_files = [None] * num_log_files
    
    # 初始化Docker读取器（按container分组）
    docker_readers = {}
    for log_config in LOG_FILES_CONFIG:
        if log_config["type"] == "docker":
            container = log_config.get("container")
            if container and container not in docker_readers:
                docker_readers[container] = DockerLogReader(
                    container=container,
                    log_path=log_config["log_path"]
                )
    
    # 遍历5个日志文件配置
    for i, log_config in enumerate(LOG_FILES_CONFIG):
        log_name = log_config["name"]
        display_name = log_config["display_name"]
        node_pattern = log_config.get("node_pattern")
        
        print(f"\n[{i+1}/5] 处理 {display_name}...")
        
        if log_config["type"] == "docker":
            # Docker 容器日志文件
            container = log_config.get("container")
            docker_reader = docker_readers.get(container) if container else None
            
            if not docker_reader:
                print(f"  [{display_name}] ✗ Docker 读取器未初始化")
                continue
            
            file_size, file_name = get_docker_log_file_info(docker_reader, node_pattern)
            if file_size is not None and file_name is not None:
                last_positions[i] = file_size
                last_files[i] = file_name
                print(f"  [{display_name}] ✓ 设置位置: {file_size}, 文件: {file_name}")
            else:
                print(f"  [{display_name}] ✗ 无法获取日志文件信息，保持默认值 0")
        else:
            # 其他类型（local/ssh）暂不支持，跳过
            print(f"  [{display_name}] ⚠ 跳过非Docker类型: {log_config['type']}")
    
    # 保存状态到文件
    print(f"\n保存状态到文件...")
    try:
        # 确保日志目录存在
        os.makedirs(LOG_DIR, exist_ok=True)
        
        state = {
            'last_positions': last_positions,
            'last_files': last_files,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'init_by': 'init_log_reader_state.py (Docker版本)'
        }
        
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ 状态已保存到: {STATE_FILE}")
        print(f"\n状态内容:")
        print(f"  last_positions: {last_positions}")
        print(f"  last_files: {last_files}")
        print(f"  last_update: {state['last_update']}")
        
    except Exception as e:
        print(f"  ✗ 保存状态文件失败: {e}")
        return 1
    
    print("\n" + "=" * 60)
    print("初始化完成！")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    exit(main())
