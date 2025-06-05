#!/usr/bin/env python3
"""
CLI工具测试脚本
测试命令行工具的基本功能
"""

import subprocess
import sys
import json
import os
import tempfile
from pathlib import Path

def test_help():
    """测试帮助功能"""
    print("🧪 测试帮助功能...")
    try:
        result = subprocess.run([sys.executable, "cli_tool.py", "--help"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "Proteus AI 命令行工具" in result.stdout:
            print("✅ 帮助功能正常")
            return True
        else:
            print("❌ 帮助功能异常")
            return False
    except Exception as e:
        print(f"❌ 帮助功能测试失败: {e}")
        return False

def test_list_models():
    """测试模型列表功能"""
    print("🧪 测试模型列表功能...")
    try:
        result = subprocess.run([sys.executable, "cli_tool.py", "list-models"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and "workflow" in result.stdout:
            print("✅ 模型列表功能正常")
            return True
        else:
            print("❌ 模型列表功能异常")
            return False
    except Exception as e:
        print(f"❌ 模型列表测试失败: {e}")
        return False

def test_config():
    """测试配置功能"""
    print("🧪 测试配置功能...")
    try:
        # 创建临时配置文件
        config_data = {
            "base_url": "http://localhost:8000",
            "default_model": "home",
            "default_iterations": 5
        }
        
        # 测试配置文件路径
        from cli_tool import ProteusCliTool
        tool = ProteusCliTool()
        
        # 检查是否能正确加载配置
        if tool.config.get("base_url") == "http://localhost:8000":
            print("✅ 配置功能正常")
            return True
        else:
            print("❌ 配置功能异常")
            return False
    except Exception as e:
        print(f"❌ 配置功能测试失败: {e}")
        return False

def test_import():
    """测试模块导入"""
    print("🧪 测试模块导入...")
    try:
        from cli_tool import ProteusClient, ProteusCliTool
        print("✅ 模块导入正常")
        return True
    except Exception as e:
        print(f"❌ 模块导入失败: {e}")
        return False

def test_dependencies():
    """测试依赖包"""
    print("🧪 测试依赖包...")
    try:
        import aiohttp
        import requests
        import sseclient
        import colorama
        import asyncio
        import json
        import argparse
        print("✅ 所有依赖包正常")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖包: {e}")
        print("请运行: pip install -r requirements_cli.txt")
        return False

def test_client_creation():
    """测试客户端创建"""
    print("🧪 测试客户端创建...")
    try:
        from cli_tool import ProteusClient
        client = ProteusClient("http://localhost:8000")
        print("✅ 客户端创建正常")
        return True
    except Exception as e:
        print(f"❌ 客户端创建失败: {e}")
        return False

def run_all_tests():
    """运行所有测试"""
    print("🚀 开始运行CLI工具测试套件...\n")
    
    tests = [
        test_dependencies,
        test_import,
        test_client_creation,
        test_config,
        test_help,
        test_list_models,
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
        print()
    
    # 统计结果
    passed = sum(results)
    total = len(results)
    
    print("="*50)
    print(f"测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！CLI工具已准备就绪。")
    else:
        print("⚠️  有部分测试失败，请检查相关功能。")
    
    print("\n💡 接下来可以尝试:")
    print("1. python cli_tool.py chat '你好' --model home")
    print("2. python cli_tool.py interactive")
    print("3. python demo.py")
    
    return passed == total

if __name__ == "__main__":
    # 切换到脚本目录
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    success = run_all_tests()
    sys.exit(0 if success else 1)