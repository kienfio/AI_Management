from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler, CommandHandler, MessageHandler, filters
import logging
from datetime import datetime
from google_sheets import GoogleSheetsManager as SheetsManager

# 设置日志
logger = logging.getLogger(__name__)

# ====================================
# 会话状态区 - ConversationHandler 状态定义
# ====================================

# 销售记录状态
SALES_PERSON, SALES_AMOUNT, SALES_CLIENT, SALES_CONFIRM = range(4)

# 费用管理状态
COST_TYPE, COST_SUPPLIER, COST_AMOUNT, COST_DESC, COST_CONFIRM = range(5, 10)

# 报表生成状态
REPORT_TYPE, REPORT_MONTH = range(10, 12)

# 系统设置状态
SETTINGS_TYPE, SETTINGS_ADD, SETTINGS_EDIT, SETTINGS_DELETE = range(12, 16)

# 新增Setting命令状态
SETTING_CATEGORY, SETTING_NAME, SETTING_IC, SETTING_TYPE = range(16, 20)

# ====================================
# 基础命令区 - /start, /help, /cancel
# ====================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /start 命令 - 主菜单"""
    # 检查并关闭其他会话
    await close_other_conversations(update, context)
    
    keyboard = [
        [InlineKeyboardButton("📊 新增销售记录", callback_data="menu_sales")],
        [InlineKeyboardButton("💰 费用管理", callback_data="menu_cost")],
        [InlineKeyboardButton("📈 报表生成", callback_data="menu_report")],
        [InlineKeyboardButton("⚙️ System Settings", callback_data="menu_setting")],
        [InlineKeyboardButton("❓ 帮助说明", callback_data="menu_help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = """
🚀 *财务管理助手*

👋 欢迎使用！请选择需要的功能：

📊 *新增销售记录* - 登记发票和佣金
💰 *费用管理* - 记录各项支出
📈 *报表生成* - 查看统计报告
⚙️ *System Settings* - 创建代理商/供应商
    """
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            welcome_message, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理 /help 命令和帮助回调"""
    keyboard = [[InlineKeyboardButton("🔙 返回主菜单", callback_data="back_main")]]
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
    await update.message.reply_text("✅ 操作已取消")
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
        [InlineKeyboardButton("➕ 新增销售记录", callback_data="sales_add")],
        [InlineKeyboardButton("📋 查看销售记录", callback_data="sales_list")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "📊 *销售记录管理*\n\n请选择操作："
    
    await update.callback_query.edit_message_text(
        message, 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def sales_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """开始添加销售记录 - 输入负责人"""
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="back_sales")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "👤 请输入负责人姓名：",
        reply_markup=reply_markup
    )
    return SALES_PERSON

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
            await query.edit_message_text("❌ 未知操作，请重新开始")
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
        await update.message.reply_text("⚠️ 请输入有效的金额数字")
        return SALES_AMOUNT
    except Exception as e:
        logger.error(f"处理金额时发生未知错误: {e}")
        await update.message.reply_text("❌ 处理出错，请重新输入金额")
        return SALES_AMOUNT

async def sales_client_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理客户类型选择"""
    query = update.callback_query
    await query.answer()
    
    client_type = "Company" if query.data == "client_company" else "Agent"
    context.user_data['sales_client'] = client_type
    
    # 如果选择的是公司，直接进入确认步骤
    if client_type == "Company":
        # 计算佣金 (示例: 公司5%)
        amount = context.user_data['sales_amount']
        commission_rate = 0.05
        commission = amount * commission_rate
        context.user_data['sales_commission'] = commission
        context.user_data['commission_rate'] = commission_rate
        
        # 跳转到确认界面
        return await show_sales_confirmation(update, context)
    
    # 如果选择的是代理商，先让用户选择佣金计算方式
    keyboard = [
        [InlineKeyboardButton("💯 设置佣金百分比", callback_data="commission_percent")],
        [InlineKeyboardButton("💰 直接输入佣金金额", callback_data="commission_amount")],
        [InlineKeyboardButton("❌ 取消", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        "🤝 <b>请选择佣金计算方式:</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup
    )
    
    # 返回一个新的状态用于处理佣金计算方式选择
    return SALES_COMMISSION_TYPE

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
        keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💯 <b>请输入佣金百分比:</b>\n\n<i>例如: 输入 10 表示 10%</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        return SALES_COMMISSION_PERCENT
        
    elif query.data == "commission_amount":
        # 选择直接输入佣金金额
        amount = context.user_data['sales_amount']
        keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💰 <b>总金额:</b> RM{amount:,.2f}\n\n<b>请直接输入佣金金额:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        return SALES_COMMISSION_AMOUNT
    
    # 未知回调数据
    await query.edit_message_text("❌ 未知操作，请重新开始")
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
            await update.message.reply_text("⚠️ 请输入0-100之间的百分比")
            return SALES_COMMISSION_PERCENT
        
        # 计算佣金
        amount = context.user_data['sales_amount']
        commission_rate = percent / 100
        commission = amount * commission_rate
        
        # 保存数据
        context.user_data['commission_rate'] = commission_rate
        context.user_data['sales_commission'] = commission
        context.user_data['commission_type'] = 'percent'
        
        # 进入代理商选择
        return await show_agent_selection(update, context)
        
    except ValueError as e:
        logger.error(f"百分比解析错误: {e}")
        await update.message.reply_text("⚠️ 请输入有效的数字百分比")
        return SALES_COMMISSION_PERCENT
    except Exception as e:
        logger.error(f"处理佣金百分比时发生错误: {e}")
        await update.message.reply_text("❌ 处理出错，请重新输入")
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
            await update.message.reply_text(f"⚠️ 佣金不能小于0或大于总金额 RM{total_amount:,.2f}")
            return SALES_COMMISSION_AMOUNT
        
        # 计算佣金比例
        commission_rate = commission / total_amount if total_amount > 0 else 0
        
        # 保存数据
        context.user_data['commission_rate'] = commission_rate
        context.user_data['sales_commission'] = commission
        context.user_data['commission_type'] = 'fixed'
        
        # 进入代理商选择
        return await show_agent_selection(update, context)
        
    except ValueError as e:
        logger.error(f"佣金金额解析错误: {e}")
        await update.message.reply_text("⚠️ 请输入有效的金额数字")
        return SALES_COMMISSION_AMOUNT
    except Exception as e:
        logger.error(f"处理佣金金额时发生错误: {e}")
        await update.message.reply_text("❌ 处理出错，请重新输入")
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
        [InlineKeyboardButton("✏️ Edit", callback_data="sales_add")],
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
    else:
        client_display = client_type
    
    confirm_message = f"""
📊 <b>INVOICE CONFIRMATION</b>

👤 <b>Person in Charge:</b> {person}
💰 <b>Amount:</b> RM{amount:,.2f}
🎯 <b>Client Type:</b> {client_display}
💵 <b>Commission:</b> RM{commission:,.2f} ({commission_rate:.1f}%)

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
            commission_note = "按百分比计算佣金"
        elif commission_type == 'fixed':
            commission_note = "固定佣金金额"
        
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
✅ <b>销售记录保存成功!</b>

👤 <b>负责人:</b> {person}
💰 <b>金额:</b> RM{amount:,.2f}
💵 <b>佣金:</b> RM{commission:,.2f}
🕒 <b>时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
        
        keyboard = [[InlineKeyboardButton("🔙 返回主菜单", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            success_message,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"保存销售记录失败: {e}")
        await query.edit_message_text(
            "❌ <b>保存失败，请重试。</b>",
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
    """费用管理主菜单"""
    await close_other_conversations(update, context)
    
    keyboard = [
        [InlineKeyboardButton("🛒 采购支出", callback_data="cost_purchase")],
        [InlineKeyboardButton("⚡ 水电网络", callback_data="cost_utility")],
        [InlineKeyboardButton("👥 人工工资", callback_data="cost_salary")],
        [InlineKeyboardButton("📦 其他支出", callback_data="cost_other")],
        [InlineKeyboardButton("📋 查看记录", callback_data="cost_list")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = "💰 *费用管理*\n\n请选择支出类型："
    
    await update.callback_query.edit_message_text(
        message, 
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def cost_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理费用类型选择"""
    query = update.callback_query
    await query.answer()
    
    cost_types = {
        "cost_purchase": "采购支出",
        "cost_utility": "水电网络", 
        "cost_salary": "人工工资",
        "cost_other": "其他支出"
    }
    
    context.user_data['cost_type'] = cost_types[query.data]
    
    if query.data == "cost_purchase":
        # 采购需要选择供应商
        keyboard = [
            [InlineKeyboardButton("🏭 供应商A", callback_data="supplier_a")],
            [InlineKeyboardButton("🏭 供应商B", callback_data="supplier_b")],
            [InlineKeyboardButton("➕ 其他供应商", callback_data="supplier_other")],
            [InlineKeyboardButton("❌ 取消", callback_data="back_cost")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🛒 *采购支出*\n\n请选择供应商：",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return COST_SUPPLIER
    else:
        # 其他类型直接输入金额
        keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💰 *{cost_types[query.data]}*\n\n请输入金额：",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        return COST_AMOUNT

async def cost_supplier_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理供应商选择"""
    query = update.callback_query
    await query.answer()
    
    suppliers = {
        "supplier_a": "供应商A",
        "supplier_b": "供应商B",
        "supplier_other": "其他供应商"
    }
    
    context.user_data['cost_supplier'] = suppliers.get(query.data, "其他供应商")
    
    keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="back_cost")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"🏭 供应商：{context.user_data['cost_supplier']}\n\n💰 请输入采购金额：",
        reply_markup=reply_markup
    )
    return COST_AMOUNT

async def cost_amount_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理费用金额输入"""
    try:
        amount = float(update.message.text.strip())
        context.user_data['cost_amount'] = amount
        
        keyboard = [[InlineKeyboardButton("❌ 取消", callback_data="back_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"💰 金额：¥{amount:,.2f}\n\n📝 请输入备注说明（可选，直接发送\"跳过\"）：",
            reply_markup=reply_markup
        )
        return COST_DESC
    except ValueError:
        await update.message.reply_text("⚠️ 请输入有效的数字金额")
        return COST_AMOUNT

async def cost_desc_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理费用说明输入"""
    desc = update.message.text.strip()
    context.user_data['cost_desc'] = "" if desc == "跳过" else desc
    
    # 生成确认信息
    cost_type = context.user_data['cost_type']
    amount = context.user_data['cost_amount']
    supplier = context.user_data.get('cost_supplier', '')
    description = context.user_data['cost_desc']
    
    keyboard = [
        [InlineKeyboardButton("✅ 确认保存", callback_data="cost_save")],
        [InlineKeyboardButton("✏️ 重新填写", callback_data=f"cost_{cost_type.lower()}")],
        [InlineKeyboardButton("❌ 取消", callback_data="back_cost")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    confirm_message = f"""
💰 *费用记录确认*

📋 类型：{cost_type}
💰 金额：¥{amount:,.2f}
"""
    
    if supplier:
        confirm_message += f"🏭 供应商：{supplier}\n"
    if description:
        confirm_message += f"📝 备注：{description}\n"
    
    confirm_message += "\n请确认信息是否正确："
    
    await update.message.reply_text(
        confirm_message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    return COST_CONFIRM

async def cost_save_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """保存费用记录"""
    query = update.callback_query
    await query.answer()
    
    try:
        # 保存到 Google Sheets
        sheets_manager = SheetsManager()
        cost_data = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'type': context.user_data['cost_type'],
            'amount': context.user_data['cost_amount'],
            'supplier': context.user_data.get('cost_supplier', ''),
            'description': context.user_data['cost_desc']
        }
        
        await sheets_manager.add_cost_record(cost_data)
        
        keyboard = [[InlineKeyboardButton("🔙 返回费用菜单", callback_data="menu_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "✅ 费用记录已成功保存！",
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"保存费用记录失败: {e}")
        await query.edit_message_text("❌ 保存失败，请重试")
    
    # 清除临时数据
    context.user_data.clear()
    return ConversationHandler.END

async def cost_list_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """查看费用记录"""
    query = update.callback_query
    await query.answer()
    
    try:
        sheets_manager = SheetsManager()
        cost_records = await sheets_manager.get_recent_costs(limit=10)
        
        if not cost_records:
            message = "📋 暂无费用记录"
        else:
            message = "📋 *最近费用记录*\n\n"
            for record in cost_records:
                message += f"📅 {record['date']}\n"
                message += f"📋 {record['type']} | 💰 ¥{record['amount']:,.2f}\n"
                if record.get('supplier'):
                    message += f"🏭 {record['supplier']}\n"
                if record.get('description'):
                    message += f"📝 {record['description']}\n"
                message += "\n"
        
        keyboard = [[InlineKeyboardButton("🔙 返回费用菜单", callback_data="menu_cost")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"获取费用记录失败: {e}")
        await query.edit_message_text("❌ 获取记录失败，请重试")

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
        await start_command(update, context)
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
        # 模拟直接调用Setting命令
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
    elif query.data == "menu_help":
        await help_command(update, context)
        return ConversationHandler.END
    
    # 销售记录回调
    elif query.data == "back_sales":
        return await sales_menu(update, context)
    elif query.data == "sales_add":
        return await sales_add_start(update, context)
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
    elif query.data in ["cost_purchase", "cost_utility", "cost_salary", "cost_other"]:
        return await cost_type_handler(update, context)
    elif query.data in ["supplier_a", "supplier_b", "supplier_other"]:
        return await cost_supplier_handler(update, context)
    elif query.data == "cost_save":
        return await cost_save_handler(update, context)
    elif query.data == "cost_list":
        await cost_list_handler(update, context)
        return ConversationHandler.END
    
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
    
    # Setting命令会话处理器
    setting_conversation = ConversationHandler(
        entry_points=[
            CommandHandler("Setting", setting_command),
            CallbackQueryHandler(setting_category_handler, pattern="^setting_create_")
        ],
        states={
            SETTING_CATEGORY: [CallbackQueryHandler(setting_category_handler, pattern="^setting_create_")],
            SETTING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_name_handler)],
            SETTING_IC: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_ic_handler)],
            SETTING_TYPE: [MessageHandler(filters.TEXT & ~filters.COMMAND, setting_type_handler)]
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
            CallbackQueryHandler(sales_add_start, pattern="^sales_add$"),
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
            SALES_CONFIRM: [CallbackQueryHandler(sales_save_handler, pattern="^sales_save$")]
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
            CallbackQueryHandler(cost_type_handler, pattern="^cost_")
        ],
        states={
            COST_TYPE: [CallbackQueryHandler(cost_type_handler, pattern="^cost_")],
            COST_SUPPLIER: [CallbackQueryHandler(cost_supplier_handler, pattern="^supplier_")],
            COST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, cost_amount_handler)],
            COST_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, cost_desc_handler)],
            COST_CONFIRM: [CallbackQueryHandler(cost_save_handler, pattern="^cost_save$")]
        },
        fallbacks=[
            CallbackQueryHandler(callback_query_handler),
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
    """处理供应商类别输入"""
    supplier_type = update.message.text.strip()
    name = context.user_data.get('setting_name')
    
    try:
        sheets_manager = SheetsManager()
        
        # 添加供应商，包含类别
        supplier_data = {
            'name': name,
            'type': supplier_type,
            'status': '激活'
        }
        
        sheets_manager.add_supplier(supplier_data)
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ Supplier \"{name}\" (Category: {supplier_type}) has been successfully added!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"添加供应商失败: {e}")
        await update.message.reply_text("❌ Failed to add. Please try again.")
    
    context.user_data.clear()
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
        keyboard.append([InlineKeyboardButton("❌ 取消", callback_data="back_main")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = "👤 <b>请选择负责人:</b>"
        
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
        error_message = "❌ <b>获取负责人数据失败</b>\n\n请稍后再试。"
        
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

# 添加一个新的状态常量
SALES_AGENT_SELECT = 20  # 使用一个新的状态码

# 添加代理商选择处理函数
async def sales_agent_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理代理商选择"""
    query = update.callback_query
    await query.answer()
    
    agent_data = query.data
    if agent_data.startswith("agent_"):
        # 解析代理商数据 agent_{name}
        agent_name = agent_data[6:]
        context.user_data['sales_agent'] = agent_name
        
        # 佣金率和佣金已经在之前的步骤中设置好了
        # 现在直接跳转到确认界面
        return await show_sales_confirmation(update, context)
    
    # 未知回调数据
    await query.edit_message_text("❌ 未知操作，请重新开始")
    return ConversationHandler.END
