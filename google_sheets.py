#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Sheets API 集成
数据存储和同步功能
"""

import logging
import os
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any, Tuple, Union
import gspread
import json
from google.oauth2.service_account import Credentials
import base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import random
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

# 添加重试装饰器
def retry_on_quota_exceeded(max_retries=3, initial_delay=5, backoff_factor=2):
    """装饰器：在配额超限时进行重试
    
    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟时间（秒）
        backoff_factor: 退避因子，每次重试后延迟时间会乘以这个因子
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    if attempt > 0:
                        logger = logging.getLogger(__name__)
                        logger.info(f"第 {attempt} 次重试 {func.__name__}...")
                    
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    last_exception = e
                    error_message = str(e).lower()
                    
                    # 检查是否是配额超限错误
                    if "quota exceeded" in error_message or "429" in error_message:
                        if attempt < max_retries:
                            logger = logging.getLogger(__name__)
                            logger.warning(f"API配额超限，等待 {delay} 秒后重试...")
                            
                            # 添加一些随机性避免所有请求同时重试
                            jitter = random.uniform(0.8, 1.2)
                            time.sleep(delay * jitter)
                            
                            # 增加下一次重试的延迟
                            delay *= backoff_factor
                        else:
                            logger.error(f"达到最大重试次数 ({max_retries})，放弃操作")
                            raise
                    else:
                        # 如果不是配额错误，直接抛出
                        raise
            
            # 如果所有重试都失败，抛出最后捕获的异常
            raise last_exception
        
        return wrapper
    
    return decorator

