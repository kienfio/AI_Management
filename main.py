import os
import logging
import time
import signal
import asyncio
import atexit
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from handlers import (start_handler, help_handler, settings_handler, cancel_command, 
                     unknown_command, error_handler, button_callback_handler, 
                     person_name_handler, agent_name_handler, agent_ic_handler, 
                     supplier_product_handler, PERSON_NAME, AGENT_NAME, AGENT_IC, 
                     SUPPLIER_CATEGORY, SUPPLIER_PRODUCT)
from google_services import GoogleServices

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 全局应用实例
application = None

async def cleanup_webhook():
    """清理webhook设置"""
    global application
    if application:
        try:
            # 删除webhook设置
            await application.bot.delete_webhook()
            logger.info("成功清理webhook设置")
        except Exception as e:
            logger.error(f"清理webhook时出错: {e}")

async def shutdown_handler(signum, frame):
    """处理程序关闭信号"""
    global application
    logger.info(f"收到信号 {signum}，正在关闭...")
    if application:
        try:
            # 停止更新
            application.stop_running()
            # 清理webhook
            await cleanup_webhook()
            # 关闭应用
            await application.shutdown()
            # 等待所有任务完成
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("机器人已正确关闭")
        except Exception as e:
            logger.error(f"关闭过程中出错: {e}")
    else:
        logger.info("没有运行中的应用实例")

def register_shutdown_handlers():
    """注册关闭处理程序"""
    # 注册信号处理
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda s, f: asyncio.run(shutdown_handler(s, f)))
    
    # 注册退出处理
    atexit.register(lambda: asyncio.run(cleanup_webhook()))

async def initialize_bot(token):
    """初始化机器人"""
    global application
    
    try:
        # 创建新的应用实例
        application = Application.builder().token(token).build()
        
        # 清理之前的webhook设置
        await cleanup_webhook()
        
        # 初始化Google服务（设置为非必需）
        try:
            google_services = GoogleServices(required=False)
        except Exception as e:
            logger.warning(f"Google服务初始化失败，某些功能可能不可用: {e}")
            google_services = None
        
        # 添加对话处理器 - 设置功能
        settings_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("settings", settings_handler),
                CallbackQueryHandler(button_callback_handler, pattern="^settings")
            ],
            states={
                PERSON_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, person_name_handler)],
                AGENT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, agent_name_handler)],
                AGENT_IC: [MessageHandler(filters.TEXT & ~filters.COMMAND, agent_ic_handler)],
                SUPPLIER_CATEGORY: [CallbackQueryHandler(button_callback_handler)],
                SUPPLIER_PRODUCT: [MessageHandler(filters.TEXT & ~filters.COMMAND, supplier_product_handler)],
            },
            fallbacks=[CommandHandler("cancel", cancel_command)],
            name="settings_conversation",
            persistent=False,
            per_message=True
        )
        
        # 添加命令处理器
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("help", help_handler))
        application.add_handler(CommandHandler("cancel", cancel_command))
        
        # 添加对话处理器
        application.add_handler(settings_conv_handler)
        
        # 添加按钮回调处理器 - 仅处理非settings开头的回调
        application.add_handler(CallbackQueryHandler(button_callback_handler, pattern="^(?!settings).*$"))
        
        # 添加新的命令处理器
        application.add_handler(CommandHandler("sales", lambda update, context: update.message.reply_text("销售记录功能正在开发中...")))
        application.add_handler(CommandHandler("cost", lambda update, context: update.message.reply_text("成本管理功能正在开发中...")))
        application.add_handler(CommandHandler("report", lambda update, context: update.message.reply_text("报表功能正在开发中...")))
        
        # 处理未知命令
        application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
        
        # 设置错误处理器
        application.add_error_handler(error_handler)
        
        return True
    except Exception as e:
        logger.error(f"初始化机器人时出错: {e}")
        return False

def main():
    """主函数，启动Telegram机器人"""
    # 加载环境变量
    load_dotenv()
    
    # 获取Telegram令牌
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("未找到TELEGRAM_TOKEN环境变量")
        return

    try:
        # 注册关闭处理程序
        register_shutdown_handlers()
        
        # 初始化机器人
        if not asyncio.run(initialize_bot(token)):
            logger.error("机器人初始化失败")
            return
        
        # 启动机器人
        logger.info("机器人正在启动...")
        application.run_polling(
            allowed_updates=["message", "callback_query", "chat_member"],
            drop_pending_updates=True,
            close_loop=False
        )
        
    except Exception as e:
        logger.error(f"运行时错误: {e}")
    finally:
        # 确保应用程序正确关闭
        if application:
            try:
                asyncio.run(shutdown_handler(signal.SIGTERM, None))
            except Exception as e:
                logger.error(f"关闭机器人时出错: {e}")

if __name__ == "__main__":
    main()
