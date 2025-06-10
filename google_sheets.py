#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Sheets API 集成 - 优化版本
支持 Render 部署的环境变量配置
"""

import logging
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
import gspread
from google.oauth2.service_account import Credentials

logger = logging.getLogger(__name__)

# Telegram Bot 配置
BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not BOT_TOKEN:
    raise ValueError("未设置 TELEGRAM_TOKEN 环境变量")

# 配置常量
SHEET_NAMES = {
    'sales': '销售记录',
    'expenses': '费用记录', 
    'agents': '代理商管理',
    'suppliers': '供应商管理'
}

SALES_HEADERS = ['日期', '销售人员', '发票金额', '客户类型', '佣金比例', '佣金金额', '备注']
EXPENSES_HEADERS = ['日期', '费用类型', '供应商', '金额', '类别', '备注']
AGENTS_HEADERS = ['姓名', '联系人', '电话', '邮箱', '佣金比例', '状态']
SUPPLIERS_HEADERS = ['供应商名称', '联系人', '电话', '邮箱', '产品/服务', '状态']

class GoogleSheetsManager:
    """Google Sheets 管理器 - 适配 Render 部署环境"""
    
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.spreadsheet_id = None
        self.folder_id = None
        self._initialize_client()
    
    def _get_credentials(self) -> Credentials:
        """获取 Google API 凭证 - 适配你的环境变量"""
        scope = [
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # 方式1: 从Base64编码的环境变量读取 (推荐用于Render)
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
        
        # 方式2: 从 GOOGLE_CREDENTIALS_CONTENT 读取 JSON 内容
        google_creds_content = os.getenv('GOOGLE_CREDENTIALS_CONTENT')
        if google_creds_content:
            try:
                # 处理可能的转义字符
                if google_creds_content.startswith('"') and google_creds_content.endswith('"'):
                    google_creds_content = google_creds_content[1:-1]
                
                # 替换转义的引号和换行符
                google_creds_content = google_creds_content.replace('\\"', '"').replace('\\n', '\n')
                
                creds_info = json.loads(google_creds_content)
                logger.info("✅ 使用 GOOGLE_CREDENTIALS_CONTENT 环境变量")
                return Credentials.from_service_account_info(creds_info, scopes=scope)
            except json.JSONDecodeError as e:
                logger.error(f"❌ 解析 GOOGLE_CREDENTIALS_CONTENT 失败: {e}")
        
        # 方式3: 从 GOOGLE_CREDENTIALS_FILE 读取文件路径
        google_creds_file = os.getenv('GOOGLE_CREDENTIALS_FILE')
        if google_creds_file and os.path.exists(google_creds_file):
            logger.info("✅ 使用 GOOGLE_CREDENTIALS_FILE 环境变量")
            return Credentials.from_service_account_file(google_creds_file, scopes=scope)
        
        # 方式4: 兼容旧的 GOOGLE_CREDENTIALS_JSON 变量名
        google_creds_json = os.getenv('GOOGLE_CREDENTIALS_JSON')
        if google_creds_json:
            try:
                creds_info = json.loads(google_creds_json)
                logger.info("✅ 使用 GOOGLE_CREDENTIALS_JSON 环境变量")
                return Credentials.from_service_account_info(creds_info, scopes=scope)
            except json.JSONDecodeError as e:
                logger.error(f"❌ 解析 GOOGLE_CREDENTIALS_JSON 失败: {e}")
        
        # 方式5: 默认文件路径 (本地开发)
        default_paths = [
            'credentials.json',
            'google_credentials.json',
            'service_account.json'
        ]
        
        for path in default_paths:
            if os.path.exists(path):
                logger.info(f"✅ 使用本地凭证文件: {path}")
                return Credentials.from_service_account_file(path, scopes=scope)
        
        raise ValueError(
            "❌ 未找到 Google API 凭证。请设置以下任一环境变量：\n"
            "- GOOGLE_CREDENTIALS_BASE64: Base64编码的JSON凭证（推荐）\n"
            "- GOOGLE_CREDENTIALS_CONTENT: 完整的 JSON 凭证内容\n"
            "- GOOGLE_CREDENTIALS_FILE: 凭证文件路径\n"
            "- GOOGLE_CREDENTIALS_JSON: JSON 凭证字符串（兼容）\n"
            "或在项目根目录放置 credentials.json 文件"
        )
    
    def _initialize_client(self):
        """初始化 Google Sheets 客户端"""
        try:
            # 获取凭证
            creds = self._get_credentials()
            
            # 获取表格 ID - 适配你的环境变量名
            self.spreadsheet_id = os.getenv('GOOGLE_SHEET_ID')  # 注意：你用的是 GOOGLE_SHEET_ID，不是 GOOGLE_SHEETS_ID
            if not self.spreadsheet_id:
                raise ValueError("❌ 未设置 GOOGLE_SHEET_ID 环境变量")
            
            # 获取 Google Drive 文件夹 ID（可选）
            self.folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
            
            # 创建客户端
            self.client = gspread.authorize(creds)
            
            # 尝试打开表格
            try:
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                logger.info(f"✅ 成功打开表格: {self.spreadsheet.title}")
            except gspread.SpreadsheetNotFound:
                logger.error(f"❌ 找不到表格 ID: {self.spreadsheet_id}")
                logger.error("请检查：1) 表格 ID 是否正确 2) 服务账号是否有访问权限")
                raise
            
            # 确保所有工作表存在
            self._ensure_worksheets_exist()
            
            logger.info("✅ Google Sheets 客户端初始化成功")
            
        except Exception as e:
            logger.error(f"❌ Google Sheets 初始化失败: {e}")
            raise
    
    def _ensure_worksheets_exist(self):
        """确保所有必需的工作表存在"""
        try:
            existing_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            logger.info(f"📋 现有工作表: {existing_sheets}")
            
            # 工作表配置
            sheet_configs = {
                'sales': {'name': SHEET_NAMES['sales'], 'headers': SALES_HEADERS},
                'expenses': {'name': SHEET_NAMES['expenses'], 'headers': EXPENSES_HEADERS},
                'agents': {'name': SHEET_NAMES['agents'], 'headers': AGENTS_HEADERS},
                'suppliers': {'name': SHEET_NAMES['suppliers'], 'headers': SUPPLIERS_HEADERS}
            }
            
            # 创建缺失的工作表
            for sheet_key, config in sheet_configs.items():
                sheet_name = config['name']
                if sheet_name not in existing_sheets:
                    try:
                        worksheet = self.spreadsheet.add_worksheet(
                            title=sheet_name, rows=1000, cols=20
                        )
                        worksheet.append_row(config['headers'])
                        logger.info(f"✅ 创建工作表: {sheet_name}")
                    except Exception as e:
                        logger.error(f"❌ 创建工作表失败 {sheet_name}: {e}")
                else:
                    logger.info(f"📋 工作表已存在: {sheet_name}")
                    
        except Exception as e:
            logger.error(f"❌ 检查工作表失败: {e}")
    
    def get_worksheet(self, sheet_name: str):
        """获取指定工作表"""
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            logger.error(f"❌ 工作表不存在: {sheet_name}")
            return None
        except Exception as e:
            logger.error(f"❌ 获取工作表失败 {sheet_name}: {e}")
            return None
    
    def test_connection(self) -> Dict[str, Any]:
        """测试连接状态和配置信息"""
        try:
            sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            
            # 收集环境变量状态
            env_status = {
                'GOOGLE_SHEET_ID': '✅' if os.getenv('GOOGLE_SHEET_ID') else '❌',
                'GOOGLE_CREDENTIALS_CONTENT': '✅' if os.getenv('GOOGLE_CREDENTIALS_CONTENT') else '❌',
                'GOOGLE_CREDENTIALS_FILE': '✅' if os.getenv('GOOGLE_CREDENTIALS_FILE') else '❌',
                'GOOGLE_DRIVE_FOLDER_ID': '✅' if os.getenv('GOOGLE_DRIVE_FOLDER_ID') else '❌',
                'TELEGRAM_TOKEN': '✅' if os.getenv('TELEGRAM_TOKEN') else '❌',
                'SERVICE_URL': '✅' if os.getenv('SERVICE_URL') else '❌',
                'DEBUG': os.getenv('DEBUG', 'False'),
                'PORT': os.getenv('PORT', '5000')
            }
            
            return {
                'success': True,
                'spreadsheet_id': self.spreadsheet_id,
                'spreadsheet_title': self.spreadsheet.title,
                'folder_id': self.folder_id,
                'worksheets': sheets,
                'env_status': env_status,
                'message': '✅ 连接成功，所有配置正常'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'❌ 连接失败: {e}'
            }
    
    # =============================================================================
    # 销售记录操作
    # =============================================================================
    
    def add_sales_record(self, data: Dict[str, Any]) -> bool:
        """添加销售记录"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['sales'])
            if not worksheet:
                return False
            
            # 准备数据行
            row_data = [
                data.get('date', datetime.now().strftime('%Y-%m-%d')),
                data.get('person', ''),
                data.get('amount', 0),
                data.get('client_type', ''),
                data.get('commission_rate', 0),
                data.get('commission_amount', 0),
                data.get('notes', '')
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 销售记录添加成功: {data.get('amount')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加销售记录失败: {e}")
            return False
    
    def get_sales_records(self, month: Optional[str] = None) -> List[Dict]:
        """获取销售记录"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['sales'])
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            
            # 按月份过滤
            if month:
                filtered_records = []
                for record in records:
                    if record.get('日期', '').startswith(month):
                        filtered_records.append(record)
                return filtered_records
            
            return records
            
        except Exception as e:
            logger.error(f"❌ 获取销售记录失败: {e}")
            return []
    
    # =============================================================================
    # 费用记录操作
    # =============================================================================
    
    def add_expense_record(self, data: Dict[str, Any]) -> bool:
        """添加费用记录"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['expenses'])
            if not worksheet:
                return False
            
            row_data = [
                data.get('date', datetime.now().strftime('%Y-%m-%d')),
                data.get('expense_type', ''),
                data.get('supplier', ''),
                data.get('amount', 0),
                data.get('category', ''),
                data.get('notes', '')
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 费用记录添加成功: {data.get('amount')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加费用记录失败: {e}")
            return False
    
    def get_expense_records(self, month: Optional[str] = None) -> List[Dict]:
        """获取费用记录"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['expenses'])
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            
            if month:
                filtered_records = []
                for record in records:
                    if record.get('日期', '').startswith(month):
                        filtered_records.append(record)
                return filtered_records
            
            return records
            
        except Exception as e:
            logger.error(f"❌ 获取费用记录失败: {e}")
            return []
    
    # =============================================================================
    # 代理商管理
    # =============================================================================
    
    def add_agent(self, data: Dict[str, Any]) -> bool:
        """添加代理商"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['agents'])
            if not worksheet:
                return False
            
            row_data = [
                data.get('name', ''),
                data.get('contact', ''),
                data.get('phone', ''),
                data.get('email', ''),
                data.get('commission_rate', 0),
                data.get('status', '激活')
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 代理商添加成功: {data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加代理商失败: {e}")
            return False
    
    def get_agents(self, active_only: bool = True) -> List[Dict]:
        """获取代理商列表"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['agents'])
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            
            if active_only:
                return [r for r in records if r.get('状态') == '激活']
            
            return records
            
        except Exception as e:
            logger.error(f"❌ 获取代理商列表失败: {e}")
            return []
    
    # =============================================================================
    # 供应商管理
    # =============================================================================
    
    def add_supplier(self, data: Dict[str, Any]) -> bool:
        """添加供应商"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['suppliers'])
            if not worksheet:
                return False
            
            row_data = [
                data.get('name', ''),
                data.get('contact', ''),
                data.get('phone', ''),
                data.get('email', ''),
                data.get('products', ''),
                data.get('status', '激活')
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 供应商添加成功: {data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加供应商失败: {e}")
            return False
    
    def get_suppliers(self, active_only: bool = True) -> List[Dict]:
        """获取供应商列表"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['suppliers'])
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            
            if active_only:
                return [r for r in records if r.get('状态') == '激活']
            
            return records
            
        except Exception as e:
            logger.error(f"❌ 获取供应商列表失败: {e}")
            return []
    
    # =============================================================================
    # 报表生成
    # =============================================================================
    
    def generate_monthly_report(self, month: str) -> Dict[str, Any]:
        """生成月度报表"""
        try:
            # 获取销售和费用数据
            sales_records = self.get_sales_records(month)
            expense_records = self.get_expense_records(month)
            
            # 计算销售总额和佣金
            total_sales = sum(float(r.get('发票金额', 0)) for r in sales_records)
            total_commission = sum(float(r.get('佣金金额', 0)) for r in sales_records)
            
            # 计算费用总额
            total_expenses = sum(float(r.get('金额', 0)) for r in expense_records)
            
            # 按类型统计费用
            expense_by_type = {}
            for record in expense_records:
                expense_type = record.get('费用类型', '其他')
                amount = float(record.get('金额', 0))
                expense_by_type[expense_type] = expense_by_type.get(expense_type, 0) + amount
            
            # 计算净利润
            net_profit = total_sales - total_commission - total_expenses
            
            report = {
                'month': month,
                'total_sales': total_sales,
                'total_commission': total_commission,
                'total_expenses': total_expenses,
                'net_profit': net_profit,
                'sales_count': len(sales_records),
                'expense_count': len(expense_records),
                'expense_by_type': expense_by_type,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            logger.info(f"✅ 月度报表生成成功: {month}")
            return report
            
        except Exception as e:
            logger.error(f"❌ 生成月度报表失败: {e}")
            return {}

# 创建全局实例
sheets_manager = GoogleSheetsManager()
