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
    'sales': '销售记录',
    'expenses': '费用记录', 
    'agents': '代理商管理',
    'suppliers': '供应商管理',
    'workers': '工作人员管理',
    'pic': '负责人管理'
}

SALES_HEADERS = ['Date', 'Personal in charge', 'Invoice Amount', 'Client Type', 'Commission Rate', 'Commission Amount', 'Notes']
EXPENSES_HEADERS = ['Date', 'Expense Type', 'Supplier', 'Amount', 'Category', 'Description']
AGENTS_HEADERS = ['Name', 'IC', 'Phone']
SUPPLIERS_HEADERS = ['Supplier Name', 'Contact', 'Phone', 'Email', 'Product/Service', 'Status']
WORKERS_HEADERS = ['Name', 'Contact', 'Phone', 'Position', 'Status']
PICS_HEADERS = ['Name', 'Contact', 'Phone', 'Department', 'Status']

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
        
        # 定义要在Google Sheet中显示的工作表
        visible_sheets = {
            'sales': SHEET_NAMES['sales'],
            'expenses': SHEET_NAMES['expenses'],
            'agents': SHEET_NAMES['agents'],
            'suppliers': SHEET_NAMES['suppliers'],
            'pic': SHEET_NAMES['pic']  # 添加负责人管理表为可见表
        }
        
        # 重新创建代理商管理表，以更新表头
        if SHEET_NAMES['agents'] in existing_sheets:
            try:
                # 先备份现有数据
                agents_ws = self.spreadsheet.worksheet(SHEET_NAMES['agents'])
                agents_data = agents_ws.get_all_records()
                
                # 删除旧表
                self.spreadsheet.del_worksheet(agents_ws)
                logger.info(f"✅ 删除旧的代理商管理表: {SHEET_NAMES['agents']}")
                
                # 从existing_sheets中移除，以便后续创建新表
                existing_sheets.remove(SHEET_NAMES['agents'])
            except Exception as e:
                logger.error(f"❌ 删除代理商管理表失败: {e}")
        
        # 创建缺失的工作表（只创建可见的工作表）
        for sheet_key, sheet_name in visible_sheets.items():
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
                    
                    # 如果有备份数据，恢复数据（只保留Name、IC和Phone三列）
                    if 'agents_data' in locals():
                        for agent in agents_data:
                            try:
                                # 只添加需要的三列数据
                                row_data = [
                                    agent.get('Name', ''),
                                    agent.get('IC', ''),  # 使用IC字段
                                    agent.get('Phone', '')
                                ]
                                worksheet.append_row(row_data)
                            except Exception as e:
                                logger.error(f"❌ 恢复代理商数据失败: {e}")
                                
                elif sheet_key == 'suppliers':
                    worksheet.append_row(SUPPLIERS_HEADERS)
                elif sheet_key == 'pic':
                    worksheet.append_row(PICS_HEADERS)
                
                logger.info(f"✅ 创建工作表: {sheet_name}")
        
        # 移除不需要显示的工作表（如果存在）
        for sheet_key, sheet_name in SHEET_NAMES.items():
            if sheet_key not in visible_sheets and sheet_name in existing_sheets:
                try:
                    worksheet = self.spreadsheet.worksheet(sheet_name)
                    self.spreadsheet.del_worksheet(worksheet)
                    logger.info(f"✅ 移除工作表: {sheet_name}")
                except Exception as e:
                    logger.error(f"❌ 移除工作表失败 {sheet_name}: {e}")
                    # 继续执行，不中断程序
    
    def get_worksheet(self, sheet_name: str):
        """获取指定工作表，对于不存在的工作表（workers）使用内存中的数据"""
        try:
            # 对于不在Google Sheet中显示的工作表，使用内存中的数据
            if sheet_name == SHEET_NAMES['workers']:  # 只有workers表使用内存数据
                # 检查是否已经有内存中的数据
                if not hasattr(self, '_memory_worksheets'):
                    self._memory_worksheets = {}
                
                if sheet_name not in self._memory_worksheets:
                    # 创建一个内存中的工作表对象
                    from collections import namedtuple
                    MemoryWorksheet = namedtuple('MemoryWorksheet', ['title', 'data', 'headers'])
                    
                    # 设置对应的表头
                    headers = WORKERS_HEADERS
                    
                    # 创建内存工作表
                    self._memory_worksheets[sheet_name] = MemoryWorksheet(
                        title=sheet_name,
                        data=[],  # 存储行数据
                        headers=headers
                    )
                    logger.info(f"✅ 创建内存工作表: {sheet_name}")
                
                # 返回内存中的工作表对象
                memory_worksheet = self._memory_worksheets[sheet_name]
                
                # 添加必要的方法，使其行为类似于gspread的worksheet
                class MemoryWorksheetWrapper:
                    def __init__(self, memory_ws):
                        self.memory_ws = memory_ws
                    
                    def append_row(self, row_data):
                        self.memory_ws.data.append(row_data)
                        return True
                    
                    def get_all_records(self):
                        if not self.memory_ws.data:
                            return []
                        
                        records = []
                        for row in self.memory_ws.data:
                            record = {}
                            for i, header in enumerate(self.memory_ws.headers):
                                if i < len(row):
                                    record[header] = row[i]
                                else:
                                    record[header] = ''
                            records.append(record)
                        return records
                
                return MemoryWorksheetWrapper(memory_worksheet)
            
            # 对于正常的工作表，使用Google Sheet
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
                    if record.get('Date', '').startswith(month):
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
            
            # 准备数据行
            row_data = [
                data.get('date', datetime.now().strftime('%Y-%m-%d')),
                data.get('type', ''),
                data.get('supplier', ''),
                data.get('amount', 0),
                data.get('category', ''),
                data.get('description', '')
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 费用记录添加成功: {data.get('amount')}")
            return True
        except Exception as e:
            logger.error(f"❌ 添加费用记录失败: {e}")
            return False
    
    def add_expense(self, date_str: str, expense_type: str, amount: float, supplier: str = "", 
                    description: str = "", receipt: str = "") -> bool:
        """添加费用记录（简化版）"""
        try:
            data = {
                'date': date_str,
                'type': expense_type,
                'supplier': supplier,
                'amount': amount,
                'category': supplier if supplier else 'Other',
                'description': description
            }
            return self.add_expense_record(data)
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
                    if record.get('Date', '').startswith(month):
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
            
            # 使用英文字段名，只添加三列数据
            row_data = [
                data.get('name', ''),
                data.get('ic', ''),  # 使用ic字段
                data.get('phone', '')
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
            
            # 由于不再有Status字段，直接返回所有记录
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
            
            # 使用英文字段名
            row_data = [
                data.get('name', ''),
                data.get('contact', ''),
                data.get('phone', ''),
                data.get('email', ''),
                data.get('products', ''),
                data.get('status', 'Active')
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
                return [r for r in records if r.get('Status') == 'Active']
            
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
            
            # 使用英文字段名
            row_data = [
                data.get('name', ''),
                data.get('contact', ''),
                data.get('phone', ''),
                data.get('position', ''),
                data.get('status', 'Active')
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
                return [r for r in records if r.get('Status') == 'Active']
            
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
            
            # 使用英文字段名
            row_data = [
                data.get('name', ''),
                data.get('contact', ''),
                data.get('phone', ''),
                data.get('department', ''),
                data.get('status', 'Active')
            ]
            
            worksheet.append_row(row_data)
            logger.info(f"✅ 负责人添加成功: {data.get('name')}")
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
            
            if active_only:
                return [r for r in records if r.get('Status') == 'Active']
            
            return records
            
        except Exception as e:
            logger.error(f"❌ 获取负责人列表失败: {e}")
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
            total_sales = sum(float(r.get('Invoice Amount', 0)) for r in sales_records)
            total_commission = sum(float(r.get('Commission Amount', 0)) for r in sales_records)
            
            # 计算费用总额
            total_expenses = sum(float(r.get('Amount', 0)) for r in expense_records)
            
            # 按类型统计费用
            expense_by_type = {}
            for record in expense_records:
                expense_type = record.get('Expense Type', '其他')
                amount = float(record.get('Amount', 0))
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

    def update_agents_worksheet(self):
        """手动更新代理商管理表的表头结构"""
        try:
            # 检查表是否存在
            existing_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            if SHEET_NAMES['agents'] not in existing_sheets:
                logger.error(f"❌ 代理商管理表不存在: {SHEET_NAMES['agents']}")
                return False
            
            # 先备份现有数据
            agents_ws = self.spreadsheet.worksheet(SHEET_NAMES['agents'])
            agents_data = agents_ws.get_all_records()
            
            # 删除旧表
            self.spreadsheet.del_worksheet(agents_ws)
            logger.info(f"✅ 删除旧的代理商管理表: {SHEET_NAMES['agents']}")
            
            # 创建新表
            worksheet = self.spreadsheet.add_worksheet(
                title=SHEET_NAMES['agents'], rows=1000, cols=20
            )
            
            # 添加新表头
            worksheet.append_row(AGENTS_HEADERS)
            logger.info(f"✅ 创建新的代理商管理表: {SHEET_NAMES['agents']}")
            
            # 恢复数据（只保留Name、IC和Phone三列）
            for agent in agents_data:
                try:
                    # 只添加需要的三列数据
                    row_data = [
                        agent.get('Name', ''),
                        agent.get('IC', ''),  # 使用IC字段
                        agent.get('Phone', '')
                    ]
                    worksheet.append_row(row_data)
                except Exception as e:
                    logger.error(f"❌ 恢复代理商数据失败: {e}")
            
            logger.info(f"✅ 成功更新代理商管理表结构")
            return True
            
        except Exception as e:
            logger.error(f"❌ 更新代理商管理表失败: {e}")
            return False

    def update_pic_worksheet(self):
        """手动更新负责人管理表，确保它存在并有正确的表头"""
        try:
            # 检查表是否存在
            existing_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            if SHEET_NAMES['pic'] not in existing_sheets:
                # 创建新表
                worksheet = self.spreadsheet.add_worksheet(
                    title=SHEET_NAMES['pic'], rows=1000, cols=20
                )
                worksheet.append_row(PICS_HEADERS)
                logger.info(f"✅ 创建负责人管理表: {SHEET_NAMES['pic']}")
            else:
                # 表已存在，确保表头正确
                worksheet = self.spreadsheet.worksheet(SHEET_NAMES['pic'])
                # 获取第一行
                first_row = worksheet.row_values(1)
                if first_row != PICS_HEADERS:
                    # 备份数据
                    pic_data = worksheet.get_all_records()
                    # 删除旧表
                    self.spreadsheet.del_worksheet(worksheet)
                    # 创建新表
                    new_worksheet = self.spreadsheet.add_worksheet(
                        title=SHEET_NAMES['pic'], rows=1000, cols=20
                    )
                    new_worksheet.append_row(PICS_HEADERS)
                    # 恢复数据
                    for pic in pic_data:
                        try:
                            row_data = [
                                pic.get('Name', ''),
                                pic.get('Contact', ''),
                                pic.get('Phone', ''),
                                pic.get('Department', ''),
                                pic.get('Status', 'Active')
                            ]
                            new_worksheet.append_row(row_data)
                        except Exception as e:
                            logger.error(f"❌ 恢复负责人数据失败: {e}")
                    logger.info(f"✅ 更新负责人管理表: {SHEET_NAMES['pic']}")
            
            return True
        except Exception as e:
            logger.error(f"❌ 更新负责人管理表失败: {e}")
            return False

# 创建全局实例
sheets_manager = GoogleSheetsManager()

# 立即更新代理商管理表和负责人管理表结构
try:
    sheets_manager.update_agents_worksheet()
    sheets_manager.update_pic_worksheet()
    logger.info("✅ 已执行表结构更新")
except Exception as e:
    logger.error(f"❌ 执行表结构更新失败: {e}")
