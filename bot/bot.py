import os
import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters
from common.shared import logger
from bot.handlers import (
    start_handler, 
    help_handler, 
    add_expense_handler, 
    photo_handler, 
    cancel_handler,
    categories_handler,
    settings_handler,
    report_handler,
    error_handler
)

# 获取Telegram Bot令牌
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("未设置TELEGRAM_BOT_TOKEN环境变量")

def create_application():
    """创建Telegram应用程序实例"""
    logger.info("正在创建Telegram Bot应用程序...")
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    # 注册命令处理程序
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("add_expense", add_expense_handler))
    application.add_handler(CommandHandler("cancel", cancel_handler))
    application.add_handler(CommandHandler("categories", categories_handler))
    application.add_handler(CommandHandler("settings", settings_handler))
    application.add_handler(CommandHandler("report", report_handler))
    
    # 注册消息处理程序
    application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    
    # 注册错误处理程序
    application.add_error_handler(error_handler)
    
    logger.info("Telegram Bot应用程序创建完成")
    return application

async def start_polling():
    """启动轮询模式"""
    logger.info("正在启动Telegram Bot（轮询模式）...")
    application = create_application()
    await application.initialize()
    await application.start_polling()
    logger.info("Telegram Bot已启动（轮询模式）")
    
    # 保持运行直到手动停止
    try:
        await application.updater.start_polling()
        await asyncio.Event().wait()  # 等待直到被取消
    finally:
        await application.stop()
        logger.info("Telegram Bot已停止")

# 导出应用程序创建函数
__all__ = ["create_application", "start_polling"] 