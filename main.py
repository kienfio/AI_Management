#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
销售管理 Telegram Bot
主程序入口 - Bot 启动和配置
"""

import logging
import os
import base64
import json
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# 检查Google凭证
print("===== 环境变量检查 =====")
print(f"GOOGLE_CREDENTIALS_BASE64: {'✅ 已设置' if os.getenv('GOOGLE_CREDENTIALS_BASE64') else '❌ 未设置'}")
print(f"GOOGLE_SHEET_ID: {'✅ 已设置' if os.getenv('GOOGLE_SHEET_ID') else '❌ 未设置'}")
print(f"TELEGRAM_TOKEN: {'✅ 已设置' if os.getenv('TELEGRAM_TOKEN') else '❌ 未设置'}")

# 先检查凭证再导入配置
from config import BOT_TOKEN
from telegram_handlers import (
    # 基础命令
    start_command, help_command, cancel_command, unknown_command, error_handler,
    # 销售记录
    sales_conversation, sales_callback_handler,
    # 费用管理  
    expenses_conversation, expenses_callback_handler,
    # 报表生成
    report_conversation, report_callback_handler,
    # 系统设置
    settings_conversation, settings_callback_handler,
    # 通用回调处理
    general_callback_handler, close_session_handler
)

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """主函数 - 启动 Bot"""
    
    # 创建 Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 注册基础命令处理器
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # 注册会话处理器（按优先级顺序）
    application.add_handler(sales_conversation)
    application.add_handler(expenses_conversation)  
    application.add_handler(report_conversation)
    application.add_handler(settings_conversation)
    
    # 注册回调查询处理器
    application.add_handler(CallbackQueryHandler(sales_callback_handler, pattern='^sales_'))
    application.add_handler(CallbackQueryHandler(expenses_callback_handler, pattern='^expenses_'))
    application.add_handler(CallbackQueryHandler(report_callback_handler, pattern='^report_'))
    application.add_handler(CallbackQueryHandler(settings_callback_handler, pattern='^settings_'))
    application.add_handler(CallbackQueryHandler(close_session_handler, pattern='^close_session$'))
    application.add_handler(CallbackQueryHandler(general_callback_handler))
    
    # 注册未知命令处理器
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # 注册错误处理器
    application.add_error_handler(error_handler)
    
    # 启动 Bot
    logger.info("🚀 销售管理 Bot 启动中...")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == '__main__':
    main()
