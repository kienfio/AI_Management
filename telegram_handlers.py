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
import asyncio
import traceback

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
COST_TYPE, COST_SUPPLIER, COST_AMOUNT, COST_DESC, COST_RECEIPT, COST_CONFIRM, COST_WORKER = range(7)  # 添加 COST_WORKER 状态

# 工人薪资计算相关状态
WORKER_BASIC_SALARY, WORKER_ALLOWANCE, WORKER_OT, WORKER_DEDUCTIONS, WORKER_EPF_RATE, WORKER_CONFIRM = range(10, 16)

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

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """回到主菜单"""
    return await start_command(update, context)

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
# 系统设置区 - 代理商、供应商、工人、负责人
# ====================================

async def setting_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理 /settings 命令"""
    return await setting_menu(update, context)

async def setting_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """设置主菜单"""
    # 清除用户数据
    context.user_data.clear()
    
    keyboard = [
        [InlineKeyboardButton("👨‍💼 Add Agent", callback_data="setting_create_agent")],
        [InlineKeyboardButton("🏭 Add Supplier", callback_data="setting_create_supplier")],
        [InlineKeyboardButton("👷 Add Worker", callback_data="setting_create_worker")],
        [InlineKeyboardButton("👨‍💼 Add PIC", callback_data="setting_create_pic")],
        [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "⚙️ <b>SETTINGS</b>\n\nPlease select an option:"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            message, 
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_html(
            message,
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def setting_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理设置类别选择"""
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("category_", "")
    context.user_data['setting_category'] = category
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    categories = {
        "agent": "Agent",
        "supplier": "Supplier",
        "worker": "Worker",
        "pic": "Person in Charge"
    }
    
    category_name = categories.get(category, "Unknown")
    
    await query.edit_message_text(
        f"✏️ <b>Adding {category_name}</b>\n\nPlease enter name:",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return SETTING_NAME

async def setting_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理名称输入"""
    name = update.message.text.strip()
    context.user_data['setting_name'] = name
    
    category = context.user_data.get('setting_category', '')
    
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 根据不同类别请求不同信息
    if category == "agent":
        await update.message.reply_html(
            f"👨‍💼 <b>Agent Name:</b> {name}\n\n<b>Please enter IC/Contact Number:</b>",
            reply_markup=reply_markup
        )
        return SETTING_IC
    elif category == "supplier":
        await update.message.reply_html(
            f"🏭 <b>Supplier Name:</b> {name}\n\n<b>Please enter Contact Person:</b>",
            reply_markup=reply_markup
        )
        return SETTING_IC
    elif category == "worker":
        await update.message.reply_html(
            f"👷 <b>Worker Name:</b> {name}\n\n<b>Please enter Contact Number:</b>",
            reply_markup=reply_markup
        )
        return SETTING_IC
    elif category == "pic":
        await update.message.reply_html(
            f"👨‍💼 <b>PIC Name:</b> {name}\n\n<b>Please enter Contact Number:</b>",
            reply_markup=reply_markup
        )
        return SETTING_IC
    
    # 未知类别
    await update.message.reply_text("❌ Unknown category")
    return ConversationHandler.END

async def setting_ic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理IC/联系方式输入"""
    ic = update.message.text.strip()
    context.user_data['setting_ic'] = ic
    
    category = context.user_data.get('setting_category', '')
    name = context.user_data.get('setting_name', '')
    
    keyboard = [
        [InlineKeyboardButton("✅ Active", callback_data="type_active")],
        [InlineKeyboardButton("❌ Inactive", callback_data="type_inactive")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 特殊处理代理商
    if category == "agent":
        await update.message.reply_html(
            f"👨‍💼 <b>Agent Name:</b> {name}\n<b>IC/Contact:</b> {ic}\n\n<b>Please enter commission rate (%):</b>",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]])
        )
        return SETTING_RATE
    
    # 其他类别设置状态
    ic_label = "Contact" if category != "agent" else "IC/Contact"
    
    await update.message.reply_html(
        f"<b>{category.capitalize()} Name:</b> {name}\n<b>{ic_label}:</b> {ic}\n\n<b>Please select status:</b>",
        reply_markup=reply_markup
    )
    
    return SETTING_TYPE

