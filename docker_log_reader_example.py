#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Docker 日志读取器示例代码
这是 Docker 版本的完整实现示例，可以直接集成到 agent.py 中
"""

import os
import logging
import subprocess
from typing import List, Tuple, Optional

# ==================== 配置部分 ====================

# Docker 容器配置
DOCKER_CONFIG = {
    "namenode": {
        "container": "namenode",
        "log_path": "/opt/hadoop-3.2.1/logs",
    },
    "datanode1": {
        "container": "datanode1",
        "log_path": "/opt/hadoop-3.2.1/logs",
    },
    "datanode2": {
        "container": "datanode2",
        "log_path": "/opt/hadoop-3.2.1/logs",
    },
    "datanode3": {
        "container": "datanode3",
        "log_path": "/opt/hadoop-3.2.1/logs",
    },
    "checkpointnode": {
        "container": "checkpointnode",
        "log_path": "/opt/hadoop-3.2.1/logs",
    }
}

# ==================== Docker 日志读取器类 ====================

class DockerLogReader:
    """通过 Docker exec 读取容器日志文件"""
    
    def __init__(self, container: str, log_path: str):
        """
        初始化 Docker 日志读取器
        
        Args:
            container: Docker 容器名称
            log_path: 容器内日志目录路径
        """
        self.container = container
        self.log_path = log_path
        self._connected = True  # Docker exec不需要持久连接
    
    def check_container_running(self) -> bool:
        """
        检查容器是否运行
        
        Returns:
            True 如果容器运行中，False 否则
        """
        try:
            check_result = subprocess.run(
                f'docker ps --format "{{{{.Names}}}}" | findstr /C:"{self.container}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            return check_result.returncode == 0 and self.container in check_result.stdout
        except Exception as e:
            logging.error(f"检查容器状态失败: {e}")
            return False
    
    def list_log_files(self, node_pattern: Optional[str] = None) -> List[str]:
        """
        列出容器中的日志文件
        
        Args:
            node_pattern: 节点匹配模式，如 'namenode', 'datanode' 等
        
        Returns:
            日志文件列表
        """
        try:
            # 首先检查容器是否运行
            if not self.check_container_running():
                logging.warning(f"容器 {self.container} 未运行，无法列出日志文件")
                return []
            
            # 使用docker exec执行ls命令（兼容Windows PowerShell）
            result = subprocess.run(
                f'docker exec {self.container} sh -c "ls -1 {self.log_path} 2>&1"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                logging.warning(f"无法列出容器 {self.container} 的日志文件: {result.stderr}")
                return []
            
            files = result.stdout.strip().split('\n')
            files = [f for f in files if f.strip()]  # 移除空行
            # 包含.log、.audit和.out文件（Hadoop的日志文件）
            log_files = [f for f in files if f.endswith(".log") or f.endswith(".audit") or f.endswith(".out")]
            
            if node_pattern:
                log_files = [f for f in log_files if node_pattern.lower() in f.lower()]
            
            return log_files
        except Exception as e:
            logging.error(f"列出日志文件失败: {e}")
            return []
    
    def read_log_file(self, file_path: str, start_pos: int = 0, 
                     max_bytes: Optional[int] = None, max_lines: Optional[int] = None) -> Tuple[str, int]:
        """
        从容器文件读取日志（支持断点续读）
        
        Args:
            file_path: 容器内文件路径（相对于 log_path 或绝对路径）
            start_pos: 开始读取的位置（字节偏移）
            max_bytes: 最大读取字节数，None 表示不限制
            max_lines: 最大读取行数，None 表示不限制（优先于 max_bytes）
        
        Returns:
            (文件内容, 新的读取位置)
        """
        try:
            if not self.check_container_running():
                logging.warning(f"容器 {self.container} 未运行，无法读取日志文件")
                return "", start_pos
            
            # 如果是相对路径，拼接 log_path
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.log_path, file_path)
            
            # 获取文件大小（在读取前获取，用于后续判断）
            try:
                result = subprocess.run(
                    f'docker exec {self.container} sh -c "stat -c %s {file_path} 2>&1"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    file_size = int(result.stdout.strip())
                    # 如果文件被轮转（变小了），重置位置
                    if start_pos > file_size:
                        logging.info(f"日志文件可能被轮转，重置读取位置: {file_path} (文件大小: {file_size}, 上次位置: {start_pos})")
                        start_pos = 0
                else:
                    file_size = None
            except Exception as e:
                logging.warning(f"无法获取文件大小: {file_path}, 错误: {e}")
                file_size = None
            
            # 如果指定了最大行数，按行读取
            if max_lines:
                # 从指定位置读取指定行数
                if start_pos == 0:
                    # 从文件末尾读取
                    result = subprocess.run(
                        f'docker exec {self.container} sh -c "tail -n {max_lines} {file_path} 2>&1"',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                else:
                    # 从指定位置读取（使用 tail -c +start_pos 然后限制行数）
                    result = subprocess.run(
                        f'docker exec {self.container} sh -c "tail -c +{start_pos} {file_path} 2>&1 | head -n {max_lines}"',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
            elif max_bytes:
                # 从指定位置读取指定字节数
                result = subprocess.run(
                    f'docker exec {self.container} sh -c "tail -c +{start_pos} {file_path} 2>&1 | head -c {max_bytes}"',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            else:
                # 读取全部（从指定位置）
                if start_pos == 0:
                    result = subprocess.run(
                        f'docker exec {self.container} sh -c "cat {file_path} 2>&1"',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                else:
                    result = subprocess.run(
                        f'docker exec {self.container} sh -c "tail -c +{start_pos} {file_path} 2>&1"',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
            
            if result.returncode != 0:
                logging.error(f"读取日志文件失败: {result.stderr}")
                return "", start_pos
            
            content = result.stdout
            # 计算新位置
            new_pos = start_pos + len(content.encode('utf-8'))
            
            # 如果文件大小已知且新位置超过文件大小，使用文件大小
            if file_size is not None and new_pos > file_size:
                new_pos = file_size
            
            return content, new_pos
            
        except FileNotFoundError as e:
            error_msg = f"Log file not found: {file_path}"
            logging.error(error_msg)
            return "", start_pos
        except PermissionError as e:
            error_msg = f"Permission denied reading: {file_path}"
            logging.error(error_msg)
            return "", start_pos
        except Exception as e:
            error_msg = f"Failed to read file {file_path}: {e}"
            logging.error(error_msg, exc_info=True)
            return "", start_pos
    
    def get_file_mtime(self, file_path: str) -> Optional[float]:
        """
        获取容器内文件的修改时间
        
        Args:
            file_path: 容器内文件路径
        
        Returns:
            修改时间（Unix 时间戳），失败返回 None
        """
        try:
            if not self.check_container_running():
                return None
            
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.log_path, file_path)
            
            result = subprocess.run(
                f'docker exec {self.container} sh -c "stat -c %Y {file_path} 2>&1"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                try:
                    return float(result.stdout.strip())
                except ValueError:
                    return None
            return None
        except Exception as e:
            logging.error(f"Failed to get mtime for {file_path}: {e}")
            return None
    
    def check_file_exists(self, file_path: str) -> bool:
        """
        检查容器内文件是否存在
        
        Args:
            file_path: 容器内文件路径
        
        Returns:
            True 如果文件存在，False 否则
        """
        try:
            if not self.check_container_running():
                return False
            
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.log_path, file_path)
            
            result = subprocess.run(
                f'docker exec {self.container} sh -c "test -f {file_path} 2>&1"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except Exception as e:
            logging.error(f"Error checking file {file_path}: {e}")
            return False
    
    def get_file_size(self, file_path: str) -> Optional[int]:
        """
        获取容器内文件的大小
        
        Args:
            file_path: 容器内文件路径
        
        Returns:
            文件大小（字节），失败返回 None
        """
        try:
            if not self.check_container_running():
                return None
            
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.log_path, file_path)
            
            result = subprocess.run(
                f'docker exec {self.container} sh -c "stat -c %s {file_path} 2>&1"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                try:
                    return int(result.stdout.strip())
                except ValueError:
                    return None
            return None
        except Exception as e:
            logging.error(f"Failed to get file size for {file_path}: {e}")
            return None
    
    def read_docker_logs(self, max_lines: Optional[int] = None, tail: bool = True) -> str:
        """
        读取Docker容器的标准输出日志（docker logs）
        
        Args:
            max_lines: 最大读取行数
            tail: 是否从末尾读取（True）还是从头读取（False）
        
        Returns:
            日志内容
        """
        try:
            # 首先检查容器是否存在（即使未运行，docker logs也可以读取历史日志）
            check_result = subprocess.run(
                f'docker ps -a --format "{{{{.Names}}}}" | findstr /C:"{self.container}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if check_result.returncode != 0 or self.container not in check_result.stdout:
                logging.warning(f"容器 {self.container} 不存在，无法读取日志")
                return ""
            
            if max_lines:
                if tail:
                    # 从末尾读取指定行数
                    result = subprocess.run(
                        f'docker logs {self.container} --tail {max_lines} 2>&1',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
                else:
                    # 从头读取指定行数
                    result = subprocess.run(
                        f'docker logs {self.container} 2>&1 | head -n {max_lines}',
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=10
                    )
            else:
                # 读取全部日志
                result = subprocess.run(
                    f'docker logs {self.container} 2>&1',
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
            
            if result.returncode == 0:
                return result.stdout
            else:
                logging.error(f"读取Docker日志失败: {result.stderr}")
                return ""
        except Exception as e:
            logging.error(f"读取Docker日志失败: {e}")
            return ""


# ==================== 适配现有函数的 Docker 版本 ====================

def check_log_files_exist_docker(docker_reader: DockerLogReader, node_pattern: Optional[str] = None) -> Tuple[bool, str]:
    """
    通过 Docker 检查容器中日志文件是否存在（兼容原有函数接口）
    
    Args:
        docker_reader: DockerLogReader 实例
        node_pattern: 节点匹配模式
    
    Returns:
        (是否存在, 检查消息)
    """
    try:
        if not docker_reader.check_container_running():
            return False, f"容器 {docker_reader.container} 未运行"
        
        log_files = docker_reader.list_log_files(node_pattern)
        
        if not log_files:
            pattern_msg = f"（模式: {node_pattern}）" if node_pattern else ""
            return False, f"未找到匹配的日志文件{pattern_msg}"
        
        # 检查文件是否可读
        readable_files = []
        for f in log_files:
            if docker_reader.check_file_exists(f):
                readable_files.append(f)
        
        if not readable_files:
            return False, f"找到 {len(log_files)} 个日志文件但都无读取权限"
        
        file_list = ', '.join(readable_files[:3])
        if len(readable_files) > 3:
            file_list += f" ... (共 {len(readable_files)} 个)"
        
        return True, f"找到 {len(readable_files)} 个可读日志文件: {file_list}"
        
    except Exception as e:
        return False, f"检查失败: {str(e)}"


def read_latest_logs_docker(docker_reader: DockerLogReader, last_pos: int, 
                        node_pattern: Optional[str] = None, max_lines: int = 200,
                        last_file: Optional[str] = None) -> Tuple[List[str], int, Optional[str]]:
    """
    通过 Docker 读取容器最新日志（兼容原有函数接口）
    
    Args:
        docker_reader: DockerLogReader 实例
        last_pos: 上次读取的文件位置
        node_pattern: 节点匹配模式
        max_lines: 最大读取行数，默认 200 行，避免日志过长
        last_file: 上次读取的文件名（可选），用于检测文件切换
    
    Returns:
        (日志行列表, 新的读取位置, 当前文件名)
    """
    try:
        print(f"read_latest_logs_docker 执行开始")
        if not docker_reader.check_container_running():
            print(f"容器 {docker_reader.container} 未运行")
            return [], last_pos, last_file
        
        # 列出日志文件
        log_files = docker_reader.list_log_files(node_pattern)
        if not log_files:
            print(f"无法找到日志文件")
            return [], last_pos, last_file
        
        # 获取文件修改时间，找到最新的文件
        log_files_with_time = []
        for f in log_files:
            mtime = docker_reader.get_file_mtime(f)
            if mtime:
                log_files_with_time.append((f, mtime))
        
        if not log_files_with_time:
            logging.warning(f"无法读取日志文件的时间信息: {docker_reader.log_path}")
            print(f"无法读取日志文件的时间信息: {docker_reader.log_path}")
            return [], last_pos, last_file
        
        # 按修改时间排序，获取最新的日志文件
        log_files_with_time.sort(key=lambda x: x[1], reverse=True)
        latest_file = log_files_with_time[0][0]
        
        # 检测文件切换：如果文件名变化，说明切换到新文件，需要重置读取位置
        if last_file and last_file != latest_file:
            logging.info(f"检测到日志文件切换: {last_file} -> {latest_file}，重置读取位置")
            last_pos = 0
        
        # 读取文件内容（从上次位置开始，限制最大行数）
        content, new_pos = docker_reader.read_log_file(latest_file, last_pos, max_lines=max_lines)
        
        # 调试信息：打印位置变化
        print(f"  [调试] 文件: {latest_file}, 上次位置: {last_pos}, 新位置: {new_pos}, 读取内容长度: {len(content)}")
        
        # 将内容转换为行列表
        lines = content.splitlines(keepends=True) if content else []
        
        # 如果读取的行数达到限制，记录信息
        if len(lines) >= max_lines:
            logging.info(f"容器日志文件较大，已限制读取 {max_lines} 行: {docker_reader.container}:{latest_file}")
        print("read_latest_logs_docker 执行成功")
        return lines, new_pos, latest_file
        
    except Exception as e:
        logging.error(f"Failed to read logs via Docker from {docker_reader.container}: {e}")
        print(f"Failed to read logs via Docker from {docker_reader.container}: {e}")
        return [], last_pos, last_file


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s'
    )
    
    # 创建 Docker 读取器
    namenode_reader = DockerLogReader(
        container=DOCKER_CONFIG["namenode"]["container"],
        log_path=DOCKER_CONFIG["namenode"]["log_path"]
    )
    
    # 检查日志文件是否存在
    exists, msg = check_log_files_exist_docker(namenode_reader, node_pattern="namenode")
    print(f"namenode 日志检查: {exists}, {msg}")
    
    if exists:
        # 读取最新日志
        lines, pos, current_file = read_latest_logs_docker(namenode_reader, 0, node_pattern="namenode")
        print(f"读取到 {len(lines)} 行日志（文件: {current_file}）")
        if lines:
            print("最新日志内容（前5行）:")
            for line in lines[:5]:
                print(f"  {line.rstrip()}")
    
    # 测试 DataNode
    datanode1_reader = DockerLogReader(
        container=DOCKER_CONFIG["datanode1"]["container"],
        log_path=DOCKER_CONFIG["datanode1"]["log_path"]
    )
    
    try:
        exists, msg = check_log_files_exist_docker(datanode1_reader, node_pattern="datanode")
        print(f"\ndatanode1 日志检查: {exists}, {msg}")
    except Exception as e:
        print(f"错误: {e}")

