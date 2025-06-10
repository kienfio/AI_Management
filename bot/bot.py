import os
import logging
import asyncio
from telegram.ext import (
    ApplicationBuilder, 
    CommandHandler, 
    MessageHandler, 
    filters, 
    ConversationHandler,
    CallbackQueryHandler
)
from common.shared import logger
from bot.handlers import (
    start_handler, 
    help_handler, 
    add_expense_handler, 
    photo_handler, 
    cancel_handler,
    categories_handler,
    settings_handler,
    settings_button_handler,
    agent_name_handler,
    agent_ic_handler,
    supplier_name_handler,
    supplier_category_handler,
    personal_name_handler,
    report_handler,
    error_handler,
    MAIN_MENU,
    WAITING_AGENT_NAME,
    WAITING_AGENT_IC,
    WAITING_SUPPLIER_NAME,
    WAITING_SUPPLIER_CATEGORY,
    WAITING_PERSONAL_NAME
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
    application.add_handler(CommandHandler("SaleInvoice", add_expense_handler))
    application.add_handler(CommandHandler("cancel", cancel_handler))
    application.add_handler(CommandHandler("Categories", categories_handler))
    application.add_handler(CommandHandler("Report", report_handler))
    
    # 注册设置会话处理器
    settings_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("Settings", settings_handler)],
        states={
            MAIN_MENU: [
                CallbackQueryHandler(settings_button_handler)
            ],
            WAITING_AGENT_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_name_handler)
            ],
            WAITING_AGENT_IC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, agent_ic_handler)
            ],
            WAITING_SUPPLIER_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, supplier_name_handler)
            ],
            WAITING_SUPPLIER_CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, supplier_category_handler)
            ],
            WAITING_PERSONAL_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, personal_name_handler)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    application.add_handler(settings_conv_handler)
    
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
