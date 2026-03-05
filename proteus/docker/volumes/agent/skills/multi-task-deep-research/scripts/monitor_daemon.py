#!/usr/bin/env python3
"""
监控守护进程脚本 - 简化版
注意: 主要功能已在 continuous_monitor.py 中实现
本脚本作为兼容性层存在
"""

import os
import sys
import json
from scripts.continuous_monitor import continuous_monitor

def main():
    print("🔍 多任务深度研究监控守护进程")
    print("📋 注意: 主要监控功能请使用 continuous_monitor.py")
    print("=" * 60)
    
    # 检查参数
    if len(sys.argv) < 2:
        print("用法: python monitor_daemon.py <任务目录> [选项]")
        print()
        print("选项:")
        print("  --interval <秒数>   检查间隔（默认: 300秒）")
        print("  --daemon            守护进程模式")
        print("  --help              显示此帮助信息")
        print()
        print("示例:")
        print("  python monitor_daemon.py /app/data/tasks/我的任务 --interval 300")
        print("  python monitor_daemon.py /app/data/tasks/我的任务 --daemon")
        print()
        sys.exit(1)
    
    task_dir = sys.argv[1]
    
    # 解析选项
    interval = 300
    daemon_mode = False
    
    i = 2
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == "--interval" and i + 1 < len(sys.argv):
            try:
                interval = int(sys.argv[i + 1])
                i += 2
            except ValueError:
                print(f"错误: 无效的间隔时间: {sys.argv[i + 1]}")
                sys.exit(1)
        elif arg == "--daemon":
            daemon_mode = True
            i += 1
        elif arg == "--help":
            # 帮助信息已显示
            sys.exit(0)
        else:
            print(f"错误: 未知选项: {arg}")
            sys.exit(1)
    
    if not os.path.exists(task_dir):
        print(f"错误: 任务目录不存在: {task_dir}")
        sys.exit(1)
    
    print(f"📁 监控目录: {task_dir}")
    print(f"⏱  检查间隔: {interval}秒")
    print(f"👻 守护模式: {'是' if daemon_mode else '否'}")
    print("=" * 60)
    
    # 调用 continuous_monitor
    try:
        continuous_monitor(
            task_dir=task_dir,
            interval_seconds=interval,
            max_checks=None,
            adaptive_interval=True
        )
    except KeyboardInterrupt:
        print("\n🛑 用户中断监控")
    except Exception as e:
        print(f"❌ 监控错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