class GoogleSheetsManager:
    """Google Sheets 管理器"""
    
    def __init__(self):
        """初始化 Google Sheets 管理器"""
        self.creds = None
        self.client = None
        self.spreadsheet = None
        self.spreadsheet_id = os.environ.get('GOOGLE_SHEET_ID')
        self.drive_service = None
        
        # 初始化API请求限制
        self.request_count = 0
        self.request_reset_time = datetime.now()
        self.max_requests_per_minute = 60  # Google Sheets API 默认限制
        
        # 初始化
        self._get_credentials()
        self._initialize_client()
        self._ensure_worksheets_exist()
    
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
    
    # 添加请求限制方法
    def _limit_request_rate(self):
        """限制API请求速率，避免超过配额"""
        now = datetime.now()
        
        # 如果已经过了一分钟，重置计数器
        if (now - self.request_reset_time).total_seconds() > 60:
            self.request_count = 0
            self.request_reset_time = now
            return
        
        # 如果接近限制，等待适当的时间
        if self.request_count >= self.max_requests_per_minute - 5:  # 留一些余量
            wait_time = 60 - (now - self.request_reset_time).total_seconds()
            if wait_time > 0:
                logger = logging.getLogger(__name__)
                logger.info(f"接近API请求限制，等待 {wait_time:.1f} 秒...")
                time.sleep(wait_time + 1)  # 额外等待1秒以确保安全
                self.request_count = 0
                self.request_reset_time = datetime.now()
        
        # 增加请求计数
        self.request_count += 1
    
    @retry_on_quota_exceeded()
    def get_worksheet(self, sheet_name: str):
        """获取指定名称的工作表
        
        Args:
            sheet_name: 工作表名称
            
        Returns:
            工作表对象，如果不存在则返回None
        """
        self._limit_request_rate()
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except Exception as e:
            logger = logging.getLogger(__name__)
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
    
    @retry_on_quota_exceeded()
    def get_sales_records(self, month: Optional[str] = None) -> List[Dict]:
        """获取销售记录
        
        Args:
            month: 可选的月份筛选，格式为 'YYYY-MM'
            
        Returns:
            销售记录列表
        """
        self._limit_request_rate()
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
    
    @retry_on_quota_exceeded()
    def get_expense_records(self, month: Optional[str] = None) -> List[Dict]:
        """获取支出记录
        
        Args:
            month: 可选的月份筛选，格式为 'YYYY-MM'
            
        Returns:
            支出记录列表
        """
        self._limit_request_rate()
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
            logger.error(f"❌ 获取支出记录失败: {e}")
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

    # =============================================================================
    # 归档和年度管理功能
    # =============================================================================
    
    def archive_yearly_data(self, year: int) -> Dict[str, Any]:
        """归档特定年份的数据
        
        将特定年份的销售和支出数据从主记录表复制到专门的归档表格
        并对数据进行整理归纳
        
        Args:
            year: 要归档的年份
            
        Returns:
            包含归档结果的字典
        """
        try:
            logger = logging.getLogger(__name__)
            logger.info(f"开始归档{year}年数据...")
            result = {
                'archived_sales': 0,
                'archived_expenses': 0,
                'archive_sheets': []
            }
            
            # 创建年度归档工作表（如果不存在）
            archive_sheet_name = f"Data Archive {year}"
            try:
                archive_sheet = self.spreadsheet.worksheet(archive_sheet_name)
                logger.info(f"归档表已存在: {archive_sheet_name}")
            except:
                archive_sheet = self.spreadsheet.add_worksheet(
                    title=archive_sheet_name, rows=5000, cols=20
                )
                logger.info(f"创建归档表: {archive_sheet_name}")
                
            result['archive_sheets'].append(archive_sheet_name)
            
            # 1. 归档销售数据
            sales_archived = self._archive_sales_data(year, archive_sheet)
            result['archived_sales'] = sales_archived
            
            # 2. 归档支出数据
            expenses_archived = self._archive_expense_data(year, archive_sheet)
            result['archived_expenses'] = expenses_archived
            
            # 3. 创建归档报表索引
            index_sheet_name = f"Archives {year}"
            try:
                index_sheet = self.spreadsheet.worksheet(index_sheet_name)
                logger.info(f"归档索引表已存在: {index_sheet_name}")
            except:
                index_sheet = self.spreadsheet.add_worksheet(
                    title=index_sheet_name, rows=100, cols=10
                )
                logger.info(f"创建归档索引表: {index_sheet_name}")
                
                # 添加索引表标题和说明
                index_sheet.update('A1', f"{year}年度数据归档")
                index_sheet.update('A2', f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                index_sheet.update('A4', "此工作表包含归档报表的索引和链接:")
                
                # 添加报表链接
                reports = [
                    (f"销售报表 {year}", f"Sales Report {year}"),
                    (f"支出报表 {year}", f"Expenses Report {year}"),
                    (f"损益表 {year}", f"P&L Report {year}"),
                    (f"数据归档 {year}", f"Data Archive {year}")
                ]
                
                row = 6
                for report_name, sheet_name in reports:
                    try:
                        sheet = self.spreadsheet.worksheet(sheet_name)
                        sheet_url = f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit#gid={sheet.id}"
                        
                        # 添加报表链接
                        index_sheet.update(f'A{row}', report_name)
                        index_sheet.update(f'B{row}', f'=HYPERLINK("{sheet_url}","点击查看")')
                        row += 1
                    except Exception as e:
                        logger.warning(f"无法添加'{sheet_name}'的链接: {e}")
                
            result['archive_sheets'].append(index_sheet_name)
            
            logger.info(f"✅ {year}年数据归档完成: 销售记录 {sales_archived} 条, 支出记录 {expenses_archived} 条")
            return result
            
        except Exception as e:
            logger.error(f"❌ 归档{year}年数据失败: {e}")
            return None
    
    def _archive_sales_data(self, year: int, archive_sheet) -> int:
        """归档销售数据到指定工作表"""
        try:
            logger = logging.getLogger(__name__)
            # 获取销售记录工作表
            sales_sheet = self.get_worksheet(SHEET_NAMES['sales'])
            if not sales_sheet:
                logger.error("无法获取销售记录工作表")
                return 0
            
            # 获取所有销售数据
            all_sales = sales_sheet.get_all_values()
            if len(all_sales) <= 1:  # 没有数据或只有表头
                logger.warning("销售记录工作表为空或只有表头")
                return 0
            
            # 获取表头和数据
            headers = all_sales[0]
            
            # 筛选出特定年份的数据
            year_str = str(year)
            year_data = []
            archived_count = 0
            
            for row in all_sales[1:]:
                if row and len(row) > 0 and row[0].startswith(year_str):  # 假设第一列是日期列
                    # 确保行数据长度与表头一致
                    if len(row) < len(headers):
                        # 如果行数据不足，填充空字符串
                        row = row + [""] * (len(headers) - len(row))
                    elif len(row) > len(headers):
                        # 如果行数据过长，截断
                        row = row[:len(headers)]
                    year_data.append(row)
                    archived_count += 1
            
            # 将数据写入归档表
            if year_data:
                try:
                    # 记录当前最大行数
                    current_values = archive_sheet.get_all_values()
                    current_row = len(current_values) + 2
                    
                    # 添加销售数据标题
                    archive_sheet.update(f'A{current_row}', f"{year}年销售记录归档")
                    archive_sheet.update(f'A{current_row+1}', f"共{len(year_data)}条记录")
                    
                    # 添加表头
                    header_row = current_row + 3
                    
                    # 确定表头范围
                    max_col = min(len(headers), 26)  # 限制最大列数为26（A-Z）
                    col_range = chr(ord('A') + max_col - 1)
                    
                    # 更新表头（确保不超出范围）
                    truncated_headers = headers[:max_col]
                    archive_sheet.update(f'A{header_row}:{col_range}{header_row}', [truncated_headers])
                    
                    # 添加数据（确保不超出范围）
                    if year_data:
                        # 截断数据以匹配表头长度
                        truncated_data = [row[:max_col] for row in year_data]
                        
                        data_start_row = header_row + 1
                        data_end_row = data_start_row + len(truncated_data) - 1
                        
                        # 分批次更新数据，避免一次性更新过多
                        batch_size = 100
                        for i in range(0, len(truncated_data), batch_size):
                            batch_end = min(i + batch_size, len(truncated_data))
                            batch_data = truncated_data[i:batch_end]
                            batch_start_row = data_start_row + i
                            batch_end_row = batch_start_row + len(batch_data) - 1
                            
                            # 更新数据
                            archive_sheet.update(f'A{batch_start_row}:{col_range}{batch_end_row}', batch_data)
                            logger.info(f"已更新第{batch_start_row}-{batch_end_row}行数据")
                    
                    # 美化表格
                    try:
                        archive_sheet.format(f'A{current_row}:A{current_row+1}', {
                            'textFormat': {'fontSize': 14, 'bold': True}
                        })
                        archive_sheet.format(f'A{header_row}:{col_range}{header_row}', {
                            'textFormat': {'bold': True},
                            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                        })
                    except Exception as format_err:
                        logger.warning(f"表格美化失败（非关键错误）: {format_err}")
                    
                    logger.info(f"✅ 已归档{len(year_data)}条{year}年销售记录")
                except Exception as update_err:
                    logger.error(f"更新归档表时出错: {update_err}")
                    # 尝试使用更简单的方法更新
                    try:
                        logger.info("尝试使用替代方法更新数据...")
                        # 简单地将数据附加到工作表末尾
                        archive_sheet.append_rows([
                            [f"{year}年销售记录归档"],
                            [f"共{len(year_data)}条记录"],
                            [],
                            headers,
                            *year_data
                        ])
                        logger.info("使用替代方法更新成功")
                    except Exception as alt_err:
                        logger.error(f"替代更新方法也失败: {alt_err}")
                        return 0
            else:
                logger.info(f"没有找到{year}年的销售记录")
            
            return archived_count
            
        except Exception as e:
            logger.error(f"❌ 归档{year}年销售数据失败: {e}")
            return 0
    
    def _archive_expense_data(self, year: int, archive_sheet) -> int:
        """归档支出数据到指定工作表"""
        try:
            logger = logging.getLogger(__name__)
            # 获取支出记录工作表
            expense_sheet = self.get_worksheet(SHEET_NAMES['expenses'])
            if not expense_sheet:
                logger.error("无法获取支出记录工作表")
                return 0
            
            # 获取所有支出数据
            all_expenses = expense_sheet.get_all_values()
            if len(all_expenses) <= 1:  # 没有数据或只有表头
                logger.warning("支出记录工作表为空或只有表头")
                return 0
            
            # 获取表头和数据
            headers = all_expenses[0]
            
            # 筛选出特定年份的数据
            year_str = str(year)
            year_data = []
            archived_count = 0
            
            for row in all_expenses[1:]:
                if row and len(row) > 0 and row[0].startswith(year_str):  # 假设第一列是日期列
                    # 确保行数据长度与表头一致
                    if len(row) < len(headers):
                        # 如果行数据不足，填充空字符串
                        row = row + [""] * (len(headers) - len(row))
                    elif len(row) > len(headers):
                        # 如果行数据过长，截断
                        row = row[:len(headers)]
                    year_data.append(row)
                    archived_count += 1
            
            # 将数据写入归档表
            if year_data:
                try:
                    # 找到插入位置（在销售记录之后）
                    all_archive_data = archive_sheet.get_all_values()
                    current_row = len(all_archive_data) + 5  # 留出足够空间
                    
                    # 添加支出数据标题
                    archive_sheet.update(f'A{current_row}', f"{year}年支出记录归档")
                    archive_sheet.update(f'A{current_row+1}', f"共{len(year_data)}条记录")
                    
                    # 添加表头
                    header_row = current_row + 3
                    
                    # 确定表头范围
                    max_col = min(len(headers), 26)  # 限制最大列数为26（A-Z）
                    col_range = chr(ord('A') + max_col - 1)
                    
                    # 更新表头（确保不超出范围）
                    truncated_headers = headers[:max_col]
                    archive_sheet.update(f'A{header_row}:{col_range}{header_row}', [truncated_headers])
                    
                    # 添加数据（确保不超出范围）
                    if year_data:
                        # 截断数据以匹配表头长度
                        truncated_data = [row[:max_col] for row in year_data]
                        
                        data_start_row = header_row + 1
                        data_end_row = data_start_row + len(truncated_data) - 1
                        
                        # 分批次更新数据，避免一次性更新过多
                        batch_size = 100
                        for i in range(0, len(truncated_data), batch_size):
                            batch_end = min(i + batch_size, len(truncated_data))
                            batch_data = truncated_data[i:batch_end]
                            batch_start_row = data_start_row + i
                            batch_end_row = batch_start_row + len(batch_data) - 1
                            
                            # 更新数据
                            archive_sheet.update(f'A{batch_start_row}:{col_range}{batch_end_row}', batch_data)
                            logger.info(f"已更新第{batch_start_row}-{batch_end_row}行数据")
                    
                    # 美化表格
                    try:
                        archive_sheet.format(f'A{current_row}:A{current_row+1}', {
                            'textFormat': {'fontSize': 14, 'bold': True}
                        })
                        archive_sheet.format(f'A{header_row}:{col_range}{header_row}', {
                            'textFormat': {'bold': True},
                            'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9}
                        })
                    except Exception as format_err:
                        logger.warning(f"表格美化失败（非关键错误）: {format_err}")
                    
                    logger.info(f"✅ 已归档{len(year_data)}条{year}年支出记录")
                except Exception as update_err:
                    logger.error(f"更新归档表时出错: {update_err}")
                    # 尝试使用更简单的方法更新
                    try:
                        logger.info("尝试使用替代方法更新数据...")
                        # 简单地将数据附加到工作表末尾
                        archive_sheet.append_rows([
                            [f"{year}年支出记录归档"],
                            [f"共{len(year_data)}条记录"],
                            [],
                            headers,
                            *year_data
                        ])
                        logger.info("使用替代方法更新成功")
                    except Exception as alt_err:
                        logger.error(f"替代更新方法也失败: {alt_err}")
                        return 0
            else:
                logger.info(f"没有找到{year}年的支出记录")
            
            return archived_count
            
        except Exception as e:
            logger.error(f"❌ 归档{year}年支出数据失败: {e}")
            return 0
    
    def initialize_new_year(self, year: int) -> Dict[str, Any]:
        """初始化新年度数据和报表
        
        为新的一年准备必要的报表模板和数据结构
        
        Args:
            year: 要初始化的年份
            
        Returns:
            包含初始化结果的字典
        """
        try:
            logger = logging.getLogger(__name__)
            logger.info(f"开始初始化{year}年数据环境...")
            result = {
                'initialized_reports': []
            }
            
            # 1. 预创建年度报表
            reports = [
                ('sales', self.export_sales_report(year)),
                ('expenses', self.export_expenses_report(year)),
                ('pl', self.export_pl_report(year))
            ]
            
            # 记录创建的报表
            for report_type, report_result in reports:
                if report_result and 'sheet_name' in report_result:
                    result['initialized_reports'].append(report_result['sheet_name'])
            
            # 2. 创建年度工作区索引
            workspace_sheet_name = f"Workspace {year}"
            try:
                workspace_sheet = self.spreadsheet.worksheet(workspace_sheet_name)
                logger.info(f"工作区索引表已存在: {workspace_sheet_name}")
            except:
                workspace_sheet = self.spreadsheet.add_worksheet(
                    title=workspace_sheet_name, rows=100, cols=10
                )
                logger.info(f"创建工作区索引表: {workspace_sheet_name}")
                
                # 添加索引表标题和说明
                workspace_sheet.update('A1', f"{year}年工作区")
                workspace_sheet.update('A2', f"创建时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                workspace_sheet.update('A4', "此工作表包含当前年度报表的索引和链接:")
                
                # 添加报表链接
                row = 6
                for _, report_result in reports:
                    if report_result and 'sheet_name' in report_result and 'sheet_url' in report_result:
                        # 添加报表链接
                        workspace_sheet.update(f'A{row}', report_result['sheet_name'])
                        workspace_sheet.update(f'B{row}', f'=HYPERLINK("{report_result["sheet_url"]}","点击查看")')
                        row += 1
                
                # 添加说明
                workspace_sheet.update(f'A{row+2}', "数据记录表:")
                workspace_sheet.update(f'A{row+3}', "- 销售记录")
                workspace_sheet.update(f'A{row+4}', "- 支出记录")
                
                # 美化表格
                workspace_sheet.format('A1:A2', {
                    'textFormat': {'fontSize': 14, 'bold': True}
                })
                
                result['initialized_reports'].append(workspace_sheet_name)
            
            logger.info(f"✅ {year}年数据环境初始化完成")
            return result
            
        except Exception as e:
            logger.error(f"❌ 初始化{year}年数据环境失败: {e}")
            return None



# 创建全局实例
sheets_manager = GoogleSheetsManager()
