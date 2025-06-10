import os
import logging
import time
import signal
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ConversationHandler
from handlers import (start_handler, help_handler, settings_handler, cancel_command, 
                     unknown_command, error_handler, button_callback_handler, 
                     person_name_handler, agent_name_handler, agent_ic_handler, 
                     supplier_product_handler, conversation_timeout, PERSON_NAME, AGENT_NAME, AGENT_IC, 
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

def shutdown_handler(signum, frame):
    """处理程序关闭信号"""
    logger.info(f"收到信号 {signum}，正在关闭...")
    if application:
        application.shutdown()
    logger.info("机器人已关闭")

def main():
    """主函数，启动Telegram机器人"""
    global application
    
    # 加载环境变量
    load_dotenv()
    
    # 获取Telegram令牌
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("未找到TELEGRAM_TOKEN环境变量")
        return
    
    # 添加延迟，确保之前的连接已超时
    logger.info("等待2秒钟以确保之前的连接已超时...")
    time.sleep(2)
    
    # 初始化Google服务
    try:
        google_services = GoogleServices()
    except Exception as e:
        logger.error(f"初始化Google服务时出错: {e}")
    
    # 创建应用
    application = Application.builder().token(token).build()
    
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
        conversation_timeout=300,  # 5分钟超时
        # 添加超时处理函数
        timeout_handler=conversation_timeout
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
    
    # 设置信号处理
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    # 启动机器人
    logger.info("机器人已启动")
    try:
        # 设置允许同时更新
        application.run_polling(allowed_updates=["message", "callback_query", "chat_member"], drop_pending_updates=True)
    except Exception as e:
        logger.error(f"运行时错误: {e}")
    finally:
        # 确保应用程序正确关闭
        logger.info("正在关闭机器人...")
        if application:
            application.shutdown()

# 仅当直接运行此脚本时执行main函数
if __name__ == "__main__":
    main() 
