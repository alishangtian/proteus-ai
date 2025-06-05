@echo off
REM Proteus AI CLI 启动脚本 (Windows)
REM 提供快捷的命令行访问

setlocal

REM 获取脚本所在目录
set "SCRIPT_DIR=%~dp0"

REM 切换到脚本目录
cd /d "%SCRIPT_DIR%"

REM 检查Python是否可用
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 未找到python
    echo 请安装Python 3.7或更高版本
    pause
    exit /b 1
)

REM 检查依赖是否已安装
python -c "import aiohttp, requests, sseclient, colorama" >nul 2>&1
if %errorlevel% neq 0 (
    echo 📦 正在安装依赖...
    python -m pip install -r requirements_cli.txt
)

REM 运行CLI工具
python cli_tool.py %*

endlocal