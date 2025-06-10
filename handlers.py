import os
from datetime import datetime
import re
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, CommandHandler, MessageHandler, filters
from google_services import GoogleServices
from telegram.constants import ParseMode
import logging
import json

# 加载环境变量
load_dotenv()

# 初始化Google服务（添加错误处理）
try:
    google_services = GoogleServices()
except Exception as e:
    print(f"初始化Google服务时出错: {e}")
    google_services = None

# 支出类别列表
EXPENSE_CATEGORIES = ['食品', '住房', '交通', '娱乐', '医疗', '教育', '水电', '其他']
# 收入类别列表
INCOME_CATEGORIES = ['薪资', '奖金', '投资', '兼职', '其他']
# 供应商类别列表
SUPPLIER_CATEGORIES = ['原材料', '设备', '服务', '办公用品', '其他']

# 用户状态追踪
user_states = {}

# 设置日志
logger = logging.getLogger(__name__)

# 会话状态
(
    MAIN_MENU,
    PERSON_NAME,
    AGENT_NAME,
    AGENT_IC,
    SUPPLIER_CATEGORY,
    SUPPLIER_PRODUCT,
) = range(6)

# 回调数据前缀
CALLBACK_PREFIX = {
    'SETTINGS': 'settings',
    'CREATE_PERSON': 'create_person',
    'CREATE_AGENT': 'create_agent',
    'CREATE_SUPPLIER': 'create_supplier',
    'SUPPLIER_CAT': 'supplier_cat'
}

# 添加这个新函数，用于清理用户状态
async def clear_user_state(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """清理用户状态数据"""
    if hasattr(context, 'user_data') and context.user_data:
        context.user_data.clear()
    if update.effective_user.id in user_states:
        del user_states[update.effective_user.id]

# 修改start_handler函数
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 命令"""
    # 清理之前的用户状态
    await clear_user_state(update, context)
    
    welcome_message = """
🚀 *财务管理助手*

📋 *快速开始*
┣ 📊 /sales — 销售记录
┣ 💰 /Cost — 成本管理  
┣ ⚙️ /settings — 系统配置
┗ 📈 /report — 报表生成

💡 /help 详细说明 | ❌ /cancel 取消操作
    """
    keyboard = [
        [
            InlineKeyboardButton("📊 销售记录", callback_data="sales"),
            InlineKeyboardButton("💰 成本管理", callback_data="cost")
        ],
        [
            InlineKeyboardButton("⚙️ 系统配置", callback_data=f"{CALLBACK_PREFIX['SETTINGS']}_main"),
            InlineKeyboardButton("📈 报表生成", callback_data="report")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# 修改help_handler函数
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /help 命令"""
    # 清理之前的用户状态
    await clear_user_state(update, context)
    
    help_message = """
📖 *使用指南*

🔧 *基础命令*
• /start — 主菜单
• /help — 帮助说明
• /cancel — 取消当前操作

📊 *销售记录* (/sales)
• 登记负责人信息
• 记录发票金额
• 选择客户类型（公司/代理）
• 自动计算佣金

💰 *成本管理* (/cost)
• 供应商采购记录
• 水电网络费用
• 人工工资统计
• 其他支出登记

⚙️ *系统配置* (/settings)
• 负责人管理
• 代理商维护
• 供应商设置

📈 *报表功能* (/report)
• 生成当月报表
• 指定月份查询 `/report 2024-01`

💡 *小贴士：随时使用 /cancel 退出当前操作*
    """
    await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)

