#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JMX 连接问题测试脚本
用于诊断和测试 Hadoop JMX API 连接问题
"""

import requests
import time
import os
import sys
from typing import Tuple, Optional, Dict, Any

# JMX API 地址
NAMENODE_JMX = "http://localhost:9870/jmx"
DATANODE1_JMX = "http://localhost:9864/jmx"
DATANODE2_JMX = "http://localhost:9865/jmx"

# 备用地址（使用 127.0.0.1）
NAMENODE_JMX_ALT = "http://127.0.0.1:9870/jmx"
DATANODE1_JMX_ALT = "http://127.0.0.1:9864/jmx"
DATANODE2_JMX_ALT = "http://127.0.0.1:9865/jmx"


def test_jmx_connection(url: str, method: str = "default", timeout: Tuple[int, int] = (10, 30)) -> Dict[str, Any]:
    """
    测试 JMX 连接
    
    Args:
        url: JMX API URL
        method: 测试方法（"default", "no_proxy", "close_connection", "simple"）
        timeout: 超时设置 (连接超时, 读取超时)
    
    Returns:
        测试结果字典
    """
    result = {
        "url": url,
        "method": method,
        "success": False,
        "status_code": None,
        "error": None,
        "response_length": 0,
        "response_time": 0,
        "content_type": None,
        "beans_count": 0
    }
    
    try:
        # 创建 Session
        session = requests.Session()
        
        # 配置连接池
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=1,
            pool_maxsize=1,
            max_retries=0
        )
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        # 根据方法设置不同的请求头
        if method == "default":
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'identity',
                'Connection': 'close',
                'Cache-Control': 'no-cache'
            }
        elif method == "no_proxy":
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Connection': 'close'
            }
        elif method == "close_connection":
            headers = {
                'Connection': 'close'
            }
        elif method == "simple":
            headers = {}
        else:
            headers = {}
        
        # 记录开始时间
        start_time = time.time()
        
        # 发送请求
        r = session.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
            stream=False,
            proxies={'http': None, 'https': None},  # 禁用代理
            verify=False
        )
        
        # 计算响应时间
        result["response_time"] = time.time() - start_time
        result["status_code"] = r.status_code
        result["content_type"] = r.headers.get('Content-Type', '')
        
        if r.status_code == 200:
            result["success"] = True
            result["response_length"] = len(r.text)
            
            # 尝试解析 JSON 并统计 beans 数量
            try:
                data = r.json()
                if "beans" in data:
                    result["beans_count"] = len(data["beans"])
            except:
                pass
        else:
            result["error"] = f"HTTP {r.status_code}: {r.reason}"
        
        session.close()
        
    except requests.exceptions.ConnectionError as e:
        result["error"] = f"连接错误: {str(e)}"
        result["response_time"] = time.time() - start_time
    except requests.exceptions.Timeout as e:
        result["error"] = f"超时错误: {str(e)}"
        result["response_time"] = time.time() - start_time
    except requests.exceptions.HTTPError as e:
        result["error"] = f"HTTP错误: {str(e)}"
        if hasattr(e, 'response') and e.response is not None:
            result["status_code"] = e.response.status_code
    except Exception as e:
        result["error"] = f"未知错误: {str(e)}"
        import traceback
        result["traceback"] = traceback.format_exc()
    
    return result


def test_all_methods(url: str, name: str) -> None:
    """测试所有方法"""
    print(f"\n{'='*80}")
    print(f"测试 {name}: {url}")
    print(f"{'='*80}")
    
    methods = ["default", "no_proxy", "close_connection", "simple"]
    
    for method in methods:
        print(f"\n[方法: {method}]")
        result = test_jmx_connection(url, method=method)
        
        if result["success"]:
            print(f"  ✅ 成功")
            print(f"  状态码: {result['status_code']}")
            print(f"  响应时间: {result['response_time']:.3f}秒")
            print(f"  响应长度: {result['response_length']} 字节")
            print(f"  内容类型: {result['content_type']}")
            print(f"  Beans数量: {result['beans_count']}")
        else:
            print(f"  ❌ 失败")
            print(f"  错误: {result['error']}")
            if result.get('status_code'):
                print(f"  状态码: {result['status_code']}")
            if result.get('response_time'):
                print(f"  响应时间: {result['response_time']:.3f}秒")


def test_urls() -> None:
    """测试所有 URL"""
    print("\n" + "="*80)
    print("JMX 连接问题诊断测试")
    print("="*80)
    print(f"\n操作系统: {os.name}")
    print(f"Python版本: {sys.version}")
    print(f"Requests版本: {requests.__version__}")
    
    # 测试 NameNode
    print("\n\n" + "="*80)
    print("测试 NameNode JMX")
    print("="*80)
    
    print("\n[测试 localhost]")
    test_all_methods(NAMENODE_JMX, "NameNode (localhost)")
    
    print("\n[测试 127.0.0.1]")
    test_all_methods(NAMENODE_JMX_ALT, "NameNode (127.0.0.1)")
    
    # 测试 DataNode1
    print("\n\n" + "="*80)
    print("测试 DataNode1 JMX")
    print("="*80)
    
    print("\n[测试 localhost]")
    test_all_methods(DATANODE1_JMX, "DataNode1 (localhost)")
    
    print("\n[测试 127.0.0.1]")
    test_all_methods(DATANODE1_JMX_ALT, "DataNode1 (127.0.0.1)")
    
    # 测试 DataNode2
    print("\n\n" + "="*80)
    print("测试 DataNode2 JMX")
    print("="*80)
    
    print("\n[测试 localhost]")
    test_all_methods(DATANODE2_JMX, "DataNode2 (localhost)")
    
    print("\n[测试 127.0.0.1]")
    test_all_methods(DATANODE2_JMX_ALT, "DataNode2 (127.0.0.1)")


def test_detailed_connection(url: str, name: str) -> None:
    """详细测试单个连接"""
    print(f"\n{'='*80}")
    print(f"详细测试: {name}")
    print(f"URL: {url}")
    print(f"{'='*80}")
    
    # 测试不同的超时设置
    timeouts = [
        (5, 15),
        (10, 30),
        (30, 60),
    ]
    
    for conn_timeout, read_timeout in timeouts:
        print(f"\n[超时设置: 连接={conn_timeout}秒, 读取={read_timeout}秒]")
        result = test_jmx_connection(url, method="default", timeout=(conn_timeout, read_timeout))
        
        if result["success"]:
            print(f"  ✅ 成功 - 响应时间: {result['response_time']:.3f}秒")
        else:
            print(f"  ❌ 失败 - {result['error']}")


def check_network_status() -> None:
    """检查网络状态"""
    print("\n" + "="*80)
    print("网络状态检查")
    print("="*80)
    
    # 检查端口监听
    import subprocess
    try:
        result = subprocess.run(
            'netstat -an | findstr "9870 9864 9865"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("\n端口监听状态:")
            print(result.stdout)
        else:
            print("\n无法检查端口状态（可能需要管理员权限）")
    except Exception as e:
        print(f"\n检查端口状态失败: {e}")
    
    # 检查 Windows 代理设置
    try:
        result = subprocess.run(
            'netsh winhttp show proxy',
            shell=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            print("\nWindows 代理设置:")
            print(result.stdout)
        else:
            print("\n无法检查代理设置")
    except Exception as e:
        print(f"\n检查代理设置失败: {e}")


def test_from_container(container: str, port: int) -> None:
    """从容器内部测试 JMX 连接"""
    print(f"\n{'='*80}")
    print(f"从容器内部测试: {container}:{port}")
    print(f"{'='*80}")
    
    import subprocess
    
    # 测试从容器内部访问 localhost
    url = f"http://localhost:{port}/jmx"
    print(f"\n[容器内访问 localhost:{port}/jmx]")
    
    try:
        result = subprocess.run(
            f'docker exec {container} sh -c "curl -s -m 10 {url} 2>&1 | head -c 500"',
            shell=True,
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if result.returncode == 0 and result.stdout:
            if "beans" in result.stdout or "{" in result.stdout:
                print(f"  ✅ 成功 - 容器内可以访问 JMX")
                print(f"  响应预览: {result.stdout[:200]}...")
            else:
                print(f"  ⚠️  响应异常: {result.stdout[:200]}")
        else:
            print(f"  ❌ 失败")
            print(f"  返回码: {result.returncode}")
            print(f"  错误: {result.stderr[:200] if result.stderr else result.stdout[:200]}")
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")


def check_jmx_configuration() -> None:
    """检查 JMX 配置"""
    print(f"\n{'='*80}")
    print("检查 JMX 配置")
    print(f"{'='*80}")
    
    import subprocess
    
    containers = ["namenode", "datanode1", "datanode2"]
    
    for container in containers:
        print(f"\n[{container}]")
        
        # 检查进程
        try:
            result = subprocess.run(
                f'docker exec {container} jps 2>&1',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                print(f"  进程列表:")
                for line in result.stdout.strip().split('\n'):
                    if line.strip():
                        print(f"    {line}")
            else:
                print(f"  无法获取进程列表: {result.stderr}")
        except Exception as e:
            print(f"  检查进程失败: {e}")
        
        # 检查端口监听
        try:
            if container == "namenode":
                port = 9870
            elif container == "datanode1":
                port = 9864
            else:
                port = 9865
            
            result = subprocess.run(
                f'docker exec {container} sh -c "netstat -tlnp 2>&1 | grep {port}"',
                shell=True,
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                print(f"  端口 {port} 监听状态: {result.stdout.strip()}")
            else:
                print(f"  端口 {port} 未监听或无法检查")
        except Exception as e:
            print(f"  检查端口失败: {e}")


def main():
    """主函数"""
    print("\n" + "="*80)
    print("Hadoop JMX 连接问题诊断工具")
    print("="*80)
    
    # 检查网络状态
    check_network_status()
    
    # 检查 JMX 配置
    check_jmx_configuration()
    
    # 从容器内部测试
    print("\n\n" + "="*80)
    print("从容器内部测试 JMX 连接")
    print("="*80)
    test_from_container("namenode", 9870)
    test_from_container("datanode1", 9864)
    test_from_container("datanode2", 9865)
    
    # 测试所有 URL
    test_urls()
    
    # 详细测试 NameNode（如果基本测试失败）
    print("\n\n" + "="*80)
    print("详细诊断测试（如果基本测试失败）")
    print("="*80)
    test_detailed_connection(NAMENODE_JMX_ALT, "NameNode (127.0.0.1)")
    
    print("\n\n" + "="*80)
    print("测试完成 - 诊断分析")
    print("="*80)
    
    print("\n【问题分析】")
    print("从测试结果看，所有从主机访问 JMX 的连接都被立即关闭（响应时间 < 0.03秒）。")
    print("错误代码 10053 表示连接被软件中止。")
    print("\n可能的原因：")
    print("1. JMX 服务可能只绑定到容器内部网络，不接受外部连接")
    print("2. JMX 可能需要特定的认证或配置")
    print("3. Docker 端口映射可能只映射了 Web UI，没有映射 JMX 端口")
    print("4. JMX 服务可能需要通过容器内部 IP 访问")
    
    print("\n【建议的解决方案】")
    print("1. 检查容器内是否可以访问 JMX（见上方测试结果）")
    print("2. 如果容器内可以访问，说明 JMX 只监听容器内部网络")
    print("3. 解决方案：")
    print("   a) 通过 docker exec 在容器内访问 JMX")
    print("   b) 修改 JMX 配置，使其监听 0.0.0.0 而不是 localhost")
    print("   c) 使用 SSH 隧道转发 JMX 端口")
    print("   d) 修改 monitor_collector.py，通过 docker exec 访问 JMX")
    
    print("\n【检查命令】")
    print("1. 检查容器内服务: docker exec namenode jps")
    print("2. 检查容器内端口: docker exec namenode netstat -tlnp | grep 9870")
    print("3. 测试容器内访问: docker exec namenode curl -s http://localhost:9870/jmx | head -20")
    print("4. 检查 JMX 配置: docker exec namenode cat /usr/local/hadoop/etc/hadoop/hadoop-env.sh | grep -i jmx")


if __name__ == "__main__":
    main()

