import os
import asyncio
from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    CallbackQueryHandler
)
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
from common.shared import logger, update_bot_status

# 全局应用实例
application = None

async def setup_webhook():
    """设置webhook"""
    global application
    
    try:
        # 获取Telegram令牌
        telegram_token = os.getenv('TELEGRAM_TOKEN')
        if not telegram_token:
            raise ValueError("缺少TELEGRAM_TOKEN环境变量")
        
        # 获取服务URL
        service_url = os.getenv('SERVICE_URL')
        if not service_url:
            # 尝试构建URL
            port = os.getenv('PORT', '5000')
            service_url = f"https://ai-financial-bot.onrender.com"
            logger.warning(f"未设置SERVICE_URL环境变量，使用默认值: {service_url}")
        
        webhook_url = f"{service_url}/webhook/{telegram_token}"
        logger.info(f"设置webhook URL: {webhook_url}")
        
        # 创建应用实例
        logger.info("创建Telegram应用实例...")
        application = Application.builder().token(telegram_token).build()
        
        # 添加处理程序
        logger.info("注册命令处理程序...")
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
            fallbacks=[CommandHandler("cancel", cancel_handler)],
            name="settings_conversation"
        )
        application.add_handler(settings_conv_handler)
        
        application.add_handler(MessageHandler(filters.PHOTO, photo_handler))
        
        # 添加错误处理程序
        application.add_error_handler(error_handler)
        
        # 初始化和启动应用
        logger.info("正在启动机器人...")
        await application.initialize()
        
        # 设置webhook
        await application.bot.set_webhook(url=webhook_url)
        logger.info(f"Webhook已设置: {webhook_url}")
        
        # 启动应用
        await application.start()
        update_bot_status(running=True)
        logger.info("机器人已启动")
        
        return True
    except Exception as e:
        logger.error(f"设置webhook时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def process_update(update_json):
    """处理来自webhook的更新"""
    global application
    
    if not application:
        logger.error("应用实例未初始化，无法处理更新")
        return False
    
    try:
        logger.info(f"收到webhook更新: {update_json}")
        await application.process_update(Update.de_json(update_json, application.bot))
        return True
    except Exception as e:
        logger.error(f"处理更新时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

async def shutdown_webhook():
    """关闭webhook"""
    global application
    
    if not application:
        logger.info("应用实例未初始化，无需关闭")
        return
    
    try:
        logger.info("正在关闭webhook...")
        
        # 删除webhook
        try:
            logger.info("正在删除webhook...")
            await application.bot.delete_webhook()
            logger.info("Webhook已删除")
        except Exception as e:
            logger.error(f"删除webhook时出错: {e}")
        
        # 停止应用
        try:
            logger.info("正在停止应用...")
            await application.stop()
            logger.info("应用已停止")
        except Exception as e:
            logger.error(f"停止应用时出错: {e}")
        
        # 关闭应用
        try:
            logger.info("正在关闭应用...")
            await application.shutdown()
            logger.info("应用已关闭")
        except Exception as e:
            logger.error(f"关闭应用时出错: {e}")
        
        # 更新状态
        update_bot_status(running=False)
        logger.info("Webhook已完全关闭")
        
        # 清除全局引用
        application = None
    except Exception as e:
        logger.error(f"关闭webhook时出错: {e}")
        import traceback
        logger.error(traceback.format_exc()) 
