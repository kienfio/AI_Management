import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler, CallbackQueryHandler
from common.google_services import GoogleServices
from common.shared import logger

# 初始化Google服务
google_services = GoogleServices()

# 定义会话状态
(
    MAIN_MENU,
    CREATE_AGENT,
    CREATE_SUPPLIER,
    CREATE_PERSONAL,
    WAITING_AGENT_NAME,
    WAITING_AGENT_IC,
    WAITING_SUPPLIER_NAME,
    WAITING_SUPPLIER_CATEGORY,
    WAITING_PERSONAL_NAME,
) = range(9)

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/start命令"""
    logger.info(f"收到/start命令，来自用户ID: {update.effective_user.id}, 用户名: {update.effective_user.username}")
    
    welcome_message = """
🚀 <b>财务管理助手</b>

📋 <b>快速开始</b>
┣ 📊 /add_expense — 添加支出
┣ 💰 /categories — 支出类别  
┣ ⚙️ /settings — 系统配置
┗ 📈 /report — 报表生成

💡 /help 详细说明 | ❌ /cancel 取消操作
    """
    
    await update.message.reply_text(welcome_message, parse_mode=ParseMode.HTML)
    logger.info(f"已回复/start命令，用户ID: {update.effective_user.id}")

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/help命令"""
    logger.info(f"收到/help命令，来自用户ID: {update.effective_user.id}")
    
    help_message = """
📖 <b>使用指南</b>

🔧 <b>基础命令</b>
• /start — 主菜单
• /help — 帮助说明
• /cancel — 取消当前操作

📊 <b>添加支出</b> (/add_expense)
• 格式: /add_expense 日期 类别 金额 描述 [备注]
• 例如: <code>/add_expense 2024-06-10 餐饮 50 午餐</code>
• 支持上传收据照片

💰 <b>支出类别</b> (/categories)
• 查看所有可用类别
• 餐饮、交通、购物等

⚙️ <b>系统配置</b> (/settings)
• 查看当前配置
• 修改默认设置

📈 <b>报表功能</b> (/report)
• 生成当月报表
• 指定月份查询 <code>/report 2024-06</code>

💡 <b>小贴士：直接发送收据照片，系统会自动处理</b>
    """
    
    await update.message.reply_text(help_message, parse_mode=ParseMode.HTML)
    logger.info(f"已回复/help命令，用户ID: {update.effective_user.id}")

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理 /cancel 命令，取消当前会话"""
    logger.info(f"收到/cancel命令，来自用户ID: {update.effective_user.id}")
    await update.message.reply_text("✅ 操作已取消，使用 /start 重新开始")
    # 清除用户数据
    context.user_data.clear()
    return ConversationHandler.END

async def add_expense_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/add_expense命令"""
    logger.info(f"收到/add_expense命令，来自用户ID: {update.effective_user.id}, 参数: {context.args}")
    try:
        # 检查参数数量
        if len(context.args) < 4:
            logger.warning(f"参数不足，用户ID: {update.effective_user.id}")
            await update.message.reply_text(
                "⚠️ <b>参数不足</b>\n\n请使用以下格式：\n<code>/add_expense 日期 类别 金额 描述 [备注]</code>\n例如：<code>/add_expense 2024-06-10 餐饮 50 午餐</code>",
                parse_mode=ParseMode.HTML
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
            
            success_message = f"""
✅ <b>支出记录已添加</b>

📅 日期：<code>{date}</code>
🏷️ 类别：<code>{category}</code>
💰 金额：<code>{amount}</code>
📝 描述：<code>{description}</code>
"""
            if note:
                success_message += f"📌 备注：<code>{note}</code>"
                
            await update.message.reply_text(success_message, parse_mode=ParseMode.HTML)
        else:
            logger.error(f"支出记录添加失败，用户ID: {update.effective_user.id}")
            await update.message.reply_text("❌ 添加支出记录失败，请稍后重试")

    except ValueError:
        logger.error(f"金额格式错误，用户ID: {update.effective_user.id}")
        await update.message.reply_text("⚠️ 金额格式错误，请输入有效的数字")
    except Exception as e:
        logger.error(f"处理add_expense命令时出错: {e}, 用户ID: {update.effective_user.id}")
        await update.message.reply_text("⚠️ 发生错误，请稍后重试")

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
                
                success_message = f"""
📸 <b>收据已上传成功</b>

请使用 /add_expense 命令添加支出记录：
<code>/add_expense 日期 类别 金额 描述 收据链接</code>

例如：
<code>/add_expense 2024-06-10 餐饮 50 午餐 {file_url}</code>
"""
                
                await update.message.reply_text(success_message, parse_mode=ParseMode.HTML)
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
        await update.message.reply_text("⚠️ 处理照片时出错，请稍后重试")

async def categories_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/categories命令"""
    logger.info(f"收到/categories命令，来自用户ID: {update.effective_user.id}")
    
    categories_message = """
📋 <b>支出类别列表</b>

• 🍔 餐饮 - 餐厅、外卖、咖啡等
• 🚌 交通 - 公交、地铁、打车等
• 🛒 购物 - 日用品、衣物等
• 🎬 娱乐 - 电影、游戏等
• 🏠 居住 - 房租、水电等
• 💊 医疗 - 药品、诊疗等
• 📚 教育 - 书籍、课程等
• 📱 通讯 - 话费、网费等
• 🔧 其他 - 未分类支出

使用 <code>/add_expense</code> 命令时请使用以上类别
"""
    
    await update.message.reply_text(categories_message, parse_mode=ParseMode.HTML)
    logger.info(f"已回复/categories命令，用户ID: {update.effective_user.id}")

async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/settings命令"""
    logger.info(f"收到/settings命令，来自用户ID: {update.effective_user.id}")
    
    # 创建内联键盘
    keyboard = [
        [InlineKeyboardButton("创建代理商", callback_data="create_agent")],
        [InlineKeyboardButton("创建供应商", callback_data="create_supplier")],
        [InlineKeyboardButton("创建负责人", callback_data="create_personal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    settings_message = """
⚙️ <b>系统设置</b>

请选择要执行的操作:
"""
    
    await update.message.reply_text(settings_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    logger.info(f"已回复/settings命令，用户ID: {update.effective_user.id}")
    return MAIN_MENU

async def settings_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理设置菜单按钮点击"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "create_agent":
        await query.edit_message_text(
            "📝 <b>创建代理商</b>\n\n请输入代理商名称:", 
            parse_mode=ParseMode.HTML
        )
        return WAITING_AGENT_NAME
        
    elif query.data == "create_supplier":
        await query.edit_message_text(
            "📝 <b>创建供应商</b>\n\n请输入供应商名称:", 
            parse_mode=ParseMode.HTML
        )
        return WAITING_SUPPLIER_NAME
        
    elif query.data == "create_personal":
        await query.edit_message_text(
            "📝 <b>创建负责人</b>\n\n请输入负责人姓名:", 
            parse_mode=ParseMode.HTML
        )
        return WAITING_PERSONAL_NAME
    
    return ConversationHandler.END

async def agent_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理代理商名称输入"""
    agent_name = update.message.text
    context.user_data['agent_name'] = agent_name
    
    await update.message.reply_text(
        f"已记录代理商名称: <b>{agent_name}</b>\n\n请输入代理商IC号码:", 
        parse_mode=ParseMode.HTML
    )
    return WAITING_AGENT_IC

async def agent_ic_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理代理商IC输入"""
    agent_ic = update.message.text
    agent_name = context.user_data.get('agent_name', '未知')
    
    # 保存到数据库或Google表格
    try:
        # 这里添加保存代理商信息的代码
        # 例如: google_services.add_agent(agent_name, agent_ic)
        
        await update.message.reply_text(
            f"✅ <b>代理商创建成功</b>\n\n名称: <code>{agent_name}</code>\nIC: <code>{agent_ic}</code>",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"用户 {update.effective_user.id} 创建了代理商: {agent_name}, IC: {agent_ic}")
    except Exception as e:
        logger.error(f"创建代理商时出错: {e}")
        await update.message.reply_text("❌ 创建代理商失败，请稍后重试")
    
    return ConversationHandler.END

async def supplier_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理供应商名称输入"""
    supplier_name = update.message.text
    context.user_data['supplier_name'] = supplier_name
    
    await update.message.reply_text(
        f"已记录供应商名称: <b>{supplier_name}</b>\n\n请输入供应商类别:", 
        parse_mode=ParseMode.HTML
    )
    return WAITING_SUPPLIER_CATEGORY

async def supplier_category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理供应商类别输入"""
    supplier_category = update.message.text
    supplier_name = context.user_data.get('supplier_name', '未知')
    
    # 保存到数据库或Google表格
    try:
        # 这里添加保存供应商信息的代码
        # 例如: google_services.add_supplier(supplier_name, supplier_category)
        
        await update.message.reply_text(
            f"✅ <b>供应商创建成功</b>\n\n名称: <code>{supplier_name}</code>\n类别: <code>{supplier_category}</code>",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"用户 {update.effective_user.id} 创建了供应商: {supplier_name}, 类别: {supplier_category}")
    except Exception as e:
        logger.error(f"创建供应商时出错: {e}")
        await update.message.reply_text("❌ 创建供应商失败，请稍后重试")
    
    return ConversationHandler.END

async def personal_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理负责人姓名输入"""
    personal_name = update.message.text
    
    # 保存到数据库或Google表格
    try:
        # 这里添加保存负责人信息的代码
        # 例如: google_services.add_personal(personal_name)
        
        await update.message.reply_text(
            f"✅ <b>负责人创建成功</b>\n\n姓名: <code>{personal_name}</code>",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"用户 {update.effective_user.id} 创建了负责人: {personal_name}")
    except Exception as e:
        logger.error(f"创建负责人时出错: {e}")
        await update.message.reply_text("❌ 创建负责人失败，请稍后重试")
    
    return ConversationHandler.END

async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理/report命令"""
    logger.info(f"收到/report命令，来自用户ID: {update.effective_user.id}")
    
    report_message = """
📊 <b>报表功能</b>

<b>功能开发中，敬请期待...</b>

将支持:
• 📅 按月份生成报表
• 📊 支出分类统计
• 📈 消费趋势分析
• 📑 自定义报表导出
"""
    
    await update.message.reply_text(report_message, parse_mode=ParseMode.HTML)
    logger.info(f"已回复/report命令，用户ID: {update.effective_user.id}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """处理错误"""
    # 获取异常信息
    error = context.error
    
    # 记录详细的错误信息
    logger.error("发生异常:", exc_info=context.error)
    if update:
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

# 导出所有处理函数
__all__ = [
    'start_handler',
    'help_handler',
    'add_expense_handler',
    'photo_handler',
    'cancel_handler',
    'categories_handler',
    'settings_handler',
    'settings_button_handler',
    'agent_name_handler',
    'agent_ic_handler',
    'supplier_name_handler',
    'supplier_category_handler',
    'personal_name_handler',
    'report_handler',
    'error_handler'
] 
