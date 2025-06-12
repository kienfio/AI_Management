#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Google Sheets API 集成 - 增强版
数据存储和同步功能，带美化和格式化
"""

import logging
import os
from datetime import datetime
from typing import List, Dict, Optional, Any
import gspread
import json
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

# 直接导入常量，避免循环导入
SHEET_NAMES = {
    'sales': '销售记录',
    'expenses': '费用记录', 
    'agents': '代理商管理',
    'suppliers': '供应商管理',
    'workers': '工作人员管理',
    'pic': '负责人管理'
}

SALES_HEADERS = ['日期', '销售人员', '发票金额', '客户类型', '佣金比例', '佣金金额', '备注']
EXPENSES_HEADERS = ['日期', '费用类型', '供应商', '金额', '类别', '备注']
AGENTS_HEADERS = ['姓名', '联系人', '电话', '邮箱', '佣金比例', '状态']
SUPPLIERS_HEADERS = ['供应商名称', '联系人', '电话', '邮箱', '产品/服务', '状态']
WORKERS_HEADERS = ['姓名', '联系人', '电话', '职位', '状态']
PICS_HEADERS = ['姓名', '联系人', '电话', '部门', '状态']

# 颜色配置
COLORS = {
    'header_bg': {'red': 0.2, 'green': 0.4, 'blue': 0.8},  # 蓝色表头
    'header_text': {'red': 1.0, 'green': 1.0, 'blue': 1.0},  # 白色文字
    'active_status': {'red': 0.8, 'green': 0.9, 'blue': 0.8},  # 浅绿色
    'inactive_status': {'red': 0.9, 'green': 0.8, 'blue': 0.8},  # 浅红色
    'amount_positive': {'red': 0.9, 'green': 1.0, 'blue': 0.9},  # 浅绿色背景
    'amount_negative': {'red': 1.0, 'green': 0.9, 'blue': 0.9},  # 浅红色背景
    'zebra_even': {'red': 0.95, 'green': 0.95, 'blue': 0.95},  # 浅灰色斑马纹
}

logger = logging.getLogger(__name__)

class GoogleSheetsManager:
    """Google Sheets 管理器 - 增强版"""
    
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
    
    def _format_header(self, worksheet, headers: List[str], row: int = 1):
        """格式化表头"""
        try:
            # 设置表头样式
            header_range = f"A{row}:{chr(ord('A') + len(headers) - 1)}{row}"
            
            # 表头格式
            header_format = {
                "backgroundColor": COLORS['header_bg'],
                "textFormat": {
                    "foregroundColor": COLORS['header_text'],
                    "fontSize": 11,
                    "bold": True
                },
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE"
            }
            
            # 应用格式
            worksheet.format(header_range, header_format)
            
            # 设置行高
            worksheet.set_row_height(row, 35)
            
            # 冻结表头行
            worksheet.freeze(rows=1)
            
            logger.info(f"✅ 表头格式化完成: {header_range}")
            
        except Exception as e:
            logger.error(f"❌ 表头格式化失败: {e}")
    
    def _format_data_columns(self, worksheet, sheet_type: str):
        """格式化数据列"""
        try:
            # 根据工作表类型设置列格式
            if sheet_type in ['sales', 'expenses']:
                # 金额列格式化为货币
                amount_cols = []
                if sheet_type == 'sales':
                    amount_cols = ['C', 'E', 'F']  # 发票金额, 佣金比例, 佣金金额
                elif sheet_type == 'expenses':
                    amount_cols = ['D']  # 金额
                
                for col in amount_cols:
                    # 设置数字格式
                    worksheet.format(f"{col}2:{col}1000", {
                        "numberFormat": {
                            "type": "CURRENCY",
                            "pattern": "¥#,##0.00"
                        },
                        "horizontalAlignment": "RIGHT"
                    })
            
            # 日期列格式化
            if sheet_type in ['sales', 'expenses']:
                worksheet.format("A2:A1000", {
                    "numberFormat": {
                        "type": "DATE",
                        "pattern": "yyyy-mm-dd"
                    },
                    "horizontalAlignment": "CENTER"
                })
            
            # 状态列格式化（条件格式）
            if sheet_type in ['agents', 'suppliers', 'workers', 'pic']:
                status_col = 'F'  # 状态列
                
                # 激活状态 - 绿色背景
                worksheet.format(f"{status_col}2:{status_col}1000", {
                    "conditionalFormatRules": [{
                        "ranges": [{"sheetId": worksheet.id, "startColumnIndex": 5, "endColumnIndex": 6}],
                        "booleanRule": {
                            "condition": {
                                "type": "TEXT_EQ",
                                "values": [{"userEnteredValue": "激活"}]
                            },
                            "format": {
                                "backgroundColor": COLORS['active_status']
                            }
                        }
                    }]
                })
            
            logger.info(f"✅ 数据列格式化完成: {sheet_type}")
            
        except Exception as e:
            logger.error(f"❌ 数据列格式化失败: {e}")
    
    def _add_zebra_stripes(self, worksheet):
        """添加斑马纹（隔行变色）"""
        try:
            # 设置隔行变色
            worksheet.format("A2:Z1000", {
                "conditionalFormatRules": [{
                    "ranges": [{"sheetId": worksheet.id}],
                    "booleanRule": {
                        "condition": {
                            "type": "CUSTOM_FORMULA",
                            "values": [{"userEnteredValue": "=ISEVEN(ROW())"}]
                        },
                        "format": {
                            "backgroundColor": COLORS['zebra_even']
                        }
                    }
                }]
            })
            
            logger.info("✅ 斑马纹格式添加完成")
            
        except Exception as e:
            logger.error(f"❌ 斑马纹格式添加失败: {e}")
    
    def _set_column_widths(self, worksheet, sheet_type: str):
        """设置列宽"""
        try:
            width_configs = {
                'sales': [120, 120, 100, 100, 80, 100, 200],  # 日期, 销售人员, 发票金额等
                'expenses': [120, 120, 120, 100, 100, 200],   # 日期, 费用类型等
                'agents': [100, 120, 120, 180, 80, 80],       # 姓名, 联系人等
                'suppliers': [150, 120, 120, 180, 150, 80],   # 供应商名称等
                'workers': [100, 120, 120, 100, 80],          # 姓名, 联系人等
                'pic': [100, 120, 120, 100, 80]               # 姓名, 联系人等
            }
            
            if sheet_type in width_configs:
                widths = width_configs[sheet_type]
                for i, width in enumerate(widths):
                    worksheet.columns_auto_resize(i, i + 1)
                    # 设置最小宽度
                    col_letter = chr(ord('A') + i)
                    worksheet.update_dimension_property(
                        'COLUMNS', 
                        col_letter, 
                        'pixelSize', 
                        width
                    )
            
            logger.info(f"✅ 列宽设置完成: {sheet_type}")
            
        except Exception as e:
            logger.error(f"❌ 列宽设置失败: {e}")
    
    def _add_data_validation(self, worksheet, sheet_type: str):
        """添加数据验证"""
        try:
            if sheet_type == 'sales':
                # 客户类型下拉选择
                worksheet.data_validation('D2:D1000', {
                    'condition': {
                        'type': 'ONE_OF_LIST',
                        'values': [
                            {'userEnteredValue': '个人客户'},
                            {'userEnteredValue': '企业客户'},
                            {'userEnteredValue': 'VIP客户'},
                            {'userEnteredValue': '新客户'}
                        ]
                    },
                    'showCustomUi': True,
                    'strict': False
                })
            
            elif sheet_type == 'expenses':
                # 费用类型下拉选择
                worksheet.data_validation('B2:B1000', {
                    'condition': {
                        'type': 'ONE_OF_LIST',
                        'values': [
                            {'userEnteredValue': '办公用品'},
                            {'userEnteredValue': '差旅费'},
                            {'userEnteredValue': '招待费'},
                            {'userEnteredValue': '营销费用'},
                            {'userEnteredValue': '其他'}
                        ]
                    },
                    'showCustomUi': True,
                    'strict': False
                })
                
                # 类别下拉选择
                worksheet.data_validation('E2:E1000', {
                    'condition': {
                        'type': 'ONE_OF_LIST',
                        'values': [
                            {'userEnteredValue': '固定成本'},
                            {'userEnteredValue': '变动成本'},
                            {'userEnteredValue': '管理费用'},
                            {'userEnteredValue': '销售费用'}
                        ]
                    },
                    'showCustomUi': True,
                    'strict': False
                })
            
            # 状态列验证（适用于人员管理表）
            if sheet_type in ['agents', 'suppliers', 'workers', 'pic']:
                status_col_range = f"F2:F1000"
                worksheet.data_validation(status_col_range, {
                    'condition': {
                        'type': 'ONE_OF_LIST',
                        'values': [
                            {'userEnteredValue': '激活'},
                            {'userEnteredValue': '停用'}
                        ]
                    },
                    'showCustomUi': True,
                    'strict': True
                })
            
            logger.info(f"✅ 数据验证添加完成: {sheet_type}")
            
        except Exception as e:
            logger.error(f"❌ 数据验证添加失败: {e}")
    
    def _ensure_worksheets_exist(self):
        """确保所有必需的工作表存在并格式化"""
        existing_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
        
        # 创建缺失的工作表
        for sheet_key, sheet_name in SHEET_NAMES.items():
            if sheet_name not in existing_sheets:
                worksheet = self.spreadsheet.add_worksheet(
                    title=sheet_name, rows=1000, cols=20
                )
                
                # 添加表头
                headers = []
                if sheet_key == 'sales':
                    headers = SALES_HEADERS
                elif sheet_key == 'expenses':
                    headers = EXPENSES_HEADERS
                elif sheet_key == 'agents':
                    headers = AGENTS_HEADERS
                elif sheet_key == 'suppliers':
                    headers = SUPPLIERS_HEADERS
                elif sheet_key == 'workers':
                    headers = WORKERS_HEADERS
                elif sheet_key == 'pic':
                    headers = PICS_HEADERS
                
                if headers:
                    worksheet.append_row(headers)
                    
                    # 应用格式化
                    self._format_header(worksheet, headers)
                    self._format_data_columns(worksheet, sheet_key)
                    self._add_zebra_stripes(worksheet)
                    self._set_column_widths(worksheet, sheet_key)
                    self._add_data_validation(worksheet, sheet_key)
                
                logger.info(f"✅ 创建并格式化工作表: {sheet_name}")
            else:
                # 如果工作表已存在，确保格式正确
                worksheet = self.spreadsheet.worksheet(sheet_name)
                headers = []
                
                if sheet_key == 'sales':
                    headers = SALES_HEADERS
                elif sheet_key == 'expenses':
                    headers = EXPENSES_HEADERS
                elif sheet_key == 'agents':
                    headers = AGENTS_HEADERS
                elif sheet_key == 'suppliers':
                    headers = SUPPLIERS_HEADERS
                elif sheet_key == 'workers':
                    headers = WORKERS_HEADERS
                elif sheet_key == 'pic':
                    headers = PICS_HEADERS
                
                if headers:
                    # 检查是否需要更新格式
                    try:
                        self._format_header(worksheet, headers)
                        self._format_data_columns(worksheet, sheet_key)
                        self._add_data_validation(worksheet, sheet_key)
                        logger.info(f"✅ 更新工作表格式: {sheet_name}")
                    except Exception as e:
                        logger.warning(f"⚠️ 更新工作表格式失败 {sheet_name}: {e}")
    
    def get_worksheet(self, sheet_name: str):
        """获取指定工作表"""
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except Exception as e:
            logger.error(f"❌ 获取工作表失败 {sheet_name}: {e}")
            return None
    
    def _format_new_row(self, worksheet, row_num: int, sheet_type: str):
        """格式化新添加的行"""
        try:
            # 基本行格式
            row_range = f"A{row_num}:Z{row_num}"
            worksheet.format(row_range, {
                "verticalAlignment": "MIDDLE",
                "textFormat": {"fontSize": 10}
            })
            
            # 根据类型设置特定格式
            if sheet_type in ['sales', 'expenses']:
                # 日期列居中
                worksheet.format(f"A{row_num}", {
                    "horizontalAlignment": "CENTER"
                })
                
                # 金额列右对齐
                if sheet_type == 'sales':
                    worksheet.format(f"C{row_num}:F{row_num}", {
                        "horizontalAlignment": "RIGHT"
                    })
                elif sheet_type == 'expenses':
                    worksheet.format(f"D{row_num}", {
                        "horizontalAlignment": "RIGHT"
                    })
            
            # 状态列居中（人员管理表）
            if sheet_type in ['agents', 'suppliers', 'workers', 'pic']:
                worksheet.format(f"F{row_num}", {
                    "horizontalAlignment": "CENTER"
                })
            
        except Exception as e:
            logger.error(f"❌ 行格式化失败: {e}")
    
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
                float(data.get('amount', 0)),
                data.get('client_type', ''),
                float(data.get('commission_rate', 0)),
                float(data.get('commission_amount', 0)),
                data.get('notes', '')
            ]
            
            worksheet.append_row(row_data)
            
            # 格式化新添加的行
            row_count = len(worksheet.get_all_values())
            self._format_new_row(worksheet, row_count, 'sales')
            
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
                float(data.get('amount', 0)),
                data.get('category', ''),
                data.get('notes', '')
            ]
            
            worksheet.append_row(row_data)
            
            # 格式化新添加的行
            row_count = len(worksheet.get_all_values())
            self._format_new_row(worksheet, row_count, 'expenses')
            
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
                float(data.get('commission_rate', 0)),
                data.get('status', '激活')
            ]
            
            worksheet.append_row(row_data)
            
            # 格式化新添加的行
            row_count = len(worksheet.get_all_values())
            self._format_new_row(worksheet, row_count, 'agents')
            
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
            
            # 格式化新添加的行
            row_count = len(worksheet.get_all_values())
            self._format_new_row(worksheet, row_count, 'suppliers')
            
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
        """获取负责人列表，使用缓存提高响应速度"""
        cache_key = f"pics_{active_only}"
        # 检查缓存是否有效（30分钟内）
        if cache_key in self._cache and cache_key in self._cache_expiry:
            if datetime.now() < self._cache_expiry[cache_key]:
                logger.info(f"✅ 使用缓存的负责人列表")
                return self._cache[cache_key]
        
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['pic'])
            if not worksheet:
                return []
            
            records = worksheet.get_all_records()
            
            if active_only:
                result = [r for r in records if r.get('Status') == 'Active']
            else:
                result = records
            
            # 更新缓存
            self._cache[cache_key] = result
            # 设置缓存过期时间（30分钟）
            self._cache_expiry[cache_key] = datetime.now() + timedelta(minutes=30)
            logger.info(f"✅ 已更新负责人列表缓存")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 获取负责人列表失败: {e}")
            return []
            
    def clear_cache(self):
        """清除所有缓存"""
        self._cache.clear()
        self._cache_expiry.clear()
        logger.info("✅ 已清除所有缓存")
        
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
            
            # 清除缓存，确保下次获取最新数据
            self.clear_cache()
            return True
        except Exception as e:
            logger.error(f"❌ 更新负责人管理表失败: {e}")
            return False
    
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

# 创建全局实例
sheets_manager = GoogleSheetsManager()

# 立即更新代理商管理表和负责人管理表结构
try:
    sheets_manager.update_agents_worksheet()
    sheets_manager.update_pic_worksheet()
    logger.info("✅ 已执行表结构更新")
except Exception as e:
    logger.error(f"❌ 执行表结构更新失败: {e}")
