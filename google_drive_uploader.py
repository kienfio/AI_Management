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
import mimetypes

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GoogleDriveUploader:
    """Google Drive文件上传工具类"""
    
    # 文件夹ID映射
    def __init__(self, credentials_file='credentials.json'):
        """
        初始化Google Drive上传器
        
        Args:
            credentials_file: 服务账号凭证JSON文件路径
        """
        self.credentials_file = credentials_file
        self.drive_service = None
        # 延迟初始化FOLDER_IDS，确保环境变量已经设置
        self.FOLDER_IDS = {}
        self.EXPENSE_TYPE_MAPPING = {
            "Electricity Bill": "electricity",
            "Water Bill": "water",
            "Purchasing": "Purchasing",
            "WiFi Bill": "wifi",
            "Other": "Other",
            "Other Expense": "Other",
            "Other Bill": "Other"  # 添加Other Bill映射
        }
        self._initialize_folders()
        self._initialize_service()
    
    def _initialize_folders(self):
        """初始化文件夹ID映射，确保使用最新的环境变量"""
        self.FOLDER_IDS = {
            "electricity": os.getenv('DRIVE_FOLDER_ELECTRICITY'),  # 电费收据文件夹
            "water": os.getenv('DRIVE_FOLDER_WATER'),             # 水费收据文件夹
            "Purchasing": os.getenv('DRIVE_FOLDER_PURCHASING', '10t-PQiLF91bUrF3oqOCaSJvBuXDzVb9i'),    # 购买杂货收据文件夹
            "wifi": os.getenv('DRIVE_FOLDER_WIFI'),                # WiFi收据文件夹
            "invoice_pdf": os.getenv('DRIVE_FOLDER_INVOICE_PDF'),   # 发票PDF文件夹
            "supplier_other": os.getenv('DRIVE_FOLDER_SUPPLIER_OTHER', '10t-PQiLF91bUrF3oqOCaSJvBuXDzVb9i'),  # Purchasing > Other的自定义供应商文件夹
            "Other": os.getenv('DRIVE_FOLDER_PURCHASING_OTHER')    # Other类型的费用文件夹
        }
        # 单独记录各类文件夹ID，确保正确设置
        other_folder_id = os.getenv('DRIVE_FOLDER_PURCHASING_OTHER')
        purchasing_folder_id = os.getenv('DRIVE_FOLDER_PURCHASING')
        supplier_other_folder_id = os.getenv('DRIVE_FOLDER_SUPPLIER_OTHER')
        
        logger.info(f"🔹 Other文件夹ID: {other_folder_id}")
        logger.info(f"🔹 Purchasing文件夹ID: {purchasing_folder_id}")
        logger.info(f"🔹 Supplier Other文件夹ID: {supplier_other_folder_id}")
        
        # 检查文件夹ID是否正确设置
        if not purchasing_folder_id:
            logger.warning("⚠️ DRIVE_FOLDER_PURCHASING环境变量未设置或为空")
        
        logger.info(f"已初始化文件夹ID映射: {self.FOLDER_IDS}")
    
    def reinitialize(self):
        """重新初始化上传器，确保使用最新的环境变量"""
        self._initialize_folders()
        if not self.drive_service:
            self._initialize_service()
        return self
    
    def _initialize_service(self):
        """初始化Google Drive服务"""
        try:
            # 添加详细日志
            logger.info("正在初始化Google Drive服务")
            logger.info(f"环境变量: GOOGLE_CREDENTIALS_BASE64={os.getenv('GOOGLE_CREDENTIALS_BASE64')[:10] + '...' if os.getenv('GOOGLE_CREDENTIALS_BASE64') else 'Not set'}")
            
            # ✅ 第三步：加日志打印环境变量
            logger.info(f"[ENV] GOOGLE_CREDENTIALS_BASE64 starts with: {os.getenv('GOOGLE_CREDENTIALS_BASE64')[:10] if os.getenv('GOOGLE_CREDENTIALS_BASE64') else 'Not set'}")
            logger.info(f"[ENV] DRIVE_FOLDER_INVOICE_PDF: {os.getenv('DRIVE_FOLDER_INVOICE_PDF')}")
            
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
        """根据费用类型获取对应的文件夹ID"""
        logger.info(f"获取文件夹ID，费用类型: {expense_type}")
        
        # 记录原始expense_type以便调试
        logger.info(f"💼 _get_folder_id 原始类型: '{expense_type}'")
        
        # 1. 优先处理发票PDF专用文件夹
        if expense_type == "invoice_pdf":
            folder_id = os.getenv('DRIVE_FOLDER_INVOICE_PDF')
            logger.info(f"发票PDF专用文件夹ID: {folder_id}")
            return folder_id
        
        # 1.5 处理自定义供应商(supplier_other)类型
        if expense_type.lower() == "supplier_other":
            # 获取供应商other文件夹ID，如果不存在，则使用Purchasing文件夹ID作为备选
            folder_id = self.FOLDER_IDS.get("supplier_other")
            if not folder_id:
                folder_id = self.FOLDER_IDS.get("Purchasing")
                logger.info(f"自定义供应商文件夹ID未设置，使用Purchasing文件夹ID作为备选: {folder_id}")
            logger.info(f"自定义供应商文件夹ID: {folder_id}")
            return folder_id
        
        # 1.55 处理采购(Purchasing)类型
        if expense_type == "Purchasing" or expense_type == "purchasing":
            folder_id = self.FOLDER_IDS.get("Purchasing")
            logger.info(f"采购类型文件夹ID: {folder_id}")
            return folder_id
            
        # 1.6 处理Other类型支出 - 使用大小写不敏感比较
        if expense_type.lower() in ["other", "other expense"] or expense_type.lower().startswith("other bill"):
            folder_id = self.FOLDER_IDS.get("Other")
            logger.info(f"Other类型支出文件夹ID: {folder_id}, 原始类型: {expense_type}")
            return folder_id
        
        # 2. 处理其他费用类型
        folder_type = self.EXPENSE_TYPE_MAPPING.get(expense_type, expense_type)
        folder_id = self.FOLDER_IDS.get(folder_type)
        
        # 3. 特殊处理 WiFi Bill
        if expense_type == "WiFi Bill" and not folder_id:
            folder_id = self.FOLDER_IDS.get("wifi")
            logger.info(f"特殊处理 WiFi Bill，获取wifi文件夹ID: {folder_id}")
        
        # 4. 如果没有找到，尝试从环境变量获取默认文件夹ID
        if not folder_id:
            folder_id = os.getenv('GOOGLE_DRIVE_FOLDER_ID')
        
        logger.info(f"最终使用的文件夹ID: {folder_id}")
        return folder_id
    
    def detect_mime_type(self, file_path_or_stream, fallback_name=None):
        """
        自动检测文件的 MIME 类型（支持路径或文件流）
        
        Args:
            file_path_or_stream: 文件路径(str) 或 文件流对象(BytesIO)
            fallback_name: 若为文件流时，额外提供的文件名以辅助判断
        
        Returns:
            str: MIME 类型字符串，例如 'application/pdf' 或 'image/jpeg'
        """
        logger.info(f"尝试检测MIME类型: path_or_stream={type(file_path_or_stream)}, fallback_name={fallback_name}")
        
        if isinstance(file_path_or_stream, str):
            mime_type, _ = mimetypes.guess_type(file_path_or_stream)
            logger.info(f"从文件路径检测MIME类型: {file_path_or_stream} -> {mime_type}")
            return mime_type or 'application/octet-stream'
        
        elif hasattr(file_path_or_stream, 'name'):  # 文件流带有 name 属性
            mime_type, _ = mimetypes.guess_type(file_path_or_stream.name)
            logger.info(f"从文件流name属性检测MIME类型: {file_path_or_stream.name} -> {mime_type}")
            return mime_type or 'application/octet-stream'
        
        elif fallback_name:  # 人工指定文件名作为辅助判断
            mime_type, _ = mimetypes.guess_type(fallback_name)
            logger.info(f"从fallback_name检测MIME类型: {fallback_name} -> {mime_type}")
            return mime_type or 'application/octet-stream'
        
        logger.info("无法检测MIME类型，使用默认值")
        return 'application/octet-stream'  # 默认兜底
    
    def upload_receipt(self, file_path_or_stream, receipt_type_or_name, mime_type=None):
        """
        根据收据类型上传文件到指定Google Drive文件夹
        
        Args:
            file_path_or_stream: 本地文件路径或文件流对象
            receipt_type_or_name: 收据类型("electricity", "water", "Purchasing", "invoice_pdf")或文件名
                                  如果是文件名，将使用默认文件夹
            mime_type: 文件MIME类型(例如'image/jpeg','application/pdf'等)，如未指定则自动检测
        
        Returns:
            dict: 包含文件ID和公开链接的字典，或者直接返回公开链接字符串(兼容旧代码)
        """
        try:
            # 强制记录日志
            logger.info(f"⏫ 开始上传文件 | 类型: {receipt_type_or_name} | MIME: {mime_type}")
            
            # 预处理收据类型 - 处理特殊格式
            processed_type = receipt_type_or_name
            if isinstance(receipt_type_or_name, str):
                # 处理"Other Bill: xxx"格式
                if receipt_type_or_name.lower().startswith("other bill:"):
                    processed_type = "Other Bill"
                    logger.info(f"🔄 检测到Other Bill格式，规范化为: {processed_type}")
                # 处理purchasing格式（确保大小写正确）
                elif receipt_type_or_name.lower() == "purchasing":
                    processed_type = "Purchasing"  # 使用正确的大小写
                    logger.info(f"🔄 统一Purchasing大小写: {processed_type}")
                # 处理supplier_other格式
                elif receipt_type_or_name.lower() == "supplier_other":
                    processed_type = "supplier_other"  # 保持原样
                    logger.info(f"🔄 检测到supplier_other类型: {processed_type}")
            
            # 添加PDF专用上传逻辑
            if processed_type == "invoice_pdf":
                logger.info("🔄 使用PDF专用上传逻辑")
                return self._upload_invoice_pdf(file_path_or_stream, mime_type)
            
            # 如果未传入 mime_type，则自动检测
            if mime_type is None:
                mime_type = self.detect_mime_type(file_path_or_stream, fallback_name=receipt_type_or_name)
            
            # 添加日志，记录上传参数
            logger.info(f"上传收据，类型: {receipt_type_or_name}, MIME类型: {mime_type}")
            
            # 确定是文件路径还是文件流
            is_file_path = isinstance(file_path_or_stream, str)
            
            # 获取文件名
            if is_file_path:
                file_name = os.path.basename(file_path_or_stream)
            else:
                # 如果receipt_type_or_name是字符串但不是已知的收据类型，可能是文件名
                if isinstance(receipt_type_or_name, str):
                    # 检查是否是已知的费用类型或映射类型
                    is_expense_type = receipt_type_or_name in self.EXPENSE_TYPE_MAPPING or receipt_type_or_name in self.FOLDER_IDS
                    
                    # 如果是已知的费用类型，则生成默认文件名
                    if is_expense_type:
                        from datetime import datetime
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        if receipt_type_or_name == "invoice_pdf":
                            file_name = f"invoice_{timestamp}.pdf"
                        else:
                            file_name = f"receipt_{timestamp}.jpg"
                    else:
                        # 否则，使用提供的字符串作为文件名
                        file_name = receipt_type_or_name
                else:
                    # 生成默认文件名
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    file_name = f"receipt_{timestamp}.jpg"
            
            logger.info(f"使用文件名: {file_name}")
            
            # 获取目标文件夹ID
            folder_id = None
            drive_folder_type = None
            logger.info(f"🔍 收据类型原始值: '{receipt_type_or_name}', 处理后: '{processed_type}'")
            if isinstance(processed_type, str):
                # 处理特殊情况
                if processed_type == "Water Bill":
                    drive_folder_type = "water"
                    folder_id = self._get_folder_id(drive_folder_type)
                    logger.info(f"Water Bill特殊处理，文件夹ID: {folder_id}")
                elif processed_type == "Electricity Bill":
                    drive_folder_type = "electricity"
                    folder_id = self._get_folder_id(drive_folder_type)
                    logger.info(f"Electricity Bill特殊处理，文件夹ID: {folder_id}")
                elif processed_type == "WiFi Bill":
                    drive_folder_type = "wifi"
                    folder_id = self.FOLDER_IDS.get(drive_folder_type)
                    logger.info(f"WiFi Bill特殊处理，直接获取wifi文件夹ID: {folder_id}")
                elif processed_type == "invoice_pdf":
                    drive_folder_type = "invoice_pdf"
                    folder_id = self.FOLDER_IDS.get(drive_folder_type)
                    logger.info(f"Invoice PDF特殊处理，直接获取invoice_pdf文件夹ID: {folder_id}")
                    if not folder_id:
                        folder_id = os.getenv('DRIVE_FOLDER_INVOICE_PDF')
                        logger.info(f"从环境变量获取PDF文件夹ID: {folder_id}")
                    logger.info(f"最终使用的Invoice PDF文件夹ID: {folder_id}")
                # 特殊处理Other Bill类型
                elif processed_type == "Other Bill":
                    drive_folder_type = "Other"
                    folder_id = self.FOLDER_IDS.get(drive_folder_type)
                    logger.info(f"Other Bill特殊处理，使用Other文件夹ID: {folder_id}")
                else:
                    drive_folder_type = self.EXPENSE_TYPE_MAPPING.get(processed_type, processed_type)
                    folder_id = self._get_folder_id(processed_type)
                
                # 日志记录
                logger.info(f"收据类型: {processed_type}, 文件夹ID: {folder_id}")
                # 添加类型映射日志
                logger.info(f"上传类型: {receipt_type_or_name}, 映射后类型: {drive_folder_type or processed_type}")
            
            # 添加文件夹ID调试
            logger.info(f"📁 使用的文件夹ID: {folder_id}")
            
            # 强制使用Other文件夹ID（如果存在）- 用于异常情况处理
            if folder_id is None and processed_type and (
                processed_type.lower() == "other bill" or 
                (isinstance(processed_type, str) and processed_type.lower().startswith("other"))
            ):
                other_folder_id = self.FOLDER_IDS.get("Other")
                if other_folder_id:
                    folder_id = other_folder_id
                    logger.info(f"⚠️ 未找到正常文件夹ID，强制使用Other文件夹ID: {folder_id}")
            
            # 强制使用Purchasing文件夹ID（如果存在）- 用于异常情况处理
            if folder_id is None and processed_type and (
                processed_type == "Purchasing" or 
                (isinstance(processed_type, str) and processed_type.lower() == "purchasing")
            ):
                purchasing_folder_id = self.FOLDER_IDS.get("Purchasing")
                if purchasing_folder_id:
                    folder_id = purchasing_folder_id
                    logger.info(f"⚠️ 未找到正常文件夹ID，强制使用Purchasing文件夹ID: {folder_id}")
            
            # 最后的兜底检查 - 如果仍然没有folder_id，尝试使用备选文件夹
            if folder_id is None:
                logger.warning("⚠️ 所有文件夹ID获取尝试均失败，尝试兜底措施")
                # 对于supplier_other类型，使用Purchasing文件夹作为最后的备选
                if processed_type == "supplier_other" or (isinstance(processed_type, str) and processed_type.lower() == "supplier_other"):
                    folder_id = self.FOLDER_IDS.get("Purchasing", '10t-PQiLF91bUrF3oqOCaSJvBuXDzVb9i')
                    logger.info(f"⚠️ 使用Purchasing文件夹ID作为supplier_other类型的兜底: {folder_id}")
                # 对于Purchasing类型，使用硬编码ID作为最后的备选
                elif processed_type == "Purchasing" or (isinstance(processed_type, str) and processed_type.lower() == "purchasing"):
                    folder_id = '10t-PQiLF91bUrF3oqOCaSJvBuXDzVb9i'  # 直接使用提供的ID
                    logger.info(f"⚠️ 使用硬编码Purchasing文件夹ID作为兜底: {folder_id}")

            # 创建文件元数据
            file_metadata = {
                'name': file_name,
            }
            if folder_id:
                file_metadata['parents'] = [folder_id]
                logger.info(f"设置父文件夹ID: {folder_id}")
            else:
                logger.warning("未找到有效的文件夹ID，文件将上传到根目录")
            
            # 创建媒体对象
            if is_file_path:
                if not os.path.exists(file_path_or_stream):
                    raise FileNotFoundError(f"文件不存在: {file_path_or_stream}")
                
                media = MediaFileUpload(file_path_or_stream, mimetype=mime_type, resumable=True)
                logger.info(f"创建文件上传对象: 文件路径: {file_path_or_stream}, MIME类型: {mime_type}")
            else:
                # 如果是文件流，确保指针在开头
                file_stream = file_path_or_stream
                if hasattr(file_stream, 'seek'):
                    file_stream.seek(0)
                
                media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)
                logger.info(f"创建媒体流上传对象: 文件名: {file_name}, MIME类型: {mime_type}")
            
            # 执行上传
            logger.info("开始上传文件...")
            # 添加上传文件夹信息日志
            logger.info(f"🚨 正在上传到文件夹: {processed_type} (原始:{receipt_type_or_name}) → {folder_id}")
            
            # 针对不同类型添加特定日志
            if processed_type == "Purchasing" or (isinstance(processed_type, str) and processed_type.lower() == "purchasing"):
                purchasing_folder_id = self.FOLDER_IDS.get("Purchasing")
                logger.info(f"🛒 Purchasing检查: 文件夹ID={purchasing_folder_id}, 当前使用={folder_id}")
                
                # 如果没有找到正确的文件夹ID，尝试强制使用Purchasing文件夹
                if folder_id is None and purchasing_folder_id:
                    folder_id = purchasing_folder_id
                    file_metadata['parents'] = [folder_id]
                    logger.info(f"🛒 强制使用Purchasing文件夹ID: {folder_id}")
            
            # 处理supplier_other类型
            if processed_type == "supplier_other" or (isinstance(processed_type, str) and processed_type.lower() == "supplier_other"):
                supplier_other_folder_id = self.FOLDER_IDS.get("supplier_other")
                purchasing_folder_id = self.FOLDER_IDS.get("Purchasing")
                logger.info(f"🏭 Supplier Other检查: supplier_other文件夹ID={supplier_other_folder_id}, purchasing文件夹ID={purchasing_folder_id}, 当前使用={folder_id}")
                
                # 如果没有找到正确的文件夹ID，尝试强制使用supplier_other或Purchasing文件夹
                if folder_id is None:
                    if supplier_other_folder_id:
                        folder_id = supplier_other_folder_id
                    elif purchasing_folder_id:
                        folder_id = purchasing_folder_id
                    
                    if folder_id:
                        file_metadata['parents'] = [folder_id]
                        logger.info(f"🏭 强制使用供应商文件夹ID: {folder_id}")
                        file = self.drive_service.files().create(
                            body=file_metadata,
                            media_body=media,
                            fields='id, webViewLink'
                        ).execute()
                        
                        file_id = file.get('id')
                        logger.info(f"文件上传成功，文件ID: {file_id}")
                        
                        # 设置文件权限为"任何人都可以查看"
                        logger.info("设置文件权限为公开...")
                        self.drive_service.permissions().create(
                            fileId=file_id,
                            body={'type': 'anyone', 'role': 'reader'},
                            fields='id'
                        ).execute()
                        
                        public_link = file.get('webViewLink', '')
                        logger.info(f"生成公开链接: {public_link}")
                        
                        # 记录上传结果的详细信息
                        upload_summary = {
                            "original_type": receipt_type_or_name,
                            "processed_type": processed_type,
                            "folder_id": folder_id,
                            "file_id": file_id,
                            "file_name": file_name
                        }
                        logger.info(f"📊 上传结果摘要: {upload_summary}")
                        
                        # 为了兼容旧代码，如果调用方式是旧的，则直接返回链接
                        if not is_file_path and not isinstance(receipt_type_or_name, str):
                            return public_link
                        
                        # 否则返回包含ID和链接的字典
                        return {
                            'file_id': file_id,
                            'public_link': public_link
                        }
            
            except Exception as e:
                # 详细记录异常
                logger.exception(f"🔥 文件上传严重失败: {str(e)}")
                logger.error(f"📂 上传参数: type={receipt_type_or_name}, mime={mime_type}")
                
                # 如果是HTTP错误，记录响应内容
                if hasattr(e, 'content'):
                    try:
                        error_details = json.loads(e.content)
                        logger.error(f"Google API错误详情: {error_details}")
                    except:
                        logger.error(f"原始错误响应: {e.content}")
                
                if not is_file_path and not isinstance(receipt_type_or_name, str):
                    return None  # 兼容旧代码
                raise
    
    def _upload_invoice_pdf(self, file_stream, mime_type=None):
        """专用方法上传发票PDF到指定文件夹"""
        from datetime import datetime
        
        logger.info("开始上传发票PDF到专用文件夹")
        
        # 确保使用正确的文件夹ID
        folder_id = os.getenv('DRIVE_FOLDER_INVOICE_PDF')
        if not folder_id:
            logger.error("未配置发票PDF文件夹环境变量")
            raise ValueError("未配置发票PDF文件夹环境变量")
        
        # 生成文件名
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"invoice_{timestamp}.pdf"
        
        # 创建文件元数据
        file_metadata = {
            'name': file_name,
            'parents': [folder_id]
        }
        
        # 确保使用正确的MIME类型
        if mime_type is None:
            mime_type = 'application/pdf'
        
        # 创建媒体对象
        if hasattr(file_stream, 'seek'):
            file_stream.seek(0)
        
        media = MediaIoBaseUpload(file_stream, mimetype=mime_type, resumable=True)
        logger.info(f"创建PDF上传对象: 文件名: {file_name}, MIME类型: {mime_type}, 文件夹ID: {folder_id}")
        
        # 执行上传
        logger.info("开始上传PDF文件...")
        file = self.drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        file_id = file.get('id')
        logger.info(f"PDF文件上传成功，文件ID: {file_id}")
        
        # 设置文件权限为"任何人都可以查看"
        logger.info("设置PDF文件权限为公开...")
        self.drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'},
            fields='id'
        ).execute()
        
        public_link = file.get('webViewLink', '')
        logger.info(f"生成PDF公开链接: {public_link}")
        
        # 返回包含ID和链接的字典
        return {
            'file_id': file_id,
            'public_link': public_link
        }
    
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
        
        # 如果是PDF文件,确保使用正确的MIME类型
        if extension == '.pdf':
            logger.info(f"检测到PDF文件: {file_path}")
            return 'application/pdf'
        
        mime_type = mime_types.get(extension, 'application/octet-stream')
        logger.info(f"文件 {file_path} 使用MIME类型: {mime_type}")
        return mime_type


# 创建全局实例，但不立即初始化
drive_uploader = None

def get_drive_uploader():
    """获取或创建GoogleDriveUploader实例"""
    global drive_uploader
    if drive_uploader is None:
        logger.info("🔄 正在初始化Google Drive上传器...")
        drive_uploader = GoogleDriveUploader()
        # 强制初始化服务
        drive_uploader._initialize_service()
        logger.info("✅ Google Drive上传器初始化完成")
    else:
        logger.info("♻️ 使用已存在的Google Drive上传器实例")
    return drive_uploader

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
        
        # 示例：上传发票PDF
        result = uploader.upload_receipt(file_stream, "invoice_pdf", mime_type="application/pdf")
        print(f"发票PDF上传成功! 文件ID: {result['file_id']}")
        print(f"公开链接: {result['public_link']}")
        
    except Exception as e:
        print(f"错误: {e}") 
