#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主修复脚本 - 执行所有必要的修复步骤
"""

import os
import sys
import base64
import json
import logging
from typing import Dict, Any, List, Optional
import traceback

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_config_file() -> bool:
    """修复config.py文件"""
    print("\n=== 修复config.py文件 ===")
    config_path = 'config.py'
    
    if not os.path.exists(config_path):
        print(f"❌ 文件不存在: {config_path}")
        return False
    
    print(f"✅ 文件存在: {config_path}")
    
    # 读取文件内容
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已包含GOOGLE_CREDENTIALS_BASE64
    if 'GOOGLE_CREDENTIALS_BASE64' in content:
        print("✅ 文件已包含 GOOGLE_CREDENTIALS_BASE64")
        
        # 检查错误消息是否包含Base64选项
        if 'Base64编码的JSON凭证' in content:
            print("✅ 错误消息已包含 Base64 选项")
            return True
    
    # 添加Base64支持
    print("正在添加Base64支持...")
    
    # 查找_get_credentials方法
    get_creds_start = content.find("def _get_credentials")
    if get_creds_start == -1:
        print("❌ 未找到 _get_credentials 方法")
        return False
    
    # 查找方式1的开始位置
    method1_start = content.find("# 方式1:", get_creds_start)
    if method1_start == -1:
        print("❌ 未找到方式1注释")
        return False
    
    # 准备Base64代码
    base64_code = '''        # 方式1: 从Base64编码的环境变量读取 (推荐用于Render)
        google_creds_base64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
        if google_creds_base64:
            try:
                import base64
                # 解码Base64字符串
                creds_json = base64.b64decode(google_creds_base64).decode('utf-8')
                creds_info = json.loads(creds_json)
                logger.info("✅ 使用 GOOGLE_CREDENTIALS_BASE64 环境变量")
                return Credentials.from_service_account_info(creds_info, scopes=scope)
            except Exception as e:
                logger.error(f"❌ 解析 GOOGLE_CREDENTIALS_BASE64 失败: {e}")
        
'''
    
    # 查找原始方式1的代码
    original_method1_code = content[method1_start:content.find("# 方式", method1_start + 10)]
    
    # 替换方式1的代码
    new_content = content.replace(original_method1_code, base64_code)
    
    # 修复错误消息
    error_pattern = 'raise ValueError('
    error_pos = new_content.find(error_pattern)
    if error_pos != -1:
        # 查找错误消息结束位置
        error_end = new_content.find(')', error_pos)
        if error_end != -1:
            old_error = new_content[error_pos:error_end+1]
            new_error = '''raise ValueError(
            "❌ 未找到 Google API 凭证。请设置以下任一环境变量：\\n"
            "- GOOGLE_CREDENTIALS_BASE64: Base64编码的JSON凭证（推荐）\\n"
            "- GOOGLE_CREDENTIALS_CONTENT: 完整的 JSON 凭证内容\\n"
            "- GOOGLE_CREDENTIALS_FILE: 凭证文件路径\\n"
            "- GOOGLE_CREDENTIALS_JSON: JSON 凭证字符串（兼容）\\n"
            "或在项目根目录放置 credentials.json 文件"
        )'''
            new_content = new_content.replace(old_error, new_error)
    
    # 写入文件
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ 已更新文件: {config_path}")
    return True

def fix_google_sheets_file() -> bool:
    """修复google_sheets.py文件"""
    print("\n=== 修复google_sheets.py文件 ===")
    file_path = 'google_sheets.py'
    
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
    
    print(f"✅ 文件存在: {file_path}")
    
    # 读取文件内容
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查是否已包含GOOGLE_CREDENTIALS_BASE64
    if 'GOOGLE_CREDENTIALS_BASE64' in content:
        print("✅ 文件已包含 GOOGLE_CREDENTIALS_BASE64")
        
        # 检查错误消息是否包含Base64选项
        if 'Base64编码的JSON凭证' in content:
            print("✅ 错误消息已包含 Base64 选项")
            return True
    
    # 添加Base64支持
    print("正在添加Base64支持...")
    
    # 查找_get_credentials方法
    get_creds_start = content.find("def _get_credentials")
    if get_creds_start == -1:
        print("❌ 未找到 _get_credentials 方法")
        return False
    
    # 查找方式1的开始位置
    method1_start = content.find("# 方式1:", get_creds_start)
    if method1_start == -1:
        print("❌ 未找到方式1注释")
        return False
    
    # 准备Base64代码
    base64_code = '''        # 方式1: 从Base64编码的环境变量读取 (推荐用于Render)
        google_creds_base64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
        if google_creds_base64:
            try:
                import base64
                # 解码Base64字符串
                creds_json = base64.b64decode(google_creds_base64).decode('utf-8')
                creds_info = json.loads(creds_json)
                logger.info("✅ 使用 GOOGLE_CREDENTIALS_BASE64 环境变量")
                return Credentials.from_service_account_info(creds_info, scopes=scope)
            except Exception as e:
                logger.error(f"❌ 解析 GOOGLE_CREDENTIALS_BASE64 失败: {e}")
        
'''
    
    # 查找原始方式1的代码
    original_method1_code = content[method1_start:content.find("# 方式", method1_start + 10)]
    
    # 替换方式1的代码
    new_content = content.replace(original_method1_code, base64_code)
    
    # 修复错误消息
    error_pattern = 'raise ValueError('
    error_pos = new_content.find(error_pattern)
    if error_pos != -1:
        # 查找错误消息结束位置
        error_end = new_content.find(')', error_pos)
        if error_end != -1:
            old_error = new_content[error_pos:error_end+1]
            new_error = '''raise ValueError(
            "❌ 未找到 Google API 凭证。请设置以下任一环境变量：\\n"
            "- GOOGLE_CREDENTIALS_BASE64: Base64编码的JSON凭证（推荐）\\n"
            "- GOOGLE_CREDENTIALS_CONTENT: 完整的 JSON 凭证内容\\n"
            "- GOOGLE_CREDENTIALS_FILE: 凭证文件路径\\n"
            "- GOOGLE_CREDENTIALS_JSON: JSON 凭证字符串（兼容）\\n"
            "或在项目根目录放置 credentials.json 文件"
        )'''
            new_content = new_content.replace(old_error, new_error)
    
    # 写入文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print(f"✅ 已更新文件: {file_path}")
    return True

def test_base64_credentials() -> bool:
    """测试Base64凭证是否可用"""
    print("\n=== 测试Base64凭证 ===")
    
    # 获取Base64凭证
    base64_creds = os.getenv('GOOGLE_CREDENTIALS_BASE64')
    if not base64_creds:
        print("❌ GOOGLE_CREDENTIALS_BASE64 环境变量未设置")
        return False
    
    try:
        # 解码Base64
        print("正在解码Base64...")
        decoded = base64.b64decode(base64_creds).decode('utf-8')
        
        # 解析JSON
        print("正在解析JSON...")
        creds_info = json.loads(decoded)
        
        # 检查必要字段
        required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
        missing = [field for field in required_fields if field not in creds_info]
        if missing:
            print(f"⚠️ 警告: 缺少必要字段: {', '.join(missing)}")
        else:
            print("✅ 凭证包含所有必要字段")
            print(f"项目ID: {creds_info.get('project_id')}")
            print(f"客户邮箱: {creds_info.get('client_email')}")
        
        return len(missing) == 0
    except Exception as e:
        print(f"❌ 测试Base64凭证失败: {e}")
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🔧 开始修复...")
    
    # 步骤1: 测试Base64凭证
    if not test_base64_credentials():
        print("❌ Base64凭证测试失败，请检查环境变量")
        return 1
    
    # 步骤2: 修复config.py
    if not fix_config_file():
        print("❌ 修复config.py失败")
        return 1
    
    # 步骤3: 修复google_sheets.py
    if not fix_google_sheets_file():
        print("❌ 修复google_sheets.py失败")
        return 1
    
    print("\n✅ 所有修复完成！请重新启动应用")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 