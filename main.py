import os
import logging
from dotenv import load_dotenv
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from handlers import start_handler, help_handler, cancel_command, unknown_command, error_handler
from google_services import GoogleServices

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    # 加载环境变量
    load_dotenv()
    
    # 获取Telegram令牌
    token = os.getenv("TELEGRAM_TOKEN")
    if not token:
        logger.error("未找到TELEGRAM_TOKEN环境变量")
        return
    
    # 初始化Google服务
    google_services = GoogleServices()
    
    # 创建应用
    application = Application.builder().token(token).build()
    
    # 添加命令处理器
    application.add_handler(CommandHandler("start", start_handler))
    application.add_handler(CommandHandler("help", help_handler))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # 添加新的命令处理器
    application.add_handler(CommandHandler("sales", lambda update, context: update.message.reply_text("销售记录功能正在开发中...")))
    application.add_handler(CommandHandler("cost", lambda update, context: update.message.reply_text("成本管理功能正在开发中...")))
    application.add_handler(CommandHandler("settings", lambda update, context: update.message.reply_text("系统设置功能正在开发中...")))
    application.add_handler(CommandHandler("report", lambda update, context: update.message.reply_text("报表功能正在开发中...")))
    
    # 处理未知命令
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # 设置错误处理器
    application.add_error_handler(error_handler)
    
    # 启动机器人
    logger.info("机器人已启动")
    application.run_polling()

if __name__ == "__main__":
    main() 