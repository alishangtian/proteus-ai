#!/usr/bin/env python3
"""
Proteus CLI 启动脚本
提供更简洁的命令行入口
"""

import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入并运行主CLI工具
from cli_tool import main

if __name__ == "__main__":
    main()