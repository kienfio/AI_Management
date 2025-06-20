#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Sheets API 集成
数据存储和同步功能
"""

import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
import gspread
import json
from google.oauth2.service_account import Credentials
# 直接导入常量，避免循环导入
SHEET_NAMES = {
    'sales': 'Sales Records',
    'expenses': 'Expense Records', 
    'agents': 'Agents Management',
    'suppliers': 'Suppliers Management',
    'workers': 'Workers Management',
    'pic': 'Person in Charge'
}

SALES_HEADERS = ['Date', 'PIC', 'Invoice NO', 'Bill To', 'Amount', 'Status', 'Type', 'Agent Name', 'IC', 'Comm Rate', 'Comm Amount', 'Invoice PDF']
EXPENSES_HEADERS = ['Date', 'Expense Type', 'Supplier', 'Amount', 'Category', 'Notes', 'Receipt']
AGENTS_HEADERS = ['Name', 'IC', 'Phone']
SUPPLIERS_HEADERS = ['Name', 'Contact', 'Phone', 'Email', 'Products/Services', 'Status']
WORKERS_HEADERS = ['Name', 'Contact', 'Phone', 'Position', 'Status']
PICS_HEADERS = ['Name', 'Contact', 'Phone', 'Department', 'Status']

# LHDN 税务汇总表头已移除

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    """Google Sheets 管理器"""
    
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self.spreadsheet_id = None
        self._initialize_client()
    
    def _get_credentials(self) -> Credentials:
        """获取 Google API 凭证 - 支持多种方式"""
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
        
        # 方式2: 从环境变量读取 JSON 字符串
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
        
        # 方式3: 从环境变量读取文件路径
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
        
        # 方式5: 默认文件路径
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
            
            # 获取表格 ID
            self.spreadsheet_id = os.getenv('GOOGLE_SHEET_ID')
            if not self.spreadsheet_id:
                raise ValueError("❌ 未设置 GOOGLE_SHEET_ID 环境变量")
            
            # 创建客户端
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            # 确保所有工作表存在
            self._ensure_worksheets_exist()
            
            logger.info("✅ Google Sheets 客户端初始化成功")
            
        except Exception as e:
            logger.error(f"❌ Google Sheets 初始化失败: {e}")
            raise
    
    def _ensure_worksheets_exist(self):
        """确保所有必需的工作表存在"""
        existing_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
        
        # 创建缺失的工作表
        for sheet_key, sheet_name in SHEET_NAMES.items():
            if sheet_name not in existing_sheets:
                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name, rows=1000, cols=20
                )
                
                # 添加表头
                if sheet_key == 'sales':
                    worksheet.append_row(SALES_HEADERS)
                elif sheet_key == 'expenses':
                    worksheet.append_row(EXPENSES_HEADERS)
                elif sheet_key == 'agents':
                    worksheet.append_row(AGENTS_HEADERS)
                elif sheet_key == 'suppliers':
                    worksheet.append_row(SUPPLIERS_HEADERS)
                elif sheet_key == 'workers':
                    worksheet.append_row(WORKERS_HEADERS)
                elif sheet_key == 'pic':
                    worksheet.append_row(PICS_HEADERS)
                
                logger.info(f"✅ 创建工作表: {sheet_name}")
    
    def get_worksheet(self, sheet_name: str):
        """获取指定工作表"""
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except Exception as e:
            logger.error(f"❌ 获取工作表失败 {sheet_name}: {e}")
            return None
    
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
            # 将佣金率转换为百分比格式
            # 支持新旧两种键名(commission_rate和comm_rate)
            commission_rate = data.get('commission_rate', data.get('comm_rate', 0))
            commission_rate_display = f"{commission_rate * 100}%" if commission_rate else "0%"
            
            # 处理日期格式，只保留日期部分
            date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
            if ' ' in date_str:  # 如果包含时间，只取日期部分
                date_str = date_str.split(' ')[0]
            
            row_data = [
                date_str,                        # Date - 只显示日期
                data.get('person', ''),          # PIC
                '',                              # Invoice NO - 留空
                data.get('bill_to', ''),         # Bill To
                data.get('amount', 0),           # Amount
                '',                              # Status - 留空
                data.get('type', ''),            # Type
                data.get('agent_name', ''),      # Agent Name
                data.get('agent_ic', ''),        # IC
                commission_rate_display,         # Comm Rate
                data.get('commission_amount', data.get('comm_amount', 0)), # Comm Amount - 支持新旧两种键名
                data.get('invoice_pdf', '')      # Invoice PDF
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
            
            # 获取所有数据（包括表头）
            all_values = worksheet.get_all_values()
            if not all_values or len(all_values) <= 1:  # 没有数据或只有表头
                return []
            
            # 获取表头和数据
            headers = all_values[0]  # 第一行是表头
            data_rows = all_values[1:]  # 从第二行开始是数据
            
            # 处理记录
            formatted_records = []
            for row in data_rows:
                # 确保行的长度与表头一致
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                
                # 创建记录字典
                record = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        record[header] = row[i]
                    else:
                        record[header] = ''
                
                # 获取字段值
                date = record.get('Date', '')
                
                # 如果指定了月份，则过滤
                if month and not date.startswith(month):
                    continue
                
                # 构建标准化的记录
                formatted_record = {
                    'date': date,
                    'person': record.get('PIC', ''),
                    'invoice_no': record.get('Invoice NO', ''),
                    'bill_to': record.get('Bill To', ''),
                    'amount': self._parse_number(record.get('Amount', 0)),
                    'status': record.get('Status', ''),
                    'type': record.get('Type', ''),
                    'agent_name': record.get('Agent Name', ''),
                    'agent_ic': record.get('IC', ''),
                    'commission_rate': self._parse_number(record.get('Comm Rate', '').replace('%', '')) / 100 if record.get('Comm Rate', '') else 0,
                    'commission': self._parse_number(record.get('Comm Amount', 0)),
                    'invoice_pdf': record.get('Invoice PDF', '')
                }
                
                formatted_records.append(formatted_record)
            
            return formatted_records
            
        except Exception as e:
            logger.error(f"❌ 获取销售记录失败: {e}")
            return []
    
    def _parse_number(self, value) -> float:
        """将各种格式的数值转换为浮点数"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            # 移除货币符号、千位分隔符等
            clean_value = value.replace(',', '').replace('¥', '').replace('$', '').replace('€', '').replace('RM', '')
            try:
                return float(clean_value)
            except ValueError:
                pass
        return 0.0
    
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
                data.get('type', ''),
                data.get('supplier', ''),
                data.get('amount', 0),
                data.get('category', ''),
                data.get('description', ''),
                data.get('receipt', '')  # 添加收据链接字段
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
            
            # 获取所有数据（包括表头）
            all_values = worksheet.get_all_values()
            if not all_values or len(all_values) <= 1:  # 没有数据或只有表头
                return []
            
            # 获取表头和数据
            headers = all_values[0]
            data_rows = all_values[1:]
            
            # 处理记录
            formatted_records = []
            for row in data_rows:
                # 确保行的长度与表头一致
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                
                # 创建记录字典
                record = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        record[header] = row[i]
                    else:
                        record[header] = ''
                
                # 获取字段值
                date = record.get('Date', '')
                
                # 如果指定了月份，则过滤
                if month and not date.startswith(month):
                    continue
                
                # 构建标准化的记录
                formatted_record = {
                    'date': date,
                    'expense_type': record.get('Expense Type', ''),
                    'supplier': record.get('Supplier', ''),
                    'amount': self._parse_number(record.get('Amount', 0)),
                    'category': record.get('Category', ''),
                    'notes': record.get('Notes', ''),
                    'receipt': record.get('Receipt', '')  # 添加收据链接字段
                }
                
                formatted_records.append(formatted_record)
            
            return formatted_records
            
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
            
            # 确保所有字段都有默认值
            row_data = [
                data.get('name', ''),          # Name
                data.get('ic', data.get('contact', '')),  # IC
                data.get('phone', '')          # Phone
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 代理商添加成功: {data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加代理商失败: {e}")
            return False
    
    def get_agents(self, active_only: bool = False) -> List[Dict]:
        """获取代理商列表"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['agents'])
            if not worksheet:
                return []
            
            # 获取所有数据（包括表头）
            all_values = worksheet.get_all_values()
            if not all_values or len(all_values) <= 1:  # 没有数据或只有表头
                logger.warning("代理商工作表为空或只有表头")
                return []
            
            # 获取表头和数据
            headers = all_values[0]
            data_rows = all_values[1:]
            
            # 处理记录
            formatted_records = []
            for row in data_rows:
                # 确保行的长度与表头一致
                if len(row) < len(headers):
                    row.extend([''] * (len(headers) - len(row)))
                elif len(row) > len(headers):
                    row = row[:len(headers)]
                
                # 创建记录字典
                record = {}
                for i, header in enumerate(headers):
                    if i < len(row):
                        record[header] = row[i]
                    else:
                        record[header] = ''
                
                # 添加兼容字段
                if 'Name' in record:
                    record['name'] = record['Name']
                if 'IC' in record:
                    record['contact'] = record['IC']
                if 'Phone' in record:
                    record['phone'] = record['Phone']
                
                formatted_records.append(record)
            
            return formatted_records
            
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
                data.get('name', ''),          # Name
                data.get('contact', ''),       # Contact
                data.get('phone', ''),         # Phone
                data.get('email', ''),         # Email
                data.get('products', ''),      # Products/Services
                data.get('status', '激活')      # Status
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
                return [r for r in records if r.get('Status') == '激活']
            
            return records
            
        except Exception as e:
            logger.error(f"❌ 获取供应商列表失败: {e}")
            return []
    
    # =============================================================================
    # 工作人员管理
    # =============================================================================
    
    def add_worker(self, data: Dict[str, Any]) -> bool:
        """添加工作人员"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['workers'])
            if not worksheet:
                return False
            
            row_data = [
                data.get('name', ''),          # Name
                data.get('contact', ''),       # Contact
                data.get('phone', ''),         # Phone
                data.get('position', ''),      # Position
                data.get('status', '激活')      # Status
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 工作人员添加成功: {data.get('name')}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加工作人员失败: {e}")
            return False
    
    def get_workers(self, active_only: bool = True) -> List[Dict]:
        """获取工作人员列表"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['workers'])
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            
            if active_only:
                return [r for r in records if r.get('Status') == '激活']
            
            return records
            
        except Exception as e:
            logger.error(f"❌ 获取工作人员列表失败: {e}")
            return []
    
    # =============================================================================
    # 负责人管理
    # =============================================================================
    
    def add_pic(self, data: Dict[str, Any]) -> bool:
        """添加负责人"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['pic'])
            if not worksheet:
                return False
            
            # 验证姓名字段
            name = data.get('name', '')
            if not name:
                name = data.get('Name', '')
                if not name:
                    logger.error("负责人姓名不能为空")
                    return False
            
            row_data = [
                name,  # Name
                data.get('contact', data.get('Contact', '')),
                data.get('phone', data.get('Phone', '')),
                data.get('department', data.get('Department', '')),
                data.get('status', data.get('Status', '激活'))
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 负责人添加成功: {name}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 添加负责人失败: {e}")
            return False
    
    def get_pics(self, active_only: bool = True) -> List[Dict]:
        """获取负责人列表"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['pic'])
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            
            # 处理记录，确保每条记录都有'姓名'字段
            processed_records = []
            for record in records:
                # 如果记录中有'姓名'字段，直接添加
                if 'Name' in record:
                    # 添加name字段作为姓名字段的别名
                    record['name'] = record['Name']
                    processed_records.append(record)
                # 如果没有'姓名'字段但有'name'字段，添加'姓名'字段
                elif 'name' in record:
                    record['Name'] = record['name']
                    processed_records.append(record)
            
            if active_only:
                # 筛选激活状态的记录，兼容'status'字段
                active_records = []
                for r in processed_records:
                    status = r.get('Status', '')
                    if status == '激活':
                        active_records.append(r)
                return active_records
            
            return processed_records
            
        except Exception as e:
            logger.error(f"❌ 获取负责人列表失败: {e}")
            return []
    
    # =============================================================================
    # 报表生成
    # =============================================================================
    
    def generate_monthly_report(self, month: str) -> Dict[str, Any]:
        """生成月度报表"""
        try:
            # 获取销售记录和费用记录
            sales_records = self.get_sales_records(month)
            expense_records = self.get_expense_records(month)
            
            # 计算销售总额和佣金
            total_sales = sum(float(r.get('amount', 0)) for r in sales_records)
            total_commission = sum(float(r.get('commission', 0)) for r in sales_records)
            
            # 计算费用总额
            total_expenses = sum(self._parse_number(r.get('Amount', r.get('amount', 0))) for r in expense_records)
            
            # 按类型统计费用
            expense_by_type = {}
            for record in expense_records:
                expense_type = record.get('Expense Type', record.get('expense_type', '其他'))
                amount = self._parse_number(record.get('Amount', record.get('amount', 0)))
                expense_by_type[expense_type] = expense_by_type.get(expense_type, 0) + amount
            
            # 计算各种费用
            purchase_cost = expense_by_type.get('Purchasing', 0)
            utility_cost = expense_by_type.get('Billing', 0) + expense_by_type.get('Water Bill', 0) + \
                          expense_by_type.get('Electricity Bill', 0) + expense_by_type.get('WiFi Bill', 0)
            salary_cost = expense_by_type.get('Worker Salary', 0)
            other_cost = total_expenses - purchase_cost - utility_cost - salary_cost
            
            # 计算毛利和净利
            gross_profit = total_sales - total_commission
            net_profit = gross_profit - total_expenses
            
            return {
                'month': month,
                'total_sales': total_sales,
                'total_commission': total_commission,
                'gross_profit': gross_profit,
                'total_cost': total_expenses,
                'purchase_cost': purchase_cost,
                'utility_cost': utility_cost,
                'salary_cost': salary_cost,
                'other_cost': other_cost,
                'net_profit': net_profit
            }
            
        except Exception as e:
            logger.error(f"❌ 生成月度报表失败: {e}")
            # 返回空报表
            return {
                'month': month,
                'total_sales': 0,
                'total_commission': 0,
                'gross_profit': 0,
                'total_cost': 0,
                'purchase_cost': 0,
                'utility_cost': 0,
                'salary_cost': 0,
                'other_cost': 0,
                'net_profit': 0
            }

    # =============================================================================
    # 收据上传
    # =============================================================================
    
    def upload_receipt_to_drive(self, file_stream, file_name, mime_type='image/jpeg', receipt_type=None):
        """上传收据到Google Drive并返回公开链接"""
        try:
            # 使用GoogleDriveUploader上传文件
            from google_drive_uploader import drive_uploader
            
            # 如果提供了收据类型，则传递给upload_receipt方法
            if receipt_type:
                return drive_uploader.upload_receipt(file_stream, receipt_type, mime_type)
            else:
                return drive_uploader.upload_receipt(file_stream, file_name, mime_type)
        except Exception as e:
            logger.error(f"上传收据到Google Drive失败: {e}")
            return None

    # =============================================================================
    # 损益表 (P&L) 报表生成
    # =============================================================================

    def generate_pl_report(self, month: str) -> Dict[str, Any]:
        """生成月度损益表"""
        try:
            # 获取销售记录和费用记录
            sales_records = self.get_sales_records(month)
            expense_records = self.get_expense_records(month)
            
            # 计算收入
            revenue = sum(float(r.get('amount', 0)) for r in sales_records)
            
            # 计算成本
            cost_of_goods = 0
            commission_cost = sum(float(r.get('commission', 0)) for r in sales_records)
            
            # 按类型统计费用
            expense_by_type = {}
            for record in expense_records:
                expense_type = record.get('Expense Type', record.get('expense_type', '其他'))
                amount = self._parse_number(record.get('Amount', record.get('amount', 0)))
                expense_by_type[expense_type] = expense_by_type.get(expense_type, 0) + amount
            
            # 计算营业费用
            salary_expense = expense_by_type.get('Worker Salary', 0)
            utility_expense = expense_by_type.get('Billing', 0) + expense_by_type.get('Water Bill', 0) + \
                             expense_by_type.get('Electricity Bill', 0) + expense_by_type.get('WiFi Bill', 0)
            other_expense = sum(amount for expense_type, amount in expense_by_type.items() 
                               if expense_type not in ['Worker Salary', 'Billing', 'Water Bill', 'Electricity Bill', 'WiFi Bill'])
            
            # 计算总营业费用
            total_operating_expense = salary_expense + utility_expense + other_expense
            
            # 计算毛利润和净利润
            gross_profit = revenue - cost_of_goods - commission_cost
            net_profit = gross_profit - total_operating_expense
            
            # 计算利润率
            profit_margin = (net_profit / revenue * 100) if revenue > 0 else 0
            
            return {
                'period': month,
                'revenue': revenue,
                'cost_of_goods': cost_of_goods,
                'commission_cost': commission_cost,
                'gross_profit': gross_profit,
                'salary_expense': salary_expense,
                'utility_expense': utility_expense,
                'other_expense': other_expense,
                'total_operating_expense': total_operating_expense,
                'net_profit': net_profit,
                'profit_margin': profit_margin
            }
            
        except Exception as e:
            logger.error(f"❌ 生成损益表失败: {e}")
            # 返回空报表
            return {
                'period': month,
                'revenue': 0,
                'cost_of_goods': 0,
                'commission_cost': 0,
                'gross_profit': 0,
                'salary_expense': 0,
                'utility_expense': 0,
                'other_expense': 0,
                'total_operating_expense': 0,
                'net_profit': 0,
                'profit_margin': 0
            }

    def generate_yearly_pl_report(self, year: int) -> Dict[str, Any]:
        """生成年度损益表"""
        try:
            yearly_data = {
                'revenue': 0,
                'cost_of_goods': 0,
                'commission_cost': 0,
                'gross_profit': 0,
                'salary_expense': 0,
                'utility_expense': 0,
                'other_expense': 0,
                'total_operating_expense': 0,
                'net_profit': 0,
                'profit_margin': 0
            }
            
            # 累计每个月的数据
            for month in range(1, 13):
                month_str = f"{year}-{month:02d}"
                monthly_data = self.generate_pl_report(month_str)
                
                # 累加各项数据
                for key in yearly_data.keys():
                    if key != 'profit_margin':  # 利润率不需要累加
                        yearly_data[key] += monthly_data[key]
            
            # 重新计算年度利润率
            yearly_data['profit_margin'] = (yearly_data['net_profit'] / yearly_data['revenue'] * 100) if yearly_data['revenue'] > 0 else 0
            
            # 添加期间信息
            yearly_data['period'] = str(year)
            
            return yearly_data
            
        except Exception as e:
            logger.error(f"❌ 生成年度损益表失败: {e}")
            # 返回空报表
            return {
                'period': str(year),
                'revenue': 0,
                'cost_of_goods': 0,
                'commission_cost': 0,
                'gross_profit': 0,
                'salary_expense': 0,
                'utility_expense': 0,
                'other_expense': 0,
                'total_operating_expense': 0,
                'net_profit': 0,
                'profit_margin': 0
            }

    # =============================================================================
    # 报表导出功能
    # =============================================================================

    def export_sales_report(self, year: int) -> Dict[str, Any]:
        """导出销售报表到Google表格"""
        try:
            # 创建或获取销售报表工作表
            sheet_name = f"Sales Report {year}"
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
                # 如果工作表已存在，清空内容
                worksheet.clear()
            except:
                # 如果工作表不存在，创建新工作表
                worksheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
            
            # 添加表头
            headers = ['Month', 'Total Sales', 'Total Commission', 'Net Sales']
            worksheet.append_row(headers)
            
            # 按月获取销售数据
            monthly_data = []
            yearly_totals = {'sales': 0, 'commission': 0, 'net': 0}
            
            for month in range(1, 13):
                month_str = f"{year}-{month:02d}"
                # 获取月度报表数据
                report_data = self.generate_monthly_report(month_str)
                
                # 添加到月度数据列表
                monthly_data.append([
                    month_str,
                    report_data['total_sales'],
                    report_data['total_commission'],
                    report_data['gross_profit']
                ])
                
                # 累加年度总计
                yearly_totals['sales'] += report_data['total_sales']
                yearly_totals['commission'] += report_data['total_commission']
                yearly_totals['net'] += report_data['gross_profit']
            
            # 添加月度数据
            worksheet.append_rows(monthly_data)
            
            # 添加年度总计
            worksheet.append_row([])  # 空行
            worksheet.append_row([
                f"Total {year}",
                yearly_totals['sales'],
                yearly_totals['commission'],
                yearly_totals['net']
            ])
            
            # 格式化数字列为货币格式
            worksheet.format('B2:D15', {'numberFormat': {'type': 'CURRENCY', 'pattern': '"RM"#,##0.00'}})
            
            logger.info(f"✅ 销售报表导出成功: {sheet_name}")
            
            return {
                'sheet_name': sheet_name,
                'sheet_url': f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={worksheet.id}",
                'year': year
            }
            
        except Exception as e:
            logger.error(f"❌ 导出销售报表失败: {e}")
            return None

    def export_expenses_report(self, year: int) -> Dict[str, Any]:
        """导出支出报表到Google表格"""
        try:
            # 创建或获取支出报表工作表
            sheet_name = f"Expenses Report {year}"
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
                # 如果工作表已存在，清空内容
                worksheet.clear()
            except:
                # 如果工作表不存在，创建新工作表
                worksheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
            
            # 添加表头
            headers = ['Month', 'Purchasing', 'Utilities', 'Salaries', 'Other', 'Total Expenses']
            worksheet.append_row(headers)
            
            # 按月获取支出数据
            monthly_data = []
            yearly_totals = {'purchasing': 0, 'utilities': 0, 'salaries': 0, 'other': 0, 'total': 0}
            
            for month in range(1, 13):
                month_str = f"{year}-{month:02d}"
                # 获取月度报表数据
                report_data = self.generate_monthly_report(month_str)
                
                # 添加到月度数据列表
                monthly_data.append([
                    month_str,
                    report_data['purchase_cost'],
                    report_data['utility_cost'],
                    report_data['salary_cost'],
                    report_data['other_cost'],
                    report_data['total_cost']
                ])
                
                # 累加年度总计
                yearly_totals['purchasing'] += report_data['purchase_cost']
                yearly_totals['utilities'] += report_data['utility_cost']
                yearly_totals['salaries'] += report_data['salary_cost']
                yearly_totals['other'] += report_data['other_cost']
                yearly_totals['total'] += report_data['total_cost']
            
            # 添加月度数据
            worksheet.append_rows(monthly_data)
            
            # 添加年度总计
            worksheet.append_row([])  # 空行
            worksheet.append_row([
                f"Total {year}",
                yearly_totals['purchasing'],
                yearly_totals['utilities'],
                yearly_totals['salaries'],
                yearly_totals['other'],
                yearly_totals['total']
            ])
            
            # 格式化数字列为货币格式
            worksheet.format('B2:F15', {'numberFormat': {'type': 'CURRENCY', 'pattern': '"RM"#,##0.00'}})
            
            logger.info(f"✅ 支出报表导出成功: {sheet_name}")
            
            return {
                'sheet_name': sheet_name,
                'sheet_url': f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={worksheet.id}",
                'year': year
            }
            
        except Exception as e:
            logger.error(f"❌ 导出支出报表失败: {e}")
            return None

    def export_pl_report(self, year: int) -> Dict[str, Any]:
        """导出损益表到Google表格"""
        try:
            # 创建或获取损益表工作表
            sheet_name = f"P&L Report {year}"
            try:
                worksheet = self.spreadsheet.worksheet(sheet_name)
                # 如果工作表已存在，清空内容
                worksheet.clear()
            except:
                # 如果工作表不存在，创建新工作表
                worksheet = self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
            
            # 添加表头
            headers = ['Period', 'Revenue', 'Cost of Goods', 'Commission', 'Gross Profit', 
                      'Salary Expense', 'Utility Expense', 'Other Expense', 'Total Operating Expense', 
                      'Net Profit', 'Profit Margin (%)']
            worksheet.append_row(headers)
            
            # 按月获取损益表数据
            monthly_data = []
            
            for month in range(1, 13):
                month_str = f"{year}-{month:02d}"
                # 获取月度损益表数据
                pl_data = self.generate_pl_report(month_str)
                
                # 添加到月度数据列表
                monthly_data.append([
                    pl_data['period'],
                    pl_data['revenue'],
                    pl_data['cost_of_goods'],
                    pl_data['commission_cost'],
                    pl_data['gross_profit'],
                    pl_data['salary_expense'],
                    pl_data['utility_expense'],
                    pl_data['other_expense'],
                    pl_data['total_operating_expense'],
                    pl_data['net_profit'],
                    f"{pl_data['profit_margin']:.1f}%"
                ])
            
            # 添加月度数据
            worksheet.append_rows(monthly_data)
            
            # 添加年度总计
            worksheet.append_row([])  # 空行
            
            # 获取年度损益表数据
            yearly_data = self.generate_yearly_pl_report(year)
            
            worksheet.append_row([
                f"Total {year}",
                yearly_data['revenue'],
                yearly_data['cost_of_goods'],
                yearly_data['commission_cost'],
                yearly_data['gross_profit'],
                yearly_data['salary_expense'],
                yearly_data['utility_expense'],
                yearly_data['other_expense'],
                yearly_data['total_operating_expense'],
                yearly_data['net_profit'],
                f"{yearly_data['profit_margin']:.1f}%"
            ])
            
            # 格式化数字列为货币格式
            worksheet.format('B2:J14', {'numberFormat': {'type': 'CURRENCY', 'pattern': '"RM"#,##0.00'}})
            
            logger.info(f"✅ 损益表导出成功: {sheet_name}")
            
            return {
                'sheet_name': sheet_name,
                'sheet_url': f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={worksheet.id}",
                'year': year
            }
            
        except Exception as e:
            logger.error(f"❌ 导出损益表失败: {e}")
            return None



# 创建全局实例
sheets_manager = GoogleSheetsManager()
