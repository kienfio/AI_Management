#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import print_function
"""
Google Sheets API 集成 - 优化版本
支持 Render 部署的环境变量配置
"""

import logging
import json
import os
import os.path
from datetime import datetime
from typing import List, Dict, Optional, Any
import gspread
from google.oauth2.service_account import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 如果修改了这些范围，删除token.json文件
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'  # 添加Drive权限
]

# 检查环境变量
print("正在检查环境变量...")
print(f"GOOGLE_CREDENTIALS_BASE64: {'✅ 已设置' if os.getenv('GOOGLE_CREDENTIALS_BASE64') else '❌ 未设置'}")
print(f"GOOGLE_SHEET_ID: {'✅ 已设置' if os.getenv('GOOGLE_SHEET_ID') else '❌ 未设置'}")
print(f"TELEGRAM_TOKEN: {'✅ 已设置' if os.getenv('TELEGRAM_TOKEN') else '❌ 未设置'}")

# Telegram Bot 配置
BOT_TOKEN = os.getenv('TELEGRAM_TOKEN')
if not BOT_TOKEN:
    raise ValueError("未设置 TELEGRAM_TOKEN 环境变量")

# 从google_sheets.py导入常量
from google_sheets import (
    SHEET_NAMES, SALES_HEADERS, EXPENSES_HEADERS,
    AGENTS_HEADERS, SUPPLIERS_HEADERS
)

