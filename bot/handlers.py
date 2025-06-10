import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from common.google_services import GoogleServices

# 配置日志
logger = logging.getLogger(__name__)

# 初始化Google服务
google_services = GoogleServices()

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/start命令"""
    await update.message.reply_text(
        "欢迎使用AI财务管理助手！\n"
        "使用 /help 查看所有可用命令。"
    )

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/help命令"""
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

async def add_expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/add_expense命令"""
    try:
        # 检查参数数量
        if len(context.args) < 4:
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

        # 添加支出记录
        if google_services.add_expense(date, category, amount, description, note):
            await update.message.reply_text(
                f"✅ 支出记录已添加\n"
                f"日期：{date}\n"
                f"类别：{category}\n"
                f"金额：{amount}\n"
                f"描述：{description}\n"
                f"备注：{note}"
            )
        else:
            await update.message.reply_text("❌ 添加支出记录失败，请稍后重试")

    except ValueError:
        await update.message.reply_text("金额格式错误，请输入有效的数字")
    except Exception as e:
        logger.error(f"处理add_expense命令时出错: {e}")
        await update.message.reply_text("发生错误，请稍后重试")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理收据照片"""
    try:
        # 获取照片文件
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        
        # 下载照片
        photo_path = f"temp_{photo.file_id}.jpg"
        await file.download_to_drive(photo_path)
        
        try:
            # 上传到Google Drive
            file_url = google_services.upload_file(photo_path, f"receipt_{photo.file_id}.jpg")
            
            if file_url:
                await update.message.reply_text(
                    "✅ 收据已上传\n"
                    "请使用 /add_expense 命令添加支出记录，并在备注中包含此链接：\n"
                    f"{file_url}"
                )
            else:
                await update.message.reply_text("❌ 收据上传失败，请稍后重试")
                
        finally:
            # 清理临时文件
            if os.path.exists(photo_path):
                os.remove(photo_path)
                
    except Exception as e:
        logger.error(f"处理照片时出错: {e}")
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