async def setting_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理类型/状态选择"""
    query = update.callback_query
    await query.answer()
    
    status = "Active" if query.data == "type_active" else "Inactive"
    context.user_data['setting_status'] = status
    
    # 尝试保存到数据库
    try:
        sheets_manager = SheetsManager()
        
        category = context.user_data.get('setting_category', '')
        name = context.user_data.get('setting_name', '')
        ic = context.user_data.get('setting_ic', '')
        
        # 准备数据
        data = {
            "name": name,
            "contact": ic,  # 使用同一字段存储IC或联系方式
            "status": status
        }
        
        # 根据不同类别调用不同方法
        if category == "agent":
            # 代理商需要先设置佣金率
            return SETTING_TYPE
        elif category == "supplier":
            sheets_manager.add_supplier(data)
        elif category == "worker":
            sheets_manager.add_worker(data)
        elif category == "pic":
            sheets_manager.add_pic(data)
        
        # 显示成功消息
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ {category.capitalize()} \"{name}\" has been successfully added!",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"保存设置失败: {e}")
        await query.edit_message_text(
            "❌ Failed to save. Please try again later.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]])
        )
    
    return ConversationHandler.END

async def setting_rate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理佣金率输入"""
    try:
        rate_text = update.message.text.strip().replace('%', '')
        rate = float(rate_text)
        
        # 验证合理性
        if rate < 0 or rate > 100:
            await update.message.reply_text("⚠️ 请输入0-100之间的百分比")
            return SETTING_RATE
        
        context.user_data['setting_rate'] = rate
        
        # 设置状态选择
        keyboard = [
            [InlineKeyboardButton("✅ Active", callback_data="type_active")],
            [InlineKeyboardButton("❌ Inactive", callback_data="type_inactive")],
            [InlineKeyboardButton("❌ Cancel", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        name = context.user_data.get('setting_name', '')
        ic = context.user_data.get('setting_ic', '')
        
        await update.message.reply_html(
            f"👨‍💼 <b>Agent Name:</b> {name}\n<b>IC/Contact:</b> {ic}\n<b>Commission Rate:</b> {rate}%\n\n<b>Please select status:</b>",
            reply_markup=reply_markup
        )
        
        return SETTING_TYPE
        
    except ValueError:
        await update.message.reply_text("⚠️ 请输入有效的数字")
        return SETTING_RATE

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
        
        # 添加Bill to步骤
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"💰 <b>Amount:</b> RM{amount:,.2f}\n\n📝 <b>Please enter Bill to (customer/company name):</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        logger.info(f"金额处理完成，等待Bill to输入")
        return SALES_BILL_TO
    except ValueError as e:
        logger.error(f"金额解析错误: {e}")
        await update.message.reply_text("⚠️ Please enter a valid amount")
        return SALES_AMOUNT
    except Exception as e:
        logger.error(f"处理金额时发生未知错误: {e}")
        await update.message.reply_text("❌ Error processing, please re-enter the amount")
        return SALES_AMOUNT

async def sales_bill_to_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理Bill to输入"""
    bill_to = update.message.text.strip()
    context.user_data['bill_to'] = bill_to
    logger.info(f"接收到Bill to输入: {bill_to}")
    
    # 继续到客户类型选择
    keyboard = [
        [InlineKeyboardButton("🏢 Company", callback_data="client_company")],
        [InlineKeyboardButton("🤝 Agent", callback_data="client_agent")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    amount = context.user_data['sales_amount']
    
    await update.message.reply_text(
        f"💰 <b>Amount:</b> RM{amount:,.2f}\n"
        f"📝 <b>Bill to:</b> {bill_to}\n\n"
        f"🎯 <b>Select Client Type:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    logger.info(f"Bill to处理完成，等待客户类型选择")
    return SALES_CLIENT

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
        agents = sheets_manager.get_agents(active_only=False)  # 不需要过滤激活状态
        
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
            name = agent.get('name', agent.get('Name', ''))
            # 获取IC号码
            ic = agent.get('ic', agent.get('IC', agent.get('contact', agent.get('Contact', ''))))
            
            if name:
                # 在回调数据中包含IC号码
                keyboard.append([InlineKeyboardButton(f"🤝 {name}", callback_data=f"agent_{name}_{ic}")])
        
        # 添加取消按钮
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🤝 <b>Select Agent:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        logger.info(f"显示代理商选择界面，找到 {len(agents)} 个代理商")
        
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
            keyboard = [[InlineKeyboardButton("⚙️ Create Agent", callback_data="setting_create_agent")],
                        [InlineKeyboardButton("❌ Cancel", callback_data="back_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "⚠️ <b>No agents found</b>\n\nPlease create an agent first.",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        # 创建代理商选择按钮
        keyboard = []
        for agent in agents:
            # 使用姓名作为按钮文本
            name = agent.get('name', agent.get('Name', ''))
            if name:
                # 将代理商IC作为回调数据的一部分
                ic = agent.get('ic', agent.get('IC', ''))
                keyboard.append([InlineKeyboardButton(f"🤝 {name}", callback_data=f"agent_{name}_{ic}")])
        
        # 添加取消按钮
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 显示佣金信息
        amount = context.user_data['sales_amount']
        
        message = f"""
💰 <b>Amount:</b> RM{amount:,.2f}

🤝 <b>Please select an agent:</b>
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
            "❌ <b>Failed to get agent data</b>\n\nPlease try again later.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

# 创建一个辅助函数来显示确认信息
async def show_sales_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示销售确认信息"""
    try:
        # 获取数据
        person = context.user_data['sales_person']
        amount = context.user_data['sales_amount']
        client_type = context.user_data['sales_client']
        bill_to = context.user_data.get('bill_to', '')
        
        # 获取佣金信息
        commission_amount = context.user_data['sales_commission']
        commission_rate = context.user_data.get('commission_rate', 0)
        commission_type = context.user_data.get('commission_type', '')
        
        # 获取代理商信息
        agent_info = ""
        if client_type == "Agent" and 'sales_agent' in context.user_data:
            agent_info = context.user_data['sales_agent']
        
        # 检查是否已上传PDF
        has_pdf = 'sales_invoice_pdf' in context.user_data and context.user_data['sales_invoice_pdf']
        
        # 构建确认消息
        confirm_message = f"""
💼 <b>SALES CONFIRMATION</b>

👤 <b>Personal in Charge:</b> {person}
💰 <b>Amount:</b> RM{amount:,.2f}
📝 <b>Bill to:</b> {bill_to}
🏢 <b>Type:</b> {client_type}
"""

        if agent_info:
            confirm_message += f"🧑‍💼 <b>Agent:</b> {agent_info}\n"
        
        # 添加佣金信息
        if commission_type == 'percent':
            confirm_message += f"💵 <b>Commission:</b> RM{commission_amount:,.2f} ({commission_rate*100}%)\n"
        else:
            confirm_message += f"💵 <b>Commission:</b> RM{commission_amount:,.2f} (Fixed)\n"
        
        # 添加PDF信息
        if has_pdf:
            confirm_message += "📄 <b>Invoice PDF:</b> Uploaded\n"
        
        confirm_message += "\n<b>Please confirm the information:</b>"
        
        # 添加确认按钮
        keyboard = []
        
        # 如果尚未上传PDF，添加上传PDF按钮
        if not has_pdf:
            keyboard.append([InlineKeyboardButton("📄 Upload Invoice PDF", callback_data="upload_invoice_pdf")])
        
        keyboard.append([InlineKeyboardButton("✅ Save", callback_data="sales_save")])
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_sales")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 处理不同类型的更新
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                confirm_message,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            # 如果是从PDF上传处理器调用，删除之前的消息
            if hasattr(update, 'message') and update.message:
                try:
                    # 尝试删除"上传成功"的消息
                    await update.message.delete()
                except Exception as e:
                    logger.error(f"删除消息失败: {e}")
            
            # 发送新的确认消息
            await update.message.reply_html(
                confirm_message,
                reply_markup=reply_markup
            )
        
        return SALES_CONFIRM
        
    except Exception as e:
        logger.error(f"显示确认信息失败: {e}")
        error_message = "❌ Error showing confirmation. Please try again."
        
        if update.callback_query:
            await update.callback_query.answer()
            await update.callback_query.edit_message_text(
                error_message,
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(error_message)
        
        return ConversationHandler.END

async def sales_save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """保存销售记录"""
    query = update.callback_query
    await query.answer()
    
    try:
        # 保存到 Google Sheets
        sheets_manager = SheetsManager()
        
        # 准备数据
        client_type = context.user_data['sales_client']  # "Agent" 或 "Company"
        agent_name = ""
        agent_ic = ""
        
        if client_type == "Agent" and 'sales_agent' in context.user_data:
            agent_name = context.user_data['sales_agent']
            
            # 直接从context获取IC，如果有的话
            if 'agent_ic' in context.user_data:
                agent_ic = context.user_data['agent_ic']
            else:
                # 如果没有，尝试从代理商列表中获取
                agents = sheets_manager.get_agents()
                for agent in agents:
                    if agent.get('name') == agent_name:
                        agent_ic = agent.get('ic', '')
                        break
        
        # 获取佣金计算方式
        commission_type = context.user_data.get('commission_type', '')
        
        bill_to = context.user_data.get('bill_to', '')
        
        # 获取PDF链接（如果有）
        pdf_link = ""
        if 'sales_invoice_pdf' in context.user_data:
            pdf_data = context.user_data['sales_invoice_pdf']
            if isinstance(pdf_data, dict) and 'public_link' in pdf_data:
                pdf_link = pdf_data['public_link']
            elif isinstance(pdf_data, str):
                pdf_link = pdf_data
        
        # 只保留日期部分
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        sales_data = {
            'date': date_str,
            'person': context.user_data['sales_person'],
            'bill_to': bill_to,
            'amount': context.user_data['sales_amount'],
            'type': client_type,  # "Agent" 或 "Company"
            'agent_name': agent_name,
            'agent_ic': agent_ic,
            'commission_rate': context.user_data.get('commission_rate', 0),  # 修正键名为commission_rate
            'commission_amount': context.user_data['sales_commission'],      # 修正键名为commission_amount
            'invoice_pdf': pdf_link  # 添加PDF链接
        }
        
        sheets_manager.add_sales_record(sales_data)
        
        # 显示成功消息，包含保存的信息
        amount = context.user_data['sales_amount']
        commission = context.user_data['sales_commission']
        person = context.user_data['sales_person']
        
        success_message = f"""
✅ <b>Invoice saved successfully!</b>

👤 <b>Personal in Charge:</b> {person}
💰 <b>Amount:</b> RM{amount:,.2f}
📝 <b>Bill to:</b> {bill_to}
🏢 <b>Type:</b> {client_type}
"""

        if agent_name:
            success_message += f"🧑‍💼 <b>Agent:</b> {agent_name}\n"
            if agent_ic:
                success_message += f"🪪 <b>IC:</b> {agent_ic}\n"
                
        success_message += f"💵 <b>Commission:</b> RM{commission:,.2f}\n"
        
        # 添加PDF链接信息
        if pdf_link:
            success_message += f"📄 <b>Invoice PDF:</b> Uploaded\n"
            
        success_message += f"🕒 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
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
        sales_records = sheets_manager.get_sales_records()
        
        # 只显示最近10条记录
        sales_records = sales_records[-10:] if len(sales_records) > 10 else sales_records
        
        if not sales_records:
            message = "📋 <b>No sales records found</b>"
        else:
            message = "📋 <b>RECENT SALES RECORDS</b>\n\n"
            for record in sales_records:
                message += f"📅 <b>Date:</b> {record['date']}\n"
                message += f"👤 <b>PIC:</b> {record['person']}\n"
                message += f"💰 <b>Amount:</b> RM{record['amount']:,.2f}\n"
                message += f"🏢 <b>Type:</b> {record.get('type', '')}\n"
                
                if record.get('agent_name'):
                    message += f"🧑‍💼 <b>Agent:</b> {record['agent_name']}\n"
                    if record.get('agent_ic'):
                        message += f"🪪 <b>IC:</b> {record['agent_ic']}\n"
                
                message += f"💵 <b>Commission:</b> RM{record['commission']:,.2f}\n"
                
                # 添加PDF链接信息
                if record.get('invoice_pdf'):
                    message += f"📄 <b>Invoice PDF:</b> Available\n"
                    
                message += "-------------------------\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"获取销售记录失败: {e}")
        await query.edit_message_text("❌ Failed to retrieve records. Please try again.",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]))
        return ConversationHandler.END

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

async def cost_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看费用记录"""
    query = update.callback_query
    await query.answer()
    
    try:
        sheets_manager = SheetsManager()
        
        # 获取当前月份的费用记录
        current_month = datetime.now().strftime('%Y-%m')
        expense_records = sheets_manager.get_expense_records(current_month)
        
        # 只显示最近10条记录
        expense_records = expense_records[-10:] if len(expense_records) > 10 else expense_records
        
        if not expense_records:
            message = "📋 <b>当月没有费用记录</b>"
        else:
            message = "📋 <b>本月费用记录</b>\n\n"
            for record in expense_records:
                message += f"📅 <b>日期:</b> {record.get('date', '')}\n"
                message += f"📝 <b>类型:</b> {record.get('type', '')}\n"
                
                if record.get('type') == "Worker Salary":
                    message += f"👷 <b>工人:</b> {record.get('supplier', '')}\n"
                else:
                    message += f"🏭 <b>供应商:</b> {record.get('supplier', '')}\n"
                    
                message += f"💰 <b>金额:</b> RM{record.get('amount', 0):,.2f}\n"
                
                if record.get('receipt'):
                    message += f"📎 <b>收据:</b> 已上传\n"
                    
                message += "-------------------------\n\n"
        
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="menu_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"获取费用记录失败: {e}")
        await query.edit_message_text("❌ 获取记录失败，请重试",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_cost")]]))
        return ConversationHandler.END

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
            
            # 创建供应商选择按钮
            keyboard = []
            
            # 从Google表格中获取的供应商
            if suppliers:
                for supplier in suppliers:
                    # 使用供应商名称作为按钮文本
                    name = supplier.get('Name', supplier.get('name', ''))
                    if name:
                        keyboard.append([InlineKeyboardButton(f"🏭 {name}", callback_data=f"supplier_{name}")])
            
            # 如果没有供应商，显示一条消息
            if not keyboard:
                keyboard.append([InlineKeyboardButton("ℹ️ No suppliers found", callback_data="no_action")])
            
            # 添加自定义输入选项
            keyboard.append([InlineKeyboardButton("✏️ Other (Custom Input)", callback_data="supplier_other")])
            keyboard.append([InlineKeyboardButton("⚙️ Create Supplier", callback_data="setting_create_supplier")])
            
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
        # 对于工资支出，显示工作人员列表
        try:
            # 获取工作人员列表
            sheets_manager = SheetsManager()
            workers = sheets_manager.get_workers(active_only=True)
            
            # 创建工作人员选择按钮
            keyboard = []
            
            # 从Google表格中获取的工作人员
            if workers:
                for worker in workers:
                    # 使用工作人员名称作为按钮文本
                    name = worker.get('Name', worker.get('name', ''))
                    if name:
                        keyboard.append([InlineKeyboardButton(f"👷 {name}", callback_data=f"worker_{name}")])
            
            # 如果没有工作人员，显示一条消息
            if not keyboard:
                keyboard.append([InlineKeyboardButton("ℹ️ No workers found", callback_data="no_action")])
            
            # 添加自定义输入选项
            keyboard.append([InlineKeyboardButton("✏️ Other (Custom Input)", callback_data="worker_other")])
            keyboard.append([InlineKeyboardButton("⚙️ Create Worker", callback_data="setting_create_worker")])
            
            # 添加取消按钮
            keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_cost")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "👷 <b>Select Worker:</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
            return COST_WORKER
            
        except Exception as e:
            logger.error(f"获取工作人员列表失败: {e}")
            await query.edit_message_text(
                "❌ <b>Failed to get worker data</b>\n\nPlease try again later.",
                parse_mode=ParseMode.HTML
            )
            return ConversationHandler.END
    
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

async def cost_receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理收据上传"""
    try:
        # 获取文件
        if update.message.photo:
            file_id = update.message.photo[-1].file_id
            file_type = 'photo'
        elif update.message.document:
            file_id = update.message.document.file_id
            file_type = 'document'
        else:
            await update.message.reply_text("⚠️ 请上传照片或文档")
            return COST_RECEIPT
        
        # 获取文件对象
        file = await context.bot.get_file(file_id)
        logger.info(f"获取文件成功: {file.file_path}")
        
        # 下载文件内容
        file_stream = io.BytesIO()
        await file.download_to_memory(out=file_stream)
        file_stream.seek(0)  # 重置指针位置
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"receipt_{timestamp}.jpg" if file_type == 'photo' else file.file_name
        
        # 获取费用类型
        cost_type = context.user_data.get('cost_type', '')
        
        # 添加日志，记录原始费用类型
        logger.info(f"上传收据，原始费用类型: {cost_type}")
        
        # 处理特殊类型映射 - 将显示名称转换为文件夹类型
        type_mapping = {
            "water bill": "water",
            "electricity bill": "electricity",
            "wifi bill": "wifi",
            "purchasing": "purchasing"
        }
        
        # 转换为小写进行匹配
        cost_type_lower = cost_type.lower()
        drive_folder_type = type_mapping.get(cost_type_lower, cost_type)
        
        # 添加日志，记录映射后的类型
        logger.info(f"映射后的文件夹类型: {drive_folder_type}")
        
        # 检测是否为PDF文件
        is_pdf = False
        mime_type = file.mime_type if hasattr(file, 'mime_type') else 'image/jpeg'
        if mime_type == 'application/pdf' or (hasattr(file, 'file_name') and file.file_name and file.file_name.lower().endswith('.pdf')):
            is_pdf = True
            logger.info("检测到PDF文件")
        
        # 发送处理中的消息
        processing_message = await update.message.reply_text("⏳ 正在处理文件，请稍候...")
        
        # 直接使用GoogleDriveUploader上传文件
        try:
            from google_drive_uploader import get_drive_uploader
            
            # 获取正确初始化的drive_uploader实例
            drive_uploader = get_drive_uploader()
            logger.info(f"Google Drive上传器已初始化: {drive_uploader is not None}")
            
            # 上传文件
            logger.info(f"使用MIME类型: {mime_type}, 文件夹类型: {drive_folder_type}")
            
            # 如果是PDF文件，使用专用处理
            if is_pdf:
                logger.info("使用PDF专用上传逻辑")
                receipt_result = drive_uploader.upload_receipt(
                    file_stream, 
                    "invoice_pdf",  # 明确指定为PDF类型
                    'application/pdf'
                )
            else:
                # 普通收据上传
                receipt_result = drive_uploader.upload_receipt(
                    file_stream, 
                    drive_folder_type,  # 使用映射后的类型
                    mime_type
                )
            
            if receipt_result:
                # 处理返回结果可能是字典或字符串的情况
                if isinstance(receipt_result, dict):
                    public_link = receipt_result.get('public_link', '')
                    context.user_data['cost_receipt'] = receipt_result
                    await processing_message.delete()
                    await update.message.reply_text(f"✅ 收据已上传成功")
                    logger.info(f"收据上传成功，链接: {public_link}")
                else:
                    # 如果是字符串，直接使用
                    context.user_data['cost_receipt'] = receipt_result
                    await processing_message.delete()
                    await update.message.reply_text(f"✅ 收据已上传成功")
                    logger.info(f"收据上传成功，链接: {receipt_result}")
            else:
                logger.error("上传结果为空")
                await processing_message.edit_text("❌ 收据上传失败")
                context.user_data['cost_receipt'] = None
        except Exception as e:
            logger.error(f"上传收据失败: {e}", exc_info=True)
            await update.message.reply_text("❌ 收据上传失败，请稍后再试")
            context.user_data['cost_receipt'] = None
        
        # 继续到确认页面
        return await show_cost_confirmation(update, context)
        
    except Exception as e:
        logger.error(f"处理收据时出错: {e}", exc_info=True)
        await update.message.reply_text("❌ 处理收据时出错，请重试")
        return COST_RECEIPT

async def cost_save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理费用保存"""
    query = update.callback_query
    await query.answer()
    
    try:
        # 获取数据
        cost_type = context.user_data['cost_type']
        amount = context.user_data['cost_amount']
        supplier = context.user_data.get('cost_supplier', '')
        worker = context.user_data.get('cost_worker', '')
        desc = context.user_data.get('cost_desc', '')
        receipt_link = context.user_data.get('cost_receipt', '')
        
        # 处理收据链接可能是字典的情况
        if isinstance(receipt_link, dict) and 'public_link' in receipt_link:
            receipt_link = receipt_link['public_link']
        
        # 记录到Google Sheets
        date_str = datetime.now().strftime('%Y-%m-%d')
        
        sheets_manager = SheetsManager()
        data = {
            'date': date_str,
            'type': cost_type,
            'supplier': supplier if cost_type != "Worker Salary" else worker,  # 如果是工资，使用工作人员名称
            'amount': amount,
            'category': supplier if supplier else (worker if worker else 'Other'),
            'description': desc,
            'receipt': receipt_link  # 使用Google Drive链接
        }
        
        # 如果是工资，并且启用了EPF或SOCSO，添加相关数据
        if cost_type == "Worker Salary":
            # 添加基本工资、津贴和加班费
            if 'basic_salary' in context.user_data:
                data['basic_salary'] = context.user_data['basic_salary']
            if 'allowance' in context.user_data:
                data['allowance'] = context.user_data['allowance']
            if 'overtime' in context.user_data:
                data['overtime'] = context.user_data['overtime']
            
            # 添加EPF相关数据
            if context.user_data.get('epf_enabled', False):
                data['epf_employee'] = context.user_data['epf_employee']
                data['epf_employer'] = context.user_data['epf_employer']
                data['epf_rate'] = context.user_data.get('employer_epf_rate', 13)
            
            # 添加SOCSO相关数据
            if context.user_data.get('socso_enabled', False):
                data['socso_employee'] = context.user_data['socso_employee']
                data['socso_employer'] = context.user_data['socso_employer']
            
            # 添加净工资
            if 'net_salary' in context.user_data:
                data['net_salary'] = context.user_data['net_salary']
            
            # 添加雇主总成本
            if 'total_employer_cost' in context.user_data:
                data['total_cost'] = context.user_data['total_employer_cost']
                
            # 更新描述信息，包含EPF和SOCSO状态
            epf_text = "EPF启用" if context.user_data.get('epf_enabled', False) else "EPF未启用"
            socso_text = "SOCSO启用" if context.user_data.get('socso_enabled', False) else "SOCSO未启用"
            data['description'] = f"{desc} ({epf_text}, {socso_text})"
        
        sheets_manager.add_expense_record(data)
        
        # 构建成功消息
        success_message = f"""
✅ <b>Expense has been saved successfully!</b>

📋 <b>Type:</b> {cost_type}
"""
        if cost_type == "Worker Salary" and worker:
            success_message += f"👷 <b>Worker:</b> {worker}\n"
            
            # 如果启用了EPF或SOCSO，显示详细信息
            if context.user_data.get('epf_enabled', False) or context.user_data.get('socso_enabled', False):
                basic_salary = context.user_data.get('basic_salary', 0)
                allowance = context.user_data.get('allowance', 0)
                overtime = context.user_data.get('overtime', 0)
                
                success_message += f"💰 <b>Basic Salary:</b> RM{basic_salary:,.2f}\n"
                if allowance > 0:
                    success_message += f"💵 <b>Allowance:</b> RM{allowance:,.2f}\n"
                if overtime > 0:
                    success_message += f"⏱️ <b>Overtime:</b> RM{overtime:,.2f}\n"
                
                if context.user_data.get('epf_enabled', False):
                    epf_employee = context.user_data.get('epf_employee', 0)
                    epf_employer = context.user_data.get('epf_employer', 0)
                    employer_epf_rate = context.user_data.get('employer_epf_rate', 13)
                    
                    success_message += f"💼 <b>EPF (Employee 11%):</b> RM{epf_employee:,.2f}\n"
                    success_message += f"🏢 <b>EPF (Employer {employer_epf_rate}%):</b> RM{epf_employer:,.2f}\n"
                
                if context.user_data.get('socso_enabled', False):
                    socso_employee = context.user_data.get('socso_employee', 0)
                    socso_employer = context.user_data.get('socso_employer', 0)
                    
                    success_message += f"🩺 <b>SOCSO (Employee 0.5%):</b> RM{socso_employee:,.2f}\n"
                    success_message += f"🏢 <b>SOCSO (Employer 1.75%):</b> RM{socso_employer:,.2f}\n"
                
                net_salary = context.user_data.get('net_salary', 0)
                success_message += f"🧾 <b>Net Salary:</b> RM{net_salary:,.2f}\n"
            else:
                success_message += f"💰 <b>Amount:</b> RM{amount:,.2f}\n"
        elif supplier:
            success_message += f"🏭 <b>Supplier:</b> {supplier}\n"
            success_message += f"💰 <b>Amount:</b> RM{amount:,.2f}\n"
        else:
            success_message += f"💰 <b>Amount:</b> RM{amount:,.2f}\n"
        
        if receipt_link:
            success_message += "📎 <b>Receipt:</b> Uploaded successfully\n"
        
        # 添加返回按钮
        keyboard = [[InlineKeyboardButton("🔙 Back to Menu", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            success_message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        # 清除用户数据
        context.user_data.clear()
        
        # 结束对话
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"保存费用记录失败: {e}")
        await query.edit_message_text(
            "❌ <b>Failed to save expense</b>\n\nPlease try again later.",
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END

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
        worker_name = context.user_data.get('cost_worker', '')
        desc = context.user_data.get('cost_desc', '')
        
        confirm_message = f"""
💵 <b>EXPENSE CONFIRMATION</b>

📋 <b>Type:</b> {cost_type}
"""
        # 如果有工作人员信息，显示工作人员名称
        if worker_name:
            confirm_message += f"👷 <b>Worker:</b> {worker_name}\n"
        
        # 如果有描述，显示描述
        if desc and not desc.startswith(f"Salary for {worker_name}"):
            confirm_message += f"📝 <b>Description:</b> {desc}\n"
            
        confirm_message += f"💰 <b>Amount:</b> RM{amount:,.2f}\n"
        
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
        # 新增LHDN报表相关选项
        [InlineKeyboardButton("📋 P&L 损益表", callback_data="report_pnl")],
        [InlineKeyboardButton("👨‍💼 员工薪资汇总", callback_data="report_salary")],
        [InlineKeyboardButton("💼 LHDN 税务摘要", callback_data="report_tax_summary")],
        [InlineKeyboardButton("💾 导出报表至Google Sheet", callback_data="report_export")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = """
📈 *报表中心*

请选择需要的报表类型：

基础报表：
• 📊 当月报表 - 查看本月收支情况
• 🗓️ 指定月份 - 查看指定月份的收支明细
• 📈 年度汇总 - 生成全年财务概览

马来西亚税务报表 (LHDN Form B):
• 📋 P&L 损益表 - 符合LHDN Working Sheets格式
• 👨‍💼 员工薪资汇总 - 含EPF/SOCSO明细
• 💼 LHDN 税务摘要 - 按Form B最新结构生成

导出功能：
• 💾 导出报表至Google Sheet - 同步更新所有报表
"""
    
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
# LHDN报表生成区 - 符合马来西亚税务要求
# ====================================

async def report_pnl_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理P&L损益表请求"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "⏳ 正在生成P&L损益表，请稍候...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # 获取当前年份
        current_year = datetime.now().year
        
        # 生成P&L报表
        sheets_manager = SheetsManager()
        pnl_data = sheets_manager.generate_pnl_report(current_year)
        
        # 构建报表消息
        message = f"""
📋 <b>P&L 损益表 ({current_year}年度)</b>
<i>符合LHDN Working Sheets格式</i>

<b>收入:</b>
• 总销售额: RM{pnl_data['sales_revenue']:,.2f}
• 佣金支出: RM{pnl_data['commission']:,.2f}
• 毛利润: RM{pnl_data['gross_profit']:,.2f}

<b>费用 (LHDN分类):</b>
• 折旧 (Depreciation): RM{pnl_data['depreciation']:,.2f}
• 自身薪资/津贴 (Own salary/allowance): RM{pnl_data['own_salary_allowance']:,.2f}
• 娱乐费用 (Entertainment): RM{pnl_data['entertainment']:,.2f}
• 礼品支出 (Gifts): RM{pnl_data['gifts']:,.2f}
• 罚款支出 (Penalties/fines): RM{pnl_data['penalties_fines']:,.2f}
• 其他费用 (Other expenses): RM{pnl_data['other_expenses']:,.2f}

<b>盈亏分析:</b>
• 总费用支出: RM{pnl_data['total_expenses']:,.2f}
• 净利润 (税前): RM{pnl_data['net_profit']:,.2f}

<i>注：此报表按照马来西亚LHDN税务要求格式生成</i>
"""
        
        # 添加返回按钮
        keyboard = [[InlineKeyboardButton("🔙 返回报表中心", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"生成P&L损益表失败: {e}")
        
        # 显示错误消息
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ 生成P&L损益表失败，请稍后重试",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def report_salary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理员工薪资汇总请求"""
    query = update.callback_query
    await query.answer()
    
    # 询问用户选择月份还是年度汇总
    keyboard = [
        [InlineKeyboardButton("📅 当月薪资", callback_data="salary_current_month")],
        [InlineKeyboardButton("📆 年度薪资汇总", callback_data="salary_yearly")],
        [InlineKeyboardButton("🔙 返回", callback_data="menu_report")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "👨‍💼 <b>员工薪资汇总</b>\n\n请选择汇总期间:",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

async def salary_current_month_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理当月薪资汇总请求"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "⏳ 正在生成当月薪资汇总，请稍候...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # 获取当前年月
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # 生成薪资汇总
        sheets_manager = SheetsManager()
        salary_data = sheets_manager.generate_salary_summary(current_year, current_month)
        
        if not salary_data:
            # 如果没有数据，显示提示信息
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="report_salary")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "ℹ️ <b>当月没有薪资记录</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        # 构建报表消息
        current_month_str = f"{current_year}-{current_month:02d}"
        message = f"👨‍💼 <b>员工薪资汇总 ({current_month_str})</b>\n\n"
        
        # 添加每个工人的薪资信息
        for i, worker in enumerate(salary_data):
            if i > 0:
                message += "\n" + "─" * 30 + "\n\n"
                
            message += f"<b>员工:</b> {worker['worker_name']}\n\n"
            message += f"<b>收入项:</b>\n"
            message += f"• 基本工资: RM{worker['basic_salary']:,.2f}\n"
            
            if worker['allowance'] > 0:
                message += f"• 津贴: RM{worker['allowance']:,.2f}\n"
                
            if worker['overtime'] > 0:
                message += f"• 加班费: RM{worker['overtime']:,.2f}\n"
            
            message += f"\n<b>法定扣除:</b>\n"
            
            if worker['epf_employee'] > 0 or worker['epf_employer'] > 0:
                message += f"• EPF (员工 11%): RM{worker['epf_employee']:,.2f}\n"
                message += f"• EPF (雇主 13%): RM{worker['epf_employer']:,.2f}\n"
                
            if worker['socso_employee'] > 0 or worker['socso_employer'] > 0:
                message += f"• SOCSO (员工 0.5%): RM{worker['socso_employee']:,.2f}\n"
                message += f"• SOCSO (雇主 1.75%): RM{worker['socso_employer']:,.2f}\n"
            
            message += f"\n<b>合计:</b>\n"
            message += f"• 净工资: RM{worker['net_salary']:,.2f}\n"
            message += f"• 雇主总成本: RM{worker['total_employer_cost']:,.2f}\n"
        
        # 添加返回按钮
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="report_salary")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"生成当月薪资汇总失败: {e}")
        
        # 显示错误消息
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="report_salary")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ 生成薪资汇总失败，请稍后重试",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def salary_yearly_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理年度薪资汇总请求"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "⏳ 正在生成年度薪资汇总，请稍候...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # 获取当前年份
        current_year = datetime.now().year
        
        # 生成薪资汇总
        sheets_manager = SheetsManager()
        salary_data = sheets_manager.generate_salary_summary(current_year)
        
        if not salary_data:
            # 如果没有数据，显示提示信息
            keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="report_salary")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"ℹ️ <b>{current_year}年度没有薪资记录</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            return ConversationHandler.END
        
        # 构建报表消息
        message = f"👨‍💼 <b>员工薪资年度汇总 ({current_year})</b>\n\n"
        
        # 添加每个工人的薪资信息
        for i, worker in enumerate(salary_data):
            if i > 0:
                message += "\n" + "─" * 30 + "\n\n"
                
            message += f"<b>员工:</b> {worker['worker_name']}\n\n"
            message += f"<b>年度收入:</b>\n"
            message += f"• 基本工资: RM{worker['basic_salary']:,.2f}\n"
            
            if worker['allowance'] > 0:
                message += f"• 津贴: RM{worker['allowance']:,.2f}\n"
                
            if worker['overtime'] > 0:
                message += f"• 加班费: RM{worker['overtime']:,.2f}\n"
            
            message += f"\n<b>年度法定扣除:</b>\n"
            
            if worker['epf_employee'] > 0 or worker['epf_employer'] > 0:
                message += f"• EPF (员工 11%): RM{worker['epf_employee']:,.2f}\n"
                message += f"• EPF (雇主): RM{worker['epf_employer']:,.2f}\n"
                
            if worker['socso_employee'] > 0 or worker['socso_employer'] > 0:
                message += f"• SOCSO (员工 0.5%): RM{worker['socso_employee']:,.2f}\n"
                message += f"• SOCSO (雇主 1.75%): RM{worker['socso_employer']:,.2f}\n"
            
            message += f"\n<b>年度合计:</b>\n"
            message += f"• 净工资: RM{worker['net_salary']:,.2f}\n"
            message += f"• 雇主总成本: RM{worker['total_employer_cost']:,.2f}\n"
        
        # 添加LHDN报税提示
        message += f"\n\n<i>注：此报表可用于员工LHDN EA/EC表格准备</i>"
        
        # 添加返回按钮
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="report_salary")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"生成年度薪资汇总失败: {e}")
        
        # 显示错误消息
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="report_salary")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ 生成薪资汇总失败，请稍后重试",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def report_tax_summary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理LHDN税务摘要请求"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "⏳ 正在生成LHDN税务摘要，请稍候...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # 获取当前年份
        current_year = datetime.now().year
        
        # 生成税务摘要
        sheets_manager = SheetsManager()
        tax_data = sheets_manager.generate_tax_summary(current_year)
        
        # 构建报表消息
        message = f"""
💼 <b>LHDN 税务摘要 ({current_year}年度)</b>
<i>符合 LHDN Form B 格式</i>

<b>1. 收入概要:</b>
• 总营业收入: RM{tax_data['total_revenue']:,.2f}

<b>2. 可扣除费用:</b>
• 业务支出: RM{tax_data['business_expenses']:,.2f}
• 折旧: RM{tax_data['depreciation']:,.2f} (不可直接扣除)

<b>3. 资本津贴与扣减:</b>
• 资本免税额: RM{tax_data['capital_allowances']:,.2f}

<b>4. 结算:</b>
• 前期亏损结转: RM{tax_data['business_loss_cf']:,.2f}
• 净课税收入: RM{tax_data['taxable_business_income']:,.2f}

<i>此报表按照马来西亚LHDN Form B要求格式生成，可用于准备税务申报</i>
<i>更新日期: {tax_data['updated_date']}</i>
"""
        
        # 添加返回按钮
        keyboard = [[InlineKeyboardButton("🔙 返回报表中心", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"生成税务摘要失败: {e}")
        
        # 显示错误消息
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ 生成税务摘要失败，请稍后重试",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def report_export_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理导出报表到Google Sheet请求"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "⏳ 正在导出所有报表到Google Sheets，请稍候...",
        parse_mode=ParseMode.HTML
    )
    
    try:
        # 获取当前年份
        current_year = datetime.now().year
        
        # 导出所有报表
        sheets_manager = SheetsManager()
        result = sheets_manager.export_all_reports(current_year)
        
        if result:
            # 导出成功
            message = f"""
✅ <b>所有报表已成功导出到Google Sheets</b>

📊 已导出的报表:
• P&L 损益表 (Monthly P&L)
• 员工薪资汇总 (Salary Summary)
• LHDN 税务摘要 (LHDN Tax Summary)

这些报表符合马来西亚LHDN最新格式要求，可用于准备税务申报。
"""
        else:
            # 导出失败
            message = "❌ <b>部分或所有报表导出失败</b>\n\n请检查日志了解详情。"
        
        # 添加返回按钮
        keyboard = [[InlineKeyboardButton("🔙 返回报表中心", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"导出报表失败: {e}")
        
        # 显示错误消息
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ 导出报表失败，请稍后重试",
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

async def custom_worker_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理自定义工作人员名称输入"""
    # 检查是否正在等待自定义工作人员输入
    if not context.user_data.get('waiting_for_custom_worker'):
        return COST_WORKER
    
    # 获取用户输入的工作人员名称
    worker_name = update.message.text.strip()
    context.user_data['cost_worker'] = worker_name
    context.user_data['cost_desc'] = f"Salary for {worker_name}"  # 自动设置描述
    
    # 清除等待标记
    context.user_data.pop('waiting_for_custom_worker', None)
    
    # 显示基本工资输入界面
    keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_html(
        f"👷 <b>Worker:</b> {worker_name}\n\n<b>Please enter basic salary amount:</b>",
        reply_markup=reply_markup
    )
    
    return WORKER_BASIC_SALARY

# ====================================
# 工人薪资计算区 - 基本工资、津贴、加班、EPF/SOCSO
# ====================================

async def worker_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理工作人员选择"""
    query = update.callback_query
    await query.answer()
    
    # 从回调数据中提取工作人员名称
    worker_data = query.data
    
    if worker_data.startswith("worker_"):
        worker_name = worker_data.replace("worker_", "")
        
        # 处理自定义工作人员输入
        if worker_name == "other":
            keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "👷 <b>Please enter worker name:</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            
            # 设置一个标记，表示我们正在等待自定义工作人员名称输入
            context.user_data['waiting_for_custom_worker'] = True
            return COST_WORKER
        
        # 正常工作人员选择
        context.user_data['cost_worker'] = worker_name
        context.user_data['cost_desc'] = f"Salary for {worker_name}"  # 自动设置描述
        context.user_data['cost_type'] = "Worker Salary"  # 设置费用类型为工资
        
        # 显示基本工资输入界面
        keyboard = [[InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"👷 <b>Worker:</b> {worker_name}\n\n<b>Please enter basic salary amount:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        return WORKER_BASIC_SALARY
    
    # 其他回调处理
    await query.edit_message_text("❌ Unknown selection, please try again",
                                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_cost")]]))
    return COST_WORKER

async def worker_basic_salary_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理工人基本工资输入"""
    try:
        basic_salary_text = update.message.text.strip()
        # 检查金额格式并转换为浮点数
        clean_amount = basic_salary_text.replace(',', '').replace('RM', '').replace('¥', '').replace('$', '').replace('€', '')
        basic_salary = float(clean_amount)
        
        # 存储基本工资
        context.user_data['basic_salary'] = basic_salary
        
        # 询问津贴
        keyboard = [[InlineKeyboardButton("⏭️ Skip (0)", callback_data="skip_allowance")],
                   [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_html(
            f"💰 <b>Basic Salary:</b> RM{basic_salary:,.2f}\n\n"
            f"<b>Please enter allowance amount (if any):</b>",
            reply_markup=reply_markup
        )
        
        return WORKER_ALLOWANCE
        
    except ValueError:
        # 金额格式不正确
        await update.message.reply_text("⚠️ <b>Invalid amount format</b>\n\nPlease enter a valid number.", parse_mode=ParseMode.HTML)
        return WORKER_BASIC_SALARY

async def worker_allowance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理工人津贴输入"""
    try:
        allowance_text = update.message.text.strip()
        # 检查金额格式并转换为浮点数
        clean_amount = allowance_text.replace(',', '').replace('RM', '').replace('¥', '').replace('$', '').replace('€', '')
        allowance = float(clean_amount)
        
        # 存储津贴
        context.user_data['allowance'] = allowance
        
        # 询问加班费
        keyboard = [[InlineKeyboardButton("⏭️ Skip (0)", callback_data="skip_overtime")],
                   [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        basic_salary = context.user_data.get('basic_salary', 0)
        
        await update.message.reply_html(
            f"💰 <b>Basic Salary:</b> RM{basic_salary:,.2f}\n"
            f"💵 <b>Allowance:</b> RM{allowance:,.2f}\n\n"
            f"<b>Please enter overtime amount (if any):</b>",
            reply_markup=reply_markup
        )
        
        return WORKER_OT
        
    except ValueError:
        # 金额格式不正确
        await update.message.reply_text("⚠️ <b>Invalid amount format</b>\n\nPlease enter a valid number.", parse_mode=ParseMode.HTML)
        return WORKER_ALLOWANCE

async def skip_allowance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """跳过津贴输入"""
    query = update.callback_query
    await query.answer()
    
    # 设置津贴为0
    context.user_data['allowance'] = 0
    
    # 询问加班费
    keyboard = [[InlineKeyboardButton("⏭️ Skip (0)", callback_data="skip_overtime")],
               [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    basic_salary = context.user_data.get('basic_salary', 0)
    
    await query.edit_message_text(
        f"💰 <b>Basic Salary:</b> RM{basic_salary:,.2f}\n"
        f"💵 <b>Allowance:</b> RM0.00\n\n"
        f"<b>Please enter overtime amount (if any):</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return WORKER_OT

async def worker_overtime_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理工人加班费输入"""
    try:
        overtime_text = update.message.text.strip()
        # 检查金额格式并转换为浮点数
        clean_amount = overtime_text.replace(',', '').replace('RM', '').replace('¥', '').replace('$', '').replace('€', '')
        overtime = float(clean_amount)
        
        # 存储加班费
        context.user_data['overtime'] = overtime
        
        # 进入扣除项选择界面
        return await show_deductions_options(update, context)
        
    except ValueError:
        # 金额格式不正确
        await update.message.reply_text("⚠️ <b>Invalid amount format</b>\n\nPlease enter a valid number.", parse_mode=ParseMode.HTML)
        return WORKER_OT

async def skip_overtime_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """跳过加班费输入"""
    query = update.callback_query
    await query.answer()
    
    # 设置加班费为0
    context.user_data['overtime'] = 0
    
    # 进入扣除项选择界面
    return await show_deductions_options(update, context, from_callback=True)

async def show_deductions_options(update: Update, context: ContextTypes.DEFAULT_TYPE, from_callback=False) -> int:
    """显示法定扣除项选择界面"""
    # 准备选择按钮
    keyboard = [
        [InlineKeyboardButton("✅ EPF + SOCSO", callback_data="deductions_both")],
        [InlineKeyboardButton("💰 EPF Only", callback_data="deductions_epf")],
        [InlineKeyboardButton("🩺 SOCSO Only", callback_data="deductions_socso")],
        [InlineKeyboardButton("⏭️ No Deductions", callback_data="deductions_none")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 获取已输入的薪资信息
    basic_salary = context.user_data.get('basic_salary', 0)
    allowance = context.user_data.get('allowance', 0)
    overtime = context.user_data.get('overtime', 0)
    
    message = f"""
👷 <b>WORKER SALARY DETAILS</b>

💰 <b>Basic Salary:</b> RM{basic_salary:,.2f}
💵 <b>Allowance:</b> RM{allowance:,.2f}
⏱️ <b>Overtime:</b> RM{overtime:,.2f}

<b>Please select statutory deductions:</b>
- EPF: Employee 11%, Employer 13%
- SOCSO: Employee 0.5%, Employer 1.75%
"""
    
    if from_callback:
        query = update.callback_query
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_html(
            message,
            reply_markup=reply_markup
        )
    
    return WORKER_DEDUCTIONS

async def worker_deductions_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理法定扣除项选择"""
    query = update.callback_query
    await query.answer()
    
    deduction_type = query.data.replace("deductions_", "")
    
    # 根据选择设置EPF和SOCSO启用状态
    if deduction_type == "both":
        context.user_data['epf_enabled'] = True
        context.user_data['socso_enabled'] = True
        
        # 询问雇主EPF缴费比例
        return await show_epf_rate_options(update, context)
        
    elif deduction_type == "epf":
        context.user_data['epf_enabled'] = True
        context.user_data['socso_enabled'] = False
        
        # 询问雇主EPF缴费比例
        return await show_epf_rate_options(update, context)
        
    elif deduction_type == "socso":
        context.user_data['epf_enabled'] = False
        context.user_data['socso_enabled'] = True
        
        # 计算工资并跳到确认界面
        return await calculate_and_show_salary_confirmation(update, context)
        
    elif deduction_type == "none":
        context.user_data['epf_enabled'] = False
        context.user_data['socso_enabled'] = False
        
        # 计算工资并跳到确认界面
        return await calculate_and_show_salary_confirmation(update, context)
    
    # 未知选择，返回扣除项选择界面
    await query.edit_message_text(
        "⚠️ <b>Invalid selection</b>\n\nPlease select a valid option.",
        parse_mode=ParseMode.HTML
    )
    return await show_deductions_options(update, context, from_callback=True)

async def show_epf_rate_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """显示雇主EPF比例选择界面"""
    query = update.callback_query
    
    keyboard = [
        [InlineKeyboardButton("13%", callback_data="epf_rate_13")],
        [InlineKeyboardButton("12%", callback_data="epf_rate_12")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 获取已输入的薪资信息
    basic_salary = context.user_data.get('basic_salary', 0)
    
    message = f"""
👷 <b>EPF EMPLOYER CONTRIBUTION RATE</b>

💰 <b>Basic Salary:</b> RM{basic_salary:,.2f}

<b>Please select the EPF employer contribution rate:</b>
- Standard rate: 13%
- Alternative rate: 12%
"""
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return WORKER_EPF_RATE

async def worker_epf_rate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理雇主EPF比例选择"""
    query = update.callback_query
    await query.answer()
    
    rate_data = query.data.replace("epf_rate_", "")
    
    try:
        employer_epf_rate = int(rate_data)
        context.user_data['employer_epf_rate'] = employer_epf_rate
        
        # 计算工资并跳到确认界面
        return await calculate_and_show_salary_confirmation(update, context)
        
    except ValueError:
        # 比例格式不正确
        await query.edit_message_text(
            "⚠️ <b>Invalid rate</b>\n\nPlease select a valid option.",
            parse_mode=ParseMode.HTML
        )
        return await show_epf_rate_options(update, context)

async def calculate_and_show_salary_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """计算工资并显示确认界面"""
    query = update.callback_query
    
    # 获取薪资信息
    basic_salary = context.user_data.get('basic_salary', 0)
    allowance = context.user_data.get('allowance', 0)
    overtime = context.user_data.get('overtime', 0)
    epf_enabled = context.user_data.get('epf_enabled', False)
    socso_enabled = context.user_data.get('socso_enabled', False)
    
    # 计算EPF和SOCSO
    epf_employee = 0
    epf_employer = 0
    socso_employee = 0
    socso_employer = 0
    
    if epf_enabled:
        # 员工EPF固定为11%
        epf_employee = basic_salary * 0.11
        
        # 雇主EPF可能是12%或13%
        employer_epf_rate = context.user_data.get('employer_epf_rate', 13) / 100
        epf_employer = basic_salary * employer_epf_rate
    
    if socso_enabled:
        # 员工SOCSO为0.5%
        socso_employee = basic_salary * 0.005
        
        # 雇主SOCSO为1.75%
        socso_employer = basic_salary * 0.0175
    
    # 计算净工资
    net_salary = basic_salary + allowance + overtime - epf_employee - socso_employee
    
    # 存储计算结果
    context.user_data['epf_employee'] = epf_employee
    context.user_data['epf_employer'] = epf_employer
    context.user_data['socso_employee'] = socso_employee
    context.user_data['socso_employer'] = socso_employer
    context.user_data['net_salary'] = net_salary
    
    # 总费用（包括雇主需要额外承担的部分）
    total_employer_cost = basic_salary + allowance + overtime + epf_employer + socso_employer
    context.user_data['total_employer_cost'] = total_employer_cost
    
    # 设置费用金额为净工资
    context.user_data['cost_amount'] = net_salary
    
    # 显示确认界面
    keyboard = [
        [InlineKeyboardButton("✅ Save", callback_data="cost_save")],
        [InlineKeyboardButton("❌ Cancel", callback_data="back_cost")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    worker_name = context.user_data.get('cost_worker', '')
    
    message = f"""
👷 <b>WORKER SALARY CONFIRMATION</b>

<b>Worker:</b> {worker_name}

<b>Income:</b>
💰 Basic Salary: RM{basic_salary:,.2f}
💵 Allowance: RM{allowance:,.2f}
⏱️ Overtime: RM{overtime:,.2f}

<b>Statutory Deductions:</b>
"""
    
    if epf_enabled:
        employer_epf_rate = context.user_data.get('employer_epf_rate', 13)
        message += f"💼 EPF (Employee 11%): RM{epf_employee:,.2f}\n"
        message += f"🏢 EPF (Employer {employer_epf_rate}%): RM{epf_employer:,.2f}\n"
    
    if socso_enabled:
        message += f"🩺 SOCSO (Employee 0.5%): RM{socso_employee:,.2f}\n"
        message += f"🏢 SOCSO (Employer 1.75%): RM{socso_employer:,.2f}\n"
    
    message += f"""
<b>Summary:</b>
🧾 Net Salary: RM{net_salary:,.2f}
💶 Total Employer Cost: RM{total_employer_cost:,.2f}

<b>Please confirm the salary details:</b>
"""
    
    await query.edit_message_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    return WORKER_CONFIRM

def register_handlers(application):
    """注册所有处理器"""
    # 基础命令
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("settings", setting_command))
    
    # 销售相关处理器
    application.add_handler(sales_conversation)
    
    # 费用相关处理器
    application.add_handler(expenses_conversation)
    
    # 报表相关处理器
    application.add_handler(report_conversation)
    
    # 设置相关处理器
    application.add_handler(setting_conversation)
    
    # 导航菜单处理器
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^back_main$"))
    application.add_handler(CallbackQueryHandler(sales_menu, pattern="^menu_sales$"))
    application.add_handler(CallbackQueryHandler(cost_menu, pattern="^menu_cost$"))
    application.add_handler(CallbackQueryHandler(report_menu, pattern="^menu_report$"))
    application.add_handler(CallbackQueryHandler(setting_menu, pattern="^menu_settings$"))
    
    # 基础报表处理器
    application.add_handler(CallbackQueryHandler(report_current_handler, pattern="^report_current$"))
    application.add_handler(CallbackQueryHandler(report_custom_handler, pattern="^report_custom$"))
    application.add_handler(CallbackQueryHandler(report_month_select_handler, pattern="^month_"))
    application.add_handler(CallbackQueryHandler(report_yearly_handler, pattern="^report_yearly$"))
    
    # LHDN报表处理器
    application.add_handler(CallbackQueryHandler(report_pnl_handler, pattern="^report_pnl$"))
    application.add_handler(CallbackQueryHandler(report_salary_handler, pattern="^report_salary$"))
    application.add_handler(CallbackQueryHandler(report_tax_summary_handler, pattern="^report_tax_summary$"))
    application.add_handler(CallbackQueryHandler(report_export_handler, pattern="^report_export$"))
    application.add_handler(CallbackQueryHandler(salary_current_month_handler, pattern="^salary_current_month$"))
    application.add_handler(CallbackQueryHandler(salary_yearly_handler, pattern="^salary_yearly$"))
    
    # 未知命令处理器
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    
    # 错误处理器
    application.add_error_handler(error_handler)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理未知命令"""
    await update.message.reply_text(
        "❓ 未知命令。请使用 /start 开始，或 /help 查看帮助。"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理错误"""
    logger.error(f"更新 {update} 导致错误 {context.error}")
    
    # 发送错误消息给用户
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "⚠️ 发生了一个错误，请稍后再试。"
        )
    
    # 发送错误详情给开发者
    if os.getenv('DEVELOPER_CHAT_ID'):
        developer_chat_id = os.getenv('DEVELOPER_CHAT_ID')
        
        # 构建错误信息
        tb_string = "".join(traceback.format_exception(None, context.error, context.error.__traceback__))
        error_message = f"❌ <b>ERROR REPORT</b>\n\n<b>Update:</b> {update}\n\n<b>Error:</b> {context.error}\n\n<b>Traceback:</b>\n<code>{tb_string[:2000]}</code>"
        
        try:
            await context.bot.send_message(
                chat_id=developer_chat_id,
                text=error_message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"向开发者发送错误报告失败: {e}")

# 添加关闭其他会话的辅助函数
async def close_other_conversations(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """关闭其他所有正在进行的会话"""
    context.user_data.clear()
    
    # 这里只是清除用户数据，实际上不会强制结束其他会话
    # 但通过清除数据，其他会话将无法正常继续

# 创建对话处理器

# 销售记录会话处理器
sales_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("sales", sales_menu),
        CallbackQueryHandler(sales_add_start, pattern="^sales_add$"),
        CallbackQueryHandler(sales_list_handler, pattern="^sales_list$")
    ],
    states={
        SALES_PERSON: [
            CallbackQueryHandler(sales_person_handler, pattern="^pic_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, sales_person_handler)
        ],
        SALES_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, sales_amount_handler)
        ],
        SALES_BILL_TO: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, sales_bill_to_handler)
        ],
        SALES_CLIENT: [
            CallbackQueryHandler(sales_client_handler, pattern="^client_")
        ],
        SALES_AGENT_SELECT: [
            CallbackQueryHandler(sales_commission_type_handler, pattern="^commission_"),
            CallbackQueryHandler(pattern="^agent_", callback=lambda u, c: asyncio.ensure_future(show_sales_confirmation(u, c)))
        ],
        SALES_COMMISSION_TYPE: [
            CallbackQueryHandler(sales_commission_type_handler, pattern="^commission_")
        ],
        SALES_COMMISSION_PERCENT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, sales_commission_percent_handler)
        ],
        SALES_COMMISSION_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, sales_commission_amount_handler)
        ],
        SALES_CONFIRM: [
            CallbackQueryHandler(sales_save_handler, pattern="^sales_save$")
        ],
        SALES_INVOICE_PDF: [
            MessageHandler(filters.PHOTO | filters.Document.PDF, lambda u, c: asyncio.ensure_future(show_sales_confirmation(u, c)))
        ]
    },
    fallbacks=[
        CallbackQueryHandler(main_menu, pattern="^back_main$"),
        CallbackQueryHandler(sales_menu, pattern="^back_sales$"),
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
        COST_WORKER: [
            CallbackQueryHandler(worker_select_handler, pattern="^worker_"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, custom_worker_handler)
        ],
        COST_AMOUNT: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, cost_amount_handler)
        ],
        COST_DESC: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, cost_desc_handler)
        ],
        COST_RECEIPT: [
            CallbackQueryHandler(pattern="^upload_receipt$", callback=lambda u, c: u.callback_query.edit_message_text("📷 Please upload the receipt...")),
            CallbackQueryHandler(pattern="^skip_receipt$", callback=lambda u, c: asyncio.ensure_future(show_cost_confirmation(u, c))),
            MessageHandler(filters.PHOTO | filters.Document.ALL, cost_receipt_handler)
        ],
        COST_CONFIRM: [
            CallbackQueryHandler(cost_save_handler, pattern="^cost_save$")
        ],
        WORKER_BASIC_SALARY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, worker_basic_salary_handler)
        ],
        WORKER_ALLOWANCE: [
            CallbackQueryHandler(skip_allowance_handler, pattern="^skip_allowance$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, worker_allowance_handler)
        ],
        WORKER_OT: [
            CallbackQueryHandler(skip_overtime_handler, pattern="^skip_overtime$"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, worker_overtime_handler)
        ],
        WORKER_DEDUCTIONS: [
            CallbackQueryHandler(worker_deductions_handler, pattern="^deductions_")
        ],
        WORKER_EPF_RATE: [
            CallbackQueryHandler(worker_epf_rate_handler, pattern="^epf_rate_")
        ],
        WORKER_CONFIRM: [
            CallbackQueryHandler(cost_save_handler, pattern="^cost_save$")
        ]
    },
    fallbacks=[
        CallbackQueryHandler(main_menu, pattern="^back_main$"),
        CallbackQueryHandler(cost_menu, pattern="^back_cost$"),
        CommandHandler("cancel", cancel_command)
    ],
    name="expenses_conversation",
    persistent=False
)

# 报表生成会话处理器
report_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("report", report_menu),
        CallbackQueryHandler(report_menu, pattern="^menu_report$")
    ],
    states={
        REPORT_TYPE: [
            CallbackQueryHandler(report_current_handler, pattern="^report_current$"),
            CallbackQueryHandler(report_custom_handler, pattern="^report_custom$"),
            CallbackQueryHandler(report_yearly_handler, pattern="^report_yearly$"),
            CallbackQueryHandler(report_pnl_handler, pattern="^report_pnl$"),
            CallbackQueryHandler(report_salary_handler, pattern="^report_salary$"),
            CallbackQueryHandler(report_tax_summary_handler, pattern="^report_tax_summary$"),
            CallbackQueryHandler(report_export_handler, pattern="^report_export$")
        ],
        REPORT_MONTH: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, report_month_handler)
        ]
    },
    fallbacks=[
        CallbackQueryHandler(main_menu, pattern="^back_main$"),
        CallbackQueryHandler(report_menu, pattern="^back_report$"),
        CommandHandler("cancel", cancel_command)
    ],
    name="report_conversation",
    persistent=False
)

# 设置管理会话处理器
setting_conversation = ConversationHandler(
    entry_points=[
        CommandHandler("settings", setting_command),
        CallbackQueryHandler(setting_menu, pattern="^menu_setting$"),
        CallbackQueryHandler(setting_menu, pattern="^setting_")
    ],
    states={
        SETTING_CATEGORY: [
            CallbackQueryHandler(setting_category_handler, pattern="^category_")
        ],
        SETTING_NAME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, setting_name_handler)
        ],
        SETTING_IC: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, setting_ic_handler)
        ],
        SETTING_TYPE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, setting_type_handler)
        ],
        SETTING_RATE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, setting_rate_handler)
        ]
    },
    fallbacks=[
        CallbackQueryHandler(main_menu, pattern="^back_main$"),
        CommandHandler("cancel", cancel_command)
    ],
    name="setting_conversation",
    persistent=False
)





async def report_month_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理月份选择"""
    query = update.callback_query
    await query.answer()
    
    # 解析选择的月份，格式为"month_YYYY-MM"
    month_data = query.data.replace("month_", "")
    
    try:
        # 验证日期格式
        selected_month = datetime.strptime(month_data, '%Y-%m').strftime('%Y-%m')
        
        sheets_manager = SheetsManager()
        report_data = await sheets_manager.generate_monthly_report(selected_month)
        
        keyboard = [[InlineKeyboardButton("🔙 返回报表菜单", callback_data="menu_report")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        report_message = f"""
📊 *{selected_month} 月度报表*

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
        
    except ValueError:
        await query.edit_message_text("⚠️ 无效的月份格式",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_report")]]))
    except Exception as e:
        logger.error(f"生成月份报表失败: {e}")
        await query.edit_message_text("❌ 生成报表失败，请重试",
                                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回", callback_data="menu_report")]]))
    
    return ConversationHandler.END

async def sale_invoice_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """销售发票命令处理"""
    await close_other_conversations(update, context)
    
    # 清除用户数据
    context.user_data.clear()
    
    # 获取负责人列表
    try:
        sheets_manager = SheetsManager()
        pics = sheets_manager.get_pics(active_only=True)
        
        if not pics:
            # 如果没有负责人数据，显示提示信息
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    "⚠️ <b>No PIC found</b>\n\nPlease create a PIC first using /settings.",
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_html(
                    "⚠️ <b>No PIC found</b>\n\nPlease create a PIC first using /settings."
                )
            return ConversationHandler.END
        
        # 创建负责人选择按钮
        keyboard = []
        for pic in pics:
            # 使用姓名作为按钮文本
            name = pic.get('name', pic.get('Name', ''))
            if name:
                keyboard.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"pic_{name}")])
        
        # 添加取消按钮
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data="back_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 根据不同调用方式显示消息
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "👤 <b>Select Person in Charge:</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_html(
                "👤 <b>Select Person in Charge:</b>",
                reply_markup=reply_markup
            )
        
        return SALES_PERSON
        
    except Exception as e:
        logger.error(f"获取负责人列表失败: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ <b>Failed to get PIC data</b>\n\nPlease try again later.",
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_html(
                "❌ <b>Failed to get PIC data</b>\n\nPlease try again later."
            )
        return ConversationHandler.END
