#!/bin/bash

# Proteus AI CLI 启动脚本 (Unix/Linux/macOS)
# 提供快捷的命令行访问

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 切换到脚本目录
cd "$SCRIPT_DIR"

# 检查Python是否可用
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到python3"
    echo "请安装Python 3.7或更高版本"
    exit 1
fi

# 检查依赖是否已安装
python3 -c "import aiohttp, requests, sseclient, colorama" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "📦 正在安装依赖..."
    python3 -m pip install -r requirements_cli.txt
fi

# 运行CLI工具
python3 cli_tool.py "$@"