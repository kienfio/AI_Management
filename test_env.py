#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
环境变量测试脚本
用于检查Render平台上的环境变量是否正确设置
"""

import os
import base64
import json
import sys

def main():
    """主函数 - 检查环境变量"""
    print("\n=== 环境变量检查 ===")
    
    # 检查Base64凭证
    base64_var = os.getenv('GOOGLE_CREDENTIALS_BASE64')
    if base64_var:
        print("✅ GOOGLE_CREDENTIALS_BASE64 已设置")
        try:
            # 尝试解码并解析JSON
            decoded = base64.b64decode(base64_var).decode('utf-8')
            json_data = json.loads(decoded)
            print("✅ Base64解码和JSON解析成功")
            print(f"项目ID: {json_data.get('project_id')}")
            print(f"客户邮箱: {json_data.get('client_email')}")
            
            # 检查是否包含必要字段
            required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
            missing = [field for field in required_fields if field not in json_data]
            if missing:
                print(f"⚠️ 警告: 缺少必要字段: {', '.join(missing)}")
            else:
                print("✅ 包含所有必要字段")
        except base64.binascii.Error as e:
            print(f"❌ Base64解码失败: {e}")
            print("提示: 确保Base64字符串没有额外的空格、换行符或其他字符")
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析失败: {e}")
            print("提示: 解码后的内容不是有效的JSON格式")
        except Exception as e:
            print(f"❌ 解码过程中出错: {e}")
    else:
        print("❌ GOOGLE_CREDENTIALS_BASE64 未设置")
    
    # 检查其他环境变量
    print("\n=== 其他环境变量 ===")
    for var in ['GOOGLE_CREDENTIALS_CONTENT', 'GOOGLE_CREDENTIALS_FILE', 'GOOGLE_CREDENTIALS_JSON', 
                'GOOGLE_SHEET_ID', 'TELEGRAM_TOKEN']:
        value = os.getenv(var)
        if value:
            print(f"✅ {var} 已设置")
            # 对于敏感信息，只显示长度
            if var in ['GOOGLE_CREDENTIALS_CONTENT', 'GOOGLE_CREDENTIALS_JSON', 'TELEGRAM_TOKEN']:
                print(f"   长度: {len(value)} 字符")
            # 对于其他变量，显示值
            elif var == 'GOOGLE_SHEET_ID':
                print(f"   值: {value}")
        else:
            print(f"❌ {var} 未设置")
    
    # 检查Python版本和工作目录
    print("\n=== 系统信息 ===")
    print(f"Python版本: {sys.version}")
    print(f"当前工作目录: {os.getcwd()}")
    print(f"目录内容: {', '.join(os.listdir('.'))}")
    
    # 检查导入模块
    print("\n=== 模块导入测试 ===")
    try:
        import config
        print("✅ 成功导入 config 模块")
    except ImportError as e:
        print(f"❌ 导入 config 模块失败: {e}")
    
    try:
        import google_sheets
        print("✅ 成功导入 google_sheets 模块")
    except ImportError as e:
        print(f"❌ 导入 google_sheets 模块失败: {e}")
    
    # 如果成功导入，尝试检查模块内容
    if 'config' in sys.modules:
        config_module = sys.modules['config']
        if hasattr(config_module, '_get_credentials'):
            print("✅ config 模块包含 _get_credentials 方法")
        else:
            print("❌ config 模块不包含 _get_credentials 方法")
    
    if 'google_sheets' in sys.modules:
        gs_module = sys.modules['google_sheets']
        if hasattr(gs_module, 'GoogleSheetsManager'):
            print("✅ google_sheets 模块包含 GoogleSheetsManager 类")
        else:
            print("❌ google_sheets 模块不包含 GoogleSheetsManager 类")

if __name__ == "__main__":
    main() 