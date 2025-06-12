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
SALES_PERSON, SALES_AMOUNT, SALES_CLIENT, SALES_COMMISSION_TYPE, SALES_COMMISSION_PERCENT, SALES_COMMISSION_AMOUNT, SALES_AGENT_SELECT, SALES_CONFIRM = range(8)

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
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = ""
    
    await update.callback_query.edit_message_text(
        message, 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def sales_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """开始添加销售记录 - 输入负责人 (已弃用)"""
    # 重定向到 sale_invoice_command
    return await sale_invoice_command(update, context)

async def sales_person_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理负责人选择"""
    query = update.callback_query
    if not query:
        # 如果不是按钮点击，可能是直接输入文本，这里我们直接存储文本
        context.user_data['sales_person'] = update.message.text.strip()
    else:
        # 处理按钮点击，格式为pic_{name}
        await query.answer()
        person_data = query.data
        if person_data.startswith("pic_"):
            context.user_data['sales_person'] = person_data[4:]  # 去掉"pic_"前缀
        else:
            # 未知回调数据
            await query.edit_message_text("❌ Unknown operation, please start again")
            return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = f"👤 <b>Person in Charge:</b> {context.user_data['sales_person']}\n\n💰 <b>Enter Amount:</b>"
    
    if query:
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    
    return SALES_AMOUNT

async def sales_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理发票金额输入"""
    logger.info(f"接收到金额输入: {update.message.text}")
    
    try:
        amount_text = update.message.text.strip()
        # 检查金额格式
        # 尝试移除千位分隔符和货币符号，如果有的话
        clean_amount = amount_text.replace(',', '').replace('¥', '').replace('$', '').replace('€', '')
        amount = float(clean_amount)
        
        logger.info(f"解析后的金额: {amount}")
        context.user_data['sales_amount'] = amount
        
        keyboard = [
            [InlineKeyboardButton("🏢 Company", callback_data="client_company")],
            [InlineKeyboardButton("🤝 Agent", callback_data="client_agent")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"💰 <b>Amount:</b> RM{amount:,.2f}\n\n🎯 <b>Select Client Type:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        logger.info(f"金额处理完成，等待客户类型选择")
        return SALES_CLIENT
    except ValueError as e:
        logger.error(f"金额解析错误: {e}")
        await update.message.reply_text("⚠️ Please enter a valid amount")
        return SALES_AMOUNT
    except Exception as e:
        logger.error(f"处理金额时发生未知错误: {e}")
        await update.message.reply_text("❌ Error processing, please re-enter the amount")
        return SALES_AMOUNT

async def sales_client_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理客户类型选择"""
    query = update.callback_query
    await query.answer()
    
    client_type = "Company" if query.data == "client_company" else "Agent"
    context.user_data['sales_client'] = client_type
    
    # 如果选择的是公司，直接进入确认步骤，不计算佣金
    if client_type == "Company":
        # 公司类型不需要计算佣金
        amount = context.user_data['sales_amount']
        commission_rate = 0  # 设置为0，表示没有佣金
        commission = 0  # 佣金金额为0
        context.user_data['sales_commission'] = commission
        context.user_data['commission_rate'] = commission_rate
        
        # 跳转到确认界面
        return await show_sales_confirmation(update, context)
    
    # 如果选择的是代理商，先获取代理商列表
    try:
        # 获取代理商列表
        sheets_manager = SheetsManager()
        agents = sheets_manager.get_agents(active_only=True)
        
        if not agents:
            # 如果没有代理商数据，显示提示信息
            keyboard = [[InlineKeyboardButton("⚙️ Create Agent", callback_data="setting_create_agent")],
                        [InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "⚠️ <b>No agents found</b>\n\nPlease create an agent first.",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        # 创建代理商选择按钮
        keyboard = []
        for agent in agents:
            # 使用姓名作为按钮文本
            name = agent.get('姓名', '')
            commission = agent.get('佣金比例', '')
            display_text = f"{name}"
            if commission:
                display_text += f" ({commission})"
                
            if name:
                keyboard.append([InlineKeyboardButton(f"🤝 {display_text}", callback_data=f"agent_{name}_{commission}")])
        
        # 添加取消按钮
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🤝 <b>Select Agent:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        # 返回代理商选择状态
        return SALES_AGENT_SELECT
        
    except Exception as e:
        logger.error(f"获取代理商列表失败: {e}")
        await query.edit_message_text(
            "❌ <b>Failed to get agent data</b>\n\nPlease try again later.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

# 添加新的状态常量
SALES_COMMISSION_TYPE = 21  # 用于选择佣金计算方式
SALES_COMMISSION_PERCENT = 22  # 用于输入佣金百分比
SALES_COMMISSION_AMOUNT = 23  # 用于直接输入佣金金额

# 添加佣金计算方式选择处理函数
async def sales_commission_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理佣金计算方式选择"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "commission_percent":
        # 选择设置佣金百分比
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💯 <b>Enter Commission Percentage:</b>\n\n<i>Example: Enter 10 for 10%</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        return SALES_COMMISSION_PERCENT
        
    elif query.data == "commission_amount":
        # 选择直接输入佣金金额
        amount = context.user_data['sales_amount']
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💰 <b>Total Amount:</b> RM{amount:,.2f}\n\n<b>Enter Commission Amount Directly:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        return SALES_COMMISSION_AMOUNT
    
    # 未知回调数据
    await query.edit_message_text("❌ Unknown operation, please start again")
    return ConversationHandler.END

# 添加佣金百分比输入处理函数
async def sales_commission_percent_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理佣金百分比输入"""
    logger.info(f"接收到佣金百分比输入: {update.message.text}")
    
    try:
        # 解析百分比
        percent_text = update.message.text.strip().replace('%', '')
        percent = float(percent_text)
        
        # 验证百分比合理性
        if percent < 0 or percent > 100:
            await update.message.reply_text("⚠️ Please enter a percentage between 0-100")
            return SALES_COMMISSION_PERCENT
        
        # 计算佣金
        amount = context.user_data['sales_amount']
        commission_rate = percent / 100
        commission = amount * commission_rate
        
        # 保存数据
        context.user_data['commission_rate'] = commission_rate
        context.user_data['sales_commission'] = commission
        context.user_data['commission_type'] = 'percent'
        
        # 跳转到确认界面
        return await show_sales_confirmation(update, context)
        
    except ValueError as e:
        logger.error(f"百分比解析错误: {e}")
        await update.message.reply_text("⚠️ Please enter a valid percentage number")
        return SALES_COMMISSION_PERCENT
    except Exception as e:
        logger.error(f"处理佣金百分比时发生错误: {e}")
        await update.message.reply_text("❌ Error occurred, please try again")
        return SALES_COMMISSION_PERCENT

# 添加佣金金额输入处理函数
async def sales_commission_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理直接输入的佣金金额"""
    logger.info(f"接收到佣金金额输入: {update.message.text}")
    
    try:
        # 解析金额
        amount_text = update.message.text.strip()
        clean_amount = amount_text.replace(',', '').replace('RM', '').replace('¥', '').replace('$', '').replace('€', '')
        commission = float(clean_amount)
        
        # 验证佣金合理性
        total_amount = context.user_data['sales_amount']
        if commission < 0 or commission > total_amount:
            await update.message.reply_text(f"⚠️ Commission cannot be less than 0 or greater than total amount RM{total_amount:,.2f}")
            return SALES_COMMISSION_AMOUNT
        
        # 计算佣金比例
        commission_rate = commission / total_amount if total_amount > 0 else 0
        
        # 保存数据
        context.user_data['commission_rate'] = commission_rate
        context.user_data['sales_commission'] = commission
        context.user_data['commission_type'] = 'fixed'
        
        # 跳转到确认界面
        return await show_sales_confirmation(update, context)
        
    except ValueError as e:
        logger.error(f"佣金金额解析错误: {e}")
        await update.message.reply_text("⚠️ Please enter a valid amount")
        return SALES_COMMISSION_AMOUNT
    except Exception as e:
        logger.error(f"处理佣金金额时发生错误: {e}")
        await update.message.reply_text("❌ Error occurred, please try again")
        return SALES_COMMISSION_AMOUNT

# 添加辅助函数来显示代理商选择
async def show_agent_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示代理商选择界面"""
    try:
        # 获取代理商列表
        sheets_manager = SheetsManager()
        agents = sheets_manager.get_agents(active_only=True)
        
        if not agents:
            # 如果没有代理商数据，显示提示信息
            keyboard = [[InlineKeyboardButton("⚙️ 创建代理商", callback_data="setting_create_agent")],
                        [InlineKeyboardButton("❌ 取消", callback_data="back_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "⚠️ <b>未找到代理商数据</b>\n\n请先创建代理商后再使用此功能。",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        # 创建代理商选择按钮
        keyboard = []
        for agent in agents:
            # 使用姓名作为按钮文本
            name = agent.get('姓名', '')
            if name:
                keyboard.append([InlineKeyboardButton(f"🤝 {name}", callback_data=f"agent_{name}")])
        
        # 添加取消按钮
        keyboard.append([InlineKeyboardButton("❌ 取消", callback_data="back_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 显示佣金信息
        amount = context.user_data['sales_amount']
        commission = context.user_data['sales_commission']
        commission_rate = context.user_data.get('commission_rate', 0) * 100
        
        message = f"""
💰 <b>总金额:</b> RM{amount:,.2f}
💵 <b>佣金:</b> RM{commission:,.2f} ({commission_rate:.1f}%)

🤝 <b>请选择代理商:</b>
"""
        
        await update.message.reply_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        # 返回代理商选择状态
        return SALES_AGENT_SELECT
        
    except Exception as e:
        logger.error(f"获取代理商列表失败: {e}")
        await update.message.reply_text(
            "❌ <b>获取代理商数据失败</b>\n\n请稍后再试。",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

# 创建一个辅助函数来显示确认信息
async def show_sales_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示销售记录确认信息"""
    keyboard = [
        [InlineKeyboardButton("✅ Save", callback_data="sales_save")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 获取数据
    amount = context.user_data['sales_amount']
    client_type = context.user_data['sales_client']
    commission = context.user_data['sales_commission']
    commission_rate = context.user_data.get('commission_rate', 0) * 100
    person = context.user_data['sales_person']
    agent = context.user_data.get('sales_agent', '')
    
    # 构建确认消息
    if client_type == "Agent":
        client_display = f"{client_type}: {agent}"
        commission_display = f"💵 <b>Commission:</b> RM{commission:,.2f} ({commission_rate:.1f}%)"
    else:
        client_display = client_type
        commission_display = ""  # 公司类型不显示佣金信息
    
    confirm_message = f"""
📊 <b>INVOICE CONFIRMATION</b>

👤 <b>Person in Charge:</b> {person}
💰 <b>Amount:</b> RM{amount:,.2f}
🎯 <b>Client Type:</b> {client_display}
{commission_display}

<b>Please confirm the information:</b>
    """
    
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

async def sales_save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """保存销售记录"""
    query = update.callback_query
    await query.answer()
    
    try:
        # 保存到 Google Sheets
        sheets_manager = SheetsManager()
        
        # 准备数据
        client_type = context.user_data['sales_client']
        agent_info = ""
        if client_type == "Agent" and 'sales_agent' in context.user_data:
            agent_info = context.user_data['sales_agent']
            client_type = f"{client_type}: {agent_info}"
        
        # 获取佣金计算方式
        commission_type = context.user_data.get('commission_type', '')
        commission_note = ""
        if commission_type == 'percent':
            commission_note = "Percentage based commission"
        elif commission_type == 'fixed':
            commission_note = "Fixed commission amount"
        
        sales_data = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'person': context.user_data['sales_person'],
            'amount': context.user_data['sales_amount'],
            'client_type': client_type,
            'commission_rate': context.user_data.get('commission_rate', 0),
            'commission_amount': context.user_data['sales_commission'],
            'notes': f"Agent: {agent_info}" + (f", {commission_note}" if commission_note else "")
        }
        
        sheets_manager.add_sales_record(sales_data)
        
        # 显示成功消息，包含保存的信息
        amount = context.user_data['sales_amount']
        commission = context.user_data['sales_commission']
        person = context.user_data['sales_person']
        
        success_message = f"""
✅ <b>Invoice saved successfully!</b>

👤 <b>Person in Charge:</b> {person}
💰 <b>Amount:</b> RM{amount:,.2f}
💵 <b>Commission:</b> RM{commission:,.2f}
🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            success_message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"保存销售记录失败: {e}")
        await query.edit_message_text(
            "❌ <b>Failed to save. Please try again.</b>",
            parse_mode=ParseMode.HTML
        )
    
    # 清除临时数据
    context.user_data.clear()
    return ConversationHandler.END

async def sales_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看销售记录"""
    query = update.callback_query
    await query.answer()
    
    try:
        sheets_manager = SheetsManager()
        sales_records = await sheets_manager.get_recent_sales(limit=10)
        
        if not sales_records:
            message = "📋 暂无销售记录"
        else:
            message = "📋 *最近销售记录*\n\n"
            for record in sales_records:
                message += f"📅 {record['date']}\n"
                message += f"👤 {record['person']} | 🎯 {record['client_type']}\n"
                message += f"💰 RM{record['amount']:,.2f} | 💵 RM{record['commission']:,.2f}\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 返回销售菜单", callback_data="menu_sales")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"获取销售记录失败: {e}")
        await query.edit_message_text("❌ 获取记录失败，请重试")

# ====================================
# 费用管理区 - 采购、水电、工资、其他支出
# ====================================

async def cost_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示费用管理菜单"""
    query = update.callback_query
    await query.answer()
    
    # 清除用户数据
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("🛒 Purchasing", callback_data="cost_purchasing")],
        [InlineKeyboardButton("💳 Billing", callback_data="cost_billing")],
        [InlineKeyboardButton("👨‍💼 Worker Salary", callback_data="cost_salary")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "💵 <b>COASTING MANAGEMENT</b>\n\n<b>Please select an expense type:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return COST_TYPE

async def cost_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理费用类型选择"""
    query = update.callback_query
    await query.answer()
    
    cost_types = {
        "cost_purchasing": "Purchasing",
        "cost_billing": "Billing",
        "cost_salary": "Worker Salary",
        "billing_water": "Water Bill",
        "billing_electricity": "Electricity Bill",
        "billing_wifi": "WiFi Bill",
        "billing_other": "Other Bill"
    }
    
    # 对于账单子类型的处理
    if query.data.startswith("billing_"):
        context.user_data['cost_type'] = cost_types[query.data]
        
        # 特殊处理 "Other Bill" 类型，让用户输入自定义描述
        if query.data == "billing_other":
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "📝 <b>Other Bill</b>\n\n<b>Please enter bill description:</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
            # 设置标记，表示等待自定义账单描述
            context.user_data['waiting_for_bill_desc'] = True
            return COST_DESC
        
        # 其他账单类型直接使用预设描述
        context.user_data['cost_desc'] = cost_types[query.data]  # 将账单类型存储为描述
        
        # 直接跳转到金额输入
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"📝 <b>{cost_types[query.data]}</b>\n\n<b>Please enter the amount:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        return COST_AMOUNT
    
    # 普通费用类型处理
    if query.data in cost_types:
        context.user_data['cost_type'] = cost_types[query.data]
    
    if query.data == "cost_purchasing":
        # 对于采购支出，需要选择供应商
        try:
            # 获取供应商列表
            sheets_manager = SheetsManager()
            suppliers = sheets_manager.get_suppliers(active_only=True)
            
            if not suppliers:
                # 如果没有供应商数据，显示提示信息
                keyboard = [[InlineKeyboardButton("⚙️ Create Supplier", callback_data="setting_create_supplier")],
                            [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(
                    "⚠️ <b>No suppliers found</b>\n\nPlease create a supplier first.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                return ConversationHandler.END
            
            # 创建供应商选择按钮
            keyboard = []
            for supplier in suppliers:
                # 使用供应商名称作为按钮文本
                name = supplier.get('供应商名称', '')
                if name:
                    keyboard.append([InlineKeyboardButton(f"🏭 {name}", callback_data=f"supplier_{name}")])
            
            # 添加自定义输入选项
            keyboard.append([InlineKeyboardButton("✏️ Other (Custom Input)", callback_data="supplier_other")])
            
            # 添加取消按钮
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_cost")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "🏭 <b>Select Supplier:</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
            return COST_SUPPLIER
            
        except Exception as e:
            logger.error(f"获取供应商列表失败: {e}")
            await query.edit_message_text(
                "❌ <b>Failed to get supplier data</b>\n\nPlease try again later.",
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
    
    elif query.data == "cost_billing":
        # 对于账单支出，显示账单类型选项
        keyboard = [
            [InlineKeyboardButton("💧 Water", callback_data="billing_water")],
            [InlineKeyboardButton("⚡ Electricity", callback_data="billing_electricity")],
            [InlineKeyboardButton("📶 WiFi", callback_data="billing_wifi")],
            [InlineKeyboardButton("✏️ Other", callback_data="billing_other")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_cost")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "📝 <b>BILLING</b>\n\n<b>Please select the billing type:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        # 返回同一状态，等待子类型选择
        return COST_TYPE
    
    elif query.data == "cost_salary":
        # 对于工资支出，直接输入金额
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "💰 <b>Enter Salary Amount:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        return COST_AMOUNT
    
    return ConversationHandler.END

async def cost_supplier_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理供应商选择"""
    query = update.callback_query
    await query.answer()
    
    # 从回调数据中提取供应商名称
    supplier_name = query.data.replace("supplier_", "")
    
    # 处理自定义供应商输入
    if supplier_name == "other":
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🏭 <b>Please enter the supplier name:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        # 设置一个标记，表示我们正在等待自定义供应商名称输入
        context.user_data['waiting_for_custom_supplier'] = True
        return COST_SUPPLIER
    
    # 正常供应商选择
    context.user_data['cost_supplier'] = supplier_name
    
    # 显示金额输入界面
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🏭 <b>Supplier:</b> {supplier_name}\n\n<b>Please enter the amount:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return COST_AMOUNT

async def custom_supplier_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理自定义供应商名称输入"""
    # 检查是否正在等待自定义供应商输入
    if not context.user_data.get('waiting_for_custom_supplier'):
        return COST_SUPPLIER
    
    # 获取用户输入的供应商名称
    supplier_name = update.message.text.strip()
    context.user_data['cost_supplier'] = supplier_name
    
    # 清除等待标记
    context.user_data.pop('waiting_for_custom_supplier', None)
    
    # 显示金额输入界面
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"🏭 <b>Supplier:</b> {supplier_name}\n\n<b>Please enter the amount:</b>",
        reply_markup=reply_markup
    )
    
    return COST_AMOUNT

async def cost_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理金额输入"""
    try:
        amount_text = update.message.text.strip()
        
        # 尝试将金额转换为浮点数
        amount = float(amount_text.replace(',', ''))
        context.user_data['cost_amount'] = amount
        
        # 对于所有采购支出和账单支出，提示上传收据
        cost_type = context.user_data.get('cost_type', '')
        if cost_type == "Purchasing" or cost_type == "Billing" or "Bill" in cost_type:
            keyboard = [
                [InlineKeyboardButton("📷 Upload Receipt", callback_data="upload_receipt")],
                [InlineKeyboardButton("⏭️ Skip", callback_data="skip_receipt")],
                [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_html(
                f"💰 <b>Amount:</b> RM{amount:,.2f}\n\n<b>Would you like to upload a receipt?</b>",
                reply_markup=reply_markup
            )
            
            return COST_RECEIPT
        
        # 如果是其他支出但还没有描述，提示输入描述
        if context.user_data.get('cost_type') == "Other Expense" and 'cost_desc' not in context.user_data:
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_html(
                "<b>Please upload the receipt:</b>",
                reply_markup=reply_markup
            )
            
            return COST_RECEIPT
        
        # 否则显示确认信息
        return await show_cost_confirmation(update, context)
        
    except ValueError:
        # 金额格式不正确
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            "⚠️ <b>Invalid amount format</b>\n\nPlease enter a valid number.",
            reply_markup=reply_markup
        )
        return COST_AMOUNT

async def cost_desc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理描述输入"""
    desc = update.message.text.strip()
    context.user_data['cost_desc'] = desc
    
    # 检查是否是自定义账单描述
    if context.user_data.get('waiting_for_bill_desc'):
        # 清除等待标记
        context.user_data.pop('waiting_for_bill_desc', None)
        
        # 保存自定义账单描述，修改类型为自定义类型+描述
        custom_type = f"Other Bill: {desc}"
        context.user_data['cost_type'] = custom_type
        
        # 提示输入金额
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"📝 <b>Bill Description:</b> {desc}\n\n<b>Please enter the amount:</b>",
            reply_markup=reply_markup
        )
        
        return COST_AMOUNT
    
    # 常规描述处理
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"📝 <b>Item:</b> {desc}\n\n<b>Please enter the amount:</b>",
        reply_markup=reply_markup
    )
    
    return COST_AMOUNT

async def cost_save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理费用保存"""
    query = update.callback_query
    await query.answer()
    
    try:
        from config import GoogleSheetsManager
        
        # 创建Google Sheets管理器实例
        sheets_manager = GoogleSheetsManager()
        
        # 获取数据
        cost_type = context.user_data.get('cost_type', '')
        amount = context.user_data.get('cost_amount', 0)
        supplier = context.user_data.get('cost_supplier', '')
        description = context.user_data.get('cost_desc', '')
        receipt_url = context.user_data.get('receipt_url', '')
        
        # 如果是账单类型，根据不同类型设置描述
        if cost_type.endswith("Bill") and cost_type != "Other Bill":
            # 对于标准账单，如水电网络等，使用类型作为描述
            category = "Utility"
        elif cost_type.startswith("Other Bill:"):
            # 对于其他账单，保留描述
            cost_type = "Other Bill"
            category = "Other"
        elif cost_type == "Worker Salary":
            category = "Salary"
        elif cost_type == "Purchasing":
            category = "Purchase"
        else:
            category = "Other"
        
        # 添加收据URL到描述
        if receipt_url:
            if description:
                description = f"{description} | Receipt: {receipt_url}"
            else:
                description = f"Receipt: {receipt_url}"
        
        # 准备数据
        expense_data = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'type': cost_type,
            'supplier': supplier,
            'amount': amount,
            'category': category,
            'description': description
        }
        
        # 保存到Google Sheets
        success = sheets_manager.add_expense_record(expense_data)
        
        if success:
            await query.edit_message_text(
                "✅ <b>Expense saved successfully!</b>",
                parse_mode=ParseMode.HTML
            )
        else:
            await query.edit_message_text(
                "❌ <b>Failed to save expense</b>",
                parse_mode=ParseMode.HTML
            )
        
        # 结束对话
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"保存费用记录失败: {e}")
        await query.edit_message_text(
            "❌ <b>Failed to save expense</b>\n\nPlease try again later.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

async def cost_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理收据上传"""
    try:
        from config import GoogleSheetsManager
        
        # 创建Google Sheets管理器实例
        sheets_manager = GoogleSheetsManager()
        
        # 这里可以处理照片或文件
        if update.message.photo:
            # 如果是照片，获取最高质量的照片ID
            file_id = update.message.photo[-1].file_id
            context.user_data['cost_receipt'] = file_id
            context.user_data['cost_receipt_type'] = 'photo'
            
            # 获取文件对象
            file_obj = await context.bot.get_file(file_id)
            
            # 生成唯一文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            file_name = f"receipt_{timestamp}.jpg"
            
            # 告诉用户正在上传
            status_message = await update.message.reply_text("📤 正在上传照片到Google Drive...")
            
            # 上传文件到Google Drive
            file_url = sheets_manager.upload_telegram_file(file_obj, file_name)
            
            if file_url:
                # 保存URL到用户数据
                context.user_data['receipt_url'] = file_url
                await status_message.edit_text("✅ 照片上传成功！")
            else:
                await status_message.edit_text("⚠️ 照片上传失败，但您可以继续操作")
            
        elif update.message.document:
            # 如果是文件，获取文件ID
            file_id = update.message.document.file_id
            file_name = update.message.document.file_name or "document"
            context.user_data['cost_receipt'] = file_id
            context.user_data['cost_receipt_type'] = 'document'
            
            # 获取文件对象
            file_obj = await context.bot.get_file(file_id)
            
            # 告诉用户正在上传
            status_message = await update.message.reply_text("📤 正在上传文件到Google Drive...")
            
            # 上传文件到Google Drive
            file_url = sheets_manager.upload_telegram_file(file_obj, file_name)
            
            if file_url:
                # 保存URL到用户数据
                context.user_data['receipt_url'] = file_url
                await status_message.edit_text("✅ 文件上传成功！")
            else:
                await status_message.edit_text("⚠️ 文件上传失败，但您可以继续操作")
            
        else:
            # 如果没有上传图片或文档，提示用户
            await update.message.reply_html(
                "⚠️ <b>Please upload a photo or document as receipt.</b>\n\nOr type /skip to continue without receipt."
            )
            return COST_RECEIPT
        
        # 继续到确认页面
        return await show_cost_confirmation(update, context)
        
    except Exception as e:
        logger.error(f"❌ 处理收据上传失败: {e}")
        # 即使上传失败，也继续流程
        return await show_cost_confirmation(update, context)

async def show_cost_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示费用确认信息"""
    # 生成确认信息
    cost_type = context.user_data['cost_type']
    amount = context.user_data['cost_amount']
    
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

<b>Please confirm the information:</b>
        """
    elif cost_type.endswith("Bill") or cost_type == "Billing":
        desc = context.user_data.get('cost_desc', '')
        
        # 如果是标准账单类型，则使用 Type 显示账单类型
        if cost_type in ["Water Bill", "Electricity Bill", "WiFi Bill"]:
            confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> {cost_type}
💰 <b>Amount:</b> RM{amount:,.2f}

<b>Please confirm the information:</b>
            """
        # 如果是自定义账单类型，显示描述
        elif cost_type.startswith("Other Bill:"):
            confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> Other Bill
📝 <b>Description:</b> {desc}
💰 <b>Amount:</b> RM{amount:,.2f}

<b>Please confirm the information:</b>
            """
        # 传统 Billing 类型
        else:
            confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> {cost_type}
📝 <b>Item:</b> {desc}
💰 <b>Amount:</b> RM{amount:,.2f}

<b>Please confirm the information:</b>
            """
    else:  # Worker Salary
        confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> {cost_type}
💰 <b>Amount:</b> RM{amount:,.2f}

<b>Please confirm the information:</b>
        """
    
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
        # 尝试发送错误消息
        try:
            if update.message:
                await update.message.reply_text("❌ Error displaying confirmation, please try again")
            elif update.callback_query:
                await update.callback_query.edit_message_text("❌ Error displaying confirmation, please try again")
        except Exception:
            pass
    
    return COST_CONFIRM

# ====================================
# 报表生成区 - 月度报表、自定义查询
# ====================================

async def report_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """报表生成主菜单"""
    await close_other_conversations(update, context)
    
    keyboard = [
        [InlineKeyboardButton("📊 当月报表", callback_data="report_current")],
        [InlineKeyboardButton("🗓️ 指定月份", callback_data="report_custom")],
        [InlineKeyboardButton("📈 年度汇总", callback_data="report_yearly")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "📈 *报表生成*\n\n请选择报表类型："
    
    await update.callback_query.edit_message_text(
        message, 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def report_current_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """生成当月报表"""
    query = update.callback_query
    await query.answer()
    
    try:
        sheets_manager = SheetsManager()
        current_month = datetime.now().strftime('%Y-%m')
        report_data = await sheets_manager.generate_monthly_report(current_month)
        
        keyboard = [[InlineKeyboardButton("🔙 返回报表菜单", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        report_message = f"""
📊 *{current_month} 月度报表*

💰 *收入统计*
• 总销售额：¥{report_data['total_sales']:,.2f}
• 总佣金：¥{report_data['total_commission']:,.2f}

💸 *支出统计*
• 采购支出：¥{report_data['purchase_cost']:,.2f}
• 水电网络：¥{report_data['utility_cost']:,.2f}
• 人工工资：¥{report_data['salary_cost']:,.2f}
• 其他支出：¥{report_data['other_cost']:,.2f}
• 总支出：¥{report_data['total_cost']:,.2f}

📈 *盈亏分析*
• 毛利润：¥{report_data['gross_profit']:,.2f}
• 净利润：¥{report_data['net_profit']:,.2f}
        """
        
        await query.edit_message_text(
            report_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"生成报表失败: {e}")
        await query.edit_message_text("❌ 生成报表失败，请重试")
    
    return ConversationHandler.END

async def report_custom_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """自定义月份报表"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="back_report")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🗓️ 请输入月份（格式：YYYY-MM，如：2024-03）：",
        reply_markup=reply_markup
    )
    return REPORT_MONTH

async def report_month_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理自定义月份输入"""
    try:
        month_input = update.message.text.strip()
        # 验证日期格式
        datetime.strptime(month_input, '%Y-%m')
        
        sheets_manager = SheetsManager()
        report_data = await sheets_manager.generate_monthly_report(month_input)
        
        keyboard = [[InlineKeyboardButton("🔙 返回报表菜单", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        report_message = f"""
📊 *{month_input} 月度报表*

💰 *收入统计*
• 总销售额：¥{report_data['total_sales']:,.2f}
• 总佣金：¥{report_data['total_commission']:,.2f}

💸 *支出统计*
• 采购支出：¥{report_data['purchase_cost']:,.2f}
• 水电网络：¥{report_data['utility_cost']:,.2f}
• 人工工资：¥{report_data['salary_cost']:,.2f}
• 其他支出：¥{report_data['other_cost']:,.2f}
• 总支出：¥{report_data['total_cost']:,.2f}

📈 *盈亏分析*
• 毛利润：¥{report_data['gross_profit']:,.2f}
• 净利润：¥{report_data['net_profit']:,.2f}
        """
        
        await update.message.reply_text(
            report_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    except ValueError:
        await update.message.reply_text("⚠️ 请输入正确的日期格式（YYYY-MM）")
        return REPORT_MONTH
    except Exception as e:
        logger.error(f"生成自定义报表失败: {e}")
        await update.message.reply_text("❌ 生成报表失败，请重试")
    
    return ConversationHandler.END

async def report_yearly_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """生成年度汇总报表"""
    query = update.callback_query
    await query.answer()
    
    try:
        sheets_manager = SheetsManager()
        current_year = datetime.now().year
        report_data = await sheets_manager.generate_yearly_report(current_year)
        
        keyboard = [[InlineKeyboardButton("🔙 返回报表菜单", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        report_message = f"""
📈 *{current_year} 年度汇总报表*

💰 *年度收入*
• 总销售额：¥{report_data['total_sales']:,.2f}
• 总佣金：¥{report_data['total_commission']:,.2f}

💸 *年度支出*
• 采购支出：¥{report_data['purchase_cost']:,.2f}
• 水电网络：¥{report_data['utility_cost']:,.2f}
• 人工工资：¥{report_data['salary_cost']:,.2f}
• 其他支出：¥{report_data['other_cost']:,.2f}
• 总支出：¥{report_data['total_cost']:,.2f}

📊 *年度分析*
• 毛利润：¥{report_data['gross_profit']:,.2f}
• 净利润：¥{report_data['net_profit']:,.2f}
• 平均月收入：¥{report_data['avg_monthly_income']:,.2f}
• 平均月支出：¥{report_data['avg_monthly_cost']:,.2f}
        """
        
        await query.edit_message_text(
            report_message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"生成年度报表失败: {e}")
        await query.edit_message_text("❌ 生成报表失败，请重试")

# ====================================
# 回调处理区 - 所有 inline keyboard 回调
# ====================================

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """统一处理所有回调查询"""
    query = update.callback_query
    await query.answer()
    
    # 主菜单回调
    if query.data == "back_main":
        try:
            # 直接在当前消息上显示主菜单
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
            """
            
            await query.edit_message_text(
                welcome_message, 
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
            # 清除用户数据
            context.user_data.clear()
            return ConversationHandler.END
        except Exception as e:
            logger.error(f"返回主菜单失败: {e}")
            # 尝试发送错误消息
            try:
                keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data="back_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.edit_message_text(
                    "❌ 系统出现错误，请稍后重试",
                    reply_markup=reply_markup
                )
            except Exception as e2:
                logger.error(f"发送错误消息失败: {e2}")
            return ConversationHandler.END
    
    # 各功能菜单回调
    elif query.data == "menu_sales":
        # 这里不做任何处理，因为menu_sales回调已经在ConversationHandler的entry_points中处理
        # 只是为了防止出错，所以保留这个分支
        logger.info("menu_sales回调被触发，但由ConversationHandler处理")
        return ConversationHandler.END
    elif query.data == "menu_cost":
        return await cost_menu(update, context)
    elif query.data == "menu_report":
        return await report_menu(update, context)
    elif query.data == "menu_setting":
        # 这个回调现在由 setting_conversation 处理
        logger.info("menu_setting 回调被触发，但由 setting_conversation 处理")
        return ConversationHandler.END
    elif query.data == "menu_help":
        await help_command(update, context)
        return ConversationHandler.END
    
    # 销售记录回调
    elif query.data == "back_sales":
        return await sales_menu(update, context)
    elif query.data == "sales_list":
        await sales_list_handler(update, context)
        return ConversationHandler.END
    elif query.data in ["client_company", "client_agent"]:
        return await sales_client_handler(update, context)
    elif query.data == "sales_save":
        return await sales_save_handler(update, context)
    elif query.data.startswith("pic_"):
        return await sales_person_handler(update, context)
    elif query.data.startswith("agent_"):
        return await sales_agent_select_handler(update, context)
    
    # 费用管理回调
    elif query.data == "back_cost":
        return await cost_menu(update, context)
    elif query.data in ["cost_purchasing", "cost_billing", "cost_salary"]:
        return await cost_type_handler(update, context)
    elif query.data.startswith("billing_"):
        return await cost_type_handler(update, context)
    elif query.data == "cost_list":
        await cost_list_handler(update, context)
        return ConversationHandler.END
    elif query.data.startswith("supplier_"):
        return await cost_supplier_handler(update, context)
    
    # 报表生成回调
    elif query.data == "back_report":
        return await report_menu(update, context)
    elif query.data == "report_current":
        return await report_current_handler(update, context)
    elif query.data == "report_custom":
        return await report_custom_handler(update, context)
    elif query.data == "report_yearly":
        await report_yearly_handler(update, context)
        return ConversationHandler.END
    
    # 默认返回主菜单
    else:
        await start_command(update, context)
        return ConversationHandler.END

# ====================================
# 工具函数区 - 辅助功能
# ====================================

async def close_other_conversations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """关闭其他进行中的会话，防止状态冲突"""
    # 清除所有用户临时数据
    context.user_data.clear()
    
    # 记录会话切换
    logger.info(f"用户 {update.effective_user.id} 切换会话，清除临时数据")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理未知命令"""
    keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "❓ 未知命令，请使用菜单按钮进行操作",
        reply_markup=reply_markup
    )

async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理非命令文本消息"""
    # 如果不在会话中，引导用户使用菜单
    if not context.user_data:
        keyboard = [[InlineKeyboardButton("🏠 主菜单", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "💡 请使用下方按钮进行操作",
            reply_markup=reply_markup
        )

# ====================================
# 错误处理区
# ====================================

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """全局错误处理"""
    logger.error(f"更新 {update} 引发错误 {context.error}")
    
    # 尝试发送错误消息给用户
    try:
        keyboard = [[InlineKeyboardButton("🏠 返回主菜单", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        error_message = "❌ 系统出现错误，请稍后重试"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                error_message,
                reply_markup=reply_markup
            )
        elif update.message:
            await update.message.reply_text(
                error_message,
                reply_markup=reply_markup
            )
    except Exception as e:
        logger.error(f"发送错误消息失败: {e}")

# ====================================
# 会话状态管理区 - ConversationHandler 配置
# ====================================

# 定义全局对话处理器变量
sales_conversation = None
expenses_conversation = None
report_conversation = None
setting_conversation = None
sales_callback_handler = callback_query_handler
expenses_callback_handler = callback_query_handler
report_callback_handler = callback_query_handler
close_session_handler = callback_query_handler
general_callback_handler = callback_query_handler

def get_conversation_handlers():
    """获取所有会话处理器配置"""
    
    global sales_conversation, expenses_conversation, report_conversation, setting_conversation
    
    # 系统设置会话处理器
    setting_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(setting_category_handler, pattern="^setting_create_"),
            CommandHandler("Setting", setting_command),
            # 添加菜单入口点 - 使用专门的处理函数
            CallbackQueryHandler(menu_setting_handler, pattern="^menu_setting$")
        ],
        states={
            SETTING_CATEGORY: [CallbackQueryHandler(setting_category_handler, pattern="^setting_create_")],
            SETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_name_handler)],
            SETTING_IC: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_ic_handler)],
            SETTING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_type_handler)],
            SETTING_RATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_rate_handler)]
        },
        fallbacks=[
            CallbackQueryHandler(callback_query_handler),
            CommandHandler("cancel", cancel_command)
        ],
        name="setting_conversation",
        persistent=False
    )
    
    # 销售记录会话处理器
    sales_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(sale_invoice_command, pattern="^sales_add$"),
            CommandHandler("SaleInvoice", sale_invoice_command),
            # 添加菜单入口点
            CallbackQueryHandler(lambda u, c: sale_invoice_command(u, c), pattern="^menu_sales$")
        ],
        states={
            SALES_PERSON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, sales_person_handler),
                CallbackQueryHandler(sales_person_handler, pattern="^pic_")
            ],
            SALES_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_amount_handler)],
            SALES_CLIENT: [CallbackQueryHandler(sales_client_handler, pattern="^client_")],
            SALES_COMMISSION_TYPE: [CallbackQueryHandler(sales_commission_type_handler, pattern="^commission_")],
            SALES_COMMISSION_PERCENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_commission_percent_handler)],
            SALES_COMMISSION_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, sales_commission_amount_handler)],
            SALES_AGENT_SELECT: [CallbackQueryHandler(sales_agent_select_handler, pattern="^agent_")],
            SALES_CONFIRM: [
                CallbackQueryHandler(sales_save_handler, pattern="^sales_save$"),
                CallbackQueryHandler(callback_query_handler, pattern="^back_main$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(callback_query_handler),
            CommandHandler("cancel", cancel_command)
        ],
        name="sales_conversation",
        persistent=False
    )
    
    # 费用管理会话处理器
    expenses_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(cost_type_handler, pattern="^cost_purchasing$|^cost_billing$|^cost_salary$"),
            CallbackQueryHandler(cost_menu, pattern="^menu_cost$"),
            CallbackQueryHandler(cost_list_handler, pattern="^cost_list$")
        ],
        states={
            COST_TYPE: [
                CallbackQueryHandler(cost_type_handler, pattern="^cost_|^billing_")
            ],
            COST_SUPPLIER: [
                CallbackQueryHandler(cost_supplier_handler, pattern="^supplier_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_supplier_handler)
            ],
            COST_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cost_amount_handler)
            ],
            COST_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, cost_desc_handler)
            ],
            COST_RECEIPT: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, cost_receipt_handler),
                CallbackQueryHandler(lambda u, c: show_cost_confirmation(u, c), pattern="^skip_receipt$"),
                CallbackQueryHandler(receipt_upload_prompt, pattern="^upload_receipt$"),
                CommandHandler("skip", lambda u, c: show_cost_confirmation(u, c))
            ],
            COST_CONFIRM: [
                CallbackQueryHandler(cost_save_handler, pattern="^cost_save$")
            ]
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: cost_menu(u, c), pattern="^back_cost$"),
            CallbackQueryHandler(callback_query_handler, pattern="^back_main$"),
            CommandHandler("cancel", cancel_command)
        ],
        name="cost_conversation",
        persistent=False
    )
    
    # 报表生成会话处理器
    report_conversation = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(report_custom_handler, pattern="^report_custom$")
        ],
        states={
            REPORT_TYPE: [CallbackQueryHandler(callback_query_handler, pattern="^report_")],
            REPORT_MONTH: [MessageHandler(filters.TEXT & ~filters.COMMAND, report_month_handler)]
        },
        fallbacks=[
            CallbackQueryHandler(callback_query_handler),
            CommandHandler("cancel", cancel_command)
        ],
        name="report_conversation",
        persistent=False
    )
    
    return [sales_conversation, expenses_conversation, report_conversation, setting_conversation]

