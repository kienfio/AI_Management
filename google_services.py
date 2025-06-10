import os
import io
import json
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from tempfile import NamedTemporaryFile
import logging

# 配置日志
logger = logging.getLogger(__name__)

class GoogleServices:
    """处理与Google服务（Sheets和Drive）的所有交互"""
    
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # 获取凭证文件路径或内容
        credentials_content = os.getenv('GOOGLE_CREDENTIALS_CONTENT')
        if not credentials_content:
            raise ValueError("未找到 GOOGLE_CREDENTIALS_CONTENT 环境变量")
            
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        if not self.spreadsheet_id:
            raise ValueError("未找到 SPREADSHEET_ID 环境变量")
            
        self.drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
        if not self.drive_folder_id:
            raise ValueError("未找到 DRIVE_FOLDER_ID 环境变量")
        
        # 定义所需权限
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        try:
            # 从环境变量中加载凭证内容
            credentials_dict = json.loads(credentials_content)
            credentials = service_account.Credentials.from_service_account_info(
                credentials_dict, scopes=self.scopes)
            
            # 初始化服务
            self.sheets_service = build('sheets', 'v4', credentials=credentials)
            self.drive_service = build('drive', 'v3', credentials=credentials)
            
            # 验证电子表格访问
            self.verify_spreadsheet_access()
            
        except Exception as e:
            logger.error(f"初始化Google服务时出错: {str(e)}")
            raise
    
    def verify_spreadsheet_access(self):
        """验证是否可以访问电子表格"""
        try:
            # 尝试获取电子表格的基本信息
            self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            logger.info("成功验证电子表格访问权限")
        except Exception as e:
            logger.error(f"验证电子表格访问时出错: {str(e)}")
            raise
    
    def add_expense(self, date, category, amount, description, note='', receipt_url=''):
        """添加支出记录到Google Sheet"""
        try:
            values = [[date, category, amount, description, note, receipt_url]]
            
            # 获取当前数据以确定下一行
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='支出!A:F'
            ).execute()
            
            existing_values = result.get('values', [])
            next_row = len(existing_values) + 1
            
            # 添加新记录
            range_name = f'支出!A{next_row}'
            body = {
                'values': values
            }
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            logger.info(f"成功添加支出记录: {values}")
            return True
            
        except Exception as e:
            logger.error(f"添加支出记录时出错: {str(e)}")
            return False
    
    def upload_file(self, file_path, file_name=None):
        """上传文件到Google Drive指定文件夹"""
        try:
            if not file_name:
                file_name = os.path.basename(file_path)
            
            file_metadata = {
                'name': file_name,
                'parents': [self.drive_folder_id]
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(open(file_path, 'rb').read()),
                mimetype='application/octet-stream',
                resumable=True
            )
            
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            logger.info(f"成功上传文件: {file_name}")
            return file.get('webViewLink')
            
        except Exception as e:
            logger.error(f"上传文件时出错: {str(e)}")
            return None
    
    def add_income(self, date, category, amount, description, note=''):
        """添加收入记录到Google Sheet"""
        try:
            values = [[date, category, amount, description, note]]
            
            # 获取当前数据以确定下一行
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='收入!A:E'
            ).execute()
            
            existing_values = result.get('values', [])
            next_row = len(existing_values) + 1
            
            # 添加新记录
            range_name = f'收入!A{next_row}'
            body = {
                'values': values
            }
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
            return True
            
        except Exception as e:
            print(f"添加收入记录时出错: {e}")
            return False
    
    def upload_receipt(self, image_bytes, description):
        """上传收据照片到Google Drive并返回链接"""
        try:
            # 准备文件元数据
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            file_name = f"收据_{timestamp}_{description}.jpg"
            
            file_metadata = {
                'name': file_name,
                'parents': [self.drive_folder_id]
            }
            
            # 准备媒体
            media = MediaIoBaseUpload(
                io.BytesIO(image_bytes),
                mimetype='image/jpeg',
                resumable=True
            )
            
            # 上传文件
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            # 返回链接
            return file.get('webViewLink')
            
        except Exception as e:
            print(f"上传收据时出错: {e}")
            return None
    
    def get_monthly_summary(self, year=None, month=None):
        """获取指定月份的收支汇总"""
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month
        
        try:
            # 格式化月份
            month_str = str(month).zfill(2)
            date_filter = f"{year}-{month_str}"
            
            # 获取支出数据
            expenses_result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='支出!A:C'
            ).execute()
            
            expense_values = expenses_result.get('values', [])
            
            # 获取收入数据
            income_result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range='收入!A:C'
            ).execute()
            
            income_values = income_result.get('values', [])
            
            # 处理数据
            total_expense = 0
            total_income = 0
            expense_by_category = {}
            income_by_category = {}
            
            # 处理表头
            if len(expense_values) > 0:
                expense_values = expense_values[1:]
            if len(income_values) > 0:
                income_values = income_values[1:]
            
            # 计算支出
            for row in expense_values:
                if len(row) >= 3 and date_filter in row[0]:
                    category = row[1]
                    try:
                        amount = float(row[2])
                        total_expense += amount
                        if category in expense_by_category:
                            expense_by_category[category] += amount
                        else:
                            expense_by_category[category] = amount
                    except ValueError:
                        continue
            
            # 计算收入
            for row in income_values:
                if len(row) >= 3 and date_filter in row[0]:
                    category = row[1]
                    try:
                        amount = float(row[2])
                        total_income += amount
                        if category in income_by_category:
                            income_by_category[category] += amount
                        else:
                            income_by_category[category] = amount
                    except ValueError:
                        continue
            
            # 准备汇总数据
            summary = {
                'year': year,
                'month': month,
                'total_income': total_income,
                'total_expense': total_expense,
                'net': total_income - total_expense,
                'expense_by_category': expense_by_category,
                'income_by_category': income_by_category
            }
            
            return summary
            
        except Exception as e:
            print(f"获取月度汇总时出错: {e}")
            return None 
