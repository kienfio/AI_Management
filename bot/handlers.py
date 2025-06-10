import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from common.google_services import GoogleServices
from common.shared import logger

# 初始化Google服务
google_services = GoogleServices()

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/start命令"""
    logger.info(f"收到/start命令，来自用户ID: {update.effective_user.id}, 用户名: {update.effective_user.username}")
    await update.message.reply_text(
        "欢迎使用AI财务管理助手！\n"
        "使用 /help 查看所有可用命令。"
    )
    logger.info(f"已回复/start命令，用户ID: {update.effective_user.id}")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/help命令"""
    logger.info(f"收到/help命令，来自用户ID: {update.effective_user.id}")
    help_text = (
        "可用命令列表：\n"
        "/start - 开始使用机器人\n"
        "/help - 显示此帮助信息\n"
        "/add_expense - 添加支出记录\n"
        "格式：/add_expense 日期 类别 金额 描述 [备注]\n"
        "例如：/add_expense 2024-01-01 餐饮 50 午餐\n"
        "\n"
        "直接发送收据照片，我会自动识别并记录支出。"
    )
    await update.message.reply_text(help_text)
    logger.info(f"已回复/help命令，用户ID: {update.effective_user.id}")

async def add_expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/add_expense命令"""
    logger.info(f"收到/add_expense命令，来自用户ID: {update.effective_user.id}, 参数: {context.args}")
    try:
        # 检查参数数量
        if len(context.args) < 4:
            logger.warning(f"参数不足，用户ID: {update.effective_user.id}")
            await update.message.reply_text(
                "参数不足。请使用以下格式：\n"
                "/add_expense 日期 类别 金额 描述 [备注]\n"
                "例如：/add_expense 2024-01-01 餐饮 50 午餐"
            )
            return

        # 解析参数
        date = context.args[0]
        category = context.args[1]
        amount = float(context.args[2])
        description = context.args[3]
        note = ' '.join(context.args[4:]) if len(context.args) > 4 else ''

        logger.info(f"正在添加支出记录: 日期={date}, 类别={category}, 金额={amount}, 描述={description}")
        
        # 添加支出记录
        if google_services.add_expense(date, category, amount, description, note):
            logger.info(f"支出记录添加成功，用户ID: {update.effective_user.id}")
            await update.message.reply_text(
                f"✅ 支出记录已添加\n"
                f"日期：{date}\n"
                f"类别：{category}\n"
                f"金额：{amount}\n"
                f"描述：{description}\n"
                f"备注：{note}"
            )
        else:
            logger.error(f"支出记录添加失败，用户ID: {update.effective_user.id}")
            await update.message.reply_text("❌ 添加支出记录失败，请稍后重试")

    except ValueError:
        logger.error(f"金额格式错误，用户ID: {update.effective_user.id}")
        await update.message.reply_text("金额格式错误，请输入有效的数字")
    except Exception as e:
        logger.error(f"处理add_expense命令时出错: {e}, 用户ID: {update.effective_user.id}")
        await update.message.reply_text("发生错误，请稍后重试")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理收据照片"""
    logger.info(f"收到照片，来自用户ID: {update.effective_user.id}")
    try:
        # 获取照片文件
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # 下载照片
        photo_path = f"temp_{photo.file_id}.jpg"
        logger.info(f"正在下载照片: {photo_path}")
        await file.download_to_drive(photo_path)
        
        try:
            # 上传到Google Drive
            logger.info(f"正在上传照片到Google Drive")
            file_url = google_services.upload_file(photo_path, f"receipt_{photo.file_id}.jpg")
            
            if file_url:
                logger.info(f"照片上传成功，URL: {file_url}")
                await update.message.reply_text(
                    "✅ 收据已上传\n"
                    "请使用 /add_expense 命令添加支出记录，并在备注中包含此链接：\n"
                    f"{file_url}"
                )
            else:
                logger.error(f"照片上传失败，用户ID: {update.effective_user.id}")
                await update.message.reply_text("❌ 收据上传失败，请稍后重试")
                
        finally:
            # 清理临时文件
            if os.path.exists(photo_path):
                os.remove(photo_path)
                logger.info(f"临时文件已删除: {photo_path}")
                
    except Exception as e:
        logger.error(f"处理照片时出错: {e}, 用户ID: {update.effective_user.id}")
        await update.message.reply_text("处理照片时出错，请稍后重试")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理错误"""
    logger.error(f"更新 {update} 导致错误 {context.error}")
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text("抱歉，处理您的请求时出错了。请稍后重试。")
    except Exception as e:
        logger.error(f"发送错误消息时出错: {e}")

# 导出所有处理函数
__all__ = [
    'start_handler',
    'help_handler',
    'add_expense_handler',
    'photo_handler',
    'error_handler'
] 