# ====================================
# 主处理器注册函数
# ====================================

def register_handlers(application):
    """注册所有处理器到应用程序"""
    
    # 初始化对话处理器
    get_conversation_handlers()
    
    # 添加会话处理器
    for conversation in [sales_conversation, expenses_conversation, report_conversation, setting_conversation]:
        if conversation:
            application.add_handler(conversation)
    
    # 基础命令处理器
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("Setting", setting_command))
    application.add_handler(CommandHandler("SaleInvoice", sale_invoice_command))
    
    # 回调查询处理器 (放在会话处理器之后)
    application.add_handler(CallbackQueryHandler(sales_callback_handler, pattern='^sales_'))
    application.add_handler(CallbackQueryHandler(expenses_callback_handler, pattern='^(cost_|expenses_)'))
    application.add_handler(CallbackQueryHandler(report_callback_handler, pattern='^report_'))
    application.add_handler(CallbackQueryHandler(close_session_handler, pattern='^close_session$'))
    application.add_handler(CallbackQueryHandler(general_callback_handler))
    
    # 文本消息处理器
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))
    
    # 未知命令处理器
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # 错误处理器
    application.add_error_handler(error_handler)
    
    logger.info("所有处理器已成功注册")

async def setting_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理 /Setting 命令 - 系统设置直接命令"""
    # 清除用户数据
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("👨‍💼  Create Agent", callback_data="setting_create_agent")],
        [InlineKeyboardButton("🏭  Create Supplier", callback_data="setting_create_supplier")],
        [InlineKeyboardButton("👷  Create Worker", callback_data="setting_create_worker")],
        [InlineKeyboardButton("👑  Create Person in Charge", callback_data="setting_create_pic")],
        [InlineKeyboardButton("🔙  Back to Main Menu", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "⚙️ <b>SYSTEM SETTINGS</b>\n\n<b>Please select what to create:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    return SETTING_CATEGORY

async def setting_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理设置类别选择"""
    query = update.callback_query
    await query.answer()
    
    category_data = query.data.replace("setting_create_", "")
    context.user_data['setting_category'] = category_data
    
    category_names = {
        "agent": "Agent",
        "supplier": "Supplier",
        "worker": "Worker",
        "pic": "Person in Charge"
    }
    
    category_emojis = {
        "agent": "👨‍💼",
        "supplier": "🏭",
        "worker": "👷",
        "pic": "👑"
    }
    
    category_name = category_names.get(category_data, "Item")
    category_emoji = category_emojis.get(category_data, "➕")
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"{category_emoji} <b>Create {category_name}</b>\n\n<b>Please enter a name:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    return SETTING_NAME

