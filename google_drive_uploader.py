from __future__ import print_function
import os
import io
import logging
import base64
import json
from typing import Dict, Optional, Union, BinaryIO
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GoogleDriveUploader:
    """Google Drive文件上传工具类"""
    
    # 文件夹ID映射
    FOLDER_IDS = {
        "electricity": os.getenv('DRIVE_FOLDER_ELECTRICITY', "1FXf65K3fY-G4CS49oFr_lxeTltPDrEhh"),  # 电费收据文件夹
        "water": os.getenv('DRIVE_FOLDER_WATER', "1L2viDKNPbuIX01mnLn5VM2VA_1iIavOh"),             # 水费收据文件夹
        "Purchasing": os.getenv('DRIVE_FOLDER_PURCHASING', "1kXKGC9bHMeMmFtPPogrvW0xdbVjOjYF8")    # 购买杂货收据文件夹
    }
    
    # 费用类型映射到文件夹类型
    EXPENSE_TYPE_MAPPING = {
        "Electricity Bill": "electricity",
        "Water Bill": "water",
        "Purchasing": "Purchasing"
    }
    
    def __init__(self, credentials_file='credentials.json'):
        """
        初始化Google Drive上传器
        
        Args:
            credentials_file: 服务账号凭证JSON文件路径
        """
        self.credentials_file = credentials_file
        self.drive_service = None
        self._initialize_service()
    
    def _initialize_service(self):
        """初始化Google Drive服务"""
        try:
            # 定义需要的权限范围
            SCOPES = ['https://www.googleapis.com/auth/drive']
            
            # 尝试不同方式获取凭证
            credentials = None
            
            # 1. 尝试从环境变量获取Base64编码的凭证
            creds_base64 = os.getenv('GOOGLE_CREDENTIALS_BASE64')
            if creds_base64:
                try:
                    creds_json = base64.b64decode(creds_base64).decode('utf-8')
                    creds_info = json.loads(creds_json)
                    credentials = service_account.Credentials.from_service_account_info(
                        creds_info, scopes=SCOPES)
                    logger.info("从环境变量GOOGLE_CREDENTIALS_BASE64加载凭证成功")
                except Exception as e:
                    logger.warning(f"从环境变量GOOGLE_CREDENTIALS_BASE64加载凭证失败: {e}")
            
            # 2. 尝试从环境变量获取JSON内容
            if not credentials:
                creds_content = os.getenv('GOOGLE_CREDENTIALS_CONTENT')
                if creds_content:
                    try:
                        creds_info = json.loads(creds_content)
                        credentials = service_account.Credentials.from_service_account_info(
                            creds_info, scopes=SCOPES)
                        logger.info("从环境变量GOOGLE_CREDENTIALS_CONTENT加载凭证成功")
                    except Exception as e:
                        logger.warning(f"从环境变量GOOGLE_CREDENTIALS_CONTENT加载凭证失败: {e}")
            
            # 3. 尝试从文件加载凭证
            if not credentials:
                # 检查环境变量中的文件路径
                file_path = os.getenv('GOOGLE_CREDENTIALS_FILE', self.credentials_file)
                if os.path.exists(file_path):
                    try:
                        credentials = service_account.Credentials.from_service_account_file(
                            file_path, scopes=SCOPES)
                        logger.info(f"从文件 {file_path} 加载凭证成功")
                    except Exception as e:
                        logger.warning(f"从文件 {file_path} 加载凭证失败: {e}")
            
            # 如果所有方法都失败，抛出异常
            if not credentials:
                raise ValueError("无法获取Google API凭证，请检查环境变量或凭证文件")
            
            # 构建Drive服务
            self.drive_service = build('drive', 'v3', credentials=credentials)
            logger.info("Google Drive服务初始化成功")
        except Exception as e:
            logger.error(f"初始化Google Drive服务失败: {e}")
            raise
    
    def _get_folder_id(self, expense_type: str) -> Optional[str]:
        """
        根据费用类型获取对应的文件夹ID
        
        Args:
            expense_type: 费用类型
            
        Returns:
            文件夹ID或None
        """
        # 首先尝试从映射中获取
        folder_type = self.EXPENSE_TYPE_MAPPING.get(expense_type, expense_type)
        folder_id = self.FOLDER_IDS.get(folder_type)
        
        # 如果没有找到，尝试从环境变量获取默认文件夹ID
        if not folder_id:
            folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
            
        return folder_id
    
    def upload_receipt(self, file_path_or_stream, receipt_type_or_name, mime_type='image/jpeg'):
        """
        根据收据类型上传文件到指定Google Drive文件夹
        
        Args:
            file_path_or_stream: 本地文件路径或文件流对象
            receipt_type_or_name: 收据类型("electricity", "water", "Purchasing")或文件名
                                  如果是文件名，将使用默认文件夹
            mime_type: 文件MIME类型
        
        Returns:
            dict: 包含文件ID和公开链接的字典，或者直接返回公开链接字符串(兼容旧代码)
        """
        try:
            # 确定是文件路径还是文件流
            is_file_path = isinstance(file_path_or_stream, str)
            
            # 获取文件名
            if is_file_path:
                file_name = os.path.basename(file_path_or_stream)
            else:
                # 如果receipt_type_or_name是字符串但不是已知的收据类型，可能是文件名
                if isinstance(receipt_type_or_name, str) and receipt_type_or_name not in self.EXPENSE_TYPE_MAPPING and receipt_type_or_name not in self.FOLDER_IDS:
                    file_name = receipt_type_or_name
                else:
                    # 生成默认文件名
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = f"receipt_{timestamp}.jpg"
            
            # 获取目标文件夹ID
            folder_id = None
            if isinstance(receipt_type_or_name, str):
                folder_id = self._get_folder_id(receipt_type_or_name)
            
            # 创建文件元数据
            file_metadata = {
                'name': file_name,
            }
            if folder_id:
                file_metadata['parents'] = [folder_id]
            
            # 创建媒体对象
            if is_file_path:
                if not os.path.exists(file_path_or_stream):
                    raise FileNotFoundError(f"文件不存在: {file_path_or_stream}")
                
                # 获取文件MIME类型
                if mime_type == 'image/jpeg':
                    mime_type = self._get_mime_type(file_path_or_stream)
                
                media = MediaFileUpload(file_path_or_stream, mimetype=mime_type, resumable=True)
            else:
                media = MediaIoBaseUpload(file_path_or_stream, mimetype=mime_type, resumable=True)
            
            # 执行上传
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            file_id = file.get('id')
            
            # 设置文件权限为"任何人都可以查看"
            self.drive_service.permissions().create(
                fileId=file_id,
                body={'type': 'anyone', 'role': 'reader'},
                fields='id'
            ).execute()
            
            public_link = file.get('webViewLink', '')
            
            logger.info(f"文件 '{file_name}' 上传成功，文件ID: {file_id}")
            logger.info(f"公开链接: {public_link}")
            
            # 为了兼容旧代码，如果调用方式是旧的，则直接返回链接
            if not is_file_path and not isinstance(receipt_type_or_name, str):
                return public_link
            
            # 否则返回包含ID和链接的字典
            return {
                'file_id': file_id,
                'public_link': public_link
            }
            
        except Exception as e:
            logger.error(f"上传文件失败: {e}")
            if not is_file_path and not isinstance(receipt_type_or_name, str):
                return None  # 兼容旧代码
            raise
    
    def upload_receipt_to_drive(self, file_stream, file_name, mime_type='image/jpeg'):
        """
        上传收据到Google Drive并返回公开链接 (兼容旧代码)
        
        Args:
            file_stream: 文件流对象
            file_name: 文件名
            mime_type: 文件MIME类型
            
        Returns:
            str: 文件的公开链接
        """
        return self.upload_receipt(file_stream, file_name, mime_type)
    
    def _get_mime_type(self, file_path):
        """根据文件扩展名获取MIME类型"""
        extension = os.path.splitext(file_path)[1].lower()
        
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.pdf': 'application/pdf',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        }
        
        return mime_types.get(extension, 'application/octet-stream')


# 创建全局实例，方便直接导入使用
drive_uploader = GoogleDriveUploader()

# 示例用法
if __name__ == "__main__":
    try:
        # 创建上传器实例
        uploader = GoogleDriveUploader('credentials.json')
        
        # 示例：上传电费收据
        result = uploader.upload_receipt('path/to/electricity_bill.jpg', 'electricity')
        print(f"电费收据上传成功! 文件ID: {result['file_id']}")
        print(f"公开链接: {result['public_link']}")
        
        # 示例：上传水费收据
        result = uploader.upload_receipt('path/to/water_bill.pdf', 'water')
        print(f"水费收据上传成功! 文件ID: {result['file_id']}")
        print(f"公开链接: {result['public_link']}")
        
        # 示例：上传购物收据
        result = uploader.upload_receipt('path/to/purchase_receipt.png', 'Purchasing')
        print(f"购物收据上传成功! 文件ID: {result['file_id']}")
        print(f"公开链接: {result['public_link']}")
        
        # 示例：使用费用类型映射
        result = uploader.upload_receipt('path/to/electricity_bill.jpg', 'Electricity Bill')
        print(f"电费收据上传成功! 文件ID: {result['file_id']}")
        
    except Exception as e:
        print(f"错误: {e}") 
