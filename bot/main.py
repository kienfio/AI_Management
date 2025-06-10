import os
import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)
from bot.handlers import (
    start_handler,
    help_handler,
    add_expense_handler,
    photo_handler,
    error_handler
)

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def run_bot():
    """运行机器人"""
    try:
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 获取Telegram令牌
        telegram_token = os.getenv('TELEGRAM_TOKEN')
        if not telegram_token:
            raise ValueError("缺少TELEGRAM_TOKEN环境变量")
        
        # 创建应用实例
        application = Application.builder().token(telegram_token).build()
        
        # 添加处理程序
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("help", help_handler))
        application.add_handler(CommandHandler("add_expense", add_expense_handler))
        application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
        
        # 添加错误处理程序
        application.add_error_handler(error_handler)
        
        logger.info("机器人初始化成功")
        
        # 使用当前事件循环运行机器人
        await application.initialize()
        await application.start()
        await application.run_polling(
            allowed_updates=["message", "callback_query", "chat_member"],
            drop_pending_updates=True,
            close_loop=False
        )
    except Exception as e:
        logger.error(f"运行机器人时出错: {e}")
        raise
    finally:
        # 清理
        try:
            if 'application' in locals():
                await application.stop()
                await application.shutdown()
        except Exception as e:
            logger.error(f"关闭机器人时出错: {e}")
        
        # 清理当前循环
        if 'loop' in locals() and loop and not loop.is_closed():
            loop.close()

if __name__ == '__main__':
    # 直接运行此文件时的入口点
    asyncio.run(run_bot())

# 明确导出的函数
__all__ = ['run_bot'] 
