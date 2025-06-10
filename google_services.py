import os
import io
import json
import stat
import tempfile
from datetime import datetime
from dotenv import load_dotenv
import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2 import service_account

class GoogleServices:
    """处理与Google服务（Sheets和Drive）的所有交互"""
    
    def __init__(self):
        # 加载环境变量
        load_dotenv()
        
        # 获取凭证文件路径或内容
        credentials_file = os.getenv('GOOGLE_CREDENTIALS_FILE')
        credentials_content = os.getenv('GOOGLE_CREDENTIALS_CONTENT')
        self.spreadsheet_id = os.getenv('SPREADSHEET_ID')
        self.drive_folder_id = os.getenv('DRIVE_FOLDER_ID')
        
        # 验证必要环境变量
        if not self.spreadsheet_id:
            raise ValueError("未设置SPREADSHEET_ID环境变量")
        if not self.drive_folder_id:
            raise ValueError("未设置DRIVE_FOLDER_ID环境变量")
        
        # 定义所需权限
        self.scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
        
        # 加载凭证
        self.credentials = None
        temp_file_path = None
        
        try:
            # 尝试从环境变量内容获取凭证
            if credentials_content:
                # 安全地解析JSON凭证
                try:
                    credentials_dict = json.loads(credentials_content)
                except json.JSONDecodeError as e:
                    raise ValueError(f"无效的JSON凭证格式: {e}")
                
                # 验证必要字段
                required_fields = ['type', 'project_id', 'private_key_id', 'private_key', 'client_email']
                for field in required_fields:
                    if field not in credentials_dict:
                        raise ValueError(f"凭证中缺少必要字段: {field}")
                
                # 创建安全的临时文件
                with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as tmp:
                    # 设置文件权限为仅所有者可读写
                    os.chmod(tmp.name, stat.S_IRUSR | stat.S_IWUSR)
                    json.dump(credentials_dict, tmp)
                    temp_file_path = tmp.name
                
                # 使用临时文件路径加载凭证
                self.credentials = service_account.Credentials.from_service_account_file(
                    temp_file_path, scopes=self.scopes
                )
                
            # 如果没有环境变量内容，尝试从文件读取
            elif credentials_file:
                if not os.path.exists(credentials_file):
                    raise ValueError(f"凭证文件不存在: {credentials_file}")
                self.credentials = service_account.Credentials.from_service_account_file(
                    credentials_file, scopes=self.scopes
                )
            else:
                raise ValueError("未提供Google凭证，请设置GOOGLE_CREDENTIALS_FILE或GOOGLE_CREDENTIALS_CONTENT环境变量")
            
            # 初始化服务
            self.sheets_service = build('sheets', 'v4', credentials=self.credentials)
            self.drive_service = build('drive', 'v3', credentials=self.credentials)
            
            # 检查并创建必要的工作表
            self._setup_sheets()
            
        except Exception as e:
            raise Exception(f"初始化Google服务时出错: {e}")
        finally:
            # 确保临时文件被删除
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except OSError:
                    pass  # 忽略删除失败的情况
    
    def _setup_sheets(self):
        """检查并创建必要的工作表"""
        try:
            # 获取现有工作表
            sheet_metadata = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            sheets = sheet_metadata.get('sheets', [])
            
            # 提取工作表名称
            sheet_names = [sheet['properties']['title'] for sheet in sheets]
            
            # 检查并创建支出工作表
            if '支出' not in sheet_names:
                self._create_sheet('支出', ['日期', '类别', '金额', '描述', '备注', '收据链接'])
            
            # 检查并创建收入工作表
            if '收入' not in sheet_names:
                self._create_sheet('收入', ['日期', '类别', '金额', '描述', '备注'])
            
        except Exception as e:
            raise Exception(f"设置工作表时出错: {e}")
    
    def _create_sheet(self, sheet_name, headers):
        """创建新工作表并添加表头"""
        try:
            # 验证输入参数
            if not sheet_name or not isinstance(sheet_name, str):
                raise ValueError("工作表名称必须是非空字符串")
            if not headers or not isinstance(headers, list):
                raise ValueError("表头必须是非空列表")
            
            # 创建新工作表
            body = {
                'requests': [{
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }]
            }
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=body
            ).execute()
            
            # 添加表头
            if len(headers) > 26:  # Excel列限制
                raise ValueError("表头数量不能超过26个")
            
            range_name = f'{sheet_name}!A1:{chr(65 + len(headers) - 1)}1'
            body = {
                'values': [headers]
            }
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            
        except Exception as e:
            raise Exception(f"创建工作表 {sheet_name} 时出错: {e}")
    
    def _validate_date_format(self, date_str):
        """验证日期格式"""
        try:
            datetime.strptime(date_str, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def _sanitize_input(self, value):
        """清理和验证输入数据"""
        if value is None:
            return ''
        if isinstance(value, str):
            # 移除潜在的恶意字符
            return value.strip()[:500]  # 限制长度
        return str(value)[:500]
    
    def add_expense(self, date, category, amount, description, note='', receipt_url=''):
        """添加支出记录到Google Sheet"""
        try:
            # 验证输入
            if not self._validate_date_format(date):
                raise ValueError("日期格式必须为YYYY-MM-DD")
            
            # 验证金额
            try:
                amount = float(amount)
                if amount < 0:
                    raise ValueError("金额不能为负数")
            except (ValueError, TypeError):
                raise ValueError("金额必须是有效数字")
            
            # 清理输入数据
            category = self._sanitize_input(category)
            description = self._sanitize_input(description)
            note = self._sanitize_input(note)
            receipt_url = self._sanitize_input(receipt_url)
            
            if not category:
                raise ValueError("类别不能为空")
            if not description:
                raise ValueError("描述不能为空")
            
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
            
            return True
            
        except Exception as e:
            raise Exception(f"添加支出记录时出错: {e}")
    
    def add_income(self, date, category, amount, description, note=''):
        """添加收入记录到Google Sheet"""
        try:
            # 验证输入
            if not self._validate_date_format(date):
                raise ValueError("日期格式必须为YYYY-MM-DD")
            
            # 验证金额
            try:
                amount = float(amount)
                if amount < 0:
                    raise ValueError("金额不能为负数")
            except (ValueError, TypeError):
                raise ValueError("金额必须是有效数字")
            
            # 清理输入数据
            category = self._sanitize_input(category)
            description = self._sanitize_input(description)
            note = self._sanitize_input(note)
            
            if not category:
                raise ValueError("类别不能为空")
            if not description:
                raise ValueError("描述不能为空")
            
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
            raise Exception(f"添加收入记录时出错: {e}")
    
    def upload_receipt(self, image_bytes, description):
        """上传收据照片到Google Drive并返回链接"""
        try:
            # 验证输入
            if not image_bytes or len(image_bytes) == 0:
                raise ValueError("图片数据不能为空")
            
            # 限制文件大小 (10MB)
            if len(image_bytes) > 10 * 1024 * 1024:
                raise ValueError("文件大小不能超过10MB")
            
            description = self._sanitize_input(description)
            if not description:
                description = "收据"
            
            # 准备文件元数据
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            # 清理文件名中的特殊字符
            safe_description = "".join(c for c in description if c.isalnum() or c in (' ', '-', '_')).rstrip()
            file_name = f"收据_{timestamp}_{safe_description}.jpg"
            
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
            raise Exception(f"上传收据时出错: {e}")
    
    def get_monthly_summary(self, year=None, month=None):
        """获取指定月份的收支汇总"""
        if year is None or month is None:
            now = datetime.now()
            year = now.year
            month = now.month
        
        # 验证年月输入
        try:
            year = int(year)
            month = int(month)
            if year < 1900 or year > 2100:
                raise ValueError("年份必须在1900-2100之间")
            if month < 1 or month > 12:
                raise ValueError("月份必须在1-12之间")
        except (ValueError, TypeError):
            raise ValueError("年份和月份必须是有效数字")
        
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
                if len(row) >= 3:
                    # 安全的日期匹配
                    date_str = str(row[0]).strip()
                    if date_str.startswith(date_filter):
                        category = str(row[1]).strip()
                        try:
                            amount = float(row[2])
                            if amount >= 0:  # 只处理非负金额
                                total_expense += amount
                                expense_by_category[category] = expense_by_category.get(category, 0) + amount
                        except (ValueError, TypeError):
                            continue  # 跳过无效金额
            
            # 计算收入
            for row in income_values:
                if len(row) >= 3:
                    # 安全的日期匹配
                    date_str = str(row[0]).strip()
                    if date_str.startswith(date_filter):
                        category = str(row[1]).strip()
                        try:
                            amount = float(row[2])
                            if amount >= 0:  # 只处理非负金额
                                total_income += amount
                                income_by_category[category] = income_by_category.get(category, 0) + amount
                        except (ValueError, TypeError):
                            continue  # 跳过无效金额
            
            # 准备汇总数据
            summary = {
                'year': year,
                'month': month,
                'total_income': round(total_income, 2),
                'total_expense': round(total_expense, 2),
                'net': round(total_income - total_expense, 2),
                'expense_by_category': {k: round(v, 2) for k, v in expense_by_category.items()},
                'income_by_category': {k: round(v, 2) for k, v in income_by_category.items()}
            }
            
            return summary
            
        except Exception as e:
            raise Exception(f"获取月度汇总时出错: {e}")
