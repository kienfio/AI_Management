#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时任务模块
负责管理系统的各种定时任务，包括年度归档和新年度初始化
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any
import schedule
import threading
import json
import gspread
from google.oauth2.service_account import Credentials
import shutil
import dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scheduler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("scheduler")

# 加载环境变量
dotenv.load_dotenv('env.example')

# 导入自定义模块
try:
    from google_sheets import GoogleSheetsManager
except ImportError:
    logger.error("无法导入GoogleSheetsManager，请确保google_sheets.py文件存在")

class ScheduledTasksManager:
    """计划任务管理器"""
    
    def __init__(self):
        """初始化任务管理器"""
        self.sheets_manager = None
        self.stop_flag = threading.Event()
        try:
            self.sheets_manager = GoogleSheetsManager()
            logger.info("✅ 计划任务管理器初始化成功")
        except Exception as e:
            logger.error(f"❌ 计划任务管理器初始化失败: {e}")
    
    def start_scheduler(self):
        """启动任务调度器"""
        try:
            # 设置任务
            # 每年12月31日23:00执行年度归档
            schedule.every().day.at("23:00").do(self._check_and_run_yearly_archive)
            
            # 每年1月1日00:05执行新年度初始化
            schedule.every().day.at("00:05").do(self._check_and_run_yearly_init)
            
            # 同时添加一个每天运行的测试任务，方便检查调度器是否正常运行
            schedule.every().day.at("09:00").do(self.daily_heartbeat_task)
            
            logger.info("✅ 任务调度器已启动")
            
            # 开始运行调度循环
            threading.Thread(target=self._run_scheduler, daemon=True).start()
            
            return True
        except Exception as e:
            logger.error(f"❌ 启动任务调度器失败: {e}")
            return False
    
    def _run_scheduler(self):
        """运行调度循环"""
        while not self.stop_flag.is_set():
            schedule.run_pending()
            time.sleep(60)  # 每分钟检查一次
    
    def stop_scheduler(self):
        """停止任务调度器"""
        self.stop_flag.set()
        logger.info("✅ 任务调度器已停止")
    
    def yearly_archiving_task(self) -> bool:
        """年度归档任务 - 在每年年底执行"""
        try:
            current_year = datetime.now().year
            logger.info(f"开始执行{current_year}年度归档任务")
            
            # 确保Sheets Manager实例可用
            if not self.sheets_manager:
                self.sheets_manager = GoogleSheetsManager()
            
            # 调用GoogleSheetsManager中的归档方法
            result = self.sheets_manager.archive_yearly_data(current_year)
            
            if result:
                logger.info(f"✅ {current_year}年度归档任务完成")
                logger.info(f"已归档销售记录: {result['archived_sales']} 条")
                logger.info(f"已归档支出记录: {result['archived_expenses']} 条")
                logger.info(f"已创建归档表: {', '.join(result['archive_sheets'])}")
                return True
            else:
                logger.error(f"❌ {current_year}年度归档任务失败")
                return False
            
        except Exception as e:
            logger.error(f"❌ 年度归档任务失败: {e}")
            return False
    
    def new_year_initialization_task(self) -> bool:
        """新年度初始化任务 - 在每年年初执行"""
        try:
            new_year = datetime.now().year
            logger.info(f"开始执行{new_year}年度初始化任务")
            
            # 确保Sheets Manager实例可用
            if not self.sheets_manager:
                self.sheets_manager = GoogleSheetsManager()
            
            # 调用GoogleSheetsManager中的初始化方法
            result = self.sheets_manager.initialize_new_year(new_year)
            
            if result:
                logger.info(f"✅ {new_year}年度初始化任务完成")
                logger.info(f"已创建报表: {', '.join(result['initialized_reports'])}")
                return True
            else:
                logger.error(f"❌ {new_year}年度初始化任务失败")
                return False
            
        except Exception as e:
            logger.error(f"❌ 新年度初始化任务失败: {e}")
            return False
    
    def daily_heartbeat_task(self) -> bool:
        """每日心跳任务 - 确认调度器正常运行"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        logger.info(f"📢 调度器心跳检查 - {current_time}")
        return True
    
    def run_archiving_now(self, year: int = None) -> bool:
        """立即执行归档任务（用于测试或手动触发）"""
        if year is None:
            year = datetime.now().year - 1  # 默认归档去年的数据
        
        logger.info(f"手动触发{year}年归档任务")
        return self.yearly_archiving_task()
    
    def run_initialization_now(self, year: int = None) -> bool:
        """立即执行新年初始化任务（用于测试或手动触发）"""
        if year is None:
            year = datetime.now().year  # 默认初始化今年
        
        logger.info(f"手动触发{year}年初始化任务")
        return self.new_year_initialization_task()
    
    def _check_and_run_yearly_archive(self) -> bool:
        """检查是否为12月31日，如果是则执行年度归档任务"""
        today = datetime.now()
        if today.month == 12 and today.day == 31:
            logger.info("今天是12月31日，执行年度归档任务")
            return self.yearly_archiving_task()
        return True
    
    def _check_and_run_yearly_init(self) -> bool:
        """检查是否为1月1日，如果是则执行新年度初始化任务"""
        today = datetime.now()
        if today.month == 1 and today.day == 1:
            logger.info("今天是1月1日，执行新年度初始化任务")
            return self.new_year_initialization_task()
        return True

# 创建全局实例
task_manager = ScheduledTasksManager()

def start_scheduler():
    """启动计划任务"""
    return task_manager.start_scheduler()

def manual_archive(year: int = None):
    """手动执行归档"""
    return task_manager.run_archiving_now(year)

def manual_initialize(year: int = None):
    """手动执行初始化"""
    return task_manager.run_initialization_now(year)

if __name__ == "__main__":
    """直接运行此脚本时执行"""
    import sys
    
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "start":
            print("启动定时任务调度器...")
            start_scheduler()
            
            # 保持程序运行
            try:
                print("按Ctrl+C停止程序...")
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("程序已停止")
                task_manager.stop_scheduler()
                
        elif command == "archive":
            year = int(sys.argv[2]) if len(sys.argv) > 2 else None
            print(f"执行归档任务，年份：{year or '当前年份'}...")
            result = manual_archive(year)
            print("完成" if result else "失败")
            
        elif command == "initialize":
            year = int(sys.argv[2]) if len(sys.argv) > 2 else None
            print(f"执行初始化任务，年份：{year or '当前年份'}...")
            result = manual_initialize(year)
            print("完成" if result else "失败")
            
        else:
            print(f"未知命令: {command}")
            print("可用命令: start, archive, initialize")
    else:
        print("使用方法:")
        print("  python scheduled_tasks.py start - 启动任务调度器")
        print("  python scheduled_tasks.py archive [年份] - 执行归档任务")
        print("  python scheduled_tasks.py initialize [年份] - 执行初始化任务") 
