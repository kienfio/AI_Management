#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
年度自动化任务调度器启动脚本
"""

import os
import sys
import signal
import time
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduler-runner")

def signal_handler(sig, frame):
    """处理SIGINT信号（Ctrl+C）"""
    print("\n正在停止任务调度器...")
    if 'task_manager' in globals() and task_manager:
        task_manager.stop_scheduler()
    sys.exit(0)

if __name__ == "__main__":
    try:
        from scheduled_tasks import task_manager, start_scheduler, manual_archive, manual_initialize
        
        # 解析命令行参数
        if len(sys.argv) > 1:
            command = sys.argv[1].lower()
            
            if command == "start":
                print("启动年度自动化任务调度器...")
                signal.signal(signal.SIGINT, signal_handler)
                
                # 启动调度器
                start_scheduler()
                
                # 打印当前调度的任务
                print("\n已配置以下定时任务:")
                print("1. 年度归档任务 - 每年12月31日23:00执行")
                print("2. 新年度初始化任务 - 每年1月1日00:05执行")
                print("3. 心跳检查任务 - 每天09:00执行")
                
                # 保持程序运行
                print("\n调度器正在运行中...")
                print("(按Ctrl+C停止程序)")
                while True:
                    time.sleep(1)
                    
            elif command == "archive":
                year = int(sys.argv[2]) if len(sys.argv) > 2 else None
                target_year = year if year else datetime.now().year - 1
                print(f"执行{target_year}年度归档任务...")
                result = manual_archive(target_year)
                print("完成" if result else "失败")
                
            elif command == "initialize":
                year = int(sys.argv[2]) if len(sys.argv) > 2 else None
                target_year = year if year else datetime.now().year
                print(f"执行{target_year}年度初始化任务...")
                result = manual_initialize(target_year)
                print("完成" if result else "失败")
                
            elif command == "test":
                print("运行测试...")
                # 测试调度器
                start_scheduler()
                # 等待几秒以确保调度器启动
                time.sleep(3)
                # 运行心跳任务
                result = task_manager.daily_heartbeat_task()
                print("心跳测试: ", "成功" if result else "失败")
                # 停止调度器
                task_manager.stop_scheduler()
                print("测试完成")
                
            else:
                print(f"未知命令: {command}")
                print("可用命令: start, archive, initialize, test")
        else:
            print("""
年度自动化任务调度器
用法:
  python start_scheduler.py start         - 启动任务调度器
  python start_scheduler.py archive [年份] - 手动执行归档任务
  python start_scheduler.py initialize [年份] - 手动执行初始化任务
  python start_scheduler.py test          - 运行测试
            """)
    
    except ImportError as e:
        logger.error(f"导入模块失败: {e}")
        print(f"错误: {e}")
        print("请确保scheduled_tasks.py文件存在并且安装了所有依赖")
        
    except Exception as e:
        logger.error(f"运行错误: {e}")
        import traceback
        traceback.print_exc()
        print(f"发生错误: {e}") 