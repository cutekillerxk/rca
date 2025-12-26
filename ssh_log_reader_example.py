#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSH 日志读取器示例代码
这是方案一的完整实现示例，可以直接集成到 agent.py 中
"""

import os
import logging
import paramiko
from typing import List, Tuple, Optional

from regex import P

# ==================== 配置部分 ====================

# SSH 连接配置
SSH_CONFIG = {
    "s2": {
        "host": "10.157.197.70",
        "user": "hadoop",  # 根据实际情况修改
        "port": 22,
        "key_file": "~/.ssh/id_rsa",  # SSH 私钥路径
        "log_path": "/media/hnu/dependency/hadoop/module/hadoop-3.1.3/logs",  # s2 的实际日志路径，需要确认
    },
    "s3": {
        "host": "10.157.197.85",
        "user": "hadoop",
        "port": 22,
        "key_file": "~/.ssh/id_rsa",
        "log_path": "/media/hnu/dependency/hadoop/module/hadoop-3.1.3/logs",  # s3 的实际日志路径，需要确认
    }
}

# ==================== SSH 日志读取器类 ====================

class SSHLogReader:
    """通过 SSH 读取远程日志文件"""
    
    def __init__(self, host: str, user: str, log_path: str, port: int = 22, 
                 key_file: Optional[str] = None, password: Optional[str] = None):
        """
        初始化 SSH 日志读取器
        
        Args:
            host: 远程服务器地址
            user: SSH 用户名
            log_path: 远程日志目录路径
            port: SSH 端口，默认 22
            key_file: SSH 私钥文件路径（可选）
            password: SSH 密码（不推荐，安全性低）
        """
        self.host = host
        self.user = user
        self.port = port
        self.log_path = log_path
        self.key_file = key_file
        self.password = password
        self.client = None
        self.sftp = None
        self._connected = False
    
    def connect(self) -> bool:
        """
        建立 SSH 连接
        
        Returns:
            True 如果连接成功，False 否则
        """
        if self._connected and self.client and self.client.get_transport() and self.client.get_transport().is_active():
            return True
        
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # 尝试使用密钥文件
            if self.key_file:
                key_path = os.path.expanduser(self.key_file)
                if os.path.exists(key_path):
                    # 检查文件读取权限
                    if not os.access(key_path, os.R_OK):
                        error_msg = f"无权限读取 SSH 密钥文件: {key_path}"
                        logging.error(error_msg)
                        raise PermissionError(error_msg + "\n提示: 如果使用其他用户的密钥，需要添加读取权限或使用 sudo")
                    
                    try:
                        private_key = paramiko.RSAKey.from_private_key_file(key_path)
                        self.client.connect(
                            hostname=self.host,
                            port=self.port,
                            username=self.user,
                            pkey=private_key,
                            timeout=10,
                            look_for_keys=False
                        )
                    except paramiko.ssh_exception.PasswordRequiredException:
                        # 如果密钥需要密码，尝试使用密码
                        if self.password:
                            private_key = paramiko.RSAKey.from_private_key_file(key_path, password=self.password)
                            self.client.connect(
                                hostname=self.host,
                                port=self.port,
                                username=self.user,
                                pkey=private_key,
                                timeout=10
                            )
                        else:
                            raise
                    except PermissionError as e:
                        # 重新抛出权限错误
                        raise
                    except Exception as e:
                        # 其他错误，记录并尝试默认方式
                        logging.warning(f"使用指定密钥文件失败: {e}，尝试使用默认密钥")
                        self.client.connect(
                            hostname=self.host,
                            port=self.port,
                            username=self.user,
                            timeout=10
                        )
                else:
                    logging.warning(f"SSH key file not found: {key_path}, trying default key")
                    # 尝试使用默认密钥
                    self.client.connect(
                        hostname=self.host,
                        port=self.port,
                        username=self.user,
                        timeout=10
                    )
            # 使用密码认证（不推荐）
            elif self.password:
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.user,
                    password=self.password,
                    timeout=10
                )
            else:
                # 使用默认的 SSH 密钥（~/.ssh/id_rsa）
                self.client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.user,
                    timeout=10
                )
            
            # 创建 SFTP 客户端用于文件操作
            self.sftp = self.client.open_sftp()
            self._connected = True
            logging.info(f"SSH connection established to {self.user}@{self.host}:{self.port}")
            return True
            
        except paramiko.AuthenticationException as e:
            error_msg = f"SSH authentication failed for {self.user}@{self.host}: {e}"
            logging.error(error_msg)
            return False
        except paramiko.SSHException as e:
            error_msg = f"SSH connection error to {self.host}: {e}"
            logging.error(error_msg)
            return False
        except Exception as e:
            error_msg = f"Failed to connect to {self.host}: {e}"
            logging.error(error_msg)
            return False
    
    def disconnect(self):
        """关闭 SSH 连接"""
        try:
            if self.sftp:
                self.sftp.close()
                self.sftp = None
            if self.client:
                self.client.close()
                self.client = None
            self._connected = False
        except Exception as e:
            logging.warning(f"Error closing SSH connection: {e}")
    
    def list_log_files(self, node_pattern: Optional[str] = None) -> List[str]:
        """
        列出远程目录中的日志文件
        
        Args:
            node_pattern: 节点匹配模式，如 's2', 's3', 'datanode' 等
        
        Returns:
            日志文件列表
        """
        if not self._connected:
            if not self.connect():
                return []
        
        try:
            # 使用 SFTP 列出目录内容
            files = self.sftp.listdir(self.log_path)
            log_files = [f for f in files if f.endswith(".log")]
            
            if node_pattern:
                log_files = [f for f in log_files if node_pattern.lower() in f.lower()]
            
            return log_files
        except FileNotFoundError:
            logging.error(f"Log directory not found: {self.log_path}")
            return []
        except PermissionError:
            logging.error(f"Permission denied accessing: {self.log_path}")
            return []
        except Exception as e:
            logging.error(f"Failed to list files in {self.log_path}: {e}")
            return []
    
    def read_log_file(self, file_path: str, start_pos: int = 0, 
                     max_bytes: Optional[int] = None, max_lines: Optional[int] = None) -> Tuple[str, int]:
        """
        从远程文件读取日志（支持断点续读）
        
        Args:
            file_path: 远程文件路径（相对于 log_path 或绝对路径）
            start_pos: 开始读取的位置（字节偏移）
            max_bytes: 最大读取字节数，None 表示不限制（但如果设置了 max_lines 会优先限制行数）
            max_lines: 最大读取行数，None 表示不限制
        
        Returns:
            (文件内容, 新的读取位置)
        """
        if not self._connected:
            if not self.connect():
                return "", start_pos
        #print(f"[read_log_file] 开始读取文件: {file_path}, 开始位置: {start_pos}")
        try:
            # 如果是相对路径，拼接 log_path
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.log_path, file_path)
            
            # 获取文件大小（在读取前获取，用于后续判断）
            try:
                file_stat = self.sftp.stat(file_path)
                file_size = file_stat.st_size
                #print(f"[read_log_file] 获取文件大小成功: {file_path}, 大小: {file_size} 字节")
                # 如果文件被轮转（变小了），重置位置
                if start_pos > file_size:
                    logging.info(f"日志文件可能被轮转，重置读取位置: {file_path} (文件大小: {file_size}, 上次位置: {start_pos})")
                    start_pos = 0
            except Exception as e:
                #print(f"[read_log_file] 警告：无法获取文件大小: {file_path}, 错误: {e}")
                logging.warning(f"无法获取文件大小: {file_path}, 错误: {e}")
                file_size = None
            
            # 使用 SFTP 打开文件
            remote_file = self.sftp.open(file_path, 'r')
            remote_file.seek(start_pos)
            
            # 如果指定了最大行数，按行读取
            if max_lines:
                lines = []
                initial_pos = remote_file.tell()  # 记录初始位置（应该等于 start_pos）
                
                # 调试信息：打印读取前的状态
                #print(f"[read_log_file] 文件: {file_path}, start_pos={start_pos}, file_size={file_size}, initial_pos={initial_pos}")
                
                # 开始读取循环
                #print(f"[read_log_file] 开始读取循环，最多读取 {max_lines} 行")
                for i in range(max_lines):
                    line = remote_file.readline()
                    if not line:  # 文件末尾
                        #print(f"[read_log_file] 到达文件末尾，退出循环")
                        break
                    # 检查 line 的类型：如果是字节串需要解码，如果是字符串直接使用
                    if isinstance(line, bytes):
                        lines.append(line.decode('utf-8', errors='ignore'))
                    else:
                        lines.append(line)
                
                content = ''.join(lines)
                current_pos = remote_file.tell()
                
                # 调试信息：打印读取后的状态
                #print(f"[read_log_file] 读取后: current_pos={current_pos}, lines_read={len(lines)}, content_len={len(content)}")
                
                # 关键修复：如果位置没有变化且没有读取到内容，说明文件没有新内容
                # 此时应该返回文件大小（文件末尾位置），而不是 start_pos
                # 但要注意：如果文件大小就是0，返回0是正确的
                if current_pos == initial_pos and not content:
                    # 文件没有新内容，返回文件大小作为当前位置
                    if file_size is not None:
                        # 如果文件大小不是0，说明文件有内容但我们已经读完了，应该返回文件大小
                        # 如果文件大小是0，返回0也是正确的
                        current_pos = file_size
                        print(f"[read_log_file] 文件无新内容，返回文件大小: {current_pos} (start_pos={start_pos}, file_size={file_size})")
                        logging.debug(f"文件无新内容，返回文件大小: {current_pos} (start_pos={start_pos})")
                    else:
                        # 如果无法获取文件大小，至少保持 current_pos（应该等于 start_pos）
                        print(f"[read_log_file] 警告：无法获取文件大小，保持位置: {current_pos}")
                # 如果读取到了内容，current_pos 应该已经正确更新了
                elif content:
                    print(f"[read_log_file] 读取到内容，位置已更新: {initial_pos} -> {current_pos}")
                # 如果位置变化了但没有内容（不应该发生，但为了安全）
                elif current_pos != initial_pos:
                    print(f"[read_log_file] 位置变化但无内容（异常情况）: {initial_pos} -> {current_pos}")
            elif max_bytes:
                content_bytes = remote_file.read(max_bytes)
                # 检查返回类型：如果是字节串需要解码，如果是字符串直接使用
                if isinstance(content_bytes, bytes):
                    content = content_bytes.decode('utf-8', errors='ignore')
                else:
                    content = content_bytes
                current_pos = remote_file.tell()
            else:
                # 默认限制：最多读取 50KB 或 500 行（取较小值）
                # 避免一次性读取过大文件
                content_parts = []
                max_default_lines = 500
                lines_read = 0
                while lines_read < max_default_lines:
                    line = remote_file.readline()
                    if not line:  # 文件末尾
                        break
                    # 检查 line 的类型：如果是字节串需要解码，如果是字符串直接使用
                    if isinstance(line, bytes):
                        line_str = line.decode('utf-8', errors='ignore')
                    else:
                        line_str = line
                    content_parts.append(line_str)
                    lines_read += 1
                
                content = ''.join(content_parts)
                current_pos = remote_file.tell()
                
                if lines_read >= max_default_lines:
                    logging.info(f"日志文件较大，已限制读取 {lines_read} 行 : {file_path}")
            
            remote_file.close()
            
            # 最终调试信息：确认返回的值
            print(f"[read_log_file] 最终返回: content_len={len(content)}, current_pos={current_pos}, file_size={file_size}")
            
            return content, current_pos
            
        except FileNotFoundError as e:
            error_msg = f"Log file not found: {file_path}"
            print(f"[read_log_file] 异常: {error_msg}")
            logging.error(error_msg)
            return "", start_pos
        except PermissionError as e:
            error_msg = f"Permission denied reading: {file_path}"
            print(f"[read_log_file] 异常: {error_msg}")
            logging.error(error_msg)
            return "", start_pos
        except Exception as e:
            error_msg = f"Failed to read file {file_path}: {e}"
            print(f"[read_log_file] 异常: {error_msg}")
            import traceback
            print(f"[read_log_file] 异常堆栈:\n{traceback.format_exc()}")
            logging.error(error_msg, exc_info=True)
            return "", start_pos
    
    def get_file_mtime(self, file_path: str) -> Optional[float]:
        """
        获取远程文件的修改时间
        
        Args:
            file_path: 远程文件路径
        
        Returns:
            修改时间（Unix 时间戳），失败返回 None
        """
        if not self._connected:
            if not self.connect():
                return None
        
        try:
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.log_path, file_path)
            
            file_stat = self.sftp.stat(file_path)
            return file_stat.st_mtime
        except Exception as e:
            logging.error(f"Failed to get mtime for {file_path}: {e}")
            return None
    
    def check_file_exists(self, file_path: str) -> bool:
        """
        检查远程文件是否存在
        
        Args:
            file_path: 远程文件路径
        
        Returns:
            True 如果文件存在，False 否则
        """
        if not self._connected:
            if not self.connect():
                return False
        
        try:
            if not os.path.isabs(file_path):
                file_path = os.path.join(self.log_path, file_path)
            self.sftp.stat(file_path)
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logging.error(f"Error checking file {file_path}: {e}")
            return False
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()


# ==================== 适配现有函数的 SSH 版本 ====================

def check_log_files_exist_ssh(ssh_reader: SSHLogReader, node_pattern: Optional[str] = None) -> Tuple[bool, str]:
    """
    通过 SSH 检查远程日志文件是否存在（兼容原有函数接口）
    
    Args:
        ssh_reader: SSHLogReader 实例
        node_pattern: 节点匹配模式
    
    Returns:
        (是否存在, 检查消息)
    """
    try:
        if not ssh_reader.connect():
            return False, f"无法连接到 {ssh_reader.host}"
        
        log_files = ssh_reader.list_log_files(node_pattern)
        
        if not log_files:
            pattern_msg = f"（模式: {node_pattern}）" if node_pattern else ""
            return False, f"未找到匹配的日志文件{pattern_msg}"
        
        # 检查文件是否可读
        readable_files = []
        for f in log_files:
            if ssh_reader.check_file_exists(f):
                readable_files.append(f)
        
        if not readable_files:
            return False, f"找到 {len(log_files)} 个日志文件但都无读取权限"
        
        file_list = ', '.join(readable_files[:3])
        if len(readable_files) > 3:
            file_list += f" ... (共 {len(readable_files)} 个)"
        
        return True, f"找到 {len(readable_files)} 个可读日志文件: {file_list}"
        
    except Exception as e:
        return False, f"检查失败: {str(e)}"


def read_latest_logs_ssh(ssh_reader: SSHLogReader, last_pos: int, 
                        node_pattern: Optional[str] = None, max_lines: int = 200,
                        last_file: Optional[str] = None) -> Tuple[List[str], int, Optional[str]]:
    """
    通过 SSH 读取远程最新日志（兼容原有函数接口）
    
    Args:
        ssh_reader: SSHLogReader 实例
        last_pos: 上次读取的文件位置
        node_pattern: 节点匹配模式
        max_lines: 最大读取行数，默认 200 行，避免日志过长
        last_file: 上次读取的文件名（可选），用于检测文件切换
    
    Returns:
        (日志行列表, 新的读取位置, 当前文件名)
    """
    try:
        print(f"read_latest_logs_ssh 执行开始")
        if not ssh_reader.connect():
            print(f"无法连接到 {ssh_reader.host}")
            return [], last_pos, last_file
        
        # 列出日志文件
        log_files = ssh_reader.list_log_files(node_pattern)
        if not log_files:
            print(f"无法找到日志文件")
            return [], last_pos, last_file
        
        # 获取文件修改时间，找到最新的文件
        log_files_with_time = []
        for f in log_files:
            mtime = ssh_reader.get_file_mtime(f)
            if mtime:
                log_files_with_time.append((f, mtime))
        
        if not log_files_with_time:
            logging.warning(f"无法读取日志文件的时间信息: {ssh_reader.log_path}")
            print(f"无法读取日志文件的时间信息: {ssh_reader.log_path}")
            return [], last_pos, last_file
        
        # 按修改时间排序，获取最新的日志文件
        log_files_with_time.sort(key=lambda x: x[1], reverse=True)
        latest_file = log_files_with_time[0][0]
        
        # 检测文件切换：如果文件名变化，说明切换到新文件，需要重置读取位置
        if last_file and last_file != latest_file:
            logging.info(f"检测到日志文件切换: {last_file} -> {latest_file}，重置读取位置")
            last_pos = 0
        
        # 读取文件内容（从上次位置开始，限制最大行数）
        content, new_pos = ssh_reader.read_log_file(latest_file, last_pos, max_lines=max_lines)
        
        # 调试信息：打印位置变化
        print(f"  [调试] 文件: {latest_file}, 上次位置: {last_pos}, 新位置: {new_pos}, 读取内容长度: {len(content)}")
        
        # 将内容转换为行列表
        lines = content.splitlines(keepends=True) if content else []
        
        # 如果读取的行数达到限制，记录信息
        if len(lines) >= max_lines:
            logging.info(f"远程日志文件较大，已限制读取 {max_lines} 行: {ssh_reader.host}:{latest_file}")
        print("read_latest_logs_ssh 执行成功")
        return lines, new_pos, latest_file
        
    except Exception as e:
        logging.error(f"Failed to read logs via SSH from {ssh_reader.host}: {e}")
        print(f"Failed to read logs via SSH from {ssh_reader.host}: {e}")
        return [], last_pos, last_file


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s: %(message)s'
    )
    
    # 创建 SSH 读取器
    s2_reader = SSHLogReader(
        host=SSH_CONFIG["s2"]["host"],
        user=SSH_CONFIG["s2"]["user"],
        log_path=SSH_CONFIG["s2"]["log_path"],
        key_file=SSH_CONFIG["s2"]["key_file"]
    )
    
    # 使用上下文管理器（推荐）
    with s2_reader:
        # 检查日志文件是否存在
        exists, msg = check_log_files_exist_ssh(s2_reader, node_pattern="s2")
        print(f"s2 日志检查: {exists}, {msg}")
        
        if exists:
            # 读取最新日志
            lines, pos, current_file = read_latest_logs_ssh(s2_reader, 0, node_pattern="s2")
            print(f"读取到 {len(lines)} 行日志（文件: {current_file}）")
            if lines:
                print("最新日志内容（前5行）:")
                for line in lines[:5]:
                    print(f"  {line.rstrip()}")
    
    # 或者手动管理连接
    s3_reader = SSHLogReader(
        host=SSH_CONFIG["s3"]["host"],
        user=SSH_CONFIG["s3"]["user"],
        log_path=SSH_CONFIG["s3"]["log_path"]
    )
    
    try:
        if s3_reader.connect():
            exists, msg = check_log_files_exist_ssh(s3_reader, node_pattern="s3")
            print(f"\ns3 日志检查: {exists}, {msg}")
    finally:
        s3_reader.disconnect()

