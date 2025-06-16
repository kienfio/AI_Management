#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Bot Handlers
处理各种用户交互的处理函数
"""

import logging
import os
import re
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import io

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes, ConversationHandler, MessageHandler, CommandHandler, 
    CallbackQueryHandler, filters
)

from google_sheets import GoogleSheetsManager as SheetsManager

# 设置日志
logger = logging.getLogger(__name__)

# ====================================
# 会话状态区 - ConversationHandler 状态定义
# ====================================

# 销售记录状态
SALES_PERSON, SALES_AMOUNT, SALES_BILL_TO, SALES_CLIENT, SALES_COMMISSION_TYPE, SALES_COMMISSION_PERCENT, SALES_COMMISSION_AMOUNT, SALES_AGENT_SELECT, SALES_CONFIRM, SALES_INVOICE_PDF = range(10)

# 费用管理状态
COST_TYPE, COST_SUPPLIER, COST_AMOUNT, COST_DESC, COST_RECEIPT, COST_CONFIRM = range(6)

# 报表生成状态
REPORT_TYPE, REPORT_MONTH = range(2)

# 系统设置状态
SETTINGS_TYPE, SETTINGS_ADD, SETTINGS_EDIT, SETTINGS_DELETE = range(12, 16)

# 新增Setting命令状态
SETTING_CATEGORY, SETTING_NAME, SETTING_IC, SETTING_TYPE, SETTING_RATE = range(5)

# ====================================
# 基础命令区 - /start, /help, /cancel
# ====================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 命令 - 显示主菜单"""
    # 清除用户数据
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("📊 Sale Invoice", callback_data="sales_add")],
        [InlineKeyboardButton("💵 Coasting", callback_data="menu_cost")],
        [InlineKeyboardButton("📈 Report", callback_data="menu_report")],
        [InlineKeyboardButton("⚙️ Setting", callback_data="menu_setting")],
        [InlineKeyboardButton("❓ Help", callback_data="menu_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = """
🚀 *财务管理助手*

👋 欢迎使用！请选择需要的功能：

📊 *Sale Invoice* - 登记发票和佣金
💵 *Coasting* - 记录各项支出
📈 *Report* - 查看统计报告
⚙️ *Setting* - 创建代理商/供应商

📄 *可用命令：*
/Setting - 创建代理商/供应商
/help - 显示帮助信息
    """
    
    # 检查是通过回调查询还是直接命令调用
    if update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    elif update.message:
        await update.message.reply_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    else:
        # 如果既不是回调查询也不是消息，记录错误
        logger.error("Unable to display main menu: update object has neither callback_query nor message attribute")
        return ConversationHandler.END
        
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /help 命令和帮助回调"""
    keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    help_message = """
📖 *使用指南*

📊 *销售记录功能*
• 登记负责人信息
• 记录发票金额  
• 选择客户类型（公司/代理）
• 自动计算佣金

💰 *费用管理功能*
• 供应商采购记录
• 水电网络费用
• 人工工资统计
• 其他支出登记

📈 *报表生成功能*
• 当月报表查看
• 指定月份查询
• 收支汇总统计

💡 *操作提示*
• 使用按钮进行所有操作
• 可随时返回主菜单
• 新操作会自动关闭旧会话
• 使用 /Setting 命令创建代理商、供应商等
    """
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            help_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            help_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理 /cancel 命令，取消当前会话"""
    await update.message.reply_text("✅ Operation cancelled")
    context.user_data.clear()
    await start_command(update, context)
    return ConversationHandler.END

# ====================================
# 销售记录区 - 发票登记、客户选择、佣金计算
# ====================================

async def sales_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """销售记录主菜单"""
    await close_other_conversations(update, context)
    
    keyboard = [
        [InlineKeyboardButton("📊 Add Sale Invoice", callback_data="sales_add")],
        [InlineKeyboardButton("📋 View Sales Records", callback_data="sales_list")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "📊 <b>SALES MANAGEMENT</b>\n\nPlease select an option:"
    
    await update.callback_query.edit_message_text(
        message, 
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

async def sales_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """开始添加销售记录 - 输入负责人 (已弃用)"""
    # 重定向到 sale_invoice_command
    return await sale_invoice_command(update, context)

async def cost_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理费用收据上传"""
    try:
        # 获取文件对象
        if update.message.photo:
            file = await update.message.photo[-1].get_file()
            file_type = 'photo'
            mime_type = 'image/jpeg'
        elif update.message.document:
            file = await update.message.document.get_file()
            file_type = 'document'
            mime_type = update.message.document.mime_type or 'application/octet-stream'
        else:
            await update.message.reply_text("❌ 请上传图片或文档格式的收据")
            return COST_RECEIPT
        
        # 下载文件内容
        file_stream = io.BytesIO()
        await file.download_to_memory(out=file_stream)
        file_stream.seek(0)  # 重置指针位置
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"receipt_{timestamp}.jpg" if file_type == 'photo' else file.file_name
        
        # 获取费用类型
        cost_type = context.user_data.get('cost_type', '')
        
        # 添加日志，记录费用类型
        logger.info(f"上传收据，费用类型: {cost_type}")
        
        # 直接使用GoogleDriveUploader上传文件
        try:
            from google_drive_uploader import get_drive_uploader
            drive_uploader = get_drive_uploader()
            file_url = drive_uploader.upload_receipt(file_stream, cost_type, mime_type=mime_type)
            context.user_data['cost_receipt'] = file_url
            logger.info(f"收据上传成功: {file_url}")
            
            # 继续到确认页面
            return await show_cost_confirmation(update, context)
            
        except Exception as e:
            logger.error(f"上传收据失败: {str(e)}")
            await update.message.reply_text("❌ 上传收据失败，请重试")
            return COST_RECEIPT
        finally:
            file_stream.close()
            
    except Exception as e:
        logger.error(f"处理收据时出错: {e}")
        await update.message.reply_text("❌ 处理收据时出错，请重试")
        return COST_RECEIPT

async def sales_invoice_pdf_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理销售发票PDF上传"""
    try:
        # 获取文件对象
        if not update.message.document:
            await update.message.reply_text("❌ 请上传PDF格式的发票")
            return SALES_INVOICE_PDF
        
        file = await update.message.document.get_file()
        mime_type = update.message.document.mime_type
        
        # 验证文件类型
        if mime_type != 'application/pdf':
            await update.message.reply_text("❌ 请上传PDF格式的发票")
            return SALES_INVOICE_PDF
        
        # 下载文件内容
        file_stream = io.BytesIO()
        await file.download_to_memory(out=file_stream)
        file_stream.seek(0)  # 重置指针位置
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"invoice_{timestamp}.pdf"
        
        # 直接使用GoogleDriveUploader上传文件
        try:
            from google_drive_uploader import get_drive_uploader
            drive_uploader = get_drive_uploader()
            file_url = drive_uploader.upload_receipt(file_stream, 'invoice_pdf', mime_type=mime_type)
            context.user_data['sales_invoice_pdf'] = file_url
            logger.info(f"发票PDF上传成功: {file_url}")
            
            # 继续到确认页面
            return await show_sales_confirmation(update, context)
            
        except Exception as e:
            logger.error(f"上传发票PDF失败: {str(e)}")
            await update.message.reply_text("❌ 上传发票PDF失败，请重试")
            return SALES_INVOICE_PDF
        finally:
            file_stream.close()
            
    except Exception as e:
        logger.error(f"处理发票PDF时出错: {e}")
        await update.message.reply_text("❌ 处理发票PDF时出错，请重试")
        return SALES_INVOICE_PDF

async def upload_invoice_pdf_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """提示上传发票PDF"""
    await update.message.reply_text(
        "📄 请上传发票PDF文件\n\n"
        "要求：\n"
        "• 必须是PDF格式\n"
        "• 文件大小不超过20MB\n\n"
        "您可以随时输入 /cancel 取消操作"
    )
    return SALES_INVOICE_PDF

async def show_sales_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示销售确认信息"""
    # 获取所有必要数据
    sales_data = context.user_data
    amount = sales_data.get('sales_amount', 0)
    bill_to = sales_data.get('sales_bill_to', '')
    client = sales_data.get('sales_client', '')
    commission_type = sales_data.get('commission_type', '')
    commission_amount = sales_data.get('commission_amount', 0)
    invoice_pdf = sales_data.get('sales_invoice_pdf', '')
    
    # 构建确认消息
    confirm_message = f"""
💼 <b>SALES CONFIRMATION</b>

💰 <b>Amount:</b> RM{amount:,.2f}
🏢 <b>Bill To:</b> {bill_to}
👤 <b>Client:</b> {client}
"""
    
    if commission_type:
        confirm_message += f"💵 <b>Commission Type:</b> {commission_type}\n"
        confirm_message += f"💸 <b>Commission Amount:</b> RM{commission_amount:,.2f}\n"
    
    if invoice_pdf:
        confirm_message += "📎 <b>Invoice PDF:</b> Uploaded\n"
    
    confirm_message += "\n<b>Please confirm the information:</b>"
    
    # 添加确认按钮
    keyboard = [
        [InlineKeyboardButton("✅ Save", callback_data="sales_save")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back_sales")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 发送确认消息
    if update.callback_query:
        await update.callback_query.edit_message_text(
            confirm_message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            confirm_message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    
    return SALES_CONFIRM

async def show_cost_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示费用确认信息"""
    # 生成确认信息
    cost_type = context.user_data['cost_type']
    amount = context.user_data['cost_amount']
    
    # 检查是否有收据，并处理可能是字典的情况
    has_receipt = 'cost_receipt' in context.user_data and context.user_data['cost_receipt']
    
    keyboard = [
        [InlineKeyboardButton("✅ Save", callback_data="cost_save")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 构建确认消息
    if cost_type == "Purchasing":
        supplier = context.user_data.get('cost_supplier', '')
        confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> {cost_type}
🏭 <b>Supplier:</b> {supplier}
💰 <b>Amount:</b> RM{amount:,.2f}
"""
        if has_receipt:
            confirm_message += "📎 <b>Receipt:</b> Uploaded\n"
            
        confirm_message += "\n<b>Please confirm the information:</b>"
        
    elif cost_type.endswith("Bill") or cost_type == "Billing":
        desc = context.user_data.get('cost_desc', '')
        
        # 如果是标准账单类型，则使用 Type 显示账单类型
        if cost_type in ["Water Bill", "Electricity Bill", "WiFi Bill"]:
            confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> {cost_type}
💰 <b>Amount:</b> RM{amount:,.2f}
"""
            if has_receipt:
                confirm_message += "📎 <b>Receipt:</b> Uploaded\n"
                
            confirm_message += "\n<b>Please confirm the information:</b>"
            
        # 如果是自定义账单类型，显示描述
        elif cost_type.startswith("Other Bill:"):
            confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> Other Bill
📝 <b>Description:</b> {desc}
💰 <b>Amount:</b> RM{amount:,.2f}
"""
            if has_receipt:
                confirm_message += "📎 <b>Receipt:</b> Uploaded\n"
                
            confirm_message += "\n<b>Please confirm the information:</b>"
            
        # 传统 Billing 类型
        else:
            confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> {cost_type}
📝 <b>Item:</b> {desc}
💰 <b>Amount:</b> RM{amount:,.2f}
"""
            if has_receipt:
                confirm_message += "📎 <b>Receipt:</b> Uploaded\n"
                
            confirm_message += "\n<b>Please confirm the information:</b>"
            
    else:  # Worker Salary
        confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> {cost_type}
💰 <b>Amount:</b> RM{amount:,.2f}
"""
        if has_receipt:
            confirm_message += "📎 <b>Receipt:</b> Uploaded\n"
            
        confirm_message += "\n<b>Please confirm the information:</b>"
    
    try:
        if update.message:
            await update.message.reply_html(
                confirm_message,
                reply_markup=reply_markup
            )
        elif update.callback_query:
            await update.callback_query.edit_message_text(
                confirm_message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            logger.error("无法显示确认信息：update对象既没有message也没有callback_query属性")
    except Exception as e:
        logger.error(f"显示确认信息失败: {e}")
        
    return COST_CONFIRM

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理回调查询"""
    query = update.callback_query
    await query.answer()
    
    # 获取回调数据
    callback_data = query.data
    
    # 处理主菜单选项
    if callback_data == "back_main":
        return await start_command(update, context)
    elif callback_data == "menu_help":
        return await help_command(update, context)
    elif callback_data == "menu_cost":
        return await cost_menu(update, context)
    elif callback_data == "menu_report":
        return await report_menu(update, context)
    elif callback_data == "menu_setting":
        return await menu_setting_handler(update, context)
    elif callback_data == "sales_add":
        return await sales_add_start(update, context)
    elif callback_data == "sales_list":
        return await sales_list_handler(update, context)
    elif callback_data == "cost_list":
        return await cost_list_handler(update, context)
    
    # 处理其他回调数据
    logger.info(f"收到回调数据: {callback_data}")
    return ConversationHandler.END

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理错误"""
    logger.error(f"Update {update} caused error {context.error}")
    
    # 获取错误信息
    error_message = str(context.error)
    
    try:
        # 如果是更新对象导致的错误
        if update:
            if update.message:
                await update.message.reply_text(
                    f"❌ 发生错误: {error_message}\n\n请重试或联系管理员"
                )
            elif update.callback_query:
                await update.callback_query.message.reply_text(
                    f"❌ 发生错误: {error_message}\n\n请重试或联系管理员"
                )
    except Exception as e:
        logger.error(f"发送错误消息时出错: {e}")

def get_conversation_handlers():
    """获取所有会话处理器"""
    # 销售记录处理器
    sales_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(sales_add_start, pattern="^sales_add$"),
            CommandHandler("sales", sales_menu)
        ],
        states={
            SALES_PERSON: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_person_handler)],
            SALES_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_amount_handler)],
            SALES_BILL_TO: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_bill_to_handler)],
            SALES_CLIENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_client_handler)],
            SALES_COMMISSION_TYPE: [
                CallbackQueryHandler(sales_commission_type_handler, pattern="^commission_type_"),
                CallbackQueryHandler(use_default_commission_handler, pattern="^use_default_commission$")
            ],
            SALES_COMMISSION_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_commission_percent_handler)],
            SALES_COMMISSION_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_commission_amount_handler)],
            SALES_AGENT_SELECT: [
                CallbackQueryHandler(sales_agent_select_handler, pattern="^agent_select_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, sales_agent_select_handler)
            ],
            SALES_CONFIRM: [
                CallbackQueryHandler(sales_save_handler, pattern="^sales_save$"),
                CallbackQueryHandler(start_command, pattern="^back_sales$")
            ],
            SALES_INVOICE_PDF: [MessageHandler(filters.Document.ALL, sales_invoice_pdf_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="sales_conversation",
        persistent=False
    )
    
    # 费用管理处理器
    cost_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cost_menu, pattern="^menu_cost$"),
            CommandHandler("cost", cost_menu)
        ],
        states={
            COST_TYPE: [
                CallbackQueryHandler(cost_type_handler, pattern="^cost_type_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cost_type_handler)
            ],
            COST_SUPPLIER: [
                CallbackQueryHandler(cost_supplier_handler, pattern="^supplier_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_supplier_handler)
            ],
            COST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cost_amount_handler)],
            COST_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, cost_desc_handler)],
            COST_RECEIPT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, cost_receipt_handler),
                CallbackQueryHandler(show_cost_confirmation, pattern="^skip_receipt$")
            ],
            COST_CONFIRM: [
                CallbackQueryHandler(cost_save_handler, pattern="^cost_save$"),
                CallbackQueryHandler(start_command, pattern="^back_cost$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="cost_conversation",
        persistent=False
    )
    
    # 报表生成处理器
    report_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(report_menu, pattern="^menu_report$"),
            CommandHandler("report", report_menu)
        ],
        states={
            REPORT_TYPE: [
                CallbackQueryHandler(report_current_handler, pattern="^report_current$"),
                CallbackQueryHandler(report_custom_handler, pattern="^report_custom$"),
                CallbackQueryHandler(report_yearly_handler, pattern="^report_yearly$")
            ],
            REPORT_MONTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_month_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="report_conversation",
        persistent=False
    )
    
    # 系统设置处理器
    setting_handler = ConversationHandler(
        entry_points=[
            CommandHandler("setting", setting_command),
            CallbackQueryHandler(menu_setting_handler, pattern="^menu_setting$")
        ],
        states={
            SETTING_CATEGORY: [
                CallbackQueryHandler(setting_category_handler, pattern="^setting_category_")
            ],
            SETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_name_handler)],
            SETTING_IC: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_ic_handler)],
            SETTING_TYPE: [
                CallbackQueryHandler(setting_type_handler, pattern="^setting_type_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, setting_type_handler)
            ],
            SETTING_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_rate_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        name="setting_conversation",
        persistent=False
    )
    
    return [sales_handler, cost_handler, report_handler, setting_handler]

def setup_handlers(application):
    """设置所有处理器"""
    # 获取所有会话处理器
    conversation_handlers = get_conversation_handlers()
    
    # 注册所有会话处理器
    for handler in conversation_handlers:
        application.add_handler(handler)
    
    # 基础命令处理器
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # 回调查询处理器 (放在会话处理器之后)
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    
    # 文本消息处理器
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # 未知命令处理器
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # 错误处理器
    application.add_error_handler(error_handler)
    
    logger.info("所有处理器已成功注册") 
