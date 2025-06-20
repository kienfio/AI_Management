#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
销售管理 Telegram Bot
主程序入口 - Bot 启动和配置
支持Webhook模式部署
"""

import logging
import os
import base64
import json
import sys

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 尝试加载.env文件
try:
    from dotenv import load_dotenv
    load_dotenv()
    logger.info("已加载.env文件")
except ImportError:
    logger.warning("dotenv模块未安装，跳过加载.env文件")

# 输出所有相关环境变量
logger.info(f"DRIVE_FOLDER_INVOICE_PDF: {os.getenv('DRIVE_FOLDER_INVOICE_PDF')}")
logger.info(f"DRIVE_FOLDER_ELECTRICITY: {os.getenv('DRIVE_FOLDER_ELECTRICITY')}")
logger.info(f"DRIVE_FOLDER_WATER: {os.getenv('DRIVE_FOLDER_WATER')}")
logger.info(f"DRIVE_FOLDER_PURCHASING: {os.getenv('DRIVE_FOLDER_PURCHASING')}")
logger.info(f"DRIVE_FOLDER_WIFI: {os.getenv('DRIVE_FOLDER_WIFI')}")

# 检查必要的环境变量
if not os.getenv('DRIVE_FOLDER_INVOICE_PDF'):
    logger.error("未设置 DRIVE_FOLDER_INVOICE_PDF 环境变量")
    raise ValueError("必须设置 DRIVE_FOLDER_INVOICE_PDF 环境变量")

# 现在导入telegram相关模块
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

def test_credentials():
    """测试Google API凭证"""
    print("===== 环境变量检查 =====")
    print(f"GOOGLE_CREDENTIALS_BASE64: {'✅ 已设置' if os.getenv('GOOGLE_CREDENTIALS_BASE64') else '❌ 未设置'}")
    print(f"GOOGLE_SHEET_ID: {'✅ 已设置' if os.getenv('GOOGLE_SHEET_ID') else '❌ 未设置'}")
    print(f"TELEGRAM_TOKEN: {'✅ 已设置' if os.getenv('TELEGRAM_TOKEN') else '❌ 未设置'}")
    print(f"DRIVE_FOLDER_INVOICE_PDF: {'✅ 已设置' if os.getenv('DRIVE_FOLDER_INVOICE_PDF') else '❌ 未设置'}")
    
    # 测试Base64凭证
    google_creds_base64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
    if google_creds_base64:
        print("\n===== 测试Base64凭证 =====")
        try:
            print("正在解码Base64...")
            creds_json = base64.b64decode(google_creds_base64).decode('utf-8')
            
            print("正在解析JSON...")
            creds_info = json.loads(creds_json)
            
            # 检查必要字段
            required_fields = [
                'type', 'project_id', 'private_key_id', 'private_key', 
                'client_email', 'client_id', 'auth_uri', 'token_uri'
            ]
            
            missing_fields = [field for field in required_fields if field not in creds_info]
            
            if missing_fields:
                print(f"❌ 凭证缺少必要字段: {', '.join(missing_fields)}")
                return False
            else:
                print("✅ 凭证包含所有必要字段")
                print(f"项目ID: {creds_info.get('project_id')}")
                print(f"客户邮箱: {creds_info.get('client_email')}")
                return True
                
        except base64.binascii.Error:
            print("❌ Base64解码失败，请检查GOOGLE_CREDENTIALS_BASE64环境变量格式")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            return False
    else:
        print("\n❌ 未设置GOOGLE_CREDENTIALS_BASE64环境变量")
        return False

# 先测试凭证再导入配置
test_credentials()

# 导入其他模块
logger.info("导入配置模块...")
from config import BOT_TOKEN
logger.info("导入处理器模块...")
from telegram_handlers import (
    # 基础命令
    start_command, help_command, cancel_command, unknown_command, error_handler,
    # 对话处理器
    get_conversation_handlers, register_handlers
)

def clear_webhook(token):
    """清除现有的webhook设置"""
    import requests
    url = f"https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true"
    try:
        response = requests.get(url)
        result = response.json()
        if result.get('ok'):
            logger.info("✅ Webhook已成功清除")
        else:
            logger.error(f"❌ 清除Webhook失败: {result.get('description')}")
    except Exception as e:
        logger.error(f"❌ 请求失败: {e}")

def main():
    """主函数 - 启动 Bot"""
    
    # 先清除现有的webhook设置
    logger.info("正在清除现有的webhook设置...")
    clear_webhook(BOT_TOKEN)
    
    # 创建 Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 使用register_handlers函数注册所有处理器
    register_handlers(application)
    
    # 确保错误处理器已注册
    application.add_error_handler(error_handler)
    
    # 尝试启动年度自动化任务调度器
    try:
        from scheduled_tasks import start_scheduler
        if start_scheduler():
            logger.info("✅ 年度自动化任务调度器已启动")
        else:
            logger.warning("⚠️ 年度自动化任务调度器启动失败")
    except ImportError:
        logger.warning("⚠️ 未找到scheduled_tasks模块，年度自动化功能将不可用")
    except Exception as e:
        logger.error(f"❌ 启动年度自动化任务调度器失败: {e}")
    
    # 获取环境变量
    port = int(os.environ.get("PORT", 8080))
    webhook_url = os.environ.get("WEBHOOK_URL")
    
    # 如果设置了webhook_url，使用webhook模式，否则使用轮询模式
    if webhook_url:
        # Webhook模式
        logger.info(f"🚀 销售管理 Bot 启动中 (Webhook模式)...")
        application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path=BOT_TOKEN,
            webhook_url=f"{webhook_url}/{BOT_TOKEN}",
            allowed_updates=["message", "callback_query"]
        )
    else:
        # 轮询模式 (本地开发)
        logger.info("🚀 销售管理 Bot 启动中 (轮询模式)...")
        application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == '__main__':
    main()
