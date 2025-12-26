#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 JMX 端点访问，找出 502 错误的原因
"""

import requests
import json
from datetime import datetime

def test_request(name, url, headers=None, **kwargs):
    """测试单个请求"""
    print(f"\n{'='*80}")
    print(f"测试: {name}")
    print(f"URL: {url}")
    if headers:
        print(f"请求头: {headers}")
    print(f"{'='*80}")
    
    try:
        start_time = datetime.now()
        r = requests.get(url, headers=headers, timeout=10, **kwargs)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        print(f"状态码: {r.status_code}")
        print(f"响应时间: {duration:.2f} 秒")
        print(f"响应头 Content-Type: {r.headers.get('Content-Type', 'N/A')}")
        print(f"响应头 Content-Length: {r.headers.get('Content-Length', 'N/A')}")
        print(f"响应头 Content-Encoding: {r.headers.get('Content-Encoding', 'N/A')}")
        
        if r.status_code == 200:
            try:
                data = r.json()
                print(f"[OK] 成功！JSON 数据包含 {len(data.get('beans', []))} 个 beans")
                return True, r.status_code
            except json.JSONDecodeError as e:
                print(f"[WARN] 状态码 200，但 JSON 解析失败: {e}")
                print(f"响应内容预览（前200字符）: {r.text[:200]}")
                return False, r.status_code
        else:
            print(f"[FAIL] 失败！状态码: {r.status_code}")
            print(f"响应内容预览（前200字符）: {r.text[:200]}")
            return False, r.status_code
            
    except requests.exceptions.ConnectionError as e:
        print(f"[ERROR] 连接错误: {e}")
        return False, "ConnectionError"
    except requests.exceptions.Timeout as e:
        print(f"[ERROR] 超时错误: {e}")
        return False, "Timeout"
    except Exception as e:
        print(f"[ERROR] 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False, "Exception"

def main():
    """运行所有测试"""
    print("="*80)
    print("JMX 端点访问测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 检查代理设置
    import os
    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    no_proxy = os.environ.get('NO_PROXY') or os.environ.get('no_proxy')
    
    print(f"\n环境变量检查:")
    print(f"HTTP_PROXY: {http_proxy}")
    print(f"HTTPS_PROXY: {https_proxy}")
    print(f"NO_PROXY: {no_proxy}")
    print(f"requests 默认代理: {requests.Session().proxies}")
    print("="*80)
    
    base_url = "http://localhost:9870/jmx"
    results = []
    
    # 测试1：最简单的请求（无任何请求头）
    success, status = test_request("测试1: 最简单的请求（无请求头）", base_url)
    results.append(("测试1: 无请求头", success, status))
    
    # 测试2：只设置 Accept 头
    success, status = test_request("测试2: 只设置 Accept 头", base_url, 
                                   headers={'Accept': '*/*'})
    results.append(("测试2: Accept头", success, status))
    
    # 测试3：使用 127.0.0.1 替代 localhost（禁用代理）
    alt_url = base_url.replace('localhost', '127.0.0.1')
    success, status = test_request("测试3: 使用 127.0.0.1（禁用代理）", alt_url, proxies={'http': None, 'https': None})
    results.append(("测试3: 127.0.0.1无代理", success, status))
    
    # 测试3b：使用 localhost 但禁用代理
    success, status = test_request("测试3b: localhost 禁用代理", base_url, proxies={'http': None, 'https': None})
    results.append(("测试3b: localhost无代理", success, status))
    
    # 测试4：模拟 curl 的请求头
    success, status = test_request("测试4: 模拟 curl 请求头", base_url,
                                   headers={'User-Agent': 'curl/7.68.0',
                                           'Accept': '*/*'})
    results.append(("测试4: curl头", success, status))
    
    # 测试5：不使用压缩
    success, status = test_request("测试5: 禁用压缩", base_url,
                                   headers={'Accept': '*/*',
                                           'Accept-Encoding': 'identity'})
    results.append(("测试5: 禁用压缩", success, status))
    
    # 测试6：使用 Session（连接复用）
    print(f"\n{'='*80}")
    print("测试6: 使用 Session（连接复用）")
    print(f"{'='*80}")
    try:
        session = requests.Session()
        r = session.get(base_url, timeout=10)
        print(f"状态码: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"[OK] 成功！JSON 数据包含 {len(data.get('beans', []))} 个 beans")
            results.append(("测试6: Session", True, r.status_code))
        else:
            print(f"[FAIL] 失败！状态码: {r.status_code}")
            results.append(("测试6: Session", False, r.status_code))
        session.close()
    except Exception as e:
        print(f"❌ 错误: {e}")
        results.append(("测试6: Session", False, "Exception"))
    
    # 测试7：完整的浏览器请求头（当前代码使用的）
    success, status = test_request("测试7: 完整浏览器请求头", base_url,
                                   headers={
                                       'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                                       'Accept': 'application/json, text/plain, */*',
                                       'Accept-Language': 'en-US,en;q=0.9',
                                       'Accept-Encoding': 'gzip, deflate',
                                       'Connection': 'keep-alive',
                                       'Cache-Control': 'no-cache'
                                   })
    results.append(("测试7: 完整浏览器头", success, status))
    
    # 测试8：移除 Accept-Encoding（关键测试）
    success, status = test_request("测试8: 移除 Accept-Encoding", base_url,
                                   headers={
                                       'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                                       'Accept': 'application/json, text/plain, */*',
                                       'Accept-Language': 'en-US,en;q=0.9',
                                       'Connection': 'keep-alive',
                                       'Cache-Control': 'no-cache'
                                   })
    results.append(("测试8: 移除压缩", success, status))
    
    # 测试9：使用 stream=False 显式设置
    success, status = test_request("测试9: 显式设置 stream=False", base_url,
                                   headers={'Accept': '*/*'},
                                   stream=False)
    results.append(("测试9: stream=False", success, status))
    
    # 测试10：使用 stream=True
    success, status = test_request("测试10: 使用 stream=True", base_url,
                                   headers={'Accept': '*/*'},
                                   stream=True)
    results.append(("测试10: stream=True", success, status))
    
    # 汇总结果
    print(f"\n{'='*80}")
    print("测试结果汇总")
    print(f"{'='*80}")
    for name, success, status in results:
        status_icon = "[OK]" if success else "[FAIL]"
        print(f"{status_icon} {name}: {status}")
    
    # 找出成功的测试
    successful_tests = [name for name, success, status in results if success]
    if successful_tests:
        print(f"\n[OK] 成功的测试方法: {', '.join(successful_tests)}")
        print("建议：在 monitor_collector.py 中使用成功的请求方式")
    else:
        print(f"\n[FAIL] 所有测试都失败了，可能是服务未启动或其他问题")
    
    print(f"\n{'='*80}")

if __name__ == "__main__":
    main()