class SheetsManager:
    """Google Sheets 管理类"""
    
    def __init__(self):
        """初始化 Sheets 管理器"""
        self.sheets_service = None
        self.drive_service = None
        self._initialize_client()
    
    def _initialize_client(self):
        """初始化 Google Sheets 客户端"""
        try:
            creds = None
            # token.json 存储用户的访问和刷新令牌
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_info(eval(open('token.json', 'r').read()), SCOPES)
            
            # 如果没有有效凭据，让用户登录
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    creds = flow.run_local_server(port=0)
                
                # 保存凭据以供下次使用
                with open('token.json', 'w') as token:
                    token.write(str(creds.to_json()))
            
            # 构建服务
            self.sheets_service = build('sheets', 'v4', credentials=creds)
            
            # 添加Google Drive服务初始化
            self.drive_service = build('drive', 'v3', credentials=creds)
            
            logger.info("✅ Google Sheets & Drive 客户端初始化成功")
        except Exception as e:
            logger.error(f"Google Sheets 客户端初始化失败: {e}")
            raise
    
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
    
    def add_sales_record(self, data):
        """添加销售记录"""
        try:
            # 获取当前日期作为默认日期
            date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            # 准备数据行
            row = [
                date_str,                     # Date
                data.get('person', ''),       # Person
                data.get('bill_to', ''),      # Bill To
                data.get('client', ''),       # Client
                float(data.get('amount', 0)), # Amount
                data.get('agent', ''),        # Agent
                data.get('comm_type', ''),    # Commission Type
                float(data.get('comm_rate', 0)), # Commission Rate
                float(data.get('comm_amount', 0)) # Commission Amount
            ]
            
            # 添加到 Sales Records 表格
            sheet_id = os.getenv('SALES_SHEET_ID')
            range_name = 'Sales Records!A:I'
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': [row]}
            ).execute()
            
            logger.info(f"销售记录已添加: {result.get('updates').get('updatedCells')} 个单元格已更新")
            return True
        except Exception as e:
            logger.error(f"添加销售记录失败: {e}")
            return False
    
    def add_expense_record(self, data):
        """添加费用记录"""
        try:
            # 获取当前日期作为默认日期
            date_str = data.get('date', datetime.now().strftime('%Y-%m-%d'))
            
            # 处理收据链接可能是字典的情况
            receipt = data.get('receipt', '')
            if isinstance(receipt, dict) and 'public_link' in receipt:
                receipt = receipt['public_link']
            
            # 准备数据行
            row = [
                date_str,                     # Date
                data.get('type', ''),         # Type
                data.get('supplier', ''),     # Supplier
                float(data.get('amount', 0)), # Amount
                data.get('category', ''),     # Category
                data.get('description', ''),  # Description
                receipt                       # Receipt Link
            ]
            
            # 添加到 Expense Records 表格
            sheet_id = os.getenv('EXPENSE_SHEET_ID')
            range_name = 'Expense Records!A:G'
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': [row]}
            ).execute()
            
            logger.info(f"费用记录已添加: {result.get('updates').get('updatedCells')} 个单元格已更新")
            return True
        except Exception as e:
            logger.error(f"添加费用记录失败: {e}")
            return False
    
    def get_agents(self):
        """获取代理商列表"""
        try:
            sheet_id = os.getenv('AGENTS_SHEET_ID')
            range_name = 'Agents!A2:C'  # 获取姓名、IC和电话号码
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.info('未找到代理商数据')
                return []
            
            agents = []
            for row in values:
                # 确保行至少有3个元素
                if len(row) >= 3:
                    agent = {
                        'name': row[0],
                        'ic': row[1],
                        'phone': row[2]
                    }
                    agents.append(agent)
                else:
                    # 处理数据不完整的情况
                    logger.warning(f"代理商数据不完整: {row}")
                    # 填充缺失的字段
                    agent = {
                        'name': row[0] if len(row) > 0 else '',
                        'ic': row[1] if len(row) > 1 else '',
                        'phone': row[2] if len(row) > 2 else ''
                    }
                    agents.append(agent)
            
            return agents
        except Exception as e:
            logger.error(f"获取代理商列表失败: {e}")
            return []
    
    def get_suppliers(self):
        """获取供应商列表"""
        try:
            sheet_id = os.getenv('SUPPLIERS_SHEET_ID')
            range_name = 'Suppliers!A2:A'  # 只获取供应商名称
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.info('未找到供应商数据')
                return []
            
            # 将二维数组转换为一维列表
            suppliers = [row[0] for row in values if row]  # 确保行不为空
            
            return suppliers
        except Exception as e:
            logger.error(f"获取供应商列表失败: {e}")
            return []
    
    def add_agent(self, agent_data):
        """添加代理商"""
        try:
            # 准备数据行
            row = [
                agent_data.get('name', ''),   # Name
                agent_data.get('ic', ''),     # IC
                agent_data.get('phone', '')   # Phone
            ]
            
            # 添加到 Agents 表格
            sheet_id = os.getenv('AGENTS_SHEET_ID')
            range_name = 'Agents!A:C'
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': [row]}
            ).execute()
            
            logger.info(f"代理商已添加: {result.get('updates').get('updatedCells')} 个单元格已更新")
            return True
        except Exception as e:
            logger.error(f"添加代理商失败: {e}")
            return False
    
    def add_supplier(self, supplier_name):
        """添加供应商"""
        try:
            # 准备数据行
            row = [supplier_name]
            
            # 添加到 Suppliers 表格
            sheet_id = os.getenv('SUPPLIERS_SHEET_ID')
            range_name = 'Suppliers!A:A'
            
            result = self.sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': [row]}
            ).execute()
            
            logger.info(f"供应商已添加: {result.get('updates').get('updatedCells')} 个单元格已更新")
            return True
        except Exception as e:
            logger.error(f"添加供应商失败: {e}")
            return False
    
    def get_monthly_report(self, year, month):
        """获取月度报表数据"""
        try:
            # 格式化年月为YYYY-MM格式
            month_str = f"{year}-{month:02d}"
            
            # 获取销售数据
            sales_data = self._get_monthly_sales(month_str)
            
            # 获取费用数据
            expense_data = self._get_monthly_expenses(month_str)
            
            # 计算总销售额和总费用
            total_sales = sum(item['amount'] for item in sales_data)
            total_expenses = sum(item['amount'] for item in expense_data)
            
            # 计算净利润
            net_profit = total_sales - total_expenses
            
            return {
                'month': month_str,
                'sales': sales_data,
                'expenses': expense_data,
                'total_sales': total_sales,
                'total_expenses': total_expenses,
                'net_profit': net_profit
            }
        except Exception as e:
            logger.error(f"获取月度报表失败: {e}")
            return None
    
    def _get_monthly_sales(self, month_str):
        """获取指定月份的销售数据"""
        try:
            sheet_id = os.getenv('SALES_SHEET_ID')
            range_name = 'Sales Records!A:E'  # 日期、人员、客户、金额
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.info('未找到销售数据')
                return []
            
            # 跳过表头行
            header = values[0]
            data = values[1:]
            
            # 筛选指定月份的数据
            monthly_data = []
            for row in data:
                if len(row) >= 4 and row[0].startswith(month_str):
                    try:
                        amount = float(row[4]) if len(row) > 4 else 0
                    except ValueError:
                        amount = 0
                    
                    sale = {
                        'date': row[0],
                        'person': row[1] if len(row) > 1 else '',
                        'bill_to': row[2] if len(row) > 2 else '',
                        'client': row[3] if len(row) > 3 else '',
                        'amount': amount
                    }
                    monthly_data.append(sale)
            
            return monthly_data
        except Exception as e:
            logger.error(f"获取月度销售数据失败: {e}")
            return []
    
    def _get_monthly_expenses(self, month_str):
        """获取指定月份的费用数据"""
        try:
            sheet_id = os.getenv('EXPENSE_SHEET_ID')
            range_name = 'Expense Records!A:D'  # 日期、类型、供应商、金额
            
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=sheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.info('未找到费用数据')
                return []
            
            # 跳过表头行
            header = values[0]
            data = values[1:]
            
            # 筛选指定月份的数据
            monthly_data = []
            for row in data:
                if len(row) >= 4 and row[0].startswith(month_str):
                    try:
                        amount = float(row[3]) if len(row) > 3 else 0
                    except ValueError:
                        amount = 0
                    
                    expense = {
                        'date': row[0],
                        'type': row[1] if len(row) > 1 else '',
                        'supplier': row[2] if len(row) > 2 else '',
                        'amount': amount
                    }
                    monthly_data.append(expense)
            
            return monthly_data
        except Exception as e:
            logger.error(f"获取月度费用数据失败: {e}")
            return []

# 不要在导入时自动创建实例
# sheets_manager = SheetsManager()
# 改为在需要时手动创建实例
