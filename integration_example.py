"""
这个示例展示如何将GoogleDriveUploader集成到现有的Telegram机器人中
"""

import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from google_drive_uploader import drive_uploader

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def cost_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理收据上传"""
    # 检查是否有照片或文件
    if update.message.photo:
        # 获取最大尺寸的照片
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # 获取文件对象
        file = await context.bot.get_file(file_id)
        
        # 创建临时文件名
        file_name = f"receipt_{file_id}.jpg"
        local_path = os.path.join("temp", file_name)
        
        # 确保临时目录存在
        os.makedirs("temp", exist_ok=True)
        
        # 下载文件
        await file.download_to_drive(local_path)
        
        # 获取费用类型
        expense_type = context.user_data.get('cost_type', 'Purchasing')
        
        try:
            # 上传到Google Drive
            result = drive_uploader.upload_receipt(local_path, expense_type)
            
            # 保存收据链接到用户数据
            context.user_data['receipt_link'] = result['public_link']
            
            # 通知用户
            await update.message.reply_text(
                f"✅ 收据已上传成功!\n"
                f"📎 链接: {result['public_link']}"
            )
            
            # 清理临时文件
            os.remove(local_path)
            
            # 继续到下一步
            return await show_cost_confirmation(update, context)
            
        except Exception as e:
            logger.error(f"上传收据失败: {e}")
            await update.message.reply_text(
                "❌ 收据上传失败，请稍后再试。"
            )
            # 清理临时文件
            if os.path.exists(local_path):
                os.remove(local_path)
            
            # 继续到下一步，但没有收据链接
            return await show_cost_confirmation(update, context)
    
    elif update.message.document:
        # 处理文档上传
        document = update.message.document
        file_id = document.file_id
        file_name = document.file_name or f"receipt_{file_id}"
        
        # 获取文件对象
        file = await context.bot.get_file(file_id)
        
        # 创建临时文件路径
        local_path = os.path.join("temp", file_name)
        
        # 确保临时目录存在
        os.makedirs("temp", exist_ok=True)
        
        # 下载文件
        await file.download_to_drive(local_path)
        
        # 获取费用类型
        expense_type = context.user_data.get('cost_type', 'Purchasing')
        
        try:
            # 上传到Google Drive
            result = drive_uploader.upload_receipt(local_path, expense_type)
            
            # 保存收据链接到用户数据
            context.user_data['receipt_link'] = result['public_link']
            
            # 通知用户
            await update.message.reply_text(
                f"✅ 收据已上传成功!\n"
                f"📎 链接: {result['public_link']}"
            )
            
            # 清理临时文件
            os.remove(local_path)
            
            # 继续到下一步
            return await show_cost_confirmation(update, context)
            
        except Exception as e:
            logger.error(f"上传收据失败: {e}")
            await update.message.reply_text(
                "❌ 收据上传失败，请稍后再试。"
            )
            # 清理临时文件
            if os.path.exists(local_path):
                os.remove(local_path)
            
            # 继续到下一步，但没有收据链接
            return await show_cost_confirmation(update, context)
    
    else:
        # 没有收到文件，提示用户
        await update.message.reply_text(
            "⚠️ 请上传收据照片或文件。"
        )
        return COST_RECEIPT  # 保持在当前状态

# 示例：如何修改GoogleSheetsManager类，添加上传收据功能
class GoogleSheetsManager:
    # ... 现有代码 ...
    
    def upload_receipt_to_drive(self, file_stream, file_name, mime_type='image/jpeg'):
        """上传收据到Google Drive并返回公开链接"""
        try:
            # 使用GoogleDriveUploader上传文件
            return drive_uploader.upload_receipt(file_stream, file_name, mime_type)
        except Exception as e:
            logger.error(f"上传收据失败: {e}")
            return ""
    
    def add_expense_record(self, data):
        """添加费用记录，包含收据链接"""
        try:
            # ... 现有代码 ...
            
            # 添加收据链接到数据行
            receipt_link = data.get('receipt', '')
            
            row_data = [
                data.get('date', ''),
                data.get('type', ''),
                data.get('supplier', ''),
                data.get('amount', 0),
                data.get('category', ''),
                data.get('description', ''),
                receipt_link  # 收据链接
            ]
            
            # ... 现有代码 ...
            
        except Exception as e:
            logger.error(f"添加费用记录失败: {e}")
            return False

# 这个函数应该在你现有的代码中
async def show_cost_confirmation(update, context):
    """显示费用确认信息"""
    # ... 现有代码 ...
    
    # 添加收据链接到确认信息
    receipt_link = context.user_data.get('receipt_link', '')
    if receipt_link:
        confirm_message += f"📎 <b>Receipt:</b> <a href='{receipt_link}'>View Receipt</a>\n"
    
    # ... 现有代码 ...
    
    return COST_CONFIRM

# 定义状态常量（这些应该已经在你的代码中定义）
COST_RECEIPT = 5  # 示例值，请使用你代码中的实际值
COST_CONFIRM = 6  # 示例值，请使用你代码中的实际值 
