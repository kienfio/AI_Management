import os
import io
import json
import threading
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account
from tempfile import NamedTemporaryFile
import logging
from common.shared import logger

# 配置日志
logger = logging.getLogger(__name__)

class GoogleServices:
    """处理与Google服务（Sheets和Drive）的所有交互"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, required=False):
        """单例模式实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, required=False):
        """
        初始化Google服务
        :param required: 如果为True，则缺少配置时抛出异常；如果为False，则仅记录警告
        """
        # 避免重复初始化
        if self._initialized:
            return
            
        self.is_available = False
        self.sheets_service = None
        self.drive_service = None
        
        # 加载环境变量
        load_dotenv()
        
        try:
            # 获取凭证内容
            credentials_content = os.getenv('GOOGLE_CREDENTIALS_CONTENT')
            credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE')
            self.spreadsheet_id = os.getenv('GOOGLE_SHEET_ID')
            self.drive_folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
            
            # 检查必要的配置是否存在
            if not any([credentials_content, credentials_file]) or not all([self.spreadsheet_id, self.drive_folder_id]):
                if required:
                    missing = []
                    if not any([credentials_content, credentials_file]):
                        missing.append("GOOGLE_CREDENTIALS_CONTENT 或 GOOGLE_CREDENTIALS_FILE")
                    if not self.spreadsheet_id:
                        missing.append("GOOGLE_SHEET_ID")
                    if not self.drive_folder_id:
                        missing.append("GOOGLE_DRIVE_FOLDER_ID")
                    raise ValueError(f"缺少必要的环境变量: {', '.join(missing)}")
                else:
                    logger.warning("Google服务配置不完整，某些功能将不可用")
                    return
            
            # 定义所需权限
            self.scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # 初始化服务
            if credentials_content:
                # 从环境变量内容初始化
                credentials_dict = json.loads(credentials_content)
                credentials = service_account.Credentials.from_service_account_info(
                    credentials_dict, scopes=self.scopes)
            else:
                # 从文件初始化
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_file, scopes=self.scopes)
            
            self.sheets_service = build('sheets', 'v4', credentials=credentials)
            self.drive_service = build('drive', 'v3', credentials=credentials)
            
            # 验证电子表格访问
            self.verify_spreadsheet_access()
            
            self.is_available = True
            self._initialized = True
            logger.info("Google服务初始化成功")
            
        except Exception as e:
            if required:
                logger.error(f"初始化Google服务时出错: {str(e)}")
                raise
            else:
                logger.warning(f"Google服务初始化失败，某些功能将不可用: {str(e)}")
    
    def verify_spreadsheet_access(self):
        """验证是否可以访问电子表格"""
        if not self.is_available:
            return False
            
        try:
            self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            logger.info("成功验证电子表格访问权限")
            return True
        except Exception as e:
            logger.error(f"验证电子表格访问时出错: {str(e)}")
            return False
    
    def add_expense(self, date, category, amount, description, note='', receipt_url=''):
        """添加支出记录到Google Sheet"""
        if not self.is_available:
            logger.warning("Google服务未正确初始化，无法添加支出记录")
            return False
            
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
        if not self.is_available:
            logger.warning("Google服务未正确初始化，无法上传文件")
            return None
            
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
    
    def add_agent(self, name, ic):
        """添加代理商"""
        try:
            logger.info(f"添加代理商: 名称={name}, IC={ic}")
            # 在这里添加将代理商数据写入Google Sheets的代码
            # 目前仅模拟成功
            return True
        except Exception as e:
            logger.error(f"添加代理商时出错: {e}")
            return False
    
    def add_supplier(self, name, category):
        """添加供应商"""
        try:
            logger.info(f"添加供应商: 名称={name}, 类别={category}")
            # 在这里添加将供应商数据写入Google Sheets的代码
            # 目前仅模拟成功
            return True
        except Exception as e:
            logger.error(f"添加供应商时出错: {e}")
            return False
    
    def add_personal(self, name):
        """添加负责人"""
        try:
            logger.info(f"添加负责人: 姓名={name}")
            # 在这里添加将负责人数据写入Google Sheets的代码
            # 目前仅模拟成功
            return True
        except Exception as e:
            logger.error(f"添加负责人时出错: {e}")
            return False
    
    def get_agents(self):
        """获取所有代理商"""
        try:
            # 在这里添加从Google Sheets获取代理商数据的代码
            # 目前仅返回模拟数据
            return [
                {"name": "代理商1", "ic": "IC12345"},
                {"name": "代理商2", "ic": "IC67890"}
            ]
        except Exception as e:
            logger.error(f"获取代理商列表时出错: {e}")
            return []
    
    def get_suppliers(self):
        """获取所有供应商"""
        try:
            # 在这里添加从Google Sheets获取供应商数据的代码
            # 目前仅返回模拟数据
            return [
                {"name": "供应商1", "category": "食品"},
                {"name": "供应商2", "category": "电子"}
            ]
        except Exception as e:
            logger.error(f"获取供应商列表时出错: {e}")
            return []
    
    def get_personals(self):
        """获取所有负责人"""
        try:
            # 在这里添加从Google Sheets获取负责人数据的代码
            # 目前仅返回模拟数据
            return [
                {"name": "张三"},
                {"name": "李四"}
            ]
        except Exception as e:
            logger.error(f"获取负责人列表时出错: {e}")
            return [] 
