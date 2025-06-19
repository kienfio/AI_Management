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
    'pic': 'Person in Charge',
    # 新增LHDN报表相关工作表
    'monthly_pnl': 'Monthly P&L',
    'salary_summary': 'Salary Summary',
    'tax_summary': 'LHDN Tax Summary'
}

SALES_HEADERS = ['Date', 'PIC', 'Invoice NO', 'Bill To', 'Amount', 'Status', 'Type', 'Agent Name', 'IC', 'Comm Rate', 'Comm Amount', 'Invoice PDF']
EXPENSES_HEADERS = ['Date', 'Expense Type', 'Supplier', 'Amount', 'Category', 'Notes', 'Receipt']
AGENTS_HEADERS = ['Name', 'IC', 'Phone']
SUPPLIERS_HEADERS = ['Name', 'Contact', 'Phone', 'Email', 'Products/Services', 'Status']
WORKERS_HEADERS = ['Name', 'Contact', 'Phone', 'Position', 'Status']
PICS_HEADERS = ['Name', 'Contact', 'Phone', 'Department', 'Status']

# 新增LHDN报表相关表头
MONTHLY_PNL_HEADERS = ['Month', 'Sales Revenue', 'Commission', 'Gross Profit', 'Expenses', 'Depreciation', 'Own Salary/Allowance', 'Entertainment', 'Gifts', 'Penalties/Fines', 'Other Expenses', 'Total Expenses', 'Net Profit', 'Notes']
SALARY_SUMMARY_HEADERS = ['Month', 'Worker Name', 'Basic Salary', 'Allowance', 'Overtime', 'EPF Employee', 'EPF Employer', 'SOCSO Employee', 'SOCSO Employer', 'Net Salary', 'Total Employer Cost']
TAX_SUMMARY_HEADERS = ['Year', 'Total Revenue', 'Business Expenses', 'Depreciation', 'Capital Allowances', 'Business Loss C/F', 'Taxable Business Income', 'Updated Date']

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
                elif sheet_key == 'monthly_pnl':
                    worksheet.append_row(MONTHLY_PNL_HEADERS)
                elif sheet_key == 'salary_summary':
                    worksheet.append_row(SALARY_SUMMARY_HEADERS)
                elif sheet_key == 'tax_summary':
                    worksheet.append_row(TAX_SUMMARY_HEADERS)
                
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
    # LHDN 报表生成 - 税务相关报表
    # =============================================================================
    
    def generate_yearly_report(self, year=None) -> Dict[str, Any]:
        """生成年度汇总报表"""
        if year is None:
            year = datetime.now().year
        
        try:
            # 构建月份列表
            months = []
            for month in range(1, 13):
                month_str = f"{year}-{month:02d}"
                months.append(month_str)
            
            # 获取每月报表并汇总
            total_sales = 0
            total_commission = 0
            total_expenses = 0
            total_purchase = 0
            total_utility = 0
            total_salary = 0
            total_other = 0
            
            for month in months:
                report = self.generate_monthly_report(month)
                total_sales += report['total_sales']
                total_commission += report['total_commission']
                total_expenses += report['total_cost']
                total_purchase += report['purchase_cost']
                total_utility += report['utility_cost']
                total_salary += report['salary_cost']
                total_other += report['other_cost']
            
            # 计算综合指标
            gross_profit = total_sales - total_commission
            net_profit = gross_profit - total_expenses
            
            # 计算月平均值
            months_count = len(months)
            avg_monthly_income = total_sales / months_count if months_count > 0 else 0
            avg_monthly_cost = total_expenses / months_count if months_count > 0 else 0
            
            return {
                'year': year,
                'total_sales': total_sales,
                'total_commission': total_commission,
                'gross_profit': gross_profit,
                'total_cost': total_expenses,
                'purchase_cost': total_purchase,
                'utility_cost': total_utility,
                'salary_cost': total_salary,
                'other_cost': total_other,
                'net_profit': net_profit,
                'avg_monthly_income': avg_monthly_income,
                'avg_monthly_cost': avg_monthly_cost
            }
            
        except Exception as e:
            logger.error(f"❌ 生成年度报表失败: {e}")
            # 返回空报表
            return {
                'year': year,
                'total_sales': 0,
                'total_commission': 0,
                'gross_profit': 0,
                'total_cost': 0,
                'purchase_cost': 0,
                'utility_cost': 0,
                'salary_cost': 0,
                'other_cost': 0,
                'net_profit': 0,
                'avg_monthly_income': 0,
                'avg_monthly_cost': 0
            }
    
    def generate_pnl_report(self, year=None) -> Dict[str, Any]:
        """
        生成P&L损益表 (符合LHDN Working Sheets格式)
        
        按照LHDN要求，将支出分类为：
        - 折旧(Depreciation)
        - 自身薪资/津贴/奖金(Own salary/allowance/bonus)
        - 娱乐费用(Entertainment)
        - 礼品(Gifts)
        - 罚款(Penalties/fines)
        - 其他费用(Other expenses)
        """
        if year is None:
            year = datetime.now().year
            
        try:
            # 获取全年报表基础数据
            yearly_data = self.generate_yearly_report(year)
            
            # 获取全年所有费用记录以进行详细分类
            expense_records = []
            for month in range(1, 13):
                month_str = f"{year}-{month:02d}"
                monthly_expenses = self.get_expense_records(month_str)
                expense_records.extend(monthly_expenses)
            
            # 按LHDN分类统计费用
            # 1. 初始化所有类别
            lhdn_expenses = {
                'depreciation': 0,              # 折旧
                'own_salary_allowance': 0,      # 自身薪资/津贴
                'entertainment': 0,             # 娱乐费用
                'gifts': 0,                     # 礼品
                'penalties_fines': 0,           # 罚款
                'other_expenses': 0             # 其他费用
            }
            
            # 2. 分析每条费用记录并分类
            for record in expense_records:
                expense_type = record.get('Expense Type', record.get('expense_type', ''))
                category = record.get('Category', record.get('category', ''))
                description = record.get('Notes', record.get('description', ''))
                amount = self._parse_number(record.get('Amount', record.get('amount', 0)))
                
                # 基于类型、类别和描述进行分类
                if expense_type == 'Depreciation' or 'depreciation' in description.lower():
                    lhdn_expenses['depreciation'] += amount
                elif expense_type == 'Own Salary' or 'salary' in description.lower() and 'owner' in description.lower():
                    lhdn_expenses['own_salary_allowance'] += amount
                elif 'entertainment' in description.lower() or 'entertain' in category.lower():
                    lhdn_expenses['entertainment'] += amount
                elif 'gift' in description.lower() or 'gift' in category.lower():
                    lhdn_expenses['gifts'] += amount
                elif 'penalty' in description.lower() or 'fine' in description.lower() or 'summon' in description.lower():
                    lhdn_expenses['penalties_fines'] += amount
                else:
                    # 其他所有费用归为其他类别
                    lhdn_expenses['other_expenses'] += amount
            
            # 合并结果到年度报表
            result = {
                'year': year,
                'sales_revenue': yearly_data['total_sales'],
                'commission': yearly_data['total_commission'],
                'gross_profit': yearly_data['gross_profit'],
                'total_expenses': yearly_data['total_cost'],
                'depreciation': lhdn_expenses['depreciation'],
                'own_salary_allowance': lhdn_expenses['own_salary_allowance'],
                'entertainment': lhdn_expenses['entertainment'],
                'gifts': lhdn_expenses['gifts'],
                'penalties_fines': lhdn_expenses['penalties_fines'],
                'other_expenses': lhdn_expenses['other_expenses'],
                'net_profit': yearly_data['net_profit']
            }
            
            # 保存到Google Sheets
            self._save_pnl_report(result)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 生成P&L损益表失败: {e}")
            # 返回空报表
            return {
                'year': year,
                'sales_revenue': 0,
                'commission': 0,
                'gross_profit': 0,
                'total_expenses': 0,
                'depreciation': 0,
                'own_salary_allowance': 0,
                'entertainment': 0,
                'gifts': 0,
                'penalties_fines': 0,
                'other_expenses': 0,
                'net_profit': 0
            }
    
    def _save_pnl_report(self, pnl_data: Dict[str, Any]) -> bool:
        """将P&L报表数据保存到Google Sheets"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['monthly_pnl'])
            if not worksheet:
                return False
            
            # 添加报表数据
            month_name = datetime.now().strftime('%Y-%m')
            row_data = [
                f"{pnl_data['year']}年度",  # 月份/年度
                pnl_data['sales_revenue'],   # 销售收入
                pnl_data['commission'],      # 佣金
                pnl_data['gross_profit'],    # 毛利润
                pnl_data['total_expenses'],  # 总支出
                pnl_data['depreciation'],    # 折旧
                pnl_data['own_salary_allowance'],  # 自身薪资/津贴
                pnl_data['entertainment'],   # 娱乐费用
                pnl_data['gifts'],           # 礼品
                pnl_data['penalties_fines'], # 罚款
                pnl_data['other_expenses'],  # 其他费用
                pnl_data['total_expenses'],  # 总支出(重复)
                pnl_data['net_profit'],      # 净利润
                f"Generated on {datetime.now().strftime('%Y-%m-%d')}"  # 备注
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ P&L报表数据已保存到Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存P&L报表失败: {e}")
            return False
    
    def generate_salary_summary(self, year=None, month=None) -> List[Dict[str, Any]]:
        """
        生成员工薪资汇总报表
        
        Args:
            year: 年份，如果为None则使用当前年份
            month: 月份，如果为None则汇总整年
        
        Returns:
            List[Dict]: 薪资汇总数据列表，每个工人一条记录
        """
        if year is None:
            year = datetime.now().year
            
        try:
            # 获取所有工人工资记录
            expense_records = []
            
            if month is None:
                # 获取全年记录
                for m in range(1, 13):
                    month_str = f"{year}-{m:02d}"
                    monthly_expenses = self.get_expense_records(month_str)
                    # 只过滤工资记录
                    salary_records = [r for r in monthly_expenses if r.get('Expense Type', r.get('expense_type', '')) == 'Worker Salary']
                    expense_records.extend(salary_records)
                period = f"{year}年度"
            else:
                # 获取指定月份记录
                month_str = f"{year}-{month:02d}" if isinstance(month, int) else month
                monthly_expenses = self.get_expense_records(month_str)
                # 只过滤工资记录
                salary_records = [r for r in monthly_expenses if r.get('Expense Type', r.get('expense_type', '')) == 'Worker Salary']
                expense_records.extend(salary_records)
                period = month_str
            
            # 按工人分组汇总
            worker_summary = {}
            
            for record in expense_records:
                worker_name = record.get('Supplier', record.get('supplier', ''))
                if not worker_name:
                    continue
                
                # 获取薪资详情
                amount = self._parse_number(record.get('Amount', record.get('amount', 0)))
                
                # 提取EPF和SOCSO相关数据
                basic_salary = self._parse_number(record.get('basic_salary', 0))
                allowance = self._parse_number(record.get('allowance', 0))
                overtime = self._parse_number(record.get('overtime', 0))
                epf_employee = self._parse_number(record.get('epf_employee', 0))
                epf_employer = self._parse_number(record.get('epf_employer', 0))
                socso_employee = self._parse_number(record.get('socso_employee', 0))
                socso_employer = self._parse_number(record.get('socso_employer', 0))
                net_salary = self._parse_number(record.get('net_salary', amount))  # 如果没有net_salary字段，使用amount
                total_cost = self._parse_number(record.get('total_cost', amount + epf_employer + socso_employer))
                
                # 初始化工人数据
                if worker_name not in worker_summary:
                    worker_summary[worker_name] = {
                        'worker_name': worker_name,
                        'basic_salary': 0,
                        'allowance': 0,
                        'overtime': 0,
                        'epf_employee': 0,
                        'epf_employer': 0,
                        'socso_employee': 0,
                        'socso_employer': 0,
                        'net_salary': 0,
                        'total_employer_cost': 0
                    }
                
                # 累加数据
                worker_summary[worker_name]['basic_salary'] += basic_salary
                worker_summary[worker_name]['allowance'] += allowance
                worker_summary[worker_name]['overtime'] += overtime
                worker_summary[worker_name]['epf_employee'] += epf_employee
                worker_summary[worker_name]['epf_employer'] += epf_employer
                worker_summary[worker_name]['socso_employee'] += socso_employee
                worker_summary[worker_name]['socso_employer'] += socso_employer
                worker_summary[worker_name]['net_salary'] += net_salary
                worker_summary[worker_name]['total_employer_cost'] += total_cost
            
            # 转换为列表
            result = []
            for worker_name, summary in worker_summary.items():
                # 添加期间信息
                summary['period'] = period
                result.append(summary)
            
            # 保存到Google Sheets
            self._save_salary_summary(result, period)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 生成员工薪资汇总失败: {e}")
            return []
    
    def _save_salary_summary(self, salary_data: List[Dict[str, Any]], period: str) -> bool:
        """将员工薪资汇总数据保存到Google Sheets"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['salary_summary'])
            if not worksheet:
                return False
            
            # 添加每个工人的数据
            for worker_data in salary_data:
                row_data = [
                    period,                              # 期间(月份或年度)
                    worker_data['worker_name'],          # 工人姓名
                    worker_data['basic_salary'],         # 基本工资
                    worker_data['allowance'],            # 津贴
                    worker_data['overtime'],             # 加班费
                    worker_data['epf_employee'],         # EPF员工缴费
                    worker_data['epf_employer'],         # EPF雇主缴费
                    worker_data['socso_employee'],       # SOCSO员工缴费
                    worker_data['socso_employer'],       # SOCSO雇主缴费
                    worker_data['net_salary'],           # 净工资
                    worker_data['total_employer_cost']   # 雇主总成本
                ]
                
                worksheet.append_row(row_data)
            
            logger.info(f"✅ 员工薪资汇总数据已保存到Google Sheets，期间: {period}")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存员工薪资汇总失败: {e}")
            return False
    
    def generate_tax_summary(self, year=None) -> Dict[str, Any]:
        """
        生成LHDN税务摘要报表
        
        按照LHDN Form B要求，包含：
        - 总收入（总营业额）
        - 总可扣除费用（按LHDN分类）
        - 资本津贴与扣减
        - 净课税利润（应课税收入）
        """
        if year is None:
            year = datetime.now().year
            
        try:
            # 获取P&L报表数据作为基础
            pnl_data = self.generate_pnl_report(year)
            
            # 计算总可扣除费用
            # 注意：根据LHDN规定，某些支出可能不可完全扣除
            business_expenses = pnl_data['total_expenses']
            
            # 折旧不能直接扣除，而是通过资本津贴扣除
            # 按50%资本津贴率计算（简化处理）
            depreciation = pnl_data['depreciation']
            capital_allowances = depreciation * 0.5  # 资本津贴通常是设备折旧的50%
            
            # 计算应课税收入
            taxable_income = pnl_data['sales_revenue'] - business_expenses + depreciation - capital_allowances
            
            # 如果有前期亏损结转，可以抵消部分应课税收入
            business_loss_cf = 0  # 假设没有前期亏损结转
            
            if taxable_income < 0:
                # 如果当年亏损，可以结转至下一年
                business_loss_cf = abs(taxable_income)
                taxable_income = 0
            
            # 创建税务摘要
            tax_summary = {
                'year': year,
                'total_revenue': pnl_data['sales_revenue'],
                'business_expenses': business_expenses,
                'depreciation': depreciation,
                'capital_allowances': capital_allowances,
                'business_loss_cf': business_loss_cf,
                'taxable_business_income': taxable_income,
                'updated_date': datetime.now().strftime('%Y-%m-%d')
            }
            
            # 保存到Google Sheets
            self._save_tax_summary(tax_summary)
            
            return tax_summary
            
        except Exception as e:
            logger.error(f"❌ 生成税务摘要报表失败: {e}")
            # 返回空报表
            return {
                'year': year,
                'total_revenue': 0,
                'business_expenses': 0,
                'depreciation': 0,
                'capital_allowances': 0,
                'business_loss_cf': 0,
                'taxable_business_income': 0,
                'updated_date': datetime.now().strftime('%Y-%m-%d')
            }
    
    def _save_tax_summary(self, tax_data: Dict[str, Any]) -> bool:
        """将税务摘要数据保存到Google Sheets"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['tax_summary'])
            if not worksheet:
                return False
            
            # 添加税务摘要数据
            row_data = [
                f"{tax_data['year']}年度",       # 年度
                tax_data['total_revenue'],        # 总收入
                tax_data['business_expenses'],    # 业务支出
                tax_data['depreciation'],         # 折旧
                tax_data['capital_allowances'],   # 资本津贴
                tax_data['business_loss_cf'],     # 亏损结转
                tax_data['taxable_business_income'], # 应课税收入
                tax_data['updated_date']          # 更新日期
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 税务摘要数据已保存到Google Sheets")
            return True
            
        except Exception as e:
            logger.error(f"❌ 保存税务摘要失败: {e}")
            return False
    
    def export_all_reports(self, year=None) -> bool:
        """
        导出所有报表到Google Sheets
        
        生成并同步更新P&L损益表、员工薪资汇总和税务摘要
        """
        if year is None:
            year = datetime.now().year
            
        try:
            # 生成并保存所有报表
            self.generate_pnl_report(year)
            self.generate_salary_summary(year)
            self.generate_tax_summary(year)
            
            logger.info(f"✅ 所有报表已成功导出到Google Sheets")
            return True
        except Exception as e:
            logger.error(f"❌ 导出报表失败: {e}")
            return False

# 创建全局实例
sheets_manager = GoogleSheetsManager()
