import os
import asyncio
import requests
from telegram import Update, Bot
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
from common.shared import logger, update_bot_status

async def check_telegram_connection(token):
    """检查与Telegram API的连接"""
    try:
        bot = Bot(token)
        me = await bot.get_me()
        logger.info(f"成功连接到Telegram API，机器人信息: {me.first_name} (@{me.username})")
        return True
    except Exception as e:
        logger.error(f"连接Telegram API失败: {e}")
        return False

async def run_bot():
    """运行机器人"""
    application = None
    loop = None
    
    try:
        logger.info("正在初始化机器人...")
        # 创建新的事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 获取Telegram令牌
        telegram_token = os.getenv('TELEGRAM_TOKEN')
        if not telegram_token:
            raise ValueError("缺少TELEGRAM_TOKEN环境变量")
        
        logger.info(f"使用令牌: {telegram_token[:5]}...{telegram_token[-5:]}")
        
        # 检查网络连接
        logger.info("检查网络连接...")
        try:
            response = requests.get('https://api.telegram.org', timeout=5)
            logger.info(f"Telegram API 可访问，状态码: {response.status_code}")
        except Exception as e:
            logger.warning(f"无法连接到Telegram API: {e}")
        
        # 检查Telegram连接
        if not await check_telegram_connection(telegram_token):
            logger.error("无法验证Telegram令牌，请检查令牌是否有效")
        
        # 创建应用实例
        logger.info("创建Telegram应用实例...")
        application = Application.builder().token(telegram_token).build()
        
        # 添加处理程序
        logger.info("注册命令处理程序...")
        application.add_handler(CommandHandler("start", start_handler))
        application.add_handler(CommandHandler("help", help_handler))
        application.add_handler(CommandHandler("add_expense", add_expense_handler))
        application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
        
        # 添加错误处理程序
        application.add_error_handler(error_handler)
        
        # 初始化和启动应用
        logger.info("正在启动机器人...")
        await application.initialize()
        await application.start()
        
        # 更新状态
        logger.info("机器人初始化成功，开始接收消息")
        update_bot_status(running=True)
        
        # 运行轮询
        logger.info("开始轮询更新...")
        await application.run_polling(
            allowed_updates=["message", "callback_query", "chat_member"],
            drop_pending_updates=True,
            close_loop=False,
            pool_timeout=10.0,
            read_timeout=15.0,
            connect_timeout=15.0
        )
    except ValueError as e:
        # 配置错误，记录但不需要详细堆栈
        logger.error(f"配置错误: {e}")
    except Exception as e:
        # 其他错误，记录详细堆栈
        logger.error(f"运行机器人时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        # 清理应用
        if application:
            try:
                logger.info("正在关闭Telegram应用...")
                # 确保这些协程被正确等待
                if hasattr(application, 'stop') and callable(application.stop):
                    await application.stop()
                if hasattr(application, 'shutdown') and callable(application.shutdown):
                    await application.shutdown()
                logger.info("Telegram应用已关闭")
            except Exception as e:
                logger.error(f"关闭机器人时出错: {e}")
        
        # 清理事件循环
        if loop and not loop.is_closed():
            try:
                logger.info("正在关闭事件循环...")
                loop.stop()
                loop.close()
                logger.info("事件循环已关闭")
            except Exception as e:
                logger.error(f"关闭事件循环时出错: {e}")
        
        update_bot_status(running=False)
        logger.info("机器人已停止运行")

if __name__ == '__main__':
    # 直接运行此文件时的入口点
    asyncio.run(run_bot())

# 明确导出的函数
__all__ = ['run_bot'] 
