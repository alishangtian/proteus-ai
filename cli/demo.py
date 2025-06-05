#!/usr/bin/env python3
"""
Proteus AI CLI工具演示脚本
展示如何使用命令行工具与Proteus AI进行交互
"""

import subprocess
import sys
import time

def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"演示: {description}")
    print(f"命令: {' '.join(cmd)}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("✅ 命令执行成功")
            if result.stdout:
                print("输出:")
                print(result.stdout)
        else:
            print("❌ 命令执行失败")
            if result.stderr:
                print("错误:")
                print(result.stderr)
    except subprocess.TimeoutExpired:
        print("⏰ 命令执行超时")
    except Exception as e:
        print(f"❌ 执行异常: {str(e)}")

def main():
    """演示主函数"""
    print("🚀 Proteus AI CLI工具演示")
    print("此演示将展示CLI工具的各种功能")
    
    # 检查依赖
    print("\n📦 检查Python依赖...")
    try:
        import aiohttp
        import requests
        import sseclient
        import colorama
        print("✅ 所有依赖已安装")
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请运行: pip install -r requirements_cli.txt")
        return
    
    # 演示各种功能
    demos = [
        (["python", "cli_tool.py", "--help"], "显示帮助信息"),
        (["python", "cli_tool.py", "list-models"], "列出可用模型"),
        (["python", "cli_tool.py", "configure"], "配置工具（演示模式，会直接退出）"),
    ]
    
    for cmd, desc in demos:
        run_command(cmd, desc)
        time.sleep(1)
    
    # 演示聊天功能（需要服务器运行）
    print(f"\n{'='*60}")
    print("💬 聊天功能演示")
    print("注意: 需要Proteus AI服务器正在运行")
    print("如果服务器未运行，命令会显示连接失败信息")
    print(f"{'='*60}")
    
    chat_cmd = ["python", "cli_tool.py", "chat", "你好，请简单介绍一下自己", "--model", "home"]
    run_command(chat_cmd, "发送简单问题")
    
    print(f"\n{'='*60}")
    print("🎯 演示完成!")
    print("\n💡 接下来你可以尝试:")
    print("1. 启动Proteus AI服务器")
    print("2. 运行: python cli_tool.py interactive")
    print("3. 或者运行: python cli_tool.py chat '你的问题' --model home")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()