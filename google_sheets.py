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

SALES_HEADERS = ['日期', '销售人员', '发票金额', '客户类型', '佣金比例', '佣金金额', '备注']
EXPENSES_HEADERS = ['日期', '费用类型', '供应商', '金额', '类别', '备注']
AGENTS_HEADERS = ['姓名', '联系人', '电话', '邮箱', '佣金比例', '状态']
SUPPLIERS_HEADERS = ['供应商名称', '联系人', '电话', '邮箱', '产品/服务', '状态']
WORKERS_HEADERS = ['姓名', '联系人', '电话', '职位', '状态']
PICS_HEADERS = ['姓名', '联系人', '电话', '部门', '状态']

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
        try:
            logger.info("开始检查和创建必要的工作表")
            existing_sheets = [ws.title for ws in self.spreadsheet.worksheets()]
            logger.info(f"现有工作表: {existing_sheets}")
            
            # 创建缺失的工作表
            for sheet_key, sheet_name in SHEET_NAMES.items():
                if sheet_name not in existing_sheets:
                    logger.info(f"创建工作表: {sheet_name}")
                    try:
                        worksheet = self.spreadsheet.add_worksheet(
                            title=sheet_name, rows=1000, cols=20
                        )
                        
                        # 添加表头
                        headers = None
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
                            logger.info(f"为工作表 {sheet_name} 添加表头: {headers}")
                            worksheet.append_row(headers)
                        
                        logger.info(f"✅ 成功创建工作表: {sheet_name}")
                    except Exception as e:
                        logger.error(f"❌ 创建工作表 {sheet_name} 失败: {e}")
                else:
                    logger.info(f"工作表已存在: {sheet_name}")
        except Exception as e:
            logger.error(f"❌ 确保工作表存在时发生错误: {e}")
            raise
    
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
    # 工作人员管理
    # =============================================================================
    
    def add_worker(self, data: Dict[str, Any]) -> bool:
        """添加工作人员"""
        try:
            worksheet = self.get_worksheet(SHEET_NAMES['workers'])
            if not worksheet:
                return False
            
            row_data = [
                data.get('name', ''),
                data.get('contact', ''),
                data.get('phone', ''),
                data.get('position', ''),
                data.get('status', '激活')
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
                return [r for r in records if r.get('状态') == '激活']
            
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
            logger.info(f"开始添加负责人，数据: {data}")
            worksheet = self.get_worksheet(SHEET_NAMES['pic'])
            if not worksheet:
                logger.error("获取负责人工作表失败")
                return False
            
            # 确保所有必要的字段都存在
            name = data.get('姓名', '')
            if not name:
                logger.error("负责人姓名不能为空")
                return False
            
            logger.info(f"准备添加负责人行数据，姓名: {name}")
            row_data = [
                name,  # 姓名
                data.get('联系人', ''),
                data.get('电话', ''),
                data.get('部门', ''),
                data.get('状态', '激活')
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
            logger.info("开始获取负责人列表")
            worksheet = self.get_worksheet(SHEET_NAMES['pic'])
            if not worksheet:
                logger.error("获取负责人工作表失败")
                return []
            
            records = worksheet.get_all_records()
            logger.info(f"获取到 {len(records)} 条负责人记录")
            
            # 打印记录的键名，用于调试
            if records:
                logger.info(f"记录的键名: {list(records[0].keys())}")
            
            if active_only:
                active_records = [r for r in records if r.get('状态') == '激活']
                logger.info(f"筛选后的激活负责人数量: {len(active_records)}")
                return active_records
            
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

# 添加一个测试函数，用于测试负责人的添加和获取
def test_pic_functions():
    """测试负责人的添加和获取"""
    try:
        logger.info("开始测试负责人功能")
        
        # 添加一个测试负责人
        test_pic = {
            '姓名': 'Test Person',
            '联系人': 'Test Contact',
            '电话': '12345678',
            '部门': 'Test Department',
            '状态': '激活'
        }
        
        result = sheets_manager.add_pic(test_pic)
        logger.info(f"添加测试负责人结果: {result}")
        
        # 获取所有负责人
        pics = sheets_manager.get_pics()
        logger.info(f"获取到 {len(pics)} 个负责人")
        
        # 打印第一个负责人的信息
        if pics:
            logger.info(f"第一个负责人: {pics[0]}")
        
        return result
    except Exception as e:
        logger.error(f"测试负责人功能失败: {e}")
        return False

# 如果需要测试，可以取消下面的注释
# if __name__ == "__main__":
#     test_pic_functions()
