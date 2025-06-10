#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
销售管理 Telegram Bot
主程序入口 - Bot 启动和配置
"""

import logging
import os
import base64
import json
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

def test_credentials():
    """测试Google API凭证"""
    print("===== 环境变量检查 =====")
    print(f"GOOGLE_CREDENTIALS_BASE64: {'✅ 已设置' if os.getenv('GOOGLE_CREDENTIALS_BASE64') else '❌ 未设置'}")
    print(f"GOOGLE_SHEET_ID: {'✅ 已设置' if os.getenv('GOOGLE_SHEET_ID') else '❌ 未设置'}")
    print(f"TELEGRAM_TOKEN: {'✅ 已设置' if os.getenv('TELEGRAM_TOKEN') else '❌ 未设置'}")
    
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
from config import BOT_TOKEN
from telegram_handlers import (
    # 基础命令
    start_command, help_command, cancel_command, unknown_command, error_handler,
    # 对话处理器
    get_conversation_handlers, register_handlers
)

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """主函数 - 启动 Bot"""
    
    # 创建 Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # 使用register_handlers函数注册所有处理器
    register_handlers(application)
    
    # 确保错误处理器已注册
    application.add_error_handler(error_handler)
    
    # 启动 Bot
    logger.info("🚀 销售管理 Bot 启动中...")
    application.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == '__main__':
    main()