async def setting_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理名称输入"""
    name = update.message.text.strip()
    context.user_data['setting_name'] = name
    
    category = context.user_data.get('setting_category')
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    category_emojis = {
        "agent": "👨‍💼",
        "supplier": "🏭",
        "worker": "👷",
        "pic": "👑"
    }
    emoji = category_emojis.get(category, "➕")
    
    if category == "agent":
        await update.message.reply_text(
            f"{emoji} *Name:* {name}\n\n*Please enter IC number:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return SETTING_IC
    elif category == "supplier":
        await update.message.reply_text(
            f"{emoji} *Name:* {name}\n\n*Please enter supplier category:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return SETTING_TYPE
    else:
        # 对于工作人员和负责人，直接保存
        try:
            sheets_manager = SheetsManager()
            category_names = {
                "worker": "Worker",
                "pic": "Person in Charge"
            }
            category_name = category_names.get(category, "Item")
            
            # 创建一个简单的数据结构，类似于其他添加方法
            setting_data = {
                'name': name,
                'status': '激活'
            }
            
            # 使用已有的方法添加数据
            if category == "worker":
                sheets_manager.add_worker(setting_data)
            else:  # pic
                sheets_manager.add_pic(setting_data)
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"✅ {category_name} \"{name}\" has been successfully added!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"添加{category}失败: {e}")
            await update.message.reply_text("❌ 添加失败，请重试")
        
        return ConversationHandler.END

async def setting_ic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理IC号码输入"""
    ic = update.message.text.strip()
    name = context.user_data.get('setting_name')
    
    try:
        sheets_manager = SheetsManager()
        
        # 添加代理商，包含IC号码
        agent_data = {
            'name': name,
            'ic': ic,
            'status': '激活'
        }
        
        sheets_manager.add_agent(agent_data)
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Agent \"{name}\" (IC: {ic}) has been successfully added!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"添加代理商失败: {e}")
        await update.message.reply_text("❌ Failed to add. Please try again.")
    
    context.user_data.clear()
    return ConversationHandler.END

