#!/usr/bin/env python3
"""
Proteus AI 命令行工具
用于与Proteus AI系统进行交互的命令行客户端
"""

import asyncio
import json
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any
import argparse
import aiohttp
import sseclient
import requests
from urllib.parse import urljoin
import colorama
from colorama import Fore, Style
import os

# 初始化colorama以支持Windows终端颜色
colorama.init()

class ProteusClient:
    """Proteus AI API客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        """
        初始化客户端
        
        Args:
            base_url: API服务器地址
        """
        self.base_url = base_url.rstrip('/')
        self.session = None
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def health_check(self) -> bool:
        """检查服务健康状态"""
        try:
            async with self.session.get(f"{self.base_url}/health") as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("success", False)
                return False
        except Exception:
            return False
    
    async def create_chat(
        self, 
        text: str, 
        model: str = "home", 
        itecount: int = 5,
        agentid: Optional[str] = None,
        team_name: Optional[str] = None
    ) -> Optional[str]:
        """
        创建聊天会话
        
        Args:
            text: 用户问题
            model: 模型类型
            itecount: 迭代次数
            agentid: 代理ID
            team_name: 团队名称
            
        Returns:
            chat_id: 聊天会话ID
        """
        payload = {
            "text": text,
            "model": model,
            "itecount": itecount
        }
        
        if agentid:
            payload["agentid"] = agentid
        if team_name:
            payload["team_name"] = team_name
            
        try:
            async with self.session.post(
                f"{self.base_url}/chat", 
                json=payload
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("chat_id")
                else:
                    error_text = await response.text()
                    print(f"{Fore.RED}错误: 创建聊天失败 (状态码: {response.status}){Style.RESET_ALL}")
                    print(f"{Fore.RED}{error_text}{Style.RESET_ALL}")
                    return None
        except Exception as e:
            print(f"{Fore.RED}错误: 网络请求失败 - {str(e)}{Style.RESET_ALL}")
            return None
    
    def stream_chat(self, chat_id: str):
        """
        获取聊天流式响应（使用同步方式以保持兼容性）
        
        Args:
            chat_id: 聊天会话ID
        """
        try:
            url = f"{self.base_url}/stream/{chat_id}"
            response = requests.get(url, stream=True, headers={'Accept': 'text/event-stream'})
            
            if response.status_code != 200:
                print(f"{Fore.RED}错误: 建立SSE连接失败 (状态码: {response.status_code}){Style.RESET_ALL}")
                return
            
            client = sseclient.SSEClient(response)
            
            print(f"{Fore.CYAN}📡 已建立SSE连接，开始接收响应...{Style.RESET_ALL}\n")
            
            for event in client.events():
                if event.data:
                    try:
                        data = json.loads(event.data)
                        self._handle_stream_event(data)
                    except json.JSONDecodeError:
                        print(f"{Fore.YELLOW}⚠️  收到无效的JSON数据: {event.data}{Style.RESET_ALL}")
                        
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}📡 连接已中断{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}错误: SSE连接异常 - {str(e)}{Style.RESET_ALL}")
    
    def _handle_stream_event(self, data: Dict[str, Any]):
        """
        处理流式事件数据
        
        Args:
            data: 事件数据
        """
        event_type = data.get("event", "unknown")
        success = data.get("success", False)
        event_data = data.get("data", {})
        
        if event_type == "status":
            status = event_data.get("status", "unknown")
            message = event_data.get("message", "")
            print(f"{Fore.BLUE}📋 状态: {status} - {message}{Style.RESET_ALL}")
            
        elif event_type == "workflow":
            nodes_count = len(event_data.get("nodes", []))
            edges_count = len(event_data.get("edges", []))
            print(f"{Fore.GREEN}🔧 工作流生成完成: {nodes_count} 个节点, {edges_count} 条边{Style.RESET_ALL}")
            
        elif event_type == "result":
            node_id = event_data.get("node_id", "unknown")
            node_success = event_data.get("success", False)
            node_status = event_data.get("status", "unknown")
            
            status_icon = "✅" if node_success else "❌"
            color = Fore.GREEN if node_success else Fore.RED
            print(f"{color}{status_icon} 节点 [{node_id}]: {node_status}{Style.RESET_ALL}")
            
            # 显示节点输出数据
            if "output" in event_data:
                output = event_data["output"]
                if isinstance(output, str) and output.strip():
                    print(f"   💬 输出: {output[:200]}{'...' if len(output) > 200 else ''}")
                    
        elif event_type == "answer":
            # 流式回答
            content = event_data if isinstance(event_data, str) else str(event_data)
            if content.strip():
                print(content, end="", flush=True)
                
        elif event_type == "complete":
            print(f"\n{Fore.GREEN}✅ 任务完成{Style.RESET_ALL}")
            
        elif event_type == "error":
            error_msg = data.get("error", "未知错误")
            print(f"{Fore.RED}❌ 错误: {error_msg}{Style.RESET_ALL}")
            
        else:
            # 其他类型的事件
            print(f"{Fore.CYAN}📨 {event_type}: {json.dumps(event_data, ensure_ascii=False, indent=2)}{Style.RESET_ALL}")

class ProteusCliTool:
    """Proteus命令行工具主类"""
    
    MODELS = [
        "workflow", "super-agent", "home", "mcp-agent", 
        "multi-agent", "browser-agent", "deep-research"
    ]
    
    def __init__(self):
        self.config_file = os.path.expanduser("~/.proteus_cli_config.json")
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件"""
        default_config = {
            "base_url": "http://localhost:8000",
            "default_model": "home",
            "default_iterations": 5
        }
        
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    default_config.update(config)
            return default_config
        except Exception:
            return default_config
    
    def _save_config(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  保存配置失败: {str(e)}{Style.RESET_ALL}")
    
    def _print_banner(self):
        """打印工具横幅"""
        banner = f"""
{Fore.CYAN}
╔══════════════════════════════════════════════════════════════╗
║                     Proteus AI 命令行工具                     ║
║                   与Proteus AI系统进行交互                    ║
╚══════════════════════════════════════════════════════════════╝
{Style.RESET_ALL}
"""
        print(banner)
    
    def configure(self, args):
        """配置命令"""
        print(f"{Fore.YELLOW}📋 当前配置:{Style.RESET_ALL}")
        for key, value in self.config.items():
            print(f"  {key}: {value}")
        
        print(f"\n{Fore.CYAN}🔧 更新配置 (直接回车保持当前值):{Style.RESET_ALL}")
        
        # 配置服务器地址
        new_url = input(f"服务器地址 [{self.config['base_url']}]: ").strip()
        if new_url:
            self.config['base_url'] = new_url
        
        # 配置默认模型
        print(f"可用模型: {', '.join(self.MODELS)}")
        new_model = input(f"默认模型 [{self.config['default_model']}]: ").strip()
        if new_model and new_model in self.MODELS:
            self.config['default_model'] = new_model
        elif new_model and new_model not in self.MODELS:
            print(f"{Fore.YELLOW}⚠️  无效的模型，保持原值{Style.RESET_ALL}")
        
        # 配置默认迭代次数
        try:
            new_iterations = input(f"默认迭代次数 [{self.config['default_iterations']}]: ").strip()
            if new_iterations:
                self.config['default_iterations'] = int(new_iterations)
        except ValueError:
            print(f"{Fore.YELLOW}⚠️  无效的迭代次数，保持原值{Style.RESET_ALL}")
        
        self._save_config()
        print(f"{Fore.GREEN}✅ 配置已保存{Style.RESET_ALL}")
    
    async def chat(self, args):
        """聊天命令"""
        # 从命令行参数或配置获取值
        base_url = args.url or self.config.get('base_url', 'http://localhost:8000')
        model = args.model or self.config.get('default_model', 'home')
        iterations = args.iterations or self.config.get('default_iterations', 5)
        
        if not args.text:
            print(f"{Fore.RED}错误: 请提供问题文本{Style.RESET_ALL}")
            return
        
        print(f"{Fore.CYAN}🚀 开始连接 Proteus AI...{Style.RESET_ALL}")
        print(f"   服务器: {base_url}")
        print(f"   模型: {model}")
        print(f"   迭代次数: {iterations}")
        if args.agent_id:
            print(f"   代理ID: {args.agent_id}")
        if args.team_name:
            print(f"   团队名称: {args.team_name}")
        print(f"   问题: {args.text}\n")
        
        async with ProteusClient(base_url) as client:
            # 检查服务状态
            if not await client.health_check():
                print(f"{Fore.RED}❌ 无法连接到服务器 {base_url}{Style.RESET_ALL}")
                print(f"{Fore.YELLOW}💡 请检查服务器是否正在运行，或使用 --url 指定正确的地址{Style.RESET_ALL}")
                return
            
            print(f"{Fore.GREEN}✅ 服务器连接成功{Style.RESET_ALL}")
            
            # 创建聊天会话
            print(f"{Fore.BLUE}📤 发送问题到服务器...{Style.RESET_ALL}")
            chat_id = await client.create_chat(
                text=args.text,
                model=model,
                itecount=iterations,
                agentid=args.agent_id,
                team_name=args.team_name
            )
            
            if not chat_id:
                print(f"{Fore.RED}❌ 创建聊天会话失败{Style.RESET_ALL}")
                return
            
            print(f"{Fore.GREEN}✅ 聊天会话已创建: {chat_id}{Style.RESET_ALL}")
            
            # 开始流式接收响应
            client.stream_chat(chat_id)
    
    def list_models(self, args):
        """列出可用模型"""
        print(f"{Fore.CYAN}📋 可用模型:{Style.RESET_ALL}")
        for model in self.MODELS:
            current = " (当前默认)" if model == self.config.get('default_model') else ""
            print(f"  • {model}{current}")
    
    def interactive(self, args):
        """交互式模式"""
        self._print_banner()
        print(f"{Fore.CYAN}💬 进入交互式模式，输入 'exit' 退出, 'help' 查看帮助{Style.RESET_ALL}\n")
        
        base_url = args.url or self.config.get('base_url', 'http://localhost:8000')
        model = args.model or self.config.get('default_model', 'home')
        iterations = args.iterations or self.config.get('default_iterations', 5)
        
        while True:
            try:
                user_input = input(f"{Fore.GREEN}> {Style.RESET_ALL}").strip()
                
                if user_input.lower() in ['exit', 'quit', '退出']:
                    print(f"{Fore.YELLOW}👋 再见!{Style.RESET_ALL}")
                    break
                elif user_input.lower() in ['help', '帮助']:
                    self._print_interactive_help()
                elif user_input.lower().startswith('model '):
                    new_model = user_input[6:].strip()
                    if new_model in self.MODELS:
                        model = new_model
                        print(f"{Fore.GREEN}✅ 模型已切换到: {model}{Style.RESET_ALL}")
                    else:
                        print(f"{Fore.RED}❌ 无效模型。可用模型: {', '.join(self.MODELS)}{Style.RESET_ALL}")
                elif user_input.lower().startswith('url '):
                    new_url = user_input[4:].strip()
                    if new_url:
                        base_url = new_url
                        print(f"{Fore.GREEN}✅ 服务器地址已更新: {base_url}{Style.RESET_ALL}")
                elif user_input.lower().startswith('iterations '):
                    try:
                        new_iterations = int(user_input[11:].strip())
                        iterations = new_iterations
                        print(f"{Fore.GREEN}✅ 迭代次数已更新: {iterations}{Style.RESET_ALL}")
                    except ValueError:
                        print(f"{Fore.RED}❌ 无效的迭代次数{Style.RESET_ALL}")
                elif user_input:
                    # 处理问题
                    print()
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        # 创建临时args对象
                        temp_args = type('Args', (), {
                            'text': user_input,
                            'url': base_url,
                            'model': model,
                            'iterations': iterations,
                            'agent_id': None,
                            'team_name': None
                        })()
                        
                        loop.run_until_complete(self.chat(temp_args))
                    finally:
                        loop.close()
                    print()
                    
            except KeyboardInterrupt:
                print(f"\n{Fore.YELLOW}👋 再见!{Style.RESET_ALL}")
                break
            except Exception as e:
                print(f"{Fore.RED}❌ 错误: {str(e)}{Style.RESET_ALL}")
    
    def _print_interactive_help(self):
        """打印交互式模式帮助"""
        help_text = f"""
{Fore.CYAN}💡 交互式模式命令:{Style.RESET_ALL}
  • 直接输入问题 - 发送到AI进行处理
  • model <模型名> - 切换AI模型
  • url <地址> - 更改服务器地址
  • iterations <数字> - 设置迭代次数
  • help - 显示此帮助
  • exit - 退出程序

{Fore.YELLOW}当前设置:{Style.RESET_ALL}
  • 模型: {self.config.get('default_model', 'home')}
  • 服务器: {self.config.get('base_url', 'http://localhost:8000')}
  • 迭代次数: {self.config.get('default_iterations', 5)}
"""
        print(help_text)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="Proteus AI 命令行工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
示例用法:
  {sys.argv[0]} chat "你好，请介绍一下自己"
  {sys.argv[0]} chat "分析一下当前市场趋势" --model deep-research
  {sys.argv[0]} chat "创建一个工作流来处理数据" --model workflow --iterations 10
  {sys.argv[0]} interactive
  {sys.argv[0]} configure
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # chat命令
    chat_parser = subparsers.add_parser('chat', help='发送问题给AI')
    chat_parser.add_argument('text', help='要发送的问题文本')
    chat_parser.add_argument('--model', '-m', choices=ProteusCliTool.MODELS, help='AI模型类型')
    chat_parser.add_argument('--url', '-u', help='服务器地址')
    chat_parser.add_argument('--iterations', '-i', type=int, help='迭代次数')
    chat_parser.add_argument('--agent-id', help='代理ID')
    chat_parser.add_argument('--team-name', help='团队名称')
    
    # interactive命令
    interactive_parser = subparsers.add_parser('interactive', help='进入交互式模式')
    interactive_parser.add_argument('--model', '-m', choices=ProteusCliTool.MODELS, help='默认AI模型类型')
    interactive_parser.add_argument('--url', '-u', help='服务器地址')
    interactive_parser.add_argument('--iterations', '-i', type=int, help='默认迭代次数')
    
    # configure命令
    subparsers.add_parser('configure', help='配置工具设置')
    
    # list-models命令
    subparsers.add_parser('list-models', help='列出可用的AI模型')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    tool = ProteusCliTool()
    
    if args.command == 'chat':
        asyncio.run(tool.chat(args))
    elif args.command == 'interactive':
        tool.interactive(args)
    elif args.command == 'configure':
        tool.configure(args)
    elif args.command == 'list-models':
        tool.list_models(args)

if __name__ == "__main__":
    main()