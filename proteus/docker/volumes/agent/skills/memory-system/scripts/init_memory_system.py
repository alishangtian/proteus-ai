"""
记忆系统初始化脚本 - 精简版
创建必要的目录结构和精简配置文件，只包含LLM和Ollama配置
包含充分的初始化检查和验证
"""

import os
import sys
import json
import argparse
import subprocess
import shutil
import datetime

def check_dependencies(auto_install=True):
    """检查系统依赖，支持自动安装
    
    Args:
        auto_install: 如果为True，自动安装缺失的Python包
        
    Returns:
        bool: 所有依赖是否满足
    """
    print("🔍 检查系统依赖...")
    
    # 系统命令依赖
    system_dependencies = {
        "python": {"command": ["python3", "--version"], "required": True},
        "sqlite3": {"command": ["sqlite3", "--version"], "required": False},
    }
    
    # Python包依赖（包名: {导入名, 是否必需, pip名称}）
    python_packages = {
        "chromadb": {"import_name": "chromadb", "required": True, "pip_name": "chromadb"},
        "sentence-transformers": {"import_name": "sentence_transformers", "required": True, "pip_name": "sentence-transformers"},
        "pyyaml": {"import_name": "yaml", "required": True, "pip_name": "pyyaml"},
        "requests": {"import_name": "requests", "required": True, "pip_name": "requests"},
        "numpy": {"import_name": "numpy", "required": True, "pip_name": "numpy"},
        "openai": {"import_name": "openai", "required": False, "pip_name": "openai"},
    }
    
    missing_system = []
    missing_python = []
    
    # 检查系统依赖
    print("📦 检查系统命令依赖:")
    for name, info in system_dependencies.items():
        try:
            import subprocess
            result = subprocess.run(info["command"], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"   ✅ {name}: 已安装")
                if name == "python":
                    print(f"      版本: {result.stdout.strip()}")
            else:
                if info["required"]:
                    missing_system.append(name)
                    print(f"   ❌ {name}: 命令失败")
                else:
                    print(f"   ⚠️  {name}: 未安装 (可选)")
        except FileNotFoundError:
            if info["required"]:
                missing_system.append(name)
                print(f"   ❌ {name}: 未安装")
            else:
                print(f"   ⚠️  {name}: 未安装 (可选)")
        except Exception as e:
            if info["required"]:
                missing_system.append(f"{name} (错误: {e})")
                print(f"   ❌ {name}: 错误 - {e}")
            else:
                print(f"   ⚠️  {name}: 错误 - {e}")
    
    # 检查Python包依赖
    print("🐍 检查Python包依赖:")
    for package_name, info in python_packages.items():
        import_name = info["import_name"]
        required = info["required"]
        pip_name = info["pip_name"]
        
        try:
            __import__(import_name)
            # 获取版本信息
            try:
                module = __import__(import_name)
                version = getattr(module, '__version__', '未知版本')
                print(f"   ✅ {package_name}: 已安装 ({version})")
            except:
                print(f"   ✅ {package_name}: 已安装")
        except ImportError:
            if required:
                missing_python.append(package_name)
                print(f"   ❌ {package_name}: 未安装")
            else:
                print(f"   ⚠️  {package_name}: 未安装 (可选)")
        except Exception as e:
            if required:
                missing_python.append(f"{package_name} (错误: {e})")
                print(f"   ❌ {package_name}: 错误 - {e}")
            else:
                print(f"   ⚠️  {package_name}: 错误 - {e}")
    
    # 处理缺失的Python包
        if missing_python and auto_install:
            print(f"🔧 尝试自动安装缺失的Python包: {', '.join(missing_python)}")
            success = install_python_packages(missing_python, python_packages)
            if success:
                # 重新检查安装的包
                print("🔍 验证安装结果...")
                # 重新检查缺失的包
                new_missing = []
                for package_name in missing_python:
                    if package_name not in python_packages:
                        continue
                    import_name = python_packages[package_name]["import_name"]
                    try:
                        __import__(import_name)
                        print(f"   ✅ {package_name}: 安装成功")
                    except ImportError:
                        new_missing.append(package_name)
                        print(f"   ❌ {package_name}: 安装失败")
                missing_python = new_missing
    # 报告最终状态
    all_missing = missing_system + missing_python
    
    if missing_system:
        print(f"⚠️  缺少必需系统依赖: {', '.join(missing_system)}")
        print("   请手动安装缺失的系统依赖")
    
    if missing_python:
        print(f"⚠️  缺少必需Python包: {', '.join(missing_python)}")
        if not auto_install:
            print("   请手动安装缺失的包，或重新运行初始化脚本")
    
    if not all_missing:
        print("✅ 所有依赖检查通过")
        return True
    else:
        print("❌ 依赖检查失败")
        return False