async def setting_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理类型输入"""
    type_value = update.message.text.strip()
    context.user_data['setting_type'] = type_value
    
    category = context.user_data.get('setting_category')
    name = context.user_data.get('setting_name')
    ic = context.user_data.get('setting_ic', '')
    
    # 如果是代理商，需要输入佣金比例
    if category == "agent":
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"👨‍💼 <b>Name:</b> {name}\n<b>IC:</b> {ic}\n<b>Type:</b> {type_value}\n\n<b>Please enter commission rate (e.g. 5%):</b>",
            reply_markup=reply_markup
        )
        return SETTING_RATE
    
    # 其他类型，直接保存
    try:
        sheets_manager = SheetsManager()
        
        if category == "supplier":
            data = {
                'name': name,
                'contact': ic,
                'phone': '',
                'email': '',
                'products': type_value,
                'status': '激活'
            }
            sheets_manager.add_supplier(data)
        elif category == "worker":
            data = {
                'name': name,
                'contact': ic,
                'phone': '',
                'position': type_value,
                'status': '激活'
            }
            sheets_manager.add_worker(data)
        elif category == "pic":
            data = {
                'name': name,
                'contact': ic,
                'phone': '',
                'department': type_value,
                'status': '激活'
            }
            sheets_manager.add_pic(data)
        
        # 显示成功消息
        category_names = {
            "agent": "Agent",
            "supplier": "Supplier",
            "worker": "Worker",
            "pic": "Person in Charge"
        }
        
        category_emojis = {
            "agent": "👨‍💼",
            "supplier": "🏭",
            "worker": "👷",
            "pic": "👑"
        }
        
        emoji = category_emojis.get(category, "➕")
        category_name = category_names.get(category, "Item")
        
        success_message = f"{emoji} <b>{category_name} created successfully!</b>\n\n"
        success_message += f"<b>Name:</b> {name}\n"
        
        if ic:
            success_message += f"<b>IC/Contact:</b> {ic}\n"
        if type_value:
            success_message += f"<b>Type:</b> {type_value}\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            success_message,
            reply_markup=reply_markup
        )
        
        # 清除用户数据
        context.user_data.clear()
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"保存设置失败: {e}")
        await update.message.reply_text("❌ <b>Failed to save</b>\n\nPlease try again later.", parse_mode=ParseMode.HTML)
        return ConversationHandler.END

async def sale_invoice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理 /SaleInvoice 命令或 menu_sales 回调 - 直接开始添加销售记录"""
    # 清除用户数据
    context.user_data.clear()
    
    # 判断是命令还是回调查询
    is_callback = update.callback_query is not None
    
    try:
        # 获取负责人列表
        sheets_manager = SheetsManager()
        pics = sheets_manager.get_pics(active_only=True)
        
        if not pics:
            # 如果没有负责人数据，显示提示信息
            keyboard = [[InlineKeyboardButton("⚙️ 创建负责人", callback_data="setting_create_pic")],
                        [InlineKeyboardButton("❌ 取消", callback_data="back_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = "⚠️ <b>未找到负责人数据</b>\n\n请先创建负责人后再使用此功能。"
            
            if is_callback:
                await update.callback_query.edit_message_text(
                    message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
            return ConversationHandler.END
            
        # 创建负责人选择按钮
        keyboard = []
        for pic in pics:
            # 使用姓名作为按钮文本
            name = pic.get('姓名', '')
            if name:
                keyboard.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"pic_{name}")])
        
        # 添加取消按钮
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = "👤 <b>Select Person in Charge:</b>"
        
        if is_callback:
            await update.callback_query.edit_message_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        
        logger.info("已显示负责人选择界面")
        # 返回的是新的状态，因为我们需要一个回调来处理选择
        return SALES_PERSON
        
    except Exception as e:
        logger.error(f"获取负责人列表失败: {e}")
        error_message = "❌ <b>Failed to get person in charge data</b>\n\nPlease try again later."
        
        if is_callback:
            await update.callback_query.edit_message_text(
                error_message,
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(
                error_message,
                parse_mode=ParseMode.HTML
            )
        return ConversationHandler.END

async def cost_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看费用记录"""
    query = update.callback_query
    await query.answer()
    
    try:
        sheets_manager = SheetsManager()
        # 获取最近的费用记录
        expense_records = sheets_manager.get_expense_records(month=None)
        
        if not expense_records:
            message = "📋 <b>No expense records found</b>"
        else:
            # 表头映射
            header_mapping = {
                '日期': 'date',
                '费用类型': 'type',
                '供应商': 'supplier',
                '金额': 'amount',
                '类别': 'category',
                '备注': 'description'
            }
            
            # 转换记录中的键名
            converted_records = []
            for record in expense_records:
                converted_record = {}
                for zh_key, en_key in header_mapping.items():
                    if zh_key in record:
                        converted_record[en_key] = record[zh_key]
                converted_records.append(converted_record)
            
            # 只显示最近10条记录
            recent_records = converted_records[:10]
            message = "📋 <b>RECENT EXPENSE RECORDS</b>\n\n"
            for record in recent_records:
                message += f"📅 <b>Date:</b> {record.get('date', 'N/A')}\n"
                message += f"📋 <b>Type:</b> {record.get('type', 'N/A')} | 💰 <b>Amount:</b> RM{float(record.get('amount', 0)):,.2f}\n"
                if record.get('supplier'):
                    message += f"🏭 <b>Supplier:</b> {record.get('supplier')}\n"
                if record.get('description'):
                    message += f"📝 <b>Description:</b> {record.get('description')}\n"
                message += "\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="menu_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"获取费用记录失败: {e}")
        await query.edit_message_text(
            "❌ <b>Failed to get expense records</b>\n\nPlease try again later.",
            parse_mode=ParseMode.HTML
        )

async def setting_rate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理代理商佣金比例输入"""
    rate_input = update.message.text.strip()
    
    try:
        # 尝试将输入转换为浮点数
        rate = float(rate_input.replace('%', '')) / 100
        if rate < 0 or rate > 1:
            await update.message.reply_text("⚠️ <b>Invalid rate</b>\n\nPlease enter a percentage between 0-100%.", parse_mode=ParseMode.HTML)
            return SETTING_RATE
            
        context.user_data['setting_rate'] = rate
        
        # 获取之前收集的数据
        category = context.user_data.get('setting_category')
        name = context.user_data.get('setting_name')
        ic = context.user_data.get('setting_ic', '')
        type_value = context.user_data.get('setting_type', '')
        
        # 保存到Google Sheets
        try:
            sheets_manager = SheetsManager()
            
            if category == "agent":
                data = {
                    'name': name,
                    'contact': ic,
                    'phone': '',
                    'email': '',
                    'commission_rate': rate,
                    'status': '激活'
                }
                sheets_manager.add_agent(data)
            
            # 显示成功消息
            category_names = {
                "agent": "Agent",
                "supplier": "Supplier",
                "worker": "Worker",
                "pic": "Person in Charge"
            }
            
            category_emojis = {
                "agent": "👨‍💼",
                "supplier": "🏭",
                "worker": "👷",
                "pic": "👑"
            }
            
            emoji = category_emojis.get(category, "➕")
            category_name = category_names.get(category, "Item")
            
            success_message = f"{emoji} <b>{category_name} created successfully!</b>\n\n"
            success_message += f"<b>Name:</b> {name}\n"
            
            if ic:
                success_message += f"<b>IC/Contact:</b> {ic}\n"
            if type_value:
                success_message += f"<b>Type:</b> {type_value}\n"
            if rate:
                success_message += f"<b>Commission Rate:</b> {rate*100:.1f}%\n"
            
            keyboard = [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_html(
                success_message,
                reply_markup=reply_markup
            )
            
            # 清除用户数据
            context.user_data.clear()
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"保存设置失败: {e}")
            await update.message.reply_text("❌ <b>Failed to save</b>\n\nPlease try again later.", parse_mode=ParseMode.HTML)
            return ConversationHandler.END
            
    except ValueError:
        await update.message.reply_text("⚠️ <b>Invalid format</b>\n\nPlease enter a valid percentage (e.g. 5 or 5%).", parse_mode=ParseMode.HTML)
        return SETTING_RATE

async def sales_agent_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理代理商选择"""
    query = update.callback_query
    await query.answer()
    
    agent_data = query.data
    if agent_data.startswith("agent_"):
        # 解析代理商数据 agent_{name}_{commission}
        parts = agent_data[6:].split('_')
        if len(parts) >= 1:
            agent_name = parts[0]
            context.user_data['sales_agent'] = agent_name
            
            # 获取代理商默认佣金比例（如果有）
            default_commission = ""
            if len(parts) >= 2:
                default_commission = parts[1]
            
            # 显示佣金计算方式选择界面
            amount = context.user_data['sales_amount']
            
            keyboard = [
                [InlineKeyboardButton("💯 Set Commission Percentage", callback_data="commission_percent")],
                [InlineKeyboardButton("💰 Enter Fixed Commission Amount", callback_data="commission_amount")],
                [InlineKeyboardButton("❌ Cancel", callback_data="back_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message = f"""
🤝 <b>Agent:</b> {agent_name}
💰 <b>Amount:</b> RM{amount:,.2f}
{f"💵 <b>Default Commission Rate:</b> {default_commission}" if default_commission else ""}

<b>Please select commission calculation method:</b>
"""
            
            await query.edit_message_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
            # 返回佣金计算方式选择状态
            return SALES_COMMISSION_TYPE
    
    # 未知回调数据
    await query.edit_message_text("❌ Unknown operation, please start again")
    return ConversationHandler.END

async def receipt_upload_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """提示用户上传收据"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "📸 <b>Please upload a photo or document as receipt</b>\n\n"
        "<i>You can also use /skip to continue without receipt</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return COST_RECEIPT

# 添加一个新函数用于处理菜单回调
async def menu_setting_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理从主菜单进入Setting的回调"""
    query = update.callback_query
    await query.answer()
    
    # 清除用户数据
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("👨‍💼  Create Agent", callback_data="setting_create_agent")],
        [InlineKeyboardButton("🏭  Create Supplier", callback_data="setting_create_supplier")],
        [InlineKeyboardButton("👷  Create Worker", callback_data="setting_create_worker")],
        [InlineKeyboardButton("👑  Create Person in Charge", callback_data="setting_create_pic")],
        [InlineKeyboardButton("🔙  Back to Main Menu", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "⚙️ <b>SYSTEM SETTINGS</b>\n\n<b>Please select what to create:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    return SETTING_CATEGORY