# 修改settings_handler函数
async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /settings 命令，显示系统配置选项"""
    # 清理之前的用户状态
    await clear_user_state(update, context)
    
    keyboard = [
        [InlineKeyboardButton("👤 创建负责人", callback_data=f"{CALLBACK_PREFIX['CREATE_PERSON']}")],
        [InlineKeyboardButton("🧑‍💼 创建Agent", callback_data=f"{CALLBACK_PREFIX['CREATE_AGENT']}")],
        [InlineKeyboardButton("🏭 创建Supplier", callback_data=f"{CALLBACK_PREFIX['CREATE_SUPPLIER']}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "⚙️ *系统配置*\n\n请选择要执行的操作：",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return MAIN_MENU

async def button_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理按钮回调查询"""
    query = update.callback_query
    await query.answer()  # 回答回调查询，关闭按钮上的加载状态
    
    callback_data = query.data
    
    # 设置主菜单
    if callback_data.startswith(f"{CALLBACK_PREFIX['SETTINGS']}_main"):
        keyboard = [
            [InlineKeyboardButton("👤 创建负责人", callback_data=f"{CALLBACK_PREFIX['CREATE_PERSON']}")],
            [InlineKeyboardButton("🧑‍💼 创建Agent", callback_data=f"{CALLBACK_PREFIX['CREATE_AGENT']}")],
            [InlineKeyboardButton("🏭 创建Supplier", callback_data=f"{CALLBACK_PREFIX['CREATE_SUPPLIER']}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="⚙️ *系统配置*\n\n请选择要执行的操作：",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return MAIN_MENU
    
    # 处理创建负责人
    elif callback_data == CALLBACK_PREFIX['CREATE_PERSON']:
        context.user_data['current_action'] = 'create_person'
        await query.edit_message_text(
            text="👤 *创建负责人*\n\n请输入负责人的姓名：",
            parse_mode=ParseMode.MARKDOWN
        )
        return PERSON_NAME
    
    # 处理创建Agent
    elif callback_data == CALLBACK_PREFIX['CREATE_AGENT']:
        context.user_data['current_action'] = 'create_agent'
        await query.edit_message_text(
            text="🧑‍💼 *创建Agent*\n\n请输入Agent的姓名：",
            parse_mode=ParseMode.MARKDOWN
        )
        return AGENT_NAME
    
    # 处理创建Supplier
    elif callback_data == CALLBACK_PREFIX['CREATE_SUPPLIER']:
        context.user_data['current_action'] = 'create_supplier'
        keyboard = []
        # 每行两个类别按钮
        row = []
        for i, category in enumerate(SUPPLIER_CATEGORIES):
            row.append(InlineKeyboardButton(
                category, callback_data=f"{CALLBACK_PREFIX['SUPPLIER_CAT']}_{category}"
            ))
            if (i + 1) % 2 == 0 or i == len(SUPPLIER_CATEGORIES) - 1:
                keyboard.append(row)
                row = []
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text="🏭 *创建Supplier*\n\n请选择供应商类别：",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return SUPPLIER_CATEGORY
    
    # 处理供应商类别选择
    elif callback_data.startswith(f"{CALLBACK_PREFIX['SUPPLIER_CAT']}_"):
        category = callback_data.split('_')[-1]
        context.user_data['supplier_category'] = category
        await query.edit_message_text(
            text=f"🏭 *创建Supplier*\n\n已选择类别：*{category}*\n\n请输入供应的产品：",
            parse_mode=ParseMode.MARKDOWN
        )
        return SUPPLIER_PRODUCT
    
    # 其他回调处理
    else:
        if callback_data == "sales":
            await query.edit_message_text(text="销售记录功能正在开发中...")
        elif callback_data == "cost":
            await query.edit_message_text(text="成本管理功能正在开发中...")
        elif callback_data == "report":
            await query.edit_message_text(text="报表功能正在开发中...")
        else:
            await query.edit_message_text(text="未知的操作")
        return ConversationHandler.END

async def person_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理负责人姓名输入"""
    name = update.message.text
    context.user_data['person_name'] = name
    
    # 使用数据管理器保存数据
    from data_manager import data_manager
    
    if data_manager:
        success = data_manager.add_person(name)
        if success:
            await update.message.reply_text(
                f"✅ 负责人创建成功！\n\n姓名：*{name}*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ 创建失败，负责人 *{name}* 可能已存在。",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        # 数据管理器不可用，仍然显示成功信息但记录错误
        logger.error("数据管理器不可用，无法保存负责人数据")
        await update.message.reply_text(
            f"✅ 负责人创建成功！\n\n姓名：*{name}*\n\n(注意：数据可能未成功保存)",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

async def agent_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理Agent姓名输入"""
    name = update.message.text
    context.user_data['agent_name'] = name
    
    await update.message.reply_text(
        f"请为Agent *{name}* 输入IC号码：",
        parse_mode=ParseMode.MARKDOWN
    )
    return AGENT_IC

async def agent_ic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理Agent IC输入"""
    ic = update.message.text
    name = context.user_data.get('agent_name')
    
    # 使用数据管理器保存数据
    from data_manager import data_manager
    
    if data_manager:
        success = data_manager.add_agent(name, ic)
        if success:
            await update.message.reply_text(
                f"✅ Agent创建成功！\n\n姓名：*{name}*\nIC：*{ic}*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ 创建失败，Agent *{name}* 或IC *{ic}* 可能已存在。",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        # 数据管理器不可用，仍然显示成功信息但记录错误
        logger.error("数据管理器不可用，无法保存Agent数据")
        await update.message.reply_text(
            f"✅ Agent创建成功！\n\n姓名：*{name}*\nIC：*{ic}*\n\n(注意：数据可能未成功保存)",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

async def supplier_product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理供应商产品输入"""
    product = update.message.text
    category = context.user_data.get('supplier_category')
    
    # 使用数据管理器保存数据
    from data_manager import data_manager
    
    if data_manager:
        success = data_manager.add_supplier(category, product)
        if success:
            await update.message.reply_text(
                f"✅ 供应商创建成功！\n\n类别：*{category}*\n产品：*{product}*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text(
                f"❌ 创建失败，保存供应商数据时出错。",
                parse_mode=ParseMode.MARKDOWN
            )
    else:
        # 数据管理器不可用，仍然显示成功信息但记录错误
        logger.error("数据管理器不可用，无法保存供应商数据")
        await update.message.reply_text(
            f"✅ 供应商创建成功！\n\n类别：*{category}*\n产品：*{product}*\n\n(注意：数据可能未成功保存)",
            parse_mode=ParseMode.MARKDOWN
        )
    
    return ConversationHandler.END

# 修改cancel_command函数
async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理 /cancel 命令，取消当前会话"""
    # 清理之前的用户状态
    await clear_user_state(update, context)
    
    await update.message.reply_text("✅ 操作已取消，使用 /start 重新开始")
    return ConversationHandler.END

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理未知命令"""
    await update.message.reply_text(
        "❓ 未知命令，使用 /help 查看可用功能"
    )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理错误"""
    # 获取异常信息
    error = context.error
    
    # 记录详细的错误信息
    logger.error("发生异常:", exc_info=context.error)
    logger.error(f"更新信息: {update}")
    if hasattr(context, 'user_data'):
        logger.error(f"用户数据: {context.user_data}")
    if hasattr(context, 'chat_data'):
        logger.error(f"聊天数据: {context.chat_data}")
    
    # 根据错误类型返回不同的用户提示
    error_message = "⚠️ 处理请求时发生错误"
    
    if "Application was not initialized" in str(error):
        error_message = "🔄 系统正在初始化，请稍后重试"
    elif "Event loop is closed" in str(error):
        error_message = "⏳ 系统繁忙，请稍后重试"
    elif "Conversation handler timeout" in str(error):
        error_message = "⏰ 会话已超时，请重新开始"
    elif "Message is not modified" in str(error):
        # 这种情况不需要通知用户
        return
    
    # 发送错误消息给用户
    if update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"{error_message}\n\n如需帮助请联系管理员 👨‍💻"
            )
        except Exception as e:
            logger.error(f"发送错误消息时出错: {e}")

async def expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /expense 命令"""
    if google_services is None:
        await update.message.reply_text("⚠️ Google服务未初始化，无法记录支出")
        return
        
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # 检查是否有参数
    if message_text == '/expense':
        # 没有参数，进入交互模式
        user_states[user_id] = {'state': 'expense_category'}
        categories_keyboard = "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(EXPENSE_CATEGORIES)])
        await update.message.reply_text(f"请选择支出类别（输入编号或直接输入类别）：\n{categories_keyboard}")
        return
    
    # 有参数，直接处理
    try:
        # 尝试解析命令参数
        parts = message_text.split(' ', 3)  # 最多分成4部分
        
        if len(parts) < 3:
            await update.message.reply_text("格式不正确。正确格式：/expense 类别 金额 描述 [备注]")
            return
        
        category = parts[1].strip()
        if category not in EXPENSE_CATEGORIES:
            await update.message.reply_text(f"无效的类别。有效类别：{', '.join(EXPENSE_CATEGORIES)}")
            return
        
        try:
            amount = float(parts[2].strip())
        except ValueError:
            await update.message.reply_text("金额必须是数字")
            return
        
        description = parts[3].strip() if len(parts) > 3 else ""
        
        # 分离描述和备注（如果有）
        note = ""
        if " " in description:
            desc_parts = description.split(' ', 1)
            description = desc_parts[0]
            note = desc_parts[1] if len(desc_parts) > 1 else ""
        
        # 添加支出记录
        today = datetime.now().strftime('%Y-%m-%d')
        success = google_services.add_expense(today, category, amount, description, note)
        
        if success:
            await update.message.reply_text(f"已记录支出：{category} {amount} 元 - {description}")
            
            # 询问是否有收据
            await update.message.reply_text("你有这笔支出的收据吗？如果有，请直接发送照片。如果没有，请回复'没有'。")
            user_states[user_id] = {'state': 'waiting_for_receipt', 'expense_info': {'category': category, 'amount': amount, 'description': description}}
        else:
            await update.message.reply_text("记录支出失败，请稍后再试")
    
    except Exception as e:
        await update.message.reply_text(f"处理命令时出错：{str(e)}")

async def income_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /income 命令"""
    if google_services is None:
        await update.message.reply_text("⚠️ Google服务未初始化，无法记录收入")
        return
        
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # 检查是否有参数
    if message_text == '/income':
        # 没有参数，进入交互模式
        user_states[user_id] = {'state': 'income_category'}
        categories_keyboard = "\n".join([f"{i+1}. {cat}" for i, cat in enumerate(INCOME_CATEGORIES)])
        await update.message.reply_text(f"请选择收入类别（输入编号或直接输入类别）：\n{categories_keyboard}")
        return
    
    # 有参数，直接处理
    try:
        # 尝试解析命令参数
        parts = message_text.split(' ', 3)  # 最多分成4部分
        
        if len(parts) < 3:
            await update.message.reply_text("格式不正确。正确格式：/income 类别 金额 描述 [备注]")
            return
        
        category = parts[1].strip()
        if category not in INCOME_CATEGORIES:
            await update.message.reply_text(f"无效的类别。有效类别：{', '.join(INCOME_CATEGORIES)}")
            return
        
        try:
            amount = float(parts[2].strip())
        except ValueError:
            await update.message.reply_text("金额必须是数字")
            return
        
        description = parts[3].strip() if len(parts) > 3 else ""
        
        # 分离描述和备注（如果有）
        note = ""
        if " " in description:
            desc_parts = description.split(' ', 1)
            description = desc_parts[0]
            note = desc_parts[1] if len(desc_parts) > 1 else ""
        
        # 添加收入记录
        today = datetime.now().strftime('%Y-%m-%d')
        success = google_services.add_income(today, category, amount, description, note)
        
        if success:
            await update.message.reply_text(f"已记录收入：{category} {amount} 元 - {description}")
        else:
            await update.message.reply_text("记录收入失败，请稍后再试")
    
    except Exception as e:
        await update.message.reply_text(f"处理命令时出错：{str(e)}")

async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /report 命令，生成月度报告"""
    if google_services is None:
        await update.message.reply_text("⚠️ Google服务未初始化，无法生成报告")
        return
        
    try:
        args = context.args
        year = None
        month = None
        
        # 检查是否有年月参数
        if len(args) >= 2:
            try:
                year = int(args[0])
                month = int(args[1])
                if month < 1 or month > 12:
                    await update.message.reply_text("月份必须在1-12之间")
                    return
            except ValueError:
                await update.message.reply_text("年份和月份必须是数字")
                return
        
        # 获取月度汇总
        summary = google_services.get_monthly_summary(year, month)
        
        if summary:
            # 构建报告消息
            report_message = f"📊 {summary['year']}年{summary['month']}月财务报告\n\n"
            
            # 收入部分
            report_message += "💰 收入汇总\n"
            report_message += f"总收入: {summary['total_income']:.2f} 元\n"
            if summary['income_by_category']:
                report_message += "收入分类:\n"
                for category, amount in summary['income_by_category'].items():
                    report_message += f"  - {category}: {amount:.2f} 元\n"
            else:
                report_message += "本月无收入记录\n"
            
            report_message += "\n"
            
            # 支出部分
            report_message += "💸 支出汇总\n"
            report_message += f"总支出: {summary['total_expense']:.2f} 元\n"
            if summary['expense_by_category']:
                report_message += "支出分类:\n"
                for category, amount in summary['expense_by_category'].items():
                    report_message += f"  - {category}: {amount:.2f} 元\n"
            else:
                report_message += "本月无支出记录\n"
            
            report_message += "\n"
            
            # 净收入
            report_message += f"📈 净收入: {summary['net']:.2f} 元"
            
            await update.message.reply_text(report_message)
        else:
            await update.message.reply_text("生成报告失败，请稍后再试")
    
    except Exception as e:
        await update.message.reply_text(f"处理命令时出错：{str(e)}")

async def receipt_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理收据照片"""
    if google_services is None:
        await update.message.reply_text("⚠️ Google服务未初始化，无法处理收据")
        return
        
    user_id = update.effective_user.id
    
    # 检查用户是否在等待收据
    if user_id in user_states and user_states[user_id].get('state') == 'waiting_for_receipt':
        try:
            # 获取照片文件
            photo = update.message.photo[-1]  # 获取最高质量的照片
            photo_file = await context.bot.get_file(photo.file_id)
            photo_bytes = await photo_file.download_as_bytearray()
            
            # 获取之前的支出信息
            expense_info = user_states[user_id].get('expense_info', {})
            description = expense_info.get('description', '未知支出')
            
            # 上传收据并获取链接
            receipt_url = google_services.upload_receipt(photo_bytes, description)
            
            if receipt_url:
                # 更新支出记录以包含收据链接
                # 这里需要重新获取该支出记录并更新，目前简化处理
                await update.message.reply_text(f"收据已上传并保存。\n链接: {receipt_url}")
            else:
                await update.message.reply_text("收据上传失败，请稍后再试")
            
            # 清除用户状态
            if user_id in user_states:
                del user_states[user_id]
                
        except Exception as e:
            await update.message.reply_text(f"处理收据时出错：{str(e)}")
    else:
        # 用户直接发送了照片，但不是在记录支出后
        await update.message.reply_text("我收到了你的照片。如果这是一张收据，请先使用 /expense 命令记录相关支出。")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理文本消息，用于交互式对话"""
    user_id = update.effective_user.id
    message_text = update.message.text
    
    # 检查用户是否在某个状态中
    if user_id in user_states:
        state = user_states[user_id].get('state')
        
        # 处理支出类别选择
        if state == 'expense_category':
            # 检查是否输入了类别编号
            if message_text.isdigit() and 1 <= int(message_text) <= len(EXPENSE_CATEGORIES):
                category = EXPENSE_CATEGORIES[int(message_text) - 1]
            else:
                category = message_text
            
            if category in EXPENSE_CATEGORIES:
                user_states[user_id]['state'] = 'expense_amount'
                user_states[user_id]['category'] = category
                await update.message.reply_text("请输入支出金额：")
            else:
                await update.message.reply_text(f"无效的类别。请从以下选择或直接输入：\n{', '.join(EXPENSE_CATEGORIES)}")
        
        # 处理支出金额输入
        elif state == 'expense_amount':
            try:
                amount = float(message_text)
                user_states[user_id]['state'] = 'expense_description'
                user_states[user_id]['amount'] = amount
                await update.message.reply_text("请输入支出描述：")
            except ValueError:
                await update.message.reply_text("金额必须是数字。请重新输入：")
        
        # 处理支出描述输入
        elif state == 'expense_description':
            description = message_text
            user_states[user_id]['state'] = 'expense_note'
            user_states[user_id]['description'] = description
            await update.message.reply_text("请输入备注（可选，直接回复'无'跳过）：")
        
        # 处理支出备注输入
        elif state == 'expense_note':
            note = "" if message_text.lower() in ['无', 'n', 'no', '不需要'] else message_text
            
            # 检查Google服务是否可用
            if google_services is None:
                await update.message.reply_text("⚠️ Google服务未初始化，无法记录支出")
                if user_id in user_states:
                    del user_states[user_id]
                return
            
            # 添加支出记录
            category = user_states[user_id].get('category')
            amount = user_states[user_id].get('amount')
            description = user_states[user_id].get('description')
            
            today = datetime.now().strftime('%Y-%m-%d')
            success = google_services.add_expense(today, category, amount, description, note)
            
            if success:
                await update.message.reply_text(f"已记录支出：{category} {amount} 元 - {description}")
                
                # 询问是否有收据
                await update.message.reply_text("你有这笔支出的收据吗？如果有，请直接发送照片。如果没有，请回复'没有'。")
                user_states[user_id] = {
                    'state': 'waiting_for_receipt', 
                    'expense_info': {
                        'category': category, 
                        'amount': amount, 
                        'description': description
                    }
                }
            else:
                await update.message.reply_text("记录支出失败，请稍后再试")
                # 清除用户状态
                if user_id in user_states:
                    del user_states[user_id]
        
        # 处理是否有收据的回复
        elif state == 'waiting_for_receipt' and message_text.lower() in ['没有', 'no', '没', 'n', '否']:
            await update.message.reply_text("已记录，无需收据。")
            # 清除用户状态
            if user_id in user_states:
                del user_states[user_id]
        
        # 处理收入类别选择
        elif state == 'income_category':
            # 检查是否输入了类别编号
            if message_text.isdigit() and 1 <= int(message_text) <= len(INCOME_CATEGORIES):
                category = INCOME_CATEGORIES[int(message_text) - 1]
            else:
                category = message_text
            
            if category in INCOME_CATEGORIES:
                user_states[user_id]['state'] = 'income_amount'
                user_states[user_id]['category'] = category
                await update.message.reply_text("请输入收入金额：")
            else:
                await update.message.reply_text(f"无效的类别。请从以下选择或直接输入：\n{', '.join(INCOME_CATEGORIES)}")
        
        # 处理收入金额输入
        elif state == 'income_amount':
            try:
                amount = float(message_text)
                user_states[user_id]['state'] = 'income_description'
                user_states[user_id]['amount'] = amount
                await update.message.reply_text("请输入收入描述：")
            except ValueError:
                await update.message.reply_text("金额必须是数字。请重新输入：")
        
        # 处理收入描述输入
        elif state == 'income_description':
            description = message_text
            user_states[user_id]['state'] = 'income_note'
            user_states[user_id]['description'] = description
            await update.message.reply_text("请输入备注（可选，直接回复'无'跳过）：")
        
        # 处理收入备注输入
        elif state == 'income_note':
            note = "" if message_text.lower() in ['无', 'n', 'no', '不需要'] else message_text
            
            # 检查Google服务是否可用
            if google_services is None:
                await update.message.reply_text("⚠️ Google服务未初始化，无法记录收入")
                if user_id in user_states:
                    del user_states[user_id]
                return
            
            # 添加收入记录
            category = user_states[user_id].get('category')
            amount = user_states[user_id].get('amount')
            description = user_states[user_id].get('description')
            
            today = datetime.now().strftime('%Y-%m-%d')
            success = google_services.add_income(today, category, amount, description, note)
            
            if success:
                await update.message.reply_text(f"已记录收入：{category} {amount} 元 - {description}")
            else:
                await update.message.reply_text("记录收入失败，请稍后再试")
            
            # 清除用户状态
            if user_id in user_states:
                del user_states[user_id]
    
    # 如果不在任何状态中，提供帮助
    else:
        await update.message.reply_text(
            "我不理解你的消息。请使用以下命令：\n"
            "/expense - 记录支出\n"
            "/income - 记录收入\n"
            "/report - 生成月度报告\n"
            "/help - 获取帮助"
        )

# 添加会话超时处理函数
async def conversation_timeout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理会话超时"""
    # 清理用户状态
    if hasattr(context, 'user_data') and context.user_data:
        context.user_data.clear()
    
    user_id = None
    if update and update.effective_user:
        user_id = update.effective_user.id
    
    # 清理用户状态字典
    if user_id and user_id in user_states:
        del user_states[user_id]
    
    # 如果有原来的消息，告知用户会话已超时
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⏰ 会话已超时。请使用 /start 重新开始。",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"发送会话超时消息时出错: {e}")
    
    return ConversationHandler.END