def install_python_packages(package_names, package_info):
    """安装指定的Python包
    
    Args:
        package_names: 包名列表
        package_info: 包信息字典
        
    Returns:
        bool: 是否全部安装成功
    """
    import subprocess
    import sys
    
    success_count = 0
    total = len(package_names)
    
    for package_name in package_names:
        if package_name not in package_info:
            print(f"   ⚠️  未知包: {package_name}，跳过")
            continue
            
        pip_name = package_info[package_name]["pip_name"]
        print(f"   📦 安装 {package_name} ({pip_name})...")
        
        try:
            # 使用当前Python的pip安装
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pip_name],
                capture_output=True,
                text=True,
                timeout=120  # 2分钟超时
            )
            
            if result.returncode == 0:
                success_count += 1
                print(f"   ✅ {package_name} 安装成功")
            else:
                print(f"   ❌ {package_name} 安装失败:")
                print(f"      错误: {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"   ❌ {package_name} 安装超时")
        except Exception as e:
            print(f"   ❌ {package_name} 安装异常: {e}")
    
    print(f"📊 安装结果: {success_count}/{total} 个包安装成功")
    return success_count == total

def check_initialization_status(storage_base):
    """检查系统是否已初始化"""
    print(f"🔍 检查初始化状态: {storage_base}")
    
    # 初始化标志文件
    init_flag = os.path.join(storage_base, ".initialized")
    
    # 如果标志文件存在，检查是否有效
    if os.path.exists(init_flag):
        try:
            with open(init_flag, 'r', encoding='utf-8') as f:
                data = f.read().strip()
                print(f"   ✅ 系统已初始化 ({data})")
                return True
        except:
            print(f"   ⚠️  初始化标志文件损坏，将重新初始化")
            return False
    
    # 检查关键目录和文件
    required_items = [
        os.path.join(storage_base, "config.yaml"),
        os.path.join(storage_base, "long"),
        os.path.join(storage_base, "medium"),
        os.path.join(storage_base, "short_term"),
    ]
    
    missing_items = []
    for item in required_items:
        if not os.path.exists(item):
            missing_items.append(item)
    
    if missing_items:
        print(f"   ❌ 系统未完全初始化，缺失: {len(missing_items)} 个项目")
        for item in missing_items[:3]:  # 只显示前3个
            print(f"      - {os.path.basename(item)}")
        if len(missing_items) > 3:
            print(f"      ... 还有 {len(missing_items)-3} 个")
        return False
    
    print(f"   ✅ 系统目录结构完整，但缺少初始化标志")
    return False

def check_directory_permissions(base_path):
    """检查目录权限"""
    print(f"🔍 检查目录权限: {base_path}")
    
    # 检查父目录是否存在且有写权限
    parent_dir = os.path.dirname(os.path.abspath(base_path))
    if not os.path.exists(parent_dir):
        print(f"   ❌ 父目录不存在: {parent_dir}")
        try:
            os.makedirs(parent_dir, exist_ok=True)
            print(f"   ✅ 已创建父目录: {parent_dir}")
        except Exception as e:
            print(f"   ❌ 无法创建父目录: {e}")
            return False
    
    # 检查写权限
    test_file = os.path.join(base_path, ".permission_test")
    try:
        os.makedirs(base_path, exist_ok=True)
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        print(f"   ✅ 目录可写: {base_path}")
        return True
    except Exception as e:
        print(f"   ❌ 目录不可写: {base_path} - {e}")
        return False

def create_minimal_config(storage_base, config_path):
    """创建最小化配置，只包含LLM和Ollama配置"""
    print("📝 创建最小化配置...")
    
    config = {
        # 绝对最小化配置 - 只包含LLM和Ollama
        "memory": {
            "long_term": {
                "database_path": os.path.join(storage_base, "long", "memory.db"),
                "use_chroma": True
            }
        },
        # 只配置llm和ollama
        "llm": {
            "enabled": True,
            "default_provider": "ollama",  # 默认使用ollama，避免API密钥依赖
            "providers": {
                "ollama": {
                    "base_url": "http://host.docker.internal:11434",
                    "default_model": "llama2",
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "timeout": 60
                },
                # OpenAI配置（可选，需要API密钥）
                "openai": {
                    "api_key": "${OPENAI_API_KEY}",
                    "base_url": "https://api.openai.com/v1",
                    "default_model": "gpt-3.5-turbo",
                    "temperature": 0.3,
                    "max_tokens": 1000,
                    "timeout": 30
                }
            }
        },
        "embedding": {
            "enabled": True,
            "default_provider": "ollama",
            "providers": {
                "ollama": {
                    "base_url": "http://host.docker.internal:11434",
                    "default_model": "bge-m3",
                    "timeout": 30
                }
            }
        }
    }
    
    # 写入配置文件
    try:
        import yaml
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        print(f"   ✅ 配置文件创建成功: {config_path}")
        return True
    except ImportError:
        try:
            config_path = config_path.replace('.yaml', '.json').replace('.yml', '.json')
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            print(f"   ✅ 配置文件创建成功 (JSON格式): {config_path}")
            return True
        except Exception as e:
            print(f"   ❌ 配置文件创建失败: {e}")
            return False
    except Exception as e:
        print(f"   ❌ 配置文件创建失败: {e}")
        return False

def create_directory_structure(storage_base):
    """创建目录结构"""
    print("📁 创建目录结构...")
    
    directories = [
        storage_base,
        os.path.join(storage_base, "short_term"),
        os.path.join(storage_base, "medium"),
        os.path.join(storage_base, "long"),
        os.path.join(storage_base, "chroma"),
        os.path.join(storage_base, "logs"),
        os.path.join(storage_base, "backups")
    ]
    
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            print(f"   ✅ 目录: {directory}")
        except Exception as e:
            print(f"   ❌ 无法创建目录 {directory}: {e}")
            return False
    
    return True

def init_memory_system(storage_base="/app/data/memory", config_path=None, force=False, auto_install=True):
    """
    初始化记忆系统 - 精简版
    
    Args:
        storage_base: 存储根目录
        config_path: 配置文件路径，如果为None则在存储目录创建config.yaml
        force: 是否强制覆盖现有配置
    """
    print("🚀 开始初始化记忆系统 (精简版)...")
    print(f"   存储目录: {storage_base}")
    
    # 步骤1: 检查依赖
    if not check_dependencies():
        print("❌ 依赖检查失败，初始化中止")
        return False
    
    # 步骤2: 检查目录权限
    if not check_directory_permissions(storage_base):
        print("❌ 目录权限检查失败，初始化中止")
        return False
    
    # 步骤3: 创建目录结构
    if not create_directory_structure(storage_base):
        print("❌ 目录创建失败，初始化中止")
        return False
    
    # 步骤4: 确定配置文件路径
    if config_path is None:
        config_path = os.path.join(storage_base, "config.yaml")
    
    # 检查配置文件是否已存在
    if os.path.exists(config_path) and not force:
        print(f"⚠️  配置文件已存在: {config_path}")
        response = input("   是否覆盖? (y/N): ")
        if response.lower() != 'y':
            print("❌ 初始化中止")
            return False
    
    # 步骤5: 创建最小化配置
    if not create_minimal_config(storage_base, config_path):
        print("❌ 配置创建失败，初始化中止")
        return False
    
    # 步骤6: 创建使用说明
    readme_path = os.path.join(storage_base, "README.md")
    try:
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(f"""# 记忆系统使用说明 (精简版)

## 配置说明
本系统已配置为最小化版本，仅包含LLM和Ollama配置。

### 主要配置项:
1. **LLM配置**: 支持OpenAI和Ollama
2. **嵌入配置**: 使用Ollama的bge-m3模型
3. **存储配置**: SQLite + Chroma向量存储

### 环境变量:
- `OPENAI_API_KEY`: OpenAI API密钥 (可选)
- 如果没有设置，系统将默认使用Ollama

## CLI使用示例

### 1. 存储记忆
```bash
python /app/.proteus/skills/memory-system/scripts/memory_cli.py store \
  --content "用户喜欢黑咖啡" \
  --importance 0.8 \
  --tags "饮食,偏好"
```

### 2. 检索记忆
```bash
python /app/.proteus/skills/memory-system/scripts/memory_cli.py retrieve \
  --query "咖啡" \
  --limit 5
```

### 3. 获取统计
```bash
python /app/.proteus/skills/memory-system/scripts/memory_cli.py stats
```

### 4. 使用环境变量指定配置
```bash
export MEMORY_CONFIG_PATH="{config_path}"
python memory_cli.py stats
```

## 目录结构
```
{storage_base}/
├── config.yaml        # 配置文件
├── short_term/        # 短期记忆
├── medium/           # 中期记忆
├── long/             # 长期记忆 (SQLite)
├── chroma/           # 向量存储
├── logs/             # 系统日志
└── backups/          # 备份文件
```

## 注意事项
1. 确保Ollama服务在运行 (默认: http://host.docker.internal:11434)
2. 如需使用OpenAI，请设置OPENAI_API_KEY环境变量
3. 所有操作通过CLI进行，无需Python代码初始化
""")
        print(f"   ✅ 使用说明创建成功: {readme_path}")
    except Exception as e:
        print(f"   ⚠️  无法创建使用说明: {e}")
    

    # 创建初始化标志文件
    try:
        init_flag_path = os.path.join(storage_base, ".initialized")
        with open(init_flag_path, 'w', encoding='utf-8') as f:
            f.write(f"初始化时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"版本: 2.1\n")
            f.write(f"存储目录: {storage_base}\n")
        print(f"   ✅ 初始化标志文件创建: {init_flag_path}")
    except Exception as e:
        print(f"   ⚠️  无法创建初始化标志文件: {e}")

    print("\n" + "="*60)
    print("✅ 记忆系统初始化完成！")
    print("="*60)
    print(f"📁 存储目录: {storage_base}")
    print(f"⚙️  配置文件: {config_path}")
    print(f"📖 使用说明: {readme_path}")
    print("🚀 快速开始:")
    print(f"   1. 存储记忆: python /app/.proteus/skills/memory-system/scripts/memory_cli.py store --content '测试记忆'")
    print(f"   2. 检索记忆: python /app/.proteus/skills/memory-system/scripts/memory_cli.py retrieve --query '测试'")
    print(f"   3. 查看统计: python /app/.proteus/skills/memory-system/scripts/memory_cli.py stats")
    print("💡 提示: 所有操作通过CLI进行，无需编写Python代码！")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="初始化记忆系统 (精简版)")
    parser.add_argument("--storage-base", default="/app/data/memory",
                       help="记忆存储根目录 (默认: /app/data/memory)")
    parser.add_argument("--config-path", 
                       help="配置文件路径 (默认: <storage-base>/config.yaml)")
    parser.add_argument("--force", action="store_true",
                       help="强制覆盖现有配置文件")
    
    parser.add_argument("--no-auto-install", action="store_true",
                   help="禁用自动安装依赖")

    args = parser.parse_args()
    
    success = init_memory_system(auto_install=not args.no_auto_install, 
        storage_base=args.storage_base,
        config_path=args.config_path,
        force=args.force)
    
    
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
